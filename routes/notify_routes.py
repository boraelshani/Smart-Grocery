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



@main_bp.route('/notifications') # Standard path for user alerts
def notifications_page(): # Entry for alerts dashboard
    """Display and manage all notifications for the logged-in user."""
    user_email = session.get('user') # Identity
    if not user_email: # Guest?
        return redirect(url_for('auth.login')) # Redirect to login
    
    from models.notifications_model import get_user_notifications, get_unread_count, notifications_model # Internal imports
    from datetime import datetime # Time helper
    
    # 1. MAINTENANCE: HOUSEKEEPING
    # Clean up old notifications (older than 7 days) to keep database efficient
    try: # Start cleanup block
        notifications_model.cleanup_old_notifications(7) # Wipe old history
    except Exception as e: # Failure?
        print(f"Error cleaning up notifications: {e}") # Log warning
    
    # 2. DATA RETRIEVAL
    # Fetch user alerts, filtering out redundant system-level notifications
    persistent_notifications = get_user_notifications(user_email, unread_only=False, limit=50) # Get top 50
    ignored_types = ['deal_alert', 'new_deal', 'price_drop'] # Types that are noisy in the list
    
    # Filter for cleaner main notification display
    notifications = [n for n in persistent_notifications if n.get('type') not in ignored_types] # Execute filter
    
    # Calculate initial unread count just from the notifications WE ARE SHOWING from DB
    current_unread_count = len([n for n in notifications if not n.get('read')]) # Filter and count unread base items

    # 3. DYNAMIC NOTIFICATIONS INJECTION
    # We supplement real database alerts with 'suggestions' based on newest store data
    try: # Start injection block
        # Helper to normalize dates for sorting (Mixed BSON/Datetime objects)
        def get_naive_date(d): # Define normalizer
            if d is None: return datetime.min # Fallback to epoch
            if d.tzinfo is not None: # timezone aware?
                return d.replace(tzinfo=None) # Strip timezone
            return d # Keep as is

        # A. INJECT PRICE DROPS (10 Latest Featured Deals)
        latest_deals_drop = featured_deals_model.get_latest_deals(limit=10) # Fetch recent promos
        
        for d in latest_deals_drop: # Process each deal
            d_id = str(d.get('id') or d.get('_id')) # Normalize ID
            
            # Construct sensible offer text (Badge content)
            offer_text = d.get('discount_label') or d.get('offer') or d.get('offer_text') # Priority chain
            if not offer_text and d.get('discount_percent'): # Fallback to percentage
                offer_text = f"{d.get('discount_percent')}% OFF" # Format
            
            # Build ephemeral notification object
            n = { # Define alert document
                'id': f"suggestion_fd_{d_id}", # Unique prefix for dynamic items
                'type': 'price_drop', # Group under 'Price Drops' section
                'title': f"Price Drop: {d.get('title') or d.get('product_name') or d.get('name')}", # Subject
                'message': d.get('description') or "Check out this amazing offer available now!", # Body
                'created_at': get_naive_date(d.get('_id').generation_time), # Extracted from Mongo ID
                'read': False, # Mark as new
                'deal_id': d_id, # Link back to deal
                'product_name': d.get('title') or d.get('product_name') or d.get('name'), # Context
                'product_image': d.get('image') or d.get('image_url'), # Asset
                'store_name': d.get('store'), # Retailer
                'price': d.get('price') or d.get('new_price'), # Current cost
                'old_price': d.get('original_price') or d.get('old_price'), # Baseline cost
                'offer_name': offer_text, # Promo badge
                'action_url': '#' # Placeholder for JS click handler
            } # End alert
            notifications.append(n) # Merge into feed
            current_unread_count += 1 # Increment UI count

        # B. INJECT MULTIBUY OFFERS (5 Latest)
        latest_multibuy = multibuy_offers_model.get_latest_offers(limit=5) # Fetch BOGOs
    
        for m_offer in latest_multibuy: # Process BOGOs
            m_id = str(m_offer.get('id') or m_offer.get('_id')) # ID
            
            # Construct human labels e.g. "Buy 2 Get 1 Free"
            offer_text = m_offer.get('title') # Check custom title
            if offer_text == "Special Offer" or not offer_text or m_offer.get('buy_quantity'): # Generic or data-driven?
                buy = m_offer.get('buy_quantity') or m_offer.get('min_quantity') # Buy qty
                get = m_offer.get('free_quantity') # Get qty
                if buy and get: # Both present?
                    offer_text = f"Buy {buy} Get {get} Free" # Standard format
                elif buy: # Single threshold?
                    offer_text = f"Buy {buy}+ Deal" # Threshold format
            
            n = { # Build document
                'id': f"suggestion_multi_{m_id}", # Prefix
                'type': 'deal_alert', # Group under 'Deals' section
                'title': f"Multibuy Offer", # Subject
                'message': "Buy more, save more with this special offer!", # Body
                'created_at': get_naive_date(m_offer.get('_id').generation_time), # Date
                'read': False, # Status
                'deal_id': m_id, # Link
                'product_name': m_offer.get('title') or m_offer.get('product_name'), # Context
                'product_image': m_offer.get('image'), # Asset
                'store_name': m_offer.get('store'), # Retailer
                'price': m_offer.get('price'), # Cost
                'old_price': m_offer.get('original_price'), # Baseline
                'offer_name': offer_text, # Label
                'action_url': '#' # Action
            } # End alert
            notifications.append(n) # Merge
            current_unread_count += 1 # Sync count

        # C. INJECT QUANTITY DISCOUNTS (3 Latest)
        latest_qty = quantity_discounts_model.get_latest_discounts(limit=3) # Fetch bulk savers
        
        for q_disc in latest_qty: # Process bulk savers
            q_id = str(q_disc.get('id') or q_disc.get('_id')) # ID
            
            # Formulate label "Buy 3+ save 15%" from tier data
            offer_text = "Bulk Savings" # Default
            tiers = q_disc.get('tiers') or q_disc.get('discount_tiers') or [] # Access tiers
            if tiers and len(tiers) > 0: # Has data?
                first = tiers[0] # Take base tier
                qty = first.get('quantity') or first.get('min_qty') # Qty
                disc = first.get('discount') or first.get('discount_percentage') or first.get('discount_percent') # Savings
                if qty and disc: # Found both?
                    offer_text = f"Buy {qty}+ Save {disc}%" # Build string

            n = { # Build document
                'id': f"suggestion_qty_{q_id}", # Prefix
                'type': 'deal_alert', # Section
                'title': "Quantity Discount", # Subject
                'message': "Stock up and save with volume discounts!", # Body
                'created_at': get_naive_date(q_disc.get('_id').generation_time), # Date
                'read': False, # Status
                'deal_id': q_id, # Link
                'product_name': q_disc.get('product_name'), # Context
                'product_image': q_disc.get('image'), # Asset
                'store_name': q_disc.get('store'), # Retailer
                'price': q_disc.get('base_price') or q_disc.get('price'), # Price
                'offer_name': offer_text, # Badge
                'action_url': '#' # Action
            } # End alert
            notifications.append(n) # Merge
            current_unread_count += 1 # Sync

        # 4. FINAL SORTING
        # Merge DB alerts and suggestions into a single chronological feed
        notifications.sort(key=lambda x: get_naive_date(x.get('created_at')), reverse=True) # Newest first

    except Exception as e: # Handle injection block failure
        print(f"Error injecting dynamic notifications: {e}") # Log warning
        # Recover: continue with just DB results

    # 5. USER PERSISTENCE: READ STATUS
    # Epic/Dynamic items don't live in the notifications collection, so we track their 'read' state in the User profile.
    try: # Start persistence block
        from models.users_model import get_user_by_email # Helper
        user = get_user_by_email(user_email) # Fetch user
        # Extract set of IDs that the user has acknowledged
        read_dynamic_ids = set(user.get('read_dynamic_notifications', [])) if user else set() # Build set
        
        # Apply the user's personal read state to the dynamic suggestions
        for n in notifications: # Scan combined list
            if n['id'].startswith('suggestion_') and n['id'] in read_dynamic_ids: # Match dynamic ID?
                n['read'] = True # Mark as already seen
    except Exception as e: # Handle profile lookup failure
        print(f"Error applying read status persistence: {e}") # Log

    # 6. UNREAD CALCULATION
    # Re-calculate final count based on both DB states and dynamic states
    current_unread_count = len([n for n in notifications if not n.get('read')]) # Filter unread
    unread_count = current_unread_count # Final count
    
    # 7. RENDER VIEW
    return render_template( # Display
        'notifications.html', # Template
        notifications=notifications, # Hybrid feed
        unread_count=unread_count # Bubble count
    )




