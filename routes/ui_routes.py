from flask import render_template, jsonify, session, request, current_app, url_for, redirect # Import core Flask components for templates, JSON, and session management
from . import main_bp # Import the main Blueprint instance for the application's core routes
from models import models as m # Import unified models interface for database connectivity checks
from models.products_model import products_model # Import specialized product database operations
from models.stores_model import stores_model # Import specialized store database operations
from models.featured_deals_model import featured_deals_model # Import specialized deals database operations
from models.multibuy_offers_model import multibuy_offers_model # Import specialized multibuy offers database operations
from models.favorites_model import favorites_model # Import specialized favorites database operations
from models.notifications_model import notifications_model # Import specialized notifications database operations
from models.quantity_discounts_model import quantity_discounts_model # Import specialized quantity discounts database operations
from utils import helpers # Import utility helper functions for data sanitization and JWT handling
from bson.decimal128 import Decimal128 # Import BSON Decimal128 for precise monetary calculations in MongoDB
import json # Import standard JSON library for data parsing
import os # Import operating system library for file path management
import random # Import random library for data shuffling/selection
import re # Import regular expressions for string manipulation
from comparison.comparison_engine import build_best_price_summary, build_compare_product_payload

# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

# Standard category list provided by user for consistent filtering across pages
STANDARD_CATEGORIES = [ # Define the list of global product categories
    "Produce", "Pantry", "Dairy", "Meat", "Frozen", # Common grocery categories
    "Bakery", "Baby food", "Snacks", "Fast Food & To Go", # Food and snack categories
    "Household", "Beverages" # Non-food and drink categories
] # Close of category list

# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════



def load_featured_deals_fallback(): # Define a function to load local data if DB is down
    """
    Load featured deals from the static JSON fallback file.
    Used when MongoDB is unavailable during development/testing.
    Returns: List of featured deal dictionaries
    """
    try: # Start error monitoring for file reading
        path = os.path.join(current_app.root_path, 'data', 'featured_deals.json') # Construct the absolute path to the local JSON file
        with open(path, 'r', encoding='utf-8') as f: # Open the fallback file in read-only mode with UTF-8 encoding
            return json.load(f) # Parse the JSON file and return the list of deals
    except Exception as e: # Handle missing files or parsing errors
        print(f'WARNING: Failed to load featured deals fallback: {e}') # Log a warning message with the error details
        return [] # Return an empty list to prevent downstream crashes








def _mark_list_metadata(items, fav_ids=None): # Define a helper to attach UI metadata (offers, hearts) to items
    """
    Universal marker function to attach offers and favorites to a list of product items.
    """
    if not items: # Check if the input list is empty
        return items # Return unchanged if no items present
        
    # 1. Attach offer metadata using Model-based helper
    multibuy_offers_model.attach_offers_to_products(items) # Call model to inject 'Buy X Get Y' info into items
    
    # 2. Attach quantity discount metadata
    quantity_discounts_model.attach_discounts_to_products(items) # Call model to inject bulk savings info

    # 3. Mark favorites if fav_ids provided
    if fav_ids is not None: # Check if we have a set of user favorite IDs
        for item in items: # Iterate through each product in the list
            if isinstance(item, dict): # Ensure the item is a dictionary object
                item_id = str(item.get('id') or item.get('_id', '')) # Resolve the unique identifier string
                item['is_favorited'] = item_id in fav_ids # Set boolean flag for front-end heart rendering
    
    return items # Return the enriched list of products


def _normalize_account_user_data(user_data, user_email):
    """Normalize user document fields so account pages can share one view model."""
    user_data = dict(user_data or {})
    prefs_obj = user_data.get('preferences') or {}

    user_data['email'] = user_data.get('email') or user_email
    user_data['name'] = user_data.get('name') or user_email.split('@')[0]
    user_data['avatar'] = user_data.get('avatar') or ''
    user_data['preferred_stores'] = user_data.get('preferred_stores') or prefs_obj.get('preferred_stores') or []
    user_data['preferred_categories'] = user_data.get('preferred_categories') or prefs_obj.get('preferred_categories') or []
    user_data['recent_views'] = user_data.get('recent_views') or []
    return user_data


def _build_account_page_context(user_email):
    """Prepare shared data for profile, favorites, settings, and preferences pages."""
    user_data = {}
    stores_list = []
    category_options = STANDARD_CATEGORIES

    try:
        from models.users_model import get_user_by_email

        user = get_user_by_email(user_email)
        if user:
            user_data = user
        else:
            user_data = getattr(m, 'users', {}).get(user_email, {})

        user_data = _normalize_account_user_data(user_data, user_email)

        favorites = favorites_model.get_user_favorites(user_email)
        for fav in favorites:
            if not isinstance(fav, dict):
                continue
            if not fav.get('id') and fav.get('product_id'):
                fav['id'] = str(fav.get('product_id'))
            if not fav.get('name') and fav.get('product_name'):
                fav['name'] = fav.get('product_name')
            if not fav.get('image') and fav.get('product_image'):
                fav['image'] = fav.get('product_image')

        user_data['favorites'] = favorites

        all_stores = stores_model.list_stores()
        seen_names = set()
        for store in all_stores:
            store_name = store.get('name')
            if not store_name or store_name in seen_names:
                continue

            seen_names.add(store_name)
            stores_list.append({
                'name': store_name,
                'id': store.get('id'),
                'image': store.get('image') or store.get('logo'),
                'count': products_model.count_by_store(store_name),
            })

        stores_list.sort(key=lambda item: item['name'])
    except Exception as e:
        print(f"Error building account context: {e}")
        user_data = _normalize_account_user_data(getattr(m, 'users', {}).get(user_email, {}), user_email)
        user_data.setdefault('favorites', [])
        stores_list = []
        category_options = []

    return {
        'user_data': user_data,
        'stores': stores_list,
        'category_options': category_options,
    }


def _save_profile_update(user_email):
    """Persist account settings from the profile/settings forms."""
    name = request.form.get('name')
    phone = request.form.get('phone_number', '')
    address = request.form.get('address')
    avatar = request.form.get('avatar')

    update_data = {
        'name': name,
        'phone': phone,
        'address': address,
    }
    if avatar:
        update_data['avatar'] = avatar

    from models.users_model import update_user_profile
    update_user_profile(user_email, update_data)

    try:
        notifications_model.create_system_notification(
            user_email,
            'Profile Updated',
            'Your profile details have been successfully updated.',
            priority='normal'
        )
    except Exception:
        pass


