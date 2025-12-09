# Smart Grocery - Detailed Python Code Explanation

## Table of Contents
1. **app.py** - Application Initialization & Setup
2. **auth_routes.py** - User Authentication System
3. **users_model.py** - User Database Operations
4. **main_routes.py** - Core Features

---

# PART 1: app.py - Application Initialization

## Overview
This is the **entry point** of your entire Flask application. It sets up the database, loads configuration, and registers all routes.

---

## Section 1.1: Imports & Environment Setup

```python
from flask import Flask, jsonify, session, url_for, request
import os
import certifi
from dotenv import load_dotenv, find_dotenv
```

**What's happening:**
- `Flask` = Framework for building web apps
- `jsonify` = Converts Python dicts to JSON responses
- `session` = Store user data across requests (persistent login)
- `url_for` = Generate URLs for routes dynamically
- `request` = Access HTTP request data
- `certifi` = SSL certificate for secure MongoDB connections
- `dotenv` = Load environment variables from `.env` file

**Why dotenv?**
Sensitive data (MongoDB password, secret keys) shouldn't be in code. Instead:
- Store in `.env` file (not in git)
- Load at startup with `load_dotenv()`
- Access via `os.environ.get('VARIABLE_NAME')`

---

## Section 1.2: Loading Environment Variables (Lines 6-18)

```python
# Load .env as early as possible
dotenv_path = find_dotenv('.env', usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path, override=True)
    print(f'INFO: Loaded .env from {dotenv_path}')
else:
    print('INFO: No .env file found in project root')

# Ensure SSL_CERT_FILE is set for pymongo TLS if not already
if not os.environ.get('SSL_CERT_FILE'):
    os.environ['SSL_CERT_FILE'] = certifi.where()
```

**Step by step:**
1. `find_dotenv('.env', usecwd=True)` - Search for `.env` file in current directory
2. If found: `load_dotenv(dotenv_path, override=True)` loads all variables from `.env` into `os.environ`
3. `override=True` means `.env` values replace any existing environment variables
4. MongoDB requires SSL certificate for secure connections - we set it to certifi's bundle

**Example `.env` file:**
```
MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/smart_grocery
SECRET_KEY=your-secret-key-here
DATABASE_NAME=smart_grocery
```

---

## Section 1.3: Flask App Creation (Lines 21-23)

```python
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
```

**Breaking it down:**
- `Flask(__name__)` - Creates Flask app instance (___name___ = current module name)
- `app.secret_key` - Encryption key for sessions and cookies
  - Tries to load from `.env` file: `os.environ.get('SECRET_KEY')`
  - Fallback: `'dev-secret-key'` (only for development, NOT production!)

**Why secret_key?**
When user logs in and we set `session['user'] = email`, Flask encrypts this data before sending to browser. The secret_key is the encryption key. Without it, anyone could forge a session cookie.

---

## Section 1.4: MongoDB Connection Setup (Lines 25-57)

```python
# Get MongoDB URI from environment
dotenv_uri = os.environ.get('MONGO_URI')
raw_uri = dotenv_uri or os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'

# Sanitize: remove angle-brackets (common copy-paste mistake)
if '<' in raw_uri or '>' in raw_uri:
    cleaned = raw_uri.replace('<', '').replace('>', '')
    app.config['MONGO_URI'] = cleaned
    print(f"Warning: MONGO_URI contained angle-brackets; using cleaned host={host}")
else:
    app.config['MONGO_URI'] = raw_uri
```

**The logic:**
1. Look for `MONGO_URI` in environment (from `.env`)
2. If not found, use local MongoDB: `mongodb://localhost:27017/smart_grocery`
3. Users often copy-paste URIs with `<password>` placeholders - we remove those

**MongoDB URI format:**
```
mongodb+srv://username:password@cluster.mongodb.net/database_name
           ↑          ↑        ↑          ↑              ↑
        Protocol   username password   host          database
```

```python
# Set default database name if not in URI
if uri:
    if uri.rstrip().endswith('/') or '/' not in uri.split('@')[-1]:
        app.config.setdefault('MONGO_DBNAME', 'smart_grocery')
```

If URI doesn't specify database, default to `smart_grocery`.

---