@main_bp.route('/api/notifications/<notification_id>', methods=['DELETE']) # API: Removal
def delete_notification(notification_id): # Logic for dismissing alerts
    """Delete a specific notification from the database or session."""
    try: # Start API block
        user_email = session.get('user') # Identity check
        if not user_email: # Guest?
            return jsonify({'error': 'Not logged in'}), 401 # Unauthorized exit
        
        # Handle ephemeral/suggestion notifications (These aren't in Mongo, just return success)
        if notification_id.startswith('suggestion_'): # Dynamic item?
            return jsonify({'success': True}) # Client will hide it visually
        
        from models.notifications_model import delete_notification as delete_notif # Persistence helper
        
        # Perform permanent deletion from MongoDB
        success = delete_notif(notification_id, user_email) # Run command
        
        if success: # Deleted?
            return jsonify({'success': True}) # OK
        else: # Fail?
            return jsonify({'error': 'Failed to delete notification'}), 500 # Server error
    
    except Exception as e: # Catch crashes
        return jsonify({'error': str(e)}), 500 # Error envelope




@main_bp.route('/api/notifications/unshown', methods=['GET']) # API: Toast system
def get_unshown_notifications(): # Fetch alerts that haven't been 'popped up' as UI toasts
    """Get notifications that haven't been shown as toasts yet"""
    try: # Start fetch
        user_email = session.get('user') # Identity check
        if not user_email: # Guest?
            return jsonify({'notifications': []}) # No toasts for guests
        
        from models.notifications_model import get_user_notifications # Fetcher
        
        # Pull latest unread records
        all_notifications = get_user_notifications(user_email, unread_only=True, limit=10)
        
        # Filter for 'new_deal' type (Only these trigger the floating UI Toast/Banner)
        new_deal_notifications = [n for n in all_notifications if n.get('type') == 'new_deal']
        
        return jsonify({'notifications': new_deal_notifications}) # Return list for JS handler
    
    except Exception as e: # Handling error
        print(f'ERROR fetching unshown notifications: {e}') # Log
        return jsonify({'error': str(e)}), 500 # Fail status




