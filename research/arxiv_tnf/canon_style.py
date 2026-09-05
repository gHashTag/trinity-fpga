"""Engraving house style for the data figures.

Applies the canon-plate look — pure white ground, black line work, hatched
fills, serif lettering, a double base rule carrying the Trinity line and one
small solid triangle in the top-right corner — to the figures that are drawn
from data. It changes only ink: every value plotted still comes from the
generator that computed it.
"""
import itertools
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Polygon, Rectangle

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif", "DejaVu Sans"],
    "mathtext.fontset": "dejavuserif",
    "text.color": "black",
    "axes.labelcolor": "black",
    "axes.edgecolor": "black",
    "axes.linewidth": 0.8,
    "xtick.color": "black",
    "ytick.color": "black",
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.major.width": 0.7,
    "ytick.major.width": 0.7,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.grid": False,
    "hatch.linewidth": 0.55,
    "font.size": 8.5,
    "axes.titlesize": 9.5,
    "legend.fontsize": 7.5,
    "legend.handlelength": 3.0,
    "legend.handleheight": 1.5,
    "legend.labelspacing": 0.45,
    "legend.borderpad": 0.5,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
    "pdf.fonttype": 42,
})

BASE_LINE = ("TRINITY S3AI  -  the cognitive stack rooted in "
             "the identity  $\\varphi^{2}+\\varphi^{-2}=3$")

_HATCH = ["////", "....", "xxxx", "\\\\\\\\", "||||", "----", "++++", "oooo", "**"]

# Colour, on the white ground. The engraved look kept every series black and told
# them apart by hatch alone; at six or seven series on one axis that is a puzzle,
# not a figure. Series now carry colour AND hatch: the colour reads on screen,
# the hatch survives a monochrome print. The palette is Okabe-Ito, which stays
# distinguishable under the common colour-vision deficiencies.
_PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
            "#56B4E9", "#8C564B", "#7F3C8D", "#4C4C4C"]

_orig_bar = Axes.bar
_orig_barh = Axes.barh
_orig_plot = Axes.plot
_orig_annotate = Axes.annotate
_orig_axvspan = Axes.axvspan
_orig_savefig = Figure.savefig


_HMAP = {}
_CMAP = {}


def _hatch_for(c):
    """One stable hatch per colour the generators used, so legends agree."""
    key = str(c)
    if key not in _HMAP:
        _HMAP[key] = _HATCH[len(_HMAP) % len(_HATCH)]
    return _HMAP[key]


def pin(original, palette_colour):
    """Fix the palette colour a generator's colour maps to.

    Without this the mapping follows the order colours are first seen, which
    makes the meaning of a colour depend on which figure ran first."""
    _CMAP[str(original)] = palette_colour


# Fixed meaning for the colours the generators use, so a colour means the same
# thing in every figure regardless of which figure was drawn first.
_PINS = {
    "#0a7a4c": "#0072B2",   # ours / TNF, and the first magnitude band
    "#b9c6c1": "#CC79A7",   # GF16 -- kept away from binary16's vermillion
    "#7d8f99": "#009E73",   # takum
    "#98a0a8": "#9AA3AB",   # "not ours" in the ranked table stays neutral grey
    "#c8912f": "#56B4E9",   # posit
    "#b04a4a": "#D55E00",   # IEEE binary16
    "#4a5b8c": "#7F3C8D",   # bfloat16
    "#9b8bb4": "#4C4C4C",   # LNS16
    "#c46a6a": "#D55E00",
    "#4f9e7a": "#009E73",   # second magnitude band
    "#9cc4b2": "#E69F00",   # third magnitude band
    "#333": "#4C4C4C",
}
_CMAP.update(_PINS)


