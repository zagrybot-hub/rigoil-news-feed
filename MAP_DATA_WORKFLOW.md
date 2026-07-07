# RigOil map data workflow

Goal: keep public map fast while allowing manual refresh from Wix CMS `platforms` data.

## Files

- `platform_map_data.json` — lightweight static map payload used by `rigoil-map-search.html`.
- `scripts/export_platform_map_data.py` — manual export/update process.
- `logs/platform_map_data_export_*.json` — export logs.
- `platform_map_data_BACKUP_YYYY-MM-DD_HH-MM-SS.json` — automatic backups before overwrite.

## Manual update

From this directory:

```bash
python3 scripts/export_platform_map_data.py
```

This writes both:

- `platform_map_data.json` for the standalone GitHub Pages map.
- `/home/zac/rigoil/00 ALL DATA/09_website_wix/website_assets/platforms.json` as the lightweight Vercel/Wix-feeder compatibility file used by current live Wix custom code.

Deploy the current live Wix feeder data:

```bash
cd "/home/zac/rigoil/00 ALL DATA/10_archive/original-root-leftovers-2026-05-28/public"
cp "/home/zac/rigoil/00 ALL DATA/09_website_wix/website_assets/platforms.json" ./platforms.json
set -a; . "/home/zac/01 All Tokens/01 Vercel_Token.env"; set +a
npx vercel deploy --prod --yes --token "$VERCEL_TOKEN"
```

Default source priority:

1. local mirror of Wix CMS/public platforms data: `/home/zac/rigoil/00 ALL DATA/09_website_wix/website_assets/platforms.json`
2. `/home/zac/rigoil/00 ALL DATA/09_website_wix/website_assets/public__platforms.json`
3. older Wix live export CSV fallback

To export from a fresh Wix CMS `platforms` CSV/JSON dump:

```bash
python3 scripts/export_platform_map_data.py --source /path/to/platforms.csv
```

Dry run:

```bash
python3 scripts/export_platform_map_data.py --dry-run
```

## Payload rules

Export includes only map-needed fields:

- `n` platform name
- `lat`, `lng`
- `img` popup image URL
- `slug`
- `url` platform page URL
- `a` aliases
- `field`, `fg` compact field/group only if present
- `c` country
- `b` block
- `t` platform type/category
- `op` operator, stored only for search/filtering; not displayed on map or popup

Large fields are deliberately excluded: intros, facilities, full Field descriptions, production data, news, full CMS metadata.

## Public map loading

`rigoil-map-search.html` loads `platform_map_data.json` as a static cached file. It does not query Wix CMS or the full public platform JSON on visitor page load.

Popup rules:

- shows platform name
- loads popup image only when popup opens
- shows Details button
- does not display operator

Map labels:

- marker icon
- platform name label only
- no operator or extra metadata on map

## Rollback

If export is bad, restore latest backup:

```bash
cp platform_map_data_BACKUP_YYYY-MM-DD_HH-MM-SS.json platform_map_data.json
```

Then commit/push or redeploy the static site.
