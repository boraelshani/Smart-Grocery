# 🔄 COMPLETE DATA RECOVERY GUIDE

## ⚠️ IMPORTANT WARNING

This script will **DELETE ALL EXISTING DATA** from PostgreSQL and perform a fresh migration from MongoDB.

**Use this when:**
- Data in PostgreSQL is corrupted or incomplete
- Parent-child relationships are broken
- You need a clean slate with all MongoDB data

---

## 🚀 Quick Start

### Run the Complete Recovery

```bash
python scripts/full_data_recovery.py
```

**The script will:**
1. Give you 5 seconds to cancel (Ctrl+C)
2. Clear ALL existing PostgreSQL data
3. Migrate everything from MongoDB in the correct order
4. Show detailed progress and results

---

## 📋 What Gets Migrated

### 1. Categories ✅
- **Proper parent_id relationships**
- Level-by-level insertion (parents before children)
- MongoDB ObjectId → PostgreSQL integer mapping
- Slug-based fallback resolution

### 2. Stores ✅
- Store information
- Logos and websites
- Active status

### 3. Products ✅
- Product details
- **Proper category_id linking**
- Brand information
- Images and barcodes

### 4. Offers ✅
- Price information
- Store-product relationships
- Availability status

### 5. Featured Deals ✅
- Deal information
- **Valid category_slug references**
- Discount percentages

---

## 🔧 How It Works

### Step 1: Clear PostgreSQL Data

```sql
TRUNCATE TABLE price_history CASCADE;
TRUNCATE TABLE offers CASCADE;
TRUNCATE TABLE products CASCADE;
TRUNCATE TABLE categories CASCADE;
TRUNCATE TABLE stores CASCADE;
-- ... and all other tables
```

### Step 2: Migrate Categories (PROPERLY!)

The script handles parent_id relationships correctly:

```python
# 1. Fetch all categories from MongoDB
# 2. Group by level (1, 2, 3, etc.)
# 3. Insert level by level:
#    - Level 1 (root categories) first
#    - Level 2 (children of level 1) second
#    - Level 3 (children of level 2) third
#    - etc.
# 4. Build mapping: MongoDB _id → PostgreSQL id
# 5. Resolve parent_id references using the mapping
```

**Example:**
```
MongoDB:
  {_id: "abc123", name: "Food", level: 1}
  {_id: "def456", name: "Dairy", level: 2, parent_id: "abc123"}

PostgreSQL:
  INSERT INTO categories (slug, name_en, level, parent_id)
  VALUES ('food', 'Food', 1, NULL);  -- Returns id=1
  
  INSERT INTO categories (slug, name_en, level, parent_id)
  VALUES ('dairy', 'Dairy', 2, 1);  -- parent_id=1 (Food's id)
```

### Step 3: Migrate Stores

Simple store information migration.

### Step 4: Migrate Products

Products are linked to categories using the mapping:

```python
# Resolve category_id:
# 1. Try MongoDB ObjectId → PostgreSQL id
# 2. Try slug → PostgreSQL id
# 3. Try name matching
```

### Step 5: Migrate Offers

Offers are linked to products using fingerprint mapping.

### Step 6: Migrate Featured Deals

Deals are linked to categories using slug validation.

---

## 📊 Expected Output

```
======================================================================
  COMPLETE DATA RECOVERY: MONGODB → POSTGRESQL
======================================================================

⚠️  WARNING: This will DELETE all existing PostgreSQL data!
   Press Ctrl+C within 5 seconds to cancel...

   Starting in 5...
   Starting in 4...
   Starting in 3...
   Starting in 2...
   Starting in 1...

🚀 Starting migration...

📡 Connecting to MongoDB...
✅ MongoDB connected

📡 Connecting to PostgreSQL...
✅ PostgreSQL connected

🗑️  CLEARING EXISTING POSTGRESQL DATA...
  ✅ Cleared price_history
  ✅ Cleared offers
  ✅ Cleared products
  ✅ Cleared categories
  ✅ Cleared stores
  ...
✅ All data cleared

======================================================================
  MIGRATING CATEGORIES (WITH PROPER PARENT_ID)
======================================================================
📥 Found 45 categories in MongoDB

🔄 Inserting categories by level...

📁 Level 1: 15 categories
  ✅ Food (food)
  ✅ Beverages (beverages)
  ✅ Household (household)
  ...

📁 Level 2: 25 categories
  ✅ Dairy (dairy) (parent: 1)
  ✅ Meat (meat) (parent: 1)
  ✅ Soft Drinks (soft-drinks) (parent: 2)
  ...

📁 Level 3: 5 categories
  ✅ Milk (milk) (parent: 15)
  ✅ Cheese (cheese) (parent: 15)
  ...

✅ Migrated 45 categories

======================================================================
  MIGRATING STORES
======================================================================
📥 Found 8 stores in MongoDB

  ✅ Billa (billa)
  ✅ Spar (spar)
  ✅ Hofer (hofer)
  ...

✅ Migrated 8 stores

======================================================================
  MIGRATING PRODUCTS
======================================================================
📥 Found 1250 products in MongoDB

  ...processed 500/1250 products
  ...processed 1000/1250 products
  ...processed 1250/1250 products

✅ Migrated 1250 products

======================================================================
  MIGRATING OFFERS
======================================================================
  ...processed 500 offers
  ...processed 1000 offers
  ...processed 1500 offers

✅ Migrated 1500 offers

======================================================================
  MIGRATING FEATURED DEALS
======================================================================
  ✅ Special Milk Deal
  ✅ Cheese Discount
  ...

✅ Migrated 24 featured deals

======================================================================
  ✅ COMPLETE MIGRATION FINISHED!
======================================================================

📊 Final Summary:
  • Categories: 45 (Root: 15, Children: 30)
  • Stores: 8
  • Products: 1250
  • Offers: 1500
  • Featured Deals: 24

📁 Category Hierarchy Sample:
  • Food → Dairy (Level 2)
  • Food → Meat (Level 2)
  • Beverages → Soft Drinks (Level 2)
  • Dairy → Milk (Level 3)
  • Dairy → Cheese (Level 3)
  ...

📦 Products with Categories Sample:
  • Milch 1L → Milk
  • Gouda Käse 200g → Cheese
  • Coca Cola 1.5L → Soft Drinks
  ...

======================================================================
  🎉 ALL DATA SUCCESSFULLY MIGRATED!
======================================================================
```

