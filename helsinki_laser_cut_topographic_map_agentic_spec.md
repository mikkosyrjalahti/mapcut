# Laser-Cut Topographic Map Generator

## 1. Purpose

This document specifies a software workflow for generating layered, laser-cut topographic maps from Helsinki open elevation data.

The intended output is a set of cut-ready vector files and an assembly package for a terrain model made from stacked plywood sheets. The workflow must support:

- large numbers of elevation layers;
- configurable real-world contour intervals, such as 2.5 m;
- cumulative terrain polygons rather than contour-line-only geometry;
- odd/even or other layer grouping for material allocation;
- automatic part identification;
- registration holes and alignment features;
- retained carrier sheets and microtabs;
- placement engravings;
- disconnected terrain components and islands;
- an assembly manifest suitable for manual fabrication.

The document is written as an implementation brief for an autonomous or agentic coding system.

---

## 2. Core geometric model

For a terrain elevation raster \(h(x,y)\), layer \(i\) is the cumulative polygon:

\[
P_i = \{(x,y) \mid h(x,y) \ge z_i\}
\]

where:

\[
z_i = z_\text{base} + i\Delta h
\]

and:

- \(z_\text{base}\) is the lowest represented elevation;
- \(\Delta h\) is the elevation interval, for example 2.5 m;
- \(P_i\) contains all terrain at or above elevation \(z_i\).

Each physical plywood layer must be cut as a cumulative solid region. Annular elevation bands alone are not sufficient for a conventional stacked model.

### 2.1 Layer index

Use zero-based or one-based indexing consistently. A recommended zero-based definition is:

```text
layer_index = round((elevation - base_elevation) / elevation_interval)
```

For filenames and engravings, use fixed-width human-readable numbering:

```text
L000
L001
L002
...
L137
```

### 2.2 Sheet grouping

For alternating groups:

```text
sheet_group = layer_index % 2
```

This separates even and odd layers, but it does not guarantee that all parts fit on two physical plywood sheets. Actual sheet count must be determined by part area, margins, kerf, grain constraints, and nesting efficiency.

---

## 3. Recommended software stack

## 3.1 Required

### QGIS

Use QGIS for:

- loading Helsinki or National Land Survey elevation data;
- selecting and clipping the area of interest;
- coordinate reference system management;
- raster preprocessing;
- inspecting generated polygons;
- optional graphical-model prototyping;
- map preview and quality control.

Recommended capability:

- QGIS 3.x with Processing Toolbox;
- GDAL processing providers enabled;
- Python console and PyQGIS available.

### Python

Use Python for the repeatable production pipeline.

Recommended baseline:

```text
Python 3.11 or newer
```

The implementation should avoid depending on the QGIS GUI for batch generation.

### GDAL

Use GDAL for:

- raster reprojection;
- raster clipping;
- threshold raster generation;
- polygonization;
- raster metadata inspection.

Required command-line utilities or Python bindings:

```text
gdalinfo
gdalwarp
gdal_translate
gdal_polygonize.py
ogr2ogr
```

### GEOS-based geometry library

Use one of:

- Shapely;
- PyQGIS geometry APIs;
- PostGIS, if a database-backed implementation is preferred.

Shapely is recommended for a standalone Python pipeline.

### Vector export library

Support at least one laser-compatible format:

- DXF;
- SVG.

Recommended libraries:

```text
ezdxf
svgwrite
```

DXF is generally preferable for preserving metric dimensions through CAD and laser CAM software.

---

## 3.2 Recommended Python packages

A standalone implementation should use:

```text
numpy
rasterio
geopandas
shapely
pyproj
fiona
ezdxf
svgwrite
pandas
pydantic
click or typer
```

Optional packages:

```text
scipy
scikit-image
networkx
matplotlib
Pillow
```

Typical use:

- `numpy`: raster threshold operations;
- `rasterio`: raster reading, clipping, masking, and coordinate transforms;
- `geopandas`: vector storage and attribute processing;
- `shapely`: polygon cleanup, unions, buffers, holes, and placement geometry;
- `pyproj`: CRS validation and coordinate transformation;
- `ezdxf`: DXF generation;
- `svgwrite`: SVG generation;
- `pandas`: assembly manifest and reports;
- `pydantic`: configuration validation;
- `typer`: command-line interface;
- `scikit-image`: optional contour or morphology operations;
- `networkx`: optional graph-based temporary bridge generation.

