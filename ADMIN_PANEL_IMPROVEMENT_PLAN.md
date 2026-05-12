# Smart Grocery Admin Panel - Complete Improvement Plan

## Current State Analysis

### ✅ Existing Components
1. **Admin Layout** - Base template with sidebar, topbar, Tailwind CSS
2. **Dashboard** - Basic metrics (products, offers, stores, users)
3. **Products Page** - List view with basic filters
4. **Categories Page** - List view
5. **Brands Page** - List view
6. **Lists Page** - Shopping lists management
7. **Feedback Page** - User feedback management
8. **Import Routes** - Basic import functionality

### ❌ Missing/Incomplete Features
1. Dashboard - No price change graph, no quick actions
2. Products - No duplicate detection/merge, no inline edit, no bulk actions
3. Offers - Entire page missing
4. Categories - No tree view with drag-drop
5. Stores - Basic page exists but needs improvement
6. Price Import - Not fully automated, no live progress
7. User Management - Missing
8. Moderation - Missing
9. Analytics & Reports - Missing
10. Promotions - Missing
11. Community Price Reports - Missing
12. System Configuration - Missing
13. AI Categorization - Missing

## Implementation Priority

### Phase 1: Core Functionality (Week 1)
1. **Dashboard Improvements**
   - Add price change graph (Chart.js)
   - Add quick action buttons
   - Improve metrics cards
   - Add recent import logs

2. **Products Management - Complete Overhaul**
   - Hide IDs/timestamps from UI
   - Implement inline editing
   - Add bulk actions (category assign, brand update, delete)
   - **Critical: Duplicate detection & merge tool**
   - Product detail modal with offers list
   - Price history graph per product

3. **Offers Management - New Page**
   - Complete CRUD interface
   - Inline price editing
   - Stale offers detection
   - Bulk operations
   - Price history modal

### Phase 2: Automation & Import (Week 2)
4. **Price Import & Sync - Full Automation**
   - Live progress tracking
   - Import history
   - Scheduled imports (cron)
   - Data validation preview

5. **Categories Management - Enhanced**
   - Tree view with SortableJS
   - Drag-drop reordering
   - Bulk product assignment

### Phase 3: User & Content Management (Week 3)
6. **User Management - New Page**
   - User CRUD
   - Role management
   - Password reset
   - Block/unblock

7. **Moderation - New Page**
   - Public shopping lists
   - Public recipes
   - Soft delete functionality

8. **Stores Management - Enhanced**
   - Improved UI
   - Toggle flags
   - Logo management

### Phase 4: Analytics & Advanced Features (Week 4)
9. **Analytics & Reports - New Page**
   - Data quality report
   - Price drop alerts
   - CSV export

10. **Promotions & Discounts - New Page**
    - Promotion CRUD
    - Bulk import
    - Auto-expire job

11. **Community Price Reports - New Page**
    - Report verification
    - Offer creation from reports

12. **System Configuration - New Page**
    - Settings management
    - Cron configuration

13. **AI Categorization - New Feature**
    - Keyword mapping
    - OpenAI integration
    - Review queue

## Technical Architecture

### Database Schema Updates Needed

```sql
-- Add missing columns to products table
ALTER TABLE products ADD COLUMN IF NOT EXISTS suggested_category_id INTEGER;
ALTER TABLE products ADD COLUMN IF NOT EXISTS suggestion_confidence DECIMAL(3,2);
ALTER TABLE products ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;

-- Add system_config table
CREATE TABLE IF NOT EXISTS system_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT,
    value_type VARCHAR(50) DEFAULT 'string',
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add keyword_mapping table for AI categorization
CREATE TABLE IF NOT EXISTS keyword_mapping (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    confidence DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_products_active ON products(active);
CREATE INDEX IF NOT EXISTS idx_offers_last_seen ON offers(last_seen);
CREATE INDEX IF NOT EXISTS idx_offers_availability ON offers(is_available);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
```

### Core Principles Implementation

1. **Hide Internal IDs**
   - Use data attributes for IDs
   - Display user-friendly names
   - Copy button for support IDs

2. **Auto-managed Fields**
   - fingerprint: Recalculated on name/unit/size change
   - timestamps: Auto-updated by database
   - price_history: Managed by triggers

3. **Product Names**
   - Only name_de displayed/edited
   - No English product names

4. **Categories**
   - Both name_de and name_en
   - Only name_de editable
   - name_en from translation file

5. **Confirmations**
   - Modal for all destructive actions
   - Preview before bulk operations

6. **User Feedback**
   - Loading spinners
   - Toast notifications
   - Progress indicators

## File Structure

