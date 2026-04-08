from flask import Blueprint

api_bp = Blueprint('api', __name__)

from . import common
from . import list
from . import notification
