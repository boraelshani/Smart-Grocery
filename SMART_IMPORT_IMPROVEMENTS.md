# Smart Import AI Feature - Comprehensive Improvements

## Overview
Major improvements to the Smart Import AI feature to fix extraction issues, add promotional pricing support, and enhance accuracy across all supported stores.

## Issues Fixed

### 1. **Hofer Product Name Extraction** ✅
**Problem**: Product names included unwanted prefix "Meine HOFER Produktempfehlung:"
- Example: "Meine HOFER Produktempfehlung: BACKBOX Butter" instead of "BACKBOX Butter"

**Solution**: Added regex pattern to remove Hofer-specific prefixes and store name suffixes
```python
# Remove "Meine HOFER Produktempfehlung:" prefix
title = re.sub(r'^Meine\s+HOFER\s+Produktempfehlung:\s*', '', title, flags=re.IGNORECASE)
# Remove store name suffixes
title = re.split(r'\s*\|\s*|\s*-\s*(?:BILLA|SPAR|HOFER|LIDL|MERKUR)', title, flags=re.IGNORECASE)[0].strip()
```

### 2. **Incorrect Price Extraction** ✅
**Problem**: Price showed 18.05 instead of 0.59 for Hofer products
- The scraper was extracting the wrong price from the page

**Solution**: Implemented multi-layered price extraction strategy:
1. Try OpenGraph meta tags first (`product:price:amount`)
2. Try JSON-LD structured data
3. Fallback to regex patterns with multiple formats:
   - `€1.49` or `€ 1.49`
   - `1,49 €` or `1.49€`
   - `Preis: €1.49`
   - `Statt: €2.49` (for old prices)

### 3. **Missing Promotional Pricing Support** ✅
**Problem**: No support for products on discount/sale
- Couldn't detect promotional prices
- No offer details (2+1 gratis, -30%, etc.)

**Solution**: Added comprehensive promotional pricing detection:
- **Promo Price Detection**: Searches for keywords like "Aktion", "Angebot", "Rabatt", "Reduziert"
- **Offer Details Extraction**: Detects patterns like:
  - `2+1 gratis` or `1+1 free`
  - `-50%` or `30% Rabatt`
  - `ab 2 Stück` (quantity discounts)
  - `Statt €2.99` (original price)
- **Automatic Discount Calculation**: If both regular and promo prices found, calculates discount percentage

## New Features

### 1. **Enhanced Form Fields**
Added new fields to the Smart Import UI:
- **Promo Price**: Separate field for promotional/discounted price
- **Size**: Product size (e.g., 500g, 1l)
- **Unit Price**: Calculated unit price (e.g., €1.99/kg)
- **Offer Details**: Promotional offer description (e.g., "2+1 gratis", "-30%")

### 2. **Database Schema Updates**
Extended the `offers` table with new columns:
```sql
ALTER TABLE offers 
ADD COLUMN base_price NUMERIC(10, 2),      -- Regular price
ADD COLUMN promo_price NUMERIC(10, 2),     -- Promotional price
ADD COLUMN unit_price TEXT,                -- Unit price string
ADD COLUMN offer_details TEXT;             -- Offer description
```

### 3. **Improved Price Logic**
- **Effective Price Method**: Returns promo price if available, otherwise base price
- **Smart Price Swapping**: Automatically swaps prices if promo is higher than regular (handles extraction errors)
- **Unit Price Calculation**: Automatically calculates unit prices based on product size

### 4. **Better Store Detection**
Enhanced store detection from URLs:
- Hofer: `hofer.at`
- Billa: `billa.at`
- Spar: `spar.at` or `interspar`
- Lidl: `lidl.at`
- Merkur: `merkur.at`

## Technical Improvements

### 1. **PostgreSQL Migration**
Converted `admin_save_ai_product` from MongoDB to PostgreSQL:
- Uses SQLAlchemy ORM properly
- Creates products, brands, stores, and offers
- Proper transaction handling with rollback on errors
- Auto-creates missing brands and stores

