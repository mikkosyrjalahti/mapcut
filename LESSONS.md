# Lessons learned: PoC v0.1

Written so the next version builds on what was learned instead of starting over. Covers the design
review of the original spec, development of the PoC, and the first session at the laser cutter.
Facts that are still unmeasured are marked **TODO**; fill them in after the first full build.

## 1. Decisions to keep, and why

| Decision | Why it held up |
|---|---|
| **In-place shell with k blanks:** layer `Q_i = P_i \ P_{i+k}`, cut on blank `i mod k` at its true map position | Material = k map-sized blanks however many layers there are. Each contour is cut once. The pieces on a blank cover the map with no overlaps, so no nesting algorithm is needed. Glue overlap = k−1 elevation bands, with no parameter |
| **k = 3** rather than 2 | With k=2 the area hidden under the next layer is one band (~2 mm on slopes); after clearances fewer than half the pieces could carry a label (synthetic test). k=3 gives a 4.5 mm shell and room for labels |
| **Frameless, with stepped side panels** | Panels close the hollow edges, act as an absolute fence, and their top edge shows the terrain cross-section. Corner heights of adjacent panels agree by construction |
| **Enforce invariants by construction, not by validation** | Blur the elevation data *before* contouring (smoothing per polygon breaks nesting). Opening/closing is monotone, so nesting survives. Simplification is not, so `P_i ∩ P_{i-1}` is re-imposed afterwards. Tests check the invariants but should never be the only defence |
| **One geo → millimetre conversion point** | `dem.py` is the only module with geographic coordinates; `levels.py` converts to model mm once. Everything downstream is mm with (0,0) at the SW map corner |
| **Engrave the layer number only** | The cut blank is a map-shaped tray: position + guide identify a piece. The number only has to stop wrong-level placement. 2 digits fit where `LL-PP` did not. Full ids stay in the manifest |
| **Single-stroke font** | Line engraving needs one stroke per glyph line. TTF outlines engrave double; DXF TEXT/MTEXT import is unreliable in CAM tools |
| **Colour is the LightBurn contract** | LightBurn maps DXF colour → layer. Named DXF layers are kept for humans only. Explicit entity colours, not BYLAYER |
| **Engrave roads/buildings only on visible faces** | Hidden faces would waste time; clipping keeps engraving 0.2 mm off cut edges |
| **Property tests over golden files** | Nesting, per-blank disjointness, ply count = `min(k, top+1)`, labels/guides/features on the right face, tab gaps uncut. These survive parameter changes; golden files would not |
| **Unknown config keys are errors** | A typo silently falling back to a default wastes plywood |

## 2. Rejected from the original spec, and why

Do not re-add these without new evidence:
- **Frames + pin registration:** incompatible with frameless in-place blanks and with the 2–3-blank budget.
- **Temporary bridges between islands and the frame:** a bridge at layer i floats over terrain that doesn't exist at layer i−1, which violates `P_{i+1} ⊆ P_i`. It also can't be cut off cleanly after gluing.
- **Irregular nesting (Deepnest etc.):** in-place layout makes it unnecessary.
- **Packets, stage caching, Docker, HTML/PDF guide, SVG, PyQGIS/PostGIS options:** no real need for these at this scale. The whole build takes ~3 s.
- **3D buildings (DSM or extruded footprints):** a DSM turns walls into slivers spanning 8+ contours. Footprints here are a median 5 mm² (≈2×2.5 mm) and 505/554 are one storey: unassemblable. Revisit only for city centres with large tall blocks, as separate parts with their own vertical scale.
- **Fixed overlap width for gluing:** in-place blanks are paid for anyway, so removing material saves nothing. Natural bands give maximal support.

## 3. Data

- **Source:** CSC Paituli mirror of NLS open data, CC BY 4.0, **no API key**. NLS's own WCS/OGC endpoints return 401 without a key.
- **Elevation:** 2 m DEM as one Finland-wide VRT; EPSG:3067; nodata −9999; float32. GDAL `/vsicurl/` reads only the window.
- **Roads and buildings:** Topographic Database (maastotietokanta) as country-wide GeoPackages (4–5 GB each). A bbox read through the GPKG spatial index takes 2–10 s per km².
  - File names carry the release date (`*_25-04-03.gpkg`), so update `features.SOURCES` per release.
  - `tieviiva.kohdeluokka` codes: 1211x/1212x main roads, 1213x streets, 12141 driveways, 123xx paths.
  - `tieviiva.tasosijainti`: below 0 is a tunnel, above 0 a bridge.
  - `rakennus.kerrosluku` is the number of storeys.
