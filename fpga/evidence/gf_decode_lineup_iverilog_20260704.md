# GF decode-линейка — evidence независимого iverilog-witness №2 (2026-07-04)

**Формат статуса (BINDING honesty):** `[verified SW на iverilog]` ≠ `[измерено на
кремнии]`. Этот документ фиксирует **sim-bitexact** результат на реальном
Verilog-симуляторе (Icarus Verilog) с fixed-width семантикой. Это НЕ decode-HW:
полная 4/4 цепь Tier-E (CI GREEN + bitstream SHA256 + UART `HW RESULT: N/N
bit-exact (fails=0)` @160000 baud + IDCODE `0x13636093`) на AX7203
(XC7A200T-2FBG484I) **НЕ выполнена** и остаётся `[ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]`.

## Что проверено

Параметрический декодер `fpga/openxc7-synth/gf_decode_param.v #(N,E,M,BIAS,OUT_REG)`
→ IEEE binary32, вся Фаза-A линейка GoldenFloat (10 форматов):

| fmt  | N  | E  | M  | BIAS | Покрытие witness №2            |
|------|----|----|----|------|-------------------------------|
| gf4  | 4  | 1  | 2  | 0    | exhaustive 16/16              |
| gf6  | 6  | 2  | 3  | 1    | exhaustive 64/64              |
| gf8  | 8  | 3  | 4  | 3    | exhaustive 256/256            |
| gf10 | 10 | 3  | 6  | 3    | exhaustive 1024/1024          |
| gf12 | 12 | 4  | 7  | 7    | exhaustive 4096/4096          |
| gf14 | 14 | 5  | 8  | 15   | representative + 5 классов    |
| gf16 | 16 | 6  | 9  | 31   | **exhaustive 65536/65536**    |
| gf20 | 20 | 7  | 12 | 63   | representative + 5 классов    |
| gf24 | 24 | 9  | 14 | 255  | representative + full-exp stress |
| gf32 | 32 | 12 | 19 | 2047 | representative + full-exp stress |

**Результат:** 10/10 Phase-A `HW RESULT: N/N bit-exact (fails=0)` на iverilog
(gf16 — полный exhaustive 65536/65536).

## Провенанс (честно)

- Witness-harness (golden-оракул на `fractions.Fraction`, Python бит-модель RTL,
  генератор векторов, testbench) воспроизводимо лежит в этом PR:
  `fpga/witness/gf_decode/`.
- Зелёный прогон `HW RESULT: N/N fails=0` был получен на **локальной машине
  разработчика** (Icarus Verilog), рабочая директория `/tmp/gf16_witness/` — вне
  CI и вне sandbox. Сырые iverilog-логи в этот коммит НЕ вложены (не хотим
  выдавать что-либо за реконструкцию). Любой ревьюер воспроизводит результат:

  ```bash
  cd fpga/witness/gf_decode
  python3 gen_vectors.py                       # (пере)генерация vectors/*.txt из golden
  # для каждого формата: iverilog tb_gf_decode.v + gf_decode_param.v (с #(N,E,M,BIAS)),
  # затем vvp -> ожидается "HW RESULT: N/N bit-exact (fails=0)"
  ```

- Python-модель (`rtl_bit_model.py`) даёт 10/10 PASS и служит **спецификацией
  целевой семантики**, но сама по себе НЕ гарантирует Verilog-RTL — см. ниже.

## Два fixed-width бага, пойманные ТОЛЬКО iverilog (не Python)

Урок 04.07 (подтверждает урок 28.06): Python-транскрипция с arbitrary-width int
физически не ловит fixed-width эффекты Verilog. Независимый iverilog-witness №2
поймал ДВА реальных бага, невидимых Python-модели:

1. **Fixed-width shift truncation** (widen-фикс). `pack_frac << (23-M)`, где
   `pack_frac` объявлен `[M-1:0]`, вычислялся в M-битном контейнере →
   старшие значащие биты обрезались ДО конкатенации. Первый прогон v1 RTL:
   gf16 exhaustive `HW RESULT: 1168/65536 bit-exact (fails=64368)` (~98% провал).
   **Фикс:** сначала расширить до полной ширины результата, потом сдвигать
   (`wire [WIDE:0] pf_wide = {..0.., pack_frac}; norm_widen_result = pf_wide <<
   (23-M)`).

2. **Out-of-bounds bit-read в FP32-subnormal packer.** `wire [M:0] sub_shifted`
   (для gf24 M=14 → 15 бит), но ниже читается `sub_shifted[22:0]` → биты 22:(M+1)
   = out-of-bounds → X. Симптом: `dut=00Xxxxxx`. Срабатывает ТОЛЬКО на
   FP32-subnormal пути (true_exp < −126, deep underflow), куда gf16 (BIAS=31)
   никогда не попадает — поэтому gf16 оставался чистым после фикса №1 и скрывал
   этот баг; только gf24/gf32 (BIAS>127) его вскрыли. **Фикс:**
   `wire [M:0] sub_shifted` → `wire [23:0] sub_shifted` (RHS zero-extends,
   `[22:0]` читает валидные нули).

Widen-фикса №1 самого по себе НЕДОСТАТОЧНО — нужны ОБА. После обоих — зелёный
10/10.

## Инварианты платы (для последующего synth/flash, не выполненного здесь)

- AX7203 = **XC7A200T-2FBG484I**, part `xc7a200tfbg484-2`, IDCODE `0x13636093`.
- Клок 200 МГц LVDS R4(+)/T4(−) → `IBUFDS`. UART @160000 baud.
- Toolchain openXC7 (Yosys + nextpnr + fasm2frames + xc7frames2bit),
  Docker `regymm/openxc7`.

## Ссылки

- Якорные статьи: arXiv:2606.05017 (семейство по единому правилу),
  arXiv:2606.09686 (каталог форматов).
- gf16-decode ТЗ (issue #237): `fpga/gf16_decode_cell_TZ.md` — закрывается как
  частный случай `#(N=16,E=6,M=9,BIAS=31)` этого generator.
- Каталог = 83 формата; эта работа = 10-форматное FP32-подсемейство GF внутри
  каталога (Фаза A). Фаза B (gf48/gf64 → FP64) и Фаза C (gf96…gf1024, SW-only) —
  следующие шаги. Никаких «первый/единственный/лучший».
