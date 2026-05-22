"""Simple smoke tests using Flask test client.
Safe, read-only requests only; does not modify DB.
"""
import sys
import os
from pathlib import Path

# Ensure project root is on sys.path so imports like `app` resolve when running from scripts/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app

ENDPOINTS = [
    '/',
    '/scanner',
    '/api/categories',
    '/api/stores',
    '/api/get-lists',
]


def run():
    with app.test_client() as c:
        results = []
        for ep in ENDPOINTS:
            try:
                resp = c.get(ep)
                results.append((ep, resp.status_code, len(resp.get_data(as_text=True) or '')))
            except Exception as e:
                results.append((ep, 'ERROR', str(e)))

    print('SMOKE TEST RESULTS:')
    for r in results:
        print(r)


if __name__ == '__main__':
    run()
