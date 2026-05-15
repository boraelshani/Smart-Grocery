# 📦 Category Recovery - Quick Start

## Problem
Categories were accidentally deleted from PostgreSQL, but they still exist in MongoDB.

## Solution
Two Python scripts to recover categories from MongoDB to PostgreSQL.

---

## 🚀 Quick Start

### Step 1: List Categories (Optional)
See what's available in MongoDB:
```bash
python scripts/list_mongo_categories.py
```

### Step 2: Recover Categories
Restore categories to PostgreSQL:
```bash
python scripts/recover_categories_from_mongo.py
```

**That's it!** ✅

---

## 📋 What the Script Does

1. ✅ Connects to MongoDB and PostgreSQL
2. ✅ Fetches all categories from MongoDB
3. ✅ Transforms data to PostgreSQL format
4. ✅ **Excludes the `icon` field** (as requested)
5. ✅ Inserts/updates categories in PostgreSQL
6. ✅ Shows before/after counts

---

## 📊 Expected Output

```
📡 Connecting to MongoDB...
✅ MongoDB connection successful

📡 Connecting to PostgreSQL...
✅ PostgreSQL connection successful

📥 Fetching categories from MongoDB...
✅ Found 45 categories in MongoDB

💾 Inserting/Updating categories in PostgreSQL...
✅ Categories inserted/updated successfully

✅ CATEGORY RECOVERY COMPLETE!
  Total categories in PostgreSQL: 45
  Categories recovered: 33
  Note: The 'icon' field was excluded as requested.
```

---

## 🔧 Requirements

### Environment Variables (.env file)
```env
MONGO_URI=mongodb://your-mongo-connection-string
DATABASE_URL=postgresql://your-postgres-connection-string
```

### Python Packages
```bash
pip install pymongo psycopg2-binary python-dotenv certifi
```

---

## 📁 Files Created

1. **`scripts/list_mongo_categories.py`**
   - Lists all categories in MongoDB
   - Read-only, safe to run
   - Shows statistics and structure

2. **`scripts/recover_categories_from_mongo.py`**
   - Recovers categories from MongoDB to PostgreSQL
   - Excludes `icon` field
   - Safe to run multiple times (uses ON CONFLICT)

3. **`CATEGORY_RECOVERY_GUIDE.md`**
   - Detailed documentation
   - Troubleshooting guide
   - SQL examples

---

## ⚠️ Important Notes

- **Icon field is excluded** from recovery (as requested)
- **Safe to run multiple times** - won't create duplicates
- **Preserves existing data** - only updates what's needed
- **Parent-child relationships** are maintained

---

## 🧪 Verify Recovery

After running the script, check PostgreSQL:

```sql
-- Check total count
SELECT COUNT(*) FROM categories;

-- View all categories
SELECT slug, name_en, level, image_url 
FROM categories 
ORDER BY level, name_en;
```

---

## 🐛 Troubleshooting

### MongoDB Connection Failed
- Check `MONGO_URI` in `.env` file
- Ensure MongoDB server is running

### PostgreSQL Connection Failed
- Check `DATABASE_URL` in `.env` file
- Ensure PostgreSQL server is running

### No Categories Found
- Script will try to extract from products automatically
- Check MongoDB has data: `db.categories.count()`

---

## ✅ Success Checklist

- [ ] Script completed without errors
- [ ] Category count increased in PostgreSQL
- [ ] Categories have proper names
- [ ] Icon field is NOT in PostgreSQL
- [ ] No duplicate slugs

---

## 📚 Full Documentation

For detailed information, see: **`CATEGORY_RECOVERY_GUIDE.md`**

---

**Ready to recover your categories?** Run the scripts above! 🚀
