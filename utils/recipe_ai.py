import os
import requests
import json

def get_recipe_ingredients(recipe_query):
    """
    Calls the Google Gemini API (or fallback) to convert a recipe name or text
    into a clean JSON array of generic ingredients.
    
    Returns a list of strings, e.g., ["500g tomatoes", "1 onion", "garlic"]
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    def fallback_ingredients():
        if "tomato soup" in recipe_query.lower():
            return ["500g tomatoes", "1 yellow onion", "2 cloves garlic", "500ml vegetable broth", "olive oil"]
        elif "carbonara" in recipe_query.lower():
            return ["400g spaghetti", "150g pancetta or guanciale", "4 eggs", "100g parmesan cheese", "black pepper"]
        return ["2 apples", "1 loaf of bread", "1 liter of milk"] # generic fallback

    if not api_key:
        print("Warning: No GEMINI_API_KEY found in environment variables.")     
        return fallback_ingredients()
    
    prompt = f"""
    You are a culinary assistant. I will give you a recipe name or a description.
    You must return a STRICT JSON array of strings representing the raw ingredients and their standard quantities needed to make this.
    Do NOT return any markdown formatting, bullet points, or conversation.      
    Just the raw JSON array of strings.
    Example output: ["500g tomatoes", "1 onion", "200ml pasta water"]

    Recipe: {recipe_query}
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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
        ingredients = json.loads(raw_text)
        if isinstance(ingredients, list):
            return ingredients
        return []
    except Exception as e:
        print(f"Error connecting to Gemini API or parsing response: {e}. Falling back to mock data.")
        return fallback_ingredients()

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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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

# Quick test if run directly
if __name__ == "__main__":
    ## Note: To test this, make sure to load your .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    test_recipe = "Spaghetti Bolognese"
    print(f"Testing recipe: {test_recipe}")
    ingredients = get_recipe_ingredients(test_recipe)
    print("Resulting Ingredients:", ingredients)
