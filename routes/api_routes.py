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
import uuid
from datetime import datetime, timezone, timedelta
from utils.db import get_db
from comparison.cheapest_finder import get_cheapest_from_product

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




@main_bp.route('/api/search-products') # API: Live Search
def api_search_products(): # JSON search endpoint for dynamic UI components
    """Search products by query string `q` (case-insensitive substring match on name).
    Returns JSON list of product docs (id, name, price, stores, cheapest, image).
    """
    q = request.args.get('q', '').strip() # Extract query
    if not q: # Empty?
        return jsonify({'items': []}) # Rapid exit

    results = [] # Init matches
    try: # Start search process
        if m.HAS_DB: # MongoDB alive?
            # Perform primary keyword search via model
            products = products_model.search_by_name(q, limit=50) # Substring match
            
            # Supplement with Quantity Discount matches (Secondary promo collection)
            try: # Nested safety
                qd_list = quantity_discounts_model.list_active_discounts() # Fetch promos
                for d in qd_list: # Scan promos
                    name = d.get('name') or d.get('product_name') or '' # Extract name
                    if q.lower() in name.lower(): # Match check
                         products.append(d) # Append to pool
            except Exception as e: # Handle promo search failure
                print(f"Error searching quantity discounts: {e}") # Log warning

            for d in products: # Filter and sanitize results
                # Helper to ensure product has valid pricing before showing to user
                def _has_price(prod): # Logic check
                    if prod is None: return False # Sanity check
                    if prod.get('price') not in (None, ''): # Simple price field?
                        return True # Valid
                    c = get_cheapest_from_product(prod)
                    if isinstance(c, dict) and c.get('price') is not None:
                        return True # Valid
                    stores_list = prod.get('stores') or [] # Check store arrays
                    try: # Access check
                        if isinstance(stores_list, list) and len(stores_list) and stores_list[0].get('price') not in (None, ''): # Array price?
                            return True # Valid
                    except Exception: # Bad structure
                        pass # Continue
                    return False # No price found

                if not _has_price(d): # Essential info missing?
                    # skip legacy/broken entries that don't have usable price info
                    continue # Ignore
                
                p_doc = dict(d)
                p_doc['url'] = f"/product/{p_doc.get('_id') or p_doc.get('id')}"
                results.append(helpers.sanitize_mongo_doc(p_doc)) # Sanitize BSON and add to final list
                
            # SUPPLEMENT WITH DEALS
            try:
                import models.featured_deals_model as featured_deals_model_local
                all_deals = featured_deals_model_local.list_featured_deals()
                for d in all_deals:
                    name = d.get('title') or d.get('name') or ''
                    if q.lower() in name.lower() or q.lower() in (d.get('store') or '').lower():
                        deal_doc = dict(d)
                        deal_doc['is_deal'] = True
                        deal_doc['name'] = name
                        deal_doc['url'] = f"/featured-deal/{str(deal_doc['_id'])}"
                        deal_doc['price'] = deal_doc.get('deal_price') or deal_doc.get('price')
                        results.append(helpers.sanitize_mongo_doc(deal_doc))
            except Exception as e:
                pass

            # SUPPLEMENT WITH STORES
            try:
                import models.stores_model as stores_model_local
                all_s = stores_model_local.list_stores()
                for s in all_s:
                    name = s.get('name') or ''
                    if q.lower() in name.lower():
                        store_doc = dict(s)
                        store_doc['is_store'] = True
                        store_doc['name'] = name
                        store_doc['url'] = f"/store/{name}"
                        store_doc['image'] = s.get('image') or s.get('logo') or s.get('logo_url') or 'https://via.placeholder.com/60'
                        results.append(helpers.sanitize_mongo_doc(store_doc))
            except Exception as e:
                pass

        else: # FALLBACK: DB Disconnected
            # fallback to in-memory search (log this so it's visible)
            print('WARNING: api_search_products used fallback in-memory products (DB unavailable)') # Warn
            for p in getattr(m, 'products', []): # Scan mock data
                name = p.get('name', '') # get name
                if q.lower() in str(name).lower(): # Substring match
                    # Valid price filter for mock data
                    if p.get('price') not in (None, '') or (p.get('cheapest') and p['cheapest'].get('price')) or (p.get('stores') and len(p.get('stores')) and p.get('stores')[0].get('price')):
                        results.append(helpers.sanitize_mongo_doc(p)) # Add
    except Exception as e: # Critical crash
        return jsonify({'error': str(e)}), 500 # Return JSON error

    return jsonify({'items': results}) # Return final JSON results




