# Smart Grocery - Project Overview & Code Guide

## 🎯 Project Purpose
A Flask-based web app helping users compare grocery prices across stores, find deals, and manage shopping lists.

---

## 📁 Project Structure

### **Root Level Files**
- **app.py** - Main Flask application entry point. Sets up Flask, MongoDB connection, registers blueprints (routes), handles middleware
- **requirements.txt** - Python dependencies (Flask, PyMongo, python-dotenv, etc.)
- **.env** - Environment variables (MONGO_URI, SECRET_KEY) - **NEVER commit this**
- **README.md** - Project documentation and setup instructions

### **Test/Check Scripts** (Temporary utilities)
- **check_products.py** - Utility to verify product data in database
- **check_prices.py** - Validates price data integrity
- **test_billa_api.py** - Tests Billa store API connection
- **test_prices.py** - Price comparison testing

---

## 🗂️ Core Directories

### **routes/** - API Routes & Page Handlers
Flask blueprints that handle HTTP requests. **Route files define what URLs do.**

- **main_routes.py** (1800+ lines) - PRIMARY ROUTES
  - `GET /` - Home page
  - `GET /stores` - Shows all stores
  - `GET /stores/<name>` - Products in specific store (store_products.html)
  - `GET /product-info/<id>` - Store product detail view
  - `GET /product-detail/<id>` - Compare prices page across stores
  - `GET /featured-deals` - Sales/deals listing
  - `GET /featured-deal/<id>` - Individual deal detail
  - `GET /compare` - Price comparison tool
  - `GET /shopping-list` - User's shopping list
  - `POST /api/toggle-favorite` - Add/remove favorite products
  - `POST /api/add-to-list` - Add items to shopping list

- **auth_routes.py** - Login/Signup handlers
  - `POST /register` - Create account
  - `POST /login` - User authentication
  - `GET /logout` - Clear session

- **admin_routes.py** - Admin functions (hidden from normal users)
  - Likely data import/export operations

### **models/** - Database Models
Python classes that interact with MongoDB. **Define data structure.**

- **models.py** - Base data models
- **products_model.py** - Product CRUD operations
  - `get_all_products()`, `get_product()`, `update_product()`
  - Manages product records in `products` collection
  
- **featured_deals_model.py** - Sales/deals management
  - Works with `featured_deals` collection
  - Handles multi-buy offers (e.g., "2+1")
  
- **stores_model.py** - Store information
  - `stores` collection - store names, hours, location
  
- **users_model.py** - User accounts & shopping lists
  - `users` collection - login, preferences, shopping lists
  
- **__init__.py** - Package initialization, imports

### **utils/** - Helper Functions & Utilities
Reusable functions used throughout the app. **Shared logic lives here.**

- **db.py** - MongoDB connection setup
  - Creates `mongo` object that all routes import
  - `get_db()` function returns database connection
  
- **helpers.py** - Common utility functions
  - String formatting, data transformations
  - Price calculations
  
- **__init__.py** - Package imports

### **templates/** - HTML Pages (Jinja2)
**Jinja2 templates** - HTML with Python logic. Flask renders these + data.

#### Main Pages:
- **home.html** - Landing page with feature overview, nav links
- **login.html** - Login form
- **signup.html** - Registration form
- **404.html**, **500.html** - Error pages

#### Feature Pages:
- **stores.html** - List all stores with hours/distance
- **store_products.html** - Products from one store (grid view, prices, favorites)
- **product_info.html** - Store product detail (large image, description, price, add to list)
- **compare_prices.html** - Compare product prices across multiple stores
- **featured_deals.html** - Sale items listing
- **featured_deal_detail.html** - Individual deal detail (with multi-buy indicators)
- **shopping_list.html** - User's list items, checkboxes, total cost
- **profile.html** - User profile & preferences
- **about.html** - App information

#### UI Components:
- All templates include Bootstrap 5.3 + Bootstrap Icons
- Navbar on every page (Home, Stores, Deals, Compare, Lists, Profile)
- Responsive grid layouts for mobile/tablet/desktop

### **static/** - Frontend Assets
**CSS, JavaScript, images** - What users' browsers download.

- **style.css** - Global styles (rarely used, most CSS inline in templates)
- **js/script.js** - Shared JavaScript functions
  - `addToShoppingList()` - Handle "Add to List" button clicks
  - Event listeners for cart, favorites
  