@main_bp.route('/') # Define the root landing page route
def home(): # Define the view function for the dashboard
    """
    The Main Dashboard (Home) Route.
    
    Logic Flow:
    1. Authentication Check: Redirects to Entry page if not logged in.
    2. Data Aggregation: Fetches Stores, Products, and Featured Deals from DB.
    3. User Personalization: 
       - Fetches user favorites to mark items with hearts.
       - Generates recommendations based on past behavior.
    4. Fallback Handling: Uses local JSON data if MongoDB fails.
    5. Statistics: Calculates total savings and counts for badges.
    """
    # 1. AUTHENTICATION CHECK
    # Check if the 'user' key exists in the session (cookies).
    # If not, the user is not logged in.
    user_email = session.get('user') # Retrieve the current user's email from the session storage
    if not user_email: # Check if the user is currently anonymous (Guest)
        # User is Guest: Render the 'entry.html' (Login/Signup options).
        return render_template('entry.html') # Return the login/signup gateway page

    # 2. INITIALIZATION
    # Initialize all potential template variables to empty defaults.
    # We do this to ensure the template never crashes due to a missing variable, 
    # even if subsequent database calls fail.
    stores = [] # Initialize empty list for retailer data
    products = [] # Initialize empty list for general products
    featured_deals = [] # Initialize empty list for promotional items
    popular_products = [] # Initialize empty list for trending items
    store_products = [] # Initialize empty list for store-specific view
    recommended_products = [] # Initialize empty list for algorithm-based items
    favorites = [] # Initialize empty list for user's favorited items
    total_deals_count = 0 # Initialize counter for deal badges
    total_product_count = 0 # Initialize counter for catalog stats
    chosen_store_name = None # Clear any selected store filter
    max_savings = 25 # Set a default baseline for the savings display
    using_fallback = False # Track if we are currently running on mock data
    user_join_date = None # Initialize variable for account age

    # 3. GET USER JOIN DATE
    # We use this later to determine if a user gets the "NEW" badge
    # or to filter content relevant to when they joined.
    if user_email: # If a user email is present in session
        try: # Start error-safe user data retrieval
            from models.users_model import get_user_by_email # Late-import user model helper
            user_data = get_user_by_email(user_email) # Fetch full user document from DB
            if user_data: # If user was found in database
                user_join_date = user_data.get('created_at') # Save their registration timestamp
        except: # Handle potential DB connection issues silently
            # Silently fail if DB error - it's non-critical UI candy
            pass # Continue with execution

    # 4. LOAD MAIN DATA
    # We wrap everything in a TRY block because external DB calls can fail.
    try: # Start primary data aggregation block
        # Fetch list of stores available in the system
        stores = stores_model.list_stores() # Call model to get all retailer information
        # Fetch list of all products
        products = products_model.list_products() # Call model to get full product catalog
        
        # Calculate Grand Total of all active deals in the system
        # This sums up Featured Deals + Multibuy Offers + Quantity Discounts
        total_deals_count = (featured_deals_model.get_deals_count() + 
                           multibuy_offers_model.get_offers_count() + 
                           len(quantity_discounts_model.list_active_discounts())) # Aggregate count from 3 models
        
        # Fetch the actual deal objects for display
        featured_deals_list = featured_deals_model.list_featured_deals() # Get primary promotions from DB
        multibuy_offers_list = multibuy_offers_model.list_active_offers() # Get active "Buy X Get Y" offers
        quantity_discounts_list = quantity_discounts_model.list_active_discounts() # Get active bulk discounts
        
        # 4a. DEAL SEPARATION STRATEGY
        # We want to mix different types of deals (Multibuy vs Regular Discounts)
        # to show variety on the home page.
        multibuy_deals = [] # Container for quantity-based promotions
        regular_deals = [] # Container for standard percentage/price reductions
        
        # Iterate through 'Featured Deals' collection and categorize them
        for deal in featured_deals_list: # Process each document from the deals collection
            # Parse the 'offer' field to detect if it's a Buy X Get Y type deal
            offer_obj = deal.get('offer') if isinstance(deal.get('offer'), dict) else None # Check for structured offer data
            offer_str = deal.get('offer', '') if isinstance(deal.get('offer'), str) else '' # Check for text-based offer descriptions
            
            # Extract quantity parameters (X and Y)
            offer_x = offer_obj.get('x') if offer_obj else (deal.get('buy_quantity') or deal.get('multibuy_buy') or '') # Identify 'Buy' amount
            offer_y = offer_obj.get('y') if offer_obj else (deal.get('free_quantity') or deal.get('multibuy_free') or '') # Identify 'Free' amount
            
            # Determine Deal Type
            offer_type = offer_obj.get('type') if offer_obj else ('buyXgetY' if offer_x and offer_y else '') # Classify deal logic
            
            # Simple heuristic: If it says "buy" and "get"/"free", consider it a multibuy
            is_multibuy = (offer_type == 'buyXgetY') or (offer_str and ('buy' in offer_str.lower() and ('get' in offer_str.lower() or 'free' in offer_str.lower() or '+' in offer_str))) # Detect multibuy via string matching
            
            if is_multibuy: # If the logic identified a quantity-based promotion
                multibuy_deals.append(deal) # Sort into multibuy container
            else: # Otherwise
                regular_deals.append(deal) # Sort into regular discounts container
        
        # Merge specialized offer collections into the main lists
        # This unifies data from different DB collections into one UI list
        multibuy_deals.extend(multibuy_offers_list) # Add specific multibuy model results
        multibuy_deals.extend(quantity_discounts_list) # Add bulk discount model results
        
        # 4b. SELECTION LOGIC
        # We want to show a balanced mix, e.g., 5 multibuy + 5 regular deals first.
        import random # Ensure random module available for shuffling
        # Slice the first 5 of each (or all if less than 5)
        selected_multibuy = multibuy_deals[:5] if len(multibuy_deals) >= 5 else multibuy_deals # Take first 5 structured offers
        selected_regular = regular_deals[:5] if len(regular_deals) >= 5 else regular_deals # Take first 5 standard discounts
        
        # Combine the selected subsets
        featured_deals = selected_multibuy + selected_regular # Merge the two balanced subsets
        
        # Fill up the rest of the list until we hit 20 total deals
        # This ensures the page doesn't look empty if we are short on one type.
        remaining_deals = [d for d in (multibuy_deals + regular_deals) if d not in featured_deals] # Find unused deals
        if remaining_deals: # If we have more deals available
            featured_deals.extend(remaining_deals[:max(0, 20 - len(featured_deals))]) # Fill up to 20 total slots
        
        # 4c. FALLBACK FOR EMPTY DB
        # If the DB returned nothing (e.g. empty collection), force fallback mode.
        if not featured_deals: # Check if the deals list is still empty after DB queries
            using_fallback = True # Enable fallback mode due to empty data
            featured_deals = load_featured_deals_fallback() # Load the static JSON file from disk
            total_deals_count = len(featured_deals) # Update the total count based on the local file
            
    except Exception as e: # Catch any major database connection failures
        # If DB connection failed completely:
        print(f'ERROR in home route: {e}') # Log the specific error for server administrators
        using_fallback = True # Switch flag to true for UI indicators
        # Load static JSON file so the user still sees something working
        featured_deals = load_featured_deals_fallback() # Call local file loader
        total_deals_count = len(featured_deals) # Sync count with local data
    
    # 5. POST-PROCESSING: DATE FILTERING
    # Ensure we don't show deals created *before* the user joined if that's a business rule.
    # (Optional logic, currently commented out user_join_date check or loosely applied)
    if user_join_date: # Check if the user has a valid registration date
        from datetime import datetime # Late-import datetime for parsing
        # Helper to safely parse dates from various formats (Mongo objects vs Strings)
        def get_date(d): # Define a safe date extractor function
            dt = d.get('created_at') # Attempt to find the creation timestamp
            if isinstance(dt, str): # If the date is stored as a string
                try: return datetime.fromisoformat(dt) # Attempt ISO-8601 parsing
                except: return None # Return None on parsing failure
            return dt # Return as-is if already a datetime object
        
        # Filter Logic: Keep deal if it has NO date OR date is >= user join date
        featured_deals = [d for d in featured_deals if not get_date(d) or get_date(d) >= user_join_date] # Apply temporal filtering to promotions

    # 6. FETCH FAVORITES
    # We need to know which products the user has liked to color the heart icon red.
    fav_ids = set() # Initialize an empty set for efficient ID lookups
    if user_email: # Only check favorites for authenticated users
        try: # Start safety block for favorites lookup
            # Query the favorites collection for this user
            user_favs = favorites_model.get_user_favorites(user_email) # Fetch favorites list from DB
            # Create a Set of Product IDs for O(1) fast lookup
            fav_ids = {str(f.get('product_id')) for f in user_favs} # Map documents to a set of ID strings
        except Exception as e: # Handle retrieval errors
            print(f"Error loading favorites for home page: {e}") # Log the error
    
    # 7. APPLY 'IS_FAVORITED' FLAG
    # Iterate through products and deals, adding a boolean flag for the template
    for p in products: # Process global product catalog
        p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids # Mark each product as favorited or not
    for d in featured_deals: # Process active promotions
        d['is_favorited'] = str(d.get('id') or d.get('_id', '')) in fav_ids # Mark each deal as favorited or not

    # 8. FETCH POPULAR PRODUCTS
    # Shows "Trending" items.
    try: # Start request for popular items
        popular_products = products_model.get_popular_products(limit=12) # Fetch top 12 products ranked by popularity
        # Apply favorite flag to these too
        for p in popular_products: # Enrich trending products
            p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids # Mark as favorited
    except Exception as e: # Handle popularity engine failure
        print(f"Error fetching popular products: {e}") # Log failure
        # Fallback to just the first 12 products
        popular_products = products[:12] if products else [] # Use standard catalog as backup list

    # 9. USER STORE PREFERENCES
    # Fetch which stores the user likes (e.g., "Costco", "Whole Foods")
    preferred_stores = [] # Initialize empty preference list
    if user_email: # Check current authentication status
        try: # Start user profile data retrieval
            from models.users_model import get_user_by_email # Late import user logic
            user_doc = get_user_by_email(user_email) # Fetch user profile record
            if user_doc: # If user exists
                # Check nested preferences object first, then root level fallback
                prefs_obj = user_doc.get('preferences') or {} # Extract preference sub-document
                preferred_stores = prefs_obj.get('preferred_stores') or user_doc.get('preferred_stores') or [] # Combine potential preference fields
        except Exception: # Ignore non-essential lookup errors
            preferred_stores = [] # Reset to empty on failure

    # 10. CALCULATE STORE STATISTICS
    # We want to show "Whole Foods (150 items)" on the UI.
    from collections import defaultdict # Import specialized dictionary for auto-initialization

    def _norm_store(name): # Define normalization helper
        """Normalize store name for case-insensitive matching"""
        return (str(name or '').strip().lower()) # Clean, trim and lowercase string

    def _norm_compact(name): # Define fuzzy matching helper
        """Removes spaces and special characters for fuzzy matching (e.g., 'Lidl' matches 'Lidl US')"""
        return re.sub(r'[^a-zA-Z0-9]', '', str(name or '').lower()) # Strip non-alphanumeric chars

    def _norm_compact(name):
        """Prepare store name for substring matching (remove spaces/punctuation)"""
        s = _norm_store(name)
        return re.sub(r'[^a-z0-9]', '', s)

    # Initialize a dictionary that defaults to 0 for missing keys
    store_counts = defaultdict(int) # Create integer-default map
    total_product_count = 0 # Initialize global catalog item counter

    # Count products per store
    for product in products: # Iterate through everything in the core catalog
        stores_list = product.get('stores', []) # Check for multi-retailer availability
        if stores_list: # If product has a detailed store/price array
            # If product is in multiple stores, add it to the global count for each availability
            total_product_count += len(stores_list) # Increment global count by retailer availability
            for s in stores_list: # Iterate through each specific retailer offering
                store_name = s.get('store') or s.get('store_name') or s.get('name') or '' # Extract name
                norm = _norm_store(store_name) # Normalize name
                if norm: # If name is valid
                    store_counts[norm] += 1 # Increment per-store tally
        else: # Handle legacy or simplified product documents
            # Single store product
            total_product_count += 1 # Increment global count
            store_name = product.get('store') or product.get('store_name') or '' # Extract name
            norm = _norm_store(store_name) # Normalize name
            if norm: # If name is valid
                    store_counts[norm] += 1 # Increment per-store tally

    # Include Featured Deals in the store counts
    for deal in featured_deals: # Iterate through active promotions
        deal_store = deal.get('store') or deal.get('source') or '' # Identify retailer
        norm = _norm_store(deal_store) # Normalize
        if norm: # If valid
            store_counts[norm] += 1 # Add to tally
    total_product_count += len(featured_deals) # Final global count adjustment including deals

    # Update the 'stores' list objects with their counts
    for store in stores: # Iterate through the authoritative store list
        name = store.get('name') or store.get('store') or '' # Get display name
        norm = _norm_store(name) # Normalize for dict lookup
        
        # Try to get authoritative count from DB first
        store_product_count = 0 # Initialize local count
        try: # Start direct database counting
            product_count = products_model.count_by_store(name) # Count standard items in DB
            deal_count = featured_deals_model.count_by_store(name) # Count promotions in DB
            store_product_count = product_count + deal_count # Sum results
        except Exception as e: # Handle count query failure
            # Fallback to the manual counts we just calculated
            print(f'WARNING: Error counting products for {name}: {e}') # Log warning
            store_product_count = store_counts.get(norm, 0) # Use the loop-based fallback count
        
        store['product_count'] = store_product_count # Save the final count to the store object

    # 11. CHOOSE A STORE TO FEATURE
    # The home page design features a specific store's products (e.g., "Best at Aldi").
    # We try to pick a store the user likes, or just a random one.
    
    # Create a quick lookup map: key=normalized_name, value=original_name
    # Example: {'costco': 'Costco', 'wholefoods': 'Whole Foods'}
    store_lookup = {(_norm_store(s.get('name') or s.get('store') or '')): (s.get('name') or s.get('store') or '') for s in stores if (s.get('name') or s.get('store'))} # Build normalization index
    
    # Filter the user's preferred stores to only those that actually exist in our DB
    # (Removes old invalid preferences)
    candidate_norms = [_norm_store(s) for s in preferred_stores if _norm_store(s) in store_lookup] # Build validated preference list
    
    # SELECTION LOGIC:
    chosen_norm = None # Initialize target store choice
    if candidate_norms: # Check for user preferences
        # A. If user has preferences, pick one of them randomly.
        # This keeps the dashboard feeling fresh but relevant.
        chosen_norm = candidate_norms[0] if len(candidate_norms) == 1 else random.choice(candidate_norms) # Select preferred store
    elif store_lookup: # Fallback to global selection
        # B. If no preferences, pick ANY store from the database.
        chosen_norm = random.choice(list(store_lookup.keys())) # Select random existing store
        
    # Get the display name back from our lookup map
    chosen_store_name = store_lookup.get(chosen_norm) if chosen_norm else None # Convert norm back to display title

    # 12. BUILD FEATURED STORE PRODUCT LIST
    # Retrieve top 20 items for the chosen store to display in the "Brand Spotlight" section.
    if chosen_norm: # Only proceed if we have a target store
        # Pre-calculate compact normalized name to speed up the loop
        chosen_compact = _norm_compact(chosen_store_name or chosen_norm) # Fuzzy norm for better matching
        
        # Iterate through ALL products to find ones belonging to this store
        # (Note: In a huge DB, a direct MongoDB query would be faster, but this works for <10k items)
        for product in products: # Scan catalog for store items
            match_entry = None # Initialize match container
            
            # Check the 'stores' array within the product document
            # (Products often have multiple price points/stores)
            for s in product.get('stores', []) or []: # Check nested retailer availability
                store_name = s.get('store') or s.get('store_name') or s.get('name') or '' # Get item retailer
                store_norm = _norm_store(store_name) # Normalize current retailer
                store_compact = _norm_compact(store_name) # Fuzzy normalize current retailer
                
                # MATCHING LOGIC:
                # 1. Exact Name (Normalized)
                # 2. Substring Match (Compact) - handle "Lidl" matching "Lidl US"
                if store_norm == chosen_norm or (store_compact and chosen_compact and (store_compact in chosen_compact or chosen_compact in store_compact)): # Execute multi-level match
                    match_entry = s # Capture the retailer details
                    break # Stop looking once found in this product
            
            # Fallback: Check if product has a single top-level 'store' field (legacy data structure)
            if not match_entry: # If not found in detailed array
                single_store = product.get('store') or product.get('store_name') # Check root field
                if single_store: # If field exists
                    single_norm = _norm_store(single_store) # Normalize
                    single_compact = _norm_compact(single_store) # Fuzzy Normalize
                    if single_norm == chosen_norm or (single_compact and chosen_compact and (single_compact in chosen_compact or chosen_compact in single_compact)): # Match
                        # Construct a temporary object to mimic the 'stores' array format
                        match_entry = {'store': single_store, 'price': product.get('price')} # Create shim object

            # If we found a match, format the data for the UI
            if match_entry: # If product belongs to our spotlight store
                # ID Resolution: Try multiple fields to get a unique identifier
                pid = product.get('id') or product.get('_id') or product.get('product_id') or match_entry.get('product_id') or match_entry.get('id') or None # Find unique ID
                
                # Image Resolution: Valid URL > First in List > Placeholder
                image = match_entry.get('image') or product.get('image') or ((product.get('images') or [None])[0]) or url_for('static', filename='placeholder.svg') # Determine best image asset
                
                # Price Resolution: Store-specific price > Base price > 0
                price_val = match_entry.get('price') or match_entry.get('price_val') or product.get('price') or 0 # Determine relevant price
                
                # Add to display list
                store_products.append({ # Append correctly formatted product object
                    'id': str(pid) if pid is not None else None, # Stringify the ID
                    'name': product.get('name') or product.get('title') or 'Product', # Set name
                    'image': image, # Set image
                    'store': match_entry.get('store') or match_entry.get('store_name') or chosen_store_name, # Set specific store
                    'price': price_val, # Set price
                    'category': product.get('category'), # Set category
                    'unit': product.get('unit'), # Set unit (oz, lbs, etc)
                    'url': product.get('url') or match_entry.get('url') or product.get('link') or product.get('product_url') or '', # Set external link
                }) # End of product object

        # Also search FEATURED DEALS for this store and mix them in
        try: # Start safety block for promotion inclusion
            for deal in featured_deals: # Iterate through global promotion list
                deal_store = deal.get('store') or deal.get('source') or '' # Figure out retailer
                deal_norm = _norm_store(deal_store) # Normalize for match
                deal_compact = _norm_compact(deal_store) # Fuzzy normalize for match
                
                # Same matching logic as above (Exact or Substring)
                if deal_norm == chosen_norm or (deal_compact and chosen_compact and (deal_compact in chosen_compact or chosen_compact in deal_compact)): # Match?
                    did = str(deal.get('id') or deal.get('_id') or '') # Extract ID
                    dname = deal.get('name') or deal.get('title') or 'Deal' # Extract Name
                    dimg = deal.get('image') or url_for('static', filename='placeholder.svg') # Extract Image
                    dprice = deal.get('price') or deal.get('best_price') or 0 # Extract Price
                    
                    store_products.append({ # Add deal to the list
                        'id': did if did else None, # ID
                        'name': dname, # Title
                        'image': dimg, # Graphic
                        'store': deal_store or chosen_store_name, # Origin
                        'price': dprice, # Cost
                        'category': deal.get('category'), # Dept
                        'unit': deal.get('unit'), # Size
                        'url': deal.get('url') or deal.get('deal_url') or deal.get('link') or '', # Purchase link
                    }) # End of deal object
        except Exception: # Ignore failures in optional deal enrichment
            pass # Continue execution

    # Limit to a manageable number for Home section (use 'View All' page for the rest)
    store_products = store_products[:20] # Take the top 20 items for UX performance

    # 13. CALCULATE SAVINGS STATS
    # We want to show a badge like "Save up to 45% today!"
    max_savings = 0 # Start savings tracker at zero
    for deal in featured_deals: # Scan promotions
        # A. Check for pre-calculated discount_percent field
        discount = deal.get('discount_percent') # Try to find direct percentage
        if discount: # If field exists
            try: # Parse value
                discount_value = float(discount) # Convert to number
                max_savings = max(max_savings, discount_value) # Keep the highest found
            except: # Ignore parse errors
                pass # Skip this item
        
        # B. Calculate from original_price and current price if available
        original = deal.get('original_price') # Get MSRP
        current = deal.get('price') # Get offer price
        if original and current: # If we have both numbers
            try: # Start math block
                original_val = float(original) # Convert MSRP
                current_val = float(current) # Convert Price
                if original_val > 0: # Avoid division by zero
                    discount_pct = ((original_val - current_val) / original_val) * 100 # Calculate diff percentage
                    max_savings = max(max_savings, discount_pct) # Keep highest
            except: # Ignore conversion issues
                pass # Skip
    
    # Final cleanup: Round to nearest integer for clean UI
    max_savings = int(round(max_savings)) if max_savings > 0 else 25 # Default to 25% if no deals found

    # 14. LOAD USER RECOMMENDATIONS
    # Use personalized data if logged in
    try: # Start user-specific data block
        favorites = favorites_model.get_user_favorites(user_email) # Fetch user's likes
        # Normalize favorite objects to ensure templates don't crash
        for fav in favorites: # Map document fields
            if isinstance(fav, dict): # Validate object type
                if not fav.get('id') and fav.get('product_id'): # Handle ID mismatch
                    fav['id'] = str(fav['product_id']) # Bridge product_id to id
                if not fav.get('name') and fav.get('product_name'): # Handle Name mismatch
                    fav['name'] = fav.get('product_name') # Bridge field
                if not fav.get('image') and fav.get('product_image'): # Handle Image mismatch
                    fav['image'] = fav.get('product_image') # Bridge field
        
        # Compute recommendations using advanced Model method
        try: # Start recommendation engine
            from models.users_model import get_user_lists # Late import
            
            # 14.1 Analyze user habits
            # Collect shops and categories from favorites and shopping lists
            favorite_shops = [fav.get('store') for fav in favorites if fav.get('store')] # Extract shops from likes
            favorite_categories = [fav.get('category') for fav in favorites if fav.get('category')] # Extract categories from likes
            
            list_shops = [] # Target variable for shopping list stores
            list_categories = [] # Target variable for shopping list categories
            lists_data = get_user_lists(user_email) or {} # Fetch user's cart history
            for lst in (lists_data.get('lists', []) or []): # Sweep through all lists
                for item in (lst.get('items', []) or []): # Sweep through all items in list
                    if isinstance(item, dict): # Check item validity
                        if item.get('store'): list_shops.append(item.get('store')) # Log store usage
                        if item.get('category'): list_categories.append(item.get('category')) # Log category usage
            
            all_shops = favorite_shops + list_shops # Combine data points
            all_categories = favorite_categories + list_categories # Combine data points
            
            # 14.2 Query the Database for Similar Items
            # Use ProductsModel to get recommendations based on the collected signals
            recommended_products = products_model.get_recommendations(all_shops, all_categories) # Run algo
                
        except Exception as e: # Handle recommendation failure
            print(f'WARNING: Failed to compute recommendations: {e}') # Log
            recommended_products = products[:12] # Fallback to standard products
    except Exception as e: # Handle favorites retrieval failure
        print(f'WARNING: Failed to load favorites: {e}') # Log

    # 15. SYNC FAVORITE STATUS ACROSS LISTS
    # Ensure all product lists are marked with is_favorited status for the heartbeat UI
    if user_email: # Only for logged in users
        try: # Start marking process
            fav_ids = {str(f.get('product_id')) for f in favorites} # Get stringified ID set
            
            # Use helper function to bulk-mark lists (DRY principle)
            _mark_list_metadata(products, fav_ids) # Mark core catalog
            _mark_list_metadata(featured_deals, fav_ids) # Mark promotions
            _mark_list_metadata(store_products, fav_ids) # Mark spotlight products
            _mark_list_metadata(recommended_products, fav_ids) # Mark personal recs
            _mark_list_metadata(popular_products, fav_ids) # Mark trending items
        except Exception as e: # Handle marking errors
            print(f"Error marking metadata in home route: {e}") # Log 1
            print(f"Error marking favorites on home page: {e}") # Log 2

    # 16. FINAL SANITIZATION
    # Sanitize all data for template rendering to prevent ObjectId errors (BSON serialization)
    stores = helpers.sanitize_mongo_doc(stores) # Clean stores
    products = helpers.sanitize_mongo_doc(products) # Clean products
    featured_deals = helpers.sanitize_mongo_doc(featured_deals) # Clean deals
    popular_products = helpers.sanitize_mongo_doc(popular_products) # Clean trending
    recommended_products = helpers.sanitize_mongo_doc(recommended_products) # Clean recs
    store_products = helpers.sanitize_mongo_doc(store_products) # Clean spotlight
    favorites = helpers.sanitize_mongo_doc(favorites) # Clean favorites

    # 17. RENDER TEMPLATE
    return render_template('home.html', # Load the home layout
                         stores=stores, # Pass data
                         products=products, # Pass data
                         featured_deals=featured_deals, # Pass data
                         popular_products=popular_products, # Pass data
                         total_deals_count=total_deals_count, # Pass count
                         favorites=favorites, # Pass likes
                         recommended_products=recommended_products, # Pass personal recs
                         store_products=store_products, # Pass spotlight
                         chosen_store_name=chosen_store_name, # Pass choice
                         using_fallback=using_fallback, # Pass status
                         total_product_count=total_product_count, # Pass total
                         max_savings=max_savings, # Pass savings percentage
                         user_join_date=user_join_date) # Pass join date



