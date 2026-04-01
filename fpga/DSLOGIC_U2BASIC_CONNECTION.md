# DSLogic U2basic Connection Guide — QMTech XC7A100T

## Overview / Обзор

**Цель**: Connect DSLogic U2basic 16-channel Logic Analyzer to QMTech XC7A100T-FGG676 FPGA for full signal analysis (UART + JTAG + SPI + Clock tree).

**Goal**: Подключить DSLogic U2basic 16-канальный логический анализатор к QMTech XC7A100T-FGG676 FPGA для полного анализа сигналов (UART + JTAG + SPI + Clock tree).

---

## Equipment / Оборудование

| Item | Описание | Purpose |
|------|----------|---------|
| DSLogic U2basic | Logic analyzer, 16 channels @ 400 MS/s | Основной инструмент анализа |
| QMTech XC7A100T-FGG676 | FPGA board (Artix-7) | Целевая плата |
| Test hooks | Small grabbers | Для тонких пинов (JTAG) |
| Crocodile clips | Alligator clips | Для GND и крупных контактов |
| Optional: ZIF-clip | IC clamp | Для проверки пинов на плате |

---

## Physical Layout / Физическое расположение

### DSLogic U2basic (Top View / Вид сверху)

```
┌─────────────────────────────────────────────────────────────────┐
│  [USB]                                              │
│   │                                                 │
│   └──► к MacBook                                    │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  GND  CH0   CH1   CH2   CH3   CH4   CH5     │   │
│  │  ●●●  ●●●   ●●●   ●●●   ●●●   ●●●   ●●●     │   │
│  │  ●●●  ●●●   ●●●   ●●●   ●●●   ●●●   ●●●     │   │
│  │  GND  0     1     2     3     4     5        │   │
│  │                                                 │
│  │  CH6   CH7   CH8   CH9   CH10  CH11  CH12    │   │
│  │  ●●●   ●●●   ●●●   ●●●   ●●●   ●●●   ●●●    │   │
│  │  ●●●  ●●●   ●●●   ●●●   ●●●   ●●●   ●●●    │   │
│  │   6     7     8     9     10    11    12     │   │
│  │                                                 │
│  │  CH13  CH14  CH15  [Trigger]                  │   │
│  │  ●●●   ●●●   ●●●   ●●●                         │   │
│  │  ●●●  ●●●   ●●●   ●●●                         │   │
│  │   13    14    15    TRIG                        │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### QMTech XC7A100T (Top View / Вид сверху)

```
        JTAG Header (6 pin)              J2 Header (64 pin)
        ┌──────────┐                    ┌──────────────────┐
        │ VCC GND  │                    │  [1] [3] [5]...  │ ← Верхний ряд
        │ TCK TDO  │                    │   ▲        ▲      │
        │ TDI TMS  │                    └──────────────────┘
        └────┬─────┘
             │
             ▼
        ┌─────────┐
        │  M22    │ ← 50 MHz oscillator
        │  U22    │ ← MMCM output
        │  T23    │ ← LED (D5)
        └─────────┘
```

---

## Connection Diagram / Диаграмма подключения

### Minimal UART Setup (4 wires) — Fast Start

```
┌─────────────────────────────────────────────────────────────────────┐
│           DSLogic U2basic               ←ПРОВОД→              QMTech FPGA    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐                       ┌─────────────┐                       │
│  │   DSLogic   │                       │   QMTech    │                       │
│  │   U2basic   │                       │  XC7A100T   │                       │
│  │             │                       │   Board     │                       │
│  │  ┌───────┐  │                       │             │                       │
│  │  │ CH0   │  │ ─────────────────────►│  J2 Pin 5   │  (K20 = FPGA TX)     │
│  │  │ CH1   │  │ ─────────────────────►│  J2 Pin 6   │  (L20 = FPGA RX)     │
│  │  │ CH2   │  │ ─────────────────────►│  M22        │  (50 MHz Clock)      │
│  │  │       │  │                       │             │                       │
│  │  │ GND   │  │ ─────────────────────►│  J2 Pin 1   │  (⬛ GND)            │
│  │  └───────┘  │                       │             │                       │
│  │             │                       │             │                       │
│  │  USB cable  │ ─────────────────────►│  MacBook    │                       │
│  └─────────────┘                       └─────────────┘                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Full 16-Channel Setup / Полное подключение (16 каналов)

