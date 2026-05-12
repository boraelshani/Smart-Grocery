# Smart Grocery - Quick Start Guide

## ✅ System Status
**Database:** PostgreSQL (Neon) - Connected ✓  
**Server:** Flask Development Server - Running ✓  
**Port:** 5001  
**Data:** 32,890 products, 8 stores, 393 categories

---

## 🚀 Starting the Application

### Start the Server
```bash
python3 app.py
```

The server will start on: **http://localhost:5001**

### Stop the Server
Press `CTRL+C` in the terminal where the server is running.

---

## 🔍 Verify Everything is Working

### 1. Check Database Connection
```bash
curl http://localhost:5001/health
```
**Expected Response:**
```json
{
  "db": "connected",
  "status": "ok"
}
```

### 2. Check Database Details
```bash
curl http://localhost:5001/debug-db
```
**Expected Response:**
```json
{
  "category_count": 393,
  "database_name": "neondb",
  "database_user": "neondb_owner",
  "product_count": 32890,
  "status": "connected",
  "store_count": 8
}
```

### 3. Test Product Search
```bash
curl 'http://localhost:5001/api/search-products?q=milk'
```
Should return a JSON array of products matching "milk".

### 4. Open in Browser
Visit: **http://localhost:5001**

You should see:
- Products displayed on the home page
- Categories in the navigation menu
- Store information
- Search functionality working

---

## 📊 Database Information

### Connection Details
- **Type:** PostgreSQL (Neon Cloud)
- **Database:** neondb
- **User:** neondb_owner
- **Connection:** Configured via `DATABASE_URL` in `.env` file

### Data Summary
| Resource | Count |
|----------|-------|
| Products | 32,890 |
| Stores | 8 |
| Categories | 393 |
| Users | 35 |

### Sample Data
- **Product:** Erdbeerstrudel (Billa)
- **Store:** Billa, Spar, Hofer, etc.
- **Category:** Fruits & Vegetables, Dairy, Bakery, etc.

---

## 🛠️ Troubleshooting

### Server Won't Start
1. Check if port 5001 is already in use:
   ```bash
   lsof -ti:5001
   ```
2. If a process is using it, kill it:
   ```bash
   kill -9 $(lsof -ti:5001)
   ```
3. Restart the server:
   ```bash
   python3 app.py
   ```

### Database Connection Error
1. Verify `.env` file exists and contains `DATABASE_URL`
2. Check the connection:
   ```bash
   curl http://localhost:5001/debug-db
   ```
3. If you see architecture errors, reinstall psycopg2:
   ```bash
   python3 -m pip uninstall -y psycopg2-binary
   python3 -m pip install psycopg2-binary --no-cache-dir
   ```

### No Products Showing
1. Check database connection: `curl http://localhost:5001/health`
2. Verify data exists: `curl http://localhost:5001/debug-db`
3. Check server logs for errors
4. Clear browser cache and reload

---

## 📁 Important Files

### Configuration
- `.env` - Environment variables (DATABASE_URL, SECRET_KEY, etc.)
- `app.py` - Main Flask application
- `requirements.txt` - Python dependencies

### Database Models
- `models/postgres_models.py` - SQLAlchemy ORM models
- `models/products_model.py` - Product data access layer
- `models/stores_model.py` - Store data access layer

### Routes
- `routes/ui/public.py` - Home page and public routes
- `routes/api/common.py` - API endpoints
- `routes/admin/` - Admin panel routes

---

## 🔗 Useful Endpoints

### Public Pages
- **Home:** http://localhost:5001/
- **Compare Prices:** http://localhost:5001/compare-prices
- **Featured Deals:** http://localhost:5001/featured-deals
- **Recipe Planner:** http://localhost:5001/recipe-planner

### API Endpoints
- **Search Products:** `/api/search-products?q=<query>`
- **Get Product:** `/api/product?id=<product_id>`
- **List Stores:** `/api/stores`
- **List Categories:** `/api/categories`

### Admin/Debug
- **Health Check:** `/health`
- **Database Debug:** `/debug-db`
- **Admin Panel:** `/admin` (requires admin login)

---

## 📝 Notes

### Database Type
This application uses **PostgreSQL** (not MongoDB). All data is stored in a Neon PostgreSQL database.

### Development Mode
The server runs in debug mode by default. For production:
1. Set `DEBUG=False` in environment
2. Use a production WSGI server (gunicorn, uwsgi)
3. Configure proper security settings

### Data Migration
If you need to migrate data from MongoDB to PostgreSQL, use:
```bash
python3 scripts/migrate_mongo_to_postgres.py
```

---

**Last Updated:** May 10, 2026  
**Status:** ✅ Fully Operational