- **The original "Helsinki" assumption:** relief is small (a central 1 km² spans roughly 0–40 m), so 2.5 m layers give ~15 levels, not 100+. That reality killed most of the scaling machinery in the original spec.
- **The PoC tile** (Espoo, 60.2137 N 24.7682 E) is inland: a hill of 10–45 m with highway embankments. **Coastal tiles are untested**: sea areas may be nodata (`fetch` refuses) or noisy near 0 m. A shoreline from the Topographic Database will likely be needed.

## 4. Surprises during development

1. **"No room for ID" was mostly a classification error.** 28 of 55 pieces are local summits (knolls, embankment crests) with nothing above them. Their whole face is visible, so having no ID is correct. Lesson: check *what* fails before tuning *how much*.
2. **Embankments make awkward pieces:** long, thin local tops with necks. Expect them on any tile with major roads.
3. **Small debris:** 11 kept pieces under 10 mm². Likely to be lost; `min_area_mm2` probably needs to rise to 10–15.
4. **Panels can be matchstick-thin:** the S panel is only 1.5 mm tall along ~70 mm where the terrain at the edge is the lowest level.
5. **Buildings split at steps:** 576 buildings became 603 outlines.
6. **Tooling:** Homebrew Python is 3.15 with no geospatial wheels, so use `uv` + Python 3.12. No system GDAL is needed; the wheels bundle it.
7. **Test tolerances:** a tab gap is a polygonised circle, ~5 nm short of its nominal radius. Compare with µm tolerances, not 1e-6.

## 5. Physical findings

Observed at the laser cutter:
- **Engraved roads help alignment.** A road continuing straight across a step shows registration directly, independent of DEM accuracy (both layers are engraved from the same coordinates). Limits: it only constrains error *across* the road direction; the 0.2 mm clearance leaves a ~0.4 mm break at each step; the unbuilt steep slopes have no roads.
- **Small pieces drop through the bed** → added tabs (0.5 mm gaps at 0/120/240° from the pole of inaccessibility, pieces ≤ 200 mm²).

**TODO: record after the first full build** (each sets a config default):

| Question | Result | Config key |
|---|---|---|
| Actual sheet thickness | | `thickness_mm` |
| Kerf width | | (tab width, gaps) |
| Narrowest strip that survives cutting + handling | | `min_width_mm` |
| Smallest piece worth keeping | | `min_area_mm2` |
| Smallest legible engraved number | | `id_min_height_mm` |
| Guide inset that stays hidden | | `guide_inset_mm` |
| Tab strength (holds in cutting? breaks cleanly?) | | `tab_width_mm` |
| Building Line vs Fill: look, fill time | | (LightBurn) |
| Does LightBurn keep the innermost-first cut order? | | |
| Alignment drift at the top layer (mm) | | |
| Glue and warp behaviour, flex of wide flat areas | | |
| Total assembly time, pieces lost | | |

## 6. Backlog for v2 (roughly by priority)

1. **Fill in §5 TODOs and update the defaults.**
2. **Alignment ticks:** short engraved marks across steps where no road crosses within a few cm, on their own colour so they can be disabled.
3. **Coastal tiles:** shoreline clip for the sea, nodata handling.
4. **Smarter tab placement:** avoid sharp vertices and thin necks; tab `thin_neck` pieces regardless of area.
5. **Production layout:** place panels and several maps per 800×600 blank automatically; tiling for maps larger than a blank.
6. **Panel robustness:** minimum panel height or a base lip where the edge terrain is at level 0.
7. **Support pillars** under wide flat areas, if the physical build shows flex.
8. **Determinism check:** same inputs → byte-identical DXF (ids are already order-stable).
9. **3D buildings for dense city centres:** separate parts, own vertical scale (see §2 for why not here).

## 7. How to start v2

- Don't rewrite: the pipeline modules map 1:1 to the concepts in §1. Extend them; see README → Development.
- Run `uv run pytest -q` first; keep every invariant test green. Add a test for each new invariant (e.g. "alignment ticks lie on visible faces").
- New config keys go into `Config` with a default so old TOML files keep working.
- Re-read §2 before adding back anything the original spec had.
