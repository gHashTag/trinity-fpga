# Sovereign Tech Fund — Grant Application
## Trinity GF16 Open Source Hardware Toolchain
### URL: https://sovereigntechfund.de/en/programs/
### Amount: €100,000–€250,000
### Programme: Sovereign Tech Fund Invest

---

## ABOUT STF

Sovereign Tech Fund (Германия, финансируется BMBF) инвестирует в open-source digital infrastructure.
Прошлые получатели: curl ($150K), OpenSSL ($900K), Sequoia PGP ($290K), WireGuard ($500K).

Trinity Stack = open-source silicon infrastructure = подходит.

---

## APPLICATION SUMMARY

**Project:** Trinity GF16 Open ASIC Toolchain

**Requested:** €150,000

**What it is:**
Open-source toolchain для ternary neural network inference на FPGA и ASIC:
- Rust CLI (`trios-fpga`) — synthesis, flash, bench
- RTL (`vsa_matmul.v`) — ternary matmul, 0 multipliers
- GF16 quantization library (`phi_numbers::gf16`)
- IHP SG13G2 tapeout pipeline

**Why it matters for digital sovereignty:**
- Альтернатива проприетарным AI chips (Nvidia, Qualcomm)
- Запускается на $30 hardware, доступном всем
- Полностью воспроизводимо: open RTL + open PDK + open toolchain
- dePIN архитектура — децентрализованный AI без Big Tech

**Deliverables:**
1. OpenLane2 flow для vsa_matmul.v (IHP SG13G2)
2. First Trinity silicon (130nm)
3. Published benchmarks + arXiv
4. Documentation for reproducibility

**Contact:** https://sovereigntechfund.de/en/contact/

*trinity-fpga/docs/funding/Sovereign-Tech-Fund-application.md*
