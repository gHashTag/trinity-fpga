# NLnet Foundation — Grant Application
## Trinity GF16 Open ASIC Core
### URL: https://nlnet.nl/propose
### Amount requested: €50,000
### Programme: NGI Zero Commons Fund

---

## WHY NLNET

NLnet финансирует open-source infrastructure. Прошлые получатели: Tor, OpenBSD, WireGuard, Rust (Mozilla), LibreSSL.

Trinity Stack = open-source hardware + open-source AI = точное попадание.

Дедлайн: **rolling** (принимают заявки постоянно, 4 раза в год).
Ответ: 2-3 месяца.

---

## APPLICATION TEXT

**Project name:** Trinity GF16 Ternary ASIC — Open Neural Inference Core

**Requested amount:** €50,000

**Summary (150 words):**

Trinity Stack is an open-source FPGA-validated ternary neural inference core using GF16 (Golden Float 16-bit) φ-structured quantization. Running on a $30 XC7A100T FPGA board, it achieves 135× CPU speedup with zero hardware multipliers — inference via XOR + popcount only.

This grant will fund:
1. OpenLane2/IHP tapeout preparation for SG13G2 130nm
2. Caravel wrapper integration for free IHP MPW shuttle
3. arXiv publication of GF16 φ-quantization results
4. Documentation enabling reproducibility worldwide

All outputs: Apache 2.0 on GitHub. No proprietary dependencies.

**Website:** https://github.com/gHashTag/trinity-fpga

---

## MILESTONES (for NLnet)

| # | Milestone | Deliverable | Amount |
|---|---|---|---|
| M1 | OpenLane2 synthesis of vsa_matmul | GDS2 preview file | €10,000 |
| M2 | IHP SG13G2 MPW submission | Submitted GDS2 | €15,000 |
| M3 | arXiv paper published | arXiv ID | €10,000 |
| M4 | Silicon received + tested | Test report | €15,000 |

---

## SUBMIT

https://nlnet.nl/propose — форма на 1 странице, очень простая.
Ответ приходит через 6-8 недель.

*trinity-fpga/docs/funding/NLnet-application.md*