@main_bp.route('/api/product') # API: Single Item Lookup
def api_get_product(): # Detailed info for one product
    """Return a single product by id or name. Query params: ?id=<id> or ?name=<name>
    Response: { item: <product-doc> }
    """
    pid = request.args.get('id') or request.args.get('product_id') # Get ID
    name = request.args.get('name') or request.args.get('title') or request.args.get('q') # Get name fallback
    if not pid and not name: # No identifier?
        return jsonify({'item': None}), 400 # Bad request
    try: # Start lookup
        if m.HAS_DB: # DB check
            doc = None # Target doc
            if pid: # Searching by ID?
                doc = products_model.get_product_by_id(str(pid)) # Direct hit
            else: # Searching by name?
                doc = products_model.get_product_by_name(str(name)) # Name match
            
            if not doc: # Not found?
                return jsonify({'item': None}), 404 # Resource missing
            return jsonify({'item': helpers.sanitize_mongo_doc(doc)}) # Return clean JSON
        else: # Fallback
            # Search in-memory product mocks
            for p in getattr(m, 'products', []): # Iterate mocks
                # Match against ID or Name
                if pid and (str(p.get('id')) == str(pid) or str(p.get('_id', '')) == str(pid)):
                    return jsonify({'item': p}) # Matched ID
                if name and name.lower() in str(p.get('name', '')).lower():
                    return jsonify({'item': p}) # Matched Name
            return jsonify({'item': None}), 404 # Not found in mocks
    except Exception as e: # Handle lookup errors
        return jsonify({'error': str(e)}), 500 # Internal error



@main_bp.route('/api/categories') # API: Category Config
def api_get_categories(): # List available product categories
    """Return specific standard categories provided by user."""
    try: # Fetch global list
        return jsonify({'categories': STANDARD_CATEGORIES}), 200 # Return constants
    except Exception as e: # Handle configuration error
        print(f'ERROR in api_get_categories: {e}') # Log
        return jsonify({'categories': [], 'error': str(e)}), 500 # Fail gracefully




@main_bp.route('/api/stores') # API: All Stores
def api_get_stores(): # Summary list of all available retailers
    """Return a list of available stores (id, name, location).
    Uses MongoDB when available, otherwise falls back to in-memory `models.stores`.
    """
    try: # Start fetch
        out = [] # Output list
        # Internal helper to format store document for consistent API response
        def shape_store(s): # Define formatter
            # Resolve image (Checking multiple potential fields)
            image = s.get('image') or (s.get('images')[0] if isinstance(s.get('images'), list) and s.get('images') else None)
            hours = s.get('hours') or s.get('opening_hours') # Extract schedule
            deals_val = s.get('active_deals') or s.get('deals') # Extract promo count
            if isinstance(deals_val, list): # Is it a list of items?
                deals_count = len(deals_val) # Count them
            else: # Is it already a number?
                deals_count = deals_val # Use directly
            # Build location string from address components
            location = s.get('location') or ', '.join(filter(None, [s.get('address'), s.get('city')]))
            return { # JSON shape
                'id': s.get('id') or s.get('_id'), # Normalized ID
                'name': s.get('name'), # Basic name
                'location': location, # Formatted location
                'image': image, # Resolved asset
                'url': s.get('url') or s.get('website'), # External link
                'hours': hours, # Working hours
                'distance': s.get('distance'), # Proximity (if available)
                'deals': deals_count # Promo summary
            } # End shape
        if m.HAS_DB: # Live database?
            stores = stores_model.list_stores()[:500] # Fetch top 500 records
            for s in stores: # Process each
                out.append(shape_store(helpers.sanitize_mongo_doc(s))) # Shape and add
        else: # Fallback data
            for s in getattr(m, 'stores', []): # Scan mock list
                out.append(shape_store(helpers.sanitize_mongo_doc(s))) # Shape and add
        return jsonify({'stores': out}) # Send JSON array
    except Exception as e: # Handle aggregation crashes
        return jsonify({'error': str(e)}), 500 # Fail status




