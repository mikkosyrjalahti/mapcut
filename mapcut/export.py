"""DXF output for LightBurn.

LightBurn assigns operations by entity colour, so colour is the contract; layer names are kept for
humans opening the file in CAD. Units are millimetres.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf
from ezdxf import units
from shapely.geometry import LineString, box

from . import font
from .config import Config
from .geom import rings
from .levels import Levels
from .panels import Panel
from .parts import Piece

# MANUAL: LightBurn layer mapping — red = cut, blue = guide engrave (line, low power),
# green = ID engrave (line), magenta = building outlines (closed: Line or Fill), cyan = road
# centrelines (Line). Disable any engrave layer in LightBurn to skip it. Put all engrave layers
# BEFORE the cut layer in LightBurn's order.
LAYERS = {"ENGRAVE_GUIDE": 5, "ENGRAVE_ID": 3, "ENGRAVE_BUILDING": 6, "ENGRAVE_ROAD": 4, "CUT": 1}
PANEL_GAP_MM = 5.0


def _new():
    doc = ezdxf.new("R2010", setup=False)
    doc.units = units.MM
    for name, colour in LAYERS.items():
        doc.layers.add(name, color=colour)
    return doc, doc.modelspace()


def _poly(msp, coords, layer: str, dx: float = 0.0, dy: float = 0.0, closed: bool = False) -> None:
    pts = [(x + dx, y + dy) for x, y in coords]
    if closed and pts[0] == pts[-1]:
        pts = pts[:-1]
    # Explicit colour, not BYLAYER: some CAM importers ignore layer colours.
    msp.add_lwpolyline(pts, close=closed, dxfattribs={"layer": layer, "color": LAYERS[layer]})


def write_blank(path: Path, j: int, lv: Levels, pieces: list[Piece], cfg: Config) -> None:
    """MANUAL: blank_<j>.dxf holds layers i ≡ j (mod k), every piece at its true map position."""
    doc, msp = _new()
    m = cfg.blank_margin_mm
    for pc in pieces:
        if pc.blank != j or not pc.ok:
            continue
        for ln in pc.guide:
            _poly(msp, ln.coords, "ENGRAVE_GUIDE", m, m)
        if pc.label:
            for s in pc.label.strokes():
                _poly(msp, s, "ENGRAVE_ID", m, m)
        for b in pc.buildings:
            for ring in [b.exterior, *b.interiors]:
                _poly(msp, ring.coords, "ENGRAVE_BUILDING", m, m, closed=True)
        for ln in pc.roads:
            _poly(msp, ln.coords, "ENGRAVE_ROAD", m, m)
    # Blank number in the margin below the map (blank coordinates, no offset).
    for s in font.render(f"B{j}", m, m * 0.3, min(4.0, m * 0.4)):
        _poly(msp, s, "ENGRAVE_ID")

    # Each contour i ≡ j is cut exactly once: it is both the outer edge of Q_i and the inner edge of Q_{i-k}.
    # Innermost (highest) first, so outer pieces are still held by the sheet while inner ones are cut.
    edge = lv.square.exterior.buffer(1e-3)
    for i in range(len(lv) - 1, 0, -1):
        if i % cfg.k != j:
            continue
        for ring in rings(lv.polys[i]):
            rest = LineString(ring.coords).difference(edge)
            if rest.equals(LineString(ring.coords)):
                _poly(msp, ring.coords, "CUT", m, m, closed=True)
            else:
                for part in getattr(rest, "geoms", [rest]):
                    if not part.is_empty:
                        _poly(msp, part.coords, "CUT", m, m)
    _poly(msp, lv.square.exterior.coords, "CUT", m, m, closed=True)
    doc.saveas(path)


def write_panels(path: Path, panels: list[Panel]) -> None:
    """MANUAL: panels.dxf — engraved letter faces INWARD; the stepped top edge follows the terrain."""
    doc, msp = _new()
    y = 0.0
    for p in panels:
        if p.label:
            for s in p.label.strokes():
                _poly(msp, s, "ENGRAVE_ID", 0, y)
        _poly(msp, p.outline.exterior.coords, "CUT", 0, y, closed=True)
        y += p.outline.bounds[3] + PANEL_GAP_MM
    doc.saveas(path)


def write_calibration(path: Path, cfg: Config) -> None:
    """MANUAL: cut this 100 mm coupon first. Check: square = 100.0 mm (scale/units), which width strips
    survive (set min_width_mm), ID legibility per text height, guide visibility per inset, and whether
    the nested squares stay in place on the bed (in-place cutting)."""
    doc, msp = _new()
    _poly(msp, box(0, 0, 100, 100).exterior.coords, "CUT", closed=True)
    # Width strips 20 mm long, labelled in tenths of a mm.
    x = 5.0
    for w in (0.6, 0.8, 1.0, 1.2, 1.5, 2.0):
        _poly(msp, box(x, 70, x + w, 90).exterior.coords, "CUT", closed=True)
        for s in font.render(f"{round(w * 10):02d}", x - 0.5, 92, 2.0):
            _poly(msp, s, "ENGRAVE_ID", 0, 0)
        x += max(w, 4.0) + 4.0
    # Text heights.
    y = 55.0
    for h in (1.2, 1.6, 2.0, 3.0):
        for s in font.render("0123456789-BNESW", 5, y, h):
            _poly(msp, s, "ENGRAVE_ID")
        y -= h + 3
    # Guide line next to a cut edge at several insets: which ones stay hidden under the next layer?
    for n, inset in enumerate((0.2, 0.4, 0.6)):
        x0 = 60 + n * 12
        _poly(msp, box(x0, 5, x0 + 10, 35).exterior.coords, "CUT", closed=True)
        _poly(msp, [(x0 + inset, 6), (x0 + inset, 34)], "ENGRAVE_GUIDE")
    # Building-sized closed shapes (1.0x1.0 .. 5x5 mm; median building here is ~2x2.5 mm) to compare
    # Line vs Fill engraving and time the fill; plus road centrelines.
    x = 5.0
    for w, h in ((1.0, 1.0), (1.5, 2.0), (2.0, 2.5), (3.0, 4.0), (5.0, 5.0)):
        _poly(msp, box(x, 22, x + w, 22 + h).exterior.coords, "ENGRAVE_BUILDING", closed=True)
        x += w + 4.0
    _poly(msp, box(5, 29, 50, 34).exterior.coords, "ENGRAVE_BUILDING", closed=True)
    for n in range(3):
        _poly(msp, [(5, 8 + 4 * n), (50, 8 + 4 * n + 2)], "ENGRAVE_ROAD")
    # Concentric squares sharing single cuts, like contours on a blank.
    for size in (30, 24, 18, 12, 6):
        o = (30 - size) / 2
        _poly(msp, box(60 + o, 50 + o, 60 + o + size, 50 + o + size).exterior.coords, "CUT", closed=True)
    doc.saveas(path)
