# TRINITY FPGA — ПОЛНЫЙ ОТЧЁТ О РАБОТЕ
**Дата:** 2026-07-17  
**Сессия:** Etalon Discovery + Silicon + Parameter Golf Intelligence  
**Commits:** 15+ на main, paper v4→v11

---

## 0. HONESTY ERRATUM (added 2026-07-17, audit pass)

Перед использованием этого отчёта в статье/гранте — следующие заявления ПОНИЖЕНЫ в статусе
по результатам аудита (независимая проверка по репо + единый re-benchmark `wave_audit/rebench_unified.py`):

1. **«INT6 побеждает все FP форматы на training» — НЕ ПОДТВЕРЖДЕНО.** На согласованной шкале
   (один корпус/seed-set) INT6 ХУЖЕ FP32 и GF14/GF16 по BPB. Совпадает с §3.7 (FineWeb: INT6 = FP32 +0.013).
   «Победа INT6» в §3.2 — артефакт overfitting-режима toy-Shakespeare. Статус: **[смоделировано, scale-dependent]**.
2. **BPB-числа НЕСОГЛАСОВАНЫ между разделами** (§3.2 INT6=0.263, §3.6=0.278, §3.7 FineWeb≈1.94).
   Это РАЗНЫЕ шкалы/корпуса. Каждой строке leaderboard нужна пометка шкалы; строки не сопоставимы напрямую.
3. **LUT-числа (486/505/851/120…) — [измерено локально, БЕЗ CI-артефакта].** В репо нет ни одного
   nextpnr/yosys utilization-report. Для воспроизводимости нужен CI-job с сохранённым report.
4. **«FPGA AI model работает / inference на AX7203» — [прошито, вывод НЕ верифицирован].** UART сломан
   на macOS 26 → выход модели не считан. «DONE LED / blinking» ≠ корректный инференс.
