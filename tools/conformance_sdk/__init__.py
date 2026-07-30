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
    inputs and report the bit-exact / value match rate.

Not in v0.1: encode/round-trip audit of arbitrary external encoders, HW-in-loop
(the HW path lives in the AX7203 conformance scripts). The architecture is
extensible via per-ref adapters in `registry.py`.
"""
from .registry import catalog, get_format, list_families
from .checker import check_decoder, audit_report

__all__ = ["catalog", "get_format", "list_families", "check_decoder", "audit_report"]
__version__ = "0.1.0"