@main_bp.route('/stores') # Define URL for store listing
def stores_page(): # Entry point for stores page
    """
    Stores Directory Page.
    
    Displays a grid of all available stores with their product counts.
    
    Data Flow:
    1. Fetch all store documents from MongoDB.
    2. For each store, calculate real-time inventory stats:
       - Count of regular products.
       - Count of featured deals.
    3. Render 'stores.html' with the enriched data.
    """
    using_fallback = False # Initialize fallback flag
    try: # Start store data retrieval
        # Fetch basic store info (name, logo, description)
        stores = stores_model.list_stores() # Get stores from DB
        
        # Enrich with live statistics
        for s in stores: # Iterate through each retailer
            store_name = s.get('name', '') # Get store identity
            
            # Execute two count queries per store
            # OPTIMIZATION NOTE: In high-scale apps, this N+1 query pattern 
            # might be slow. Consider aggregation pipelines [$lookup] instead.
            product_count = products_model.count_by_store(store_name) # Query catalog count
            deals_count = featured_deals_model.count_by_store(store_name) # Query promo count
            
            # Add 'product_count' field for the frontend badge
            s['product_count'] = product_count + deals_count # Store the sum
            
    except Exception as e: # Handle DB error
        print(f"Error fetching stores with counts: {e}") # Log failure
        # If DB fails, we might show empty list or fallback data if configured
    
    # Prepare filter options for the UI
    category_options = [{"name": cat} for cat in STANDARD_CATEGORIES] # Format categories for select box
    
    # Convert BSON types (ObjectId) to strings for Jinja2 compatibility
    stores = helpers.sanitize_mongo_doc(stores) # Run final cleanup

    return render_template('stores.html', # Render the view
                         stores=stores, # Pass store list
                         using_fallback=using_fallback, # Pass status
                         category_options=category_options)



