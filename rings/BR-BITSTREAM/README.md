# BR-BITSTREAM — CLI

Command-line interface for trios-fpga.

## Commands

```
trios-fpga flash   --xvc 192.168.1.100 --bitstream ./bitstream/design.bit
trios-fpga synth   --rtl ./fpga/rtl/   --constraints ./fpga/xdc/
trios-fpga status  --xvc 192.168.1.100
trios-fpga verify  --xvc 192.168.1.100  # IDCODE == 0x0362D093
```

## Replaces

- `AUTO_FLASH.sh`
- `status.sh`
- All CLI-related .sh scripts

`phi^2 + 1/phi^2 = 3`
