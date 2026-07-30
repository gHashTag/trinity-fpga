"""Trinity Conformance SDK — audit low-precision numeric decoders against the
Trinity SSOT golden oracles.

This is the tooling counterpart of the "format-conformance infrastructure"
pitched in `docs/funding/TRI-NET_grant_onepager_RU.md`: a single API/CLI that
lets an ML team plug in THEIR decoder (FP8/MX/NF4/posit/...) and get a bit-exact
audit against the independent golden references in `conformance/*_ref.py`.

v0.1 scope:
  * discover all golden oracles (`*_ref.py`) and their formats into one registry;
  * `report` — one-command status of every format (family, width, availability);
  * `check` — run a user-supplied decoder against the golden over random + vector
    inputs and report the bit-exact / value match rate;
  * `encode` / `roundtrip` — golden encode of a single value, and encode/decode
    round-trip audit (encode-stability + idempotence) over the format grid;
  * `fp8-audit` — audit a built-in naive IEEE fp8 decoder against the golden to
    expose the e4m3 no-Inf / NaN-at-max trap (teaching control).

Not in v0.1: ADD/MUL compute-audit of external kernels, HW-in-loop (the HW path
lives in the AX7203 conformance scripts). The architecture is extensible via
per-ref adapters in `registry.py`.
"""
from .registry import catalog, get_format, list_families
from .checker import check_decoder, audit_report
from .roundtrip import check_roundtrip, encode_value
from .fp8_audit import audit_fp8, naive_ieee_fp8

__all__ = ["catalog", "get_format", "list_families", "check_decoder", "audit_report",
           "check_roundtrip", "encode_value", "audit_fp8", "naive_ieee_fp8"]
__version__ = "0.2.0"
