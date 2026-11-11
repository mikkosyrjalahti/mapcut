"""Stepped side panels: close the hollow shell at the map edges and act as an alignment fence."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString, Point, Polygon

from .config import Config
from .levels import Levels
from .parts import Label, place_label

EDGE_PROBE_MM = 0.05  # sample just inside the edge; P_i boundaries lie exactly on it
MIN_STEP_MM = 0.5  # shorter profile steps are merged; they cannot be cut or seen


@dataclass(frozen=True)
class Panel:
    name: str
    outline: Polygon  # panel-local mm: x along the panel, y up from the table
    label: Label | None


def build_panels(lv: Levels, cfg: Config) -> list[Panel]:
    side, t = cfg.map_mm, cfg.thickness_mm
    e = EDGE_PROBE_MM
    # Each edge is traversed as seen from INSIDE the model, so the engraved face ends up hidden.
    edges = {
        "S": ((side, e), (-1.0, 0.0)),
        "N": ((0.0, side - e), (1.0, 0.0)),
        "W": ((e, 0.0), (0.0, 1.0)),
        "E": ((side - e, side), (0.0, -1.0)),
    }
    panels = []
    for name, (start, d) in edges.items():
        steps = _profile(lv, start, d, side, t)
        # N and S run past the corners to cover the end grain of E and W.
        ext = t if name in "NS" else 0.0
        pts = [(0.0, 0.0), (0.0, steps[0][2])]
        for s0, s1, h in steps:
            pts += [(s0 + ext, h), (s1 + ext, h)]
        pts += [(side + 2 * ext, steps[-1][2]), (side + 2 * ext, 0.0)]
        outline = Polygon(pts).simplify(0)
        label = place_label(outline.buffer(-0.5), name, [2.0, 1.6, 1.2])
        panels.append(Panel(name, outline, label))
    return panels


def _profile(lv: Levels, start, d, length: float, t: float) -> list[tuple[float, float, float]]:
    """(s0, s1, height) runs along the edge; height = stacked layer count x thickness."""
    line = LineString([start, (start[0] + d[0] * length, start[1] + d[1] * length)])
    cuts = {0.0, length}
    for p in lv.polys[1:]:
        for b in _endpoints(line.intersection(p)):
            cuts.add(round(line.project(b), 4))
    xs = sorted(cuts)
    runs: list[list[float]] = []
    for s0, s1 in zip(xs, xs[1:]):
        if s1 - s0 < 1e-6:
            continue
        mid = line.interpolate((s0 + s1) / 2)
        top = max(i for i, p in enumerate(lv.polys) if p.covers(mid))
        h = (top + 1) * t
        if runs and (runs[-1][2] == h or s1 - s0 < MIN_STEP_MM):
            runs[-1][1] = s1
        else:
            runs.append([s0, s1, h])
    return [tuple(r) for r in runs]


def _endpoints(g):
    if g.is_empty:
        return []
    if hasattr(g, "geoms"):
        return [pt for part in g.geoms for pt in _endpoints(part)]
    if isinstance(g, Point):
        return [g]
    return [Point(g.coords[0]), Point(g.coords[-1])]
