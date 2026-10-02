# x7-board.gif — three `tri x7-board` commands, recorded

`x7-board.cast` is an asciicast v2 recording of one session on 2026-10-02
(about 20:00 UTC), made with `tri blog gif record`:

1. `tri x7-board compare --ref` exited 0. fasm2frames was re-timed at 55.79 s
   against bitwalk at 0.91, 0.84 and 0.86 s, and both the frames and the .bit
   were byte-identical. The 1-minute load was 44 on 8 cpus.
2. `tri x7-board load x7-board-gif-load --owner-yes '…'` exited 0 with
   `done 1`. Log: `conformance/board_runs/x7-board-gif-load.log`.
3. `tri x7-board receipts x7-board-gif --quick` exited 0 with
   `receipts verified (tag) : 51840/51840 under node 0x5452494e` and rows
   320/320. Log: `conformance/board_runs/x7-board-gif.log`.

`x7-board.gif` is `tri blog gif render x7-board.cast x7-board.gif --max-idle 2 --colors 16`
(967×598, 107 frames).

**Staged:** the prompt and the key-by-key typing of each command.

**Real:** every byte the commands printed, at the time they printed it.

**Shortened:** any silence longer than 2 s is shown for 2 s, and that frame
carries a note saying so, e.g. "waited 56 s, shown 2 s" over the fasm2frames
run. The real session took 100.7 s; the GIF runs 40 s.
