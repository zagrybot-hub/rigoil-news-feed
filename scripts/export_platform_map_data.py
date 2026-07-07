#!/usr/bin/env python3
"""Export lightweight RigOil map data from latest Wix CMS export.

Default source is the latest local CSV export of the Wix CMS `platforms` collection.
Optional: pass --source PATH to a CSV/JSON exported from Wix CMS.

Output:
  platform_map_data.json
  logs/platform_map_data_export_YYYY-MM-DD_HH-MM-SS.json
  platform_map_data_BACKUP_YYYY-MM-DD_HH-MM-SS.json before overwrite
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "platform_map_data.json"
LOG_DIR = ROOT / "logs"

DEFAULT_SOURCE_CANDIDATES = [
    # Authoritative master CSV with curated platform names, photos, layout links.
    Path("/home/zac/rigoil/00 ALL DATA/02_processed_data/master_spreadsheets/rigoil-platforms-master-review-v1.0-2026-05-28.csv"),
    Path("/home/zac/rigoil/00 ALL DATA/09_website_wix/website_assets/platforms.json"),
    Path("/home/zac/rigoil/00 ALL DATA/09_website_wix/website_assets/public__platforms.json"),
    Path("/home/zac/rigoil/00 ALL DATA/09_website_wix/wix_exports/platform_name_update_2026-07-04/exports__wix-live-export__platforms_import1_live_export__names_from_master.csv"),
]

SITE_BASE = "https://bookbitemedia.wixsite.com/rigoil-zac"
DETAIL_PATH = "/blank-3?slug="

@dataclass
class SkipRecord:
    name: str
    slug: str
    reason: str


def first(row: Dict[str, Any], *keys: str, case_insensitive: bool = True) -> str:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return str(row[key]).strip()
    if case_insensitive:
        low = {str(k).lower(): v for k, v in row.items()}
        for key in keys:
            v = low.get(key.lower())
            if v not in (None, ""):
                return str(v).strip()
    return ""


def parse_float(value: Any) -> Optional[float]:
    try:
        if value is None or str(value).strip() == "":
            return None
        x = float(str(value).strip())
        if not math.isfinite(x):
            return None
        return x
    except Exception:
        return None


def slugify(value: str) -> str:
    value = value.strip().lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def split_aliases(value: str) -> List[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in re.split(r"[|,;]", value) if x.strip()]


def load_rows(path: Path) -> List[Dict[str, Any]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("platforms") or data.get("data") or data.get("items") or []
        if not isinstance(data, list):
            raise ValueError(f"JSON source is not a list: {path}")
        return [x for x in data if isinstance(x, dict)]
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        return list(csv.DictReader(f))


def normalize(row: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[SkipRecord], Dict[str, bool]]:
    name = first(row, "Name", "name", "Title", "title")
    slug = first(row, "slug", "routeSlug", "Slug", "Platforms (Item)", "slugRef", "SlugRef")
    if slug.startswith("/platforms/"):
        slug = slug.rsplit("/", 1)[-1]
    slug = slug.lower().strip()
    if not slug and name:
        slug = slugify(name)

    lat = parse_float(first(row, "Latitude", "latitude", "lat"))
    lng = parse_float(first(row, "Longitude", "longitude", "lng"))
    if not name:
        return None, SkipRecord(name="", slug=slug, reason="missing platform name"), {}
    if lat is None or lng is None or not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return None, SkipRecord(name=name, slug=slug, reason="missing or invalid latitude/longitude"), {}
    if not slug:
        return None, SkipRecord(name=name, slug="", reason="missing usable slug/page URL"), {"missing_slug": True}

    image = first(row, "photo", "Photo", "image", "Image", "mainImage", "Main Image", "platformImage")
    country = first(row, "Country", "country")
    block = first(row, "Location (blocks)", "blockLocation", "Block", "block", "location")
    # Keep map payload small: use only compact field/group fields, not long CMS rich-text `Field` descriptions.
    field = first(row, "Field name", "fieldName", "Field", "field", case_insensitive=False)
    field_group = first(row, "Field group", "fieldGroup", "assetGroup", "newsGroup", case_insensitive=False)
    asset_type = first(row, "Platform type", "assetType", "type", "Category", "category")
    operator = first(row, "Operator", "operator")
    aliases = split_aliases(first(row, "aliases", "Aliases", "alternativeNames", "Alternative Names"))
    layout = first(row, "layout", "Layout")

    rec = {
        "n": name,
        "lat": round(lat, 7),
        "lng": round(lng, 7),
        "img": image,
        "ly": layout,
        "slug": slug,
        "url": f"{SITE_BASE}{DETAIL_PATH}{slug}",
        "a": aliases,
        "field": field,
        "fg": field_group,
        "c": country,
        "b": block,
        "t": asset_type,
        "op": operator,
        "st": first(row, "status", "Current Status", "Status"),
        "intro": first(row, "intro", "Intro"),
        "rm": first(row, "remarks", "Remarks"),
        "fac": first(row, "facilities", "Facilities"),
        "news": first(row, "news", "News"),
        "prod": first(row, "primaryProduction", "Primary production", "primaryProduction", "Production"),
        "water": first(row, "waterDepth", "Water Depth", "Water Depth (m)"),
        "cat": first(row, "category", "Category"),
        "fn": first(row, "function", "Function"),
        "ops": first(row, "operationsStart", "Operations start"),
        "field_obj": first(row, "fieldObj", "fieldObj"),
        "news_group": first(row, "newsGroup", "newsGroup", "Field group", "fieldGroup"),
        "group": first(row, "group", "Group"),
    }
    # drop empty optional keys, keep compact payload
    rec = {k: v for k, v in rec.items() if v not in ("", [], None)}
    flags = {"missing_image": not bool(image), "missing_slug": False}
    return rec, None, flags


def choose_source(source_arg: Optional[str]) -> Path:
    if source_arg:
        p = Path(source_arg).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(p)
        return p
    for p in DEFAULT_SOURCE_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("No default CMS export source found; pass --source")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="CSV/JSON export from Wix CMS `platforms` collection")
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output compact GitHub/static map data JSON")
    ap.add_argument(
        "--wix-feed-output",
        default="/home/zac/rigoil/00 ALL DATA/09_website_wix/website_assets/platforms.json",
        help="Optional Vercel/Wix feeder compatibility JSON path; pass empty string to skip",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    source = choose_source(args.source)
    output = Path(args.output).expanduser().resolve()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_rows(source)
    exported: List[Dict[str, Any]] = []
    skipped: List[SkipRecord] = []
    seen: Dict[str, str] = {}
    duplicates: List[Dict[str, str]] = []
    missing_images: List[Dict[str, str]] = []
    missing_slugs: List[Dict[str, str]] = []

    for row in rows:
        rec, skip, flags = normalize(row)
        if skip:
            skipped.append(skip)
            if flags.get("missing_slug"):
                missing_slugs.append({"name": skip.name, "slug": skip.slug})
            continue
        assert rec is not None
        key = rec.get("slug") or f"{rec['n']}:{rec['lat']}:{rec['lng']}"
        if key in seen:
            duplicates.append({"slug": key, "first": seen[key], "duplicate": rec["n"]})
            skipped.append(SkipRecord(name=rec["n"], slug=str(key), reason="duplicate slug/record"))
            continue
        seen[str(key)] = rec["n"]
        if flags.get("missing_image"):
            missing_images.append({"name": rec["n"], "slug": rec.get("slug", "")})
        exported.append(rec)

    exported.sort(key=lambda x: str(x.get("n", "")).lower())
    payload = {
        "schemaVersion": 1,
        "generatedAt": now.isoformat(),
        "source": str(source),
        "count": len(exported),
        "platforms": exported,
    }

    backup_path = None
    if output.exists() and not args.dry_run:
        backup_path = output.with_name(f"{output.stem}_BACKUP_{stamp}{output.suffix}")
        shutil.copy2(output, backup_path)

    wix_feed_path = Path(args.wix_feed_output).expanduser().resolve() if args.wix_feed_output else None
    wix_feed_backup = None
    wix_feed_payload = None
    if wix_feed_path:
        wix_feed_payload = {
            "generatedAt": payload["generatedAt"],
            "source": "RigOil CMS static map export",
            "count": len(exported),
            "platforms": [
                {
                    "name": p.get("n", ""),
                    "latitude": p.get("lat"),
                    "longitude": p.get("lng"),
                    "routeSlug": p.get("slug", ""),
                    "slug": p.get("slug", ""),
                    "photo": p.get("img", ""),
                    "image": p.get("img", ""),
                    "layout": p.get("ly", ""),
                    "fieldName": p.get("field", ""),
                    "country": p.get("c", ""),
                    "block": p.get("b", ""),
                    "platformType": p.get("t", ""),
                    "operator": p.get("op", ""),
                    "status": p.get("st", ""),
                    "intro": p.get("intro", ""),
                    "remarks": p.get("rm", ""),
                    "facilities": p.get("fac", ""),
                    "news": p.get("news", ""),
                    "primaryProduction": p.get("prod", ""),
                    "waterDepth": p.get("water", ""),
                    "category": p.get("cat", ""),
                    "function": p.get("fn", ""),
                    "operationsStart": p.get("ops", ""),
                    "searchAliases": p.get("a", []),
                    "fieldGroup": p.get("fg", ""),
                    "newsGroup": p.get("news_group", ""),
                    "group": p.get("group", ""),
                    "fieldObj": p.get("field_obj", ""),
                }
                for p in exported
            ],
        }
        if wix_feed_path.exists() and not args.dry_run:
            wix_feed_backup = wix_feed_path.with_name(f"{wix_feed_path.name}.bak-static-map-{now.strftime('%Y%m%dT%H%M%SZ')}")
            shutil.copy2(wix_feed_path, wix_feed_backup)

    if not args.dry_run:
        output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        if wix_feed_path and wix_feed_payload is not None:
            wix_feed_path.parent.mkdir(parents=True, exist_ok=True)
            wix_feed_path.write_text(json.dumps(wix_feed_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    log = {
        "status": "dry_run" if args.dry_run else "success",
        "exportedAt": now.isoformat(),
        "source": str(source),
        "output": str(output),
        "backup": str(backup_path) if backup_path else None,
        "cmsRecordsRead": len(rows),
        "platformsExported": len(exported),
        "platformsSkipped": len(skipped),
        "skipped": [asdict(x) for x in skipped],
        "missingImages": missing_images,
        "missingSlugsOrUrls": missing_slugs,
        "duplicates": duplicates,
        "outputBytes": output.stat().st_size if output.exists() and not args.dry_run else None,
        "wixFeedOutput": str(wix_feed_path) if wix_feed_path else None,
        "wixFeedBackup": str(wix_feed_backup) if wix_feed_backup else None,
        "wixFeedBytes": wix_feed_path.stat().st_size if wix_feed_path and wix_feed_path.exists() and not args.dry_run else None,
    }
    log_path = LOG_DIR / f"platform_map_data_export_{stamp}.json"
    if not args.dry_run:
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({k: log[k] for k in ["status", "source", "output", "backup", "cmsRecordsRead", "platformsExported", "platformsSkipped", "outputBytes"]}, ensure_ascii=False, indent=2))
    if skipped:
        print(f"Skipped {len(skipped)} records; see log: {log_path}")
    return 0 if exported else 2

if __name__ == "__main__":
    raise SystemExit(main())
