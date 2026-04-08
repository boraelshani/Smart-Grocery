from flask import Blueprint

admin_bp = Blueprint('admin', __name__)

# Register admin sub-routes
from . import common
# from . import import_routes 
# Disabling import_routes for now as it contains duplicate endpoints already in common.py