@main_bp.route('/stores/<store_name>') # Dynamic path for specific retailer products
def store_products_page(store_name): # Logic to handle per-store inventory browsing
    """Display all products for a specific store."""
    products = [] # Initialize results container
    store_info = None # Initialize store metadata container
    
    try: # Start primary data retrieval (Database)
        # Get store info (Logo, banner, description) using Model
        store_info = stores_model.get_store_by_name(store_name) # Fetch profile
        
        # Get products for this store using specialized Model query
        prod_docs = products_model.find_by_store(store_name) # Search product collection
        
        for prod in prod_docs: # Process each found document
            # Extract matched store data from the nested 'stores' array
            matched_stores = [s for s in (prod.get('stores') or []) 
                            if (s.get('store') or '').lower() == store_name.lower()] # Find exact price entry
            if matched_stores: # If specific price entry exists
                prod['store_price'] = matched_stores[0].get('price') # Prefer store-specific price
                prod['store_image'] = matched_stores[0].get('image') or prod.get('image') # Prefer store-specific image
                # Extract URL from store entry if available (Deep links)
                if matched_stores[0].get('url'): # Check for link
                    prod['url'] = matched_stores[0].get('url') # Assign deep link
            else: # Fallback for flat data structures
                prod['store_price'] = prod.get('price') # Use root price
                prod['store_image'] = prod.get('image') # Use root image
            products.append(prod) # Add processed item to list
        
        # Also get active Promotions (featured deals) for this store
        deals_docs = featured_deals_model.find_by_store(store_name) # Search promotion collection
        
        for deal in deals_docs: # Process found promotions
            # Normalization: Use deal's name field as 'name' for consistency across templates
            if 'title' in deal and 'name' not in deal: # Field bridge
                deal['name'] = deal['title'] # Sync field
            # Set store-specific identifiers for the card component
            deal['store_price'] = deal.get('price') # Map price
            deal['store_image'] = deal.get('image') # Map image
            products.append(deal) # Merge promotion into main product list

        # Enrichment: Get Quantity Discounts (e.g. "2 for $5") for this retailer
        try: # Start safety wrapper for secondary feature
            qd_all = quantity_discounts_model.list_active_discounts() # Fetch all discounts
            for qd in qd_all: # Filter results in memory
                if (qd.get('store') or '').lower() == store_name.lower(): # Match retailer
                     if 'title' in qd and 'name' not in qd: # Normalize
                         qd['name'] = qd['title'] # Bridge name
                     qd['store_price'] = qd.get('price') # Map price
                     qd['store_image'] = qd.get('image') # Map image
                     products.append(qd) # Add to list
        except Exception as e: # Handle secondary query failure
            print(f"Error merging quantity discounts: {e}") # Log warning

        # User Personalization: Check which items are already in favorites
        user_email = session.get('user') # Get current user identity
        fav_ids = set() # Initialize lookup set
        if user_email: # Only fetch for logged in users
            try: # Start favorites lookup
                user_favs = favorites_model.get_user_favorites(user_email) # Query DB
                fav_ids = {str(f.get('product_id')) for f in user_favs} # Create ID set for O(1) matching
            except Exception as e: # Handle favorites failure
                print(f"Error loading favorites for store products: {e}") # Log error
        
        for p in products: # Apply flags
            p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids # Mark favorites
        
        # Final Enrichment: Attach offers and additional metadata using core marking helper
        _mark_list_metadata(products, fav_ids) # Standardize all items for UI consistency

    except Exception as e: # Handle critical database failure
        print(f'ERROR loading products for {store_name}: {e}') # Log hard error

    # FALLBACK LOGIC: 
    # Use in-memory data and JSON files when DB is unavailable or returned nothing.
    try: # Start fallback wrapper
        if not products: # Trigger if DB returned nothing
            store_lc = store_name.lower() # Case-insensitive seed

            # A. Scan internal mock data
            for prod in getattr(m, 'products', []): # Access memory-stored items
                matched_stores = [s for s in (prod.get('stores') or [])
                                  if (s.get('store') or s.get('name') or '').lower() == store_lc] # Check price matrix
                top_level_match = isinstance(prod.get('store'), str) and prod.get('store', '').lower() == store_lc # Check flat field
                if matched_stores or top_level_match: # If found in mocks
                    shaped = dict(prod) # Copy
                    if '_id' in shaped: # Handle ID
                        shaped['id'] = str(shaped['_id']) # Stringify
                    shaped['store_price'] = matched_stores[0].get('price') if matched_stores else prod.get('price') # Map price
                    shaped['store_image'] = matched_stores[0].get('image') if matched_stores else prod.get('image') # Map image
                    if matched_stores and matched_stores[0].get('url'): # Map external link
                        shaped['url'] = matched_stores[0].get('url') # Map URL
                    products.append(shaped) # Add item

            # B. Scan featured deals fallback JSON
            for deal in load_featured_deals_fallback(): # Access static file
                deal_store = (deal.get('store') or deal.get('source') or '').lower() # Get retailer
                if deal_store == store_lc: # Check match
                    shaped = dict(deal) # Copy
                    if '_id' in shaped: # Handle ID
                        shaped['id'] = str(shaped['_id']) # Stringify
                    products.append(shaped) # Add promotion
    except Exception as e: # Handle fallback failure
        print(f'ERROR loading fallback products for {store_name}: {e}') # Log
    
    # Re-apply favorited status to fallback products
    user_email = session.get('user') # Identity
    fav_ids = set() # Set
    if user_email: # Auth check
        try: # Try DB
            from models.favorites_model import get_user_favorites # Helper
            user_favs = get_user_favorites(user_email) # Fetch
            fav_ids = {str(f.get('product_id')) for f in user_favs} # Build set
        except Exception: # Ignore
            pass # Continue
            
    for p in products: # Scan all
        if 'is_favorited' not in p: # If missing
            p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids # Re-mark
    
    # 3. GET UI FILTERS
    category_options = [{"name": cat} for cat in STANDARD_CATEGORIES] # Map categories
    
    # 4. FINAL CLEANUP
    products = helpers.sanitize_mongo_doc(products) # Clean list
    store_info = helpers.sanitize_mongo_doc(store_info) # Clean metadata
    
    return render_template('store_products.html', # Render
                         store_name=store_name, # Pass
                         store=store_info, # Pass
                         products=products, # Pass
                         product_count=len(products), # Pass
                         category_options=category_options) # Pass



