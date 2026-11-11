"""MANUAL: command line.

    mapcut fetch  configs/x.toml [--force]   download DEM tile + roads/buildings (NLS via Paituli)
    mapcut build  configs/x.toml             write blanks, panels, calibration, manifest, previews
"""

from __future__ import annotations

import argparse
import sys

from . import config, dem, export, features, levels, panels, parts, preview, report


def build(cfg: config.Config) -> str:
    grid = dem.load(cfg)
    sx, sy = dem.tile_square(cfg)
    lv = levels.build_levels(grid, sx, sy, cfg)
    pieces = parts.build_pieces(lv, cfg)
    if feats := features.load(cfg, sx, sy):
        features.engrave_on(pieces, lv, feats, cfg)
    pans = panels.build_panels(lv, cfg)
    out = cfg.output_dir
    out.mkdir(parents=True, exist_ok=True)
    for j in range(cfg.k):
        export.write_blank(out / f"blank_{j}.dxf", j, lv, pieces, cfg)
    export.write_panels(out / "panels.dxf", pans)
    export.write_calibration(out / "calibration.dxf", cfg)
    report.write_manifest(out / "manifest.csv", pieces)
    text = report.summary(lv, pieces, pans, cfg)
    (out / "report.txt").write_text(text)
    preview.render(out, lv, pieces, pans, cfg)
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mapcut")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download the DEM tile")
    f.add_argument("config")
    f.add_argument("--force", action="store_true")
    b = sub.add_parser("build", help="generate cut files")
    b.add_argument("config")
    args = ap.parse_args(argv)
    cfg = config.load(args.config)
    if args.cmd == "fetch":
        print("dem: downloaded" if dem.fetch(cfg, args.force) else f"dem: cached {cfg.dem} (use --force)")
        for line in features.fetch(cfg, *dem.tile_square(cfg), force=args.force):
            print(line)
    else:
        print(build(cfg), end="")
        print(f"output: {cfg.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
