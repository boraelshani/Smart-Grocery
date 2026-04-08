from flask import Blueprint

compare_bp = Blueprint('compare_engine', __name__)

from . import common