@main_bp.route('/featured-deals') # Define URL for promotions
def featured_deals_page(): # Entry point for Deals gallery
    """
    Deals & Offers Page.
    
    Aggregates special offers from three sources:
    1. Featured Deals: Single item discounts (e.g., 20% off).
    2. Multibuy Offers: Quantity-based deals (e.g., Buy 1 Get 1 Free).
    3. Quantity Discounts: Bulk purchase price drops.
    """
    using_fallback = False # DB flag
    per_page = 30 # Page size
    try: # Parse page
        page = int(request.args.get('page', 1)) # Get ?page=
    except Exception: # Handle bad input
        page = 1 # Start
    page = max(page, 1) # Force positive

    category_filter = (request.args.get('category') or '').strip() # e.g. ?category=Produce
    search_query = (request.args.get('search') or '').strip() # e.g. ?search=Milk
    user_email = session.get('user') # Auth check
    
    deals = [] # Init results
    category_options = [] # Init filters
    fav_ids = set() # Init likes

    # 1. FETCH ALL ACTIVE DEALS
    try: # Start sweep
        featured_deals_list = featured_deals_model.list_featured_deals() # Get core deals
        multibuy_offers_list = multibuy_offers_model.list_active_offers() # Get multi-item
        quantity_discounts_list = quantity_discounts_model.list_active_discounts() # Get bulk price
        deals = featured_deals_list + multibuy_offers_list + quantity_discounts_list # Combine
    except Exception as e: # Handle failure
        print(f'WARNING: Model query failed for deals: {e}') # Log
        using_fallback = True # Visual flag
        deals = load_featured_deals_fallback() # JSON backup

    # 2. POPULATE SIDEBAR FILTERS
    try: # Category stats
        cat_counts = products_model.get_category_counts() # DB query
        category_options = [{"name": cat, "count": cat_counts.get(cat, 0)} for cat in STANDARD_CATEGORIES] # Build options
    except Exception as e: # Handle failure
        print(f"Error getting categories for deals: {e}") # Log
        category_options = [] # Hide badges

    # 3. APPLY IN-MEMORY FILTERING
    if category_filter: # Category pick
        deals = [d for d in deals if category_filter.lower() in (d.get('category') or '').lower()] # Filter
    
    if search_query: # Keyword search
        sq = search_query.lower() # Case seed
        deals = [d for d in deals if sq in (d.get('title') or d.get('name') or '').lower() or 
                sq in (d.get('store') or '').lower() or 
                sq in (d.get('category') or '').lower() or
                sq in (d.get('description') or '').lower()] # Match any field

    # 4. Load Favorites
    if user_email:
        try:
            user_favs = favorites_model.get_user_favorites(user_email)
            fav_ids = {str(f.get('product_id')) for f in user_favs}
        except Exception as e:
            print(f"Error loading favorites for deals page: {e}")
    
    # 5. Attach Metadata
    _mark_list_metadata(deals, fav_ids)
    
    # 6. Notifications logic
    if user_email and deals and not using_fallback:
        try:
            notifications_model.cleanup_old_notifications(7)
            from models.users_model import get_user_by_email, update_user
            user = get_user_by_email(user_email)
            if user:
                current_deal_ids = [str(d.get('id') or d.get('_id')) for d in deals]
                if 'seen_deals' not in user:
                    update_user(user_email, {'seen_deals': current_deal_ids})
                else:
                    seen_deals = set(user.get('seen_deals', []))
                    new_deal_ids = []
                    for deal in deals:
                        deal_id = str(deal.get('id') or deal.get('_id'))
                        if deal_id and deal_id not in seen_deals:
                            deal_title = deal.get('title') or deal.get('name', 'New Deal')
                            store_name = deal.get('store', '')
                            notifications_model.create_notification({
                                'user_email': user_email,
                                'type': 'new_deal',
                                'title': 'New Deal Available!',
                                'message': f'{deal_title}{" at " + store_name if store_name else ""}',
                                'deal_id': deal_id,
                                'store_name': store_name,
                                'action_url': f'/featured-deal/{deal_id}',
                                'priority': 'normal'
                            })
                            new_deal_ids.append(deal_id)
                    if new_deal_ids:
                        update_user(user_email, {'seen_deals': current_deal_ids})
        except Exception as e:
            print(f'WARNING: Failed notifications: {e}')
    
    # Sort deals by discount percentage (highest first)
    def get_sort_key(deal):
        discount = 0
        if deal.get('discount_percent'):
            try: discount = float(deal.get('discount_percent'))
            except: pass
        else:
            original = deal.get('original_price')
            current = deal.get('price')
            if original and current:
                try:
                    original_val = float(original)
                    current_val = float(current)
                    if original_val > 0:
                        discount = ((original_val - current_val) / original_val) * 100
                except: pass
        return -discount 
    
    deals.sort(key=get_sort_key)

    # Implement Pagination metadata
    total_products = len(deals)
    total_pages = (total_products + per_page - 1) // per_page if total_products else 1
    page = min(page, total_pages) if total_products else 1
    
    showing_start = (page - 1) * per_page + 1 if total_products else 0
    showing_end = min(page * per_page, total_products)
    
    # Slice deals for the current page
    paginated_deals = deals[(page - 1) * per_page: page * per_page]
    
    return render_template('featured_deals.html', 
                          deals=paginated_deals, 
                          total_products=total_products,
                          total_pages=total_pages,
                          current_page=page,
                          showing_start=showing_start,
                          showing_end=showing_end,
                          category_filter=category_filter,
                          category_options=category_options,
                          search_query=search_query,
                          using_fallback=using_fallback)



@main_bp.route('/compare-prices')
def compare_prices():
    """
    Core Feature: Price Comparison Engine.
    
    This route handles the complex logic of displaying products with:
    1. Filtering: By Category (e.g., 'Dairy', 'Meat').
    2. Searching: By name, store, or description (RegEx based).
    3. Pagination: Server-side pagination to handle large datasets efficiently.
       - Formula: skip = (page - 1) * per_page
    4. Data Enrichment: Adds real store logos and 'favorited' status to each item.
    """
    per_page = 30
    try:
        page = int(request.args.get('page', 1))
    except Exception:
        page = 1
    page = max(page, 1)

    category_filter = (request.args.get('category') or '').strip()
    search_query = (request.args.get('search') or '').strip()

    total_products = 0
    total_pages = 1
    products = []
    deals = []
    stores = []
    category_options = []

    try:
        query = {}
        if category_filter:
            query['category'] = {'$regex': f"^{re.escape(category_filter)}$", '$options': 'i'}
        
        product_query = dict(query)
        if search_query:
            search_regex = {'$regex': re.escape(search_query), '$options': 'i'}
            product_query['$or'] = [
                {'name': search_regex},
                {'title': search_regex},
                {'category': search_regex},
                {'stores.store': search_regex},
                {'stores.name': search_regex}
            ]
        
        # 4. EXECUTE MODEL QUERY
        # Using simplified logic from logic model for clean abstraction
        total_products = products_model.count_products(product_query)
        
        total_pages = (total_products + per_page - 1) // per_page if total_products else 1 # Calc total pagination pages
        page = min(page, total_pages) if total_products else 1 # Bounds checking for current page
        skip_amount = (page - 1) * per_page # Calc offset for MongoDB [skip]
        
        # Fetch the results for the current page
        products = products_model.list_products( # Execute paginated search
            query=product_query, # Pass filters/search regex
            skip=skip_amount, # Pass offset
            limit=per_page # Pass page size
        )
        
        # 5. DATA ENRICHMENT: RETAILER LOGOS
        # Our product documents only store store name strings. 
        # We need to attach actual logo URLs from the stores collection.
        db_stores = stores_model.list_stores() # Fetch all store metadata for cross-referencing
            
        def find_store_logo_and_image(store_name, db_stores): # Define matching helper
            """Finds logo/image assets for a given store name from the metadata list"""
            norm = lambda n: (n or '').strip().lower() # Normalization lambda
            for s in db_stores: # Scan metadata
                if norm(s.get('name')) == norm(store_name) or norm(s.get('store')) == norm(store_name): # Match?
                    return s.get('logo'), s.get('image') or s.get('store_image') # Return assets
            return None, None # Fallback
            
        for p in products: # Process each product in result set
            product_img = p.get('image') or (p.get('images')[0] if p.get('images') else None) # Determine primary product image
            for s in (p.get('stores') or []): # Iterate through retailer availability array
                store_name = s.get('store') or s.get('store_name') or s.get('name') # Identify retailer
                logo, img = find_store_logo_and_image(store_name, db_stores) # Look up assets
                
                # Attach real store logos/images for UI display
                if logo: s['logo'] = logo # Bind logo
                if img: s['store_image'] = img # Bind hero image
                
                # CLEANUP: If the store entry's 'image' is actually just the product image, clear it
                # to avoid it being used as a redundant store logo in the frontend
                if s.get('image') and s.get('image') == product_img: # Check for duplication
                    s['image'] = None # Clear redundant field

        # 6. USER CONTEXT: FAVORITES & OFFERS
        # Mark favorites and attach active offers using the automated marking helper
        user_email = session.get('user') # Identity check
        fav_ids = set() # ID set
        if user_email: # Auth check
            try: # Start safety block
                user_favs = favorites_model.get_user_favorites(user_email) # Query DB for likes
                fav_ids = {str(f.get('product_id')) for f in user_favs} # Build set for O(1) matching
            except Exception as e: # Handle retrieval failure
                print(f"Error loading favorites for compare page: {e}") # Log error
        
        # Use helper method to bulk-mark products (Dry Principle)
        _mark_list_metadata(products, fav_ids) # Apply heart icons and discount badges

        # 7. POPULATE SIDEBAR FILTERS
        cat_counts = products_model.get_category_counts() # Query DB for item counts per department
        category_options = [{"name": cat, "count": cat_counts.get(cat, 0)} for cat in STANDARD_CATEGORIES] # Map counts to names

        # 8. EXTENDED SEARCH RESULTS (DEALS & STORES)
        # If the user performed a search, we also look for related deals and stores
        if search_query: # Check for active search
            try: # Start sweep
                # Search all three promotion types
                all_deals = (featured_deals_model.list_featured_deals() + 
                           multibuy_offers_model.list_active_offers() + 
                           quantity_discounts_model.list_active_discounts()) # Merge promotion lists
                # Perform in-memory fuzzy match for keywords
                deals = [d for d in all_deals if search_query.lower() in (d.get('title') or d.get('name') or '').lower() or search_query.lower() in (d.get('store') or '').lower()] # Match deals
                
                # Search the store directory for matches
                all_stores = stores_model.list_stores() # Get all retailers
                stores = [s for s in all_stores if search_query.lower() in (s.get('name') or '').lower() or search_query.lower() in (s.get('description') or '').lower()] # Match retailers
            except: # Ignore failure in secondary results
                pass # Keep empty lists

    except Exception as e: # Handle critical engine failure
        print(f'ERROR in compare_prices route: {e}') # Log hard error
        # Minimal emergency fallback to prevent 500 status
        products = getattr(m, 'products', [])[:30] # Use first 30 mock items
        total_products = len(products) # Set count
        total_pages = 1 # Set pages

    # 9. OUTPUT PAGINATION METADATA
    has_prev = page > 1 # Bool for 'Back' button
    has_next = page < total_pages # Bool for 'Next' button
    showing_start = ((page - 1) * per_page) + 1 if total_products else 0 # Status text e.g. "Showing 1..."
    showing_end = min(page * per_page, total_products) # Status text e.g. "...to 30"

    # 10. RENDER VIEW
    return render_template( # Load layout
        'compare_prices.html', # Template file
        products=products, # Primary item list
        deals=deals, # Matched promotions
        stores=stores, # Matched retailers
        using_fallback=(len(products) == 0 or total_products == 0), # Empty state flag
        page=page, # Current index
        per_page=per_page, # Items per request
        total_products=total_products, # Global result count
        total_pages=total_pages, # Total partitions
        has_prev=has_prev, # UI Control
        has_next=has_next, # UI Control
        showing_start=showing_start, # UI Label
        showing_end=showing_end, # UI Label
        category_filter=category_filter, # Active state
        search_query=search_query, # Active state
        category_options=category_options, # Sidebar items
    )



