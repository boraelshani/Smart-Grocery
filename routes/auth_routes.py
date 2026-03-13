"""
═══════════════════════════════════════════════════════════════════════════
AUTHENTICATION ROUTES
═══════════════════════════════════════════════════════════════════════════
Handles user login, signup, logout, and session management.
Also includes shopping list API endpoints for adding/removing items.
"""

from flask import render_template, request, redirect, url_for, session, jsonify, current_app # Import core Flask modules for HTTP handling and sessions
from . import auth_bp # Import the authentication Blueprint instance from the local package
import re # Import Regular Expression module for string pattern matching
import os # Import Operating System module for environment variable access
from bson import Decimal128 # Import BSON Decimal128 for precise MongoDB currency storage
from models import models as m # Import the shared models package for data connectivity checks
from models.users_model import users_model # Import user-specific database logic and authentication methods
from models.products_model import products_model # Import product database methods for item enrichment
from models.featured_deals_model import featured_deals_model # Import deals database methods for promotional item lookup
from models.multibuy_offers_model import multibuy_offers_model # Import multibuy offers database methods
from utils import helpers # Import utility helpers for JWT generation and email extraction
from comparison.cheapest_finder import get_cheapest_from_product


# ═══════════════════════════════════════════════════════════════════════════
# LOGIN & SIGNUP ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@auth_bp.route('/login', methods=['GET', 'POST']) # Define the login endpoint supporting both form view and submission
def login(): # Define the view function for user authentication
    """
    Handle user login with email and password.
    
    Operations:
    1. REQUEST HANDLING: Accepts both GET (form display) and POST (submission).
    2. CREDENTIAL VERIFICATION: Calls `users_model.authenticate()` to check hash/plaintext.
    3. ACCESS TOKEN GENERATION: Creates a JWT (JSON Web Token) for secure API access.
    4. SESSION ESTABLISHMENT: Sets a secure HTTP-only cookie to maintain login state.
    
    POST: Authenticates user.
    GET: Renders login.html.
    """
    if request.method == 'POST': # Check if the user submitted the login form
        # 1. EXTRACT CREDENTIALS
        # Pull data from the form submission
        email = request.form['email'] # Extract the email address from the POST payload
        password = request.form['password'] # Extract the password from the POST payload
        
        # Log attempts (excluding password for security)
        print(f'[LOGIN] Attempt for email={email}') # Print a debug log message tracking the login email
        
        # 2. VERIFY CREDENTIALS
        # Delegate to the model layer (users_model.py) which handles bcrypt hashing logic.
        ok = users_model.authenticate(email, password) # Call authentication method to verify email/password match in DB
        print(f'[LOGIN] auth result={ok}') # Print the boolean result of the authentication attempt
        
        if ok: # If the credentials are valid
            # 3. GENERATE TOKEN (JWT)
            # This token securely encodes the user's identity and is signed by the server's secret key.
            token = helpers.generate_jwt(email) # Create a signed JSON Web Token for the user
            
            # 4. HANDLE API CLIENTS (Mobile App / AJAX)
            # If the request specifically asked for JSON, return the token directly.
            if request.is_json or request.accept_mimetypes.best == 'application/json': # Check if client expects JSON
                return jsonify({'token': token, 'email': email}), 200 # Return token and email as JSON response

            # 5. HANDLE BROWSER CLIENTS
            # Store primary identifier in Flask's session object (server-side signed cookie).
            session['user'] = email  # Store the user's email in the encrypted session cookie
            
            # Prepare redirect response to the home page
            resp = redirect(url_for('main.home')) # Create a redirect object pointing to the dashboard
            
            # Set a secondary 'auth_token' cookie for client-side JS or API usage if needed.
            # 'httponly=True' prevents XSS scripts from stealing the cookie.
            # 'samesite=Lax' provides CSRF protection.
            # 'secure=True' ensures cookie is only sent over HTTPS (in production).
            resp.set_cookie( # Attach a secure cookie to the response
                'auth_token', # Name of the cookie
                token, # The JWT token value
                httponly=True, # Prevent JavaScript access to this cookie for security
                samesite='Lax', # Set cookie strictness to prevent cross-site request forgery
                secure=bool(os.environ.get('COOKIE_SECURE')) # Only send over HTTPS if configured
            ) # Close set_cookie parameters
            return resp # Return the redirect with the new authentication cookie
        else: # If the credentials failed verification
            # 6. HANDLE FAILURE
            # Return email back to the template so the user doesn't have to re-type it.
            # (Good UX practice)
            
            if request.is_json or request.accept_mimetypes.best == 'application/json': # Check if client expects JSON
                return jsonify({'error': 'Invalid credentials'}), 401 # Return 401 Unauthorized error in JSON
                
            # Render page again with error message
            return render_template('login.html', error="Invalid credentials", email=email) # Reload form with error feedback
            
    # GET request: Just show the empty form
    return render_template('login.html') # Render the initial empty login form