@main_bp.route('/api/store/<store_name>/products') # API: Store Catalog
def api_get_store_products(store_name): # Fetch products filtered by retailer
    """Return products for a given store name (no featured deals).

    Searches `products` for any entry where the `stores` array (or top-level `store`) matches
    the provided name case-insensitively. Only the matching store entries are returned in
    `matched_stores` so the UI can display per-store prices/images cleanly.
    """
    if not store_name: # No identifier?
        return jsonify({'error': 'missing_store'}), 400 # Bad input exit

    store_query = store_name.strip() # Clean name
    if not store_query: # Blank?
        return jsonify({'error': 'missing_store'}), 400 # Duplicate check

    store_lc = store_query.lower() # Case-neutral comparison target

    # Internal helper to prepare Mongo documents for JSON/UI
    def _normalize(doc): # Formatter
        if not isinstance(doc, dict): # Validate object
            return {} # Empty fallback
        shaped = dict(doc) # Shallow copy
        if '_id' in shaped: # Mongo PK present?
            shaped['id'] = str(shaped['_id']) # Convert to string
            shaped.pop('_id', None) # Remove raw BSON key
        return shaped # Clean object

    # Internal helper to identify if a store entry matches our target
    def _match_store_entry(entry): # Filter logic
        try: # Field access check
            # Look for 'store' or 'name' field in embedded store object
            val = (entry.get('store') or entry.get('name') or '').strip()
        except Exception: # Access failure
            val = '' # Fallback
        return val and val.lower() == store_lc # Case-neutral match

    # Internal helper to transform raw product docs into store-indexed docs
    def _shape_product(prod): # Transformation logic
        shaped = _normalize(prod) # Initial cleanup
        # Filter 'stores' array to only include the specific store requested
        matched_stores = [s for s in (shaped.get('stores') or []) if _match_store_entry(s)]
        # Some legacy docs may store a single store field at top-level instead of in an array
        if not matched_stores and isinstance(shaped.get('store'), str) and shaped.get('store', '').lower() == store_lc:
            # Reconstruct the expected object structure for UI consistency
            matched_stores.append({'store': shaped.get('store'), 'price': shaped.get('price'), 'image': shaped.get('image')})
        shaped['matched_stores'] = matched_stores # Store filtered results
        
        # Primary price resolution
        price_val = None # Reset
        if matched_stores: # Found local store info?
            price_val = matched_stores[0].get('price') # Extract local price
        if price_val in (None, ''): # No local price?
            cheapest = get_cheapest_from_product(shaped)
            price_val = cheapest.get('price') if cheapest.get('price') is not None else shaped.get('price')
        
        # Ensure price is serializable (handle BSON Decimal128)
        try: # Type conversion block
            from bson.decimal128 import Decimal128 # Import type
            if isinstance(price_val, Decimal128): # Is BSON?
                price_val = float(price_val.to_decimal()) # Convert to Python float
        except Exception: # Skip if library missing or invalid
            pass # Keep original value
            
        shaped['price'] = price_val # Save resolved price
        shaped['source'] = 'product' # Tag for UI routing
        return shaped # Return processed item

    # Internal helper to designate source type for deals
    def _shape_deal(deal): # Deal formatter
        shaped = _normalize(deal) # Clean base fields
        shaped['source'] = 'featured_deal' # Explicit source tag
        return shaped # Return processed item

    products = [] # Init result pool
    try: # Start store product fetch
        # Fetch standard products associated with this store via Model
        products = [_shape_product(p) for p in products_model.find_by_store(store_query)] # Batch process
        
        # If primary Model returns nothing, allow fallback to scanning all products in-memory (safety net)
        if not products: # Empty?
            # Manually filter mocks for store name matches (Case-Insensitive)
            products = [_shape_product(p) for p in getattr(m, 'products', []) if any(_match_store_entry(s) for s in (p.get('stores') or [])) or (isinstance(p.get('store'), str) and p.get('store', '').lower() == store_lc)]
    except Exception as e: # Handle aggregation error
        return jsonify({'error': str(e)}), 500 # Return JSON fail

    # Return results for specific retailer
    return jsonify({
        'store': store_query, # Context
        'products': products, # Match list
        'count': len(products) # UI helper
    })




