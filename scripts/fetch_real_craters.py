#!/usr/bin/env python3
"""Tải published Quang Tri crater predictions từ Zenodo record 10629987.

Chạy tốt trên Kaggle khi Internet=ON. Script dùng Zenodo REST API nên không phụ
thuộc URL file tĩnh.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import zipfile

import requests

RECORD_ID = 10629987


def download(url: str, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r{100*done/total:5.1f}%", end="", flush=True)
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="data/real/craters/quang_tri")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    meta = requests.get(
        f"https://zenodo.org/api/records/{RECORD_ID}", timeout=30
    ).json()
    files = meta.get("files", [])
    pred = next((f for f in files if f.get("key") == "predictions.zip"), None)
    if pred is None:
        raise RuntimeError("Zenodo record không có predictions.zip")

    links = pred.get("links", {})
    url = links.get("content") or links.get("self")
    if not url:
        raise RuntimeError("Không tìm thấy download URL từ Zenodo metadata")

    zip_path = out / "predictions.zip"
    if not zip_path.exists():
        print("Đang tải predictions.zip (~48 MB) ...")
        download(url, zip_path)

    with zipfile.ZipFile(zip_path) as z:
        candidates = [
            n for n in z.namelist()
            if "quang_tri" in n.lower()
            and n.lower().endswith(("crater_centroids.geojson", "crater_polygons.geojson"))
        ]
        if not candidates:
            # fallback tìm mọi Quang Tri geojson để người dùng inspect
            candidates = [
                n for n in z.namelist()
                if "quang_tri" in n.lower() and n.lower().endswith(".geojson")
            ]
        print("Các file Quảng Trị tìm thấy:")
        for n in candidates:
            print(" -", n)
            target = out / Path(n).name
            with z.open(n) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)

    manifest = {
        "zenodo_record": RECORD_ID,
        "source_title": meta.get("metadata", {}).get("title"),
        "extracted": [str(out / Path(n).name) for n in candidates],
    }
    (out / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Hoàn tất:", out)


if __name__ == "__main__":
    main()
