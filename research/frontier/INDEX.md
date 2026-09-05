# What the frontier work has already settled, and where it is written down

76 documents across `research/frontier/` and `research/block/`, indexed because
their number is now the problem. Three separate sessions have re-derived results
that were already here -- the block axis, a Lucas identity check, a published
finding -- because the answer sat under a filename nobody guessed. A search that
does not know the filename finds nothing, and an empty search reads as an open
question.

**Read this before starting anything.** The titles are written as claims, so the
index is the claim list.

The grouping below is mechanical -- it reads the title for words like "closed",
"withdrawn", "still" -- so treat it as a first sort, not a verdict. A document in
"standing results" may have been superseded by one two lines below it. The
filename and the title are reliable with one measured exception: of the 76
documents, exactly one -- `LADDER_THIRD_MODEL_BREAKS_4BIT` -- is refuted by a
follow-up appended below a rule inside itself, so its title states a result the
same file goes on to withdraw. Read to the end of a document before citing its
title. The bucket is a convenience.

The one exception is "Negative results and open ends", which has been resolved
by hand and carries supersession links, because a wrong entry there costs the
most: it is the section a reader goes to for something to work on.

## Closed — do not re-open without new evidence (7)

- **Pipelining does not rescue the non-closed path -- it hits a ceiling**  
  `research/frontier/PIPELINE_CEILING_2026-08-10.md`
- **Post-route resolution: three prior disputes, decided on the right instrument**  
  `research/frontier/POST_ROUTE_RESOLUTION_2026-08-10.md`
- **The block axis is closed, and not because we lost it**  
  `research/frontier/BLOCK_AXIS_CLOSED_2026-08-10.md`
- **The block axis is decided, and it is decided against us**  
  `research/block/BLOCK_AXIS_VERDICT_2026-08-10.md`
- **The closed form does not select the winner at 4 bits — on either model**  
  `research/frontier/LADDER_FORMULA_FAILS_4BIT_2026-08-10.md`
- **The granularity/cost curve is not smooth, and the optimum has a closed form**  
  `research/frontier/LADDER_COST_AND_LAW_2026-08-10.md`
- **Three regimes, not one law — why the closed form gets 3 and 5 bits and misses 4**  
  `research/frontier/LADDER_THREE_REGIMES_2026-08-10.md`

## Negative results and open ends (0 open — all three closed)

This is the one section where the mechanical grouping was actively harmful, so
it has been resolved by hand. It listed three open ends. **All three were already
closed**, and a reader who trusted the bucket -- this one did -- re-opened a
solved problem. Each entry below now says what closed it.

- ~~A third family breaks the 4-bit result — and with it the fitted λ~~  
  `research/frontier/LADDER_THIRD_MODEL_BREAKS_4BIT_2026-08-10.md`  
  → closed **by its own appended follow-up**, below the rule in the same file --
  the only document in the 76 that contradicts its own title, which is why the
  title-reading grouping missed it. `boundary.py` asked five parameter-free
  quantities to put Pythia (supergolden) on one side and SmolLM2/Qwen (φ) on the
  other. Only kurtosis separated, by 3.4 %, which is what chance produces from
  three points and five candidates. The informative row is the MSE gap
  (0.2833 / 0.1896 / 0.2719): Pythia sits *between* the two models that disagree
  with it, so the weight statistics do not distinguish the cases and no weight
  statistic is likely to. Four bits is a near-tie whose direction flips --
  measured margins 2.7 % and 10.7 % to φ, 5.9 % to supergolden. **Conclusion:
  report the 4-bit budget per model as measured, do not predict it.** The λ
  question is settled with it: λ was fitted to force φ at 4 bits, so on a family
  where φ loses it is worse than no λ at all.
- ~~The block axis, attacked a second way, and still lost~~  
  `research/frontier/BLOCK_AXIS_SECOND_ATTEMPT_2026-08-10.md`  
  → closed by `BLOCK_AXIS_CLOSED_2026-08-10.md`: a Lloyd-Max bound on the
  within-block distribution (18,850,950 values, block of 32, E8M0 scale) shows a
  fourth attempt is not warranted. The axis is decided, on a measurement rather
  than on fatigue.
- ~~The complete node: LUTs per neuron, and why the figure is not yet the format's~~  
  `research/frontier/NODE_SILICON_2026-08-10.md`  
  → closed by `NODE_FOLDED_2026-08-10.md`, which did the fold that document
  named as its own next step: **82.5 → 28.0 LUT per weight** at fan-in 8, and
  33.2 at fan-in 32. Then `NODE_PIPELINED_2026-08-11.md` cut the tree once more,
  +25.6 % and +37.6 % MHz/LUT at fan-in 8 and 16 — and −8.7 % at 32, so the cut
  is not free at every width. The RTL is `fpga/phiscale/tern_node3.v`; the
  negation is already an XOR plus a carry summed in a second narrow tree.

