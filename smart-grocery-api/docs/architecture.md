# Smart Grocery Production Architecture (MongoDB + Mongoose)

## 1) Collections and Domain Boundaries
- Catalog: stores, brands, categories, products
- Pricing: storeProducts, priceHistory
- User domain: users, lists, publicLists, feedback
- Automation: scraperRules, productMetrics

## 2) Data Flow
1. Admin creates or updates stores, brands, category tree, products, and store products.
2. Category path is auto-built and cached.
3. Scraper worker periodically updates storeProducts and writes deltas to priceHistory.
4. List totals are recalculated when affected prices change.
5. Labels are recomputed using product age, promo activity, and metrics.
6. Category explorer, product detail, and list reads are served through caching.

## 3) Required Scaling Tactics
- Use compound indexes for frequent aggregations.
- Keep catalog IDs as stable business IDs (storeId, productId).
- Keep ObjectId references for fast Mongo joins and future sharding flexibility.
- Precompute cheapest store projection in products to avoid repeated min calculations.
- Track productMetrics separately to prevent oversized product documents.
- Use Redis when available; fall back to in-memory cache in local mode.

## 4) Security and Stability
- Helmet + CORS + strict JSON limits.
- Global and route-level rate limits.
- Protected admin endpoints with admin JWT.
- Input validation with Joi and unknown-field stripping.
- Enforced scraper throttling plus timeout guards.

## 5) SEO and Structured Data
- Store multilingual names and descriptions as name_en/name_de fields.
- Keep category slugs stable and language-agnostic for canonical paths.
- Generate schema.org Product payload in frontend/API composition layer using:
  - product name and image
  - offers (price + currency + availability)
  - brand

## 6) Suggested Next-Phase Production Upgrades
- Move worker scheduling to a queue system (BullMQ / RabbitMQ).
- Add change streams for near-real-time list recalculation and notifications.
- Add OpenTelemetry tracing and per-route latency metrics.
- Add row-level audit logs for admin actions.
- Add integration tests with Mongo memory server.
