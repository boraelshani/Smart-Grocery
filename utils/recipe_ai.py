import os
import requests
import json

def get_recipe_details(recipe_query):
    """
    Calls the Google Gemini API (or fallback) to extract ingredients and step-by-step instructions.
    
    Returns a dict: {"ingredients": ["500g tomatoes", "1 onion"], "instructions": ["Chop tomatoes", "Fry onion"]}
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    def fallback_details():
        if "tomato soup" in recipe_query.lower():
            return {
                "ingredients": ["500g tomatoes", "1 yellow onion", "2 cloves garlic", "500ml vegetable broth", "olive oil"],
                "instructions": ["Chop the onion and garlic.", "Sauté in olive oil until soft.", "Add chopped tomatoes and broth.", "Simmer for 20 minutes, then blend."]
            }
        elif "carbonara" in recipe_query.lower():
            return {
                "ingredients": ["400g spaghetti", "150g pancetta or guanciale", "4 eggs", "100g parmesan cheese", "black pepper"],
                "instructions": ["Boil water and cook spaghetti.", "Fry the pancetta until crispy.", "Beat eggs with grated parmesan and black pepper.", "Mix pasta with pancetta, remove from heat, and quickly stir in egg mixture."]
            }
        return {
            "ingredients": ["2 apples", "1 loaf of bread", "1 liter of milk"],
            "instructions": ["Slice apples.", "Serve with bread and a glass of milk."]
        }

    if not api_key:
        print("Warning: No GEMINI_API_KEY found in environment variables.")     
        return fallback_details()
    
    prompt = f"""
    You are a culinary assistant. I will give you a recipe name or a description.
    You must return a STRICT JSON object representing the recipe details. The object MUST have two keys:
    1. 'ingredients': A JSON array of strings representing raw ingredients and quantities.
    2. 'instructions': A JSON array of strings representing the step-by-step cooking instructions.
    Do NOT return any markdown formatting, bullet points, or conversation. Just the raw JSON object.
    Example output: {{"ingredients": ["500g tomatoes", "1 onion", "200ml pasta water"], "instructions": ["Chop onion.", "Fry onion.", "Add tomatoes and simmer.", "Serve hot."]}}

    Recipe: {recipe_query}
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
        
        if response.status_code != 200:
            print(f"API Error: {response.text}")
            response.raise_for_status()
            
        data = response.json()
        
        # Extract response text
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]

        # Try to parse it as JSON
        recipe_data = json.loads(raw_text)
        if isinstance(recipe_data, dict) and "ingredients" in recipe_data and "instructions" in recipe_data:
            return recipe_data
        # Fallback if structure is wrong but somehow parsed
        return fallback_details()
    except Exception as e:
        print(f"Error connecting to Gemini API or parsing response: {e}. Falling back to mock data.")
        return fallback_details()

def get_budget_meal_ideas(budget_str):
    """
    Uses Gemini to suggest 3 cheap meal ideas that roughly fit the given budget.
    Returns a strict JSON array of strings (the meal titles).
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        return ["Tomato Pasta", "Fried Rice with Eggs", "Lentil Soup"]
        
    prompt = f"""
    You are a strict, ultra-frugal budget culinary assistant. The user has a STRICT maximum budget of {budget_str}.
    You MUST provide exactly 3 distinct, radically cheap meal ideas where the TOTAL COMBINED COST of all ingredients to make the meal is GUARANTEED to be UNDER {budget_str}.
    Only choose meals that rely on extremely basic, inexpensive ingredients like rice, pasta, beans, lentils, or cheap seasonal vegetables. Do NOT suggest meals with expensive meats, seafood, or exotic spices.
    Just return a STRICT JSON array of strings representing the meal names ONLY.
    Do NOT include prices or descriptions in the strings, just the meal names.
    Example when budget is $5: ["Spaghetti Aglio e Olio", "Vegetable Stir Fry", "Black Bean Tacos"]
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        meals = json.loads(raw_text)
        if isinstance(meals, list):
            return meals
        return []
    except Exception as e:
        print(f"Error connecting to Gemini API for budget meals: {e}")
        return ["Tomato Pasta", "Fried Rice with Eggs", "Lentil Soup"]

def get_ingredient_alternatives(recipe_query, missing_ingredients):
    """
    If specific ingredients for a recipe cannot be found, query Gemini
    for the closest commonly available alternatives.
    Returns a list of strings of the same length as the missing ingredients.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return [f"Alternative for {m}" for m in missing_ingredients]

    prompt = f"""
    You are a culinary assistant. I am making '{recipe_query}'. 
    I cannot find the following ingredients in my store: {json.dumps(missing_ingredients)}.
    Please provide a 1-to-1 list of common alternative ingredients I can use instead.
    Return ONLY a strict JSON array of strings of the same length as the missing ingredients.
    Example: if I am missing ['30g pine nuts', 'guanciale'], return ['30g walnuts', 'bacon'].
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        alts = json.loads(raw_text)
        if isinstance(alts, list) and len(alts) == len(missing_ingredients):
            return alts
        return missing_ingredients # Fallback if shape mismatches
    except Exception as e:
        print(f"Error connecting to Gemini API for alternatives: {e}")
        return missing_ingredients

# Quick test if run directly
if __name__ == "__main__":
    ## Note: To test this, make sure to load your .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    test_recipe = "Spaghetti Bolognese"
    print(f"Testing recipe: {test_recipe}")
    ingredients = get_recipe_ingredients(test_recipe)
    print("Resulting Ingredients:", ingredients)