## Withdrawn — claims this project retracted itself (15)

- **Isolating the decoder: withdrawal 13 is itself withdrawn, and the result is larger**  
  `research/frontier/DECODER_ISOLATED_2026-08-10.md`
- **RETRACTED — this withdrawal was wrong. The Fmax figures are real nextpnr-xilinx measurements.**  
  `research/frontier/WITHDRAWAL_FMAX_UNSOURCED_2026-08-10.md`
- **Seven iterations, seven withdrawals: what is left**  
  `research/block/ACCOUNTING_2026-08-10.md`
- **WITHDRAWN -- the salience correction fails on the second model**  
  `research/frontier/WHY_COARSER_2026-08-10.md`
- **Withdrawal 10: the oracle and the RTL implement different formats under one name**  
  `research/frontier/WITHDRAWAL_10_ARTEFACT_DIVERGENCE_2026-08-10.md`
- **Withdrawal 11: the format in the silicon table is in no source of truth**  
  `research/frontier/WITHDRAWAL_11_ORPHAN_2026-08-10.md`
- **Withdrawal 12: the instrument limitation was false, and it reverses withdrawal 7**  
  `research/frontier/WITHDRAWAL_12_POST_ROUTE_2026-08-10.md`
- **Withdrawal 13: the groups overlap, and the metric mostly restates area**  
  `research/frontier/WITHDRAWAL_13_GROUPS_2026-08-10.md`
- **Withdrawal 14: observing four bits pruned 85% of the design**  
  `research/frontier/WITHDRAWAL_14_OBSERVATION_2026-08-10.md`
- **Withdrawal 15: subtracting a harness that is not the same size in every build**  
  `research/frontier/HARNESS_SUBTRACTION_2026-08-10.md`
- **Withdrawal 16: the LNS comparison was never well-posed**  
  `research/frontier/WITHDRAWAL_16_INCOMMENSURABLE_2026-08-10.md`
- **Withdrawal 17: a taper's slope is a property of the fitting window**  
  `research/frontier/SLOPE_WINDOW_2026-08-10.md`
- **Withdrawal 18: the prescription claim was too strong, and this is the third time**  
  `research/frontier/EXTERNAL_THIRD_OVERTURN_2026-08-10.md`
- **Withdrawal 8: the headline result was a positions-versus-bits artefact**  
  `research/frontier/PACKED_FRONTIER_2026-08-10.md`
- **Withdrawal 9: the ternary rungs are wider than their names**  
  `research/frontier/WITHDRAWAL_9_NAMED_WIDTHS_2026-08-10.md`

## Standing results (51)

- **A geometric scale grid beats a float one at every width, and the margin is 1/ln 2**  
  `research/frontier/GEOMETRIC_SCALE_2026-08-10.md`
- **APoT refutes the phi scale-grid claim, and exactness turns out not to be ours**  
  `research/block/APOT_REFUTES_PHI_GRID_2026-08-10.md`
- **Block-scaled 4-bit quantisation — what survived**  
  `research/block/FINDINGS.md`
- **Closing the 64-bit gap: the scan is superlinear and the recommendation flips**  
  `research/frontier/SCALING_2026-08-10.md`
- **Crossovers for all eleven tapers, measured**  
  `research/frontier/CROSSOVERS_2026-08-10.md`
- **Fineness costs registers, not adders**  
  `research/frontier/ONE_ADDER_FAMILY_2026-08-10.md`
- **Four families, one live network, one metric**  
  `research/block/FOUR_FAMILIES_2026-08-10.md`
- **Full observation splits the group claim by axis, and gives a better theorem**  
  `research/frontier/DECODER_FULL_OBS_2026-08-10.md`
- **Median of five seeds: the top of the table was never established**  
  `research/frontier/MEDIAN_SWEEP_2026-08-10.md`
- **One pipeline register in the node: worth it at eight and sixteen, not at thirty-two**  
  `research/frontier/NODE_PIPELINED_2026-08-11.md`
- **T7 applied: which of our comparisons are well-posed**  
  `research/frontier/T7_APPLIED_2026-08-10.md`
- **Ternary is forced by cardinality, not by identity**  
  `research/frontier/ALPHABET_CARDINALITY_2026-08-11.md`
- **The accumulator law for ternary networks**  
  `research/block/TERNARY_ACCUMULATOR_2026-08-09.md`
- **The area ordering inverts with the regime, and our number was measured in the wrong one**  
  `research/block/REGIME_INVERSION_2026-08-10.md`
- **The break-even width does not exist, and the last estimate is gone**  
  `research/frontier/EXCHANGE_RATE_2026-08-10.md`
- **The campaign, as science**  
  `research/frontier/SCIENCE_2026-08-10.md`
