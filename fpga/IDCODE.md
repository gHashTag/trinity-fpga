# IDCODE — QMTech XC7A200T (FGG676)

## Raw IDCODE

```
0x13631093
```

## Decoded Fields (IEEE 1149.1)

| Field          | Bits   | Value    | Meaning               |
|----------------|--------|----------|-----------------------|
| Version        | 31:28  | 0x1      | Silicon revision 1    |
| Part Number    | 27:12  | 0x3631   | XC7A200T              |
| Manufacturer   | 11:1   | 0x049    | Xilinx                |
| Required LSB   | 0      | 1        | Valid IDCODE          |

## Part Number Cross-Reference

| Part Number | Device     | Expected IDCODE |
|-------------|------------|-----------------|
| 0x362D      | XC7A100T   | 0x0362D093      |
| 0x3631      | XC7A200T   | 0x03631093      |

The board is labeled "XC7A100T" but the silicon reports part number 0x3631 (XC7A200T) with version=1. This is compatible — XC7A200T is a superset of XC7A100T.

## IR Length

6 bits (standard Xilinx 7-series).

## Detection Command

```bash
openFPGALoader --cable xvc-client --ip 192.168.1.30 --port 2542 --detect
```

Output:
```
found 1 devices
index 0:
	idcode 0x3631093
	manufacturer xilinx
	family artix a7 100t
	model  xc7a100
	irlength 6
```