@main_bp.route('/api/claim-deal', methods=['POST']) # API: Shopping Cart Hook
def api_claim_deal(): # Logic for adding specific deal items to list
    """Endpoint to claim a featured deal and add it to the user's shopping list.
    Expects JSON { deal_id: '<id>' } or { title: '<title>' }. Returns JSON { success: bool }.
    """
    data = request.get_json() or {} # Parse payload
    deal_id = data.get('deal_id') or data.get('id') or data.get('title') # Identity priority
    if not deal_id: # Missing ID?
        return jsonify({'error': 'no_deal_id_provided'}), 400 # Bad input

    # Check user identity for list targeting
    email = helpers.get_user_email()

    try: # Start lookup
        # Attempt to find the specific deal document across all promo collections
        deal_doc = None # Target
        if m.HAS_DB: # Live DB?
            # 1. Check primary Promotions collection
            deal_doc = featured_deals_model.get_deal_by_id(str(deal_id))
            
            # 2. Check BOGO/Multibuy collection if not in primary
            if not deal_doc:
                deal_doc = multibuy_offers_model.get_offer_by_id(str(deal_id))
        else: # FALLBACK
            # Scan in-memory mock deals for title/id match
            for d in getattr(m, 'featured_deals', []):
                if str(d.get('title')) == str(deal_id) or str(d.get('id')) == str(deal_id):
                    deal_doc = d # Capture match
                    break

        # Mark deal as 'claimed' for analytics/personalization tracking
        claimed = False # Status
        if deal_doc: # Found record?
            claimed = m.claim_featured_deal_by_id(deal_id, email=email) # Persist claim event
        else: # Missing record?
            # Try incrementing by ID directly as a fallback measure
            claimed = m.claim_featured_deal_by_id(deal_id, email=email)

        # Persistence: Add to user's real shopping list
        added = False # Tracking flag
        active_added = False # Tracking flag
        if email: # Logged in?
            # Prefer the modern multi-list architecture
            try: # List operation block
                from models.users_model import (
                    get_user_lists, # Fetch lists
                    add_item_to_list, # Add helper
                    create_shopping_list, # Init helper
                    set_active_list, # Set current helper
                )

                # Resolve pricing and offers (Merging client data with server records)
                raw_price = data.get('price') or (deal_doc or {}).get('price') # Deal price
                raw_original = data.get('original_price') or (deal_doc or {}).get('original_price') # Base price
                raw_offer = data.get('offer') or (deal_doc or {}).get('offer') or '' # Promo label
                raw_image = data.get('image') or (deal_doc or {}).get('image') or ((deal_doc or {}).get('images') or [None])[0] # Asset
                qty = int(data.get('qty') or 1) # User qty choice
                price_val = data.get('price_val') or raw_original or raw_price # Final unit value

                # Cleaner for currency/formatting
                def _to_float(val): # Normalizer
                    try: # Conversion attempt
                        return float(str(val).replace('€', '').replace('$', '').replace(',', '').strip()) if val is not None else 0.0
                    except Exception: # Parsing error
                        return 0.0 # Standard fallback

                # Helper to turn string offers (e.g., "2+1") into structured objects
                def _parse_offer(val): # Structure helper
                    # 1. Is it already structured?
                    if isinstance(val, dict) and val.get('type'):
                        return { # Map fields
                            'type': val.get('type'),
                            'x': val.get('x'),
                            'y': val.get('y'),
                        }
                    # 2. Is it a standard string e.g. "2+1"?
                    if isinstance(val, str):
                        match_res = re.match(r"(\d+)\s*\+\s*(\d+)", val) # Regex check
                        if match_res: # Found?
                            return {'type': 'buyXgetY', 'x': int(match_res.group(1)), 'y': int(match_res.group(2))}
                    return None # No standard offer found

                offer_obj = _parse_offer(raw_offer) # Run parser
                # fallback: check legacy multibuy fields from MongoDB collections
                if not offer_obj:
                    # Look for separate buy/free fields (Standard in Mongo BOGO docs)
                    mb_buy = (deal_doc or {}).get('buy_quantity') or (deal_doc or {}).get('multibuy_buy') or data.get('multibuy_buy')
                    mb_free = (deal_doc or {}).get('free_quantity') or (deal_doc or {}).get('multibuy_free') or data.get('multibuy_free')
                    if mb_buy and mb_free: # Found pair?
                        offer_obj = {'type': 'buyXgetY', 'x': int(mb_buy), 'y': int(mb_free)} # Structure it

                # Normalize all prices to floats for calculation
                price_val_num = _to_float(price_val)
                discounted_price_num = _to_float(raw_price) # Current deal price
                original_price_num = _to_float(raw_original) # unit baseline

                # Logic: Resolve the correct unit price for the shopping list
                if offer_obj and offer_obj.get('type') == 'buyXgetY':
                    # FOR MULTIBUY: User pays original price per unit, but list logic applies 'Free' cycles
                    charge_price = original_price_num if original_price_num > 0 else discounted_price_num
                else:
                    # FOR REGULAR DEALS: Use the lower of the two available prices
                    charge_price = discounted_price_num or original_price_num or price_val_num

                # Build final payload for the list collection
                payload = { # Document
                    'name': (deal_doc or {}).get('title') or (deal_doc or {}).get('name') or str(deal_id),
                    'price': charge_price, # Resolved per-unit cost
                    'price_val': charge_price, # Redundant field for UI legacy
                    'store': (deal_doc or {}).get('store') or (deal_doc or {}).get('source', ''),
                    'image': raw_image, # Context asset
                    'qty': 1, # Increment by 1 unit per click
                    'offer': offer_obj or raw_offer, # Pass offer logic to list for calculation
                }

                # Resolve which list to update
                lists_data = get_user_lists(email) or {} # Fetch all
                active_list_id = lists_data.get('active_list_id') # Identify current choice

                if not active_list_id: # No list exists?
                    new_id = create_shopping_list(email, 'My List') # Create default
                    if new_id: # Success?
                        set_active_list(email, new_id) # Set as primary
                        active_list_id = new_id # Select for update

                if active_list_id: # Final check
                    active_added = add_item_to_list(email, active_list_id, payload) # RUN DB UPDATE
            except Exception: # Handling list logic failure
                active_added = False # Mark fail

            # Legacy fallback: add to single global list for older accounts
            added = m.add_deal_to_user_shopping_list(email, deal_doc or str(deal_id))

        # Return comprehensive success status
        return jsonify({'success': bool(claimed or added or active_added), 'claimed': bool(claimed), 'added': bool(added or active_added)})
    except Exception as e: # Catch API crashes
        return jsonify({'error': str(e)}), 500 # Server error




