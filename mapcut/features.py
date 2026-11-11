"""Roads and buildings from the NLS topographic database, engraved on the visible faces of pieces."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyogrio.raw
import shapely
from shapely.geometry import LineString, Polygon

from .config import Config
from .geom import lines, polygons
from .levels import Levels
from .parts import Piece

# SERVICE_GUIDE: NLS topographic database (maastotietokanta), country-wide GeoPackages on the CSC
# Paituli mirror, CC BY 4.0. GDAL range-reads only the bbox via the GPKG spatial index. The file
# names carry the release date; update them when a new yearly release appears.
MTK_BASE = "/vsicurl/https://www.nic.funet.fi/index/geodata/mml/maastotietokanta/2025/gpkg/"
SOURCES = {
    "buildings": ("MTK-rakennus_25-04-03.gpkg", "rakennus", ["kerrosluku"]),
    "roads": ("MTK-tie_25-04-03.gpkg", "tieviiva", ["kohdeluokka", "tasosijainti"]),
}
FETCH_MARGIN_M = 10.0
MIN_ROAD_MM = 0.3  # shorter clipped road fragments are engraving noise


@dataclass(frozen=True)
class Features:
    buildings: list[Polygon]  # model mm
    roads: list[LineString]  # model mm, already filtered by class and level


def fetch(cfg: Config, sx: float, sy: float, force: bool = False) -> list[str]:
    """MANUAL: `mapcut fetch` also caches buildings/roads for the tile when [features] paths are set."""
    done = []
    m = FETCH_MARGIN_M
    bbox = (sx - m, sy - m, sx + cfg.size_m + m, sy + cfg.size_m + m)
    for kind, (fname, layer, cols) in SOURCES.items():
        path = getattr(cfg, kind)
        if path is None or (path.exists() and not force):
            continue
        meta, _, geom, data = pyogrio.raw.read(MTK_BASE + fname, layer=layer, columns=cols, bbox=bbox, force_2d=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        pyogrio.raw.write(
            path, geom, data, meta["fields"], layer=kind, driver="GPKG",
            geometry_type=meta["geometry_type"].replace(" Z", ""), crs=meta["crs"],
        )
        done.append(f"{kind}: {len(geom)}")
    return done


def load(cfg: Config, sx: float, sy: float) -> Features | None:
    if cfg.buildings is None and cfg.roads is None:
        return None
    f = cfg.mm_per_m
    to_mm = lambda c: (c - np.array([sx, sy])) * f  # noqa: E731

    def read(kind):
        path = getattr(cfg, kind)
        if path is None:
            return [], {}
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; run `mapcut fetch`")
        meta, _, geom, data = pyogrio.raw.read(path)
        return shapely.transform(shapely.from_wkb(geom), to_mm), dict(zip(meta["fields"], data))

    bgeom, _ = read("buildings")
    rgeom, rattr = read("roads")
    roads = []
    if len(rgeom):
        # Class filter keeps main roads and streets; negative level = tunnel, not visible on terrain.
        keep = np.isin(rattr["kohdeluokka"], cfg.road_classes) & (rattr["tasosijainti"] >= 0)
        roads = [ln for g in rgeom[keep] for ln in lines(g)]
    return Features(buildings=[p for g in bgeom for p in polygons(g)], roads=roads)


def engrave_on(pieces: list[Piece], lv: Levels, feats: Features, cfg: Config) -> None:
    """Clip features to each piece's visible face: what layer i+1 covers is never seen."""
    btree = shapely.STRtree(feats.buildings)
    rtree = shapely.STRtree(feats.roads)
    n = len(lv)
    for pc in pieces:
        if not pc.ok:
            continue
        visible = pc.geom.difference(lv.polys[pc.layer + 1]) if pc.layer + 1 < n else pc.geom
        # Stay off the cut edge: an engraved line in the kerf zone burns the edge.
        visible = visible.buffer(-cfg.feature_clearance_mm)
        if visible.is_empty:
            continue
        for idx in btree.query(visible, predicate="intersects"):
            pc.buildings += [p for p in polygons(feats.buildings[idx].intersection(visible)) if p.area >= cfg.min_building_mm2]
        for idx in rtree.query(visible, predicate="intersects"):
            pc.roads += [ln for ln in lines(feats.roads[idx].intersection(visible)) if ln.length >= MIN_ROAD_MM]