## Section 1.5: Initialize PyMongo (Lines 60-62)

```python
from utils.db import mongo

# Initialize PyMongo with the Flask app
mongo.init_app(app)
```

**What's `mongo`?**
It's a `PyMongo()` instance from `utils/db.py`. It's Flask-PyMongo, which:
- Manages MongoDB connections
- Provides `mongo.db` = database connection object
- Handles connection pooling and reuse

**After this line:**
- All routes can access database via: `mongo.db.users.find()`, `mongo.db.products.find()`, etc.

---

## Section 1.6: Import Routes (Lines 64-66)

```python
from routes import main_bp, auth_bp
from routes.admin_routes import admin_bp
```

**Why after mongo.init_app?**
- Routes need database access
- If we import routes before mongo is initialized, they'd fail
- Order matters! Initialize first, then import routes

---

## Section 1.7: Register Blueprints (Lines 111-114)

```python
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
```

**What's a Blueprint?**
Think of it as a "route group". Blueprint = collection of related routes:
- `main_bp` = Features (home, compare prices, stores, shopping list)
- `auth_bp` = Authentication (login, signup, logout)
- `admin_bp` = Admin features

Benefits:
- Organize related routes together
- Avoid huge single route file
- Reusable code

**Under the hood:**
When you do `@auth_bp.route('/login')`, the route becomes `/login` (not scoped).
If you want scoped routes like `/api/login`, do:
```python
app.register_blueprint(auth_bp, url_prefix='/api')
```

---

## Section 1.8: Context Processor (Lines 117-132)

```python
@app.context_processor
def inject_shopping_list_count():
    """Expose shopping list count for nav badges."""
    count = 0
    try:
        email = session.get('user')
        if email:
            from models.users_model import get_user_lists
            data = get_user_lists(email) or {}
            lists = data.get('lists', []) or []
            total = 0
            for lst in lists:
                items = lst.get('items', []) or []
                total += sum(1 for it in items if not it.get('purchased'))
            count = total
    except Exception:
        count = 0
    return {'shopping_list_count': count}
```

**What's a context processor?**
A function that runs **before every template render**. It injects variables into ALL templates.

**Breaking down the code:**
1. `email = session.get('user')` - Get logged-in user's email
2. If no user logged in, skip this
3. `get_user_lists(email)` - Fetch user's shopping lists from database
4. Loop through each list and count items where `purchased != True`
5. Return dict: `{'shopping_list_count': total}`

**Why?**
Every page (home, compare prices, etc.) needs to show cart badge. Instead of calculating this on every page, calculate once here and it's available everywhere:

**In templates:**
```html
<span class="badge">{{ shopping_list_count }}</span>
```

The variable is available without passing it explicitly.

---

## Section 1.9: Image Processing Helper (Lines 135-150)

```python
def processed_image_url(image_url: str | None) -> str | None:
    if not image_url:
        return None
    try:
        key = hashlib.sha1(image_url.encode('utf-8')).hexdigest() + '.webp'
        path = os.path.join(app.root_path, 'static', 'processed', key)
        if os.path.exists(path):
            return url_for('static', filename=f'processed/{key}')
    except Exception:
        pass
    return None
```

**What's happening:**
1. Take image URL: `"https://example.com/product.jpg"`
2. Generate SHA1 hash: `"a3f2b1c...webp"`
3. Check if processed version exists: `static/processed/a3f2b1c.webp`
4. If exists, return local URL (faster, cached)
5. If not exists, return original URL

**Why?**
- External image URLs are slow (network latency)
- Download and compress to WebP (smaller file size)
- Cache locally for instant loading next time

**In templates:**
```html
<img src="{{ prefer_processed(product.image) }}">
```

---

## Section 1.10: Error Handlers (Lines 157-168)

```python
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500
```

**What's this?**
- `404` = Page not found
- `500` = Server error

When these happen, render pretty HTML pages instead of ugly error messages.

---

## Section 1.11: Health Check Endpoint (Lines 171-180)

```python
@app.route('/health')
def health():
    try:
        if getattr(mongo, 'db', None) is not None:
            mongo.db.command('ping')
        else:
            from pymongo import MongoClient
            uri = app.config.get('MONGO_URI')
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
        return jsonify({'status': 'ok', 'mongo': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'mongo': 'disconnected', 'detail': str(e)}), 500
```

