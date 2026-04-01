# Zig UART Echo Test — Instructions

## Building and Running

```bash
# 1. Build
zig build uart-echo-test

# 2. Run
zig-out/bin/uart-echo-test
```

## What Test Does

1. Scans `/dev/cu.usbserial-*` (macOS) or `/dev/ttyUSB*` (Linux)
2. Finds FT232RL device
3. Sequentially sends test bytes:
   - `'A'` (0x41)
   - `0x55` (alternating 01010101)
   - `0xAA` (alternating 10101010)
   - `"Hello"` (string)
   - `0x00` (zero)
   - `0xFF` (all ones)
4. Waits for echo response (2 seconds)
5. Verifies byte-by-byte match
6. Shows PASS/FAIL for each test

## Expected Output When Working

```
═══════════════════════════════════════════════════╗
║           Trinity UART Echo Test v1.0                       ║
║    phi² + 1/phi² = 3 = TRINITY                        ║
╚═══════════════════════════════════════════════════╝

[+] Scanning for FT232RL device...
[+] Found FT232RL: /dev/cu.usbserial-xxx

═════════════════════════════════════════════════════╗
║  Testing:                                                     ║
╚══════════════════════════════════════════════════════╝

[→] Test 1/6 Sending 'A' (0x41)
[←] Received 41
[✓] ECHO SUCCESS!

[→] Test 2/6 Sending 0x55 (alternating) (0x55)
[←] Received 55
[✓] ECHO SUCCESS!

...

═════════════════════════════════════════════════════════╗
║  SUMMARY                                                       ║
╚══════════════════════════════════════════════════════╝

Passed: 6/6
```

## If FT232RL Not Found

```
[!] FT232RL not found!

Available serial ports:
  /dev/cu.usbserial-xxx
  /dev/cu.usbserial-yyy
```

**Actions:**
- Check that FT232RL is connected
- Check wire colors (GND, RXD, TXD)
- Try different USB port

## If TIMEOUT / No Response

```
[→] Test 1/6 Sending 'A' (0x41)
[←] Received
[✗] TIMEOUT - Received 0 bytes, expected 1
```

**Possible causes:**
1. ❌ FPGA not flashed → reflash firmware
2. ❌ Pins crossed → check J2: 1=GND, 5=RX, 6=TX
3. ❌ FT232RL not working → try different adapter
4. ❌ Speed mismatch → code uses default settings

**Actions:**
- Reflash: `sudo fxload ... && sudo ./jtag_program uart_echo_top.bit`
- Check LED on board (should blink when receiving)
- Power cycle FT232RL (unplug/replug)

## Debugging Tips

1. Verify pin mapping in constraint file
2. Use oscilloscope on pins L20/K20
3. Test FT232RL with loopback (TX → RX directly)
4. Check DSLogic shows same data on CH0/CH1