### 2. **Enhanced Scraping**
- **Playwright Fallback**: Uses Playwright for sites that block regular HTTP requests (403 errors)
- **Multiple Data Sources**: Tries OpenGraph, JSON-LD, and HTML parsing
- **Robust Regex Patterns**: Handles various price formats and languages

### 3. **Better Error Handling**
- Validates price formats before saving
- Provides clear error messages to users
- Graceful fallbacks when data is missing

## Testing Results

### Hofer Product Test
**URL**: `https://www.hofer.at/de/p.bbq-grillschalen-eckig--teilig.000000000000478567.html`

**Before**:
```json
{
  "name_de": "Meine HOFER Produktempfehlung: BBQ Grillschalen eckig, 10",
  "price": "18.05",
  "offer_details": ""
}
```

**After**:
```json
{
  "name_de": "BBQ Grillschalen eckig, 10-teilig",
  "price": "1.95",
  "size": "10stk",
  "unit_price": "€0.20/unit",
  "offer_details": "Angebot"
}
```

### Hofer Product with Brand Test
**URL**: `https://www.hofer.at/de/p.fair-hof-grill-burger.000000000000736117.html`

**Result**:
```json
{
  "name_de": "FAIR HOF Grill-Burger",
  "brand_raw": "Fair Hof",
  "price": "1.99",
  "size": "200g",
  "unit_price": "€1.00/100g",
  "offer_details": "aktion"
}
```

## Files Modified

### Backend
1. **`scripts/ai_product_fetcher.py`**
   - Improved title cleaning (remove prefixes/suffixes)
   - Enhanced price extraction with multiple strategies
   - Added promotional price detection
   - Better offer details extraction
   - Improved unit price calculation

2. **`routes/admin/common.py`**
   - Converted `admin_save_ai_product` to PostgreSQL
   - Added support for new fields (promo_price, size, unit_price, offer_details)
   - Proper transaction handling
   - Auto-create missing brands/stores

3. **`models/postgres_models.py`**
   - Extended `Offer` model with new fields
   - Added `effective_price()` method
   - Updated `to_dict()` to include new fields

### Frontend
4. **`templates/admin_smart_import.html`**
   - Added form fields for promo_price, size, unit_price, offer_details
   - Updated JavaScript to populate new fields
   - Better UI organization with labeled sections

### Database
5. **`migrations/add_offer_promo_fields.sql`**
   - Migration script to add new columns
   - Migrates existing data (price → base_price)
   - Adds indexes for performance

6. **`scripts/run_migration.py`**
   - Utility script to run SQL migrations
   - Lists available migrations

## Usage

### For Users
1. Navigate to **Admin Panel → AI Smart Import**
2. Paste a product URL from any supported store
3. Click **Extract with AI**
4. Review extracted data (now includes promotional pricing!)
5. Edit if needed and click **Save Product**

### For Developers
Run the migration to add new database fields:
```bash
python3 scripts/run_migration.py add_offer_promo_fields.sql
```

Or manually:
```bash
psql $DATABASE_URL < migrations/add_offer_promo_fields.sql
```

## Supported Stores

| Store | Status | Notes |
|-------|--------|-------|
| Hofer | ✅ Full | All features working |
| Billa | ✅ Full | All features working |
| Spar | ✅ Full | Uses Playwright for 403 bypass |
| Lidl | ⚠️ Partial | Limited data availability |
| Merkur | ✅ Full | All features working |

## Future Improvements

1. **AI-Powered Category Mapping**: Use ML to better map store categories to internal taxonomy
2. **Bulk Import**: Support importing multiple products at once
3. **Price History Tracking**: Automatically track price changes over time
4. **Image OCR**: Extract product info from images when URL scraping fails
5. **Multi-language Support**: Better handling of bilingual product names

## Summary

The Smart Import AI feature is now significantly more accurate and feature-rich:
- ✅ Correct product name extraction (no more prefixes)
- ✅ Accurate price detection
- ✅ Full promotional pricing support
- ✅ Better data extraction across all stores
- ✅ PostgreSQL integration
- ✅ Enhanced UI with more fields

---
**Date**: January 2025  
**Status**: ✅ Complete and Tested
