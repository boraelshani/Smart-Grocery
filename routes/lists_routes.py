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
from utils.db import get_db

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



@main_bp.route('/api/list/create', methods=['POST']) # API: Initialize a fresh shopping list
def create_shopping_list_api(): # Triggered by the "New List" button
    """Create a new shopping list"""
    try: # Start write
        user_email = session.get('user') # Identity check
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny access
        
        data = request.get_json() # Fetch request body
        list_name = data.get('name', '').strip() # Clean name string
        
        if not list_name: # Empty name?
            return jsonify({'success': False, 'error': 'List name is required'}), 400 # Fail
        
        # Load profile persistence helpers
        from models.users_model import create_shopping_list, set_active_list
        # 1. Create the list object and get its unique ID
        new_list_id = create_shopping_list(user_email, list_name)
        
        if new_list_id: # Database write successful?
            # 2. Automatically make this new list the active selection
            set_active_list(user_email, new_list_id)
            return jsonify({'success': True, 'list_id': new_list_id}) # Return identifier
        else: # Mongo error or unknown failure
            return jsonify({'success': False, 'error': 'Failed to create list'}), 500 # Fail
    except Exception as e: # Handle server-side crash
        return jsonify({'success': False, 'error': str(e)}), 500 # Return error trace




@main_bp.route('/api/list/rename', methods=['POST']) # API: Modify list title
def rename_shopping_list_api(): # Updates the name property of a specific list object
    """Rename a shopping list"""
    try: # Start update
        user_email = session.get('user') # Identity
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        data = request.get_json() # Fetch body
        list_id = data.get('list_id') # Target identification
        new_name = data.get('name', '').strip() # New label
        
        if not list_id or not new_name: # Incomplete data?
            return jsonify({'success': False, 'error': 'List ID and name are required'}), 400 # Fail
        
        from models.users_model import rename_shopping_list # DAO helper
        # Executes an atomic $set operation on the target list in the user's array
        success = rename_shopping_list(user_email, list_id, new_name)
        return jsonify({'success': success}) # Return boolean result
    except Exception as e: # Catch failure
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/list/delete', methods=['POST']) # API: Remove a list
def delete_shopping_list_api(): # Permanently deletes a list and its items
    """Delete a shopping list"""
    try: # Start deletion
        user_email = session.get('user') # Identity
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        data = request.get_json() # Fetch body
        list_id = data.get('list_id') # Target UUID
        
        if not list_id: # Missing ID?
            return jsonify({'success': False, 'error': 'List ID is required'}), 400 # Fail
        
        from models.users_model import delete_shopping_list # DAO helper
        # Executes $pull operation to remove the specific list object from the profile
        success = delete_shopping_list(user_email, list_id)
        return jsonify({'success': success}) # Return result
    except Exception as e: # Catch error
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/list/set-active', methods=['POST']) # API: Switch current list
def set_active_list_api(): # Updates the 'active_list_id' pointer in the user profile
    """Set the active shopping list"""
    try: # Start update
        user_email = session.get('user') # Identity
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        data = request.get_json() # Fetch body
        list_id = data.get('list_id') # Target target
        
        if not list_id: # Missing?
            return jsonify({'success': False, 'error': 'List ID is required'}), 400 # Fail
        
        from models.users_model import set_active_list # Profile helper
        # Sets the active_list_id field so UI knows which list to render on load
        success = set_active_list(user_email, list_id)
        return jsonify({'success': success}) # OK
    except Exception as e: # Catch
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/list/duplicate', methods=['POST']) # API: Create deep copy
def duplicate_shopping_list_api(): # Clones items and name to a new list object
    """Duplicate a shopping list"""
    try: # Start clone
        user_email = session.get('user') # Identity
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        data = request.get_json() # Fetch
        list_id = data.get('list_id') # Source ID
        
        if not list_id: # Missing source?
            return jsonify({'success': False, 'error': 'List ID is required'}), 400 # Fail
        
        # Profile interaction helpers
        from models.users_model import get_user_lists, create_shopping_list, update_list_items
        
        # 1. Fetch current list data to find the original source
        lists_data = get_user_lists(user_email)
        source_list = next((lst for lst in lists_data['lists'] if lst['id'] == list_id), None)
        
        if not source_list: # Source missing?
            return jsonify({'success': False, 'error': 'List not found'}), 404 # 404
        
        # 2. Format a new name for the clone
        new_name = f"{source_list['name']} (Copy)"
        # 3. Initialize the shell for the new list
        new_list_id = create_shopping_list(user_email, new_name)
        
        if new_list_id: # Shell created?
            # 4. Copy all item arrays from source to new target
            items = source_list.get('items', [])
            update_list_items(user_email, new_list_id, items)
            return jsonify({'success': True, 'list_id': new_list_id}) # Done
        else: # Shell creation failed
            return jsonify({'success': False, 'error': 'Failed to create list'}), 500 # Fail
    except Exception as e: # Server crash
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/list/update-items', methods=['POST'])
def update_list_items_api():
    """Update items in the active shopping list"""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        items = data.get('items', [])
        
        from models.users_model import get_user_lists, update_list_items
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        
        if not active_list_id:
            return jsonify({'success': False, 'error': 'No active list'}), 400
        
        success = update_list_items(user_email, active_list_id, items)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500




