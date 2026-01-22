"""
═══════════════════════════════════════════════════════════════════════════
ADMIN ROUTES - Administrative Functions
═══════════════════════════════════════════════════════════════════════════
Purpose: Handle admin-only operations and data management
Routes:
- Add/edit/delete products
- Manage featured deals
- Upload product images
- View analytics/statistics
Prefix: /admin
Security: Should be restricted to admin users only
═══════════════════════════════════════════════════════════════════════════
"""

from flask import Blueprint, request, jsonify, current_app # Import core Flask components for routing and JSON responses
from models.products_model import products_model # Import the product data model for database operations
from models.stores_model import stores_model # Import store data model to handle retailer information
from models.featured_deals_model import featured_deals_model # Import featured deals model for promotional management
from models.multibuy_offers_model import multibuy_offers_model # Import multibuy model for "Buy X Get Y" logic
from models.notifications_model import notifications_model # Import notifications model to alert users of changes

# Log the blueprint setup
# 'url_prefix' ensures all routes here start with /admin
admin_bp = Blueprint('admin', __name__, url_prefix='/admin') # Initialize the Blueprint for admin-specific endpoints


def _require_token(): # Define a helper function to verify administrative privileges
    """
    HELPER: Token Verification
    --------------------------
    A private helper to secure admin routes.
    
    Logic:
    1. Check if 'ADMIN_TOKEN' is configured (env var or app config).
    2. If NOT configured, assume development mode/unsecured and allow access (Return None).
    3. If configured, check for 'X-Admin-Token' in request headers.
    4. If header matches token => Allow.
    5. If header mismatch => Return 403 Forbidden.
    
    Returns:
        None if access granted.
        Tuple (JSON response, 403) if access denied.
    """
    token = current_app.config.get('ADMIN_TOKEN') or None # Retrieve the secret admin token from the application configuration
    if not token: # Check if the token is even set in the environment
        # Security Warning: No token required if variable not set!
        return None # If no token is set, bypass security (usually for local development)
        
    hdr = request.headers.get('X-Admin-Token') # Extract the security token from the incoming request headers
    if not hdr or hdr != token: # Compare the provided header token with the expected system token
        return jsonify({'status': 'error', 'detail': 'missing or invalid admin token'}), 403 # Return error if tokens don't match
    return None # Return None to indicate authorization succeeded