---

## 3.3 Fabrication software

At least one laser CAM package is required:

- LightBurn;
- manufacturer-specific laser software;
- another application able to import DXF or SVG with exact dimensions.

For irregular sheet nesting, use one of:

- Deepnest;
- LightBurn nesting;
- another no-fit-polygon or irregular nesting package.

The generator should not depend on a specific nesting application. It should export individual parts and optional pre-arranged sheets.

---

## 3.4 Optional software

### Inkscape

Useful for:

- SVG inspection;
- manual cleanup;
- checking layers and engraving groups;
- adding legends or decorative elements.

### Blender or FreeCAD

Useful for:

- 3D visualisation;
- checking vertical exaggeration;
- previewing the assembled stack.

### Git

Required for source control and reproducible agentic development.

### Docker or Podman

Recommended for a standalone GDAL/Python pipeline to make geospatial dependencies reproducible.

---

## 4. Data requirements

## 4.1 Elevation raster

The input must be a georeferenced digital elevation model.

Suitable sources include:

- Helsinki city elevation-model services;
- National Land Survey of Finland elevation models;
- a local GeoTIFF exported from QGIS.

The implementation should accept:

```text
GeoTIFF
Cloud-Optimized GeoTIFF
WCS-derived GeoTIFF
VRT
```

### Required raster metadata

The application must validate:

- coordinate reference system;
- pixel size;
- nodata value;
- elevation units;
- horizontal units;
- raster bounds;
- minimum and maximum elevation.

### Recommended coordinate systems

Use a projected metric CRS.

Typical alternatives:

```text
EPSG:3879  ETRS-GK25FIN
EPSG:3067  ETRS-TM35FIN
```

Do not perform geometry fabrication in geographic latitude/longitude coordinates.

---

## 4.2 Area of interest

The area of interest must be provided as one of:

- polygon in a GeoPackage;
- GeoJSON;
- Shapefile;
- WKT polygon;
- bounding box in the raster CRS;
- QGIS-selected polygon exported to file.

The pipeline should optionally add a rectangular outer frame around the area of interest.

---

## 5. Configuration

Use a human-readable YAML or TOML configuration file.

Example:

```yaml
project:
  name: helsinki_centre
  output_directory: output/helsinki_centre

input:
  dem: data/helsinki_dem.tif
  area_of_interest: data/aoi.gpkg
  aoi_layer: map_boundary
  working_crs: EPSG:3879

terrain:
  base_elevation_m: 0.0
  top_elevation_m: auto
  elevation_interval_m: 2.5
  simplify_tolerance_ground_m: 1.0
  minimum_component_area_model_mm2: 8.0
  minimum_hole_area_model_mm2: 5.0
  smoothing_distance_ground_m: 0.0

model:
  scale_denominator: 5000
  material_thickness_mm: 1.5
  map_width_mm: 200
  map_height_mm: 200
  frame_margin_mm: 12
  preserve_sea_base: true

registration:
  enabled: true
  primary_hole_diameter_mm: 3.1
  secondary_slot_width_mm: 3.1
  secondary_slot_length_mm: 6.0
  clamp_hole_diameter_mm: 4.0
  asymmetric_layout: true

identification:
  engrave_layer_id: true
  engrave_component_id: true
  engrave_source_sheet_id: true
  add_north_arrow: true
  fixed_width_layer_digits: 3

placement_guides:
  engrave_next_layer_outline: true
  guide_mode: segmented
  segment_length_mm: 4.0
  segment_spacing_mm: 20.0

microtabs:
  enabled: true
  width_mm: 0.5
  count_per_component: 3
  retain_in_source_sheet: true

bridges:
  enabled: true
  maximum_component_area_for_bridge_mm2: 40.0
  bridge_width_mm: 0.8
  bridge_to: frame

grouping:
  mode: parity
  groups: 2

export:
  dxf: true
  svg: true
  geopackage: true
  manifest_csv: true
  assembly_html: true
  preview_png: true
```

---

## 6. Dimensional calculations

## 6.1 Horizontal scale

For scale denominator \(S\):

\[
d_\text{model,mm} = \frac{1000d_\text{ground,m}}{S}
\]

and:

\[
d_\text{ground,m} = \frac{Sd_\text{model,mm}}{1000}
\]

Example at 1:5000:

```text
1 m ground distance = 0.2 mm in the model
5 m ground distance = 1.0 mm in the model
```

