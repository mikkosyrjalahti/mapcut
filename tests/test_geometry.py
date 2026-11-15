"""Property tests on synthetic terrain: the invariants the physical build depends on."""

from pathlib import Path

import numpy as np
import pytest
import shapely
from shapely.geometry import Point

from mapcut import font
from mapcut.config import Config
from mapcut.dem import Grid
from mapcut.levels import build_levels
from mapcut.panels import build_panels
from mapcut.parts import build_pieces

RES = 2.0
SIZE_M = 500.0
MARGIN_M = 50.0


def _cfg(**kw) -> Config:
    base = dict(name="t", output_dir=Path("."), dem=Path("x"), center_lat=0, center_lon=0, size_m=SIZE_M, k=3)
    return Config(**(base | kw))


def _grid(fn) -> Grid:
    n = int((SIZE_M + 2 * MARGIN_M) / RES)
    c = (np.arange(n) + 0.5) * RES - MARGIN_M  # metres relative to the square's west/south edge
    x, y = np.meshgrid(c, c[::-1])  # rows north -> south
    return Grid(z=fn(x, y), x0=-MARGIN_M, y_top=SIZE_M + MARGIN_M, res=RES)


def _two_hills(x, y):
    h1 = 30 * np.exp(-((x - 180) ** 2 + (y - 250) ** 2) / (2 * 70**2))
    h2 = 20 * np.exp(-((x - 360) ** 2 + (y - 200) ** 2) / (2 * 40**2))
    return 5 + h1 + h2 + 0.01 * x  # slight tilt so terrain crosses the map edge


@pytest.fixture(scope="module", params=[2, 3])
def built(request):
    cfg = _cfg(k=request.param)
    lv = build_levels(_grid(_two_hills), 0.0, 0.0, cfg)
    return cfg, lv, build_pieces(lv, cfg)


def test_scale_and_exaggeration():
    cfg = _cfg(size_m=1000, scale=5000, thickness_mm=1.5, interval_m=2.5)
    assert cfg.map_mm == pytest.approx(200)
    assert cfg.vertical_exaggeration == pytest.approx(3)


def test_levels_are_nested(built):
    _, lv, _ = built
    assert len(lv) > 8
    for a, b in zip(lv.polys, lv.polys[1:]):
        assert b.difference(a).area < 1e-6


def test_pieces_on_a_blank_never_overlap(built):
    cfg, _, pieces = built
    for j in range(cfg.k):
        on = [p.geom for p in pieces if p.blank == j]
        for n, a in enumerate(on):
            for b in on[n + 1 :]:
                assert a.intersection(b).area < 1e-6


def test_every_point_has_min_k_plies(built):
    """The shell invariant: a point under level `top` is covered by min(k, top+1) kept pieces."""
    cfg, lv, pieces = built
    kept = [p.geom for p in pieces if p.ok]
    dropped = [p.geom for p in pieces if not p.ok]
    rng = np.random.default_rng(1)
    checked = 0
    for x, y in rng.uniform(0, cfg.map_mm, size=(300, 2)):
        pt = Point(x, y)
        if any(d.distance(pt) < 0.01 for d in dropped) or any(p.boundary.distance(pt) < 0.01 for p in lv.polys):
            continue
        top = max(i for i, p in enumerate(lv.polys) if p.contains(pt))
        assert sum(g.contains(pt) for g in kept) == min(cfg.k, top + 1)
        checked += 1
    assert checked > 200


def test_labels_and_guides_stay_on_their_piece(built):
    _, _, pieces = built
    for pc in pieces:
        if pc.label:
            from shapely.geometry import MultiLineString

            assert MultiLineString(pc.label.strokes()).within(pc.geom)
        for ln in pc.guide:
            assert ln.within(pc.geom.buffer(1e-6))


def test_ids_unique_and_most_pieces_labelled(built):
    cfg, _, pieces = built
    ids = [p.id for p in pieces]
    assert len(ids) == len(set(ids))
    with_room = [p for p in pieces if p.ok and "top_piece_no_id" not in p.notes]
    labelled = sum(p.label is not None for p in with_room)
    if cfg.k == 2:
        # Known limitation: with k=2 the hidden area is one band (~2 mm here), too narrow for text
        # once guide and cut clearances are taken. Only assert that it degrades, not fails outright.
        assert labelled >= 0.4 * len(with_room)
    else:
        assert labelled >= 0.9 * len(with_room)


