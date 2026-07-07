#!/usr/bin/env python3
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'platform_map_data.json'
HTML = ROOT / 'rigoil-map-search.html'
LOG_DIR = ROOT / 'logs'

payload = json.loads(DATA.read_text(encoding='utf-8'))
platforms = payload['platforms']
assert payload['schemaVersion'] == 1
assert payload['count'] == len(platforms)
assert len(platforms) > 500
seen = set()
for p in platforms:
    assert p.get('n'), p
    assert isinstance(p.get('lat'), (int, float)) and -90 <= p['lat'] <= 90, p
    assert isinstance(p.get('lng'), (int, float)) and -180 <= p['lng'] <= 180, p
    assert p.get('slug') or p.get('url'), p
    key = p.get('slug') or p['url']
    assert key not in seen, key
    seen.add(key)
    forbidden = ['intro', 'facilities', 'productionChart', 'latestNews', 'remarks']
    assert not any(k in p for k in forbidden), p

html = HTML.read_text(encoding='utf-8')
assert 'platform_map_data.json' in html
assert 'public-zagrybot.vercel.app/platforms.json' not in html
assert "wixData.query" not in html
assert "loc.operator||''+'</span>" not in html
assert 'loading="lazy"' in html
assert 'decoding="async"' in html
assert 'Search platform, field, country, block' in html
assert 'Search by name, field, country or block' in html
assert re.search(r"\[r\.loc\.country,r\.loc\.block\]", html)
assert LOG_DIR.exists() and any(LOG_DIR.glob('platform_map_data_export_*.json'))
assert any(ROOT.glob('platform_map_data_BACKUP_*.json'))
print(json.dumps({
    'ok': True,
    'platforms': len(platforms),
    'bytes': DATA.stat().st_size,
    'latestLog': str(sorted(LOG_DIR.glob('platform_map_data_export_*.json'))[-1].name),
}, indent=2))
