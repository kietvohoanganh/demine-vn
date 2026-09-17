#!/usr/bin/env python3
"""Discover and download PUBLIC Quang Tri mine-action validation layers.

Primary discovery source: Stimson Center's War Legacies Data Dashboard
(ArcGIS Experience Builder), whose Quang Tri clearance tab is described by
Stimson as using data courtesy of QTMAC.

This script never fabricates a fallback. If public ArcGIS geometry cannot be
found/downloaded, it writes a provenance/discovery manifest and exits cleanly
with ground_truth_available=false.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import requests

EXPERIENCE_ID = "70dd78951d9e454faaf78fa8f265744f"
ARCGIS = "https://www.arcgis.com/sharing/rest/content/items"
USER_AGENT = "Hệ thống hỗ trợ xếp hạng khu vực ưu tiên rà phá bom mìn/1.0 public-research-validation"
HEX_ID = re.compile(r"\b[a-f0-9]{32}\b", re.I)

SOURCE_CONTEXT = {
    "accessed_utc": "2026-09-16T17:00:00Z",
    "spatial_ground_truth_policy": (
        "Only public point/polygon records are accepted as spatial validation. "
        "Aggregate province statistics are context only and are never allocated to grid cells."
    ),
    "sources": [
        {
            "name": "Stimson Center — War Legacies Data Dashboard",
            "url": "https://www.stimson.org/2024/war-legacies-data-dashboard/",
            "arcgis_experience_item": EXPERIENCE_ID,
            "role": "public spatial validation discovery",
            "scope_note": "Stimson describes the Quang Tri Clearance Data tab as focused on Dong Ha District and courtesy of QTMAC.",
        },
        {
            "name": "Quang Tri Mine Action Center (QTMAC)",
            "url": "https://qtmac.vn/public/en",
            "role": "authoritative mine-action context / IMSMA provenance",
            "scope_note": "QTMAC states its dashboard is updated from the IMSMA database managed by QTMAC/DBU.",
            "aggregate_snapshot": {
                "surveyed_cha_area_ha": 91581,
                "land_released_ha": 63604,
                "explosive_ordnance_found_destroyed": 938541,
                "use": "context_only_not_spatial_ground_truth",
            },
        },
    ],
}


def get_json(session: requests.Session, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    r = session.get(url, params=params, timeout=45)
    r.raise_for_status()
    return r.json()


def item_meta(session: requests.Session, item_id: str) -> dict[str, Any]:
    return get_json(session, f"{ARCGIS}/{item_id}", {"f": "json"})


def item_data(session: requests.Session, item_id: str) -> dict[str, Any]:
    return get_json(session, f"{ARCGIS}/{item_id}/data", {"f": "json"})


def extract_ids(obj: Any) -> set[str]:
    text = json.dumps(obj, ensure_ascii=False)
    return set(HEX_ID.findall(text))


def classify_layer(name: str) -> str | None:
    s = name.lower()
    if any(k in s for k in ["confirmed hazardous", "hazardous area", " cha", "cha ", "cha_"]):
        return "cha"
    if any(k in s for k in ["land release", "released land", "clearance", "cleared area"]):
        return "land_release"
    if any(k in s for k in ["eod", "ordnance", "explosive", "uxo", "munition"]):
        return "eod"
    return None


def feature_service_layers(session: requests.Session, service_url: str) -> list[dict[str, Any]]:
    meta = get_json(session, service_url, {"f": "json"})
    return meta.get("layers", [])


def query_geojson(session: requests.Session, layer_url: str) -> dict[str, Any]:
    ids = get_json(session, f"{layer_url}/query", {"where": "1=1", "returnIdsOnly": "true", "f": "json"}).get("objectIds") or []
    features: list[dict[str, Any]] = []
    for i in range(0, len(ids), 500):
        chunk = ids[i:i+500]
        data = get_json(session, f"{layer_url}/query", {
            "objectIds": ",".join(map(str, chunk)),
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        })
        features.extend(data.get("features", []))
    return {"type": "FeatureCollection", "features": features}


def discover_service_urls(session: requests.Session, root_item: str) -> tuple[list[dict[str, Any]], list[str]]:
    visited: set[str] = set()
    queue = [root_item]
    items: list[dict[str, Any]] = []
    services: set[str] = set()

    while queue and len(visited) < 80:
        item_id = queue.pop(0)
        if item_id in visited:
            continue
        visited.add(item_id)
        try:
            meta = item_meta(session, item_id)
            data = item_data(session, item_id)
        except Exception:
            continue
        items.append({"id": item_id, "title": meta.get("title"), "type": meta.get("type"), "url": meta.get("url")})
        if meta.get("type") in {"Feature Service", "Map Service"} and meta.get("url"):
            services.add(str(meta["url"]))
        # Web-map operational layers may include service URLs directly.
        for layer in (data.get("operationalLayers", []) if isinstance(data, dict) else []):
            if isinstance(layer, dict):
                if layer.get("url"):
                    services.add(str(layer["url"]))
                if layer.get("itemId"):
                    queue.append(str(layer["itemId"]))
        for linked in extract_ids(data):
            if linked not in visited:
                queue.append(linked)
    return items, sorted(services)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="data/real/ground_truth")
    ap.add_argument("--experience-item", default=EXPERIENCE_ID)
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    manifest: dict[str, Any] = dict(SOURCE_CONTEXT)
    manifest.update({"ground_truth_available": False, "downloaded_layers": [], "discovered_items": [], "discovered_services": []})

    try:
        items, services = discover_service_urls(session, args.experience_item)
        manifest["discovered_items"] = items
        manifest["discovered_services"] = services
        for service in services:
            try:
                layers = feature_service_layers(session, service)
            except Exception:
                continue
            for layer in layers:
                layer_id = layer.get("id")
                name = str(layer.get("name", ""))
                kind = classify_layer(" " + name + " ")
                if kind is None or layer_id is None:
                    continue
                layer_url = f"{service.rstrip('/')}/{layer_id}"
                try:
                    geo = query_geojson(session, layer_url)
                except Exception as exc:
                    manifest["downloaded_layers"].append({"name": name, "kind": kind, "url": layer_url, "status": "query_failed", "error": str(exc)})
                    continue
                safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:80] or f"layer_{layer_id}"
                path = out / f"{kind}__{safe}.geojson"
                path.write_text(json.dumps(geo, ensure_ascii=False), encoding="utf-8")
                manifest["downloaded_layers"].append({"name": name, "kind": kind, "url": layer_url, "features": len(geo.get("features", [])), "file": path.name, "status": "downloaded"})
        manifest["ground_truth_available"] = any(x.get("status") == "downloaded" and x.get("features", 0) > 0 for x in manifest["downloaded_layers"])
    except Exception as exc:
        manifest["discovery_error"] = str(exc)

    (out / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "ground_truth_available": manifest["ground_truth_available"], "downloaded_layers": len(manifest["downloaded_layers"]), "manifest": str(out / 'source_manifest.json')}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