def _colour_for(c):
    """One stable palette colour per colour the generators used.

    Idempotent: barh() delegates to bar() inside matplotlib, so a horizontal bar
    chart passes through the remapper twice. Without this guard the second pass
    treated the palette colour as a fresh generator colour and mapped it again,
    which is how the ranked table came out pink and orange instead of blue and
    grey."""
    key = str(c)
    if key in _CMAP.values() or key in _PINS.values():
        return key
    if key not in _CMAP:
        _CMAP[key] = _PALETTE[len(_CMAP) % len(_PALETTE)]
    return _CMAP[key]


def _engrave_kwargs(ax, kwargs):
    cyc = getattr(ax, "_canon_hatch", None)
    if cyc is None:
        cyc = itertools.cycle(_HATCH)
        ax._canon_hatch = cyc
    ccyc = getattr(ax, "_canon_colour", None)
    if ccyc is None:
        ccyc = itertools.cycle(_PALETTE)
        ax._canon_colour = ccyc
    colors = kwargs.pop("color", None)
    if isinstance(colors, (list, tuple)):
        # per-bar colouring in the original is remapped onto the palette, and
        # each palette entry keeps its own hatch
        kwargs["color"] = [_colour_for(c) for c in colors]
        kwargs.setdefault("hatch", [_hatch_for(c) for c in colors])
    elif colors is not None:
        kwargs["color"] = _colour_for(colors)
        kwargs.setdefault("hatch", _hatch_for(colors))
    else:
        kwargs["color"] = next(ccyc)
        kwargs.setdefault("hatch", next(cyc))
    kwargs.setdefault("edgecolor", "black")
    kwargs.setdefault("linewidth", 0.7)
    return kwargs


_orig_text = Axes.text


def text(self, *a, **kw):
    # labels the generators drew white-on-colour sit inside a hatched bar now,
    # so they get a small opaque white cartouche to stay legible
    if str(kw.get("color", "")).lower() in ("white", "w", "#ffffff"):
        kw.setdefault("bbox", dict(facecolor="white", edgecolor="none",
                                   boxstyle="square,pad=0.15"))
    kw.setdefault("color", "black")
    return _orig_text(self, *a, **kw)


def bar(self, *a, **kw):
    return _orig_bar(self, *a, **_engrave_kwargs(self, kw))


def barh(self, *a, **kw):
    return _orig_barh(self, *a, **_engrave_kwargs(self, kw))


def plot(self, *a, **kw):
    ccyc = getattr(self, "_canon_line_colour", None)
    if ccyc is None:
        ccyc = itertools.cycle(_PALETTE)
        self._canon_line_colour = ccyc
    c = kw.get("color")
    kw["color"] = _colour_for(c) if c is not None else next(ccyc)
    kw.setdefault("markerfacecolor", "white")
    kw.setdefault("markeredgecolor", kw["color"])
    kw.setdefault("linewidth", 1.2)
    return _orig_plot(self, *a, **kw)


_SUB = {"\u2702": "*", "\u2713": "+"}


def _fix(t):
    if isinstance(t, str):
        for k, v in _SUB.items():
            t = t.replace(k, v)
    return t


_orig_set_title = Axes.set_title


def set_title(self, label, *a, **kw):
    return _orig_set_title(self, _fix(label), *a, **kw)


def annotate(self, text, *a, **kw):
    kw["color"] = "black"
    kw.setdefault("bbox", dict(facecolor="white", edgecolor="none",
                               boxstyle="square,pad=0.12"))
    return _orig_annotate(self, _fix(text), *a, **kw)


def axvspan(self, *a, **kw):
    kw["color"] = "#0072B2"
    kw["alpha"] = 0.10
    kw["facecolor"] = "#0072B2"
    kw["edgecolor"] = "none"
    kw.pop("hatch", None)
    kw["linewidth"] = 0.0
    return _orig_axvspan(self, *a, **kw)