## 6.2 Vertical exaggeration

For material thickness \(t\), horizontal scale denominator \(S\), and elevation interval \(\Delta h\):

\[
E_v = \frac{tS}{1000\Delta h}
\]

Example:

```text
material thickness = 1.5 mm
scale = 1:5000
elevation interval = 2.5 m
vertical exaggeration = 3
```

The application must report vertical exaggeration before generating parts.

---

## 7. Processing pipeline

## 7.1 Validate inputs

The application must:

1. open the DEM;
2. verify that the CRS is projected;
3. verify that horizontal coordinates use metres;
4. verify or request elevation units;
5. open and validate the area of interest;
6. reproject the area of interest to the working CRS if required;
7. calculate output model dimensions;
8. calculate elevation range and layer count;
9. report estimated part count and approximate total cut area.

Fail with a clear message if dimensional metadata is ambiguous.

---

## 7.2 Clip and preprocess the DEM

Processing steps:

1. reproject the DEM to the working CRS if necessary;
2. clip it to the area of interest plus a small processing margin;
3. preserve nodata outside valid terrain;
4. optionally resample;
5. optionally apply mild smoothing;
6. store the processed raster as a GeoTIFF.

Recommended resampling:

- bilinear for elevation reprojection;
- nearest-neighbour only for binary masks.

Avoid excessive smoothing because it can remove narrow ridges and coastal features.

---

## 7.3 Generate elevation thresholds

For every layer elevation \(z_i\), create a binary mask:

```text
mask_i = 1 where DEM >= z_i
mask_i = nodata elsewhere
```

Then polygonize the mask.

Each resulting layer must be a cumulative polygon, not a contour line or annular band.

Expected pseudocode:

```python
for layer_index, elevation in enumerate(levels):
    mask = dem >= elevation
    polygons = polygonize(mask)
    terrain = union(polygons_with_value_1)
    terrain = clean_geometry(terrain)
    save_layer(layer_index, elevation, terrain)
```

---

## 7.4 Geometry cleanup

For each layer:

1. fix invalid geometries;
2. dissolve adjacent polygons;
3. remove holes below the configured model-space area;
4. remove or merge components below the configured model-space area;
5. simplify the geometry;
6. optionally smooth selected sharp raster artefacts;
7. clip to the model boundary;
8. ensure the result is valid after each destructive operation.

All fabrication tolerances should be configured in model millimetres and converted to ground units internally.

### 7.4.1 Simplification

The code should support:

- topology-preserving simplification;
- configurable ground-space tolerance;
- optional model-space tolerance.

Do not simplify registration features or engraved text.

### 7.4.2 Small components

Each small disconnected component must be handled by a policy:

```text
retain
omit
merge_to_nearest
bridge_to_frame
bridge_to_main_component
place_on_sea_base
```

The selected action must be recorded in the manifest.

---

## 7.5 Scale into model coordinates

After terrain generation, transform map coordinates into a local model coordinate system measured in millimetres.

Recommended origin:

```text
lower-left corner of the outer frame = (0, 0)
```

The transform must preserve aspect ratio.

The implementation should separate:

- geospatial coordinates;
- model millimetres;
- sheet-layout coordinates.

Never mix these coordinate spaces implicitly.

---

## 8. Assembly-assistance geometry

## 8.1 Common frame

Generate a rectangular or custom frame around each layer.

The frame provides:

- consistent handling;
- registration features;
- space for identifiers;
- support for disconnected components;
- optional permanent model border.

The application must support:

```text
permanent frame
sacrificial frame
no frame
```

For high layer counts, a sacrificial or permanent frame is strongly recommended.

---

## 8.2 Registration system

Use a kinematic-style registration system:

- one circular primary datum hole;
- one elongated secondary slot;
- optionally one oversized clamping hole.

The primary hole fixes translation. The slot fixes rotation without overconstraining the stack.

Requirements:

- holes must be in identical positions on all layers;
- placement must be asymmetric;
- features must not intersect terrain geometry;
- model orientation must be impossible to reverse accidentally;
- registration geometry must be exported as cut geometry.

Kerf compensation should be handled either:

- in the generator;
- or in laser CAM, but not both.

---

## 8.3 Orientation cues

Generate at least two orientation cues:

- asymmetric registration;
- clipped frame corner;
- engraved north arrow;
- layer identifier in a fixed corner.

