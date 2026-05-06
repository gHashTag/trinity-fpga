#![doc = include_str!("../README.md")]

use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{Context, Result, bail};
use trios_fpga_fp00::BoardConfig;

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
}
