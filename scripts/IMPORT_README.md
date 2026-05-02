# Heisse Preise Data Import

Downloads product data from [heisse-preise.io](https://heisse-preise.io) and imports it into the Smart Grocery MongoDB database for BILLA, SPAR, and HOFER.

## Quick Start

```bash
# 1. Ensure .env has MONGO_URI set
# 2. Run the import (downloads data + imports ~58K items):
.venv/bin/python3 scripts/import_heissepreise.py

# 3. Merge store data into products collection (~25 min):
.venv/bin/python3 scripts/merge_stores_to_products.py
```

## Files

| File | Purpose |
|---|---|
| `import_heissepreise.py` | Downloads data, transforms it, inserts into `store_products` and `price_history` collections |
| `merge_stores_to_products.py` | Merges store data from `store_products` into the `products` collection's `stores` array |

## How It Works

### Data Source
- Downloads `https://heisse-preise.io/data/latest-canonical.json` (275K+ items total)
- Filters to BILLA (19K), SPAR (33K), HOFER (6.5K) — ~58K items

### Product URLs
- **BILLA**: `https://shop.billa.at/p/{slug}` (from heissepreise `url` field)
- **SPAR**: Search URL fallback (heissepreise provides no direct URLs for SPAR)
- **HOFER**: `https://www.roksh.at/hofer/produkte/{slug}` (from heissepreise `url` field)

### Discount Detection
Compares current price vs. previous price in `priceHistory`. If the drop is >5%, marks as potential offer (`isOnOffer: true`).

### Product Matching
Products are matched across stores using a deterministic SHA-256 fingerprint of `normalized_name + quantity + unit`.

### Database Collections
| Collection | Purpose |
|---|---|
| `products` | Main catalog with embedded `stores` array |
| `store_products` | Normalized link table (product + store + price) |
| `price_history` | Historical price tracking (up to 10 entries per product) |

## Environment Variables

Set in `.env` file:
```
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/smart_grocery
DATABASE_NAME=smart_grocery
```

## Running the Import

```bash
# Navigate to project root
cd /path/to/Smart-Grocery

# Activate virtual environment
source .venv/bin/activate

# Step 1: Main import (~3 minutes)
python3 scripts/import_heissepreise.py

# Step 2: Merge stores into products (~25 minutes)
python3 scripts/merge_stores_to_products.py
```

Both scripts are **idempotent** — safe to run multiple times.

## Verification

```python
.venv/bin/python3 -c "
from utils.db import get_db
db = get_db()
print('Products:', db.products.count_documents({}))
print('Store products:', db.store_products.count_documents({}))
print('Price history:', db.price_history.count_documents({}))
"
```

## Notes

- **HOFER availability**: All HOFER items from heissepreise are currently marked `unavailable: true` because HOFER's data feed on heissepreise is historical-only. Items are imported for price history tracking.
- **Performance**: The import takes ~30 minutes total due to MongoDB Atlas network latency. Running locally with a nearby Atlas region speeds this up significantly.
- **Duplicates**: Some products exist in multiple variants (different sizes, packaging). The fingerprinting algorithm separates these correctly.
