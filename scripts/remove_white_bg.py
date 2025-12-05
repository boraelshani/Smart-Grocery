#!/usr/bin/env python3
"""Download product images from the DB, convert near-white pixels to transparent,
and save processed images to `static/processed/<sha1>.webp`.

Usage: run from project root with MONGO_URI in environment or in .env
  python scripts/remove_white_bg.py

Notes:
- Requires `requests` and `Pillow`.
- Converted images are stored in `static/processed` and referenced by a URL
  based on the sha1 of the original image URL.
"""
import os
import hashlib
import io
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

MONGO_URI = os.environ.get('MONGO_URI')
if not MONGO_URI:
    print('Error: MONGO_URI not set in environment or .env')
    raise SystemExit(1)

from pymongo import MongoClient
import requests
from PIL import Image
try:
    from rembg import remove as rembg_remove
except Exception:
    rembg_remove = None


ROOT = Path(__file__).resolve().parents[1]
STATIC_PROCESSED = ROOT / 'static' / 'processed'
STATIC_PROCESSED.mkdir(parents=True, exist_ok=True)


def sha1_for_url(url: str) -> str:
    return hashlib.sha1(url.encode('utf-8')).hexdigest()


def download_image(url: str) -> bytes | None:
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f'  download failed for {url}: {e}')
        return None


def convert_white_to_alpha(img_bytes: bytes, threshold: int = 240) -> bytes | None:
    try:
        with Image.open(io.BytesIO(img_bytes)) as im:
            im = im.convert("RGBA")
            datas = im.getdata()

            new_data = []
            for r, g, b, a in datas:
                # distance from white
                if max(r, g, b) >= threshold and (abs(r-g) < 20 and abs(g-b) < 20):
                    new_data.append((255, 255, 255, 0))  # make transparent
                else:
                    new_data.append((r, g, b, a))

            im.putdata(new_data)

            output = io.BytesIO()
            im.save(output, "WEBP", quality=95)
            return output.getvalue()

    except Exception as e:
        print("  convert failed:", e)
        return None


def main():
    client = MongoClient(MONGO_URI)
    dbname = os.environ.get('MONGO_DBNAME') or 'smart_grocery'
    # if a default DB was embedded in the URI, get_default_database() will return it
    try:
        default_db = client.get_default_database()
        if default_db is not None and default_db.name:
            dbname = default_db.name
    except Exception:
        # keep dbname from env or fallback
        pass
    db = client[dbname]
    print('Connected to DB:', db.name)

    products = db.products.find({})
    count = 0
    for p in products:
        image_url = None
        # Support various field names
        if isinstance(p.get('image'), str) and p.get('image').startswith('http'):
            image_url = p.get('image')
        elif p.get('images') and isinstance(p.get('images'), list) and len(p.get('images')):
            candidate = p.get('images')[0]
            if isinstance(candidate, str) and candidate.startswith('http'):
                image_url = candidate

        if not image_url:
            continue

        key = sha1_for_url(image_url)
        out_name = key + '.webp'
        out_path = STATIC_PROCESSED / out_name
        # overwrite existing processed files to apply new algorithm
        if out_path.exists():
            print(f'Overwriting existing processed file: {out_name} for product id={p.get("_id")}')

        print(f'Processing product id={p.get("_id")} url={image_url}')
        img_bytes = download_image(image_url)
        if not img_bytes:
            continue
        processed = None
        # If rembg is available, prefer it (better background removal)
        if rembg_remove is not None:
            try:
                out_bytes = rembg_remove(img_bytes)
                # convert returned bytes (PNG) to WEBP for consistency
                try:
                    with Image.open(io.BytesIO(out_bytes)) as rim:
                        rim = rim.convert('RGBA')
                        out_buf = io.BytesIO()
                        rim.save(out_buf, format='WEBP', quality=95)
                        processed = out_buf.getvalue()
                except Exception:
                    # if conversion fails, fall back to raw rembg output
                    processed = out_bytes
            except Exception as e:
                print('  rembg failed:', e)
                processed = None

        if processed is None:
            processed = convert_white_to_alpha(img_bytes)
        if not processed:
            print('  processing failed, skipping')
            continue
        try:
            with open(out_path, 'wb') as f:
                f.write(processed)
            print('  wrote', out_path)
            count += 1
        except Exception as e:
            print('  write failed:', e)

    print('Done. Processed', count, 'images. Processed files are under static/processed')


if __name__ == '__main__':
    main()