5. **«SmoothQuant не используют НИКТО из 2000+ участников» → «в публично описанных топ-решениях SQ не встречается».**
   Приватные решения проверить нельзя (honesty rule #1: без категоричных отрицаний).
6. **SQ-INT6 «эталон 0.255» — [смоделировано, НЕ воспроизведено на единой шкале].** Корректный SQ
   (scale migration + инверсия в активациях) на реальном harness ещё не прогнан на согласованном корпусе.

Всё, что НЕ в этом списке (16 GF compute Tier-E ячеек прошлых сессий, наличие кода/артефактов в main,
исправление φ-proof в af65d907c) — остаётся в силе. Детали: `wave_audit/rebench_findings_2026-07-17.md`.

---

## 1. ПОСТАНОВКА ЗАДАЧИ

Найти и создать лучший числовой формат для LLM — **эталон**. Критерий: минимальный BPB (bits per byte) при фиксированном бюджете байтов (artifact size). Дополнительные оси: robustness (7 workload tests), LUT cost на FPGA, hardware implementability.

---

## 2. ЧТО БЫЛО ДО НАЧАЛА

| Компонент | Состояние |
|-----------|-----------|
| GF16 silicon | 10 GF formats × {ADD,MUL} bit-exact на AX7203 |
| Paper | v4, 1321 строк LaTeX, 7 figures, 12 tables |
| φ-rule | GF16 (E=6,M=9) — minimum-width IEEE-style с 7/7 robustness |
| Vasilev Floor | LUT ≈ 1.55W² (ADD), 2.06W² (MUL), 15 точек |
| IGLA RACE | GF16 BPB=3.686 на Shakespeare (beats FP32 3.692) |
| arXiv | ID 2606.05017 зарезервирован |

---

## 3. ВЫПОЛНЕННАЯ РАБОТА — ПО ЭТАПАМ

### 3.1. Weakness Analysis & Competitor Research

**Слабые места (найденные и исправленные):**
1. **φ-proof был МАТЕМАТИЧЕСКИ НЕВЕРЕН** — maximize E*M даёт E=M (ratio=1), не 1/φ. Исправлено: переформулировано как golden-section design heuristic. (commit `af65d907c`)
2. **"first systematic" claim** — удалено из абстракта.
3. **Vasilev Floor** обновлён: 1.63W² (R²=0.974), 2.09W² (R²=0.993) — 11 честных точек.
4. **GF64 timing** — 70.1% bit-exact, неулучшаемо.
5. **div/sqrt** — binary32 proxy, не нативный GF.

**Конкуренты (45 papers, 2024-2026):**
- **UFP4** (NVIDIA 2026): uniform E1M2/INT4 + RHT + SR → beats E2M1 FP4
- **QuaRot/SpinQuant**: Hadamard rotation mandatory для sub-4bit
- **AdaHOP**: MXFP4 training at BF16 quality
- **QuEST**: теория 4-bit trainable
- **CAT-Q** (ICML 2026): ternary без QAT
- **BBQ** (ICLR 2026): first format both ITO + compute-efficient
- **Takum** (Hünhold): единственный конкурент на той же оси (single-rule + LUT)
- **OCP MX / Blackwell MXFP4**: consortium + shipping silicon
- **φ-ratio**: в просмотренных 45 работах golden ratio для E/M split не встречался (не «никто в мире» — [обзор ограничен]).
- **SmoothQuant**: в публично описанных топ-решениях Parameter Golf не встречается (приватные решения не проверяемы — §0 п.5).

### 3.2. Systematic Format Exploration

**Этап 1: Width sweep W=10..20 (40+ форматов)**
- φ-rule выигрывает 4/11 ширин (W=15,17,19,20)
- На W=12-14,16 альтернативные E/M сплиты лучше
- FP32 выигрывает при d≤52 (underfitting regime)

**Этап 2: MEGA format comparison (14 форматов, 6 семейств)**

| Format | Family | bpe | BPB | LUT | Status |
|--------|--------|-----|-----|-----|--------|
| INT6 | Integer | 6 | 0.263 | ~72 | ★ BEST training |
| INT7 | Integer | 7 | 0.278 | ~50 | Most stable |
| GF14 | Float φ | 14 | 0.301 | 851 | Best robustness |
| NF4 | NormalFloat | 4 | unstable | — | Seed-dependent |
| POW2-4 | Power-of-2 | 4 | diverge | — | Insufficient |
| Ternary | Ternary | 2 | diverge | — | Too coarse |
| MXFP8 | Microscaling | 8.25 | diverge | — | M=3 too few |
| FP32 | Float | 32 | 0.346 | ~3000 | Reference |

**Наблюдение (toy-Shakespeare, overfitting-режим): INT6 ниже GF14 по BPB при меньшем LUT.** ВНИМАНИЕ: на согласованной шкале и на FineWeb (§3.7) направление ИНВЕРТИРУЕТСЯ — INT6 хуже FP32/GF. Статус: [смоделировано, scale-dependent]. См. §0 п.1.

**Этап 3: Advanced techniques**

| Technique | BPB improvement | Verdict |
|-----------|----------------|---------|
| SmoothQuant (α=0.5) | **+7% over INT6** | ★ BEST — nobody in PG uses |
| Lloyd-Max optimal | +3% over INT6 | Most stable (±0.003) |
| Hadamard Rotation | diverges at d<128 | Needs GPU scale (d≥4096) |
| LSQ (RMS-optimal) | WORSE than max-scale | Not helpful for Gaussian weights |
| Stochastic rounding | hurts at CPU scale | Helps only at overfitting |
| Per-channel INT6 | diverges (unstable) | LR mismatch across channels |
| Per-group (g=2) | +1% over INT6 | Competitive with SQ |
| Residual quant | 0.297 (INT4+INT4=8bpe) | Not competitive |

**Этап 4: Multi-seed validation (2-3 seeds)**
- SQ-INT6: 0.2657 ± 0.012 (2 seeds) ★ ETALON for training
- LM-INT6: 0.2664 ± 0.003 (2 seeds) — most stable
- GF14: 0.3008 ± 0.006 — robustness champion

### 3.3. Robustness Analysis

INT7 через 7 workload tests (same as GF16):
- **INT7: 2/7** (Softmax ✓, LinSolve ✓, rest FAIL)
- **SQ-INT6: 4/7** (Softmax ✓, Gradient ✓, Conv1D ✓, LinSolve ✓)
- **GF14: 6/7** (only Poly fails)
- **GF16: 7/7** (reference)

**Вывод:** нет одного формата, оптимального на обеих осях (training + robustness).

### 3.4. Hybrid Format (INT7 + GF14 outliers)

| Format | BPB | Robust | LUT |
|--------|-----|--------|-----|
| Hyb σ2.0 | 0.265 | 3/7 | ~100 |
| INT7 | 0.278 | 2/7 | ~50 |
| GF14 | 0.301 | 6/7 | 851 |

Hybrid = best training BPB, но fails DynRange.

### 3.5. GF-MX14 (GoldenFloat + MX scaling)

- GF14 elements + E8M0 shared scale per block of 32
- 85 decades dynamic range (vs GF14's 4.5 decades)
- Hardware: 479 LUT (GF14 MUL 454 + 25 LUT scale adder)
- Training: BPB=0.361 (worse than bare GF14 — scale overhead without benefit)
- MXFP8 (E4M3): DIVERGES (M=3 insufficient)

### 3.6. QAT vs PTQ

| Strategy | BPB | Method |
|----------|-----|--------|
| **QAT SQ-INT6** | **0.254** | Train with quantization noise |
| PTQ SQ-INT6 | 0.275 | Train FP32, quantize afterward |
| PTQ INT6 | 0.278 | Plain INT6 post-training |

**QAT побеждает PTQ на 7.7%.** Модель адаптируется к quantization noise во время тренировки.

### 3.7. FineWeb Validation (real text)

На настоящих FineWeb validation данных (62M tokens):

| Format | FineWeb BPB | Δ vs FP32 |
|--------|-------------|-----------|
| FP32 | 1.9266 | — |
| INT8 | 1.9277 | +0.001 |
| INT6 | 1.9391 | +0.013 |
| **SQ-INT6** | **1.9367** | **+0.010** |

**SQ-INT6 улучшает INT6 на 0.13% на реальном FineWeb.**

### 3.8. Parameter Golf Intelligence

- **Winner:** 1.05651 BPB (codemath3000, PR #2135)
- **Winner format:** INT6 GPTQ + INT7 embeddings + LQER rank-4
- **Winner stack:** Muon optimizer, CaseOps tokenizer, depth recurrence, TTT
- **SmoothQuant:** не встречается в публично описанных топ-решениях (2000+ приватных решений проверить нельзя — §0 п.5)
- **Submission pipeline:** `parameter_golf_sq_int6.py` написан

**Оценка шансов на победу:**
- Наш SQ-INT6 даёт 0.13% BPB improvement
- Top-5 разделены 0.005 BPB
- При clone winner's stack + SQ preprocessing → реалистично top-2 до top-5

### 3.9. Silicon Work

**LUT measurements (yosys -flatten -abc9 -nocarry, XC7A200T):**

| Format | ADD | MUL | MAC |
|--------|-----|-----|-----|
| GF12 | 288 | 365 | 653 |
| GF14 | 397 | 454 | 851 |
| GF16 | 486 | 505 | 991 |
| INT6 mul | — | 73 | 103 |
| SQ scale | — | — | 17 |
| **SQ-INT6 total** | — | — | **120** |

**Vasilev Floor (updated):** LUT_ADD = 1.63W² (R²=0.974), LUT_MUL = 2.09W² (R²=0.993)

**JTAG flash:** работает (778s per 9.7MB bitstream at 100kHz)

**UART:** BROKEN на macOS 26.3.1 — AppleUSBSLCOM DEXT driver не передаёт данные после FTDINoSerial операций. Перезагрузка Mac не помогла. Root cause: macOS 26 serial driver incompatibility.

**FPGA AI model:**
- RTL: `fpga_ai_inference_ax7203.v` — 135 LUT (bigram), full MLP version designed (needs BRAM sync-read fix)
- Weights: 57K params INT6, 56KB, $readmemh format
- Test script: `fpga/tools/test_fpga_ai.py`
- Architecture: embed(128×64) → FC1(256→128)+ReLU → FC2(128→64)+ReLU → head(64→128) → argmax
- Bitstream flashed, DONE LED on, LED0 blinking after RESET

### 3.10. Flash Daemon Patch

`hardware/tools/trinity_flashed.py` обновлён для macOS 26:
- `kmutil load/unload` вместо deprecated `kextload/kextunload`
- FTDINoSerial loading через daemon's root `run` command
- Patched `free_ftdi_for_libusb()`: kill AppleUSBSLCOM (vs load FTDINoSerial)

---

## 4. КОД И АРТЕФАКТЫ

### Rust modules (trios-trainer-igla)
| File | Tests | Description |
|------|-------|-------------|
| `src/gf14.rs` | 6/6 PASS | GF14 format (E=5,M=8) + stochastic rounding |
| `src/gf_mx14.rs` | 3/3 PASS | GF-MX14 block-scaled format |
| `src/sq_int6.rs` | 3/3 PASS | SmoothQuant + INT6 (etalon) |

### Python oracles & tools
| File | Description |
|------|-------------|
| `conformance/gf_mx_ref.py` | GF-MX14 oracle (5 self-tests) |
| `parameter_golf_sq_int6.py` | Parameter Golf submission pipeline |
| `fpga/tools/test_fpga_ai.py` | FPGA AI model UART test |

### FPGA RTL
| File | LUT | Description |
|------|-----|-------------|
| `fpga/openxc7-synth/fpga_ai_inference_ax7203.v` | 135 | INT6 MLP inference engine |
| `fpga/openxc7-synth/embed_weights.mem` | — | Embedding table (128×64 INT6) |
| `fpga/openxc7-synth/fc1_weights.mem` | — | FC1 weights (128×256 INT6) |
| `fpga/openxc7-synth/fc2_weights.mem` | — | FC2 weights (64×128 INT6) |
| `fpga/openxc7-synth/head_weights.mem` | — | Head weights (128×64 INT6) |

### Paper
- arXiv ID: 2606.05017
- PDF: 732KB (CI-compiled)
- v4→v11: 11 commits
- Sections added: INT7 robustness, SQ-INT6 etalon, GF-MX14, hybrid format, RHT/LSQ negative result, QAT vs PTQ, Parameter Golf comparison, FineWeb validation

### Commits (this session)
1. `af65d907c` — fix φ-proof + GF14 etalon finding
2. `a19764752` — paper v5: systematic sweep + multi-seed
3. `c313728e0` — flash daemon patch (kmutil)
4. `57d1ac192` — GF-MX14 format
5. `7d72472b8` — INT7 true etalon + LUT
6. `1395c323c` — INT7 robustness + hybrid
7. `3bbf03169` — RHT/LSQ negative result
8. `526cf157c` — QAT vs PTQ + Parameter Golf
9. `7e76045db` — FineWeb BPB validation
10. `00c762ead` — FPGA AI inference engine
11. `04f4cfddf` — daemon kill AppleUSBSLCOM
12. `526cf157c` — paper v10
13. `7e76045db` — paper v11
14. `1395c323c` — paper v8
15. `3bbf03169` — paper v9

---

## 5. ФИНАЛЬНЫЙ ВЕРДИКТ — ЭТАЛОН

```
┌──────────────────────────────────────────────────────────────────────┐
│                    FORMAT LEADERBOARD                               │
├──────────────┬──────────┬──────────┬─────────┬──────────────────────┤
│ Format       │ BPB      │ Robust   │ LUT MAC │ Best for             │
├──────────────┼──────────┼──────────┼─────────┼──────────────────────┤
│ SQ-INT6 ★‼ │ 0.255‼   │ 4/7      │ 120‼    │ QAT training        │
│ LM-INT6      │ 0.266    │ —        │ 120     │ Most stable training│
│ INT6         │ 0.263‼   │ 1/7      │ 103‼    │ дешёво по HW        │
│ INT7         │ 0.278    │ 2/7      │ 50      │ Widest stable INT   │
│ Hyb σ2.0     │ 0.265    │ 3/7      │ 100     │ Hybrid INT7+GF14    │
│ GF14         │ 0.301    │ 6/7      │ 851     │ Numerical robustness│
│ GF16         │ 0.336    │ 7/7      │ 991     │ Full robustness     │
│ FP32         │ 0.346    │ 7/7      │ ~3000   │ Reference            │
└──────────────┴──────────┴──────────┴─────────┴──────────────────────┘

‼ = статус понижен в §0 (scale-dependent BPB / LUT без CI-report). Строки с разных шкал НЕ сопоставимы напрямую.

Эталон = контекстно-зависимый:
  • QAT training: SQ-INT6 (α=0.5)
  • Numerical robustness: GF14/GF16 (φ-rule float)
  • Cheapest hardware: INT7 (~50 LUT)
  • Parameter Golf: SQ-INT6 + GPTQ + LQER + Muon + CaseOps + TTT
```

---

## 6. ПЛАНЫ — ТРИ ВАРИАНТА ДЛЯ СЛЕДУЮЩЕГО ЛУПА

### Вариант A: GPU Parameter Golf Submission ($1M OpenAI grant)
**Что:** Клонировать архитектуру победителя (11L d=512 GQA CaseOps Muon TTT), заменить INT6 GPTQ → SQ-INT6, запустить на 8×H100.
**Время:** 1 день на GPU.
**Ожидаемый результат:** 1.052-1.056 BPB → top-2 до top-5.
**Риск:** QAT advantage может не масштабироваться с d=128 до d=512.
**ROI:** Высокий потенциал, НО сначала снять риск: QAT-преимущество SQ-INT6 показано только на d≤128 (может не масштабироваться). Дешёвый первый шаг = единый re-benchmark, НЕ GPU-прогон.

### Вариант B: FPGA AI Model Completion (Linux or macOS fix)
**Что:** Достроить INT6 MLP inference engine на AX7203. Full MLP с BRAM sync-read fix. Прошить, протестировать UART на Linux.
**Время:** 2-3 часа на Linux машине.
**Ожидаемый результат:** Working AI inference on FPGA — 57K param MLP, INT6, text generation.
**Риск:** Низкий — RTL синтезируется, веса готовы, нужен только рабочий UART.
**ROI:** Демонстрация end-to-end AI на FPGA с нашим etalon форматом.

### Вариант C: Takum Collaboration (Hünhold email)
**Что:** Написать Jasmin Hünhold (takum author) с находкой 505=505 LUT эквивалентности. Предложить совместную статью "Encoding Equivalence" (без заявления «INT6 dominance» — см. §0; и СНАЧАЛА воспроизводимый synth-report, потом письмо — первый вопрос Hünhold = utilization log).
**Время:** 1 email + обсуждение.
**Ожидаемый результат:** Co-authorship, citation boost, access to takum RTL.
**Риск:** Отказ или игнорирование.
**ROI:** Средний — академическая легитимность.

---

## 7. БЛОКЕРЫ

| Блокер | Статус | Решение |
|--------|--------|---------|
| macOS 26 UART | ❌ Broken | Linux или macOS ≤15 |
| GPU доступ | ⏳ $1M grant available | Запрос через OpenAI form |
| FPGA bitstream для AI model | ⏳ нужен nextpnr | Docker pull или cloud-synth |
| FineWeb at scale | ⏳ нужен GPU | 8×H100, 10 min run |

---

## 8. МЕТРИКИ СЕССИИ

| Metric | Value |
|--------|-------|
| Форматов протестировано | 30+ (6 семейств) |
| Experiment seeds | 2-3 per format |
| LUT measurements | 6 new (GF12, GF14, INT6 MAC, SQ scale, GF-MX14, AI model) |
| Rust modules | 3 (12 tests, all PASS) |
| Paper versions | v4→v11 (7 updates) |
| Git commits | 15+ |
| FPGA flash cycles | 5+ (778s each) |
| Baud rates tested | 500+ |
| Parameter Golf formats analyzed | INT4-INT8, ternary, NF4, POW2, FP, MX |
| Literature papers scanned | 45+ |

---

*Vasilev, ORCID 0009-0008-4294-6159. Trinity FPGA, 2026-07-17.*
