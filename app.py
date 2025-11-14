from flask import Flask, render_template, request, jsonify, redirect,
url_for, session
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Mock Data — Replace with real DB later
stores = [
    {"id": 1, "name": "Supermart", "location": "123 Main St",
"distance": "2.5 miles", "opening_hours": "9 AM - 9 PM", "url":
"https://supermart.com", "deals": ["Free delivery", "50% off milk"]},
    {"id": 2, "name": "Grocery Hub", "location": "456 Oak Ave",
"distance": "1.2 miles", "opening_hours": "8 AM - 8 PM", "url":
"https://groceryhub.com", "deals": ["Buy 2 get 1", "Free shipping over
$25"]},
]

# Mock Product Comparison Data
products = [
    {
        "name": "Milk",
        "unit": "gal",
        "stores": [
            {"store": "Supermart", "price": "$3.99", "discount": "10%
off", "deal": "Free delivery"},
            {"store": "Grocery Hub", "price": "$4.49", "discount":
"None", "deal": "Buy 2 get 1"},
            {"store": "Fresh & Co", "price": "$3.79", "discount": "20%
off", "deal": "Free shipping"}
        ],
        "cheapest": {"store": "Fresh & Co", "price": "$3.79",
"discount": "20% off", "deal": "Free shipping"}
    },
    {
        "name": "Bread",
        "unit": "loaf",
        "stores": [
            {"store": "Supermart", "price": "$2.99", "discount":
"None", "deal": "Free delivery"},
            {"store": "Grocery Hub", "price": "$3.49", "discount":
"Buy 1 get 1", "deal": "Buy 2 get 1"},
            {"store": "Fresh & Co", "price": "$3.29", "discount":
"None", "deal": "Free shipping"}
        ],
        "cheapest": {"store": "Supermart", "price": "$2.99",
"discount": "None", "deal": "Free delivery"}
    }
]

# Mock User Data (Login)
users = {
    "user1@example.com": {"email": "user1@example.com", "password": "password123", "name": "John Doe", "shopping_list": ["milk", "bread"], "total_cost": 6.98},
    "user2@example.com": {"email": "user2@example.com", "password": "password456", "name": "Jane Smith", "shopping_list": ["bottled water"], "total_cost": 3.99}
}

# Mock Featured Deals
featured_deals = [
    {"title": "Free Delivery on Milk", "store": "Supermart", "price":
"$3.99", "image": "https://via.placeholder.com/150x150"},
    {"title": "Buy 2 Get 1", "store": "Grocery Hub", "price": "$3.49",
"image": "https://via.placeholder.com/150x150"},
]

# Routes

@app.route('/')
def home():
    return render_template('home.html', stores=stores, products=products, featured_deals=featured_deals)

@app.route('/stores')
def stores():
    return render_template('stores.html', stores=stores)

@app.route('/featured-deals')
def featured_deals_page():
    return render_template('featured_deals.html', deals=featured_deals)

@app.route('/compare-prices')
def compare_prices():
    return render_template('compare_prices.html', products=products)

@app.route('/shopping-list')
def shopping_list():
    return render_template('shopping_list.html', user_data=users.get("user1@example.com", {}))

@app.route('/profile')
def profile():
    return render_template('profile.html', user_data=users.get("user1@example.com", {}))

# Login / Sign Up Routes

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email in users and users[email]['password'] == password:
            session['user'] = email
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        if email not in users:
            users[email] = {"password": password, "name": name,
"shopping_list": [], "total_cost": 0.0}
            session['user'] = email
            return redirect(url_for('home'))
        else:
            return render_template('signup.html', error="Email already exists")
    return render_template('signup.html')

# Protected Routes (requires login)
@app.route('/profile', methods=['POST'])
def update_profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    email = session['user']
    new_list = request.form.getlist('shopping_list')
    users[email]['shopping_list'] = new_list
    return redirect(url_for('profile'))

# Homepage with dynamic content
@app.route('/about')
def about():
    return render_template('about.html')


# Error Handling
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)