---

## ✅ Verification

After migration, verify the data:

### Check Categories

```sql
-- Total categories
SELECT COUNT(*) FROM categories;

-- Root categories (no parent)
SELECT name_en, slug, level 
FROM categories 
WHERE parent_id IS NULL 
ORDER BY name_en;

-- Child categories (with parent)
SELECT 
    c1.name_en as parent,
    c2.name_en as child,
    c2.level
FROM categories c1
JOIN categories c2 ON c2.parent_id = c1.id
ORDER BY c1.name_en, c2.name_en;

-- Categories by level
SELECT level, COUNT(*) 
FROM categories 
GROUP BY level 
ORDER BY level;
```

### Check Products

```sql
-- Products with categories
SELECT 
    p.name_de,
    c.name_en as category
FROM products p
LEFT JOIN categories c ON p.category_id = c.id
LIMIT 10;

-- Products without categories
SELECT COUNT(*) 
FROM products 
WHERE category_id IS NULL;
```

### Check Offers

```sql
-- Offers per store
SELECT store_id, COUNT(*) 
FROM offers 
GROUP BY store_id 
ORDER BY COUNT(*) DESC;

-- Products with offers
SELECT 
    p.name_de,
    COUNT(o.id) as offer_count
FROM products p
LEFT JOIN offers o ON o.product_id = p.id
GROUP BY p.id, p.name_de
ORDER BY offer_count DESC
LIMIT 10;
```

---

## 🐛 Troubleshooting

### MongoDB Connection Failed

**Error:** `pymongo.errors.ServerSelectionTimeoutError`

**Solutions:**
1. Check `MONGO_URI` in `.env`
2. Ensure MongoDB is running
3. Check network/firewall
4. Verify credentials

### PostgreSQL Connection Failed

**Error:** `psycopg2.OperationalError`

**Solutions:**
1. Check `DATABASE_URL` in `.env`
2. Ensure PostgreSQL is running
3. Verify credentials
4. Check if database exists

### Parent_id Still Wrong

**Check:**
```sql
-- Find orphaned categories (parent_id points to non-existent category)
SELECT c.name_en, c.parent_id
FROM categories c
LEFT JOIN categories p ON c.parent_id = p.id
WHERE c.parent_id IS NOT NULL AND p.id IS NULL;
```

**If found:** The MongoDB data itself may have invalid parent_id references.

### Categories Missing

**Check MongoDB:**
```javascript
// In MongoDB shell
db.categories.count()
db.categories.find().limit(5)
```

**If empty:** Categories may be embedded in products. The script handles this automatically.

---

## 🔒 Safety Features

### 5-Second Countdown
You have 5 seconds to cancel before data deletion starts.

### Transaction Safety
PostgreSQL operations use autocommit, but you can modify the script to use transactions.

### Conflict Handling
Uses `ON CONFLICT` clauses to handle duplicates gracefully.

### Error Reporting
Detailed error messages with stack traces.

---

## 📝 Requirements

### Environment Variables

```env
MONGO_URI=mongodb://your-connection-string
DATABASE_URL=postgresql://your-connection-string
```

### Python Packages

```bash
pip install pymongo psycopg2-binary python-dotenv certifi python-dateutil
```

---

## ⚡ Performance

- **Categories:** ~1 second per 100 categories
- **Products:** ~5 seconds per 1000 products
- **Offers:** ~3 seconds per 1000 offers
- **Total:** ~2-5 minutes for typical dataset

---

## 🎯 Key Improvements

### vs. Previous Scripts

1. ✅ **Proper parent_id handling** - Level-by-level insertion
2. ✅ **Complete data migration** - Not just categories
3. ✅ **Clean slate** - Clears existing data first
4. ✅ **Better mapping** - MongoDB ObjectId → PostgreSQL id
5. ✅ **Verification** - Shows hierarchy and relationships
6. ✅ **Progress tracking** - Detailed output at each step

---

## 🚨 Important Notes

1. **Backup First:** Always backup your PostgreSQL database before running this script
2. **Downtime:** Your application will have no data during migration
3. **Users:** User data is NOT migrated (add if needed)
4. **Testing:** Test on a development database first
5. **Monitoring:** Watch the output for any errors

---

## 🎉 Success!

After successful migration, you should have:
- ✅ All categories with proper parent_id relationships
- ✅ All stores
- ✅ All products linked to categories
- ✅ All offers linked to products and stores
- ✅ All featured deals with valid category references

**Your data is now clean and properly structured!** 🎊
