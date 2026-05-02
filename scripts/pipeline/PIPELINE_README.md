# Smart Grocery – Data Cleaning Pipeline

Automated pipeline that transforms raw heissepreise.io imports into a professional product catalog.

## Quick Start

```bash
# Full pipeline (all 4 steps)
python scripts/pipeline/orchestrator.py

# Preview mode (no database writes)
python scripts/pipeline/orchestrator.py --dry-run

# Run specific steps only
python scripts/pipeline/orchestrator.py --steps 1 2

# Daily update after import (price freshness + product matching only)
python scripts/pipeline/orchestrator.py --steps 3 4
```

## Pipeline Steps

### Step 1: Name Cleaning (`name_cleaner.py`)
- **What**: Strips store prefixes, extracts brands, normalizes units, formats professionally
- **Why**: Raw names contain "BILLA ", "SPAR Natur Pur " noise that makes searching difficult
- **Example**: `"SPAR Natur Pur Vollmilch 3.5% 1l"` → `"Vollmilch 3.5%"` (Brand: none, Size: "1 Liter")
- **Example**: `"Pringles Classic Paprika"` → `"Classic Paprika"` (Brand: "Pringles")
- **Run standalone**: `python scripts/pipeline/name_cleaner.py --dry-run --limit 20`

### Step 2: Categorisation (`categoriser.py`)
- **What**: Keyword-based category assignment with full hierarchical paths
- **Why**: Imported products have no category for website navigation and filtering
- **How**: 500+ bilingual keywords (DE/EN) mapped to 30+ subcategories across 11 departments
- **Confidence**: 0.9–1.0 auto-assign, 0.3–0.59 review queue, <0.3 uncategorized
- **Ambiguity detection**: If top 2 categories are close, confidence is reduced
- **Run standalone**: `python scripts/pipeline/categoriser.py --dry-run --limit 30`

### Step 3: Price Freshness (`price_freshness.py`)
- **What**: Flags stale prices, discovers missing URLs, marks unavailable products
- **Why**: Some prices are weeks old; BILLA/HOFER products need product-specific URLs
- **Detection**: Aggregation pipeline on price_history timestamps (fast, no N+1 queries)
- **URL Discovery**:
  - BILLA: Search shop.billa.at for product URLs
  - HOFER: Construct from roksh.at pattern
  - SPAR: Already has URLs from import
- **Run standalone**: `python scripts/pipeline/price_freshness.py --dry-run`

### Step 4: Product Matching (`product_matcher.py`)
- **What**: Cross-store product merging — groups same product from BILLA/SPAR/HOFER into one
- **Why**: Same product should have one entry with prices from all stores for comparison
- **Matching criteria (ALL must match)**:
  - Identical fingerprint (cleaned name + quantity + unit)
  - Prices within 2.5x of each other
  - From different stores
  - Brand-aware: same product, different brands = separate products
- **Conservative**: If ANY doubt, DO NOT match. Zero false positives.
- **Run standalone**: `python scripts/pipeline/product_matcher.py --dry-run`

## Integration with Daily Import

```bash
# 1. Import fresh data
python scripts/import_heissepreise.py

# 2. Run full pipeline
python scripts/pipeline/orchestrator.py

# Or just freshness + matching for daily updates
python scripts/pipeline/orchestrator.py --steps 3 4
```

## Category Structure

| Department | Subcategories |
|---|---|
| Dairy & Eggs | Milk, Cheese, Yogurt, Butter & Cream, Eggs |
| Fresh Produce | Fresh Fruits, Fresh Vegetables, Herbs & Spices |
| Meat & Fish | Poultry, Beef & Pork, Fish & Seafood, Deli & Cold Cuts |
| Bakery & Bread | Bread, Pastries & Cakes |
| Pantry & Staples | Pasta, Rice & Grains, Oils & Vinegars, Sauces, Spices, Canned |
| Beverages | Water, Soft Drinks, Juices, Beer, Wine & Spirits, Coffee & Tea |
| Snacks & Sweets | Chocolate, Candy & Gum, Chips & Snacks, Protein Bars |
| Frozen | Frozen Meals, Frozen Vegetables & Fruits, Ice Cream |
| Household | Cleaning, Paper & Disposables, Personal Care |
| Baby & Kids | Baby Food & Care |
| Pets | Pet Food |

## Configuration

| Module | Setting | Default |
|---|---|---|
| `price_freshness.py` | `MAX_STALE_DAYS` | 3 days |
| `price_freshness.py` | `MAX_MISSING_RUNS` | 2 imports |
| `product_matcher.py` | `MAX_PRICE_RATIO` | 2.5x |
| `categoriser.py` | confidence threshold (CLI) | 0.3 |

## Performance

| Step | Speed |
|---|---|
| Name cleaning | ~10K products/sec |
| Categorisation | ~20K products/sec |
| Price freshness | ~60K in 5 sec (aggregation) |
| Product matching | ~60K in 30 sec |