@main_bp.route('/api/list/mark-seen/<list_id>', methods=['POST']) # API: Status reset
def mark_list_seen(list_id): # Removes 'new' highlights from items in a list
    """Clear the 'is_new' flag for all items in the specified list"""
    try: # Start update
        user_email = session.get('user') # Identity check
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        from models.users_model import mark_items_as_seen # Profile helper
        # Executes $set: { "lists.$.items.$[].is_new": false } in MongoDB
        success = mark_items_as_seen(user_email, list_id)
        return jsonify({'success': success}) # Return result
    except Exception as e: # Catch
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/list/remove-item', methods=['POST']) # API: Delete item from list
def remove_item_from_list_api(): # Removes a specific item from the primary list
    """Remove an item from the active shopping list"""
    try: # Start deletion
        user_email = session.get('user') # Identity
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        data = request.get_json() # Fetch request
        item_name = data.get('item_name') # Target text
        
        if not item_name: # Missing param?
            return jsonify({'success': False, 'error': 'Item name is required'}), 400 # Fail
        
        from models.users_model import get_user_lists, remove_item_from_list
        # 1. Fetch current metadata to find the active list ID
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        
        if not active_list_id: # No list selected?
            return jsonify({'success': False, 'error': 'No active list'}), 400 # Fail
        
        # 2. Execute atomic removal of the item from the MongoDB array
        success = remove_item_from_list(user_email, active_list_id, item_name)
        return jsonify({'success': success}) # Return status
    except Exception as e: # Catch
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/list/clear-completed', methods=['POST']) # API: Cleanup purchased items
def clear_completed_items_api(): # Removes all items marked as 'purchased'
    """Clear completed items from the active shopping list"""
    try: # Start write
        user_email = session.get('user') # Identity
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        from models.users_model import get_user_lists, update_list_items
        # 1. Identify context
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        
        if not active_list_id: # Error check
            return jsonify({'success': False, 'error': 'No active list'}), 400 # Fail
        
        # 2. Locate list content
        active_list = next((lst for lst in lists_data['lists'] if lst['id'] == active_list_id), None)
        if not active_list: # List not found?
            return jsonify({'success': False, 'error': 'List not found'}), 404 # 404
        
        # 3. Filter the array: Keep only items where 'purchased' is false (or missing)
        items = active_list.get('items', [])
        remaining_items = [item for item in items if not (isinstance(item, dict) and item.get('purchased'))]
        
        # 4. Overwrite list with cleansed array
        success = update_list_items(user_email, active_list_id, remaining_items)
        return jsonify({'success': success}) # Success
    except Exception as e: # Catch
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/list/clear-all', methods=['POST']) # API: Wipe list content
def clear_all_items_api(): # Resets a list to an empty state
    """Clear all items from the active shopping list"""
    try: # Start wipe
        user_email = session.get('user') # Identity
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        from models.users_model import get_user_lists, update_list_items
        # 1. Identify active list
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        
        if not active_list_id: # Verify list exists
            return jsonify({'success': False, 'error': 'No active list'}), 400 # Fail
        
        # 2. Write an empty array to the items field in MongoDB
        success = update_list_items(user_email, active_list_id, [])
        return jsonify({'success': success}) # OK
    except Exception as e: # Catch
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/list/move-item', methods=['POST']) # API: Relocate item between lists
def move_item_to_list_api(): # Moves an item from active selection to a sidebar list
    """Move an item from active list to another list"""
    try: # Start transfer
        user_email = session.get('user') # Identity check
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        data = request.get_json() # Fetch body
        item_name = data.get('item_name') # Target item
        target_list_id = data.get('target_list_id') # Destination list
        
        if not item_name or not target_list_id: # Missing params?
            return jsonify({'success': False, 'error': 'Item name and target list are required'}), 400 # Fail
        
        # Load profile and item management tools
        from models.users_model import get_user_lists, remove_item_from_list, add_item_to_list
        # 1. Fetch current active list to find the source
        lists_data = get_user_lists(user_email)
        active_list_id = lists_data.get('active_list_id')
        
        if not active_list_id: # No source?
            return jsonify({'success': False, 'error': 'No active list'}), 400 # Fail
        
        # 2. Locate the source list document
        active_list = next((lst for lst in lists_data['lists'] if lst['id'] == active_list_id), None)
        if not active_list: # List missing?
            return jsonify({'success': False, 'error': 'List not found'}), 404 # 404
        
        # 3. Find the specific item document/string in the source array
        item_to_move = None
        for item in active_list.get('items', []): # Scan
            if isinstance(item, dict) and item.get('name') == item_name: # Handle complex object
                item_to_move = item
                break
            elif isinstance(item, str) and item == item_name: # Handle simple string
                item_to_move = item
                break
        
        if not item_to_move: # Item not found in current list?
            return jsonify({'success': False, 'error': 'Item not found'}), 404 # 404
        
        # 4. Atomic Database Update: Add to Target then Remove from Source
        success = add_item_to_list(user_email, target_list_id, item_to_move)
        if success: # If addition worked
            success = remove_item_from_list(user_email, active_list_id, item_name) # Remove from source
        return jsonify({'success': success}) # Return result
    except Exception as e: # Catch server-side crash
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/list/add-item', methods=['POST']) # API: Quick item injection
def add_item_to_active_list_api(): # Adds an item to a list without opening it
    """Add an item to a shopping list (supports specifying which list)"""
    try: # Start write
        user_email = session.get('user') # Identity check
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        data = request.get_json() # Fetch body
        item = data.get('item') # Item payload (string or dict)
        target_list_id = data.get('list_id') # Optional target
        
        if not item: # Missing item?
            return jsonify({'success': False, 'error': 'Item is required'}), 400 # Fail
        
        from models.users_model import get_user_lists, add_item_to_list
        lists_data = get_user_lists(user_email) # Current metadata

        # Internal helper to count unread items for UI badge sync
        def _unpurchased_total(lists_payload):
            try: # Nest safety
                total = 0
                for lst in (lists_payload.get('lists', []) or []): # Iterate lists
                    items = lst.get('items', []) or [] # Get items
                    # Count items that don't have the 'purchased' flag
                    total += sum(1 for it in items if not (isinstance(it, dict) and it.get('purchased')))
                return total # Return aggregate
            except Exception: # Fallback
                return 0
        
        # Default behavior: use active list if target isn't explicitly provided
        if not target_list_id:
            target_list_id = lists_data.get('active_list_id')
        
        if not target_list_id: # Absolute fallback
            return jsonify({'success': False, 'error': 'No list specified and no active list'}), 400 # Fail
        
        # Execute atomic write to MongoDB
        success = add_item_to_list(user_email, target_list_id, item)
        # Fetch fresh data if successful to update UI counts
        updated_lists = get_user_lists(user_email) if success else lists_data
        
        # Normalize and return updated list state
        sanitized_lists = helpers.sanitize_mongo_doc(updated_lists)
        return jsonify({'success': success, 'count': _unpurchased_total(sanitized_lists)})
    except Exception as e: # Catch
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/get-lists', methods=['GET']) # API: Metadata fetch
def get_lists_api(): # Simple utility to get all user list titles and IDs
    """Get all shopping lists for the current user"""
    try: # Start fetch
        user_email = session.get('user') # Identity
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        from models.users_model import get_user_lists # Primary source
        lists_data = get_user_lists(user_email) # Fetch doc
        
        return jsonify({'success': True, 'lists': helpers.sanitize_mongo_doc(lists_data.get('lists', []))})
    except Exception as e: # Catch
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail




@main_bp.route('/api/list/<list_id>/items', methods=['GET']) # API: Detailed item stream
def get_list_items_api(list_id): # The main data provider for the shopping list UI
    """Get all items for a specific shopping list"""
    try: # Start retrieval
        user_email = session.get('user') # Identity check
        if not user_email: # Guest?
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401 # Deny
        
        from models.users_model import get_user_lists # Fetch lists
        lists_data = get_user_lists(user_email)
        
        # 1. Locate the specific list in the user document
        target_list = None
        for lst in lists_data.get('lists', []):
            if lst.get('id') == list_id:
                target_list = lst
                break
        
        if not target_list: # List ID mismatch?
            return jsonify({'success': False, 'error': 'List not found'}), 404 # 404
        
        # 2. ENRICHMENT PHASE: Link text-only items to images and real product data
        raw_items = target_list.get('items', []) # Get items
        products = products_model.list_products() # Load product catalog for matching

        # Logic to find visual assets for typed strings or partial matches
        def find_product_by_name(name):
            if not name: return None
            name_l = name.lower() # Case insensitive comparison
            # High precision match first
            for p in products: 
                try: # Check exact string
                    if isinstance(p.get('name'), str) and p.get('name').lower() == name_l:
                        return p
                except Exception: continue
            # Keyword / Substring match second
            for p in products:
                try: # Check if part of name matches
                    if isinstance(p.get('name'), str) and name_l in p.get('name').lower():
                        return p
                except Exception: continue
            return None # No matching asset found

        placeholder_url = url_for('static', filename='placeholder.svg') # Icon fallback
        enriched_items = [] # Target collector
        
        # 3. Iterate through list items and 'decorate' them with metadata
        for entry in raw_items: # Scan
            # Determine starting name and image (if it was added from a deal page)
            if isinstance(entry, dict): # Item is a structured object
                name = entry.get('name') or ''
                img_val = entry.get('image') or ''
            else: # Item is a legacy simple string
                name = str(entry)
                img_val = ''

            # Attempt to find visual data in the database
            product = find_product_by_name(name)
            if not img_val and product: # Map database image to list item
                try: # Preference: 'image' field -> first element of 'images' array
                    img_val = product.get('image') or (product.get('images') and product.get('images')[0]) or ''
                except Exception: img_val = ''
            
            # Use placeholder if we still have no visual data
            if not img_val: img_val = placeholder_url

            # Map results to a standard dictionary format for JSON consumption
            if isinstance(entry, dict): # Preserve existing keys (purchased, list_id, etc)
                enriched = dict(entry)
                enriched['image'] = img_val
            else: # Convert string to object
                enriched = {'name': name, 'qty': 1, 'image': img_val}
            enriched_items.append(enriched)

        # Return standardized list payload with all enriched visual assets
        return jsonify({
            'success': True,
            'list_id': list_id,
            'name': target_list.get('name'),
            'items': enriched_items,
            'created_at': target_list.get('created_at')
        })
    except Exception as e: # Catch failure
        return jsonify({'success': False, 'error': str(e)}), 500 # Fail