@main_bp.route('/api/notifications/mark-read', methods=['POST']) # API: UI state sync
def mark_notifications_read(): # Bulk mark alerts as read when user clicks the notifications bell
    """Mark notifications as read"""
    try: # Start write
        user_email = session.get('user') # Identity check
        if not user_email: # Guest?
            return jsonify({'error': 'Not logged in'}), 401 # Protect
        
        data = request.get_json() # Body
        notification_ids = data.get('notification_ids', []) # Priority targets
        
        if not notification_ids or not isinstance(notification_ids, list): # Validation
            return jsonify({'error': 'Notification IDs required'}), 400
        
        from models.notifications_model import mark_as_read # Logic helper
        
        # Tracking variables for batch processing
        success_count = 0
        ids_to_mark = [] # Real Mongo documents
        dynamic_ids = [] # Ephemeral suggestions
        
        # Categorize IDs based on their origin (Mongo vs Suggestion Engine)
        for nid in notification_ids: # Scan array
            if str(nid).startswith('suggestion_'): # Suggestion?
                dynamic_ids.append(str(nid)) # Add to profile tracker
            else: # Real?
                ids_to_mark.append(nid) # Add to notification tracker

        # PERSISTENCE FOR DYNAMIC ITEMS: Save read status in User Profile array
        if dynamic_ids: # Any dynamic hits?
            try: # Nest safety
                from models.users_model import users_model # Use static/model methods
                users_model.mark_dynamic_notifications_read(user_email, dynamic_ids) # Update profile
                success_count += len(dynamic_ids) # Update total
            except Exception as e: # Handle profile update error
                print(f"Error saving dynamic read status: {e}") # Log warning

        # PERSISTENCE FOR REAL ITEMS: Update individual documents in MongoDB
        if ids_to_mark: # Any real hits?
            for nid in ids_to_mark: # Iterate
                if mark_as_read(nid, user_email): # Run $set in database
                    success_count += 1 # Update total
        
        return jsonify({'success': True, 'marked_count': success_count}) # Success
    
    except Exception as e: # Catch API crashes
        return jsonify({'error': str(e)}), 500 # Fail status




