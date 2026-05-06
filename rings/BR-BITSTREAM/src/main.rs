use std::net::IpAddr;
use std::path::PathBuf;

use clap::{Parser, Subcommand};
use trios_fpga_fp00::{BoardConfig, XvcConfig, ARTIX7_200T};

#[derive(Parser)]
#[command(name = "trios-fpga", version, about = "FPGA synthesis, flash and verify via XVC WiFi JTAG")]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    #[arg(long, default_value = "192.168.1.100")]
    xvc_host: String,

    #[arg(long, default_value_t = 2542)]
    xvc_port: u16,

    #[arg(long, default_value_t = 30_000)]
    timeout_ms: u64,
}

#[derive(Subcommand)]
enum Commands {
    Flash {
        #[arg(long)]
        bitstream: PathBuf,
        #[arg(long, default_value = "XC7A200T")]
        board: String,
    },
    Synth {
        #[arg(long)]
        rtl_dir: PathBuf,
        #[arg(long)]
        constraints: PathBuf,
        #[arg(long, default_value = "build")]
        output_dir: PathBuf,
        #[arg(long, default_value = "hslm_full_top")]
        top: String,
    },
    Status {},
    Verify {},
}

fn resolve_board(name: &str) -> Option<&'static BoardConfig> {
    match name.to_uppercase().as_str() {
        "XC7A200T" | "ARTIX7-200T" => Some(&ARTIX7_200T),
        _ => None,
    }
}

fn make_xvc_config(cli: &Cli) -> anyhow::Result<XvcConfig> {
    let host: IpAddr = cli
        .xvc_host
        .parse()
        .map_err(|e| anyhow::anyhow!("invalid IP '{}': {}", cli.xvc_host, e))?;
    Ok(XvcConfig {
        host,
        port: cli.xvc_port,
        timeout_ms: cli.timeout_ms,
    })
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    let xvc = make_xvc_config(&cli)?;

    match &cli.command {
        Commands::Flash {
            bitstream,
            board,
        } => {
            let board_cfg = resolve_board(board)
                .ok_or_else(|| anyhow::anyhow!("unknown board '{board}'. Use XC7A200T"))?;
            let flasher = trios_fpga_fp02::XvcFlasher::new(xvc, board_cfg);

            eprintln!("Flashing {} via XVC...", bitstream.display());
            let result = flasher.flash_file(bitstream)?;
            eprintln!(
                "OK: {} bytes, IDCODE=0x{:08X}, {:.2}s",
                result.bytes_written,
                result.idcode,
                result.elapsed.as_secs_f64()
            );
        }

        Commands::Synth {
            rtl_dir,
            constraints,
            output_dir,
            top,
        } => {
            let config = trios_fpga_fp01::SynthConfig::for_board(
                &ARTIX7_200T,
                rtl_dir,
                constraints,
                output_dir,
            );
            let runner = trios_fpga_fp01::OpenXc7Runner::new(config);

            eprintln!("Synthesizing {}...", top);
            let result = runner.synthesize()?;
            eprintln!("OK: {}", result.bit_path.display());
        }

        Commands::Status {} => {
            let flasher = trios_fpga_fp02::XvcFlasher::new(xvc, &ARTIX7_200T);
            let status = flasher.status()?;
            println!(
                "IDCODE: 0x{:08X} | DONE: {}",
                status.idcode,
                if status.done { "YES" } else { "NO" }
            );
        }

        Commands::Verify {} => {
            let flasher = trios_fpga_fp02::XvcFlasher::new(xvc, &ARTIX7_200T);
            let idcode = flasher.verify_idcode()?;
            println!("IDCODE: 0x{idcode:08X} — MATCH");
        }
    }

    Ok(())
}
