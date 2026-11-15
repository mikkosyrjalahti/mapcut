"""DXF output for LightBurn.

LightBurn assigns operations by entity colour, so colour is the contract; layer names are kept for
humans opening the file in CAD. Units are millimetres.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf
import shapely
from ezdxf import units
from shapely.geometry import LineString, Point, box

from . import font
from .config import Config
from .geom import lines, rings
from .levels import Levels
from .panels import Panel
from .parts import Piece

# MANUAL: LightBurn layer mapping — red = cut, yellow = map perimeter cut, blue = guide engrave
# (line, low power), green = ID engrave (line), magenta = building outlines (closed: Line or Fill),
# cyan = road centrelines (Line). Disable any engrave layer in LightBurn to skip it. Order: engraves,
# then red, then yellow LAST.
# The perimeter is its own layer because the optimiser cannot order it reliably within one layer:
# edge-touching contours are open paths, so "cut inner shapes first" does not see them as inside the
# square. Cut early, the perimeter frees the whole map from the rim and parts warp out of focus.
# Yellow, not a near-red colour, so LightBurn cannot merge it into the red layer on import.
LAYERS = {
    "ENGRAVE_GUIDE": 5,
    "ENGRAVE_ID": 3,
    "ENGRAVE_BUILDING": 6,
    "ENGRAVE_ROAD": 4,
    "CUT": 1,
    "CUT_PERIMETER": 2,
}
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

    tabs = [t for pc in pieces if pc.blank == j and pc.ok for t in pc.tabs]
    inner, perimeter = cut_lines(lv, j, tabs, cfg)
    for layer, lns in (("CUT", inner), ("CUT_PERIMETER", perimeter)):
        for ln in lns:
            _poly(msp, ln.coords, layer, m, m, closed=ln.is_closed)
    doc.saveas(path)


def cut_lines(lv: Levels, j: int, tabs: list[Point], cfg: Config) -> tuple[list[LineString], list[LineString]]:
    """(inner, perimeter) cut paths for blank j in map mm, with an uncut gap at every tab.

    Inner contours are innermost first; the map-square perimeter is returned separately so it can be
    cut after all of them (see LAYERS)."""
    # Each contour i ≡ j is cut exactly once: it is both the outer edge of Q_i and the inner edge of Q_{i-k}.
    # Innermost (highest) first, so outer pieces are still held by the sheet while inner ones are cut.
    edge = lv.square.exterior.buffer(1e-3)
    out: list[LineString] = []
    for i in range(len(lv) - 1, 0, -1):
        if i % cfg.k == j:
            for ring in rings(lv.polys[i]):
                out += lines(shapely.line_merge(LineString(ring.coords).difference(edge)))
    perimeter = [LineString(lv.square.exterior.coords)]
    if not tabs:
        return out, perimeter
    # A tab may also fall on a neighbouring same-blank contour closer than half a tab width; that only
    # adds an extra holding point, so it is not worth special-casing. Tabs on the map edge stay: they
    # hold the finished map in the sheet.
    gaps = shapely.union_all([t.buffer(cfg.tab_width_mm / 2) for t in tabs])

    def gapped(lns: list[LineString]) -> list[LineString]:
        return [part for ln in lns for part in lines(shapely.line_merge(ln.difference(gaps)))]

    return gapped(out), gapped(perimeter)


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
    # Perimeter layer like a real blank, so the coupon also tests the layer order.
    _poly(msp, box(0, 0, 100, 100).exterior.coords, "CUT_PERIMETER", closed=True)
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
