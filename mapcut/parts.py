"""Layer pieces Q_i = P_i \\ P_{i+k}, their engraved IDs and placement guides."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import polylabel

from . import font
from .config import Config
from .geom import lines, points, polygons
from .levels import Levels

LABEL_CLEARANCE_MM = 0.4  # keep text this far from cuts and from the guide line


# Upright (north-up) first: it doubles as an orientation cue. Rotations are a fallback for
# narrow overlap bands, where upright text does not fit.
LABEL_ANGLES = (0, 30, -30, 60, -60, 90)


@dataclass(frozen=True)
class Label:
    text: str
    cx: float  # centre of the text box
    cy: float
    height: float
    angle: float = 0.0  # degrees, counter-clockwise

    def strokes(self) -> list[list[tuple[float, float]]]:
        w = font.width(self.text, self.height)
        a = math.radians(self.angle)
        ca, sa = math.cos(a), math.sin(a)
        return [
            [(self.cx + x * ca - y * sa, self.cy + x * sa + y * ca) for x, y in s]
            for s in font.render(self.text, -w / 2, -self.height / 2, self.height)
        ]


@dataclass
class Piece:
    layer: int
    blank: int
    z_m: float
    geom: Polygon
    id: str
    status: str  # "ok" | "dropped_small" | "dropped_thin"
    label: Label | None = None
    guide: list[LineString] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    buildings: list[Polygon] = field(default_factory=list)  # outlines on the visible face
    roads: list[LineString] = field(default_factory=list)  # centrelines on the visible face
    tabs: list[Point] = field(default_factory=list)  # points on the outline left uncut

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def build_pieces(lv: Levels, cfg: Config) -> list[Piece]:
    P, n, k = lv.polys, len(lv), cfg.k
    inset = cfg.guide_inset_mm
    # Where P_{i+1} runs along the map edge its outline is the edge itself; the side panel aligns it there.
    edge_band = lv.square.difference(lv.square.buffer(-2 * inset))
    heights = _ladder(cfg.id_height_mm, cfg.id_min_height_mm)
    pieces: list[Piece] = []
    for i in range(n):
        q = P[i].difference(P[i + k]) if i + k < n else P[i]
        above = P[i + 1] if i + 1 < n else None
        guide_src = above.buffer(-inset).boundary.difference(edge_band) if above is not None else None
        # Text goes only where layer i+1 will cover it, clear of the guide line.
        hidden = above.buffer(-(inset + LABEL_CLEARANCE_MM)) if above is not None else None
        # Deterministic order (largest first) gives stable IDs for identical inputs.
        comps = sorted(polygons(q), key=lambda g: (-round(g.area, 3), round(g.centroid.x, 3), round(g.centroid.y, 3)))
        kept = dropped = 0
        for g in comps:
            status = _status(g, cfg)
            if status == "ok":
                kept += 1
                pid = f"{i:02d}-{kept:02d}"
            else:
                dropped += 1
                pid = f"{i:02d}-x{dropped:02d}"
            pc = Piece(layer=i, blank=i % k, z_m=lv.z[i], geom=g, id=pid, status=status)
            if pc.ok:
                _decorate(pc, guide_src, hidden, heights, cfg)
                if g.area <= cfg.tab_max_area_mm2:
                    pc.tabs = tab_points(g, cfg.tab_angles_deg)
            pieces.append(pc)
    return pieces


def tab_points(g: Polygon, angles_deg) -> list[Point]:
    """MANUAL: small pieces are held by tabs where rays at the given angles (0 = east, CCW) from the
    piece's interior centre first meet its outline. Each tab joins the piece to its neighbour on the
    same blank (or the blank margin); break it and sand the nub on the visible edge."""
    # Pole of inaccessibility, not centroid: the centroid of a concave piece can lie outside it.
    c = polylabel(g, tolerance=0.05)
    minx, miny, maxx, maxy = g.bounds
    reach = math.hypot(maxx - minx, maxy - miny) + 1.0
    out = []
    for a in angles_deg:
        r = math.radians(a)
        ray = LineString([(c.x, c.y), (c.x + reach * math.cos(r), c.y + reach * math.sin(r))])
        hits = points(ray.intersection(g.exterior))
        if hits:
            out.append(min(hits, key=c.distance))
    return out


def _status(g: Polygon, cfg: Config) -> str:
    if g.area < cfg.min_area_mm2:
        return "dropped_small"
    if g.buffer(-cfg.min_width_mm / 2).is_empty:
        return "dropped_thin"
    return "ok"


def _decorate(pc: Piece, guide_src, hidden, heights: list[float], cfg: Config) -> None:
    g = pc.geom
    # A neck narrower than min_width survives the filter above but may snap during handling.
    w = cfg.min_width_mm / 2
    if len(polygons(g.buffer(-w).buffer(w))) > 1:
        pc.notes.append("thin_neck")
    if guide_src is not None:
        pc.guide = [ln for ln in lines(guide_src.intersection(g)) if ln.length > 0.5]
    region = g.buffer(-LABEL_CLEARANCE_MM).intersection(hidden) if hidden is not None else None
    if region is None or g.intersection(hidden.buffer(LABEL_CLEARANCE_MM + cfg.guide_inset_mm)).area < 1.0:
        # Local summit (knoll, embankment crest): its whole face is visible, so no hidden ID by design.
        # It is found by its position in the blank and by the guide engraved on the layer below.
        pc.notes.append("top_piece_no_id")
        return
    # MANUAL: pieces are engraved with their LAYER number only. In-place cutting makes the blank a
    # map-shaped tray, so position + the guide below identify a piece; the engraving only has to stop
    # it going onto the wrong level. Two digits fit far more pieces than the full LL-PP id.
    pc.label = place_label(region, f"{pc.layer:02d}", heights)
    if pc.label is None:
        pc.notes.append("no_room_for_id")
    elif pc.label.height < heights[0]:
        pc.notes.append(f"id_small_{pc.label.height:.2f}mm")


def place_label(region: BaseGeometry, text: str, heights: list[float], angles=LABEL_ANGLES) -> Label | None:
    parts = sorted(polygons(region), key=lambda p: -p.area)
    for h in heights:
        w = font.width(text, h)
        for p in parts:
            if p.area < w * h:
                continue
            cands = list(_candidates(p, h))
            for angle in angles:
                shape = rotate(box(-w / 2, -h / 2, w / 2, h / 2), angle, origin=(0, 0))
                for c in cands:
                    if translate(shape, c.x, c.y).within(p):
                        return Label(text, c.x, c.y, h, angle)
    return None


def _candidates(p: Polygon, step: float, limit: int = 300):
    """Pole of inaccessibility first, then a grid ordered by distance from the outline."""
    yield polylabel(p, tolerance=0.05)
    minx, miny, maxx, maxy = p.bounds
    pts = []
    y = miny + step / 2
    while y < maxy:
        x = minx + step / 2
        while x < maxx:
            pt = Point(x, y)
            if p.contains(pt):
                pts.append(pt)
            x += step
        y += step
    pts.sort(key=lambda q: -p.exterior.distance(q))
    yield from pts[:limit]


def _ladder(start: float, stop: float, step: float = 0.2) -> list[float]:
    out, h = [], start
    while h >= stop - 1e-9:
        out.append(round(h, 3))
        h -= step
    return out

