# TASK — BR-BITSTREAM

Ring: BR-BITSTREAM (CLI Binary Ring)
Priority: P1

## Done

- [x] clap-based CLI with flash/synth/status/verify subcommands
- [x] XVC host/port/timeout configurable via CLI args
- [x] Board selection (XC7A200T)
- [x] Flash: bitstream file → FPGA via XVC
- [x] Synth: RTL dir → bitstream via openxc7 Docker
- [x] Status: IDCODE + DONE flag
- [x] Verify: IDCODE match check

## Next

Integration testing with real hardware