The generator should make flipping or rotating a layer visually obvious.

---

## 8.4 Layer and component IDs

Each layer receives an ID:

```text
L042
```

Each disconnected component receives an ID:

```text
L042-P01
L042-P02
L042-P03
```

Optional full identifier:

```text
HEL-CENTRE-L042-P03-G1-S04
```

where:

- `HEL-CENTRE` is the project;
- `L042` is the layer;
- `P03` is the component;
- `G1` is the parity/material group;
- `S04` is the source sheet.

Identifiers must be:

- unique;
- fixed-width where practical;
- included in the manifest;
- engraved on the component where possible;
- engraved beside the retained component position in the source sheet.

For visible surfaces, place the component engraving in an area covered by the next layer or on a removable tab.

---

## 8.5 Placement guides

On layer \(n\), generate engraving geometry indicating the placement of layer \(n+1\).

Supported guide modes:

```text
full outline
segmented outline
corner marks
centroid cross
component labels
```

Segmented outlines are recommended to avoid clutter.

Placement engravings must use a separate output layer or colour so the laser CAM can assign a low-power engraving operation.

---

## 8.6 Microtabs and retained source sheets

The preferred workflow keeps components attached to the source sheet until needed.

Requirements:

- add configurable microtabs between the cut component and its source-sheet waste;
- place tabs away from fragile vertices;
- use at least two tabs per ordinary component;
- use additional tabs for long, thin, or fragile components;
- emit a warning if no valid tab positions are available;
- include tab positions in preview files.

The source sheet acts as a numbered parts tray.

Assembly sequence:

1. locate the next layer or component;
2. cut its microtabs;
3. remove it;
4. place it immediately onto the registration pins;
5. leave later parts retained in their sheets.

---

## 8.7 Temporary bridges

Disconnected components may be linked temporarily to:

- the outer frame;
- the main component;
- another stable component.

Bridge-generation requirements:

- configurable width;
- shortest valid route that does not cross protected geometry;
- avoid placement on visible edges where possible;
- mark temporary bridges in the manifest;
- optionally engrave a cut-after-assembly symbol;
- verify that bridges survive kerf and material constraints.

Bridge generation may be implemented as a graph problem over candidate anchor points.

---

## 8.8 Sub-stack assembly

The software should assign layers to assembly packets:

```text
Packet 01: L000-L014
Packet 02: L015-L029
Packet 03: L030-L044
```

Packet size should be configurable by:

- number of layers;
- physical stack height;
- estimated assembly time.

The manifest should recommend assembling and gluing one packet at a time before joining packets.

---

## 9. Sheet layout and nesting

## 9.1 Source-sheet layout

The generator should support two modes:

### Ordered tray layout

Place layers in sequential order on sheets. This prioritises assembly convenience over material efficiency.

Recommended arrangement:

```text
left-to-right, top-to-bottom
ascending layer number
one packet per sheet where practical
```

### Material-efficient layout

Export parts to external nesting software.

The output must preserve:

- part IDs;
- engraving geometry;
- grouping constraints;
- grain orientation constraints;
- source-sheet mapping after nesting.

---

## 9.2 Grouping policies

Supported grouping modes:

```text
none
parity
material
packet
height_range
manual
```

Parity grouping:

```text
group = layer_index % 2
```

The application must state that parity grouping does not imply that only two physical sheets are required.

---

## 9.3 Nesting constraints

The sheet-layout subsystem should support:

- sheet width and height;
- edge margin;
- part spacing;
- grain direction;
- rotation allowed or prohibited;
- mirrored placement prohibited by default;
- keep-together constraints for layer and engraving geometry;
- packet grouping;
- microtab clearance.

Parts must never be nested inside another cumulative terrain part unless the receiving part has a genuine through-hole intended for that purpose.

---

## 10. Output structure

Recommended directory structure:

```text
output/
└── helsinki_centre/
    ├── config_resolved.yaml
    ├── report.json
    ├── report.md
    ├── geospatial/
    │   ├── clipped_dem.tif
    │   ├── terrain_layers.gpkg
    │   └── aoi_working_crs.gpkg
    ├── parts/
    │   ├── dxf/
    │   │   ├── L000.dxf
    │   │   ├── L001.dxf
    │   │   └── ...
    │   ├── svg/
    │   └── previews/
    ├── sheets/
    │   ├── group_0/
    │   ├── group_1/
    │   └── ordered/
    ├── assembly/
    │   ├── manifest.csv
    │   ├── manifest.json
    │   ├── assembly_guide.html
    │   ├── packet_01.pdf
    │   └── thumbnails/
    └── validation/
        ├── geometry_errors.geojson
        ├── warnings.csv
        └── dimensional_check.dxf
```

