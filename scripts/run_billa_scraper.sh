#!/bin/bash
# Helper script to run the Billa scraper with smart update logic

echo "========================================================================"
echo "BILLA SCRAPER - Smart Update Mode"
echo "========================================================================"
echo ""
echo "This will:"
echo "  ✓ Add missing products (~2,609 products)"
echo "  ✓ Update prices/offers for products that changed"
echo "  ✓ Skip products that haven't changed (saves time!)"
echo "  ✓ Never replace or delete existing data"
echo ""
echo "Smart Logic:"
echo "  - New products → Full insert"
echo "  - Price changed → Update offer only"
echo "  - Nothing changed → Skip"
echo ""
echo "Expected duration: 2-3 hours"
echo "You can stop (Ctrl+C) and restart anytime - it will resume automatically"
echo ""
echo "========================================================================"
echo ""

# Change to script directory
cd "$(dirname "$0")/.."

# Run verification first
echo "Running pre-scrape verification..."
python3 scripts/verify_billa_data.py
echo ""
echo "========================================================================"
echo ""

read -p "Press Enter to start scraping, or Ctrl+C to cancel..."
echo ""

# Run the scraper
python3 scripts/billa_sitemap_to_postgres.py --workers 8 --chunk-size 300 --resume

# Run verification after
echo ""
echo "========================================================================"
echo "Scraping complete! Running post-scrape verification..."
echo "========================================================================"
echo ""
python3 scripts/verify_billa_data.py

echo ""
echo "========================================================================"
echo "NEXT STEPS"
echo "========================================================================"
echo ""
echo "For future updates, use the fast offer-only update:"
echo "  python3 scripts/billa_update_offers_only.py --workers 12"
echo ""
echo "This updates only prices/offers in 30-45 minutes (vs 2-3 hours)"
echo ""
