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



@main_bp.route('/update-stores', methods=['POST']) # API/Form: Store Prefs
def update_stores(): # Update user's store tracking preferences
    """Handle preferred stores update from profile page"""
    user_email = helpers.get_user_email() # check auth
    if not user_email: # Guest?
        return redirect(url_for('auth.login')) # Send to login
        
    selected_stores = request.form.getlist('stores') # Get array from multi-select/checkboxes
    from models.users_model import update_user # Import logic
    update_user(user_email, {'preferred_stores': selected_stores}) # Persist to MongoDB
    
    # Trigger success alert in notifications feed
    try: # Start safety block
        notifications_model.create_system_notification( # Alert helper
            user_email, # User
            "Preferences Updated", # Title
            f"You have updated your preferred stores to: {', '.join(selected_stores) if selected_stores else 'None'}", # Msg
            priority="normal" # Level
        )
    except: # Log failure silently
        pass # Not critical
        
    return redirect(url_for('main.profile')) # Return to profile




@main_bp.route('/update-categories', methods=['POST']) # API/Form: Category Prefs
def update_categories(): # Update user's shopping category preferences
    """Handle preferred categories update from profile page"""
    user_email = helpers.get_user_email() # check auth
    if not user_email: # Guest?
        return redirect(url_for('auth.login')) # Protect
        
    selected_categories = request.form.getlist('categories') # Get selections
    from models.users_model import update_user # Import logic
    update_user(user_email, {'preferred_categories': selected_categories}) # Write to DB
    
    # Trigger success alert
    try: # Start safety block
        notifications_model.create_system_notification( # Alert helper
            user_email, # User
            "Preferences Updated", # Title
            f"You have updated your preferred categories to include {len(selected_categories)} items.", # Msg
            priority="normal" # Level
        )
    except: # Silent fail
        pass # Proceed
        
    return redirect(url_for('main.profile')) # Refresh view




@main_bp.route('/admin/status') # Diagnostics: DB Stats
def admin_status(): # Health check for database connectivity
    """Return JSON with collection counts so you can verify DB connectivity."""
    try: # Start check
        from models.models import get_db_info # Helper for counts
        info = get_db_info() # Run aggregation
        return jsonify({'db': info.get('collections', {})}) # Return stats
    except Exception as e: # Catch connection errors
        return jsonify({'error': str(e)}), 500 # Return error JSON