@admin_bp.route('/product', methods=['POST']) # Define the endpoint to add or update products via HTTP POST
def add_or_update_product(): # Define the view function for the product upsert operation
    """
    Upsert (Update or Insert) a single product document.

    Expected JSON body (example):
    {
      "name": "Organic Bananas",
      "price": "€1.29",
      "price_val": 1.29,
      "image": "https://cdn.example/42e9as7nataai4a6jcufwg.jpg",
      "images": ["https://.../1.jpg"],
      "category": "Produce",
      "stores": [{"store":"FreshMart","price":"€1.29"}],
      "description": "...",
      "qty": 1,
      "_id": "OPTIONAL_ID_FOR_UPDATES"
    }

    Logic:
    1. Verify Admin Token.
    2. Validate JSON payload.
    3. Determine uniqueness key: Use 'name' or '_id'.
    4. Call Model to perform upsert.
    5. If New Product -> Broadcast 'New Product' notification.
    6. If Price Drop -> Broadcast 'Price Drop' notification.
    """
    # 1. SECURITY CHECK
    err = _require_token() # Run the token verification helper
    if err: # Check if the security check returned an error
        return err # Halt and return the 403 error if unauthorized

    # 2. INPUT VALIDATION
    if not request.is_json: # Check if the request body is formatted as valid JSON
        return jsonify({'status': 'error', 'detail': 'expected JSON body'}), 400 # Return 400 Bad Request if not JSON

    data = request.get_json() # Parse the incoming JSON payload into a Python dictionary
    if not data or not isinstance(data, dict): # Validate that the data is not empty and is a dictionary
        return jsonify({'status': 'error', 'detail': 'invalid JSON body'}), 400 # Return error for malformed payloads

    # 3. DETERMINE LOOKUP KEY
    # We need to know which document to update. 
    # Prefer 'name' (user friendly unique key) or '_id' (system unique key).
    key = None # Initialize the database query key variable
    if data.get('name'): # Check if the product name is provided in the payload
        key = {'name': data['name']} # Set the unique identifier key to the product name
    elif data.get('_id'): # Fallback to checking for a specific MongoDB ObjectID
        key = {'_id': data['_id']} # Set the unique identifier key to the specific ID
    else: # If neither name nor ID are provided
        return jsonify({'status': 'error', 'detail': 'provide at least a "name" or "_id" field'}), 400 # Return error for missing key

    # Clean the data: remove '_id' from the update payload to prevent
    # "Modifying the immutable _id" errors from MongoDB.
    set_doc = {k: v for k, v in data.items() if k != '_id'} # Create a new document dictionary excluding the protected '_id' field

    try: # Start a try-except block to handle database or processing errors
        # 4. PRE-CHECK FOR NOTIFICATIONS (Get existing state)
        old_price = None # Variable to store the price before the update
        existing_product = None # Variable to store the current product state from DB
        
        # Try to find the product before we change it
        if data.get('name'): # If we have a name, try finding the product by name first
            existing_product = products_model.get_product_by_name(data.get('name')) # Call model to fetch existing product by name
        
        if not existing_product and data.get('_id'): # If not found by name, try finding it by ID
             existing_product = products_model.get_product_by_id(str(data.get('_id'))) # Call model to fetch existing product by ID
             
        if existing_product: # If the product already exists in the database
            old_price = existing_product.get('price_val') # Save its current price for comparison later

        # 5. EXECUTE UPSERT via Model
        res = products_model.upsert_product(key, set_doc) # Perform the update or insert operation in MongoDB
        
        # Determine if it was an INSERT (new) or UPDATE (existing)
        action = 'updated' # Set default action message to 'updated'
        product_id = existing_product.get('id') if existing_product else None # Get the ID for tracking
        
        # upserted_id is only present if a new document was created
        if res.get('upserted_id'): # Check if MongoDB indicates a new document was inserted
            action = 'created' # Update action message to 'created'
            product_id = str(res.get('upserted_id')) # Store the newly generated unique ID
            
            # 6a. BROADCAST: NEW PRODUCT
            # Notify users that a new item is available
            notifications_model.broadcast_notification({ # Call model to send a system-wide alert
                'type': 'deal_alert', # Categorize as a deal alert for front-end styling
                'title': f"New Product: {set_doc.get('name')}", # Set alert title with product name
                'message': f"Available now! {set_doc.get('name')} has been added to our catalog.", # Set detailed alert message
                'product_id': product_id, # Link the notification to the new product ID
                'priority': 'normal', # Set standard notification priority
                # redundant data for rich card immediate rendering without DB lookup
                'product_name': set_doc.get('name'), # Include name directly in notification for faster display
                'product_image': set_doc.get('image'), # Include image URL directly in notification
                'price': set_doc.get('price_val'), # Include current price in notification
                'store_name': 'New Arrival' # Set placeholder store name
            }) # Close the broadcast dictionary
            
        elif old_price and set_doc.get('price_val') and float(set_doc.get('price_val')) < float(old_price): # If price decreased
            # 6b. BROADCAST: PRICE DROP
            # Only if price is lower than before
            diff = float(old_price) - float(set_doc.get('price_val')) # Calculate the actual money saved
            notifications_model.broadcast_notification({ # Send a price drop alert to all users
                'type': 'price_drop', # Categorize as price drop for special UI handling
                'title': f"Price Drop: {set_doc.get('name')}", # Set alert title
                'message': f"Great news! The price dropped by €{diff:.2f}.", # Format message with currency difference
                'product_id': product_id, # Link alert to the specific product
                'priority': 'high', # Set high priority to ensure users see the saving immediately
                'price': set_doc.get('price_val'), # Include the new, lower price
                'old_price': old_price, # Include the old price for comparison in the UI
                # Context data for notification card
                'product_name': set_doc.get('name'), # Include name for instant rendering
                'product_image': set_doc.get('image') # Include image for instant rendering
            }) # Close the broadcast dictionary

        return jsonify({'status': 'ok', 'action': action, 'id': product_id}), 201 if action == 'created' else 200 # Return success response
        
    except Exception as e: # Catch any unexpected failures
        # Catch DB errors and return 500
        return jsonify({'status': 'error', 'detail': str(e)}), 500 # Return formatted error message and 500 status