| DSLogic Channel | Recommended Color | FPGA Location | Signal | Purpose |
|----------------|-------------------|---------------|--------|---------|
| **GND** | ⬛ Чёрный | J2 Pin 1 (верхний ряд, 1-я дырка) | Земля | ОБЯЗАТЕЛЬНО! Без него не работает |
| **CH0** | 🟡 Жёлтый | J2 Pin 5 (верхний ряд, 3-я дырка) | FPGA TX (K20) | UART данные от FPGA |
| **CH1** | 🟢 Зелёный | J2 Pin 6 (нижний ряд, 3-я дырка) | FPGA RX (L20) | UART данные к FPGA |
| **CH2** | 🔵 Синий | M22 (плата, штырь рядом с JTAG) | 50 MHz | Базовый генератор |
| **CH3** | 🟣 Фиолетовый | U22 (плата) | MMCM 81.25 MHz | Системный клок |
| **CH4** | 🔴 Красный | T23 (плата, LED D5) | LED output | Визуальная индикация |
| **CH5** | Оранжевый | [Spare - J21] | SPI_SCK | Резерв для SPI |
| **CH6** | Белый | [Spare - H21] | SPI_MISO | Резерв для SPI |
| **CH7** | Серый | [Spare - G22] | SPI_MOSI | Резерв для SPI |
| **CH8** | Розовый | [Spare - F22] | SPI_CS | Резерв для SPI |
| **CH9** | Коричневый | JTAG TCK (через test hook) | JTAG Clock | Для JTAG анализа |
| **CH10** | Бежевый | JTAG TDI (через test hook) | JTAG Data In | Для JTAG анализа |
| **CH11** | Лайм | JTAG TDO (через test hook) | JTAG Data Out | Для JTAG анализа |
| **CH12** | Бирюзовый | JTAG TMS (через test hook) | JTAG Mode | Для JTAG анализа |
| **CH13** | Тёмно-синий | [Spare - D26] | J2 Pin 5 alt | Проверка маппинга пинов |
| **CH14** | Тёмно-зелёный | [Spare - E26] | J2 Pin 6 alt | Проверка маппинга пинов |
| **CH15** | Тёмно-красный | [Spare] | Trigger Ref | Референс для триггера |

---

## Step-by-Step Connection Guide / Пошаговое подключение

### ⚠️ CRITICAL RULES / КРИТИЧЕСКИЕ ПРАВИЛА

1. **GND ПЕРВЫМ!** (GND FIRST!) Всегда подключайте чёрный провод (GND) первым и отключайте последним. Без земли измерения не будут работать.
2. **Осторожно с пинами!** Не замкните соседние пины металлическим зондом.
3. **Test hooks для JTAG** — используйте маленькие крючки для тонких пинов (JTAG header).
4. **Crocodile clips для GND** — используйте крокодилы для земли и крупных контактов.
5. **НЕ подключайте DSLogic и Xilinx JTAG одновременно к одному JTAG header!** Используйте test hooks чтобы подключить DSLogic к пинам ПОД кабелем.

### Phase 1: UART Only (Minimal Setup) — 4 провода

Это минимальная настройка для базовой отладки UART:

```
1. 📌 Подключите:
   GND  → J2 Pin 1 (⬛ чёрный)       ← ВСЕГДА ПЕРВЫМ!
   CH0  → J2 Pin 5 (🟡 жёлтый)       = FPGA TX
   CH1  → J2 Pin 6 (🟢 зелёный)      = FPGA RX
   CH2  → M22        (🔵 синий)        = 50 MHz Clock

2. 💻 Настройте DSView:
   - Sample rate: 400 MS/s
   - Channels: 0, 1, 2, 3, 4 (GND на CH15 для триггера)
   - Trigger: Rising edge on CH0 (UART TX)

3. ▶️ Начните захват:
   - Отправьте UART команду (например, PING 0x03)
   - Должны видеть байты на CH0 (TX) и ответ на CH1 (RX)

4. ✅ Проверьте:
   - CH0 показывает данные от FPGA (TX)
   - CH1 показывает данные от FT232RL (RX)
   - CH2 показывает стабильный 50 MHz клок
```

### Phase 2: Full Signal Analysis — All 16 Channels

```
1. 📌 Подключите все провода (см. таблицу выше):
   - GND всегда первым и последним!
   - Проверьте каждое соединение

2. 💻 Настройте DSView:
   - Sample rate: 400 MS/s (максимальный)
   - Channels: [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]
   - Trigger: Pulse width on CH2 (50MHz, min 18ns)
   - Thresholds: 3.3V (LVCMOS33)

3. 🧪 Для JTAG (если Xilinx Cable подключён):
   ⚠️ ВНИМАНИЕ! JTAG header ОДИН для двух источников!
   - Вариант A: Отключите Xilinx Cable, подключите DSLogic
   - Вариант B: Используйте test hooks для подключения ПОД кабелем
   - НИКОГДА не подключайте оба TCK источника одновременно!

   Подключение JTAG:
   JTAG TCK (pin 3) ──► DSLogic CH9 (коричневый)
   JTAG TDO (pin 4) ──► DSLogic CH11 (лайм)
   JTAG TDI (pin 5) ──► DSLogic CH10 (бежевый)
   JTAG TMS (pin 6) ──► DSLogic CH12 (бирюзовый)

4. ▶️ Начните захват всех сигналов

5. ✅ Проверьте все каналы:
   - CH0-CH1: UART TX/RX
   - CH2: 50 MHz стабильный
   - CH3: MMCM клок (81.25 MHz)
   - CH4: LED индикация
   - CH9-CH12: JTAG сигналы (если подключены)
```