```
routes/admin/
├── __init__.py
├── dashboard.py (✅ exists, needs improvement)
├── products.py (✅ exists, needs major overhaul)
├── offers.py (❌ NEW)
├── categories.py (❌ NEW)
├── stores.py (❌ NEW)
├── import_routes.py (✅ exists, needs automation)
├── users.py (❌ NEW)
├── moderation.py (❌ NEW)
├── analytics.py (❌ NEW)
├── promotions.py (❌ NEW)
├── community_reports.py (❌ NEW)
├── system_config.py (❌ NEW)
├── ai_categorization.py (❌ NEW)
└── common.py (✅ exists, needs utilities)

templates/
├── admin_layout.html (✅ exists)
├── admin_dashboard.html (✅ exists, needs improvement)
├── admin_products.html (✅ exists, needs overhaul)
├── admin_offers.html (❌ NEW)
├── admin_categories.html (✅ exists, needs tree view)
├── admin_stores.html (❌ NEW)
├── admin_import.html (❌ NEW)
├── admin_users.html (❌ NEW)
├── admin_moderation.html (❌ NEW)
├── admin_analytics.html (❌ NEW)
├── admin_promotions.html (❌ NEW)
├── admin_community_reports.html (❌ NEW)
├── admin_system_config.html (❌ NEW)
└── admin_ai_categorization.html (❌ NEW)

static/admin/
├── js/
│   ├── dashboard.js (❌ NEW)
│   ├── products.js (❌ NEW)
│   ├── offers.js (❌ NEW)
│   ├── duplicate-merge.js (❌ NEW - CRITICAL)
│   ├── import-progress.js (❌ NEW)
│   └── common.js (❌ NEW)
└── css/
    └── admin-custom.css (❌ NEW)
```

## Key Features Detail

### 1. Duplicate Detection & Merge (CRITICAL)

**Algorithm:**
```python
# Find duplicates by fingerprint
duplicates_by_fingerprint = db.session.query(
    Product.fingerprint,
    func.count(Product.id).label('count')
).group_by(Product.fingerprint).having(func.count(Product.id) > 1).all()

# Find similar by name+size (trigram similarity)
# Use pg_trgm extension
similar_products = db.session.execute("""
    SELECT p1.id, p2.id, similarity(p1.name_de, p2.name_de) as sim
    FROM products p1, products p2
    WHERE p1.id < p2.id
    AND similarity(p1.name_de, p2.name_de) > 0.7
    AND p1.size_normalized = p2.size_normalized
    ORDER BY sim DESC
""").fetchall()
```

**Merge Process:**
1. Show group of duplicates
2. Admin selects canonical product
3. Preview: Show all offers that will be moved
4. Confirm
5. Execute:
   - Move all offers to canonical product
   - Update offer.product_id
   - Mark duplicates as inactive
   - Log merge action

### 2. Live Import Progress

**Implementation:**
```python
# Store progress in Redis or database
import_status = {
    'status': 'running',
    'current': 1000,
    'total': 58000,
    'message': 'Processing products...',
    'errors': []
}

# Frontend polls every 2 seconds
setInterval(() => {
    fetch('/admin/api/import-status')
        .then(r => r.json())
        .then(data => updateProgressBar(data));
}, 2000);
```

### 3. AI Categorization Workflow

**Step 1: Keyword Mapping**
```python
keyword_map = {
    'milch': category_id_for_milk,
    'brot': category_id_for_bread,
    # ... admin can edit this
}
```

**Step 2: OpenAI Fallback**
```python
prompt = f"""
Assign this product to one category:
Product: {product_name}
Categories: {', '.join(category_names)}
Return only the category name.
"""
```

**Step 3: Review Queue**
- Show suggested category
- Confidence score
- Accept/Reject buttons
- Accepted suggestions update keyword map

## Next Steps

1. Create database migrations
2. Implement Phase 1 (Dashboard + Products + Offers)
3. Add JavaScript for interactivity
4. Implement Phase 2 (Import automation)
5. Continue with remaining phases

## Estimated Timeline

- **Phase 1**: 5-7 days
- **Phase 2**: 3-4 days
- **Phase 3**: 4-5 days
- **Phase 4**: 5-6 days

**Total**: 3-4 weeks for complete implementation

## Testing Checklist

- [ ] All IDs hidden from UI
- [ ] Fingerprint auto-recalculated
- [ ] Duplicate merge works correctly
- [ ] Bulk operations work
- [ ] Import progress shows live
- [ ] Scheduled imports work
- [ ] AI categorization works
- [ ] All confirmations show
- [ ] All toasts work
- [ ] Dark/light mode works
- [ ] Mobile responsive
- [ ] Role permissions work
