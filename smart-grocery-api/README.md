# Smart Grocery API (Mongoose Architecture)

A production-focused Node API module for your Smart Grocery platform.

## What this module contains
- MongoDB/Mongoose schemas for all requested entities.
- EN/DE localization helper.
- Scraper rules + auto-update workflow with price history.
- Product labels logic (new, popular, on_sale, trending).
- Unlimited user lists with auto-total recalculation and sharing.
- Category explorer filters and sort options.
- Suggestion engine for alternatives and deals.
- Caching layer (Redis or in-memory fallback).
- Admin endpoints for creating products/categories/stores from website.

## Quick start
1. Copy .env.example to .env and set credentials.
2. Run npm install
3. Run npm run dev

## API groups
- /api/products
- /api/categories
- /api/lists
- /api/public-lists
- /api/feedback
- /api/admin
- /api/scraper

## Key Files
- src/models/: all Mongoose models
- src/services/: domain logic (pricing, labels, suggestions, scraper)
- src/aggregations/pipelines.js: reusable aggregation builders
- docs/example-documents.json: sample documents for every collection
- docs/architecture.md: production architecture notes