@auth_bp.route('/signup', methods=['GET', 'POST']) # Define the registration endpoint
def signup(): # Define view function for new user account creation
    """
    Handle new user registration.
    
    Process Flow:
    1. Input Extraction: Get name, email, password from form.
    2. Validation: Check for empty fields.
    3. Duplicate Check: Query DB to ensure email is unique.
    4. Account Creation: Insert new document into 'users' collection via logic in `create_user`.
    5. Auto-Login: Set session immediately so user doesn't have to log in subsequently.
    
    Returns:
        Redirects to home on success, re-renders signup template on error.
    """
    if request.method == 'POST': # Check if the registration form was submitted
        # 1. EXTRACT FORM DATA
        name = request.form.get('name') # Get the full name from form
        email = request.form.get('email') # Get the email address from form
        password = request.form.get('password') # Get the password from form
        print(f'[SIGNUP] Registration attempt for email={email}') # Log the signup attempt
        
        # 2. BASIC VALIDATION
        # Ensure mandatory fields are present
        if not email or not password: # Validate that required fields are not empty
            return render_template('signup.html', error='Please provide email and password', name=name, email=email) # Return error for empty fields

        # 3. DATA INTEGRITY CHECK
        # Query the database (via model) to prevent duplicate accounts.
        existing = None # Initialize variable for existing user check
        try: # Start error monitoring block for DB query
            existing = users_model.get_user_by_email(email) # Check if this email is already registered in MongoDB
        except Exception: # Handle database connection errors
            # If DB error, assume None to avoid blocking user (risky but fail-open) or handle error
            existing = None # Reset to None on failure
            
        if existing: # If a user with this email already exists
            # User already exists
            return render_template('signup.html', error='Email already registered', name=name, email=email) # Return error to user

        # 4. PREPARE USER DOCUMENT
        # This dictionary mirrors the structure found in MongoDB 'users' collection.
        user_doc = { # Define the dictionary for the new user record
            'email': email, # Assign provided email
            'password': password,   # Will be hashed by create_user() later in the process
            'name': name or email,  # Fallback to email if name provided is empty
            'shopping_list': [],    # Initialize an empty list for purchases
            'total_cost': 0.0, # Initialize spending history to zero
            'seen_deals': []        # Track notifications user has dismissed to avoid repetition
        } # Close the user document dictionary
        
        # 5. CREATE ACCOUNT
        # We wrap in a retry loop for resilience (e.g. temporary network blip)
        try: # Attempt to write new user to the database
            users_model.create_user(user_doc) # Call model method to hash password and save to DB
        except Exception: # Handle initial failure
            # Retry logic: Try once more immediately
            try: # Attempt a secondary registration call
                print("[SIGNUP] First attempt failed, retrying...") # Log the retry attempt
                users_model.create_user(user_doc) # Execute the user creation again
            except Exception as e: # Handle permanent storage failure
                # Permanent failure
                print(f"[SIGNUP] Critical failure creating user: {e}") # Log the specific error exception
                return render_template('signup.html', error='Could not create user account. Please try again later.', name=name, email=email) # Return system error

        # 6. AUTO-LOGIN
        # Set session variable directly so user is immediately logged in
        session['user'] = email # Authenticate session immediately after account creation
        return redirect(url_for('main.home')) # Redirect the new user to the home dashboard

    # GET request: Show registration form
    return render_template('signup.html') # Render the empty registration form


