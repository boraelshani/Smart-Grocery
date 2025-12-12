# New Features: Notifications & Favorites Collection

## Overview
This update adds two key features to Smart Grocery:

1. **New Deal Notifications** - Users get toast notifications when new featured deals are added
2. **Normalized Favorites Collection** - Favorites moved from embedded `users.favorites` to dedicated `favorites` collection

---

## 1. New Deal Notifications

### How It Works
- Each user has a `seen_deals` field (array of deal IDs they've already viewed)
- When visiting Featured Deals page, the system compares current deals vs. seen deals
- New deals trigger toast notifications on page load
- After showing notifications, deals are marked as seen automatically

### Implementation Details

**Backend Changes:**
- `routes/auth_routes.py`: New users get `seen_deals: []` field
- `routes/main_routes.py`: 
  - Featured Deals route detects new deals and passes to template
  - New API endpoint `/api/mark-deals-seen` to record viewed deals
- `templates/featured_deals.html`: Client-side JS shows notifications and marks deals as seen

**User Experience:**
- Up to 3 individual deal notifications (staggered 1.5s apart)
- If more than 3 new deals, shows "+N more new deals" summary
- Notifications auto-dismiss after 5 seconds
- Deals marked as seen after 5 seconds (prevents re-notification on page refresh)

**API Endpoints:**
```
POST /api/mark-deals-seen
Body: { deal_ids: ["id1", "id2", ...] }
Response: { success: true, marked_count: N }
```

---

## 2. Favorites Collection

### Why Normalize?
Moving favorites from embedded arrays in `users` to a dedicated collection provides:
- Better query performance (indexed lookups)
- Richer metadata (timestamps, store-specific favorites)
- Scalability (no document size limits)
- Analytics capabilities (popular products, category trends)

### Schema
```javascript
{
  user_email: string,        // User who favorited
  product_id: string,         // Product reference
  product_name: string,       // Cached product name
  product_image: string,      // Cached image URL
  category: string,           // Product category
  added_at: datetime,         // When favorited
  store_id: string,           // Optional store filter
  best_price: mixed          // Cached best price
}
```

### Indexes
- `(user_email, product_id)` - unique compound index (fast lookup + prevents duplicates)
- `(user_email, added_at)` - chronological queries (recent favorites)
- `(category)` - category filtering

### Migration Script
**File:** `scripts/create_favorites_collection.py`

**Usage:**
```bash
# Preview changes (dry run)
python scripts/create_favorites_collection.py --dry-run

# Create collection and indexes only
python scripts/create_favorites_collection.py

# Create collection + migrate existing data from users.favorites
python scripts/create_favorites_collection.py --migrate-data

# Preview migration
python scripts/create_favorites_collection.py --migrate-data --dry-run
```

**What it does:**
1. Creates `favorites` collection (drops existing if confirmed)
2. Creates required indexes
3. Optionally migrates data from `users.favorites` to new collection
4. Preserves original data in `users` (manual cleanup needed)

**Post-Migration Cleanup (Optional):**
```javascript
// Remove old favorites field from users collection
db.users.update_many({}, {$unset: {"favorites": ""}})
```

### Code Changes

**New Model:** `models/favorites_model.py`
Provides clean API for favorites operations:
- `add_favorite(email, product_id, product_data)` - Add to favorites
- `remove_favorite(email, product_id)` - Remove from favorites
- `is_favorited(email, product_id)` - Check if favorited
- `get_user_favorites(email, category=None, limit=100)` - Get user's favorites
- `get_favorites_count(email)` - Count favorites
- `get_favorite_product_ids(email)` - Get list of favorited product IDs
- `clear_user_favorites(email)` - Remove all favorites

**Updated Endpoints:**
- `routes/main_routes.py`:
  - Home route uses `favorites_model.get_user_favorites()`
  - `/api/toggle-favorite` uses `favorites_model.add_favorite()` / `remove_favorite()`
  - `/api/check-favorite` uses `favorites_model.is_favorited()`

**Backward Compatibility:**
- Template normalization ensures old `users.favorites` format works with new model
- Home page maps new fields (`product_name` → `name`, `product_image` → `image`)

---

## Testing

### Test New Deal Notifications
1. Log in to app
2. Visit Featured Deals page
3. Should see notifications for all current deals (first visit)
4. Refresh page - no notifications (deals marked as seen)
5. Add a new deal to MongoDB `featured_deals` collection
6. Refresh Featured Deals page - see notification for new deal only

### Test Favorites Collection
1. Run migration script: `python scripts/create_favorites_collection.py --migrate-data`
2. Check MongoDB: `db.favorites.find({})`
3. Verify indexes: `db.favorites.getIndexes()`
4. Test UI: favorite/unfavorite products on product detail page
5. Check home page "Liked Products" section displays favorites correctly

---

## Deployment Checklist

- [ ] Backup MongoDB database before migration
- [ ] Run migration script on production: `python scripts/create_favorites_collection.py --migrate-data`
- [ ] Verify indexes created: Check MongoDB Atlas/Compass
- [ ] Test notifications: Visit Featured Deals as logged-in user
- [ ] Test favorites: Add/remove favorites, check home page
- [ ] Monitor for errors in application logs
- [ ] Optional: Clean up old `users.favorites` field after confirming stability

---

## Rollback Plan

If issues arise:

1. **Revert Code:** 
   ```bash
   git revert <commit-hash>
   ```

2. **Restore Old Favorites Logic:**
   - Favorites still exist in `users.favorites` (not deleted by migration)
   - Can manually revert `routes/main_routes.py` changes to use embedded favorites

3. **Drop New Collection:**
   ```javascript
   db.favorites.drop()
   ```

---

## Future Enhancements

### Notifications
- Add notification preferences (opt-in/out per category)
- Implement price drop alerts for favorited products (requires `price_history` collection)
- Add notification bell icon with dropdown/inbox
- Server-side notification generation on deal import

### Favorites
- Export/import favorites
- Favorites analytics dashboard (most favorited products/categories)
- Share favorites list with family/friends
- Store-specific favorites (e.g., "favorite at Walmart")
- Auto-suggest products based on favorites (collaborative filtering)

---

## Technical Notes

### Performance
- Favorites collection queries are O(1) lookup via compound index
- New deals detection is O(n) comparison but runs once per page load
- Notifications batch-marked (single DB write for multiple deal IDs)

### Database Size
- Each favorite ~200 bytes (small)
- 10,000 users × 50 favorites = ~10MB collection (negligible)
- seen_deals grows linearly with deal count; consider pruning old deals (>30 days)

### Error Handling
- All favorites operations fail gracefully (return False/empty list)
- Migration script has dry-run mode to preview changes
- New deal detection wrapped in try-catch (won't break page if fails)