@main_bp.route('/api/notifications/mark-all-read', methods=['POST']) # API: Reset all bubbles
def mark_all_notifications_read(): # Efficiently clears the entire unread notification feed
    """Mark all notifications for the user as read"""
    try: # Start write
        user_email = session.get('user') # Identity check
        if not user_email: # Guest?
            return jsonify({'error': 'Not logged in'}), 401 # Deny
        
        from models.notifications_model import notifications_model # Import
        
        # 1. Update all persistent notification documents in MongoDB
        notifications_model.mark_all_as_read(user_email)
        
        # 2. Synchronize Dynamic items (Suggestions)
        # We re-fetch current IDs to ensure we mark everything the user just saw
        try: # Nest safety
            dynamic_ids = [] # Collector
            
            # Featured Deals IDs (Latest 10)
            fds = featured_deals_model.get_latest_deals(limit=10)
            dynamic_ids.extend([f"suggestion_fd_{str(d.get('_id'))}" for d in fds])
            
            # Multibuy IDs (Latest 5)
            mbs = multibuy_offers_model.get_latest_offers(limit=5)
            dynamic_ids.extend([f"suggestion_multi_{str(m.get('_id'))}" for m in mbs])
            
            # Quantity IDs (Latest 3)
            qds = quantity_discounts_model.get_latest_discounts(limit=3)
            dynamic_ids.extend([f"suggestion_qty_{str(q.get('_id'))}" for q in qds])
            
            if dynamic_ids: # Found suggestions?
                from models.users_model import users_model # Profile helper
                users_model.mark_dynamic_notifications_read(user_email, dynamic_ids) # Batch update profile
        except Exception as e: # Handle suggestion sync failure
            print(f"Error marking all dynamic as read: {e}") # Log
        
        return jsonify({'success': True}) # OK
    
    except Exception as e: # Catch crash
        return jsonify({'error': str(e)}), 500 # Fail




@main_bp.route('/api/notifications/clear-all', methods=['DELETE']) # API: Feed cleanup
def clear_all_notifications(): # Permanently deletes all user's notification records
    """Delete all notifications for the user"""
    try: # Start delete
        user_email = session.get('user') # Identity
        if not user_email: # Guest?
            return jsonify({'error': 'Not logged in'}), 401 # Deny
        
        from models.notifications_model import notifications_model # DAO
        
        # Perform permanent mass deletion from MongoDB
        success = notifications_model.delete_all_notifications(user_email)
        
        return jsonify({'success': True}) # OK
    
    except Exception as e: # Handle failure
        return jsonify({'error': str(e)}), 500 # Fail