**Purpose:**
Test if MongoDB connection is working.

**How to use:**
```bash
curl http://localhost:5000/health
# Returns: {"status": "ok", "mongo": "connected"}
```

Used for deployment monitoring - cloud systems check this to see if app is healthy.

---

## Section 1.12: Main Entry (Lines 246-247)

```python
if __name__ == '__main__':
    app.run(debug=True)
```

**What's this?**
- Only runs if file is executed directly: `python app.py`
- NOT run if imported in another file
- `debug=True` = Auto-reload on code changes, verbose errors

---

---

# PART 2: auth_routes.py - Authentication System

## Overview
Handles login, signup, and logout functionality.

---

## Section 2.1: Login Route (Lines 11-25)

```python
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        print(f'[LOGIN] email={email}, password_entered={repr(password)}')
        ok = users_model.authenticate(email, password)
        print(f'[LOGIN] auth result={ok}')
        if ok:
            session['user'] = email
            return redirect(url_for('main.home'))
        else:
            return render_template('login.html', error="Invalid credentials", email=email)
    return render_template('login.html')
```

**HTTP Methods:**
- `GET` = Display login form
- `POST` = Process login form

**Flow:**

**GET /login:**
```
Browser sends: GET /login
     ↓
Flask checks: request.method == 'GET'
     ↓
Skip the if block, go to last line
     ↓
return render_template('login.html')
     ↓
Browser shows login form (email/password inputs)
```

**POST /login:**
```
User fills form & clicks "Login"
     ↓
Browser sends: POST /login with email & password
     ↓
Flask checks: request.method == 'POST'
     ↓
Extract form data:
  email = request.form['email']      # "user@example.com"
  password = request.form['password'] # "mypassword"
     ↓
Call users_model.authenticate(email, password)
  This checks if password matches database
     ↓
If True:
  session['user'] = email
    → Sets session cookie in browser
    → User now "logged in"
  return redirect(url_for('main.home'))
    → Redirect to home page
     ↓
If False:
  return render_template('login.html', error="Invalid credentials", email=email)
    → Show login form again with error message
    → Keep email in form (user doesn't retype it)
```

**Key detail:**
```python
return redirect(url_for('main.home'))
```

- `url_for('main.home')` = Generate URL for route named `home` in blueprint `main`
  - Looks up: `@main_bp.route('/')`
  - Returns: `"/"`
- `redirect('/')` = Tell browser to navigate to `/`

---

## Section 2.2: Signup Route (Lines 28-58)

```python
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        print(f'[SIGNUP] email={email}, password_entered={repr(password)}, name={name}')
        
        if not email or not password:
            return render_template('signup.html', error='Please provide email and password', name=name, email=email)

        # check whether an account already exists
        existing = users_model.get_user_by_email(email)
        if existing:
            return render_template('signup.html', error='Email already registered', name=name, email=email)

        # create user record
        user_doc = {
            'email': email,
            'password': password,
            'name': name or email,
            'shopping_list': [],
            'total_cost': 0.0
        }
        users_model.create_user(user_doc)
        session['user'] = email
        return redirect(url_for('main.home'))

    return render_template('signup.html')
```

**Signup Flow:**

**Step 1: Validation**
```python
if not email or not password:
    return render_template('signup.html', error='Please provide email and password', ...)
```
Check email and password are provided. If not, show error.

**Step 2: Check if email exists**
```python
existing = users_model.get_user_by_email(email)
if existing:
    return render_template('signup.html', error='Email already registered', ...)
```
Prevent duplicate accounts. Query database for this email.

**Step 3: Create user document**
```python
user_doc = {
    'email': email,
    'password': password,
    'name': name or email,         # Use provided name, or use email as fallback
    'shopping_list': [],           # Empty shopping list
    'total_cost': 0.0              # No items yet
}
```

This is the data structure stored in MongoDB:
```json
{
  "_id": ObjectId("..."),
  "email": "user@example.com",
  "password": "mypassword",
  "name": "John Doe",
  "shopping_list": [],
  "total_cost": 0.0
}
```

