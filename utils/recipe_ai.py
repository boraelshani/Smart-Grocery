import os
import requests
import json

def get_recipe_ingredients(recipe_query):
    """
    Calls the OpenAI API (or another LLM) to convert a recipe name or text
    into a clean JSON array of generic ingredients.
    
    Returns a list of strings, e.g., ["500g tomatoes", "1 onion", "garlic"]
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    
    def fallback_ingredients():
        if "tomato soup" in recipe_query.lower():
            return ["500g tomatoes", "1 yellow onion", "2 cloves garlic", "500ml vegetable broth", "olive oil"]
        elif "carbonara" in recipe_query.lower():
            return ["400g spaghetti", "150g pancetta or guanciale", "4 eggs", "100g parmesan cheese", "black pepper"]
        return ["2 apples", "1 loaf of bread", "1 liter of milk"] # generic fallback

    if not api_key:
        print("Warning: No OPENAI_API_KEY found in environment variables.")     
        return fallback_ingredients()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # We ask the AI to act as a strict JSON generator
    prompt = f"""
    You are a culinary assistant. I will give you a recipe name or a description.
    You must return a STRICT JSON array of strings representing the raw ingredients and their standard quantities needed to make this.
    Do NOT return any markdown formatting, bullet points, or conversation.
    Just the raw JSON array of strings.
    Example output: ["500g tomatoes", "1 onion", "200ml pasta water"]
    
    Recipe: {recipe_query}
    """

    payload = {
        "model": "gpt-3.5-turbo", # Or gpt-4o
        "messages": [
            {"role": "system", "content": "You output strict JSON arrays of strings."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract the content from the AI's response
        content = data["choices"][0]["message"]["content"].strip()
        
        # Try to parse it as JSON
        ingredients = json.loads(content)
        if isinstance(ingredients, list):
            return ingredients
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to OpenAI API: {e}. Falling back to mock data.")
        return fallback_ingredients()
    except json.JSONDecodeError as e:
        print(f"Error parsing AI response to JSON: {e}\nResponse was: {content}. Falling back to mock data.")
        return fallback_ingredients()

# Quick test if run directly
if __name__ == "__main__":
    ## Note: To test this, make sure to load your .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    test_recipe = "Spaghetti Bolognese"
    print(f"Testing recipe: {test_recipe}")
    ingredients = get_recipe_ingredients(test_recipe)
    print("Resulting Ingredients:", ingredients)