@main_bp.route('/product/<product_id>') # Dynamic path for product specification
def product_detail(product_id): # Logic for single item detail view
    """Display deep-dive information for a single product."""
    product = None # Init container
    requested_store = request.args.get('store') # Optional filter from URL
    
    # 1. FETCH PRODUCT DATA
    # We check multiple sources starting from most authoritative.
    try: # Start DB lookup
        # A. Check standard products collection
        product = products_model.get_product_by_id(product_id) # Direct ID query
        
        # B. If not found in primary, check promotions collection
        if not product: # Miss?
            product = featured_deals_model.get_deal_by_id(product_id) # Search deals
            
    except Exception as e: # Handle lookup error
        print(f'Error fetching product using Models: {e}') # Log
    

    # 2. EMERGENCY FALLBACK: JSON DATA
    # Use static files if DB is down or item is missing.
    if not product: # Still missing?
        featured_deals = load_featured_deals_fallback() # Load disk JSON
        for deal in featured_deals: # Scan items
            if deal.get('id') == product_id: # Match ID?
                product = deal # Capture
                break # Stop scan

    # 3. EMERGENCY FALLBACK: MOCK MEMORY
    if not product: # Still missing?
        from models import models as m # Import legacy mocks
        for prod in getattr(m, 'products', []): # Scan constant list
            if prod.get('id') == product_id: # Match?
                product = prod # Capture
                break # Stop

    # If item doesn't exist anywhere, return standard Not Found
    if not product: # Total miss?
        return render_template('404.html'), 404 # Failure exit

    # 4. ATTACH ACTIVE PROMOTIONS
    # Use model helpers to find BOGO or Bulk deals for this specific item
    multibuy_offers_model.attach_offers_to_products([product]) # Map multibuys
    quantity_discounts_model.attach_discounts_to_products([product]) # Map quantity tiers

    # 5. DATA STRUCTURE NORMALIZATION
    # Products and Deals have slightly different shapes; we unify them for the template.
    if not product.get('stores'): # If item is from a single-source deal list
        store_name = product.get('store') or product.get('source') or 'Store' # Root retailer
        price_val = product.get('price') or product.get('best_price') or product.get('original_price') or 'N/A' # Root price
        # Create a shim 'stores' array to match the standard catalog format
        product['stores'] = [{ # Single entry list
            'store': store_name, # Retailer
            'price': price_val, # Cost
            'image': product.get('image') # Visual
        }] # End shim
    
    # 6. ASSET ENRICHMENT (RETAILER LOGOS)
    stores_list = product.get('stores') or [] # Access retailers
    db_stores = stores_model.list_stores() # Get all store metadata
    
    def find_store_logo_and_image(store_name, db_stores): # Match function
        norm = lambda n: (n or '').strip().lower() # Normalize
        for s in db_stores: # Scan
            if norm(s.get('name')) == norm(store_name) or norm(s.get('store')) == norm(store_name): # Match?
                return s.get('logo'), s.get('image') or s.get('store_image') # Return logos
        return None, None # Fallback
    for s in stores_list: # Enrich each availability entry
        store_name = s.get('store') or s.get('store_name') or s.get('name') # Item identity
        logo, image = find_store_logo_and_image(store_name, db_stores) # Fetch assets
        if logo: # Found logo?
            s['logo'] = logo # Bind
        if image: # Found hero?
            # Assign store hero image as background or auxiliary graphic
            s['store_display_image'] = image # Bind

    # 7. MARKET ANALYSIS: FIND BEST PRICE VIA SHARED ENGINE
    best_price_value = None
    best_price_stores = []
    try:
        compare_payload = build_compare_product_payload(product)
        best_price_value, best_price_stores = build_best_price_summary(compare_payload)
    except Exception:
        best_price_value = None
        best_price_stores = []

    # 8. USER STATUS: FAVORITES
    is_favorited = False # Default state
    user_email = session.get('user') # Identity
    if user_email: # Auth check
        try: # Check DB
            from models.favorites_model import is_favorited as check_fav # Direct model helper
            is_favorited = check_fav(user_email, str(product.get('id') or product.get('_id', ''))) # Run bool check
        except Exception as e: # Handle failure
            print(f"Error checking favorites for product_detail: {e}") # Log error

    # 9. RENDER VIEW
    return render_template('product_detail.html', product=product, best_price_value=best_price_value, best_price_stores=best_price_stores, is_favorited=is_favorited)




@main_bp.route('/featured-deal/<deal_id>') # Unique path for promotion specifics
def featured_deal_detail(deal_id): # Entry for single promotion page
    """Display a single featured deal with deep store linking."""
    deal = None # Init target

    # 1. FETCH DEAL DATA
    # We check three separate promotion collections.
    try: # Start DB sweep
        # A. Check standard price-drop collection
        deal = featured_deals_model.get_deal_by_id(deal_id) # Search
        
        # B. If miss, check Buy X Get Y collection
        if not deal: # Missing?
            deal = multibuy_offers_model.get_offer_by_id(deal_id) # Search
            
        # C. If miss, check Bulk discount collection
        if not deal: # Still missing?
            deal = quantity_discounts_model.get_discount_by_id(deal_id) # Search
            
        if deal: # Found something?
            # ------------------------------------------------------------------
            # NORMALIZE DEAL OBJECT 
            # Sub-documents vary by source; we standardize them for a single UI template.
            # ------------------------------------------------------------------
            
            # 1. Normalize Title/Name
            if not deal.get('title'): # Ensure display label
                deal['title'] = deal.get('product_name') or deal.get('name') or "Special Offer" # Field priority
            
            # 2. Normalize Price
            if deal.get('price') is None: # Ensure cost is present
                deal['price'] = deal.get('base_price') or deal.get('new_price') # Field priority
            
            # 3. Normalize Original Price (if applicable)
            if deal.get('original_price') is None: # Ensure baseline is present
                deal['original_price'] = deal.get('old_price') # Field priority

            # 4. Normalize Image (Ensure it exists)
            # If deal record is missing a photo, we try to pull it from the core product catalog.
            if not deal.get('image') and deal.get('product_id'): # Check for link
                try: # Start product lookup
                    p = products_model.get_product_by_id(str(deal['product_id'])) # Fetch core item
                    if p: # Found?
                        deal['image'] = p.get('image') or p.get('image_url') # Inherit graphic
                        # Also backfill other metadata if deal record is sparse
                        if not deal.get('category'): deal['category'] = p.get('category') # Inherit dept
                        if not deal.get('unit'): deal['unit'] = p.get('unit') # Inherit size
                except: # Ignore backdrop failures
                    pass # Keep going

            # 5. CONSTRUCT OFFER LABELS
            # Formulate human-readable text from raw numeric tiers.
            if not deal.get('offer') and not deal.get('discount_label'): # Sparse label?
                if deal.get('discount_tiers'): # Case: Bulk Tiers
                    tiers = deal.get('discount_tiers') # Access array
                    if tiers and len(tiers) > 0: # Has entries?
                        first = tiers[0] # Take primary discount
                        qty = first.get('quantity') or first.get('min_qty') # Determine threshold
                        disc = first.get('discount') or first.get('discount_percentage') or first.get('discount_percent') # Determine savings
                        if qty and disc: # Data valid?
                            deal['offer'] = f"Buy {qty}+ Save {disc}%" # Build sentence
                            deal['discount_label'] = f"Save {disc}%" # Build badge
                elif deal.get('buy_quantity') and deal.get('free_quantity'): # Case: BOGO/Multibuy
                     deal['discount_label'] = f"{deal['buy_quantity']}+{deal['free_quantity']}" # Build badge
                     deal['offer'] = f"Buy {deal['buy_quantity']} Get {deal['free_quantity']} Free" # Build sentence

            # If deal target URL is missing, we try to inherit it from the core product link
            if (not deal.get('url') and not deal.get('link') and not deal.get('product_url') and not deal.get('store_url')): # Total URL miss?
                 product_id = deal.get('product_id') # Identify parent
                 if product_id: # Has parent?
                     try: # Start lookup
                         prod = products_model.get_product_by_id(str(product_id)) # Fetch parent
                         if prod: # Found parent?
                             # Try to find URL for the specific store mention in the deal
                             deal_store = deal.get('store') or deal.get('source') # Target retailer
                             found_url = None # URL holder
                             
                             if deal_store and prod.get('stores'): # Has candidate list?
                                 for s in prod.get('stores', []): # Scan retailer availability
                                     s_name = s.get('store') or s.get('name') # Entry name
                                     if s_name and deal_store.lower() in s_name.lower(): # Match?
                                         found_url = s.get('url') or s.get('link') or s.get('product_url') # Capture link
                                         break # Stop search
                             
                             # If not found for specific store, use any available URL as best-effort
                             if not found_url and prod.get('stores'): # Still missing?
                                 first_store = prod.get('stores')[0] # Take first entry
                                 found_url = first_store.get('url') or first_store.get('link') or first_store.get('product_url') # Capture link
                             
                             if found_url: # Found something?
                                 deal['url'] = found_url # Bind URL to deal
                     except Exception as e: # Handle parent lookup failure
                         print(f"Error fetching product url for deal: {e}") # Log error

            # Attach any active multibuy/quantity offers using Model-based helper (Secondary enrichment)
            multibuy_offers_model.attach_offers_to_products([deal]) # Sync offers
            
            # Check if favorited using Model
            is_favorited = False # Default state
            user_email = session.get('user') # Identity
            if user_email: # Auth check
                try: # Start safety block
                    product_id = str(deal.get('_id') or deal.get('id')) # Identify
                    is_favorited = favorites_model.is_favorited(user_email, product_id) # Run check
                except Exception as e: # Handle check failure
                    print(f"Error checking favorites for featured_deal_detail: {e}") # Log error
    except Exception as e: # Handle critical documentation retrieval failure
        print(f'ERROR loading featured deal {deal_id}: {e}') # Log hard error

    # 2. EMERGENCY FALLBACK
    if deal is None: # Missed in DB?
        all_deals = load_featured_deals_fallback() # Load JSON from disk
        for d in all_deals: # Scan static file
            if str(d.get('id')) == str(deal_id) or str(d.get('_id', '')) == str(deal_id): # Match?
                deal = d # Capture
                break # Stop
        
        # Re-check favorite status for fallback data
        if deal: # Found in JSON?
            user_email = session.get('user') # Identity
            if user_email: # Auth check
                try: # Start check
                    product_id = str(deal.get('_id') or deal.get('id')) # Identify
                    is_favorited = favorites_model.is_favorited(user_email, product_id) # Run check
                except: # Ignore failures here
                    pass # Continue

    # Final validation before rendering
    if deal is None: # Still missing?
        return render_template('404.html'), 404 # Failure exit

    # 3. RENDER VIEW
    return render_template('featured_deal_detail.html', deal=deal, is_favorited=is_favorited)




