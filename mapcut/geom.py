"""Small shapely helpers shared by the geometry modules."""

from __future__ import annotations

import shapely
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry

AREA_EPS = 1e-6  # mm²; anything smaller is numerical debris from boolean ops


def polygons(g: BaseGeometry) -> list[Polygon]:
    """Polygonal parts of any geometry; set operations can return lines/points we must ignore."""
    if g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g] if g.area > AREA_EPS else []
    if hasattr(g, "geoms"):
        return [p for part in g.geoms for p in polygons(part)]
    return []


def lines(g: BaseGeometry) -> list[LineString]:
    """Linear parts of any geometry."""
    if g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    if hasattr(g, "geoms"):
        return [ln for part in g.geoms for ln in lines(part)]
    return []


def points(g: BaseGeometry) -> list[Point]:
    """Point parts of any geometry; a collinear overlap contributes its endpoints."""
    if g.is_empty:
        return []
    if isinstance(g, Point):
        return [g]
    if isinstance(g, LineString):
        return [Point(g.coords[0]), Point(g.coords[-1])]
    if hasattr(g, "geoms"):
        return [p for part in g.geoms for p in points(part)]
    return []


def polygonal(g: BaseGeometry) -> MultiPolygon:
    return MultiPolygon(polygons(shapely.make_valid(g)))


def rings(g: BaseGeometry):
    for p in polygons(g):
        yield p.exterior
        yield from p.interiors
