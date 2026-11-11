"""PNG previews: what each blank looks like, and the assembled top view."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402

from .config import Config  # noqa: E402
from .geom import polygons  # noqa: E402
from .levels import Levels  # noqa: E402
from .panels import Panel  # noqa: E402
from .parts import Piece  # noqa: E402


def _patch(poly, **kw) -> PathPatch:
    verts, codes = [], []
    for ring in [poly.exterior, *poly.interiors]:
        xy = list(ring.coords)
        verts += xy
        codes += [MplPath.MOVETO] + [MplPath.LINETO] * (len(xy) - 2) + [MplPath.CLOSEPOLY]
    return PathPatch(MplPath(verts, codes), **kw)


def render(out: Path, lv: Levels, pieces: list[Piece], panels: list[Panel], cfg: Config) -> None:
    side = cfg.map_mm
    cmap = plt.get_cmap("terrain")
    fig, axes = plt.subplots(1, cfg.k + 1, figsize=(6 * (cfg.k + 1), 6.4))
    ax = axes[0]
    for i, p in enumerate(lv.polys):
        for poly in polygons(p):
            ax.add_patch(_patch(poly, facecolor=cmap(0.15 + 0.8 * i / len(lv)), edgecolor="k", lw=0.2))
    for pc in pieces:
        if not pc.ok:
            for poly in polygons(pc.geom):
                ax.add_patch(_patch(poly, facecolor="red", edgecolor="none"))
        # Features sit only on visible faces, so drawing all of them shows the finished top view.
        for b in pc.buildings:
            ax.add_patch(_patch(b, facecolor="#333", edgecolor="none"))
        for ln in pc.roads:
            ax.plot(*ln.xy, color="#333", lw=0.6)
    ax.set_title("assembled (red = dropped)")
    for j in range(cfg.k):
        ax = axes[j + 1]
        for pc in pieces:
            if pc.blank != j:
                continue
            ax.add_patch(_patch(pc.geom, facecolor="#e8d9b5" if pc.ok else "#f4b0b0", edgecolor="red", lw=0.3))
            for ln in pc.guide:
                ax.plot(*ln.xy, color="blue", lw=0.3)
            if pc.label:
                for s in pc.label.strokes():
                    ax.plot(*zip(*s), color="green", lw=0.4)
            for b in pc.buildings:
                ax.add_patch(_patch(b, facecolor="none", edgecolor="magenta", lw=0.3))
            for ln in pc.roads:
                ax.plot(*ln.xy, color="c", lw=0.5)
        ax.set_title(f"blank B{j}: layers {', '.join(str(i) for i in range(j, len(lv), cfg.k))}")
    for ax in axes:
        ax.set_xlim(0, side)
        ax.set_ylim(0, side)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(out / "preview.png", dpi=110)
    plt.close(fig)

    fig, axes = plt.subplots(len(panels), 1, figsize=(12, 1.2 * len(panels) + 1))
    for ax, p in zip(axes, panels):
        ax.add_patch(_patch(p.outline, facecolor="#e8d9b5", edgecolor="red", lw=0.5))
        ax.set_xlim(-2, p.outline.bounds[2] + 2)
        ax.set_ylim(0, max(q.outline.bounds[3] for q in panels) + 1)
        ax.set_aspect("equal")
        ax.set_title(f"panel {p.name} (seen from inside)", fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "panels.png", dpi=110)
    plt.close(fig)
