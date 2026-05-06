#![doc = include_str!("../README.md")]

use std::io::{Read, Write};
use std::net::TcpStream;
use std::path::Path;
use std::time::Duration;

use anyhow::{Context, Result, bail};
use trios_fpga_fp00::{BoardConfig, JtagConfig, XvcConfig};

const XVC_INFO_CMD: &[u8] = b"getinfo:";
const _XVC_SHIFT_CMD: &[u8] = b"shift:";
const _XVC_SET_FREQ_CMD: &[u8] = b"settck:";

#[derive(Debug)]
pub struct FlashResult {
    pub bytes_written: usize,
    pub idcode: u32,
    pub elapsed: Duration,
}

#[derive(Debug)]
pub enum FlashError {
    Connection(String),
    Protocol(String),
    Verify { expected: u32, got: u32 },
    Timeout,
}

impl std::fmt::Display for FlashError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            FlashError::Connection(e) => write!(f, "connection: {e}"),
            FlashError::Protocol(e) => write!(f, "protocol: {e}"),
            FlashError::Verify { expected, got } => {
                write!(f, "IDCODE mismatch: expected 0x{expected:08X}, got 0x{got:08X}")
            }
            FlashError::Timeout => write!(f, "timeout"),
        }
    }
}
impl std::error::Error for FlashError {}

pub struct XvcFlasher {
    pub xvc: XvcConfig,
    pub jtag: JtagConfig,
    pub board: &'static BoardConfig,
}

impl XvcFlasher {
    pub fn new(xvc: XvcConfig, board: &'static BoardConfig) -> Self {
        Self {
            xvc,
            jtag: JtagConfig::default(),
            board,
        }
    }

    pub fn connect(&self) -> Result<XvcConnection> {
        let addr = format!("{}:{}", self.xvc.host, self.xvc.port);
        let stream = TcpStream::connect_timeout(
            &addr.parse().with_context(|| format!("parse address {addr}"))?,
            Duration::from_millis(self.xvc.timeout_ms),
        )
        .with_context(|| format!("connect to XVC at {addr}"))?;

        stream.set_read_timeout(Some(Duration::from_millis(self.xvc.timeout_ms)))?;
        stream.set_write_timeout(Some(Duration::from_millis(self.xvc.timeout_ms)))?;

        Ok(XvcConnection { stream })
    }

    pub fn verify_idcode(&self) -> Result<u32> {
        let mut conn = self.connect()?;
        let _info = conn.get_info().context("get XVC info")?;

        conn.shift_ir(&[0xE0], 6)?;
        let idcode = conn.read_dr(32)?;

        if idcode != self.board.idcode {
            bail!(FlashError::Verify {
                expected: self.board.idcode,
                got: idcode,
            });
        }
        Ok(idcode)
    }

    pub fn flash(&self, bitstream: &[u8]) -> Result<FlashResult> {
        let start = std::time::Instant::now();
        let mut conn = self.connect()?;

        let idcode = {
            conn.shift_ir(&[0xE0], 6)?;
            conn.read_dr(32)?
        };

        if idcode != self.board.idcode {
            bail!(FlashError::Verify {
                expected: self.board.idcode,
                got: idcode,
            });
        }

        conn.shift_ir(&[0x01], 6)?;
        let nbytes = bitstream.len();
        let addr_bytes = 0u32.to_le_bytes();
        let len_bytes = (nbytes as u32).to_le_bytes();
        conn.shift_dr(&addr_bytes, 32)?;
        conn.shift_dr(&len_bytes, 32)?;

        for chunk in bitstream.chunks(256) {
            conn.shift_dr(chunk, (chunk.len() * 8) as u32)?;
        }

        conn.shift_ir(&[0x07], 6)?;
        let busy = conn.read_dr(1)?;
        if busy & 1 != 0 {
            bail!("device busy after programming");
        }

        conn.shift_ir(&[0x3C], 6)?;

        Ok(FlashResult {
            bytes_written: nbytes,
            idcode,
            elapsed: start.elapsed(),
        })
    }

    pub fn flash_file(&self, path: &Path) -> Result<FlashResult> {
        let data = std::fs::read(path)
            .with_context(|| format!("read bitstream {}", path.display()))?;
        self.flash(&data)
    }