@main_bp.route('/product-info/<product_id>') # Simplified info path
def product_info(product_id): # Entry for lightweight product drawer
    """Simple product info page showing just description and unit details."""
    product = None # Init container
    
    # Extract contextual info from query parameters (Passed from complex product cards)
    store_name = request.args.get('store_name', '') # Retailer context
    store_price = request.args.get('store_price', '') # Price context
    
    # 1. FETCH DATA (DATABASE)
    try: # Start sweep
        # A. Check standard catalog
        product = products_model.get_product_by_id(product_id) # Query
        
        # B. Check promotion catalog
        if not product: # Miss?
            product = featured_deals_model.get_deal_by_id(product_id) # Query

        # C. Check buy-X-get-Y catalog
        if not product: # Miss?
            product = multibuy_offers_model.get_offer_by_id(product_id) # Query

        # D. Check bulk discount catalog
        if not product: # Still missing?
            try: # Nested safety
                product = quantity_discounts_model.get_discount_by_id(product_id) # Query
            except Exception: # Ignore
                pass # Next
        
        # 2. DATA ENRICHMENT (PARENT LINKING)
        # If found in specialized collections (multibuy/discount) but missing details, 
        # try to fetch parent product to fill in gaps (name, image, etc.)
        if product and (not product.get('name') or not product.get('image')): # Sparse data?
            parent_id = product.get('product_id') or product.get('product_parent_id') # Identify parent
            if parent_id: # Has ancestor?
                try: # Start ancestry lookup
                    # Handle ObjectId conversion if necessary
                    if not isinstance(parent_id, str): # Raw BSON?
                        parent_id = str(parent_id) # Stringify
                        
                    parent_product = products_model.get_product_by_id(parent_id) # Fetch parent
                    if parent_product: # Found parent?
                        # Merge parent data into the discount object without overwriting unique keys
                        for k, v in parent_product.items(): # Scan attributes
                            if k == 'id' or k == '_id': # Protected keys
                                continue # Skip
                            if k not in product or not product[k]: # Missing or empty?
                                 product[k] = v # Inherit
                except Exception as e: # Handle lineage failure
                    print(f"Error fetching parent product {parent_id} for {product_id}: {e}") # Log error

    except Exception as e: # Handle critical retrieval error
        print(f'Error fetching product using Models for product-info: {e}') # Log error
    
    # 3. EMERGENCY FALLBACK
    if not product: # Missed in DB?
        try: # Check memory mocks
            for p in getattr(m, 'products', []): # Scan constant list
                pid = str(p.get('id') or p.get('_id', '')) # Identify
                if pid and str(product_id) == pid: # Match?
                    product = p # Capture
                    break # Stop
        except Exception: # Ignore
            pass # Next
    if not product: # Still missing?
        try: # Check JSON disk file
            for d in load_featured_deals_fallback(): # Scan static file
                did = str(d.get('id') or d.get('_id', '')) # Identify
                if did and str(product_id) == did: # Match?
                    product = d # Capture
                    break # Stop
        except Exception: # Ignore
            pass # Next

    # Final validation
    if not product: # Failed to find?
        return render_template('404.html'), 404 # Failure exit
    
    # 4. USER STATUS: FAVORITES
    is_favorited = False # Default state
    user_email = session.get('user') # Identity
    if user_email: # Auth check
        try: # Query
            is_favorited = favorites_model.is_favorited(user_email, str(product.get('id') or product.get('_id', ''))) # Run check
        except Exception as e: # Handle error
            print(f"Error checking favorites for product_info: {e}") # Log error
    
    # 5. RENDER VIEW
    return render_template('product_info.html', product=product, store_name=store_name, store_price=store_price, is_favorited=is_favorited)