**Step 4: Insert into database**
```python
users_model.create_user(user_doc)
```
Calls the database function to insert this document.

**Step 5: Auto-login**
```python
session['user'] = email
return redirect(url_for('main.home'))
```
After signup succeeds, immediately log them in (don't make them re-login).

---

## Section 2.3: Add to Shopping List (Lines 65-100+)

```python
@auth_bp.route('/shopping-list/add', methods=['POST'])
def add_shopping_item():
    fallback = 'user1@example.com' if 'user1@example.com' in m.users else None
    email = session.get('user') or fallback
    if not email:
        return jsonify({'error': 'no_user_available'}), 400
    
    data = request.get_json() or request.form
    item = data.get('item')
    
    if not item:
        return jsonify({'error': 'no_item_provided'}), 400
```

**Complex Request Handling:**
```python
data = request.get_json() or request.form
```

Accept data in multiple formats:
1. JSON: `fetch('/shopping-list/add', {body: JSON.stringify({item: ...})})`
2. Form: `<form method="POST"><input name="item"></form>`

---

---

# PART 3: users_model.py - Database Operations

## Overview
User-related database queries. Acts as a "database helper" for auth and main routes.

---

## Section 3.1: Class Structure (Lines 12-50)

```python
class CountryModel:
    def __init__(self):
        mongo_uri = os.getenv('MONGO_URI') or 'mongodb://localhost:27017/smart_grocery'
        
        # Try Flask-PyMongo first
        try:
            from utils.db import mongo as flask_mongo
        except Exception:
            flask_mongo = None

        if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
            self.db = flask_mongo.db
            self.client = None
        else:
            # Fallback: create direct MongoClient
            self.client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
            self.db = self.client['smart_grocery']
        
        self.collection = self.db['countries']
```

**Why this pattern?**
Prefer Flask-PyMongo (managed by app.py) over creating new connections. Fewer connections = better performance.

**Connection priority:**
1. Flask-PyMongo (if available) ← Preferred
2. Direct MongoClient ← Fallback

---

## Section 3.2: Authenticate Function (Lines 158-172)

```python
def authenticate(email: str, password: str) -> bool:
    user = get_user_by_email(email)
    if not user:
        print(f'[AUTH] user {email} not found')
        return False
    
    stored = user.get('password')
    if stored is None:
        print(f'[AUTH] user {email} has no password field')
        return False
    
    # Compare passwords
    match = str(stored).strip() == str(password).strip()
    print(f'[AUTH] result={match}')
    return match
```

**How authentication works:**

```
User enters password: "mypassword"
     ↓
Fetch user from database: user = get_user_by_email(email)
     ↓
Get stored password: stored = user.get('password')
     ↓
Compare:
  entered: "mypassword"
  stored:  "mypassword"
     ↓
Match? Return True
Otherwise: Return False
```

**⚠️ Security Issue:**
This code compares passwords as **plain text**. In production, passwords should be **hashed**:

```python
# Better approach (hashed):
import bcrypt

# Signup - hash before storing
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
user_doc['password'] = hashed

# Login - compare hash
if bcrypt.checkpw(password.encode(), stored_password):
    login_success()
```

Why? If database is compromised, hackers don't get plain text passwords.

---

## Section 3.3: Get User by Email (Lines 128-143)

```python
def get_user_by_email(email: str):
    if not email:
        return None
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        doc = flask_mongo.db.users.find_one({'email': email})
        if not doc:
            return None
        doc = dict(doc)
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
        return doc
    
    # Fallback: in-memory mock data
    if getattr(mock_models, 'users', None) is None:
        return None
    return mock_models.users.get(email)
```

**Query breakdown:**
```python
doc = flask_mongo.db.users.find_one({'email': email})
```

MongoDB query:
- Collection: `users`
- Filter: `{'email': email}` (find where email matches)
- `find_one()` returns first match (or None)

**Result:**
```json
{
  "_id": ObjectId("..."),
  "email": "user@example.com",
  "password": "mypassword",
  "name": "John Doe",
  "shopping_list": [...]
}
```

**Convert ObjectId to string:**
```python
if '_id' in doc:
    doc['id'] = str(doc['_id'])
```

JavaScript can't work with MongoDB ObjectIds, so convert to string.

---

## Section 3.4: Create User (Lines 146-153)

```python
def create_user(user_doc: dict):
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        res = flask_mongo.db.users.insert_one(user_doc)
        return str(res.inserted_id)
    
    # Fallback: add to in-memory dict
    mock_models.users[user_doc['email']] = user_doc
    return user_doc['email']
```

**Insert into MongoDB:**
```python
res = flask_mongo.db.users.insert_one(user_doc)
```

MongoDB automatically generates `_id` field and returns it as `res.inserted_id`.

**In-memory fallback:**
If MongoDB unavailable, store in Python dict (for development/testing).

---

## Section 3.5: Update Shopping List (Lines 163-179)

```python
def update_shopping_list(email: str, new_list: list) -> bool:
    if not email:
        return False
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            flask_mongo.db.users.update_one(
                {'email': email},
                {'$set': {'shopping_list': new_list}},
                upsert=True
            )
            return True
        except Exception:
            return False
```

**MongoDB update syntax:**
```python
db.users.update_one(
    {'email': email},              # FILTER: which document?
    {'$set': {'shopping_list': new_list}},  # UPDATE: what to change?
    upsert=True                    # If not found, create it
)
```

**Breaking it down:**
- `update_one()` = Update first matching document
- Filter `{'email': email}` = Find user by email
- `{'$set': {...}}` = Set these fields (doesn't delete other fields)
- `upsert=True` = If user doesn't exist, create them (insert + update)

---

## Section 3.6: Add to Shopping List (Lines 182-199)

```python
def add_to_shopping_list(email: str, item) -> bool:
    if not email or not item:
        return False
    
    if flask_mongo is not None and getattr(flask_mongo, 'db', None) is not None:
        try:
            res = flask_mongo.db.users.update_one(
                {'email': email},
                {'$push': {'shopping_list': item}},  # Append item to array
                upsert=True
            )
            return True
        except Exception:
            return False
```

**Key difference:**
- `{'$set': ...}` = Replace entire field
- `{'$push': ...}` = Append to array

Example:
```
Before: shopping_list = ['Milk', 'Bread']
Command: {'$push': {'shopping_list': 'Eggs'}}
After: shopping_list = ['Milk', 'Bread', 'Eggs']
```

---

---

# PART 4: main_routes.py - Core Features

## Overview
Main feature routes: home page, product comparison, stores, shopping list.

---

## Section 4.1: Home Route (Lines 85-144)

```python
@main_bp.route('/')
def home():
    user_email = session.get('user')
    if not user_email:
        return render_template('entry.html')
    
    db = get_db()
    stores = list(db.stores.find({}))
    products = list(db.products.find({}))
    featured_deals = list(db.featured_deals.find({}))
    
    # Convert ObjectId to string
    for doc_list in (stores, products, featured_deals):
        for d in doc_list:
            if '_id' in d:
                d['id'] = str(d['_id'])
    
    return render_template('home.html', 
                         stores=stores, 
                         products=products, 
                         featured_deals=featured_deals)
```

**Flow:**

```
GET /
  ↓
Check if user logged in: session.get('user')
  ↓
If No: return render_template('entry.html')
  Shows: "Sign In" / "Create Account" prompts
  
If Yes:
  ↓
  Fetch data from MongoDB:
    stores = db.stores.find({})
      → Query entire stores collection: []
      → Returns: [store1, store2, store3, ...]
    
    products = db.products.find({})
      → Query entire products collection
      → Returns: [product1, product2, ...]
    
    featured_deals = db.featured_deals.find({})
      → Query entire deals collection
      → Returns: [deal1, deal2, ...]
  ↓
  Convert IDs: MongoDB uses ObjectId, JavaScript uses strings
    For each document:
      d['id'] = str(d['_id'])
  ↓
  Render template with all data:
    return render_template('home.html', stores=stores, ...)
```

**In the template (home.html):**
```html
{% for store in stores %}
  <div class="store-card">
    <h5>{{ store.name }}</h5>
    <p>{{ store.location }}</p>
  </div>
{% endfor %}
```

---

## Section 4.2: Stores Page (Lines 159-175)

```python
@main_bp.route('/stores')
def stores_page():
    db = get_db()
    stores = list(db.stores.find({}))
    for s in stores:
        if '_id' in s:
            s['id'] = str(s['_id'])
    return render_template('stores.html', stores=stores)
```

**Simpler than home:**
Just fetch stores, no authentication check (could be public).

---

## Section 4.3: Store Products (Lines 177-200+)

```python
@main_bp.route('/stores/<store_name>')
def store_products_page(store_name):
    """Display all products for a specific store."""
    db = get_db()
    products = []
```

**Dynamic route:**
```
URL: /stores/Billa
  ↓
store_name = "Billa"
  ↓
Query: db.products.find({'store': 'Billa'})
  ↓
Return: [product1, product2, ...]
```

**Route syntax:**
- `<store_name>` = URL parameter (captured from URL)
- Passed as function argument: `def store_products_page(store_name)`

---

---

# PART 5: Key Concepts & Patterns

## Pattern 1: Try-Except Fallback

```python
try:
    db = get_db()
    stores = list(db.stores.find({}))
except Exception:
    stores = getattr(m, 'stores', [])  # Use in-memory fallback
```

**Why?**
App can work WITHOUT MongoDB (using mock data). Good for development.

**Fallback chain:**
1. Try real MongoDB
2. If fails, use in-memory mock data
3. If no mock data, return empty list

---

## Pattern 2: Session Management

```python
# Login
session['user'] = email

# Check login
user_email = session.get('user')

# Logout
session.pop('user', None)
```

**How sessions work:**
1. Server sets: `session['user'] = 'user@example.com'`
2. Flask encrypts this with `app.secret_key`
3. Sends to browser as HTTP cookie: `Set-Cookie: session=encrypted_data`
4. Browser sends back on every request: `Cookie: session=encrypted_data`
5. Flask decrypts and loads session data

---

## Pattern 3: AJAX Responses

```python
@auth_bp.route('/shopping-list/add', methods=['POST'])
def add_shopping_item():
    # ... code ...
    return jsonify({'success': True, 'count': total}), 200
```

**Returns JSON:**
```json
{
  "success": true,
  "count": 5
}
```

**Frontend JavaScript:**
```javascript
fetch('/shopping-list/add', {method: 'POST', body: JSON.stringify({...})})
  .then(r => r.json())
  .then(data => {
    console.log(data.count);  // 5
    updateBadge(data.count);
  });
```

---

## Pattern 4: MongoDB Query Syntax

### Find All
```python
docs = list(db.users.find({}))
```

### Find One
```python
doc = db.users.find_one({'email': 'user@example.com'})
```

### Filter
```python
docs = list(db.products.find({'store': 'Billa'}))
```

### Insert
```python
result = db.users.insert_one({'email': 'new@example.com', ...})
inserted_id = result.inserted_id
```

### Update
```python
db.users.update_one(
    {'email': 'user@example.com'},
    {'$set': {'shopping_list': [...]}}
)
```

### Push to Array
```python
db.users.update_one(
    {'email': 'user@example.com'},
    {'$push': {'shopping_list': 'Milk'}}
)
```

---

## Pattern 5: Error Handling

```python
try:
    user = db.users.find_one({'email': email})
except Exception as e:
    print(f'Database error: {e}')
    user = None

if user is None:
    return "User not found"
```

Always wrap database operations in try-except - they can fail (network issues, invalid data, etc.).

---

# Summary Table

| Task | Code |
|------|------|
| Start app | `python app.py` |
| Load config | `load_dotenv()` |
| Create Flask app | `app = Flask(__name__)` |
| Connect MongoDB | `mongo.init_app(app)` |
| Register routes | `app.register_blueprint(main_bp)` |
| Get user session | `email = session.get('user')` |
| Set login | `session['user'] = email` |
| Query database | `db.users.find_one({'email': email})` |
| Insert document | `db.users.insert_one({...})` |
| Update document | `db.users.update_one({'email': email}, {'$set': {...}})` |
| Return JSON | `return jsonify({'key': 'value'}), 200` |
| Render template | `return render_template('page.html', data=data)` |
| Redirect | `return redirect(url_for('route_name'))` |

---

**Good luck with your presentation! This covers all the critical Python code. 🚀**
