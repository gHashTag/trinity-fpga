#![doc = include_str!("../README.md")]

use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{Context, Result, bail};
use trios_fpga_fp00::{BoardConfig, TritValue};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct SynthConfig {
    pub top_module: String,
    pub rtl_sources: Vec<PathBuf>,
    pub constraints: PathBuf,
    pub output_dir: PathBuf,
    pub freq_mhz: f64,
}

impl SynthConfig {
    pub fn for_board(board: &BoardConfig, rtl_dir: &Path, xdc: &Path, out: &Path) -> Self {
        let mut rtl_sources = Vec::new();
        collect_verilog(rtl_dir, &mut rtl_sources);

        Self {
            top_module: "hslm_full_top".to_string(),
            rtl_sources,
            constraints: xdc.to_path_buf(),
            output_dir: out.to_path_buf(),
            freq_mhz: board.clock_mhz,
        }
    }

    pub fn vsa_matmul(board: &BoardConfig, out: &Path) -> Self {
        let vsa_dir = Path::new("fpga/vsa");
        let mut rtl_sources = Vec::new();
        collect_verilog(vsa_dir, &mut rtl_sources);
        Self {
            top_module: "vsa_matmul_top".to_string(),
            rtl_sources,
            constraints: PathBuf::from("fpga/vsa/vsa_matmul_top.xdc"),
            output_dir: out.to_path_buf(),
            freq_mhz: board.clock_mhz,
        }
    }
}

fn collect_verilog(dir: &Path, out: &mut Vec<PathBuf>) {
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let p = entry.path();
            if p.extension().is_some_and(|e| e == "v") {
                out.push(p);
            }
        }
    }
    out.sort();
}

#[derive(Debug)]
pub struct SynthResult {
    pub json_path: PathBuf,
    pub fasm_path: PathBuf,
    pub bit_path: PathBuf,
}

#[derive(Debug)]
pub struct OpenXc7Runner {
    pub config: SynthConfig,
    pub docker_image: String,
}

impl Default for OpenXc7Runner {
    fn default() -> Self {
        Self {
            config: SynthConfig {
                top_module: "hslm_full_top".to_string(),
                rtl_sources: Vec::new(),
                constraints: PathBuf::from("fpga/openxc7-synth/hslm_full_top.xdc"),
                output_dir: PathBuf::from("build"),
                freq_mhz: 81.25,
            },
            docker_image: "regymm/openxc7:latest".to_string(),
        }
    }
}

impl OpenXc7Runner {
    pub fn new(config: SynthConfig) -> Self {
        Self {
            config,
            ..Default::default()
        }
    }

    pub fn synthesize(&self) -> Result<SynthResult> {
        let out = &self.config.output_dir;
        std::fs::create_dir_all(out)
            .with_context(|| format!("create output dir {}", out.display()))?;

        let json_path = out.join(format!("{}.json", self.config.top_module));
        let fasm_path = out.join(format!("{}.fasm", self.config.top_module));
        let bit_path = out.join(format!("{}.bit", self.config.top_module));

        self.run_yosys(&json_path)?;
        self.run_nextpnr(&json_path, &fasm_path)?;
        self.run_fasm2bit(&fasm_path, &bit_path)?;

        Ok(SynthResult {
            json_path,
            fasm_path,
            bit_path,
        })
    }