- **processed/** - Folder for processed images (background removal scripts)

### **data/** - JSON Data Files (Backup/Fallback)
**Local JSON copies** used if MongoDB is unavailable.

- **products.json** - All products (title, price, store, image URL)
- **featured_deals.json** - All sales/deals with offer info

### **scripts/** - Data Import/Processing Tools
**One-off scripts** for database maintenance. NOT part of running app.

- **seed_db.py** - Populate MongoDB from JSON files initially
- **seed_db_fixed.py** - Corrected version of seeding
- **import_all_data.py** - Import products/deals into database
- **import_featured_deals.py** - Import sales/deals specifically
- **import_all_data_fixed.py** - Improved import logic
- **expand_product_stores.py** - Add store info to products
- **remove_white_bg.py** - Process product images
- **backfill_shopping_list_images.py** - Add missing images
- **update_product_descriptions.py** - Bulk description updates
- **normalize_prices.py** - Fix price formatting
- **fix_product_paths.py**, **fix_product_paths_hierarchical.py** - Path corrections
- **check_db.py**, **check_db_fixed.py** - Database verification
- **test_list_db.py** - Test shopping list functionality

---

## 🔄 How the App Works (Request Flow)

### **User visits `/stores`:**
1. Browser sends `GET /stores` request
2. **main_routes.py** receives it in `stores_page()` function
3. Function calls `stores_model.get_all_stores()` to fetch from MongoDB
4. **models/stores_model.py** queries `db.stores` collection
5. Flask renders **templates/stores.html** with store data
6. Browser receives HTML + Bootstrap styling + JavaScript
7. User sees list of stores with hours, distance, "View Products" buttons

### **User clicks "View Products" for a store:**
1. Link goes to `/stores/Billa` (store name in URL)
2. **main_routes.py** `store_products()` function catches it
3. Gets products from that store: `db.products.find({'store_name': 'Billa'})`
4. Renders **store_products.html** with products in grid
5. User sees prices, favorite hearts, product images
6. Clicking product card navigates to `/product-info/<product_id>`

### **User clicks "Add to List":**
1. JavaScript `addToShoppingList()` captures button click
2. Sends `POST /api/add-to-list` with product data (name, price, image)
3. **auth_routes.py** or **main_routes.py** updates user's shopping list
4. Stores in `users` collection under their email
5. Shopping list total cost updates in real-time

### **User compares prices:**
1. Search for product name on `/compare`
2. **main_routes.py** `compare_prices()` searches `db.products` by name
3. Finds all versions of product from different stores
4. Renders **compare_prices.html** showing price from each store
5. User clicks "View Details" → goes to `/product-detail/<id>`
6. **product_detail.html** shows that store's version with full details

---

## 💾 Database (MongoDB)

### **Collections (Tables):**

**products**
```
{
  _id: ObjectId,
  id: "string",
  name: "Bananas",
  category: "Fruit",
  price: 2.50,
  store_price: 2.50,
  store_name: "Billa",
  image: "https://...",
  store_image: "https://...",
  description: "Fresh yellow bananas",
  unit: "per kg",
  url: "https://store.com/product"
}
```

**featured_deals**
```
{
  _id: ObjectId,
  title: "Blueberries 2+1",
  price: 3.99,
  original_price: 5.99,
  offer: "2+1",
  multibuy_buy: 2,
  multibuy_free: 1,
  image: "https://...",
  store: "Billa",
  description: "Buy 2 get 1 free"
}
```

**stores**
```
{
  _id: ObjectId,
  name: "Billa",
  hours: "8am-10pm",
  distance_miles: 2.5,
  address: "123 Main St"
}
```

**users**
```
{
  _id: ObjectId,
  email: "user@example.com",
  password_hash: "hashed_password",
  lists: [
    {
      items: [
        {name: "Bananas", price: 2.50, image: "...", purchased: false}
      ],
      total: 10.50
    }
  ]
}
```

---

## 🎨 Frontend Features

### **Styling:**
- Bootstrap 5.3 for responsive grid/components
- Bootstrap Icons for small icons (heart, cart, search, etc.)
- Custom CSS: purple gradient theme (#667eea → #764ba2)
- Glass-morphism effects on product cards

### **JavaScript Interactivity:**
- Toggle favorite hearts (POST to `/api/toggle-favorite`)
- Add items to shopping list (POST to `/api/add-to-list`)
- Search products on compare page
- Expand/collapse filters
- Keyboard navigation (Enter/Space on product cards)

### **Responsive Design:**
- Mobile: 1-2 columns
- Tablet: 3-4 columns  
- Desktop: 4+ columns
- Navbar collapses on mobile

---

## 🔑 Key Concepts

### **Favorite Products:**
- Stored in user's MongoDB document
- When user clicks heart → calls `/api/toggle-favorite`
- Next visit shows heart as filled for favorited items

### **Shopping List:**
- Per-user list stored in `users` collection
- Items persist across sessions (login required)
- Checkbox marks items purchased (soft delete, not removed)
- Total cost calculated client-side + server-side

### **Multi-Buy Offers (2+1, 3+2, etc.):**
- `featured_deals` has `offer` field: "2+1"
- Frontend calculates positions to highlight which items are free
- `multibuy_buy` & `multibuy_free` fields store the numbers

### **Product Lookup:**
- Query by `_id` (MongoDB ObjectId) for single products
- Query by `name` for search/compare
- Query by `store_name` to filter by store
- Use both `store_image` (store-specific) + `image` (generic fallback)

---

## 🚀 Running the App

```bash
# Install dependencies
pip install -r requirements.txt

# Set up .env with MONGO_URI and SECRET_KEY
echo "MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/smart_grocery" > .env

# Run Flask app
python app.py

# Visit http://localhost:5000
```

**Default login (if seeded):**
- Email: test@test.com
- Password: test

---

## ⚠️ Important Notes

1. **MongoDB Required:** App needs MongoDB running. Either:
   - Local: `mongod` running on `localhost:27017`
   - Atlas: Connection string in `.env`

2. **Images are URLs:** Products use external image URLs, not local files

3. **Prices in EUR:** All prices are euros (€)

4. **Multi-Buy Logic:** Complex math for "2+1" deals to show which items free

5. **Session-Based Auth:** Uses Flask sessions (cookie-based), not tokens

6. **No API Keys:** Doesn't use external APIs currently (some tests reference Billa API but not used)

---

## 📝 Quick Command Reference

```bash
# Check Python syntax
python -m py_compile models/products_model.py

# Test database connection
python check_products.py

# Seed database with JSON data
python scripts/seed_db.py

# Run server in debug mode
FLASK_ENV=development python app.py
```

---

## 🎯 Next Steps for Understanding

1. **Start with main_routes.py** - See what URLs exist and what they do
2. **Look at store_products.html** - See how products display on frontend
3. **Check products_model.py** - Understand how data is fetched
4. **Explore compare_prices.html** - See JavaScript interactivity
5. **Read shopping_list handling** - Understand how lists persist

Each template has inline comments explaining key sections!