@main_bp.route('/shopping-list') # Standard path for user lists
def shopping_list(): # Logic for cart and inventory view
    """Display and manage the user's shopping lists."""
    user_email = session.get('user') # Identity

    # 1. MAINTENANCE: ASSET ENRICHMENT
    # Auto-enrich existing list items with missing images using catalog sync
    if user_email: # Auth check
        try: # Start safety block
            from models.users_model import get_user_lists, update_user # Import helpers
            lists_data = get_user_lists(user_email) or {'lists': [], 'active_list_id': None} # Fetch current lists
            all_user_lists = lists_data.get('lists', []) # Extract array
            needs_update = False # Diff flag

            for lst in all_user_lists: # Scan each list
                list_items = lst.get('items', []) # Scan each item in list
                for item in list_items: # Process item
                    if isinstance(item, dict) and not item.get('image'): # Missing photo?
                        # Item is missing image, try to find a match in the global catalog
                        item_name = item.get('name') # Item identity
                        if item_name: # Has name?
                            try: # Start catalog search
                                prod = products_model.get_product_by_name(item_name) # Fuzzy name match
                            except Exception: # Ignore
                                prod = None # Miss

                            if prod: # Found product?
                                if prod.get('image'): # Has primary image?
                                    item['image'] = prod.get('image') # Copy
                                    needs_update = True # Mark for sync
                                elif prod.get('images') and isinstance(prod.get('images'), list) and len(prod.get('images')) > 0: # Has gallery?
                                    item['image'] = prod.get('images')[0] # Copy first
                                    needs_update = True # Mark for sync

            if needs_update: # Change detected?
                try: # Perform persistent sync
                    update_user(user_email, {'shopping_lists': all_user_lists}) # Save back to DB
                except Exception as e: # Handle write failure
                    print(f'Error updating lists with images: {e}') # Log
        except Exception as e: # Handle maintenance failure
            print(f'Error enriching images: {e}') # Log

    # 2. STATUS TRACKING: CLEAR BADGES
    # Mark items as 'viewed' by storing the current count in the user's session
    if user_email: # Auth check
        from models.users_model import get_user_lists # Helper
        data = get_user_lists(user_email) or {} # Fetch data
        lists = data.get('lists', []) or [] # Extract lists
        total = 0 # Counter
        for lst in lists: # Scan
            items = lst.get('items', []) or [] # Scan items
            total += sum(1 for it in items if not (isinstance(it, dict) and it.get('purchased'))) # Count unbought items
        session['last_viewed_list_count'] = total # Sync session
        session.modified = True # Ensure cookie update

    # 3. USER PROFILE RESOLUTION
    user_data = {} # Init
    if user_email: # Authenticated?
        try: # Fetch DB profile
            from models.users_model import get_user_by_email # Helper
            user_data = get_user_by_email(user_email) or {} # Fetch
        except Exception: # Fallback to mock on DB failure
            user_data = getattr(m, 'users', {}).get('user1@example.com', {}) # Mock match
    else: # Guest user?
        user_data = getattr(m, 'users', {}).get('user1@example.com', {}) # Default mock

    # 4. MULTI-LIST RESOLUTION
    # Retrieve all lists and ensure at least one default list exists
    try: # Start multi-list block
        from models.users_model import get_user_lists # Helper
        lists_data = get_user_lists(user_email) if user_email else {'lists': [], 'active_list_id': None} # Fetch
        all_lists = lists_data.get('lists', []) # Extract

        # If no lists exist for this user, bootstrap a default one
        if not all_lists and user_email: # Empty list set?
            from models.users_model import create_shopping_list, set_active_list # Sync helpers
            new_id = create_shopping_list(user_email, 'My List') # Create "My List"
            if new_id: # Success?
                set_active_list(user_email, new_id) # Set as primary
                lists_data = get_user_lists(user_email) # Re-fetch
                all_lists = lists_data.get('lists', []) # Sync local array

        # 5. CLEAR NOTIFICATION STATES
        # Reset 'is_new' status for items in the currently active list view
        requested_list_id = request.args.get('list_id') or lists_data.get('active_list_id') # Determine focused list
        if user_email and requested_list_id: # Valid target?
            from models.users_model import users_model # Status helper
            users_model.mark_items_as_seen(user_email, requested_list_id) # Update status in DB
            # Refresh data to reflect the cleared status flags in the UI
            lists_data = get_user_lists(user_email) # Re-fetch
            all_lists = lists_data.get('lists', []) # Sync array

        # 6. ENRICHMENT & MATH
        # Iterate through items to apply discounts and calculate order totals
        for lst in all_lists: # Scan each list
            if 'items' in lst: # Check field name
                lst['list_items'] = lst.pop('items') # Standardize internal key
            
            # Enrich items with fresh promotion data from the live catalogs
            items = lst.get('list_items') or [] # Extract items
            # Ensure items are valid dictionaries before enrichment
            valid_items = [i for i in items if isinstance(i, dict)] # Filter garbage
            if valid_items: # Has items?
                 multibuy_offers_model.attach_offers_to_products(valid_items) # Sync multibuys
                 quantity_discounts_model.attach_discounts_to_products(valid_items) # Sync bulk

            # Initialize counters for this specific list
            total = 0.0 # Price counter
            completed_count = 0 # Checkout item counter
            for item in items: # Scan items
                if isinstance(item, dict): # Type validation
                    if item.get('purchased') or item.get('completed'): # Item already in cart?
                        completed_count += 1 # Increment tally
                    price = item.get('price', 0) # Raw price
                    qty = item.get('qty', 1) # Raw quantity
                    
                    # Currency cleaning and normalization
                    if isinstance(price, str): # String format?
                        price = float(price.replace('$', '').replace('€', '').replace(',', '').strip() or 0) # Strip symbols and parse
                    elif isinstance(price, Decimal128): # Mongo format?
                        try: # Convert
                            price = float(price.to_decimal()) # Extract numeric
                        except Exception: # Handle fail
                            price = 0.0 # Reset
                    else: # Other numeric format?
                         try: # Convert
                             price = float(price) # Cast
                         except Exception: # Reset
                             price = 0.0 # Reset

                    # Apply advanced promotion pricing logic
                    offer = item.get('offer') # Check for associated offer
                    effective_price = price * int(qty) # Default baseline calculation

                    # Handle 'Buy X Get Y Free' logic (e.g. Buy 2 Get 1 Free)
                    if offer and isinstance(offer, dict) and offer.get('type') == 'buyXgetY': # Multi-buy type?
                        try: # Start math
                            ox = int(offer.get('x') or 0) # Buy quantity
                            oy = int(offer.get('y') or 0) # Free quantity
                            quantity = int(qty) # Cart quantity
                            
                            if ox and oy: # Valid parameters?
                                cycle = ox + oy # Total items in one deal group
                                full_cycles = quantity // cycle # How many groups fit in cart
                                remainder = quantity % cycle # Loose items left over
                                
                                # BUSINESS LOGIC:
                                # Pay for 'ox' items in each full cycle.
                                # Pay for remainder items (capped at 'ox' before free ones kick in).
                                payable_qty = (full_cycles * ox) + min(remainder, ox) # Determine billed count
                                effective_price = payable_qty * price # Calculate list cost
                        except Exception: # Handle math errors
                            pass # Use fallback baseline
                    
                    total += effective_price # Add to running total
            lst['estimated_total'] = f'€{total:.2f}' # Format currency for UI
            # Filter and store completed items for the "Checklist" view
            lst['completed'] = [item for item in items if isinstance(item, dict) and (item.get('purchased') or item.get('completed'))] # Store checked items
        
        # 7. ACTIVE LIST RESOLUTION
        active_list_id = lists_data.get('active_list_id') # Determine focused list

        # Select the active list object from the user's collection
        active_list = None # Reference holder
        if all_lists: # Has data?
            if active_list_id: # ID specified?
                active_list = next((lst for lst in all_lists if lst.get('id') == active_list_id), all_lists[0]) # Match or first
            else: # No ID?
                active_list = all_lists[0] # Take first

        # 8. SANITIZATION
        # Convert BSON/ObjectId to JSON safe strings for Jinja2
        all_lists = helpers.sanitize_mongo_doc(all_lists) # Clean all

        # Re-fetch active_list from the sanitized all_lists to ensure consistency
        if active_list_id:
            active_list = next((l for l in all_lists if str(l.get('id')) == str(active_list_id)), all_lists[0] if all_lists else None)
        else:
            active_list = all_lists[0] if all_lists else None

        # 9. ITEM AGGREGATION & PRICE SYNC
        # Deep-enrich each item in the shopping list with live catalog prices
        shopping_entries = active_list.get('list_items', active_list.get('items', [])) if active_list else [] # Access items

        # Load global catalog for fuzzy price matching
        products = products_model.list_products() # Fetch everything

        def find_product_by_name(name): # Helper for fuzzy lookup
            """Find product in catalog by exact or partial name match"""
            if not name: return None # Exit early
            name_l = name.lower() # Case seed
            # Priority 1: Exact Match
            for p in products: # Scan
                if isinstance(p.get('name'), str) and p.get('name').lower() == name_l: # Exact?
                    return p # Winner
            # Priority 2: Partial/Contains Match
            for p in products: # Scan
                if isinstance(p.get('name'), str) and name_l in p.get('name').lower(): # Contained?
                    return p # Secondary winner
            return None # Miss

        items = [] # Result items
        agg = {} # Deduplication map
        for idx, entry in enumerate(shopping_entries): # Process list items
            # Parse entry name and quantity
            if isinstance(entry, dict): # Complex entry?
                name = entry.get('name') # Get Name
                qty = int(entry.get('qty', entry.get('quantity', 1))) if entry.get('qty') or entry.get('quantity') else 1 # Get quantity
                purchased = bool(entry.get('purchased', False)) # Get status
            else: # String entry?
                name = str(entry) # Name is string
                qty = 1 # Qty is 1
                purchased = False # Status is fresh

            # A. Attempt to find matching product in catalog
            product = find_product_by_name(name) # Search
            price_val = 0.0 # Default
            store_name = '' # Default

            # B. Extract Price (Preferring entry's specific price)
            if isinstance(entry, dict): # Entry has metadata?
                entry_price = entry.get('price') or entry.get('price_val') # Extract
                store_name = entry.get('store', '') # Extract retailer
                if entry_price is not None: # Field exists?
                    try: # Parse
                        if isinstance(entry_price, (int, float)): # Numeric?
                            price_val = float(entry_price) # Cast
                        elif isinstance(entry_price, Decimal128): # Mongo?
                            try: price_val = float(entry_price.to_decimal()) # Extract
                            except Exception: price_val = 0.0 # Handle fail
                        else: # String with symbols?
                            cleaned = re.sub(r"[^0-9.]", "", str(entry_price)) # Regex strip symbols
                            price_val = float(cleaned) if cleaned else 0.0 # Cast
                    except Exception: # Handle errors
                        price_val = 0.0 # Reset

            # C. Sync Price from Catalog if entry has no price
            if (not price_val or price_val == 0) and product: # Missing price but found catalog item?
                cheapest = product.get('cheapest') or {} # Check record cheap
                price_field = cheapest.get('price') if isinstance(cheapest, dict) else product.get('price') # Identify best field
                if price_field is None: # Missing cheap index?
                    try: # Deep look
                        stores_list = product.get('stores', []) # Access retailer matrix
                        if stores_list and isinstance(stores_list, list): # Has entries?
                            price_field = stores_list[0].get('price') # Take first
                            if not store_name: # Retailer missing?
                                store_name = stores_list[0].get('store') or stores_list[0].get('name') # Assign
                    except Exception: # Handle traverse error
                        price_field = None # Reset
                if price_field is not None: # Found a replacement price?
                    try: # Parse
                        if isinstance(price_field, (int, float)): # Numeric?
                            price_val = float(price_field) # Cast
                        elif isinstance(price_field, Decimal128): # Mongo?
                            try: price_val = float(price_field.to_decimal()) # Extract
                            except Exception: price_val = 0.0 # Reset
                        else: # String?
                            cleaned = re.sub(r"[^0-9.]", "", str(price_field)) # Strip
                            price_val = float(cleaned) if cleaned else 0.0 # Cast
                    except Exception: # Errors?
                        price_val = 0.0 # Reset
                if not store_name: # Still no retailer?
                    try: # Look up cheapest retailer string
                        store_name = (product.get('cheapest') or {}).get('store', '') # Extract
                    except Exception: # Fail?
                        store_name = '' # Clear

            # D. Retailer Resolution
            store_from_entry = '' # Holder
            if isinstance(entry, dict): # Complex entry?
                store_from_entry = entry.get('store', '') # Capture
            if not store_from_entry: # Missing?
                store_from_entry = store_name # Use catalog retailer

            # E. Deduplication Logic: Group by ID + Store
            if product and product.get('id'): # Has ID?
                item_key = f"{str(product.get('id'))}#{store_from_entry}" # Unique composite key
            else: # Sparse data?
                item_key = f"{(name or f'item-{idx}').strip().lower()}#{store_from_entry}" # Unique composite key from name
            
            existing = agg.get(item_key) # Check for existing group
            
            # F. Image Resolution
            image_val = '' # Holder
            try: # Start asset lookup
                if isinstance(entry, dict): # Entry has asset?
                    image_val = entry.get('image') # Primary
                    if not image_val and entry.get('images'): # Gallery?
                        if isinstance(entry.get('images'), list) and len(entry.get('images')) > 0: # Array?
                            image_val = entry.get('images')[0] # First
                        elif isinstance(entry.get('images'), str): # Simple key?
                            image_val = entry.get('images') # Link

                if not image_val and product: # Missing asset but has catalog item?
                    image_val = product.get('image') # Catalog primary
                    if not image_val and product.get('images'): # Catalog gallery?
                        if isinstance(product.get('images'), list) and len(product.get('images')) > 0: # Array?
                            image_val = product.get('images')[0] # First
                        elif isinstance(product.get('images'), str): # String?
                            image_val = product.get('images') # Link
            except Exception: # Asset error?
                image_val = '' # Clear

            # G. Update Existing Group or Add New
            if existing: # Aggregate?
                existing['qty'] += qty # Add quantity
                existing['purchased'] = existing['purchased'] or purchased # Logic OR for status
                if existing.get('price_val', 0) == 0 and price_val: # Missing price?
                    existing['price_val'] = price_val # Sync
                if not existing.get('image') and image_val: # Missing photo?
                    existing['image'] = image_val # Sync
            else: # Create new row?
                agg[item_key] = { # Bind object
                    'id': product.get('id') if product and product.get('id') else f'item-{idx}', # ID
                    'name': name, # Display Name
                    'price_val': price_val, # Decimal price
                    'store': store_from_entry or store_name, # Effective retailer
                    'qty': qty, # Quantity
                    'purchased': purchased, # Status
                    'image': image_val or '', # Final asset
                    'offer': entry.get('offer') if isinstance(entry, dict) else None, # Tied offer
                    'discount_tiers': entry.get('discount_tiers') if isinstance(entry, dict) else None # Bulk tiers
                } # End object

        # 10. FINAL ITEM MATH
        # Calculate sub-totals for each grouped item row
        for k, v in agg.items(): # Process deduplicated items
            unit = float(v.get('price_val') or 0.0) # Unit price
            qty = int(v.get('qty') or 1) # Total quantity
            total = unit * qty # Baseline total

            # Re-apply promotion pricing on the aggregated quantity
            offer = v.get('offer') # Check offer
            if offer and isinstance(offer, dict) and offer.get('type') == 'buyXgetY': # Multi-buy?
                try: # Logic check
                    ox = int(offer.get('x') or 0) # Buy threshold
                    oy = int(offer.get('y') or 0) # Free bonus
                    
                    if ox > 0 and oy > 0: # Valid?
                        cycle = ox + oy # Group size
                        full_cycles = qty // cycle # Deal hits
                        remainder = qty % cycle # Partial hits
                        
                        # Calculate payable vs free items
                        payable_qty = (full_cycles * ox) + min(remainder, ox) # Determine check
                        total = payable_qty * unit # Update item subtotal
                except Exception: # Math error?
                    pass # Keep baseline

            v['price'] = f"€{total:.2f}" # Format currency string for template
            items.append(v) # Add to final array
            
        print("DEBUG: Rendering template") # Log for server monitors

        # 11. RENDER VIEW
        return render_template('shopping_list.html', # Load cart layout
                            user_data=user_data, # User demographics
                            items=items, # Processed inventory
                            all_lists=all_lists, # Navigation menu
                            active_list=active_list) # Current list context
    except Exception as e: # Major controller failure
        import traceback # Detailed error printer
        traceback.print_exc() # Show stack trace in server logs
        raise e # Let global handler capture it



@main_bp.route('/profile', methods=['GET', 'POST']) # Standard profile path
def profile(): # Logic for user settings and account management
    """User account profile management."""
    user_email = helpers.get_user_email() # Identity
    
    # 1. HANDLE UPDATES (POST)
    if request.method == 'POST' and user_email: # Form submit?
        _save_profile_update(user_email)
        return redirect(url_for('main.profile')) # Reload page to reflect changes

    context = _build_account_page_context(user_email) if user_email else {
        'user_data': {},
        'stores': [],
        'category_options': [],
    }
    return render_template('profile.html', **context)


@main_bp.route('/profile/favorites')
def profile_favorites():
    """Dedicated page for the user's saved favorites."""
    user_email = helpers.get_user_email()
    if not user_email:
        return redirect(url_for('auth.login'))

    return render_template(
        'account_favorites.html',
        account_section='favorites',
        **_build_account_page_context(user_email),
    )


@main_bp.route('/profile/settings', methods=['GET', 'POST'])
def profile_settings():
    """Dedicated page for account settings and avatar management."""
    user_email = helpers.get_user_email()
    if not user_email:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        _save_profile_update(user_email)
        return redirect(url_for('main.profile_settings'))

    return render_template(
        'account_settings.html',
        account_section='settings',
        **_build_account_page_context(user_email),
    )


@main_bp.route('/profile/preferences')
def profile_preferences():
    """Dedicated page for store and category preferences."""
    user_email = helpers.get_user_email()
    if not user_email:
        return redirect(url_for('auth.login'))

    return render_template(
        'account_preferences.html',
        account_section='preferences',
        **_build_account_page_context(user_email),
    )



