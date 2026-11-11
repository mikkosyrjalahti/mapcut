"""Manifest (one row per piece) and a short text report."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from .config import Config
from .levels import Levels
from .panels import Panel
from .parts import Piece

ATTRIBUTION = (
    "Contains data from the National Land Survey of Finland Elevation model 2 m "
    "and Topographic Database (CC BY 4.0)"
)


def write_manifest(path: Path, pieces: list[Piece]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["piece_id", "layer", "z_m", "blank", "status", "area_mm2", "cx_mm", "cy_mm", "id_height_mm", "tabs", "notes"])
        for pc in pieces:
            c = pc.geom.centroid
            w.writerow([
                pc.id, pc.layer, f"{pc.z_m:.2f}", pc.blank, pc.status, f"{pc.geom.area:.1f}",
                f"{c.x:.1f}", f"{c.y:.1f}", f"{pc.label.height:.2f}" if pc.label else "", len(pc.tabs), ";".join(pc.notes),
            ])


def summary(lv: Levels, pieces: list[Piece], panels: list[Panel], cfg: Config) -> str:
    ok = [p for p in pieces if p.ok]
    notes = Counter(n.split("_")[0] if n.startswith("id_small") else n for p in ok for n in p.notes)
    status = Counter(p.status for p in pieces)
    lines = [
        f"map               {cfg.map_mm:.0f} x {cfg.map_mm:.0f} mm at 1:{cfg.scale}",
        f"levels            {len(lv)}  ({lv.z[0]:.1f} .. {lv.z[-1]:.1f} m, every {cfg.interval_m} m)",
        f"vertical exagg.   {cfg.vertical_exaggeration:.2f}x",
        f"stack height      {len(lv) * cfg.thickness_mm:.1f} mm",
        f"blanks (k)        {cfg.k}",
        f"pieces kept       {len(ok)}   " + "  ".join(f"B{j}: {sum(p.blank == j for p in ok)}" for j in range(cfg.k)),
        f"pieces dropped    {status['dropped_small']} small, {status['dropped_thin']} thin "
        f"({sum(p.geom.area for p in pieces if not p.ok):.0f} mm² total)",
        "piece notes       " + (", ".join(f"{k}: {v}" for k, v in sorted(notes.items())) or "none"),
        f"tabbed pieces     {sum(bool(p.tabs) for p in ok)} ({sum(len(p.tabs) for p in ok)} tabs, {cfg.tab_width_mm} mm, pieces <= {cfg.tab_max_area_mm2:.0f} mm²)",
        f"engraved features {sum(len(p.buildings) for p in ok)} building outlines, "
        f"{sum(ln.length for p in ok for ln in p.roads):.0f} mm of road centreline",
        "panels            " + ", ".join(f"{p.name} {p.outline.bounds[2]:.1f}x{p.outline.bounds[3]:.1f} mm" for p in panels),
        "",
        ATTRIBUTION,
    ]
    return "\n".join(lines) + "\n"