    fn run_yosys(&self, json_out: &Path) -> Result<()> {
        let rtl_args: Vec<String> = self
            .config
            .rtl_sources
            .iter()
            .map(|p| format!("read_verilog {};", p.display()))
            .collect();

        let yosys_cmd = format!(
            "read_verilog {}; synth_xilinx -flatten -abc9 -arch xc7 -top {}; setundef -zero -params; write_json {}",
            rtl_args.join(" "),
            self.config.top_module,
            json_out.display()
        );

        let output = Command::new("docker")
            .args(["run", "--rm", "-v", &format!("{}:/work", self.config.output_dir.display()), "-w", "/work"])
            .arg(&self.docker_image)
            .args(["yosys", "-p", &yosys_cmd])
            .output()
            .context("run yosys")?;

        if !output.status.success() {
            bail!(
                "yosys failed: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }
        Ok(())
    }

    fn run_nextpnr(&self, json_in: &Path, fasm_out: &Path) -> Result<()> {
        let chipdb = self.config.output_dir.join("chipdb/xc7a100tfgg676-1.bin");
        let xdc = &self.config.constraints;

        let output = Command::new("docker")
            .args(["run", "--rm", "-v", &format!("{}:/work", self.config.output_dir.display()), "-w", "/work"])
            .arg(&self.docker_image)
            .args([
                "nextpnr-xilinx",
                "--chipdb", chipdb.to_str().unwrap_or(""),
                "--xdc", xdc.to_str().unwrap_or(""),
                "--json", json_in.to_str().unwrap_or(""),
                "--fasm", fasm_out.to_str().unwrap_or(""),
                "--freq", &format!("{}", self.config.freq_mhz),
                "--seed", "1",
                "--placer", "sa",
                "--force",
            ])
            .output()
            .context("run nextpnr")?;

        if !output.status.success() {
            bail!(
                "nextpnr failed: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }
        Ok(())
    }

    fn run_fasm2bit(&self, fasm_in: &Path, bit_out: &Path) -> Result<()> {
        let fasm_cmd = format!(
            "source /prjxray/env/bin/activate && \
             fasm2frames --db-root /nextpnr-xilinx/xilinx/external/prjxray-db/artix7 \
             --part xc7a100tfgg676-1 {} {}.frames && \
             /prjxray/build/tools/xc7frames2bit \
             --part_file /nextpnr-xilinx/xilinx/external/prjxray-db/artix7/xc7a100tfgg676-1/part.yaml \
             --part_name xc7a100tfgg676-1 \
             --frm_file {}.frames \
             --output_file {}",
            fasm_in.display(),
            fasm_in.display(),
            fasm_in.display(),
            bit_out.display()
        );

        let output = Command::new("docker")
            .args(["run", "--rm", "-v", &format!("{}:/work", self.config.output_dir.display()), "-w", "/work"])
            .arg(&self.docker_image)
            .args(["bash", "-c", &fasm_cmd])
            .output()
            .context("run fasm2frames + xc7frames2bit")?;

        if !output.status.success() {
            bail!(
                "fasm2bit failed: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }
        Ok(())
    }

    pub fn generate_chipdb(&self, chipdb_dir: &Path) -> Result<PathBuf> {
        std::fs::create_dir_all(chipdb_dir)?;
        let bba_path = chipdb_dir.join("xc7a100tfgg676-1.bba");
        let bin_path = chipdb_dir.join("xc7a100tfgg676-1.bin");

        let cmd = format!(
            "cd /nextpnr-xilinx && \
             python3 xilinx/python/bbaexport.py --device xc7a100tfgg676-1 --bba {} && \
             bbasm -l {} {}",
            bba_path.display(),
            bba_path.display(),
            bin_path.display()
        );

        let output = Command::new("docker")
            .args(["run", "--rm", "-v", &format!("{}:/work", chipdb_dir.display()), "-w", "/work"])
            .arg(&self.docker_image)
            .args(["bash", "-c", &cmd])
            .output()
            .context("generate chipdb")?;

        if !output.status.success() {
            bail!("chipdb generation failed: {}", String::from_utf8_lossy(&output.stderr));
        }
        Ok(bin_path)
    }
}

pub const GF16_MAGIC: u32 = 0x47463136;
pub const GF16_VERSION: u32 = 1;

#[derive(Debug, Clone)]
pub struct Gf16Tensor {
    pub name: String,
    pub rows: u32,
    pub cols: u32,
    pub data: Vec<u16>,
}

#[derive(Debug, Clone)]
pub struct Gf16Binary {
    pub tensors: Vec<Gf16Tensor>,
}

impl Gf16Binary {
    pub fn from_bytes(buf: &[u8]) -> Result<Self> {
        if buf.len() < 16 {
            bail!("GF16 binary too short: {} bytes", buf.len());
        }
        let magic = u32::from_le_bytes(buf[0..4].try_into()?);
        if magic != GF16_MAGIC {
            bail!("bad magic: 0x{magic:08X}, expected 0x{GF16_MAGIC:08X}");
        }
        let version = u32::from_le_bytes(buf[4..8].try_into()?);
        if version != GF16_VERSION {
            bail!("bad version: {version}");
        }
        let n_tensors = u32::from_le_bytes(buf[8..12].try_into()?) as usize;
        let _reserved = u32::from_le_bytes(buf[12..16].try_into()?);

        let mut tensors = Vec::with_capacity(n_tensors);
        let mut off = 16usize;
        for _ in 0..n_tensors {
            if off + 8 > buf.len() {
                bail!("truncated tensor header at offset {off}");
            }
            let rows = u32::from_le_bytes(buf[off..off + 4].try_into()?);
            let cols = u32::from_le_bytes(buf[off + 4..off + 8].try_into()?);
            off += 8;

            let name_len = u32::from_le_bytes(buf[off..off + 4].try_into()?) as usize;
            off += 4;
            if off + name_len > buf.len() {
                bail!("truncated tensor name at offset {off}");
            }
            let name = String::from_utf8(buf[off..off + name_len].to_vec())
                .context("tensor name utf8")?;
            off += name_len;

            let n = (rows * cols) as usize;
            let data_bytes = n * 2;
            if off + data_bytes > buf.len() {
                bail!("truncated tensor data for '{name}' at offset {off}");
            }
            let data: Vec<u16> = (0..n)
                .map(|i| u16::from_le_bytes(buf[off + i * 2..off + i * 2 + 2].try_into().unwrap()))
                .collect();
            off += data_bytes;

            tensors.push(Gf16Tensor { name, rows, cols, data });
        }
        Ok(Gf16Binary { tensors })
    }

    pub fn from_file(path: &Path) -> Result<Self> {
        let mut f = std::fs::File::open(path)
            .with_context(|| format!("open GF16 binary {}", path.display()))?;
        let mut buf = Vec::new();
        f.read_to_end(&mut buf)?;
        Self::from_bytes(&buf)
    }
}

#[derive(Debug, Clone)]
pub struct TernaryWeights {
    pub name: String,
    pub rows: usize,
    pub cols: usize,
    pub packed: Vec<u64>,
}

pub struct TernaryWeightConverter {
    pub threshold: f64,
}

impl Default for TernaryWeightConverter {
    fn default() -> Self {
        Self { threshold: 0.5 }
    }
}

impl TernaryWeightConverter {
    pub fn new(threshold: f64) -> Self {
        Self { threshold }
    }

    pub fn convert_tensor(&self, tensor: &Gf16Tensor) -> TernaryWeights {
        let trits = self.quantize(&tensor.data);
        let packed = Self::pack_trits(&trits);
        TernaryWeights {
            name: tensor.name.clone(),
            rows: tensor.rows as usize,
            cols: tensor.cols as usize,
            packed,
        }
    }

    pub fn quantize(&self, gf16: &[u16]) -> Vec<TritValue> {
        let gf16_max = u16::MAX as f64;
        gf16.iter()
            .map(|&v| {
                let norm = (v as f64) / gf16_max;
                if norm > self.threshold {
                    TritValue::PlusOne
                } else if norm < -self.threshold + 1.0 {
                    let normalized = 2.0 * norm - 1.0;
                    if normalized < -self.threshold {
                        TritValue::MinusOne
                    } else {
                        TritValue::Zero
                    }
                } else {
                    TritValue::Zero
                }
            })
            .collect()
    }

    pub fn pack_trits(trits: &[TritValue]) -> Vec<u64> {
        let n_words = trits.len().div_ceil(32);
        let mut packed = vec![0u64; n_words];
        for (i, t) in trits.iter().enumerate() {
            let word = i / 32;
            let bit_off = (i % 32) * 2;
            packed[word] |= (t.to_bits() as u64) << bit_off;
        }
        packed
    }

    pub fn write_verilog_mem(weights: &TernaryWeights, path: &Path) -> Result<()> {
        let mut lines = Vec::new();
        for (i, word) in weights.packed.iter().enumerate() {
            lines.push(format!("{:064b}", word));
            let _ = i;
        }
        std::fs::write(path, lines.join("\n"))
            .with_context(|| format!("write mem {}", path.display()))?;
        Ok(())
    }

    pub fn write_header(weights: &TernaryWeights, path: &Path) -> Result<()> {
        let sparsity: f64 = {
            let total = weights.rows * weights.cols;
            if total == 0 {
                0.0
            } else {
                let nz = weights.packed.iter().map(|w| w.count_ones() as f64).sum::<f64>() / 2.0;
                1.0 - nz / (total as f64)
            }
        };
        let content = format!(
            "// Ternary weights: {} ({}x{})\n// Packed words: {}\n// Sparsity: {:.1}%\n// Encoding: 2'b00=0, 2'b01=+1, 2'b10=-1\n",
            weights.name,
            weights.rows,
            weights.cols,
            weights.packed.len(),
            sparsity * 100.0,
        );
        std::fs::write(path, content)
            .with_context(|| format!("write header {}", path.display()))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_runner() {
        let runner = OpenXc7Runner::default();
        assert_eq!(runner.config.top_module, "hslm_full_top");
        assert_eq!(runner.docker_image, "regymm/openxc7:latest");
    }

    #[test]
    fn synth_config_for_board() {
        let cfg = SynthConfig::for_board(
            &trios_fpga_fp00::ARTIX7_200T,
            Path::new("fpga/vsa"),
            Path::new("fpga/xdc/qmtech_xc7a.xdc"),
            Path::new("build/test"),
        );
        assert_eq!(cfg.top_module, "hslm_full_top");
        assert_eq!(cfg.freq_mhz, 81.25);
    }

    #[test]
    fn collect_verilog_finds_v_files() {
        let dir = std::env::current_dir().unwrap();
        let vsa_dir = dir.join("fpga/vsa");
        if vsa_dir.exists() {
            let mut files = Vec::new();
            collect_verilog(&vsa_dir, &mut files);
            assert!(!files.is_empty());
            for f in &files {
                assert_eq!(f.extension().unwrap(), "v");
            }
        }
    }

    #[test]
    fn gf16_roundtrip() {
        let mut buf = Vec::new();
        buf.extend_from_slice(&GF16_MAGIC.to_le_bytes());
        buf.extend_from_slice(&1u32.to_le_bytes());
        buf.extend_from_slice(&1u32.to_le_bytes());
        buf.extend_from_slice(&0u32.to_le_bytes());
        buf.extend_from_slice(&2u32.to_le_bytes());
        buf.extend_from_slice(&3u32.to_le_bytes());
        buf.extend_from_slice(&1u32.to_le_bytes());
        buf.extend_from_slice(b"W");
        buf.extend_from_slice(&100u16.to_le_bytes());
        buf.extend_from_slice(&200u16.to_le_bytes());
        buf.extend_from_slice(&300u16.to_le_bytes());
        buf.extend_from_slice(&400u16.to_le_bytes());
        buf.extend_from_slice(&500u16.to_le_bytes());
        buf.extend_from_slice(&600u16.to_le_bytes());
        let gf16 = Gf16Binary::from_bytes(&buf).unwrap();
        assert_eq!(gf16.tensors.len(), 1);
        assert_eq!(gf16.tensors[0].name, "W");
        assert_eq!(gf16.tensors[0].rows, 2);
        assert_eq!(gf16.tensors[0].cols, 3);
        assert_eq!(gf16.tensors[0].data.len(), 6);
    }

    #[test]
    fn ternary_quantize_center() {
        let conv = TernaryWeightConverter::new(0.5);
        let gf16_max = u16::MAX as f64;
        let zero_val = (gf16_max * 0.5) as u16;
        let trits = conv.quantize(&[zero_val]);
        assert_eq!(trits[0], TritValue::Zero);
    }

    #[test]
    fn ternary_quantize_positive() {
        let conv = TernaryWeightConverter::new(0.5);
        let trits = conv.quantize(&[u16::MAX]);
        assert_eq!(trits[0], TritValue::PlusOne);
    }

    #[test]
    fn ternary_quantize_negative() {
        let conv = TernaryWeightConverter::new(0.5);
        let trits = conv.quantize(&[0u16]);
        assert_eq!(trits[0], TritValue::MinusOne);
    }

    #[test]
    fn pack_trits_roundtrip() {
        let trits = vec![
            TritValue::Zero, TritValue::PlusOne, TritValue::MinusOne,
            TritValue::Zero, TritValue::Zero, TritValue::PlusOne,
        ];
        let packed = TernaryWeightConverter::pack_trits(&trits);
        assert_eq!(packed.len(), 1);
        for (i, t) in trits.iter().enumerate() {
            let bits = ((packed[0] >> (i * 2)) & 0b11) as u8;
            assert_eq!(TritValue::from_bits(bits), Some(*t), "mismatch at index {i}");
        }
    }

    #[test]
    fn write_mem_file() {
        let weights = TernaryWeights {
            name: "test".into(),
            rows: 1,
            cols: 4,
            packed: vec![0b01_10_00_01u64],
        };
        let dir = std::env::temp_dir().join("trios-fpga-test-mem");
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("test.mem");
        TernaryWeightConverter::write_verilog_mem(&weights, &path).unwrap();
        let content = std::fs::read_to_string(&path).unwrap();
        assert!(content.contains("01"));
    }
}
