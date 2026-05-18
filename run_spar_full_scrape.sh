#!/bin/bash

# SPAR Full Scraper - Runs continuously to get all products
# This will scrape all 1178 pages and save unique products

echo "╔═══════════════════════════════════════════════════════════════════════════╗"
echo "║                    SPAR FULL SCRAPER                                      ║"
echo "║                    Target: 37,692 products                                ║"
echo "╚═══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Starting full scrape of all 1178 pages..."
echo "This will take approximately 1-2 hours"
echo ""
echo "Press Ctrl+C to stop at any time (progress will be saved)"
echo ""

cd "$(dirname "$0")"

# Run the scraper for all pages
python3 run_spar_playwright_scraper.py --max-pages 1178 --delay 0.5

echo ""
echo "╔═══════════════════════════════════════════════════════════════════════════╗"
echo "║                    SCRAPING COMPLETE                                      ║"
echo "╚═══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Check database for results:"
echo "python3 -c \"from app import app; from models.postgres_models import db, ProductStore; app.app_context().push(); print(f'SPAR products: {ProductStore.query.filter_by(store_id=\"spar\").count()}')\""
