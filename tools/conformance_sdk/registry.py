"""Registry — discover every golden oracle in conformance/*_ref.py and expose a
unified (family, name, fmt_obj, width) catalog.

All `*_ref.py` modules follow the same convention:
  FORMATS: dict[str, <Format>]   # name -> format descriptor object
  decode(fmt, raw) -> value      # golden decode
  encode(fmt, value) -> raw      # golden encode (optional per ref)
  format_add / format_mul (optional)
The descriptor objects carry width under varying attribute names (.width/.W/
.total/.bits/.nbits); we probe heuristically and fall back to parsing the name.
"""
from __future__ import annotations
import sys
import importlib.util
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONF = os.path.join(REPO, "conformance")


def _load_ref_module(path: str):
    name = "cf_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # Register before executing: a module using @dataclass looks itself up in
    # sys.modules while the decorator runs, and under a synthetic name it is not
    # there. conformance/takum_log_ref.py fails exactly that way, so an
    # unregistered loader omitted it silently.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # refs are self-contained (fractions, no heavy deps)
    return mod


def _guess_width(fmt, name: str) -> int:
    for attr in ("width", "W", "total", "bits", "nbits", "N"):
        v = getattr(fmt, attr, None)
        if isinstance(v, int):
            return v
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else 0


def _family_from_filename(fname: str) -> str:
    return os.path.splitext(fname)[0].removesuffix("_ref")


class FormatEntry:
    __slots__ = ("family", "name", "fmt", "width", "ref")

    def __init__(self, family, name, fmt, width, ref):
        self.family = family
        self.name = name
        self.fmt = fmt
        self.width = width
        self.ref = ref

    def decode(self, raw: int):
        return self.ref.decode(self.fmt, raw)

    def encode(self, value):
        if hasattr(self.ref, "encode"):
            return self.ref.encode(self.fmt, value)
        raise AttributeError(f"{self.family}_ref has no encode()")

    def __repr__(self):
        return f"<Format {self.name} [family={self.family} width={self.width}]>"


def catalog() -> dict[str, FormatEntry]:
    """Return {format_name: FormatEntry} over every golden oracle."""
    out: dict[str, FormatEntry] = {}
    if not os.path.isdir(CONF):
        return out
    for fn in sorted(os.listdir(CONF)):
        if not fn.endswith("_ref.py") or fn.startswith("_"):
            continue
        path = os.path.join(CONF, fn)
        try:
            mod = _load_ref_module(path)
        except Exception as e:  # a ref may fail to import on a minimal box
            continue
        formats = getattr(mod, "FORMATS", None)
        if not isinstance(formats, dict):
            continue
        family = _family_from_filename(fn)
        for name, fmt in formats.items():
            if name in out:
                continue  # first ref wins; avoids collisions across modules
            out[name] = FormatEntry(family, name, fmt, _guess_width(fmt, name), mod)
    return out


def get_format(name: str) -> FormatEntry:
    cat = catalog()
    key = name.strip().lower()
    # exact, then case-insensitive, then family-prefix match
    if name in cat:
        return cat[name]
    for k, v in cat.items():
        if k.lower() == key:
            return v
    fam = key.split("_")[0]
    matches = [v for k, v in cat.items() if k.lower().startswith(fam)]
    if len(matches) == 1:
        return matches[0]
    raise KeyError(f"format {name!r} not found; available: {sorted(cat)[:12]}...")


def list_families() -> dict[str, int]:
    cat = catalog()
    fam: dict[str, int] = {}
    for e in cat.values():
        fam[e.family] = fam.get(e.family, 0) + 1
    return dict(sorted(fam.items(), key=lambda kv: (-kv[1], kv[0])))
