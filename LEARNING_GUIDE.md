# Smart Grocery - Complete Learning Guide for Presentation

## Project Overview
**Smart Grocery** is a web application that helps users shop smarter by comparing prices across stores, viewing featured deals, managing shopping lists, and discovering special offers.

**Key Technologies:**
- Backend: Python (Flask framework)
- Database: MongoDB (Atlas cloud)
- Frontend: HTML, CSS, Bootstrap, JavaScript
- Authors: Bora Elshani, Dren Buqa

---

## Part 1: Architecture Overview (Start Here!)

### High-Level Flow
```
User Visit → Browser (HTML/CSS/JS)
              ↓
         Flask Server (app.py)
              ↓
         Routes (main_routes.py, auth_routes.py)
              ↓
         Models (users_model.py, products_model.py, etc.)
              ↓
         MongoDB Database
              ↓
         JSON Response ← back to Frontend
```

### Key Components
1. **app.py** - Main Flask application (entry point)
2. **routes/** - URL endpoints and business logic
3. **models/** - Database models and queries
4. **templates/** - HTML pages
5. **static/** - CSS, JavaScript, images
6. **utils/db.py** - Database connection

---

## Part 2: Step-by-Step Learning Path

### STEP 1: Start with `app.py` (The Entry Point)
**File:** `/app.py` (lines 1-50)

**What happens here:**
- Initializes the Flask app
- Loads environment variables from `.env` file (MongoDB connection URI, secret key)
- Sets up MongoDB connection using PyMongo
- Registers three blueprints (route groups)

**Key Lines:**
```python
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')  # Session secret
mongo.init_app(app)  # Connect Flask to MongoDB
```

**Context Processor (lines ~125):**
- Special function that makes `shopping_list_count` available in ALL templates
- Calculates how many unpurchased items are in user's shopping lists
- Used for the cart badge in navigation

**→ Next, understand how routes are registered**

---

### STEP 2: Route Registration (`routes/__init__.py`)
**File:** `/routes/__init__.py`

**What happens:**
- Creates two Blueprints: `main_bp` (primary features) and `auth_bp` (login/signup)
- Imports actual route handlers from `main_routes.py` and `auth_routes.py`

**Why Blueprints?**
- Organize related routes together
- `main_bp` = public features (home, compare prices, deals, stores, shopping list)
- `auth_bp` = authentication (login, signup, logout)

**→ Next, understand what routes do**

---

### STEP 3: Authentication Routes (`routes/auth_routes.py`)
**File:** `/routes/auth_routes.py` (lines 1-100)

**Key Routes:**

**POST /login**
```
User enters email & password
   ↓
Route calls users_model.authenticate()
   ↓
Password compared with database
   ↓
If valid: session['user'] = email
   ↓
Redirect to home page
```

**POST /signup**
```
User enters name, email, password
   ↓
Check if email already exists in database
   ↓
If new: create user with hashed password
   ↓
session['user'] = email
   ↓
Auto-redirect to home
```

**GET /logout**
```
Remove session['user']
   ↓
Redirect to login
```

**Import Chain:**
- `auth_routes.py` imports `users_model` (database operations)
- `users_model.authenticate()` checks password hash
- Uses `mongo` from `utils/db.py`

**→ Now see how main features work**

---

### STEP 4: Main Routes (`routes/main_routes.py`)
**File:** `/routes/main_routes.py` (1645 lines)

**This file contains ALL feature endpoints. Key ones:**

#### **GET /**  (Home Page)
```
User not logged in? → Show entry.html (login/signup prompts)
User logged in? → Show home.html with:
  - All stores
  - Featured products
  - Featured deals
  - User's personal shopping lists
```

**Data comes from:**
- `mongo.db.stores.find({})` - All store data
- `mongo.db.products.find({})` - All products
- `mongo.db.featured_deals.find({})` - Special deals

#### **GET /compare-prices** (Compare Products Across Stores)
```
Load all products with their prices at each store
   ↓
Show comparison table
   ↓
User can search and filter by category/store/price
```

#### **GET /stores** (Browse All Stores)
```
Fetch all stores with:
  - Name
  - Location (distance in miles)
  - Opening hours
   ↓
Show store cards
```

#### **GET /store/<store_name>** (Products in Specific Store)
```
Fetch only products from that store
   ↓
Display products grid
```

#### **GET /featured-deals** (Special Offers)
```
Query mongo.db.featured_deals
   ↓
Show limited-time offers
   ↓
User can claim deals
```

#### **POST /shopping-list/add** (Add Item to Shopping List)
```
User clicks "Add to Shopping List"
   ↓
Route receives: item name, price, store, etc.
   ↓
Find user's active shopping list
   ↓
Add item to items array
   ↓
Return { success: true, count: NEW_COUNT }
   ↓
Frontend updates badge with NEW_COUNT
```

**Important Detail:** When user adds item, the server returns the updated count, which the frontend uses to update the badge WITHOUT a page refresh.

#### **GET /shopping-list** (View Shopping List)
```
Fetch user's lists
   ↓
Render shopping_list.html with items
   ↓
Show total cost
   ↓
Can check off purchased items
```

---

### STEP 5: Database Models (`models/` folder)

#### **users_model.py**
```python
authenticate(email, password)
  → Check if password hash matches stored hash
  → Return True/False

get_user_by_email(email)
  → Find user in database
  → Return user document

get_user_lists(email)
  → Get all shopping lists for user
  → Return lists with items
```

#### **products_model.py**
```
get_product_by_name(name)
  → Search for product
  → Return product details with all store prices
```

#### **stores_model.py**
```
get_all_stores()
  → Fetch all stores from database
  → Return store names, locations, hours
```

#### **featured_deals_model.py**
```
get_featured_deals()
  → Fetch special offers
  → Return limited-time deals
```

#### **models.py**
```
Contains mock/default data if MongoDB not available
Useful for development/testing
```

---

### STEP 6: Database Connection (`utils/db.py`)
**File:** `/utils/db.py`

**Simple 2-line file:**
```python
from flask_pymongo import PyMongo
mongo = PyMongo()
```

**How it works:**
- `PyMongo()` creates MongoDB connector object
- In `app.py`: `mongo.init_app(app)` connects it to Flask
- In routes: `mongo.db` = MongoDB database connection
- All routes can now query like: `mongo.db.users.find({...})`

**Database Collections (Tables):**
- `users` - User accounts with hashed passwords
- `products` - All products with prices per store
- `stores` - Store information
- `featured_deals` - Special promotions
- `shopping_lists` - User shopping lists (embedded in users or separate)

---

## Part 3: Frontend/Template Flow

### STEP 7: HTML Templates (`templates/` folder)

**Page Flow:**
```
entry.html
  ↓ (User clicks Login/Signup)
login.html  ←→  signup.html
  ↓ (User authenticates)
home.html (displays after session created)
  ↓ (User clicks navigation links)
  ├→ compare_prices.html (Compare products)
  ├→ featured_deals.html (View deals)
  ├→ stores.html (Browse stores)
  ├→ store_products.html (Products in specific store)
  ├→ shopping_list.html (View shopping list)
  ├→ product_detail.html (Product details with comparison)
  ├→ product_info.html (Detailed product info)
  ├→ profile.html (User profile)
  └→ about.html (About page)
```

### Navigation Bar (shared across templates)
- All templates use the same navbar with:
  - Links to Home, Stores, Deals, Compare, Shopping List
  - **Cart Badge**: Shows count of unpurchased items (hidden when 0)
  - Profile link

### How Badge Works:
```
app.py context_processor creates shopping_list_count
   ↓
Every template can access {{ shopping_list_count }}
   ↓
Template renders: <span class="badge">{{ shopping_list_count }}</span>
   ↓
If count = 0: <span class="d-none">...</span> (hidden)
   ↓
When user adds item: JavaScript updates badge via API response
```

---

### STEP 8: Frontend JavaScript (`static/js/script.js`)

**Key Functions:**

#### **setupShoppingListHandlers()**
```
Listen for "Add to Shopping List" button clicks
   ↓
When clicked: AJAX POST to /shopping-list/add
   ↓
Server returns { success: true, count: 5 }
   ↓
Update DOM badge: document.getElementById('shopping-list-count').textContent = 5
   ↓
Show confirmation (no longer showing "Added!" toast per recent changes)
```

#### **setupProfileEditHandlers()**
```
Handle profile form submissions
   ↓
AJAX POST to profile update endpoint
```

#### **setupCompareHandlers()**
```
Client-side sorting of store prices
   ↓
Parse prices from product comparison table
   ↓
Sort by price (low to high)
   ↓
Re-render sorted list
```

---

## Part 4: Data Flow Examples

### Example 1: User Adds Item to Shopping List

**Frontend (User Action):**
```
User on home.html
  ↓
Clicks "Add to Shopping List" on a product card
  ↓
Button has data attributes:
  - data-name="Milk"
  - data-price="2.99"
  - data-store="Billa"
```

**JavaScript (static/js/script.js):**
```javascript
// Listen for click
document.addEventListener('click', (e) => {
  if (e.target.matches('.add-to-cart-btn')) {
    const name = e.target.dataset.name;
    const price = e.target.dataset.price;
    const store = e.target.dataset.store;
    
    // Send to backend
    fetch('/shopping-list/add', {
      method: 'POST',
      body: JSON.stringify({
        product_name: name,
        product_price: price,
        store_name: store
      })
    })
    .then(r => r.json())
    .then(data => {
      // Update badge with new count
      document.getElementById('shopping-list-count').textContent = data.count;
    });
  }
});
```

**Backend (routes/main_routes.py):**
```python
@main_bp.route('/shopping-list/add', methods=['POST'])
def add_item_to_active_list_api():
    email = session.get('user')
    if not email:
        return jsonify({'success': False}), 401
    
    # Parse JSON from frontend
    data = request.get_json()
    product_name = data.get('product_name')
    product_price = data.get('product_price')
    store_name = data.get('store_name')
    
    # Find or create user's active shopping list
    user = users_model.get_user_by_email(email)
    lists = user.get('shopping_lists', [])
    active_list = lists[0] if lists else None
    
    if active_list:
        # Add item to list
        active_list['items'].append({
            'name': product_name,
            'price': product_price,
            'store': store_name,
            'purchased': False
        })
        
        # Save back to database
        mongo.db.users.update_one(
            {'email': email},
            {'$set': {'shopping_lists': lists}}
        )
    
    # Count unpurchased items for badge
    total = sum(1 for item in active_list['items'] if not item.get('purchased'))
    
    return jsonify({
        'success': True,
        'count': total
    }), 200
```

**Result:**
- Item stored in MongoDB
- User sees badge update from 4 → 5
- No page refresh needed
- Data persists (next login shows item still there)

---

### Example 2: User Compares Prices

**Frontend:**
```
User on home.html
  ↓
Clicks "Compare Prices" button
  ↓
Navigates to GET /compare-prices
```

**Backend (routes/main_routes.py):**
```python
@main_bp.route('/compare-prices')
def compare_prices():
    # Get all products from all stores
    products = mongo.db.products.find({})
    
    # Group by product name
    grouped = {}
    for prod in products:
        name = prod['name']
        if name not in grouped:
            grouped[name] = {}
        store = prod['store']
        price = prod['price']
        grouped[name][store] = price
    
    return render_template('compare_prices.html', 
                         products=grouped)
```

**Template (compare_prices.html):**
```html
{% for product_name, stores in products.items() %}
  <div class="product-card">
    <h5>{{ product_name }}</h5>
    <table>
      {% for store, price in stores.items() %}
        <tr>
          <td>{{ store }}</td>
          <td>€{{ price }}</td>
        </tr>
      {% endfor %}
    </table>
  </div>
{% endfor %}
```

**Result:**
- User sees all products with prices at each store
- Can sort by price (via JavaScript)
- Can filter by category

---

## Part 5: Key Concepts to Explain in Presentation

### 1. Session Management
- User logs in → `session['user'] = email` stored on server
- Session cookie sent to browser
- On each request, Flask checks if session['user'] exists
- If not logged in → redirect to login page
- If logged in → user_email = session.get('user')

### 2. Database Schema (MongoDB Collections)

**users collection:**
```json
{
  "_id": ObjectId,
  "email": "user@example.com",
  "password": "hashed_password_here",
  "name": "John Doe",
  "shopping_lists": [
    {
      "id": "list1",
      "name": "Weekly Shopping",
      "items": [
        {
          "name": "Milk",
          "price": 2.99,
          "store": "Billa",
          "purchased": false
        }
      ]
    }
  ]
}
```

**products collection:**
```json
{
  "_id": ObjectId,
  "name": "Milk",
  "store": "Billa",
  "price": 2.99,
  "category": "Dairy",
  "image": "url_to_image"
}
```

### 3. AJAX (Real-time Updates Without Refresh)
- User clicks button → JavaScript sends AJAX request
- Server processes, returns JSON response
- JavaScript updates DOM (no page reload)
- Badge updates, notification shown, list refreshed

### 4. MVC Pattern
- **Model**: `users_model.py`, `products_model.py` (database)
- **View**: `templates/*.html` (HTML pages)
- **Controller**: `routes/main_routes.py`, `routes/auth_routes.py` (business logic)

---

## Part 6: Code Files Overview (Quick Reference)

| File | Purpose | Key Functions |
|------|---------|---|
| `app.py` | Flask entry point | Initialize app, load env vars, register blueprints |
| `routes/__init__.py` | Route registration | Create and import blueprints |
| `routes/auth_routes.py` | Authentication | `/login`, `/signup`, `/logout` |
| `routes/main_routes.py` | Features | `/`, `/compare-prices`, `/stores`, `/shopping-list/add` |
| `models/users_model.py` | User queries | `authenticate()`, `get_user_by_email()` |
| `models/products_model.py` | Product queries | Search, filter products |
| `models/stores_model.py` | Store queries | Get all stores, store details |
| `utils/db.py` | Database connection | PyMongo setup |
| `templates/*.html` | Pages | Render UI with Jinja templating |
| `static/js/script.js` | Frontend logic | AJAX handlers, DOM updates |
| `.env` | Configuration | MongoDB URI, secret key (NOT in git) |
| `requirements.txt` | Dependencies | Flask, PyMongo, Python packages |

---

## Part 7: Running the App (For Demo)

```bash
# 1. Activate virtual environment
source .venv/bin/activate  (Mac/Linux)
.\.venv\Scripts\Activate.ps1  (Windows)

# 2. Run Flask server
python app.py

# 3. Open in browser
http://localhost:5000/

# 4. Test flow:
# - Click "Sign Up" → Create account
# - Login with credentials
# - Browse products and add to shopping list
# - View shopping list
# - Compare prices across stores
```

---

## Part 8: Common Interview Questions & Answers

**Q: How does the shopping list persist across sessions?**
A: User data (including shopping lists) is stored in MongoDB. When user logs in, their email is stored in the session. On each request, the app fetches their shopping lists from the database using that email.

**Q: How are prices compared across stores?**
A: All products are stored with a "store" field. We group products by name and collect all store-price pairs, then display them in a comparison table.

**Q: How does the cart badge update without page refresh?**
A: When user adds item, JavaScript sends AJAX POST request. Server returns updated count in JSON response. JavaScript updates the badge DOM element directly.

**Q: Why use MongoDB instead of SQL?**
A: MongoDB is flexible (schema-less) - we can store variable product data. Easy document embedding (shopping lists inside user document).

**Q: How is password security handled?**
A: Passwords are hashed before storing in database. Login checks if entered password's hash matches stored hash (never stores plain text).

**Q: What's the difference between main_routes.py and auth_routes.py?**
A: `auth_routes.py` handles login/signup/logout. `main_routes.py` handles all features (only accessible if logged in).

---

## Quick Learning Checklist

Before presentation, make sure you understand:

- [ ] How Flask routes work (`@main_bp.route()`)
- [ ] How session authentication works (session['user'])
- [ ] How MongoDB queries work (mongo.db.collection.find())
- [ ] How Jinja templating works (`{{ variable }}`)
- [ ] How AJAX updates DOM without refresh
- [ ] The flow: User Action → JavaScript → Server Route → Database → Response → DOM Update
- [ ] Why we use blueprints (code organization)
- [ ] The three models: users, products, stores
- [ ] What a context processor does (available in all templates)
- [ ] How the shopping list badge updates

---

## Presentation Structure Suggestion

**5-10 Minute Overview:**

1. **Welcome slide** - Project name, authors, purpose
2. **Architecture diagram** - Flow from browser → Flask → MongoDB
3. **Key features demo** - Show working app (signup, browse, add to list, compare)
4. **Technical deep dive**:
   - Show `app.py` (entry point, MongoDB connection)
   - Show `routes/auth_routes.py` (authentication flow)
   - Show `routes/main_routes.py` (feature endpoints)
   - Show `models/users_model.py` (database queries)
   - Show `templates/home.html` (frontend rendering)
   - Show `static/js/script.js` (AJAX updates)
5. **Database schema** - Show example documents in MongoDB
6. **Live demo** - Walk through user flow
7. **Q&A** - Use this guide to answer questions

Good luck with your presentation! 🚀