@main_bp.route('/api/toggle-favorite', methods=['POST']) # API: User Likes
def toggle_favorite(): # Handles heart icon interaction
    """Add or remove a product from user's favorites"""
    try: # Start logic
        user_email = session.get('user') # Auth check
        if not user_email: # Guest?
            return jsonify({'error': 'Not logged in'}), 401 # Deny
        
        data = request.get_json() # Parse body
        product_id = data.get('product_id') # Extract target
        
        if not product_id: # ID missing?
            return jsonify({'error': 'Product ID required'}), 400 # Bad input
        
        from models import favorites_model # Import DAO
        
        # Check current state to determine if we are ADDING or REMOVING
        is_favorited = favorites_model.is_favorited(user_email, product_id)
        
        if is_favorited: # Already liked?
            # Perform Removal
            success = favorites_model.remove_favorite(user_email, product_id)
            if success: # OK?
                return jsonify({'success': True, 'action': 'removed', 'is_favorite': False})
            else: # Fail?
                return jsonify({'error': 'Failed to remove favorite'}), 500
        else: # NOT yet liked?
            # Perform Addition. We need to fetch product metadata first to save a snapshot in favorites.
            # Scan all potential collections for the product info
            product = products_model.get_product_by_id(product_id) # 1. Standard
            if not product: # Not there?
                product = featured_deals_model.get_deal_by_id(product_id) # 2. Featured
            if not product: # Not there?
                product = multibuy_offers_model.get_offer_by_id(product_id) # 3. Multibuy
            if not product: # Not there?
                try: # 4. Quantity Discount (Promo)
                    product = quantity_discounts_model.get_discount_by_id(product_id)
                except Exception: pass # Ignore error
            
            if not product: # Completely missing?
                print(f'ERROR: Product not found with id {product_id}') # Log
                return jsonify({'error': 'Product not found'}), 404 # 404
            
            # Resolve store info for the favorite snapshot
            cheapest = get_cheapest_from_product(product)
            store_name = cheapest.get('store') or product.get('store') or product.get('source', '')
            
            # Formulate the document to be saved in favorited_products collection
            product_data = { # Snapshot
                'name': product.get('name') or product.get('title', ''), # Name
                'image': product.get('image', ''), # Asset
                'category': product.get('category', ''), # Context
                'best_price': cheapest.get('price') if cheapest.get('price') is not None else product.get('price', 'N/A'),
                'store': store_name, # Origin
                'discount_tiers': product.get('discount_tiers'), # Meta
                'offer': product.get('offer') # Meta
            }
            
            # Run the addition command in DB
            success = favorites_model.add_favorite(user_email, product_id, product_data)
            if success: # OK?
                return jsonify({'success': True, 'action': 'added', 'is_favorite': True})
            else: # Persistence failure?
                return jsonify({'error': 'Failed to add favorite'}), 500 # Fail
    
    except Exception as e: # Handling API crashes
        return jsonify({'error': str(e)}), 500 # Server crash




