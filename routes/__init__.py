from flask import Blueprint

# Base Blueprints
main_bp = Blueprint('main', __name__)
auth_bp = Blueprint('auth', __name__)

# Modular Package Imports
# The following lines import and register routes from the modern package structure.
# Each package (ui, auth, admin, api, compare, recipe) has its own __init__.py 
# that manages its internal exports.

# 1. UI Package (Home, Products, Stores details)
from .ui import *

# 2. Auth Package (Login, Signup)
from .auth import auth_bp

# 3. Admin Package (Dashboard, Management)
from .admin import admin_bp

# 4. API Package (Lists, Notifications, Common)
from .api import api_bp

# 5. Compare Package (Comparison Engine)
from .compare import compare_bp as compare_engine_bp

# 6. Recipe Package (Smart Planner)
from .recipe import recipe_bp