    pub fn status(&self) -> Result<DeviceStatus> {
        let mut conn = self.connect()?;
        let idcode = {
            conn.shift_ir(&[0xE0], 6)?;
            conn.read_dr(32)?
        };

        let done = {
            conn.shift_ir(&[0x3C], 6)?;
            let status = conn.read_dr(32)?;
            (status & (1 << 14)) != 0
        };

        Ok(DeviceStatus { idcode, done })
    }
}

#[derive(Debug)]
pub struct DeviceStatus {
    pub idcode: u32,
    pub done: bool,
}

pub struct XvcConnection {
    stream: TcpStream,
}

#[derive(Debug)]
pub struct XvcInfo {
    pub version: String,
    pub max_bits: u32,
}

impl XvcConnection {
    pub fn get_info(&mut self) -> Result<XvcInfo> {
        self.stream.write_all(XVC_INFO_CMD)?;
        self.stream.flush()?;

        let mut buf = [0u8; 256];
        let n = self.stream.read(&mut buf)?;
        let resp = String::from_utf8_lossy(&buf[..n]);
        let parts: Vec<&str> = resp.split(':').collect();

        if parts.len() < 2 {
            bail!("invalid XVC info response: {resp}");
        }

        Ok(XvcInfo {
            version: parts[0].to_string(),
            max_bits: parts[1].trim().parse().unwrap_or(0),
        })
    }

    pub fn shift_ir(&mut self, tdi: &[u8], bits: u32) -> Result<()> {
        self.xvc_shift(bits, tdi, &vec![0xFFu8; tdi.len()])
    }

    pub fn shift_dr(&mut self, tdi: &[u8], bits: u32) -> Result<()> {
        self.xvc_shift(bits, tdi, &vec![0xFFu8; tdi.len()])
    }

    pub fn read_dr(&mut self, bits: u32) -> Result<u32> {
        let nbytes = bits.div_ceil(8) as usize;
        let tdi = vec![0u8; nbytes];
        let tdo = self.xvc_read(bits, &tdi)?;
        let mut result = 0u32;
        for (i, &b) in tdo.iter().enumerate() {
            result |= (b as u32) << (i * 8);
        }
        Ok(result)
    }

    fn xvc_shift(&mut self, bits: u32, tdi: &[u8], tms: &[u8]) -> Result<()> {
        let hdr = format!("shift:{}:", bits);
        self.stream.write_all(hdr.as_bytes())?;
        self.stream.write_all(tdi)?;
        self.stream.write_all(tms)?;
        self.stream.flush()?;

        let nbytes = bits.div_ceil(8) as usize;
        let mut tdo = vec![0u8; nbytes];
        self.stream.read_exact(&mut tdo)?;
        Ok(())
    }

    fn xvc_read(&mut self, bits: u32, tdi: &[u8]) -> Result<Vec<u8>> {
        let hdr = format!("shift:{}:", bits);
        let tms = vec![0u8; tdi.len()];
        self.stream.write_all(hdr.as_bytes())?;
        self.stream.write_all(tdi)?;
        self.stream.write_all(&tms)?;
        self.stream.flush()?;

        let nbytes = bits.div_ceil(8) as usize;
        let mut tdo = vec![0u8; nbytes];
        self.stream.read_exact(&mut tdo)?;
        Ok(tdo)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use trios_fpga_fp00::ARTIX7_200T;

    #[test]
    fn flasher_creation() {
        let xvc = XvcConfig::default();
        let flasher = XvcFlasher::new(xvc, &ARTIX7_200T);
        assert_eq!(flasher.board.idcode, 0x0362D093);
        assert_eq!(flasher.xvc.port, 2542);
    }

    #[test]
    fn device_status_display() {
        let status = DeviceStatus {
            idcode: 0x0362D093,
            done: true,
        };
        assert!(status.done);
        assert_eq!(status.idcode, 0x0362D093);
    }

    #[test]
    fn flash_error_display() {
        let err = FlashError::Verify {
            expected: 0x0362D093,
            got: 0xDEAD,
        };
        let msg = format!("{err}");
        assert!(msg.contains("0362D093"));
        assert!(msg.contains("0000DEAD"));
    }

    #[test]
    fn jtag_config_defaults() {
        let cfg = JtagConfig::default();
        assert_eq!(cfg.chain_speed_khz, 15_000);
        assert_eq!(cfg.retry_count, 3);
    }
}
