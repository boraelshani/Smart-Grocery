# Smart Grocery

**Smart Grocery** is a comprehensive full-stack web application developed to modernize the grocery shopping experience. It allows users to compare product prices across different stores (real-time price comparison), discover featured deals, manage personal shopping lists, and receive notifications about price drops.

## Features

- **Store Price Comparison:** Compare prices for the same product across multiple vendors (e.g., Aldi, Lidl, Spar) to find the cheapest option.
- **Smart Shopping List:** Add items to a digital list, check them off as you shop, and see estimated total costs.
- **Notifications System:** Receive alerts for price drops, new deals, and system announcements.
- **Featured Deals:** Browse aggregated special offers and discounts from all supported stores.
- **User Accounts:** Secure login/signup system with profile management (avatar, address, phone).
- **Store Locator:** View store details, opening hours, and distance from your location.
- **Admin Dashboard:** Special administrative routes for managing products and deals.
- **Robust Error Handling:** Custom, user-friendly 404 and 500 error pages.

## Technologies Used

- **Backend:** Python (Flask)
- **Database:** MongoDB Atlas (NoSQL)
- **Frontend:** HTML5, CSS3, Bootstrap 5, Jinja2 Templates
- **Scripting:** JavaScript (Vanilla JS & Async Fetch API)
- **Security:** Bcrypt (hashing), JWT (JSON Web Tokens)

## Setup Instructions

### Prerequisites
- Python 3.8 or higher
- Git

### Step 1: Clone the Repository
```powershell
git clone https://github.com/boraelshani/Smart-Grocery.git
cd Smart-Grocery
```

### Step 2: Create Virtual Environment
Run this command in PowerShell to create an isolated Python environment:
```powershell
python -m venv venv
```

### Step 3: Activate Virtual Environment
**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

### Step 4: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 5: Configure Environment
Create a `.env` file in the root directory with your secrets:
```env
MONGO_URI="mongodb+srv://<your-connection-string>"
SECRET_KEY="your-secret-key"
JWT_SECRET_KEY="your-jwt-secret"
```

### Step 6: Run the Application
```powershell
python app.py
```
Open your browser and navigate to `http://127.0.0.1:5000`.

---

## Project Structure (For Professor/Grading)

*   **`app.py`**: The entry point. Initializes Flask, connects to MongoDB, and registers Blueprints.
*   **`routes/`**: Contains the controllers (logic) for different parts of the app (`main`, `auth`, `admin`).
*   **`models/`**: Handles all Database interactions. We use the **DAO (Data Access Object)** pattern here.
*   **`templates/`**: HTML files using Jinja2 syntax to inject dynamic data.
*   **`static/`**: CSS, Images, and JavaScript files.
*   **`utils/`**: Helper functions for DB connections and common tasks (DRY principle).

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
│   ├── ui_routes.py
│   ├── lists_routes.py
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
│   ├── css/
│   └── js/
│       └── modules/
└── utils/                # Helper functions
    └── helpers.py
```
