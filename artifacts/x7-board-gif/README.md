# x7-board.gif — three `tri x7-board` commands, recorded

`x7-board.cast` is an asciicast v2 recording of one session on 2026-10-02
(20:34 UTC), made with `termgif.py record` (`tri cast record`). It
replaced the two earlier recordings of the same commands (run names
`x7-board-gif*` and `x7-board-gif2*`). The command banner now carries the
project's full name, Trinity S³AI, and its mark with the point down.

1. `tri x7-board compare --ref` exited 0. fasm2frames was re-timed at 33.34 s
   against bitwalk at 0.44, 0.43 and 0.64 s (77×), and both the frames and the
   .bit were byte-identical. The 1-minute load was 23 on 8 cpus.
2. `tri x7-board load x7-board-gif3-load --owner-yes '…'` exited 0 with
   `done 1`. Log: `conformance/board_runs/x7-board-gif3-load.log`.
3. `tri x7-board receipts x7-board-gif3 --quick` exited 0 with
   `receipts verified (tag) : 51840/51840 under node 0x5452494e` and rows
   320/320. Log: `conformance/board_runs/x7-board-gif3.log`.

`x7-board.gif` is
`tri cast render x7-board.cast x7-board.gif --max-idle 2 --colors 64 --title "tri x7-board · t27 back half on the AX7203"`
(1043×740, 112 frames, black window in the t27.ai palette).

The same recording is published, with its own page, player and preview card,
at `https://t27.ai/term/x7-board/` (`tri cast publish`); a copy of that page
is kept under `~/skills/_state/casts/x7-board/`.

**Staged:** the prompt and the key-by-key typing of each command.

**Real:** every byte the commands printed, at the time they printed it. The
banners, bars and boxes are what `tri x7-board` prints on a terminal; piped
into a file it prints only the plain lines, which are unchanged.

**Edited:** the home directory is shown as `~` (`tri cast scrub`); the header
says so in `redacted`. Nothing else was changed.

**Owner's quote:** passed to `--owner-yes` in English, so nothing was
translated after the fact in this recording.

**Shortened:** any silence longer than 2 s is shown for 2 s, and that frame
carries a note saying so, e.g. "waited 33 s, shown 2 s" over the fasm2frames
run. The real session took 73.7 s; the GIF runs 37.9 s.