@main_bp.route('/api/list/share', methods=['POST'])
def share_list_api():
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        data = request.get_json() or {}
        list_id = data.get('list_id')
        
        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400

        target_email = data.get('target_email')
        
        if target_email:
            # Our User-to-User Sync sharing logic
            role = data.get('role', 'view')
            from models.users_model import users_model
            success = users_model.share_list_with_user(user_email, list_id, target_email, role)
            
            if success:
                # Drop a notification
                from models.notifications_model import notifications_model        
                notifications_model.create_notification({
                    'user_email': target_email,
                    'type': 'list_share',
                    'title': 'New Shared List!',
                    'message': f'Exciting news! {user_email} has invited you to collaborate on a shopping list. You can now view and manage items together directly from your Lists page.',
                    'action_url': '/shopping-list'
                })
            return jsonify({'success': success})
            
        else:
            # Their Link-based sharing logic
            from models.users_model import get_user_by_email
            db = get_db()
            if db is None or 'lists' not in db.list_collection_names():
                return jsonify({'success': False, 'error': 'Lists collection unavailable'}), 500

            user = get_user_by_email(user_email) or {}
            owner_id = str(user.get('userId') or user_email)
            row = db.lists.find_one({'listId': list_id, 'userId': owner_id}, {'_id': 0, 'shareCode': 1})
            if not row:
                return jsonify({'success': False, 'error': 'List not found'}), 404

            share_code = row.get('shareCode') or uuid.uuid4().hex[:10]
            db.lists.update_one(
                {'listId': list_id, 'userId': owner_id},
                {'$set': {'shared': True, 'shareCode': share_code}},
            )
            return jsonify({'success': True, 'share_code': share_code})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/list/unshare', methods=['POST'])