@admin_bp.route('/dbinfo', methods=['GET']) # Define route to fetch database summary statistics
def db_info(): # View function for the stats endpoint
    """
    Get Database Statistics.
    
    Returns:
        JSON object containing counts of products, users, deals, etc.
        Useful for admin dashboard widgets.
        
    Security:
        Protected by ADMIN_TOKEN.
    """
    err = _require_token() # Perform the mandatory security check
    if err: # If security check failed
        return err # Return the error response immediately

    try: # Begin processing the stats request
        from models.models import get_db_info # Import helper to aggregate database counts
        info = get_db_info() # Execute the aggregation function
        return jsonify(info), 200 # Return the stats as JSON
    except Exception as e: # Handle potential DB connection errors
        return jsonify({'status': 'error', 'detail': str(e)}), 500 # Return error message for debugging


@admin_bp.route('/featured-deal', methods=['POST']) # Define endpoint to create promotional "Featured Deals"
def add_featured_deal(): # View function to handle featured deal creation
    """
    Add a new featured deal manually.
    
    Trigger:
    - User/Admin submits form to promote a product.
    
    Side Effects:
    - Inserts record into 'featured_deals' collection.
    - Sends a HIGH PRIORITY push notification to all users.
    """
    err = _require_token() # Validate administrative access via token
    if err: # Check for authorization failure
        return err # Return early with 403 Forbidden

    if not request.is_json: # Validate that request body provides data in JSON format
        return jsonify({'status': 'error', 'detail': 'expected JSON body'}), 400 # Return error if wrong format

    data = request.get_json() # Parse JSON data into dictionary
    if not data or 'title' not in data: # Ensure mandatory 'title' field exists
        return jsonify({'status': 'error', 'detail': 'missing "title" in deal data'}), 400 # Return error for missing fields

    try: # Start processing the new deal
        # 1. Insert into DB
        from models.featured_deals_model import FeaturedDealsModel # Load the featured deals database model
        fdm = FeaturedDealsModel() # Instantiate the model class
        deal_id = fdm.insert_deal(data) # Save the new deal document to MongoDB

        # 2. BROADCAST NOTIFICATION
        # Grab the global NotificationsModel instance
        from models.notifications_model import NotificationsModel # Load the notification alert system
        nm = NotificationsModel() # Instantiate the notification engine
        nm.broadcast_notification({ # Send a massive alert for the new hot deal
            'type': 'deal_alert', # Set styling to 'deal' alert
            'title': f"HOT DEAL: {data.get('title')}", # Set attention-grabbing title
            'message': f"New discount available: {data.get('description', 'Check out the new deal!')}", # Set deal description
            'product_id': data.get('product_id'), # Link to product if available
            'priority': 'high' # Set high priority to push this to all users instantly
        }) # Close alert broadcast

        return jsonify({'status': 'ok', 'action': 'created', 'id': deal_id}), 201 # Return 201 Created status
    except Exception as e: # Catch processing or network errors
        return jsonify({'status': 'error', 'detail': str(e)}), 500 # Return error detail
