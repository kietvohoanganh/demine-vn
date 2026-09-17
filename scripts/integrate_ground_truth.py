#!/usr/bin/env python3
"""Overlay optional PUBLIC field-validation layers onto the existing priority grid.

This script does not alter the priority score. It writes validation-only outputs.
"""
from __future__ import annotations
import argparse
import json
from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demine.data.ground_truth import integrate_validation


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ground-truth-dir", default="data/real/ground_truth")
    ap.add_argument("--grid", default="outputs_final/data/priority_grid_compact.json")
    ap.add_argument("--output-dir", default="outputs_final/data")
    args = ap.parse_args()

    gt = Path(args.ground_truth_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    cha = sorted(gt.glob("cha__*.geojson"))
    release = sorted(gt.glob("land_release__*.geojson"))
    eod = sorted(gt.glob("eod__*.geojson"))

    manifest_path = gt / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    if not (cha or release or eod):
        result = {
            "available": False,
            "spatial_layers_loaded": 0,
            "field_verified": False,
            "is_probability": False,
            "message": "Chưa tải được point/polygon ground truth công khai. Không tạo dữ liệu thay thế.",
            "source_context": manifest.get("sources", []),
        }
        (out / "ground_truth_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "PASS", **result}, ensure_ascii=False, indent=2))
        return

    cells, summary = integrate_validation(args.grid, cha, release, eod)
    cells.to_csv(out / "ground_truth_cells.csv", index=False, encoding="utf-8-sig")
    result = asdict(summary)
    result.update({
        "spatial_layers_loaded": len(cha) + len(release) + len(eod),
        "cha_files": [p.name for p in cha],
        "land_release_files": [p.name for p in release],
        "eod_files": [p.name for p in eod],
        "field_verified": bool(summary.available),
        "is_probability": False,
        "metric_note": "Coverage@topX measures overlap with independent field-validation records; it is not a calibrated P(UXO) and may be affected by survey/clearance selection bias.",
        "source_context": manifest.get("sources", []),
    })
    (out / "ground_truth_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
