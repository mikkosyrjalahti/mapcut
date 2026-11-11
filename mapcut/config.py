"""Map configuration: one TOML file per map, flattened into a frozen dataclass."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

SECTIONS = ("project", "input", "terrain", "model", "fabrication", "features")


@dataclass(frozen=True)
class Config:
    # [project]
    name: str
    output_dir: Path
    # [input] tile centre in WGS84; the square itself is laid out in EPSG:3067 (NLS native CRS)
    dem: Path
    center_lat: float
    center_lon: float
    size_m: float = 1000.0
    # [terrain]
    interval_m: float = 2.5
    base_m: float | None = None  # None: lowest terrain floored to the interval
    blur_sigma_mm: float = 0.5
    smooth_radius_mm: float = 0.3
    simplify_mm: float = 0.05
    # [model]
    scale: int = 5000
    thickness_mm: float = 1.5
    k: int = 3
    # [fabrication]
    min_width_mm: float = 1.0
    min_area_mm2: float = 4.0
    guide_inset_mm: float = 0.4
    id_height_mm: float = 2.0
    id_min_height_mm: float = 1.2
    blank_width_mm: float = 800.0
    blank_height_mm: float = 600.0
    blank_margin_mm: float = 10.0
    # Tabs: uncut gaps in the cut path that hold small pieces in the sheet. The real bridge is
    # narrower than tab_width_mm by roughly one kerf.
    tab_width_mm: float = 0.5
    tab_angles_deg: tuple[float, ...] = (0.0, 120.0, 240.0)
    tab_max_area_mm2: float = 200.0  # only pieces this small get tabs; each tab leaves a visible nub
    # [features] NLS topographic database; None disables that feature
    buildings: Path | None = None
    roads: Path | None = None
    # NLS road classes: 1211x/1212x main roads, 1213x streets. Driveways (12141) and paths (123xx) excluded.
    road_classes: tuple[int, ...] = (12111, 12112, 12121, 12122, 12131, 12132)
    min_building_mm2: float = 1.0
    feature_clearance_mm: float = 0.2

    def __post_init__(self) -> None:
        if self.k < 2:
            # k=1 would put overlapping layers on the same blank
            raise ValueError("k must be >= 2")
        for name in ("size_m", "interval_m", "scale", "thickness_mm", "min_width_mm", "id_height_mm"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        need = self.map_mm + 2 * self.blank_margin_mm
        if need > min(self.blank_width_mm, self.blank_height_mm):
            raise ValueError(f"map {self.map_mm:.0f} mm + margins does not fit the blank; tile it or change scale")

    @property
    def mm_per_m(self) -> float:
        return 1000.0 / self.scale

    @property
    def map_mm(self) -> float:
        return self.size_m * self.mm_per_m

    @property
    def vertical_exaggeration(self) -> float:
        return self.thickness_mm * self.scale / (1000.0 * self.interval_m)


def load(path: str | Path) -> Config:
    path = Path(path)
    raw = tomllib.loads(path.read_text())
    # Typos must fail loudly instead of silently falling back to a default.
    if bad := set(raw) - set(SECTIONS):
        raise ValueError(f"unknown config sections: {sorted(bad)}")
    flat: dict = {}
    for section in SECTIONS:
        flat.update(raw.get(section, {}))
    if bad := set(flat) - {f.name for f in fields(Config)}:
        raise ValueError(f"unknown config keys: {sorted(bad)}")
    for key in ("output_dir", "dem", "buildings", "roads"):
        if key in flat:
            flat[key] = (path.parent / flat[key]).resolve()
    for key in ("road_classes", "tab_angles_deg"):
        if key in flat:
            flat[key] = tuple(flat[key])
    return Config(**flat)
