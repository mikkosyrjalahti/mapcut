# mapcut — PoC spec

Supersedes `helsinki_laser_cut_topographic_map_agentic_spec.md` for the proof of concept.
Goal of the PoC: one physical end-to-end build to find out what the physical process gets wrong.
This version does not try to be a product yet.

## Fabrication model: k-ply in-place shell

- Levels `z_i = base + i·Δh`; `P_i = {h ≥ z_i}`, nested: `P_{i+1} ⊆ P_i`.
- Layer piece set `Q_i = P_i \ P_{i+k}`. Blank `j` holds every layer with `i mod k = j`,
  each cut **at its true map position**. The pieces on one blank partition the map, so:
  - material = k map-sized blanks, independent of layer count;
  - each contour is cut exactly once (the outer edge of `Q_i` is also the inner edge of `Q_{i-k}`);
  - every point of the model is covered by `min(k, top+1)` plies; hollow beneath.
- Layer `i+1` rests on layer `i` over `k−1` elevation bands (glue overlap).
- No frame, no pins. Alignment: engraved guide (contour `i+1`, inset so it's hidden) on each piece,
  plus four **stepped side panels** whose top edge follows the terrain profile; they close the hollow
  and act as an absolute fence.
- Pieces narrower than `min_width` or smaller than `min_area` are dropped (waste); the layer below
  shows through (a one-layer dip). Reported in the manifest.
- IDs `LL-PP` (layer-piece) engraved upright (north up) in the area hidden under the next layer.
  Pieces with no layer above get no ID (flagged).

## PoC parameters

- Tile: 1×1 km centred at 60.213737 N, 24.768206 E (Espoo), EPSG:3067.
- Data: NLS 2 m DEM via the Paituli mirror VRT (CC BY 4.0, National Land Survey of Finland).
- 1:5000 → 200×200 mm; Δh 2.5 m; 1.5 mm birch ply; k = 3 (3 blanks + side panels).
- Software: LightBurn (DXF; colour = operation, layer names for humans).

## Pipeline

`fetch` (window from VRT) → `build`: blur (σ in model mm) → filled contours (contourpy, sub-pixel)
→ morphological open/close (monotone, keeps nesting) → simplify → clip → re-enforce nesting
→ `Q_i` → filter → IDs, guides → per-blank DXF + panels DXF + calibration DXF + manifest + previews.

## Out of scope for the PoC

3D buildings (most buildings here are 1–2 storeys and ~2×2.5 mm at 1:5000, too small to assemble;
they are engraved instead), support pillars, nesting, caching, packets, HTML guide, SVG, Docker.

Added after the first physical tests: building outlines and road centrelines engraved on visible
faces (roads also turned out to help alignment), and tabs on small pieces (they fell through the bed).

## What the PoC build must measure

1. Alignment drift over 15 layers using only guides + panels.
2. Which min_width survives cutting and handling (calibration strips).
3. ID legibility at 1.2–2 mm (stroke font).
4. Glue / warp behaviour of 3-ply 1.5 mm shell; stiffness of wide flat areas.
5. Whether in-place pieces stay put on the honeycomb bed during the job.
6. Actual assembly time and piece count.
