from flask import Blueprint

# Create blueprints for route organization
main_bp = Blueprint('main', __name__)
auth_bp = Blueprint('auth', __name__)
admin_bp = Blueprint('admin', __name__)
compare_engine_bp = Blueprint('compare_engine', __name__, url_prefix='/api/compare')
recipe_bp = Blueprint('recipe', __name__)

from .ui_routes import *
from .lists_routes import *
from .api_routes import *
from .notify_routes import *
from .misc_routes import *
from .compare_engine_routes import *
from .recipe_routes import *

from .auth_routes import *
from .admin_routes import *
