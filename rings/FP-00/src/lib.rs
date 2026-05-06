#![doc = include_str!("../README.md")]

use std::net::IpAddr;

pub const TRINITY_ANCHOR: f64 = 3.0;

pub const IDCODE_ARTIX7_200T: u32 = 0x0362D093;
pub const IDCODE_ARTIX7_100T: u32 = 0x03631093;
pub const XVC_DEFAULT_PORT: u16 = 2542;
pub const BITSTREAM_SIZE_APPROX: usize = 3_800_000;
pub const DEFAULT_CLOCK_MHZ: f64 = 81.25;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct BoardConfig {
    pub name: &'static str,
    pub idcode: u32,
    pub bitstream_size_approx: usize,
    pub clock_mhz: f64,
}

pub const ARTIX7_200T: BoardConfig = BoardConfig {
    name: "XC7A200T",
    idcode: IDCODE_ARTIX7_200T,
    bitstream_size_approx: BITSTREAM_SIZE_APPROX,
    clock_mhz: DEFAULT_CLOCK_MHZ,
};

pub const ARTIX7_100T: BoardConfig = BoardConfig {
    name: "XC7A100T",
    idcode: IDCODE_ARTIX7_100T,
    bitstream_size_approx: 2_600_000,
    clock_mhz: DEFAULT_CLOCK_MHZ,
};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct XvcConfig {
    pub host: IpAddr,
    pub port: u16,
    pub timeout_ms: u64,
}

impl Default for XvcConfig {
    fn default() -> Self {
        Self {
            host: IpAddr::from([192, 168, 1, 100]),
            port: XVC_DEFAULT_PORT,
            timeout_ms: 30_000,
        }
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct JtagConfig {
    pub chain_speed_khz: u32,
    pub retry_count: u32,
}

impl Default for JtagConfig {
    fn default() -> Self {
        Self {
            chain_speed_khz: 15_000,
            retry_count: 3,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TritValue {
    Zero,
    PlusOne,
    MinusOne,
}

impl TritValue {
    pub fn to_bits(self) -> u8 {
        match self {
            TritValue::Zero => 0b00,
            TritValue::PlusOne => 0b01,
            TritValue::MinusOne => 0b10,
        }
    }

    pub fn from_bits(bits: u8) -> Option<Self> {
        match bits & 0b11 {
            0b00 => Some(TritValue::Zero),
            0b01 => Some(TritValue::PlusOne),
            0b10 => Some(TritValue::MinusOne),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VsaOp {
    Bind,
    Unbind,
    Bundle,
}

impl VsaOp {
    pub fn code(self) -> u8 {
        match self {
            VsaOp::Bind => 0,
            VsaOp::Unbind => 1,
            VsaOp::Bundle => 2,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trinity_anchor() {
        let phi: f64 = (1.0 + 5.0f64.sqrt()) / 2.0;
        let lhs = phi.powi(2) + phi.powi(-2);
        assert!((lhs - TRINITY_ANCHOR).abs() < 1e-12);
    }

    #[test]
    fn idcode_artix7_200t() {
        assert_eq!(ARTIX7_200T.idcode, 0x0362D093);
        assert_eq!(ARTIX7_200T.name, "XC7A200T");
    }

    #[test]
    fn idcode_artix7_100t() {
        assert_eq!(ARTIX7_100T.idcode, 0x03631093);
    }

    #[test]
    fn xvc_default_port() {
        assert_eq!(XvcConfig::default().port, 2542);
    }

    #[test]
    fn trit_roundtrip() {
        for val in [TritValue::Zero, TritValue::PlusOne, TritValue::MinusOne] {
            assert_eq!(TritValue::from_bits(val.to_bits()), Some(val));
        }
    }

    #[test]
    fn trit_invalid() {
        assert_eq!(TritValue::from_bits(0b11), None);
    }

    #[test]
    fn vsa_op_codes() {
        assert_eq!(VsaOp::Bind.code(), 0);
        assert_eq!(VsaOp::Unbind.code(), 1);
        assert_eq!(VsaOp::Bundle.code(), 2);
    }

    #[test]
    fn board_config_serialization() {
        let cfg = XvcConfig::default();
        let json = serde_json::to_string(&cfg).unwrap();
        let back: XvcConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(cfg.port, back.port);
        assert_eq!(cfg.timeout_ms, back.timeout_ms);
    }
}