---

## 11. Vector-layer conventions

DXF and SVG exports should separate operations.

Recommended logical layers:

```text
CUT_OUTER
CUT_TERRAIN
CUT_REGISTRATION
CUT_MICROTABS
CUT_TEMPORARY_BRIDGES
ENGRAVE_LAYER_ID
ENGRAVE_COMPONENT_ID
ENGRAVE_NEXT_LAYER_GUIDE
ENGRAVE_ORIENTATION
REFERENCE_DO_NOT_CUT
```

For DXF, use named CAD layers.

For SVG, use named groups with stable IDs.

Do not encode operation semantics only by colour. Layer names must carry the meaning.

---

## 12. Assembly manifest

The manifest must contain one row per component.

Recommended fields:

```text
project_id
layer_index
layer_id
elevation_m
component_index
component_id
packet_id
group_id
source_sheet_id
source_sheet_x_mm
source_sheet_y_mm
component_area_mm2
component_perimeter_mm
small_component_action
temporary_bridge_count
microtab_count
engraving_position
covered_by_next_layer
warnings
```

The human-readable assembly guide should include:

- layer thumbnail;
- elevation;
- component count;
- source sheet;
- packet;
- orientation;
- warnings;
- previous and next layer IDs;
- placement-guide illustration.

---

## 13. Command-line interface

Recommended commands:

```bash
topomap validate config.yaml
topomap preprocess config.yaml
topomap generate-layers config.yaml
topomap add-assembly-features config.yaml
topomap export-parts config.yaml
topomap layout-sheets config.yaml
topomap build-guide config.yaml
topomap run-all config.yaml
```

Useful inspection commands:

```bash
topomap inspect-layer config.yaml --layer 42
topomap preview config.yaml --layer 42
topomap estimate-material config.yaml
topomap check-dimensions output/sheets/group_0/sheet_01.dxf
```

All commands should be:

- deterministic;
- restartable;
- safe to rerun;
- able to skip unchanged stages;
- verbose enough for autonomous debugging.

---

## 14. Software architecture

Recommended modules:

```text
topomap/
├── cli.py
├── config.py
├── crs.py
├── raster.py
├── thresholds.py
├── polygonize.py
├── geometry_cleanup.py
├── scaling.py
├── frame.py
├── registration.py
├── identifiers.py
├── placement_guides.py
├── microtabs.py
├── bridges.py
├── grouping.py
├── nesting.py
├── export_dxf.py
├── export_svg.py
├── manifest.py
├── preview.py
├── validation.py
└── pipeline.py
```

### 14.1 Stage caching

Each stage should write:

- input hashes;
- resolved configuration;
- output metadata;
- software versions.

A later stage should be recomputed only if its relevant inputs or configuration changed.

### 14.2 Determinism

Given the same:

- input raster;
- area of interest;
- configuration;
- software versions;

the pipeline should produce identical geometry and stable identifiers.

---

## 15. Validation requirements

## 15.1 Geometry

For every layer:

- geometry is valid;
- no self-intersections;
- no empty components;
- no component is below the minimum retained size unless explicitly allowed;
- registration features do not overlap terrain;
- engraving remains inside a valid engraving region;
- temporary bridges meet minimum width;
- microtabs meet minimum width;
- no accidental mirrored export.

## 15.2 Layer monotonicity

Because layers are cumulative:

\[
P_{i+1} \subseteq P_i
\]

The application must verify that every higher layer lies within the previous layer, allowing only a small numeric tolerance.

Any violation must be reported visually and in machine-readable form.

## 15.3 Dimensional validation

Generate a calibration file containing:

- 100 mm square;
- registration hole;
- registration slot;
- tab-width samples;
- kerf test comb;
- engraved text samples.

This file must be cut before the full project.

## 15.4 Assembly validation

The application should detect:

- components with no identification location;
- components too small to engrave;
- components with no microtab;
- components not connected to a carrier;
- ambiguous orientation;
- guide geometry missing for disconnected pieces;
- repeated or missing IDs.

---

## 16. Testing strategy