---

## Troubleshooting / Решение проблем

### Problem: "No signal captured" / Нет захвата сигнала

**Symptoms / Симптомы**:
- CH0-CH4 всё время на LOW или HIGH (без изменений)
- UART данные не видны

**Solutions / Решения**:
1. Проверьте GND подключение (обязательно!)
2. Убедитесь что провод не отвалился от пина
3. Проверьте voltage threshold в DSView (установите 3.3V для LVCMOS33)
4. Попробуйте другой провод или test hook вместо crocodile clip

### Problem: "Wrong channel shows UART" / Неверный канал показывает UART

**Symptoms / Симптомы**:
- CH13 или CH14 показывает UART вместо CH0/CH1

**Solutions / Решения**:
1. Это указывает на неправильное mapping пинов (D26/E26 vs K20/L20)
2. Используйте `tri fpga dslogic-pins` для проверки маппинга
3. Обновите `fpga/constraints/uart_bridge_j2.xdc` если найдена ошибка
4. Пересоберите битовуюю: `tri fpga build-uart`

### Problem: "JTAG signals not visible" / JTAG сигналы не видны

**Symptoms / Симптомы**:
- CH9-CH12 всегда на LOW или не меняется

**Solutions / Решения**:
1. Проверьте что Xilinx JTAG Cable отключён перед подключением DSLogic
2. Убедитесь что test hooks правильно подключены к пинам
3. JTAG header маленький — используйте test hooks
4. Проверьте что TCK не коротнул на землю

### Problem: "Clock unstable" / Клок нестабильный

**Symptoms / Симптомы**:
- CH2 (50 MHz) показывает джиттер или неправильную частоту

**Solutions / Решения**:
1. Проверьте что M22 это правильный штырь (рядом с JTAG)
2. Убедитесь что осциллятор 50 MHz исправен
3. Проверьте уровень сигнала (должен быть LVCMOS33)
4. Измерьте частоту на M22 напрямую мультиметром если возможно

---

## DSView Configuration Tips / Настройки DSView

### Basic Settings / Базовые настройки

```
Channel Setup:
- Input mode: Digital
- Threshold: 3.3V (для LVCMOS33)
- Sample rate: 400 MS/s (максимальный для U2basic)

Trigger Setup:
- Type: Pulse Width
- Channel: CH2 (50 MHz)
- Min width: 18ns (один период 50 MHz)
- Direction: Rising
```

### Protocol Decoding / Декодирование протоколов

```
UART:
- Baud rate: 115200
- Data bits: 8
- Parity: None
- Stop bits: 1

JTAG:
- Protocol: JTAG
- TCK frequency: Auto

SPI:
- Clock polarity: CPOL=0
- Clock phase: CPHA=0
```

---

## Quick Reference / Быстрая справка

### What each channel monitors / Что мониторит каждый канал

| CH | Signal | Expected | Notes |
|----|--------|----------|-------|
| 0 | FPGA TX (K20) | UART out from FPGA |
| 1 | FPGA RX (L20) | UART in to FPGA |
| 2 | 50 MHz (M22) | Base clock reference |
| 3 | MMCM (U22) | System clock (81.25 MHz) |
| 4 | LED (T23) | Visual feedback |
| 5-8 | SPI (if implemented) | Future use |
| 9-12 | JTAG | Timing reference only |
| 13-14 | Alt mapping | Pin verification |
| 15 | Trigger | Reference |

### Expected timings at 115200 baud / Ожидаемые тайминги

```
Byte width @ 115200 baud = 8.68 µs
Bit period @ 115200 baud = 8.68 µs / 8 = 1.085 µs

Expected UART frame:
START (0) + 8 DATA bits + STOP (1) = 10 bits
Total: 8.68 µs per byte @ 115200
```

---

## Next Steps / Следующие шаги

After connection:

1. Run diagnostics: `tri fpga dslogic-connect`
2. Capture signals: `tri fpga dslogic-capture --preset full_analysis`
3. Analyze UART: `tri fpga dslogic-uart`
4. Check pin mapping: `tri fpga dslogic-pins`
5. Log results to: `.trinity/fpga/experience.json`

---

## Safety Notes / Безопасность

1. ⚠️ **Disconnect GND last** — отсоединяйте землю последним
2. ⚠️ **No power while wiring** — не включайте плату во время подключения
3. ⚠️ **Double-check before powering** — убедитесь что нет коротких замыканий
4. ⚠️ **One JTAG source** — никогда не подключайте Xilinx Cable и DSLogic к одному JTAG header одновременно

---

φ² + 1/φ² = 3 = TRINITY
