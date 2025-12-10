# Smart Grocery

**Smart Grocery** is a web application designed to help users shop smarter by comparing prices of the same products across different stores. 
It also provides useful features like featured deals, store information, a personal shopping list, and more.

## Features

- **Home Page:** Provides an overview of all the features and quick access to different sections of the app.
- **Login / Sign Up:** Allows users to create an account and log in for personalized access.
- **Compare Prices:** Check prices for the same product across multiple stores to find the best deal.
- **Featured Deals:** Discover special offers and discounts from various stores.
- **Stores Information:** See details like store distance (miles away) and opening hours.
- **Profile Page:** Manage your personal account and preferences.
- **Shopping List:** Keep track of items you want to buy, with checkboxes to mark purchased items. You can add or remove items, and see the total cost of your list.

## Technologies Used

- Python (Flask)
- HTML & CSS
- Bootstrap
- JavaScript
- MongoDB Atlas (Database)

## Team Members and Roles

### **Bora Elshani** - Leader**
- **Backend Development:**
  - Flask application setup and configuration (`app.py`)
  - Main routing logic and navigation (`routes/main_routes.py`)
  - User authentication and session management (`models/users_model.py`)
  - Database models and fallback data (`models/models.py`)
  - Featured deals import script and data processing
  
- **Frontend Development:**
  - Shopping List page - complete UI and functionality (`templates/shopping_list.html`)
  - Profile page and user account management (`templates/profile.html`)
  - Featured Deals pages (`templates/featured_deals.html`, `templates/featured_deal_detail.html`)
  - Compare Prices page layout and features (`templates/compare_prices.html`)
  - Product information view (`templates/product_info.html`)
  - Entry/landing page (`templates/entry.html`)
  
- **JavaScript Development:**
  - Shopping list interactive features (add/remove items, list management)
  - Dynamic UI updates and real-time calculations
  - API endpoint integrations
  - Favorite products functionality

### **Dren Buqa** 
- **Backend Development:**
  - Authentication routes and user management (`routes/auth_routes.py`)
  - Main application routes (`routes/main_routes.py`)
  - Admin functionality (`routes/admin_routes.py`)
  - Flask app configuration (`app.py`)

- **Frontend Development:**
  - Homepage design and layout (`templates/home.html`)
  - Product detail pages (`templates/product_detail.html`)
  - Compare prices interface (`templates/compare_prices.html`)
  - Authentication pages (Login & Signup) (`templates/login.html`, `templates/signup.html`)
  - Error handling pages (`templates/404.html`, `templates/500.html`)
  
- **Styling & Design:**
  - Complete CSS styling and theme (`static/style.css`)
  - Responsive design implementation
  - Bootstrap integration and customization
  - Component styling and animations
  
- **Database Models:**
  - Products data model (`models/products_model.py`)
  - Stores data model (`models/stores_model.py`)
  - Featured deals model (`models/featured_deals_model.py`)
  - User model operations (`models/users_model.py`)
  
- **JavaScript Development:**
  - Form validation and user input handling
  - UI enhancements and interactions
  - Product search and filtering

---

## Setup Instructions (First Time Only)

Follow these steps **once** when you first clone the project or start working on it.

### Step 1: Clone the Repository
```bash
git clone https://github.com/boraelshani/Smart-Grocery.git
cd "Smart Grocery Project"
```

### Step 2: Create Virtual Environment
This creates a local Python environment for the project.

```powershell
python -m venv .venv
```

### Step 3: Activate Virtual Environment

**Option A: PowerShell (Recommended)**
```powershell
.\.venv\Scripts\Activate.ps1
```

If you get an execution policy error, run this once:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

**Option B: Command Prompt (CMD)**
```cmd
.venv\Scripts\activate.bat
```

**Option C: Without Activating (Use venv Python Directly)**
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

### Step 4: Install Dependencies
This downloads and installs all required packages listed in `requirements.txt`.

```powershell
pip install -r requirements.txt
```

---

## Running the Project (Every Time You Work)

Once setup is complete, follow these steps **every time** you start working:

### Step 1: Navigate to Project Folder
```powershell
cd "C:\Users\[YourUsername]\Desktop\Smart Grocery Project"
```

### Step 2: Activate Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

You'll see `(.venv)` at the start of your PowerShell prompt when activated.

### Step 3: Run the Flask App
```powershell
python app.py
```

You should see:
```
 * Running on http://127.0.0.1:5000
```

### Step 4: Open in Browser
Visit: **http://127.0.0.1:5000/**

### Step 5: Stop the Server
Press `Ctrl + C` in PowerShell to stop the app.

---

## Quick Reference

| Task | Command |
|------|---------|
| Clone repo (first time) | `git clone https://github.com/boraelshani/Smart-Grocery.git` |
| Create venv (first time) | `python -m venv .venv` |
| Activate venv | `.\.venv\Scripts\Activate.ps1` |
| Install packages (first time) | `pip install -r requirements.txt` |
| Run app | `python app.py` |
| Stop app | `Ctrl + C` |
| Deactivate venv | `deactivate` |

---

## Project Structure

```
Smart Grocery Project/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .gitignore            # Git ignore rules
├── routes/               # Flask route handlers
│   ├── main_routes.py
│   └── auth_routes.py
├── models/               # Data models
│   └── models.py
├── templates/            # HTML templates
│   ├── home.html
│   ├── login.html
│   ├── signup.html
│   ├── compare_prices.html
│   ├── featured_deals.html
│   ├── stores.html
│   └── ...
├── static/               # CSS and JavaScript
│   ├── style.css
│   └── js/
│       └── script.js
└── utils/                # Helper functions
    └── helpers.py
```