@auth_bp.route('/shopping-list/add', methods=['POST']) # Define API endpoint to add items to a user's list
def add_shopping_item(): # Define view function for list addition
    email = helpers.get_user_email() # Get currently logged-in user email from session/token
    if not email: # If user is not authenticated
        return jsonify({'error': 'no_user_available'}), 400 # Return error message to client
    data = request.get_json() or request.form # Handle data from either JSON or URL-encoded form
    item = data.get('item') # Extract the product item object/name from the data
    # coerce form-like objects to plain dicts to avoid type surprises
    try: # Start safety wrapper for object conversion
        if not isinstance(item, dict) and hasattr(item, 'to_dict'): # If item is a custom object with to_dict method
            item = item.to_dict() # Convert custom object to dictionary
        # also allow item to be a simple string (convert to dict)
        if not isinstance(item, dict) and item is not None: # If item is a string/primitive
            # if item looks like a JSON string, try to parse
            try: # Attempt to parse JSON string
                import json # Import JSON handling module
                parsed = json.loads(item) # Parse the string into a dictionary
                if isinstance(parsed, dict): # If parsing resulted in a dictionary
                    item = parsed # Set item to the parsed dictionary
            except Exception: # If not a JSON string
                item = {'name': str(item)} # Wrap the string in a standard item dictionary
    except Exception: # Handle conversion failures
        pass # Continue with original item if conversion fails
    if not item: # If no item data was extracted
        return jsonify({'error': 'no_item_provided'}), 400 # Return error for empty item
    def _unpurchased_count(seq): # Private helper to count items still needed on list
        try: # Wrap logic to prevent calculation crashes
            return sum(1 for it in (seq or []) if not (isinstance(it, dict) and it.get('purchased'))) # Iterate and count active items
        except Exception: # Handle sequence iteration errors
            return 0 # Default to zero count

    shopping_count = 0 # Initialize the final count variable

    try: # Begin database-backed addition process
        if m.HAS_DB: # Check if MongoDB connection is active
            # If item is an object and missing a usable unit price or image, try to enrich it using Models
            try: # Attempt to find extra details for the item
                if isinstance(item, dict): # Only enrich if item is a dictionary
                    # prefer product id if provided
                    prod = None # Initialize product carrier
                    prod_id = item.get('id') or item.get('product_id') # Extract unique ID if present
                    if prod_id: # If an ID was provided
                        prod = products_model.get_product_by_id(str(prod_id)) # Fetch full product spec from DB
                    
                    # fallback: try matching by name
                    if prod is None and item.get('name'): # If ID fetch failed, use name search
                        prod = products_model.get_product_by_name(item.get('name')) # Search DB for product by title

                    # enrich from product if found
                    if prod is not None: # If we successfully matched a DB product
                        # Set image first (always enrich image if available from product)
                        try: # Safe image extraction
                            if not item.get('image'):  # Only set if item doesn't already have an image
                                if prod.get('image'): # Use primary image if set
                                    item['image'] = prod.get('image') # Update item dictionary
                                elif prod.get('images') and isinstance(prod.get('images'), list) and len(prod.get('images')): # Use image gallery
                                    item['image'] = prod.get('images')[0] # Grab first image from gallery
                        except Exception: # Ignore image failures
                            pass # Proceed without image enrichment
                        
                        # determine price from product if available
                        cheapest = get_cheapest_from_product(prod)
                        price_field = cheapest.get('price') if isinstance(cheapest, dict) else prod.get('price') # Extract numeric price
                        if price_field is None: # If price is missing from standard fields
                            try: # Try store-specific extraction
                                stores_list = prod.get('stores', []) # Get list of retailer prices
                                if stores_list and isinstance(stores_list, list): # Validate store list
                                    price_field = stores_list[0].get('price') # Grab first available retailer price
                            except Exception: # Ignore store lookup failures
                                price_field = None # Reset price field
                        # normalize to numeric unit price if found
                        if price_field is not None: # If a price string was found
                            try: # Attempt numeric conversion
                                if isinstance(price_field, (int, float)): # If already numeric
                                    unit_price = float(price_field) # Cast to float
                                else: # If formatted as string (e.g. "€3.99")
                                    cleaned = re.sub(r"[^0-9.]", "", str(price_field)) # Strip currency symbols
                                    unit_price = float(cleaned) if cleaned else 0.0 # Convert cleaned string to float
                            except Exception: # Handle conversion errors
                                unit_price = 0.0 # Default to zero
                            # set/overwrite item price with product unit price (store as Decimal128)
                            try: # Attempt to save as BSON Decimal
                                item['price'] = Decimal128(f"{unit_price:.2f}") # Format as precise monetary value
                            except Exception: # Fallback for non-BSON environments
                                item['price'] = float(unit_price) # Save as standard float
                        # ensure the item contains the product id so server-side aggregation can group correctly
                        try: # Link item back to source product
                            item['id'] = str(prod.get('id') or prod.get('_id')) # Store source ID for analytics
                        except Exception: # Ignore mapping errors
                            pass # Proceed without link
                    
                    # If product not found or still missing image, try to enrich from deals collections
                    try: # Secondary search for promotional items
                        if not item.get('image'): # Only if image is still missing
                            deal_doc = None # Initialize deal carrier
                            # Try featured_deals using model
                            pid = item.get('id') or item.get('product_id') # Extract ID
                            if pid: # If ID available
                                deal_doc = featured_deals_model.get_deal_by_id(str(pid)) # Search promoted deals
                            if deal_doc is None and item.get('name'): # Fallback to name search in deals
                                deal_doc = featured_deals_model.get_deal_by_title(item.get('name')) # Execute title search
                            
                            # Try multibuy_offers if not found using model
                            if deal_doc is None: # If still not found
                                if pid: # Use ID for multibuy lookup
                                    deal_doc = multibuy_offers_model.get_offer_by_id(str(pid)) # Search offers
                                if deal_doc is None and item.get('name'): # Search offers by name
                                    # Multibuy offers might not have title-based lookup but we can search by list if needed
                                    # For now assume id is preferred
                                    pass # Placeholder for advanced matching
                                    deal_doc = None # Ensure reset
                            # Set image from deal if available
                            if deal_doc: # If we matched a promotional deal
                                try: # Safe image assignment
                                    if deal_doc.get('image'): # Check standard image field
                                        item['image'] = deal_doc.get('image') # Apply image
                                    elif deal_doc.get('product_image'): # Check alternative image field
                                        item['image'] = deal_doc.get('product_image') # Apply image
                                except Exception: # Ignore failures
                                    pass # Proceed
                    except Exception: # Ignore deal-layer failures
                        pass # Proceed
            except Exception: # Ignore overall enrichment failure
                # enrichment should never block adding; ignore errors
                pass # Proceed directly to DB write

            # Use the multi-list structure - add to active list
            from models.users_model import get_user_lists, add_item_to_list, create_shopping_list, set_active_list # Import new list management tools
            
            # Get user's lists
            lists_data = get_user_lists(email) or {'lists': [], 'active_list_id': None} # Fetch all lists for the current user
            active_list_id = lists_data.get('active_list_id') # Identify which list is currently selected
            
            # If no active list, create a default one
            if not active_list_id: # If user has no active list set
                lists = lists_data.get('lists', []) # Get their collection of lists
                if lists: # If they have existing lists but none active
                    active_list_id = lists[0].get('id') # Select the first one automatically
                    set_active_list(email, active_list_id) # Update User preference in DB
                else: # If they have no lists at all
                    # Create a default list
                    active_list_id = create_shopping_list(email, 'My List') # Create new "My List" container
                    if active_list_id: # If creation succeeded
                        set_active_list(email, active_list_id) # Set as the user's primary list
            
            # Add item to the active list
            if active_list_id: # If we have a valid target list
                success = add_item_to_list(email, active_list_id, item) # Insert the enriched item into that specific list
                # Get updated count
                lists_data = get_user_lists(email) or {'lists': [], 'active_list_id': None} # Refresh user data from DB
                active_list = next((lst for lst in lists_data.get('lists', []) if lst.get('id') == active_list_id), None) # Locate the active list
                if active_list: # If list exists
                    shopping_count = _unpurchased_count(active_list.get('items', [])) # Re-calculate remaining item count
                else: # Default if list missing
                    shopping_count = 0 # Set count to zero
            else: # If list initialization failed
                success = False # Record operation failure
                shopping_count = 0 # Set count to zero
        else: # Fallback path for development mode without a database
            # Fallback for non-DB mode
            success = users_model.add_to_shopping_list(email, item) # Call mock model addition
            try: # Attempt count update in mock
                user_doc = users_model.get_user_by_email(email) # Fetch mock user
                shopping_count = _unpurchased_count(user_doc.get('shopping_list', [])) if user_doc else 0 # Count items in memory
            except Exception: # Ignore mock failures
                shopping_count = 0 # Default to zero
        return jsonify({'success': bool(success), 'count': shopping_count}) # Return success status and current badge count
    except Exception as e: # Catch critical runtime exceptions
        return jsonify({'error': str(e)}), 500 # Return system error 500


