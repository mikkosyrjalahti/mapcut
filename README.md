# mapcut

Laser-cut, stacked-plywood topographic maps from Finnish open data (National Land Survey 2 m
elevation model, roads and buildings). Status: **proof of concept**. One map has been cut so far;
expect the defaults to change as physical builds teach us more. Design rationale: [SPEC.md](SPEC.md).

## How the model works

Terrain is sliced at a fixed elevation interval (e.g. 2.5 m). Instead of cutting every layer as a
full solid sheet, layer `i` is only the terrain between level `i` and level `i+k`:

```
L4          ████████████              blank B1: L1, L4      (k = 3)
L3        ████████████████            blank B0: L0, L3
L2      ████████████████████          blank B2: L2
L1    ██████            ██████
L0  ██████                ██████
    every point is covered by up to k plies (fewer only at the lowest levels); hollow beneath
```

- Layers are distributed over **k blanks** (`i mod k`) and every piece is cut **at its true map
  position**. One blank is the map divided along every k-th contour. Material cost is k map-sized
  blanks regardless of how many layers the terrain has; each contour is cut exactly once.
- Each layer rests on the one below over `k−1` elevation bands. That overlap is the glue surface.
- No frame and no pins. Alignment comes from an engraved guide line hidden under each next layer,
  continuous roads across steps, and four **stepped side panels** that close the hollow edges.

## Install

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 is pinned in `.python-version`; uv fetches
it if missing. Homebrew's newer Python lacks wheels for the geospatial stack, so always go via `uv`.

```sh
uv sync
uv run pytest -q          # property tests, ~1 s
```

No system GDAL is needed; rasterio and pyogrio ship their own.

## Quick start

```sh
cp configs/espoo_poc.toml configs/my_map.toml     # edit name, centre, paths
uv run mapcut fetch configs/my_map.toml           # download DEM + roads/buildings for the tile
uv run mapcut build configs/my_map.toml           # write cut files to output_dir
```

`fetch` caches into `data/` and skips files that exist (`--force` re-downloads). `build` takes a few
seconds and prints a report (also saved as `report.txt`).

Pick the tile centre from any map (e.g. Karttapaikka, Google Maps) as latitude/longitude. The map
square is laid out in EPSG:3067 and snapped to the 2 m grid.

## Configuration

One TOML file per map. Unknown sections or keys are an error, so typos can't silently fall back to
defaults. Paths are relative to the config file.

| Section | Key | Default | Meaning |
|---|---|---|---|
| project | `name`, `output_dir` | – | Output folder for this map |
| input | `dem` | – | Cached DEM GeoTIFF (written by `fetch`) |
| | `center_lat`, `center_lon` | – | Tile centre, WGS84 |
| | `size_m` | 1000 | Side of the square tile, metres |
| terrain | `interval_m` | 2.5 | Elevation per layer |
| | `base_m` | auto | Lowest level; default is the lowest terrain floored to the interval |
| | `blur_sigma_mm` | 0.5 | DEM smoothing before contouring (model mm) |
| | `smooth_radius_mm` | 0.3 | Removes specks/notches smaller than ~2× this |
| | `simplify_mm` | 0.05 | Contour simplification tolerance |
| model | `scale` | 5000 | 1:scale |
| | `thickness_mm` | 1.5 | **Measured** sheet thickness; sets stack and panel heights |
| | `k` | 3 | Number of blanks = plies; 3 recommended (k=2 leaves too little hidden area for IDs) |
| fabrication | `min_width_mm` | 1.0 | Pieces thinner than this everywhere are dropped |
| | `min_area_mm2` | 4.0 | Pieces smaller than this are dropped |
| | `guide_inset_mm` | 0.4 | Guide line distance inside the next layer's edge (keeps it hidden) |
| | `id_height_mm`, `id_min_height_mm` | 2.0, 1.2 | Layer-number text height range |
| | `blank_width_mm`, `blank_height_mm`, `blank_margin_mm` | 800, 600, 10 | Blank size; map + margins must fit |
| | `tab_width_mm` | 0.5 | Uncut gap per tab (real bridge ≈ one kerf narrower) |
| | `tab_angles_deg` | [0, 120, 240] | Tab directions from the piece centre (0 = east, CCW) |
| | `tab_max_area_mm2` | 200 | Only pieces up to this area get tabs |
| features | `buildings`, `roads` | unset | Cache paths; omit a key to disable that feature |
| | `road_classes` | main roads + streets | NLS `kohdeluokka` codes to engrave (driveways 12141 and paths 123xx excluded by default) |
| | `min_building_mm2` | 1.0 | Smaller building fragments are skipped |
| | `feature_clearance_mm` | 0.2 | Keep engraving this far from cut edges |

Vertical exaggeration is `thickness × scale / (1000 × interval)`; it is printed in the report
(1.5 mm, 1:5000, 2.5 m → 3×).

## Output

| File | Content |
|---|---|
| `blank_0.dxf` … `blank_{k-1}.dxf` | One per blank: map at (margin, margin), blank number `B<j>` in the bottom margin |
| `panels.dxf` | Four side panels S, N, W, E. N and S are 2 × thickness longer to cover the corners |
| `calibration.dxf` | 100 mm test coupon; cut this first |
| `manifest.csv` | One row per piece: id `LL-PP`, layer, blank, area, position, tabs, notes |
| `report.txt` | Summary: levels, exaggeration, piece counts, dropped area, warnings |
| `preview.png` | Assembled top view + each blank; `panels.png` panel profiles |