- **The competitor found, and what it shows about our own claim**  
  `research/frontier/CLOSURE_VS_FQP_2026-08-10.md`
- **The cost of non-closure, measured**  
  `research/frontier/CLOSURE_MEASURED_2026-08-10.md`
- **The fourth defect class, found systematically rather than by accident**  
  `research/frontier/DOCUMENT_TRACEABILITY_2026-08-10.md`
- **The gate caught my own hour-old work, and the LNS number has halved twice**  
  `research/frontier/OBSERVATION_TREND_2026-08-10.md`
- **The ladder law over the whole one-adder family**  
  `research/frontier/ELEMENT_ONEADDER_2026-08-10.md`
- **The ladder law replicates on a second model**  
  `research/frontier/LADDER_REPLICATED_2026-08-10.md`
- **The multiply-free scales are Pisot numbers -- some of them**  
  `research/frontier/PISOT_2026-08-10.md`
- **The node, with the negation folded: 28 LUT per weight**  
  `research/frontier/NODE_FOLDED_2026-08-10.md`
- **The one-adder family measured on networks, and a calibration error of ours**  
  `research/frontier/ONEADDER_MEASURED_2026-08-10.md`
- **The operating point: cheap under both operations, and only where the datapath needs it**  
  `research/block/OPERATING_POINT_2026-08-10.md`
- **The optimal multiply-free ladder depends on the bit budget, and follows from the weights**  
  `research/frontier/LADDER_LAW_2026-08-10.md`
- **The phi grid is twice as good as powers of two, at the same hardware cost**  
  `research/block/PHI_GRID_2026-08-10.md`
- **The rot was not one script**  
  `research/frontier/SCRIPT_ROT_2026-08-10.md`
- **The scale applier has three vertices and no winner**  
  `research/block/SCALE_FRONTIER_2026-08-10.md`
- **The scale axis: a phi-power block scale beats a power-of-two one at equal bits**  
  `research/frontier/SCALE_AXIS_2026-08-10.md`
- **The scale-cost frontier, and a strict win over MXFP4**  
  `research/frontier/SCALE_FRONTIER_2026-08-10.md`
- **The selection table: what to use, at what width, and what it costs**  
  `research/frontier/SELECTION_2026-08-10.md`
- **The silicon table reproduces, its LUT column is exact, and its MHz column is not**  
  `research/frontier/SEED_NOISE_2026-08-10.md`
- **The six-bit ladder in silicon: +37% area takes 70% error to 3.7%**  
  `research/frontier/ELEMENT_SILICON_2026-08-10.md`
- **The staircase form decides how a taper must be compared**  
  `research/frontier/CROSSOVERS_CORRECTED_2026-08-10.md`
- **The staircase taxonomy prescribes a comparison method for every form**  
  `research/frontier/TAXONOMY_PRESCRIBES_2026-08-10.md`
- **The two sides of a node want different rungs**  
  `research/frontier/TWO_SIDES_2026-08-10.md`
- **There is no gap in the multiply-free spectrum -- the enumeration stopped early**  
  `research/frontier/NO_SPECTRUM_GAP_2026-08-10.md`
- **Three theorems about pair checks, from a registry that passed while broken**  
  `research/frontier/KEY_AND_FORMAT_2026-08-10.md`
- **Асимметричный диалект против DialectFP4 — прямое сравнение**  
  `research/block/ASYM_VS_BLOCKDIALECT_2026-08-09.md`
- **Вердикт: заявки на «формат номер один» нет, и вот чем это доказано**  
  `research/block/VERDICT_2026-08-09.md`
- **Замер на оси масштаба: TEF сравнялся с предложением IBM, но не обошёл его**  
  `research/block/SCALE_AXIS_2026-08-09.md`
- **Итог линии: три теоремы о границах чужих методов**  
  `research/block/SUMMARY.md`
- **Отбор насыщается; знак композиции задаётся числом несовпадений**  
  `research/block/THEOREM_2026-08-09.md`
- **Порядок операций меняет результат до 2.78× — прямая проверка условия складывания**  
  `research/block/ORDER_MATTERS_2026-08-09.md`
- **Преобразования двигают потолок, форматы его делят — и иногда мешают друг другу**  
  `research/block/TRANSFORMS_VS_FORMATS_2026-08-09.md`
- **Проверка на настоящих обученных тензорах — что выжило**  
  `research/block/REAL_TENSORS_2026-08-09.md`
- **Фронт и кремний: два результата, которые надо читать вместе**  
  `research/frontier/FRONTIER.md`
- **Что осталось на границе — семь замеров и одна честная оценка**  
  `research/block/FRONTIER_2026-08-09.md`
- **Энергетическая асимметрия: где остался незанятый потолок**  
  `research/block/ENERGY_ASYMMETRY_2026-08-09.md`

