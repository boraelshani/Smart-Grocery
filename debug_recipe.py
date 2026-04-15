import os
from app import app
from utils.recipe_ai import get_recipe_details

with app.app_context():
    print("API KEY:", os.environ.get("GEMINI_API_KEY"))
    res = get_recipe_details("Lentil Soup")
    print(res)
