"""Elevation data access. The only module that deals with geographic coordinates."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

from .config import Config

# SERVICE_GUIDE: NLS 2 m DEM for all of Finland, mirrored by CSC Paituli. No API key needed;
# GDAL reads only the blocks covering the requested window. Licence CC BY 4.0 (NLS).
PAITULI_VRT = "/vsicurl/https://www.nic.funet.fi/index/geodata/mml/dem2m/dem2m_direct.vrt"
CRS_EPSG = 3067
NODATA = -9999.0
FETCH_MARGIN_M = 100.0  # room for blurring beyond the map edge


@dataclass(frozen=True)
class Grid:
    z: np.ndarray  # rows run north to south
    x0: float  # west edge of column 0, metres
    y_top: float  # north edge of row 0, metres
    res: float


def tile_square(cfg: Config) -> tuple[float, float]:
    """South-west corner of the map square in EPSG:3067, snapped to the 2 m DEM grid."""
    to_tm35 = Transformer.from_crs("EPSG:4326", f"EPSG:{CRS_EPSG}", always_xy=True)
    e, n = to_tm35.transform(cfg.center_lon, cfg.center_lat)
    half = cfg.size_m / 2
    return round((e - half) / 2) * 2.0, round((n - half) / 2) * 2.0


def fetch(cfg: Config, force: bool = False) -> bool:
    """MANUAL: `mapcut fetch` downloads the tile plus margin to `input.dem`. Returns False if cached."""
    if cfg.dem.exists() and not force:
        return False
    sx, sy = tile_square(cfg)
    m = FETCH_MARGIN_M
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"), rasterio.open(PAITULI_VRT) as src:
        win = from_bounds(sx - m, sy - m, sx + cfg.size_m + m, sy + cfg.size_m + m, src.transform)
        z = src.read(1, window=win)
        profile = src.profile | dict(
            driver="GTiff", width=z.shape[1], height=z.shape[0], transform=src.window_transform(win), compress="deflate"
        )
    for key in ("blockxsize", "blockysize", "tiled"):
        profile.pop(key, None)
    if (z == NODATA).any():
        raise ValueError("DEM window contains nodata (sea outside coverage or Finland border); move the tile")
    cfg.dem.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(cfg.dem, "w", **profile) as dst:
        dst.write(z, 1)
    return True


def load(cfg: Config) -> Grid:
    with rasterio.open(cfg.dem) as src:
        if src.crs is None or src.crs.to_epsg() != CRS_EPSG:
            raise ValueError(f"{cfg.dem}: expected EPSG:{CRS_EPSG}, got {src.crs}")
        t = src.transform
        if t.b != 0 or t.d != 0 or abs(t.a) != abs(t.e):
            raise ValueError("DEM must be north-up with square pixels")
        z = src.read(1).astype(np.float64)
        nodata = src.nodata
    if nodata is not None and (z == nodata).any():
        raise ValueError("DEM contains nodata")
    grid = Grid(z=z, x0=t.c, y_top=t.f, res=t.a)
    sx, sy = tile_square(cfg)
    # Blur needs ~4 sigma of real data beyond the square, otherwise the edges are biased.
    need = 4 * cfg.blur_sigma_mm / cfg.mm_per_m + 2 * grid.res
    x1 = grid.x0 + z.shape[1] * grid.res
    y0 = grid.y_top - z.shape[0] * grid.res
    if sx - grid.x0 < need or sy - y0 < need or x1 - (sx + cfg.size_m) < need or grid.y_top - (sy + cfg.size_m) < need:
        raise ValueError(f"DEM does not cover the map square plus {need:.0f} m margin; re-run fetch --force")
    return grid