def unshare_list_api():
    try:
        user_email = session.get('user')
        if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        data = request.get_json()
        list_id = data.get('list_id')
        target_email = data.get('target_email')

        from models.users_model import users_model
        success = users_model.remove_collaborator(user_email, list_id, target_email)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


        user = get_user_by_email(user_email) or {}
        owner_id = str(user.get('userId') or user_email)
        row = db.lists.find_one({'listId': list_id, 'userId': owner_id}, {'_id': 0, 'shareCode': 1})
        if not row:
            return jsonify({'success': False, 'error': 'List not found'}), 404

        share_code = row.get('shareCode') or uuid.uuid4().hex[:10]
        db.lists.update_one(
            {'listId': list_id, 'userId': owner_id},
            {'$set': {'shared': True, 'shareCode': share_code}},
        )
        return jsonify({'success': True, 'share_code': share_code})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/list/by-share/<share_code>', methods=['GET'])
def get_shared_list_api(share_code):
    """Fetch a shared public view of a list by share code."""
    try:
        db = get_db()
        if db is None:
            return jsonify({'success': False, 'error': 'Database unavailable'}), 500

        row = db.lists.find_one({'shareCode': share_code, 'shared': True}, {'_id': 0})
        if not row:
            return jsonify({'success': False, 'error': 'List not found'}), 404

        return jsonify({'success': True, 'list': helpers.sanitize_mongo_doc({
            'id': row.get('listId'),
            'name': row.get('name'),
            'items': row.get('items', []),
            'totalPrice': row.get('totalPrice', 0),
            'shared': row.get('shared', False),
            'shareCode': row.get('shareCode'),
            'updated_at': row.get('updatedAt'),
        })})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/public-lists', methods=['GET'])
def get_public_lists_api():
    """List public list templates and user-published lists."""
    try:
        db = get_db()
        if db is None or 'public_lists' not in db.list_collection_names():
            return jsonify({'success': True, 'items': []})

        type_filter = request.args.get('type')
        query = {'type': type_filter} if type_filter else {}
        rows = list(db.public_lists.find(query, {'_id': 0}).sort([('popularityScore', -1), ('createdAt', -1)]).limit(100))
        return jsonify({'success': True, 'items': helpers.sanitize_mongo_doc(rows)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/api/public-lists/create-from-list', methods=['POST'])
def create_public_list_from_user_list_api():
    """Publish one of the current user's lists as a public template/user list."""
    try:
        user_email = session.get('user')
        if not user_email:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        data = request.get_json() or {}
        list_id = data.get('list_id')
        if not list_id:
            return jsonify({'success': False, 'error': 'List ID is required'}), 400

        from models.users_model import get_user_by_email

        db = get_db()
        if db is None:
            return jsonify({'success': False, 'error': 'Database unavailable'}), 500

        user = get_user_by_email(user_email) or {}
        owner_id = str(user.get('userId') or user_email)
        row = db.lists.find_one({'listId': list_id, 'userId': owner_id}, {'_id': 0})
        if not row:
            return jsonify({'success': False, 'error': 'List not found'}), 404

        public_id = f"public_{uuid.uuid4().hex[:12]}"
        payload = {
            'id': public_id,
            'type': data.get('type') or 'user',
            'name_en': data.get('name_en') or row.get('name') or 'Public List',
            'name_de': data.get('name_de') or row.get('name') or 'Public List',
            'description_en': data.get('description_en') or None,
            'description_de': data.get('description_de') or None,
            'items': row.get('items', []),
            'creatorUserId': owner_id,
            'popularityScore': 0,
            'createdAt': __import__('datetime').datetime.utcnow(),
        }
        db.public_lists.insert_one(payload)
        return jsonify({'success': True, 'public_id': public_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