def test_panel_heights_match_edge_terrain(built):
    cfg, lv, _ = built
    pans = build_panels(lv, cfg)
    assert all(p.outline.is_valid for p in pans)
    # The tallest panel step equals the highest level touching any map edge.
    top = max(i for i, p in enumerate(lv.polys) if p.intersection(lv.square.exterior).length > 0.5)
    assert max(p.outline.bounds[3] for p in pans) == pytest.approx((top + 1) * cfg.thickness_mm)
    for p in pans:
        assert p.outline.bounds[2] == pytest.approx(cfg.map_mm + (2 * cfg.thickness_mm if p.name in "NS" else 0))


def test_font_width():
    assert font.width("07-03", 2.0) == pytest.approx((5 * 5.5 - 1.5) * 2 / 6)


def test_features_only_on_visible_faces(built):
    from shapely.geometry import LineString, box

    from mapcut.features import Features, engrave_on

    cfg, lv, pieces = built
    side = cfg.map_mm
    # A grid of "buildings" and a diagonal "road" spanning every level.
    blds = [box(x, y, x + 2, y + 2.5) for x in range(2, int(side) - 4, 6) for y in range(2, int(side) - 4, 6)]
    feats = Features(buildings=blds, roads=[LineString([(0, 0), (side, side)]), LineString([(0, side), (side, 0)])])
    engrave_on(pieces, lv, feats, cfg)
    n_b = n_r = 0
    for pc in pieces:
        above = lv.polys[pc.layer + 1] if pc.layer + 1 < len(lv) else None
        for b in pc.buildings:
            assert b.within(pc.geom) and b.area >= cfg.min_building_mm2
            assert above is None or b.intersection(above).area < 1e-6
            n_b += 1
        for ln in pc.roads:
            assert ln.within(pc.geom.buffer(1e-6))
            assert above is None or ln.intersection(above).length < 1e-6
            n_r += 1
    assert n_b > 50 and n_r > 5


def test_tabs_on_outline_and_left_uncut(built):
    from mapcut.export import cut_lines

    cfg, lv, pieces = built
    small = [p for p in pieces if p.ok and p.geom.area <= cfg.tab_max_area_mm2]
    assert small, "fixture should contain small pieces"
    for pc in pieces:
        if pc in small:
            assert 1 <= len(pc.tabs) <= len(cfg.tab_angles_deg)
            assert all(pc.geom.exterior.distance(t) < 1e-6 for t in pc.tabs)
        else:
            assert pc.tabs == []
    for j in range(cfg.k):
        tabs = [t for p in pieces if p.blank == j for t in p.tabs]
        inner, perimeter = cut_lines(lv, j, tabs, cfg)
        cuts = shapely.union_all([*inner, *perimeter])
        for t in tabs:
            # The uncut gap is the full tab width: nothing within half of it is cut.
            assert cuts.distance(t) >= cfg.tab_width_mm / 2 - 1e-3  # gap is a polygonised circle


def test_perimeter_cut_separate_from_inner(built):
    from mapcut.export import cut_lines

    cfg, lv, _ = built
    edge = lv.square.exterior
    for j in range(cfg.k):
        inner, perimeter = cut_lines(lv, j, [], cfg)
        # The whole map edge is on the perimeter layer and nothing else is.
        assert shapely.union_all(perimeter).equals(edge)
        # No inner path runs along the edge; at most its end points touch it.
        assert all(ln.intersection(edge.buffer(1e-3)).length < 1e-2 for ln in inner)


def test_tab_points_follow_angles():
    from shapely.geometry import box

    from mapcut.parts import tab_points

    pts = tab_points(box(0, 0, 10, 10), (0, 90, 180, 270))
    assert [(round(p.x, 3), round(p.y, 3)) for p in pts] == [(10, 5), (5, 10), (0, 5), (5, 0)]