## 16.1 Unit tests

Test:

- scale conversions;
- vertical exaggeration;
- level generation;
- fixed-width IDs;
- parity grouping;
- model-to-sheet transforms;
- hole and slot geometry;
- simplification tolerance conversion;
- manifest generation.

## 16.2 Geometry-property tests

Use generated polygons to verify:

- valid output;
- containment monotonicity;
- no unintended overlaps;
- minimum feature widths;
- bridge connectivity;
- microtab connectivity.

## 16.3 Golden-file tests

Maintain small known DEM fixtures:

```text
single hill
two hills
island
ridge
flat coastline
nested depression
nodata edge
```

Compare generated vectors against reviewed reference outputs.

## 16.4 End-to-end test

A minimal end-to-end fixture should generate:

- 10-20 layers;
- at least one disconnected island;
- at least one temporary bridge;
- two registration features;
- DXF and SVG outputs;
- manifest;
- assembly guide;
- one ordered sheet.

---

## 17. Agentic implementation plan

An autonomous coding agent should implement the project in the following order.

### Phase 1: Minimum viable terrain generation

1. Create project structure.
2. Implement configuration parsing.
3. Load and validate DEM and area of interest.
4. Clip DEM.
5. Generate threshold masks.
6. Polygonize cumulative layers.
7. Export layers to GeoPackage.
8. Add monotonicity tests.

### Phase 2: Fabrication geometry

1. Add model-space scaling.
2. Add frame.
3. Add primary hole and secondary slot.
4. Add layer and component IDs.
5. Export DXF.
6. Generate a calibration file.
7. Validate exact dimensions.

### Phase 3: Assembly support

1. Add next-layer placement guides.
2. Add microtabs.
3. Add retained source-sheet layout.
4. Add temporary bridges.
5. Generate packet assignments.
6. Generate CSV and HTML assembly manifests.

### Phase 4: Nesting and production hardening

1. Add sheet grouping.
2. Add ordered sheet layout.
3. Add interface for external nesting.
4. Preserve source-sheet IDs after nesting.
5. Add caching and stage hashes.
6. Add comprehensive validation reports.
7. Package using Docker or another reproducible environment.

---

## 18. Acceptance criteria

The implementation is complete when it can:

1. ingest a georeferenced Helsinki DEM and polygonal area of interest;
2. generate cumulative terrain layers at a configurable elevation interval;
3. preserve correct metric scale;
4. verify that each higher layer is contained within the previous layer;
5. create a common frame, round datum hole, and elongated datum slot;
6. create stable layer and component identifiers;
7. generate placement engravings for the next layer;
8. retain parts in source sheets with configurable microtabs;
9. create or record a policy for every disconnected small component;
10. split layers into configurable groups, including odd/even parity;
11. export cut and engraving geometry as named DXF layers;
12. produce an assembly manifest and visual guide;
13. produce a dimensional calibration file;
14. report all warnings without silently discarding geometry;
15. reproduce identical outputs from identical inputs.

---

## 19. Practical default settings for a first Helsinki prototype

```text
Area: approximately 1 km × 1 km
Model size: approximately 200 mm × 200 mm
Horizontal scale: 1:5000
Material: 1.5 mm birch plywood
Elevation interval: 2.5 m
Vertical exaggeration: 3×
Simplification tolerance: 1 m ground distance
Minimum retained component: 8 mm² model area
Frame margin: 12 mm
Registration: one 3.1 mm round hole and one 3.1 × 6 mm slot
Microtabs: 0.5 mm, three per component
Packet size: 15 layers
Primary vector format: DXF
Secondary vector format: SVG
```

These values must be treated as starting points and verified with a physical kerf and fit test.

---

## 20. Key implementation decisions

The coding agent should preserve the following design principles:

- Generate cumulative polygons, not only contour lines.
- Keep geospatial, model, and sheet coordinate systems separate.
- Express fabrication tolerances in model millimetres.
- Build alignment and identification into the geometry.
- Keep parts retained in source sheets until assembly.
- Use a round-hole-and-slot datum system rather than two tight circular holes.
- Give every disconnected component a stable identity and explicit handling policy.
- Prefer ordered, packet-based layouts when assembly reliability is more important than maximum material utilisation.
- Treat odd/even grouping as an organisational feature, not proof that two physical sheets are sufficient.
- Produce machine-readable reports alongside human-readable assembly instructions.
