#!/usr/bin/env python3
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / 'static' / 'processed'

if not PROC.exists():
    print('No processed directory found at', PROC)
    raise SystemExit(1)

files = sorted([p for p in PROC.iterdir() if p.suffix.lower() in ('.webp', '.png', '.jpg', '.jpeg')])
if not files:
    print('No processed images found')
    raise SystemExit(0)

for f in files:
    try:
        im = Image.open(f).convert('RGBA')
        px = im.getdata()
        total = im.width * im.height
        trans = 0
        # sample pixels to speed up: check every 10th pixel if large
        step = 1
        if total > 100000:
            step = max(1, total // 10000)
        for i in range(0, total, step):
            a = px[i][3]
            if a < 255:
                trans += 1
                break
        print(f.name, '->', 'contains_transparency' if trans else 'opaque')
    except Exception as e:
        print(f.name, '-> error:', e)