@main_bp.route('/api/check-favorite', methods=['GET']) # API: UI Logic helper


@main_bp.route('/api/check-favorite/<product_id>', methods=['GET']) # Supports both patterns
def check_favorite(product_id=None): # Verifies if star should be filled
    """Check if a product is in user's favorites"""
    try: # Start check
        # Normalize input from URL path or Query string
        if not product_id: # Missing ID in path?
            product_id = request.args.get('product_id') # Check query ?product_id=...
        
        if not product_id: # Still missing?
            return jsonify({'error': 'Product ID required'}), 400 # Exit
        
        user_email = session.get('user') # Identity check
        if not user_email: # Guest?
            return jsonify({'is_favorite': False}) # Fast exit (Guests can't favorite)
        
        from models import favorites_model # Import DAO
        is_favorited = favorites_model.is_favorited(user_email, product_id) # DB inquiry
        
        return jsonify({'is_favorite': is_favorited}) # Return status
    
    except Exception as e: # Handle error
        return jsonify({'error': str(e)}), 500 # Fail status




@main_bp.route('/api/save-preferences', methods=['POST'])
def save_preferences():
    """Save user preferences without overwriting existing ones"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'error': 'Not logged in'}), 401
        
        data = request.get_json() or {}
        
        update_doc = {}
        
        # Build update document based on provided keys
        if 'preferred_stores' in data:
            preferred_stores = [s for s in data.get('preferred_stores', []) if s]
            update_doc['preferred_stores'] = preferred_stores
            update_doc['preferences.preferred_stores'] = preferred_stores
            
        if 'preferred_categories' in data:
            preferred_categories = [c for c in data.get('preferred_categories', []) if c]
            update_doc['preferred_categories'] = preferred_categories
            update_doc['preferences.preferred_categories'] = preferred_categories
            
        if not update_doc:
            return jsonify({'success': True, 'message': 'No changes provided'})
            
        from models.users_model import update_user
        update_user(user_email, update_doc)
        
        return jsonify({'success': True, 'updated_fields': list(update_doc.keys())})
    
    except Exception as e:
        print(f"Error saving preferences: {e}")
        return jsonify({'error': str(e)}), 500
        return jsonify({'error': str(e)}), 500


# Shopping List API Endpoints


def _resolve_reporter_identity():
    """Resolve user/guest reporter identity without requiring authentication."""
    user_email = helpers.get_user_email()
    if user_email:
        return {'reporter_type': 'user', 'reporter_id': user_email}

    anon_id = session.get('anon_reporter_id')
    if not anon_id:
        anon_id = f"guest-{uuid.uuid4().hex[:16]}"
        session['anon_reporter_id'] = anon_id
    return {'reporter_type': 'guest', 'reporter_id': anon_id}


@main_bp.route('/api/community-price-report', methods=['POST'])
def api_community_price_report_create():
    """Create community price report (guest-friendly)."""
    try:
        payload = request.get_json() or {}
        product_id = str(payload.get('product_id') or '').strip()
        store_name = str(payload.get('store_name') or '').strip()
        note = str(payload.get('note') or '').strip()

        try:
            observed_price = float(payload.get('observed_price'))
        except Exception:
            observed_price = None

        if not product_id or not store_name or observed_price is None:
            return jsonify({'error': 'product_id, store_name and observed_price are required'}), 400
        if observed_price <= 0 or observed_price > 10000:
            return jsonify({'error': 'observed_price is out of accepted range'}), 400
        if len(note) > 220:
            return jsonify({'error': 'note is too long'}), 400

        identity = _resolve_reporter_identity()
        now = datetime.now(timezone.utc)

        db = get_db()

        # Basic anti-spam: same reporter/product/store once per 10 minutes.
        dedupe_since = now - timedelta(minutes=10)
        existing = db.community_price_reports.find_one({
            'reporter_id': identity['reporter_id'],
            'product_id': product_id,
            'store_name': store_name,
            'created_at': {'$gte': dedupe_since},
        })
        if existing:
            return jsonify({'success': False, 'error': 'duplicate_recent_report'}), 429

        doc = {
            'product_id': product_id,
            'store_name': store_name,
            'observed_price': round(observed_price, 2),
            'note': note,
            'reporter_type': identity['reporter_type'],
            'reporter_id': identity['reporter_id'],
            'source': 'web_compare',
            'created_at': now,
        }
        res = db.community_price_reports.insert_one(doc)

        return jsonify({'success': True, 'report_id': str(res.inserted_id)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main_bp.route('/api/community-price-report-summary', methods=['GET'])
def api_community_price_report_summary():
    """Return report counts and latest report for a product (guest-friendly)."""
    product_id = str(request.args.get('product_id') or '').strip()
    if not product_id:
        return jsonify({'error': 'product_id required'}), 400

    try:
        db = get_db()
        count = db.community_price_reports.count_documents({'product_id': product_id})
        latest = db.community_price_reports.find_one(
            {'product_id': product_id},
            sort=[('created_at', -1)],
        )
        if latest:
            latest = helpers.sanitize_mongo_doc(latest)
        return jsonify({'success': True, 'count': count, 'latest': latest})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

