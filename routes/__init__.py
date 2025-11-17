from flask import Blueprint

# Create blueprints for route organization
main_bp = Blueprint('main', __name__)
auth_bp = Blueprint('auth', __name__)

from .main_routes import *
from .auth_routes import *
