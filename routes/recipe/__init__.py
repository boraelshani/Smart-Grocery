from flask import Blueprint

recipe_bp = Blueprint('recipe', __name__)

from . import common
