# EIC Pathfinder Open 2026 — Application Outline
## Trinity dePIN-Compute: φ-Structured Open ASIC for Decentralized AI
### Deadline: 28 October 2026
### Portal: https://eic.ec.europa.eu
### Budget requested: €3,500,000

---

## 1. PROJECT TITLE

**TrinityASIC: Open-Source φ-Structured Ternary ASIC for Decentralized Physical AI Infrastructure**

Short name: **TRINITY-ASIC**

---

## 2. ABSTRACT (300 words)

We propose to design, fabricate, and deploy **TrinityASIC-1** — the world's first open-source ASIC chip implementing GF16 (Golden Float 16-bit) φ-structured ternary neural network inference for decentralized physical infrastructure (dePIN) networks.

**The problem:** AI inference is centralized (AWS, GCP control >65% of compute), expensive ($4.50/h per GPU node), and energy-inefficient. Edge devices lack affordable, energy-efficient inference silicon.

**Our breakthrough:** We have demonstrated on FPGA (XC7A100T, $30 board):
- 135× speedup over CPU baseline
- 43× better performance-per-watt
- 0 hardware multipliers (pure XOR + popcount, GF16 ternary)
- Full open-source RTL (Apache 2.0, Yosys + nextpnr)
- Validated: 64/64 iverilog PASS, BPB=0.1427 (IGLA champion model)

**ASIC projection (28nm):** 200× energy improvement over FPGA → **>8,000× over CPU**.

**dePIN network:** Each $5 TrinityASIC chip becomes a sovereign decentralized AI inference node — connected via WireGuard mesh (headscale), earning token rewards for inference and bandwidth.

**Why EIC Pathfinder:** This is a **disruptive paradigm shift** — from centralized GPU clouds to distributed ASIC mesh networks where every chip is a sovereign dePIN node. No commercial player pursues open-source + φ-quantization + dePIN simultaneously.

---

## 3. WORK PACKAGES

### WP1 — ASIC RTL Design (Month 1–6) — €800K
- Extend `vsa_matmul.v` to full ASIC standard-cell implementation
- SRAM controller for 144KB weight buffer
- UART/SPI I/O interface
- OpenLane2 synthesis flow
- Target: GDS2-ready for 28nm MPW

### WP2 — Fabrication (Month 6–18) — €1,200K
- 28nm MPW tapeout via broker (ChipWork / IHP)
- Package: QFN32
- Bring-up and characterization
- Target: 100 functional chips for dePIN pilot

### WP3 — dePIN Network (Month 12–24) — €800K
- headscale mesh coordinator (Railway/self-hosted)
- Token economics PoC (Solana/Cosmos)
- 100-node pilot network
- Benchmark: tokens/sec, watts/token, cost/node

### WP4 — Dissemination (Month 1–36) — €300K
- arXiv papers (cs.AR + cs.LG)
- ISSCC / DAC / FPGA conference submissions
- Open-source release of all RTL, toolchain, data
- HackerNews, academic workshops

### WP5 — Coordination (Month 1–36) — €400K
- Project management
- EU partner coordination
- Ethics & open-source compliance

---

## 4. CONSORTIUM (REQUIRED: min 1 EU legal entity)

| Partner | Country | Role |
|---|---|---|
| **Trinity Stack** (OÜ Estonia e-Residency) | 🇪🇪 Estonia | Lead, RTL, dePIN |
| **IHP-GmbH** (pending LOI) | 🇩🇪 Germany | PDK, fabrication guidance |
| **[University TBD]** | 🇪🇸/🇫🇷/🇵🇱 | Academic validation, arXiv |

**Action required:**
- [ ] Register OÜ via e-Residency Estonia: https://e-resident.gov.ee ($100, 1 week)
- [ ] Contact IHP for Letter of Intent: open-pdk@ihp-microelectronics.com
- [ ] Find academic partner via ResearchGate / LinkedIn

---

## 5. TRL PROGRESSION

```
TRL 4 (now):  FPGA-validated core, 135x speedup proven
TRL 5 (WP1):  ASIC RTL complete, OpenLane2 synthesis
TRL 6 (WP2):  First silicon (28nm MPW chips)
TRL 7 (WP3):  dePIN pilot (100 nodes)
TRL 8 (WP4):  Published results, reproducible
```

---

## 6. BUDGET BREAKDOWN

| Category | Amount | Notes |
|---|---|---|
| Personnel (engineers) | €1,500,000 | 3 FTE × 3 years |
| Subcontracting (fab) | €1,200,000 | 28nm MPW tapeout |
| Equipment | €300,000 | Test equipment, servers |
| Travel | €100,000 | Conferences, partner visits |
| Indirect costs | €400,000 | 25% flat rate |
| **TOTAL** | **€3,500,000** | |

---

## 7. PORTAL SUBMISSION STEPS

```
1. https://eic.ec.europa.eu → "Apply"
2. Вызов: HORIZON-EIC-2026-PATHFINDEROPEN-01
3. Дедлайн: 28 октября 2026, 17:00 Brussels time
4. Язык: English
5. Формат: PDF, max 17 pages
6. Приложения: CVs, Letters of Support, Ethics
```

---

*trinity-fpga/docs/funding/EIC-Pathfinder-outline.md*