@auth_bp.route('/shopping-list/remove', methods=['POST']) # Define API endpoint to delete an item from the list
def remove_shopping_item(): # Define view function for list deletion
    email = helpers.get_user_email() # Identify current user
    if not email: # Check session
        return jsonify({'error': 'no_user_available'}), 400 # Return error
    data = request.get_json() or request.form # Parse input
    item = data.get('item') # Identify item to remove
    if not item: # Check input presence
        return jsonify({'error': 'no_item_provided'}), 400 # Return error
    try: # Start deletion process
        success = users_model.remove_from_shopping_list(email, item) # Call model to pull item from array in DB
        return jsonify({'success': bool(success)}) # Return success status
    except Exception as e: # Handle DB error
        return jsonify({'error': str(e)}), 500 # Return error code



@auth_bp.route('/shopping-list/update', methods=['POST']) # Define API for bulk-updating the shopping list state
def update_shopping_list_api(): # Define view function for list synchronization
    """Accept JSON payload: { items: [ {name: str, purchased: bool, qty: int, price: float, image: str}, ... ] }
    Persists the ordered list of full item objects (keeps price/image/qty/purchased).
    Backwards-compatible with older string-only lists.
    """
    email = helpers.get_user_email() # Get user identity
    if not email: # Verify login
        return jsonify({'error': 'no_user_available'}), 400 # Return error
    data = request.get_json() or {} # Parse bulk items payload
    items = data.get('items') # Extract list of items
    if not isinstance(items, list): # Validate that items is a list object
        return jsonify({'error': 'invalid_items'}), 400 # Return error for bad structure
    # For persistence we store the full item objects (dicts) when provided,
    # but allow older string-only entries as well.
    to_store = [] # Initialize storage array
    for it in items: # Iterate through each item sent from client
        if isinstance(it, dict): # If it's a structural dictionary
            # normalize keys: ensure name exists
            if 'name' not in it and 'title' in it: # Correct for inconsistent key names
                it['name'] = it.get('title') # Standardize title to name
            to_store.append(it) # Add dictionary to storage
        else: # Handle legacy string items
            to_store.append(str(it)) # Cast to string and add to storage

    try: # Persist changes to database
        users_model.update_shopping_list(email, to_store) # Overwrite current list with new synchronized list
        return jsonify({'success': True, 'items': to_store}) # Return confirmation with the stored data
    except Exception as e: # Handle persistence errors
        return jsonify({'error': str(e)}), 500 # Return 500 error


