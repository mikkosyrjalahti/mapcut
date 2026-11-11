"""Cumulative level polygons P_i = {h >= z_i}, in model millimetres, strictly nested."""

from __future__ import annotations

import math
from dataclasses import dataclass

import contourpy
import numpy as np
import shapely
from scipy.ndimage import gaussian_filter
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry

from .config import Config
from .dem import Grid
from .geom import polygonal


@dataclass(frozen=True)
class Levels:
    z: list[float]  # elevation of level i, metres
    polys: list[BaseGeometry]  # P_i in model mm; polys[i+1] is inside polys[i]
    square: Polygon  # map outline, (0,0) = south-west corner

    def __len__(self) -> int:
        return len(self.z)


def build_levels(grid: Grid, sq_x0: float, sq_y0: float, cfg: Config) -> Levels:
    f = cfg.mm_per_m
    # Smooth the surface once, before contouring: unlike per-polygon smoothing it cannot break nesting.
    sigma_px = cfg.blur_sigma_mm / f / grid.res
    zb = gaussian_filter(grid.z, sigma=sigma_px, mode="nearest")[::-1]  # flip so y increases with row
    nrows, ncols = zb.shape
    # Convert to model mm here, at the single geo -> model boundary.
    xs = (grid.x0 + (np.arange(ncols) + 0.5) * grid.res - sq_x0) * f
    ys = (grid.y_top - (np.arange(nrows)[::-1] + 0.5) * grid.res - sq_y0) * f

    side = cfg.map_mm
    square = box(0, 0, side, side)
    inside = zb[np.ix_((ys >= 0) & (ys <= side), (xs >= 0) & (xs <= side))]
    dz = cfg.interval_m
    base = cfg.base_m if cfg.base_m is not None else math.floor(inside.min() / dz) * dz
    if base > inside.min():
        raise ValueError(f"base_m {base} is above the lowest terrain {inside.min():.2f}; the model would have holes")

    gen = contourpy.contour_generator(xs, ys, zb, fill_type=contourpy.FillType.OuterOffset)
    upper = float(zb.max()) + 1.0
    r = cfg.smooth_radius_mm
    zs, polys = [base], [polygonal(square)]
    i = 1
    while (z := base + i * dz) <= inside.max():
        p = _filled(gen, z, upper)
        # Open then close: removes sub-2r specks and notches. Both are monotone, so nesting survives;
        # contouring the full margin first keeps the rounding off the map edge.
        p = p.buffer(-r, quad_segs=4).buffer(2 * r, quad_segs=4).buffer(-r, quad_segs=4)
        p = p.simplify(cfg.simplify_mm, preserve_topology=True)
        # Simplification is not monotone; re-impose P_i inside P_{i-1} by construction rather than validate later.
        p = polygonal(p.intersection(square).intersection(polys[-1]))
        if p.is_empty:
            break
        zs.append(z)
        polys.append(p)
        i += 1
    return Levels(z=zs, polys=polys, square=square)


def _filled(gen: contourpy.ContourGenerator, lower: float, upper: float) -> BaseGeometry:
    pts_list, offs_list = gen.filled(lower, upper)
    parts = []
    for pts, offs in zip(pts_list, offs_list):
        rs = [pts[offs[a] : offs[a + 1]] for a in range(len(offs) - 1)]
        parts.append(Polygon(rs[0], rs[1:]))
    return polygonal(shapely.union_all(parts)) if parts else polygonal(Polygon())
