# JTAG на macOS ARM — Фиксированные проблемы (2026-04-01)

## Hardware
- **Mac**: Apple Silicon (M1/M2/M3), macOS 14.x
- **Cable**: Xilinx DLC10 (clone)
- **FPGA**: QMTech XC7A100T-FGG676
- **Tools**: openFPGALoader, jtag_program (tri)

## Проблемы

### 1. DLC10 не определяется на macOS ARM
```
❌ openFPGALoader --cable xpc
Error: FTDI: -3 (device not found)

❌ jtag_program flash bitstream.bit
Error: No JTAG cable found
```

**Причина**: FTDI драйвера на macOS ARM имеют ограничения с некоторыми клонами.

### 2. fxload не помогает
Даже после попытки переключить PID:
```bash
fxload -t fx2 -I /usr/share/openfpgaloader/firmware/xilinx_ft232h.hex
```
Кабель остаётся невидимым для JTAG инструментов.

## Вывод

**На текущем Mac (Apple Silicon) НЕВОЗМОЖНО прошивать FPGA через JTAG**:
- ❌ DLC10 clone — не работает
- ❌ openFPGALoader — не видит кабель
- ❌ jtag_program (tri) — не видит кабель

## Допустимые пути вперёд

| Вариант | Требуется | Статус |
|---------|-----------|--------|
| **Linux PC/VM** | Отдельный хост с Linux | ✅ Надёжно |
| **RP2040 мост** | RP2040 + firmware JTAG-bridge | 🔄 Нужна прошивка |
| **SPI программатор** | CH341A +ibre т.п. | 🔄 Нужен адаптер |
| **FTDI genuine** | Оригинальный Xilinx cable | ❌ Не гарантируется |

## Рекомендация

Для JTAG операций:
1. Использовать отдельный Linux ПК/ноутбук
2. Или настроить Linux VM с USB passthrough
3. UART отладка работает — DSLogic U2basic ✅

## Опыты

| Дата | Попытка | Результат |
|------|---------|-----------|
| 2026-03-30 | jtag_program на Mac | FTDI -3 |
| 2026-03-31 | openFPGALoader --cable xpc | FTDI -3 |
| 2026-04-01 | fxload + jtag | FTDI -3 |

## Фикс

```
status: BLOCKED
blocker: macOS ARM FTDI compatibility
workaround: Use Linux host for JTAG
```