@auth_bp.route('/shopping-list/clear', methods=['POST']) # Define API endpoint to empty the shopping list
def clear_shopping_list(): # Define view function for list reset
    email = helpers.get_user_email() # Get current user
    if not email: # Check login status
        return jsonify({'error': 'no_user_available'}), 400 # Return error
    try: # Execute clear operation
        users_model.update_shopping_list(email, []) # Set the shopping_list array to empty in DB
        return jsonify({'success': True}) # Return success
    except Exception as e: # Handle DB failure
        return jsonify({'error': str(e)}), 500 # Return error


@auth_bp.route('/logout') # Define logout endpoint
def logout(): # Define view function for session termination
    session.clear() # Wipe all session data from server-side storage/cookie
    resp = redirect(url_for('main.home')) # Prepare redirect to landing page
    try: # Clean up persistent cookies
        resp.delete_cookie('auth_token') # Remove the authentication JWT cookie
    except Exception: # Ignore cookie deletion errors
        pass # Proceed with logout
    return resp # Complete logout and redirect


@auth_bp.route('/profile/update', methods=['POST']) # Define API for user profile modifications
def api_update_profile(): # Define view function for profile updates
    email = helpers.get_user_email() # Validate current user session
    if not email: # If not logged in
        return jsonify({'error': 'not_authenticated'}), 401 # Return unauthorized error
        
    data = {} # Initialize payload carrier
    if request.is_json: # Check if update is JSON
        data = request.get_json() # Parse JSON
    else: # Handle form submission
        data = request.form # Extract form data
        
    phone = data.get('phone') # Identify phone number field
    address = data.get('address') # Identify address field
    avatar = data.get('avatar') # Identify avatar image URL field
    name = data.get('name') # Identify display name field
    
    update_data = {} # Build delta for database update
    if phone is not None: update_data['phone'] = phone # Include phone in update if provided
    if address is not None: update_data['address'] = address # Include address if provided
    if avatar is not None: update_data['avatar'] = avatar # Include avatar if provided
    if name is not None: update_data['name'] = name # Include name if provided

    try: # Execute profile update
        from models.users_model import update_user_profile # Import specific profile update logic
        success = update_user_profile(email, update_data) # Update user document in MongoDB
        
        if success: # If DB write succeeded
            return jsonify({'success': True, **update_data}) # Return updated fields to client
        else: # If user not found or write failed
            return jsonify({'error': 'Failed to update profile'}), 500 # Return error
    except Exception as e: # Handle processing errors
        return jsonify({'error': str(e)}), 500 # Return error code