def _dress(fig):
    """Double base rule with the Trinity line, and one small solid triangle."""
    for ax in fig.axes:
        if ax.get_yscale() == "log":
            lo, hi = ax.get_ylim()
            ax.set_ylim(lo, hi * 4.0)
        ax.yaxis.label.set_color("black")
        ax.xaxis.label.set_color("black")
        ax.tick_params(axis="both", which="both", colors="black")
        for lb in ax.get_xticklabels() + ax.get_yticklabels():
            lb.set_color("black")
        for sp in ax.spines.values():
            sp.set_color("black")
        for sp in ("top", "right"):
            if sp in ax.spines:
                ax.spines[sp].set_linewidth(0.5)
        lg = ax.get_legend()
        if lg is not None:
            # The legend key must carry the hatch of the artist it stands for.
            # Deriving it from the key's own facecolour is wrong: by this point
            # the bars have already been recoloured white, so every key would
            # come out with the same hatch -- a legend that cannot be matched
            # against the plot. Take the hatch from the labelled artist itself.
            labelled = {}
            for cont in getattr(ax, "containers", []):
                lab = cont.get_label()
                if lab and not lab.startswith("_") and len(cont):
                    labelled[lab] = cont[0]
            for ln in ax.get_lines():
                lab = ln.get_label()
                if lab and not lab.startswith("_"):
                    labelled.setdefault(lab, ln)
            for pa in ax.patches:
                lab = pa.get_label()
                if lab and not lab.startswith("_"):
                    labelled.setdefault(lab, pa)
            for h, t in zip(lg.legend_handles, lg.get_texts()):
                try:
                    src = labelled.get(t.get_text())
                    hatch = None
                    face = None
                    if src is not None:
                        if hasattr(src, "get_hatch"):
                            hatch = src.get_hatch()
                        if hasattr(src, "get_facecolor"):
                            face = src.get_facecolor()
                        elif hasattr(src, "get_color"):
                            face = src.get_color()
                    if hatch is None and hasattr(h, "get_facecolor"):
                        hatch = _hatch_for(
                            matplotlib.colors.to_hex(h.get_facecolor()))
                    if hasattr(h, "set_hatch"):
                        h.set_hatch(hatch)
                        if face is not None:
                            h.set_facecolor(face)
                        h.set_edgecolor("black")
                        h.set_linewidth(0.7)
                except Exception:
                    pass
            lg.get_frame().set_linewidth(0.5)
            lg.get_frame().set_edgecolor("black")
            for t in lg.get_texts():
                t.set_color("black")
        if ax.get_title():
            ax.set_title(ax.get_title(), fontfamily="serif", color="black")
    fig.subplots_adjust(bottom=fig.subplotpars.bottom)
    # Base rules and the Trinity line are placed under the real drawn extent of
    # the figure, measured with the renderer, so they can never cross an axis
    # label, a rotated tick, or a multi-line tick. The earlier fixed offsets
    # collided with exactly those three cases.
    H = fig.get_figheight()
    try:
        fig.canvas.draw()
        bb = fig.get_tightbbox(fig.canvas.get_renderer())
        y0 = bb.y0 / H            # lowest drawn point, in figure fractions
    except Exception:
        y0 = 0.0
    gap = 0.24 / H                # constant paper gap, not a fraction of height
    top_rule = y0 - gap
    for y in (top_rule, top_rule - 0.11 / H):
        fig.add_artist(plt.Line2D([0.02, 0.98], [y, y], transform=fig.transFigure,
                                  color="black", linewidth=0.6, clip_on=False))
    fig.text(0.5, top_rule + 0.05 / H, BASE_LINE, transform=fig.transFigure, ha="center",
             va="bottom", fontsize=6.6, style="italic", color="black",
             fontfamily="serif")
    # The Trinity mark is deliberately NOT drawn on plots: it belongs on the
    # engraved plates, not on measurement figures, where it reads as an artefact
    # of the axes.


def savefig(self, *a, **kw):
    _dress(self)
    kw.setdefault("bbox_inches", "tight")
    kw.setdefault("facecolor", "white")
    return _orig_savefig(self, *a, **kw)


Axes.bar = bar
Axes.barh = barh
Axes.plot = plot
Axes.annotate = annotate
Axes.set_title = set_title
Axes.text = text
Axes.axvspan = axvspan
Figure.savefig = savefig
