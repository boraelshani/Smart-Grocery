# 📦 Category Recovery Guide

## Overview

This guide explains how to recover deleted categories from MongoDB and restore them to PostgreSQL.

---

## 🎯 What Happened

Categories were accidentally deleted from the PostgreSQL database, but they still exist in MongoDB. We need to:
1. Fetch categories from MongoDB
2. Transform them to match PostgreSQL structure
3. Insert/update them in PostgreSQL
4. **Exclude the `icon` field** (as requested)

---

## 📋 Prerequisites

### Required Environment Variables

Make sure your `.env` file contains:

```env
# MongoDB Connection
MONGO_URI=mongodb://your-mongo-connection-string

# PostgreSQL Connection
DATABASE_URL=postgresql://your-postgres-connection-string
# OR
SQLALCHEMY_DATABASE_URI=postgresql://your-postgres-connection-string
```

### Required Python Packages

```bash
pip install pymongo psycopg2-binary python-dotenv certifi
```

---

## 🔍 Step 1: List Available Categories

First, see what categories exist in MongoDB:

```bash
python scripts/list_mongo_categories.py
```

**This will show:**
- All categories grouped by level
- Category names (English and German)
- Slugs
- Which categories have images
- Which categories have icons
- Parent-child relationships
- Statistics

**Example output:**
```
📁 Level 1 (15 categories):
  • Beverages / Getränke (beverages) [🖼️, icon:bi-cup-straw]
  • Dairy / Milchprodukte (dairy) [🖼️, icon:bi-egg]
  • Fruits & Vegetables / Obst & Gemüse (fruits-vegetables) [🖼️]
  ...

📊 Statistics:
  • Total categories: 45
  • Levels: 1, 2, 3
  • With images: 38
  • With icons: 15
  • With parent: 30
```

---

## 🔄 Step 2: Recover Categories

Once you've verified the categories exist in MongoDB, run the recovery script:

```bash
python scripts/recover_categories_from_mongo.py
```

**This script will:**
1. ✅ Connect to MongoDB and PostgreSQL
2. ✅ Fetch all categories from MongoDB
3. ✅ Process and deduplicate categories
4. ✅ **Exclude the `icon` field** (as requested)
5. ✅ Insert/update categories in PostgreSQL
6. ✅ Show before/after counts
7. ✅ Display sample of recovered categories

**Example output:**
```
📡 Connecting to MongoDB...
✅ MongoDB connection successful

📡 Connecting to PostgreSQL...
✅ PostgreSQL connection successful

📥 Fetching categories from MongoDB...
✅ Found 45 categories in MongoDB

🔄 Processing categories...
  • Beverages (beverages)
  • Dairy (dairy)
  • Fruits & Vegetables (fruits-vegetables)
  ...

🔍 Deduplicating categories...
✅ Deduplicated to 45 unique categories

📊 Checking current PostgreSQL categories...
   Current categories in PostgreSQL: 12

💾 Inserting/Updating categories in PostgreSQL...
✅ Categories inserted/updated successfully

✅ Verifying results...
   Categories in PostgreSQL after recovery: 45
   Categories added/updated: 33

📋 Sample of categories in PostgreSQL:
   🖼️ Level 1: Beverages (beverages)
   🖼️ Level 1: Dairy (dairy)
   🖼️ Level 1: Fruits & Vegetables (fruits-vegetables)
   ...

✅ CATEGORY RECOVERY COMPLETE!
  Total categories in PostgreSQL: 45
  Categories recovered: 33
  Note: The 'icon' field was excluded as requested.
```

---

## 📊 PostgreSQL Category Structure

The categories are stored in PostgreSQL with this structure:

```sql
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    slug TEXT UNIQUE,
    name_en TEXT,
    name_de TEXT,
    parent_id INTEGER REFERENCES categories(id),
    level INTEGER,
    -- icon TEXT,  -- EXCLUDED as requested
    image_url TEXT
);
```

**Fields:**
- `id`: Auto-incrementing primary key
- `slug`: Unique identifier (e.g., "fruits-vegetables")
- `name_en`: English name
- `name_de`: German name
- `parent_id`: Reference to parent category (for hierarchical structure)
- `level`: Category level (1 = top level, 2 = subcategory, etc.)
- `image_url`: URL to category image
- ~~`icon`~~: **EXCLUDED** (not copied from MongoDB)

---

## 🔧 How It Works

### Data Transformation

The script transforms MongoDB categories to PostgreSQL format:

**MongoDB Format:**
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "name": "Beverages",
  "name_en": "Beverages",
  "name_de": "Getränke",
  "slug": "beverages",
  "level": 1,
  "icon": "bi-cup-straw",  // ← EXCLUDED
  "image_url": "https://example.com/beverages.jpg",
  "parent_id": null
}
```

**PostgreSQL Format:**
```sql
INSERT INTO categories (slug, name_en, name_de, parent_id, level, image_url)
VALUES ('beverages', 'Beverages', 'Getränke', NULL, 1, 'https://example.com/beverages.jpg');
```

### Conflict Handling

The script uses `ON CONFLICT` to handle existing categories:

```sql
ON CONFLICT (slug) DO UPDATE SET 
    name_en = EXCLUDED.name_en,
    name_de = EXCLUDED.name_de,
    parent_id = COALESCE(EXCLUDED.parent_id, categories.parent_id),
    level = EXCLUDED.level,
    image_url = COALESCE(EXCLUDED.image_url, categories.image_url)
```

This means:
- If category exists: **Update** it with MongoDB data
- If category doesn't exist: **Insert** it
- Preserve existing data if MongoDB data is empty

---

## ⚠️ Important Notes

### 1. Icon Field Excluded
As requested, the `icon` field from MongoDB is **NOT** copied to PostgreSQL. If you need icons later, you'll need to add them manually or modify the script.

### 2. Parent-Child Relationships
The script preserves parent-child relationships. Make sure parent categories are inserted before child categories (the script handles this automatically).

### 3. Slug Uniqueness
Slugs must be unique. The script deduplicates categories by slug, keeping the one with the most data.

### 4. Safe Operation
The script uses `ON CONFLICT DO UPDATE`, so it's safe to run multiple times. It won't create duplicates.

---

## 🧪 Testing

After recovery, verify the categories:

```sql
-- Check total count
SELECT COUNT(*) FROM categories;

-- View all categories
SELECT id, slug, name_en, level, image_url 
FROM categories 
ORDER BY level, name_en;

-- Check hierarchy
SELECT 
    c1.name_en as parent,
    c2.name_en as child
FROM categories c1
JOIN categories c2 ON c2.parent_id = c1.id
ORDER BY c1.name_en, c2.name_en;

-- Find categories without images
SELECT slug, name_en 
FROM categories 
WHERE image_url IS NULL OR image_url = '';
```

---

## 🐛 Troubleshooting

### MongoDB Connection Failed

**Error:** `pymongo.errors.ServerSelectionTimeoutError`

**Solutions:**
1. Check `MONGO_URI` in `.env` file
2. Ensure MongoDB server is running
3. Check network connectivity
4. Verify credentials

### PostgreSQL Connection Failed

**Error:** `psycopg2.OperationalError`

**Solutions:**
1. Check `DATABASE_URL` in `.env` file
2. Ensure PostgreSQL server is running
3. Verify credentials
4. Check if database exists

### No Categories Found

**Error:** `No categories found in MongoDB`

**Solutions:**
1. Check if MongoDB has data: `db.categories.count()`
2. Try extracting from products (script does this automatically)
3. Verify you're connected to the correct database

### Duplicate Slug Error

**Error:** `duplicate key value violates unique constraint`

**Solutions:**
1. The script handles this with `ON CONFLICT`
2. If error persists, check for manual duplicates in PostgreSQL
3. Run: `SELECT slug, COUNT(*) FROM categories GROUP BY slug HAVING COUNT(*) > 1;`

---

## 📚 Additional Scripts

### Backup MongoDB Categories

```bash
python scripts/backup_mongodb.py
```

This creates a JSON backup of all MongoDB data, including categories.

### Full Migration

If you need to migrate everything (not just categories):

```bash
python scripts/migrate_mongo_to_postgres.py
```

**Warning:** This migrates ALL data, not just categories.

---

## ✅ Success Checklist

After running the recovery script, verify:

- [ ] Script completed without errors
- [ ] Category count increased in PostgreSQL
- [ ] Sample categories display correctly
- [ ] Categories have proper names (English and German)
- [ ] Categories have slugs
- [ ] Categories have image URLs (where applicable)
- [ ] Icon field is NOT present in PostgreSQL
- [ ] Parent-child relationships preserved
- [ ] No duplicate slugs

---

## 🎉 Done!

Your categories should now be recovered from MongoDB and available in PostgreSQL!

If you encounter any issues, check the troubleshooting section or review the script output for specific error messages.

---

## 📞 Support

If you need help:
1. Check the script output for error messages
2. Review the troubleshooting section
3. Verify your environment variables
4. Check database connections
5. Review the PostgreSQL logs

---

**Last Updated:** 2024
**Scripts Location:** `/scripts/`
**Documentation:** This file
