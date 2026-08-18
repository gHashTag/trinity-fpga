# Why these results are quarantined (2026-08-15)

`bench-20260815-080720.csv` (+ its `machine-20260815-080720.txt`) is the first
full N=5 Vivado campaign. Its `bitgen_s` column is CONTAMINATED by network
stalls and none of its rows may be published as benchmark numbers.

## What happened

Vivado 2026.1's Flexera RUI SDK telemetry (`~/.Xilinx/Vivado/.RUISDK`) phones
home during `write_bitstream`. On this egress-filtered host the TCP connects
hang in SYN retries, and that wall time is booked into the timed
`write_bitstream` phase. Example (identical deterministic work per run):

    litex-ddr-arty-s7-deephier bitgen_s = 138.68 / 282.69 / 140.69 / 14.13 / 407.99

True value is ~13 s (run 4 above; confirmed by 3x namespace-isolated
verification runs after hardening).

The harness DID export `http_proxy`/`https_proxy` (+ uppercase) pointing at a
closed local port (127.0.0.1:9). That was not sufficient: the RUI SDK issues
raw `connect()` calls that never consult the proxy environment. Endpoints
observed via `ss -tnp` attached to the vivado pid (diag/ss-sample.log,
diag/ss-diagA.log):

- 67.227.186.229:443  (Flexera) — stuck in SYN-SENT, minutes of retries
- 72.52.161.233:443   (Flexera) — sometimes ESTABlishes, slow exchange
- 169.254.169.254:80  (cloud metadata probe) — stuck in SYN-SENT

The stall is nondeterministic (depends on which endpoint/retry cadence the
telemetry thread hits during the timed window), which is why run 4 came out
clean at 14.13 s while run 5 lost 394 s.

## Also wrong in this CSV

- The 5 `picosoc` rows are the kx2 configuration (xc7k160tffg676-2, kx2.v,
  picosoc-kx2.xdc): ALL FAILED with DRC PLIO-9 (clock LOCed to an N-type
  CCIO). The row was replaced by the qmtech configuration
  (xc7k325tffg676-1, qmtech.v) for campaign v2; the old row is preserved in
  designs.tsv.bak-kx2.
- The 5 `litex-ddr-arty-s7` (main revision) rows: ALL FAILED with DRC
  BIVRU-1 (Bank 34 SSTL135 needs INTERNAL_VREF; VREF sites occupied) — a
  design/constraint property of the frozen main revision, not a harness
  problem.

## Fix applied for campaign v2

Every vivado invocation in bench.sh now runs inside a rootless user+network
namespace (`unshare -r -n`): only loopback exists, `connect()` fails instantly
with ENETUNREACH, no SYN retries possible. The FlexNet node-locked license
hostid (host MAC) is satisfied by recreating the MAC on a dummy `lic0`
interface inside the namespace (no external connectivity). See the comment
block in bench.sh.

Keep these files as evidence of the contamination; never use them as
benchmark rows.
