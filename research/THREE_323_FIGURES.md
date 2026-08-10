# Three different results share the number 323, and confusing them has cost real time

Written because it has already produced two wrong conclusions in this
repository, one of them mine. Anyone about to repeat a "323" from this project
should first decide which of the three it is.

| # | figure | module | registers | status |
|---|---|---|---|---|
| 1 | 323 MHz, 41.2 GOPS | `gf16_matmul4x4` / `gf16_dot4` | **none** | **withdrawn 2026-08-08** |
| 2 | 323.31 MHz | bare `gf16` core, quoted for the codec | codec is clocked | real, **mis-described** |
| 3 | 323.42 MHz | `phi^k` iterative applier | clocked | real, unrelated to 1 and 2 |

## 1 — withdrawn, and correctly so

`grep -c posedge` returns 0 in all nine copies of the matmul across the
repositories. A block with no registers has no clock, so no frequency can belong
to it, and 41.2 GOPS was derived as 323 MHz x 128 operations and falls with it.
Removed 2026-08-08 from the site, the sample report, the NLnet annex, the
outreach material and the profiles.

The replacement figures are what was actually measured: 32,252 LUT with `-nodsp`
or 21,223 LUT with 64 DSP48, the block being combinational.

## 2 — real, but not what the sentence says

Source: `trinity-gf16.tex`, *"Max frequency for clock `chain[19]`: 323.31 MHz"*.
`chain[19]` is a ripple-counter probe clock and the bare `gf16` core is a purely
combinational multiply, so the number is `1 / (combinational delay)` exposed
through a counter. That is a normal way to characterise a combinational block.

It appears in the abstract of arXiv:2606.05017 attached to the **codec**, where it
reads as the design's clock rate. `gf16_codec_ax7203.v` carries 8 `posedge` and
11 `always` blocks, so the codec is sequential and a clock rate can belong to it
-- which is exactly why the sentence passes a quick read. The routed clocked
conformance design measures 27.55 MHz by nextpnr static timing.

Both numbers are true. They measure different things.
See `ERRATUM_arXiv_2606.05017_board_and_frequency.md`.

## 3 — a different module entirely

`POST_ROUTE_RESOLUTION_2026-08-10.md`: the `phi^k` iterative applier, 156 LUT,
**323.42 MHz** post-route. It has nothing to do with GF16. It appears in the
comparison where the unrolled variant loses frequency (110.93 MHz) because eight
steps in sequence form one long carry chain.

## Why this keeps happening

The three arose independently and none of them is wrong on its own. What makes
them dangerous is that a search for "323" returns all three plus unrelated hits
-- the ionisation energy of beryllium is 9.323, an RNA base mass is 323.2, and
`0.6932323` is a physics constant in the site's own source.

Two failures already caused by this:

- A session concluded the arXiv abstract carried the withdrawn matmul figure and
  advised against linking the paper from the site. It carried figure 2, a
  different module.
- A session searching for the provenance of figure 2 found figure 3's post-route
  logs and nearly reported them as the codec's.

**Rule:** before repeating a 323, name the module and check whether it has
registers. `grep -c posedge` on the file settles it in one command.