Manifest notes: `top_piece_no_id` (local summit, whole face visible, so no engraving by design),
`no_room_for_id`, `id_small_*`, `thin_neck` (may snap; handle carefully). Dropped pieces have ids
`LL-xNN` and are waste.

## LightBurn setup

DXF units are millimetres. Operations are identified by **colour**:

| Colour | DXF layer | Suggested operation |
|---|---|---|
| Blue | `ENGRAVE_GUIDE` | Line, low power (hidden under the next layer) |
| Green | `ENGRAVE_ID` | Line |
| Magenta | `ENGRAVE_BUILDING` | Line or Fill (closed outlines). Optional |
| Cyan | `ENGRAVE_ROAD` | Line. Optional, but useful for alignment |
| Red | `CUT` | Cut, after all engraves |
| Yellow | `CUT_PERIMETER` | Cut, **very last** (map square edge) |

- Order the layers: engraves, then red, then yellow. Pieces cut free may shift slightly.
- The perimeter has its own layer because it frees the whole map from the blank's rim. Cut before
  the inner contours, the map can warp and go out of focus. LightBurn cannot keep it last within
  one layer: contours that reach the map edge are open paths, so "cut inner shapes first" does not
  treat them as inside the square.
- The inner cut paths are written innermost (highest) contour first. Check in the preview that
  LightBurn's optimisation keeps that order.
- If you fill buildings, use LightBurn's option to fill shapes individually. Otherwise it may scan
  the full width between scattered buildings.

## Fabrication workflow

1. **Measure** the plywood thickness and set `thickness_mm`; rebuild.
2. **Cut `calibration.dxf`** and check:
   - the outer square measures 100.0 mm (units/scale);
   - which width strips (labelled in tenths of a mm) survive → `min_width_mm`;
   - text legibility per height → `id_min_height_mm`;
   - which guide inset (0.2/0.4/0.6) stays hidden next to a cut edge → `guide_inset_mm`;
   - Line vs Fill on the building samples, and fill time;
   - whether the nested squares stay in place on the bed.
3. **Cut the blanks and panels.** Leave pieces in the sheet; the blank is a map-shaped parts tray.
   Small pieces are held by tabs; cut them free only when placing.
4. **Assemble** (suggested; refine after builds):
   - Dry-fit the four panels around the layer-0 piece. The engraved letters face inward; the stepped
     top edge must match the terrain at each edge. Glue the panel corners.
   - Stack upward, layer 1, 2, …, taking pieces from their blanks (`B<i mod k>`). Each piece's outer
     edge sits just outside the blue guide on the layer below. Edge pieces butt against the panels.
     Engraved roads should run straight across each step; a jog means misalignment.
   - Engraved numbers are the **layer** number. A piece without a number is a local summit; its
     position in the blank and the guide below identify it.
   - Glue sparingly (thin PVA); press with weights rather than clamps. Wide flat areas are only 3 plies
     thick over a hollow.
5. Break tab nubs off and sand the visible edges lightly.

## Data and licence

All data are from the National Land Survey of Finland (NLS/MML), **CC BY 4.0**, fetched without an
API key from the CSC Paituli mirror:

- elevation: 2 m DEM, single Finland-wide VRT (`mapcut/dem.py`);
- roads and buildings: Topographic Database GeoPackages, `MTK-tie` / `MTK-rakennus`
  (`mapcut/features.py`). File names carry the release date; update `SOURCES` when a new yearly
  release appears.

GDAL reads only the tile's area over HTTP (seconds per tile; the source files are several GB).
Finished models must carry the attribution printed in `report.txt`:
*Contains data from the National Land Survey of Finland Elevation model 2 m and Topographic
Database (CC BY 4.0)*.

## Limitations

- Areas outside DEM coverage (sea beyond the coastline, outside Finland) fail at `fetch`.
- One tile per blank; maps larger than a blank need tiling (not implemented).
- Very steep faces (more than k layers within ~1 mm) get thin backing; true cliffs show a one-layer
  dip where slivers are dropped.
- Buildings and roads are engraved, not built up in 3D.
- Tab nubs land on visible edges; there is no hidden place for them.

## Development

```
mapcut/
  config.py    TOML -> frozen Config (unknown keys rejected)
  dem.py       DEM fetch/load (the only module with geographic coordinates)
  levels.py    blur -> filled contours -> nested level polygons P_i (model mm)
  parts.py     pieces Q_i = P_i \ P_{i+k}, drop filter, guides, layer labels, tabs
  features.py  roads/buildings fetch, clipped to visible faces
  panels.py    stepped side panel profiles
  export.py    DXF writers (blanks, panels, calibration), cut_lines() with tab gaps
  font.py      single-stroke engraving font
  report.py, preview.py, cli.py
tests/test_geometry.py   property tests on synthetic terrain
```

The tests check the invariants the physical build depends on: levels are nested, pieces on a blank
never overlap, every point is covered by `min(k, top+1)` plies, labels/guides/features stay on their
piece's correct face, and tab gaps are really uncut.
