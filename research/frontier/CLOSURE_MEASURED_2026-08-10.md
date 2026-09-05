# The cost of non-closure, measured

Corollary `cor:closure` says a representable set that is not closed under its
own operation needs a stage returning results to the set. This measures that
stage on the fabric the decoder table was measured on: isolated unit, every
output bit folded into the observed reduction, median of five placement seeds,
Yosys 0.65 + nextpnr-xilinx 1743d0f, xc7a200t.

## One accumulation step

| | LUT | Fmax (median of 5) |
|---|---|---|
| closed -- `Z[phi]`, componentwise | **182** | **299.94 MHz** |
| non-closed -- normalise back into the set | 1756 | 11.46 MHz |
| **cost of non-closure, 16-bit** | **x9.6 area** | **/26.2 frequency** |
| closed -- `Z[phi]`, componentwise (32-bit) | **283** | **239.35 MHz** |
| non-closed -- normalise back (32-bit) | 7017 | 4.25 MHz |
| **cost of non-closure, 32-bit** | **x24.8 area** | **/56.3 frequency** |

Seed spread: 0.20--0.25 MHz on the non-closed units, 16.85--59.39 MHz on the
closed ones. The closed units are fast enough that placement noise is visible;
the non-closed ones are so far from the constraint that every seed lands in the
same place.

The non-closed 32-bit unit **fails** the 12 MHz bench constraint. The closed one
passes it twenty-fold.

## Why accumulation and not multiplication

The first version of this measurement compared weight *application*, and it was
the wrong place to look. A weight can be applied either way. What cannot be
avoided is that a neural layer accumulates, at fan-in 512 per neuron, and:

- In `Z[phi]` the sum of two ring elements is a ring element. The accumulator is
  a pair of integer registers and addition is componentwise -- the same cost as
  any integer accumulator, and exact.
- In a Fibonacci/Zeckendorf representation the sum of two representable numbers
  is **not** representable. `F_3 + F_3 = 4 = F_4 + F_1`: the representation
  changes non-trivially. Every accumulation must be renormalised.

So the stage does not run once per multiply. It runs once per accumulation, 512
times per neuron, and that is the number above.

## What this does and does not establish

**Does.** For the straightforward normaliser -- greedy Zeckendorf, oracle-checked
exhaustively at 65,536/65,536 for both the sum and the no-two-adjacent-ones
property, and for agreement with an independently written greedy model -- returning to
a non-closed set costs an order of magnitude more area than the entire closed
accumulation, and two orders on frequency.

**Does not.** It is not a reimplementation of FQP, whose units are not public in
detail; it measures the structural cost their number set imposes, not their
design. Greedy is not proven to be the cheapest normaliser -- constant-time
Zeckendorf adders exist -- so the *ratio* is an upper bound on this
implementation while the *qualitative* claim (some stage is required; the closed
path requires none) is what the corollary proves. And part of the frequency gap
is combinational depth, 46 dependent stages against one addition; pipelining
converts that into latency and registers rather than removing it.

## The self-caught strawman

The first opponent built here was greedy Zeckendorf applied to weight
application, and it would have been a strawman: the identity
`F_m F_n = (L_{m+n} - (-1)^n L_{m-n})/5` -- verified over 300 index pairs before
any RTL was written -- turns a product into two Lucas-table lookups, a subtract
and a divide by five. Far cheaper than 46 compare-subtract stages.

Finding that identity is what showed the measurement was aimed at the wrong
operation. The comment at the top of our own `phi_step.v` had already stated the
rule -- *an unmatched comparison is wrong whichever way it points* -- and the
first draft of this measurement broke it in our favour.

**T27.** Build the opponent's strongest form before measuring, not their most
obvious one. The search for their best case is also the check on whether you are
measuring the right operation: the identity that would have rescued them is what
revealed that products were never where their cost lived.


## Reproducing this

This repository forbids shell scripts (`.claude/rules/no-shell-scripts.md`), and
the first version of this measurement shipped one. The recipe belongs in prose
where it can be read, not in a file the rules mark for deletion. Paste into a
zsh shell from `fpga/phiscale/`:

