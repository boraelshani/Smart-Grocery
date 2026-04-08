from dotenv import load_dotenv; load_dotenv(); from utils.recipe_ai import get_ingredient_alternatives; print(get_ingredient_alternatives('pesto pasta', ['30g pine nuts', '20g fresh basil']))
