# 2026-07-07 · MXFP4 BLOCK-LEVEL TIER-E на AX7203

**AGENT**: V (Verdict) + T (Queen, печать) + E (Experience)
**PR**: #249 (merged cc77c58)
**Issue**: #199

## Итог

mxfp4-block — первая **block-level Tier-E ячейка** в каталоге. Все 4 звена
proof-chain закрыты на кремнии AX7203 (XC7A200T-FBG484-2).

## Proof-chain

| Звено | Значение |
|---|---|
| CI-run | `28865563368` SUCCESS (workflow `ax7203-corona-decode-mxfp4-block.yml`) |
| nextpnr routing | clean seed=1 с первой попытки (`--placer heap --router router1`) |
| Bitstream SHA256 | `36acee1b781b92332e3de3ab59ab87d6ac35c19636be026d77bcccf0247b4f13` |
| Bitstream size | 9 730 809 B (XC7A200T-FBG484-2, uncompressed .bit) |
| IDCODE | `0x13636093` (Artix-7 rev 1) — JTAG scan via OpenOCD |
| UART | `HW RESULT: 1056/1056 bit-exact (fails=0)` |
| Test set | 33 blocks × 32 lanes = 1056 representative точек |

## Что доказано физически

32 × E2M1 element codes + shared E8M0 block-scale → 32 масштабированных FP32.
Масштаб применён как **сложение экспонент** (степень двойки, без общего
умножителя). Это **реальная OCP MX mxfp4-семантика**, отличная от
single-element fp4-decode (где block-scale отсутствует).

### Чем отличается от fp4 (single-element)

- `fp4` decode: 1 код E2M1 → 1 FP32 (без масштаба)
- `mxfp4-block` decode: 32 кода E2M1 + 1 E8M0 scale → 32 FP32 (масштабированных)

`corona_decode_mxfp4_ax7203.v` (НЕ block) — побайтово идентичен `corona_decode_fp4_ax7203.v`
(доказано SHA256-diff'ом, SHA mxfp4-single = `1b7773853f983ebdf6d3bcf9e57c29d73bf7d9d0d8dae86b67ac574a3d7de8f5`,
SHA fp4 = `dcee9dec7246c1398ae0525719d067ae70a2953efc4cf905846923075aaad450`),
поэтому single-mxfp4 НЕ засчитан как отдельная ячейка (B-path из развилки 2026-07-07).
Block-decoder — отдельная аппаратная реализация с реальной новизной.

## Ledger impact

- decode-HW: 53 → **54** (+1, mxfp4-block как отдельная ячейка)
- union: 55 → **56**
- catalog: 83 → **84**
- обе оси: 8 / 8 (без изменений)
- SW: 75/0/8 (без изменений)
- compute-HW: 10 (без изменений)

## Инженерные уроки сессии

### 1. Routing-cliff = профиль netlist, не fan-out width

Прогноз 70% на routing-cliff оказался **неверным**. GF-семья валится при N≥24
из-за параметрического barrel-shifter в датапати. 32-lane mxfp4-block **не имеет
barrel-shifter** — масштаб реализован как сложение экспонент (степень двойки).
ABC дал ~2094 LUT, router1 нашёл маршрут за seed=1.

**Критерий дружелюбности к разводке** (подтверждён):
- ✅ Fixed-field (binary128, ibm_hfp128, vax_h, mxfp4-block) — route'ятся
- ❌ Barrel-shifter (gf24/32/48/64/96/128, takum32/64) — cliff при N≥24

### 2. macOS AppleUSBFTDI блокирует FTDI bulk-write

На Apple Silicon с Full Security `nvram boot-args="-apple_usb_ftdi"` **тихо
игнорируется**. Симптом: `libusb_detach_kernel_driver() failed with
LIBUSB_ERROR_ACCESS`. JTAG scan проходит (короткие async-transfers), но `pld
load` виснет на mpsse_flush с удваивающимся таймаутом.

**Решение** (что сработало):
1. Recovery Mode (зажать power при загрузке на Apple Silicon)
2. Startup Security Utility → **Reduced Security** + "Allow kernel extensions"
3. `sudo nvram boot-args="-apple_usb_ftdi"`
4. `sudo reboot`
5. Физический reconnect USB после каждого `pld load` (FPGA делает USB-reset,
   macOS повторно сматчит AppleUSBFTDI без boot-arg, но с boot-arg matching
   становится non-exclusive, и повторное открытие libusb работает)

Замечание: даже после boot-arg, `Warn: libusb_detach_kernel_driver() failed`
остаётся в логе OpenOCD, но **перестаёт блокировать bulk-write**.

### 3. `/tmp/` на macOS чистится при reboot

После каждого reboot битстрим пропадает. Нужно перекачивать через:
```bash
gh run download 28865563368 -D /tmp/mxfp4_block -n corona-decode-mxfp4-block-bitstream
```

### 4. Два serial node после FTDI-unlock

После применения boot-arg появляются два `/dev/cu.usbserial-*`:
- `/dev/cu.usbserial-120` — работает для UART (FPGA отвечает на 160000 baud)
- `/dev/cu.usbserial-210512180081` — второй FTDI interface (CP2102N или channel B)

Host script по умолчанию использует `/dev/cu.usbserial-120` — работает.

## Команды воспроизведения

```bash
# 1. Скачивание битстрима из CI артефакта
gh run download 28865563368 -D /tmp/mxfp4_block -n corona-decode-mxfp4-block-bitstream

# 2. SHA verify
shasum -a 256 /tmp/mxfp4_block/corona_decode_ax7203.bit
# expected: 36acee1b781b92332e3de3ab59ab87d6ac35c19636be026d77bcccf0247b4f13

# 3. Flash (требует FTDI-unlock через boot-arg + reboot, см. урок 2)
openocd -f fpga/openxc7-synth/ax7203_al321.cfg \
  -c "init" \
  -c "pld load 0 /tmp/mxfp4_block/corona_decode_ax7203.bit" \
  -c "runtest 200000" \
  -c "shutdown"
# ожидаемое время: ~78 сек (9.7 MB @ 1 MHz JTAG)

# 4. UART conformance
python3 conformance/mxfp4_block_host_ax7203.py \
  --port /dev/cu.usbserial-120 --baud 160000
# ожидаемый вывод: HW RESULT: 1056/1056 bit-exact (fails=0)
```

## Open issues / Horizon

- [ ] Single-element `mxfp4` (`corona_decode_mxfp4_ax7203.v`) остался в репо
  как single-decode пример, но **не засчитан** как отдельная Tier-E ячейка
  (B-path: физически идентичен fp4). Решение: либо переименовать в
  `corona_decode_fp4_alias_ax7203.v`, либо удалить в пользу block-версии.
- [ ] Boot-arg `-apple_usb_ftdi` глобально отключает FTDI-VCP. Если в будущем
  понадобится FTDI-CDC для других устройств — нужно `sudo nvram -d boot-args`.
- [ ] После power-cycle FPGA битстрим слетает (volatile). Для постоянной
  работы нужен SPI-flash (отдельная задача, пока не приоритет).