```
# The structural cost of non-closure, measured in the harness that produced the
# decoder table: isolated unit, EVERY output bit folded into the observed
# reduction, median of five placement seeds.
#
# The comparison is deliberately stacked against us. For the closed path we
# measure the WHOLE weight application. For the non-closed path we measure ONLY
# the transformation stage that non-closure forces -- none of the arithmetic
# that would sit on top of it. If the closed path is still smaller, the claim
# holds a fortiori.
NP=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/t27/target/nextpnr-xilinx/build/nextpnr-xilinx
CDB=/Users/ssdm4/Desktop/PROJECTS/CLAUDE/video-ax7203/build_lcd_diag2/chipdb/xc7a200tfbg484.bin
run() {  # $1 name  $2 instance  $3 sources  $4 observed-width
cat > c_$1.v <<V
\`default_nettype none
module c_$1 (input wire clk, input wire rst_n, output wire [3:0] led);
  reg [63:0] lf = 64'h1234_5678_9ABC_DEF0;
  always @(posedge clk) lf <= !rst_n ? 64'h1234_5678_9ABC_DEF0 : {lf[62:0], lf[63]^lf[62]^lf[60]^lf[59]};
  wire [$(($4-1)):0] o;
  $2
  reg [$(($4-1)):0] q;
  always @(posedge clk) q <= !rst_n ? {$4{1'b0}} : o;
  assign led = ^{q, 4'b0} ? (q[3:0] ^ q[$(($4-1)):$(($4-4))]) : 4'b0;
endmodule
V
yosys -q -p "read_verilog c_$1.v $3; synth_xilinx -flatten -nodsp -top c_$1 -json c_$1.json" > cy_$1.log 2>&1
[ -f c_$1.json ] || { echo "$1|СИНТЕЗ_НЕ_ПРОШЁЛ"; return; }
FS=""
for S in 1 2 3 4 5; do
  $NP --chipdb $CDB --xdc bench.xdc --json c_$1.json --seed $S --write /dev/null > cs_$1_$S.log 2>&1
  FS="$FS $(grep -oE "Max frequency for clock .[^']*.: [0-9.]+" cs_$1_$S.log|tail -1|grep -oE "[0-9.]+$")"
done
L=$(grep -oE "SLICE_LUTX: *[0-9]+" cs_$1_1.log|tail -1|grep -oE "[0-9]+$")
echo "$1|$L|$FS"
}
run phi16   "wire [15:0] oa,ob; phi_step #(.W(16)) u (.clk(clk),.dir(1'b0),.a(lf[15:0]),.b(lf[31:16]),.oa(oa),.ob(ob)); assign o = {oa,ob};" "phi_step.v" 32
run zeck16  "zeck_reenc16 u (.clk(clk),.x(lf[15:0]),.z(o));" "zeck_reenc16.v" 23
run phi32   "wire [31:0] oa,ob; phi_step #(.W(32)) u (.clk(clk),.dir(1'b0),.a(lf[31:0]),.b(lf[63:32]),.oa(oa),.ob(ob)); assign o = {oa,ob};" "phi_step.v" 64
run zeck32  "zeck_reenc32 u (.clk(clk),.x(lf[31:0]),.z(o));" "zeck_reenc32.v" 46
run zphi16  "wire [15:0] sa,sb; zphi_add #(.W(16)) u (.clk(clk),.a0(lf[15:0]),.b0(lf[31:16]),.a1(lf[47:32]),.b1(lf[63:48]),.sa(sa),.sb(sb)); assign o = {sa,sb};" "zphi_add.v" 32
run zphi32  "wire [31:0] sa,sb; zphi_add #(.W(32)) u (.clk(clk),.a0(lf[31:0]),.b0(lf[63:32]),.a1(lf[63:32]),.b1(lf[31:0]),.sa(sa),.sb(sb)); assign o = {sa,sb};" "zphi_add.v" 64
```

`bench.xdc` is copied from `fpga/tnet/`. Every output bit folds into the
observed reduction, so synthesis prunes each unit equally; five placement seeds
are run and the median reported.
