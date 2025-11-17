# Mock Data — Replace with real DB later

stores = [
    {"id": 1, "name": "Supermart", "location": "123 Main St", "distance": "2.5 miles", "opening_hours": "9 AM - 9 PM", "url": "https://supermart.com", "deals": ["Free delivery", "50% off milk"]},
    {"id": 2, "name": "Grocery Hub", "location": "456 Oak Ave", "distance": "1.2 miles", "opening_hours": "8 AM - 8 PM", "url": "https://groceryhub.com", "deals": ["Buy 2 get 1", "Free shipping over $25"]},
]

# Mock Product Comparison Data
products = [
    {
        "name": "Milk",
        "unit": "gal",
        "stores": [
            {"store": "Supermart", "price": "$3.99", "discount": "10% off", "deal": "Free delivery"},
            {"store": "Grocery Hub", "price": "$4.49", "discount": "None", "deal": "Buy 2 get 1"},
            {"store": "Fresh & Co", "price": "$3.79", "discount": "20% off", "deal": "Free shipping"}
        ],
        "cheapest": {"store": "Fresh & Co", "price": "$3.79", "discount": "20% off", "deal": "Free shipping"}
    },
    {
        "name": "Bread",
        "unit": "loaf",
        "stores": [
            {"store": "Supermart", "price": "$2.99", "discount": "None", "deal": "Free delivery"},
            {"store": "Grocery Hub", "price": "$3.49", "discount": "Buy 1 get 1", "deal": "Buy 2 get 1"},
            {"store": "Fresh & Co", "price": "$3.29", "discount": "None", "deal": "Free shipping"}
        ],
        "cheapest": {"store": "Supermart", "price": "$2.99", "discount": "None", "deal": "Free delivery"}
    }
]

# Mock User Data (Login)
users = {
    "user1@example.com": {"email": "user1@example.com", "password": "password123", "name": "John Doe", "shopping_list": ["milk", "bread"], "total_cost": 6.98},
    "user2@example.com": {"email": "user2@example.com", "password": "password456", "name": "Jane Smith", "shopping_list": ["bottled water"], "total_cost": 3.99}
}

# Mock Featured Deals
featured_deals = [
    {"title": "Free Delivery on Milk", "store": "Supermart", "price": "$3.99", "image": "https://via.placeholder.com/150x150"},
    {"title": "Buy 2 Get 1", "store": "Grocery Hub", "price": "$3.49", "image": "https://via.placeholder.com/150x150"},
]
