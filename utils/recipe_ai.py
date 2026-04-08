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
        q = recipe_query.lower()
        
        # 1. Try TheMealDB dynamically for actual matching ingredients/instructions
        try:
            import requests, urllib.parse
            r = requests.get(f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(recipe_query)}", timeout=3).json()
            if r and r.get('meals') and r['meals']:
                meal = r['meals'][0]
                ingredients = []
                for i in range(1, 21):
                    ing = meal.get(f'strIngredient{i}')
                    meas = meal.get(f'strMeasure{i}')
                    if ing and ing.strip():
                        ingredients.append(f"{meas.strip() if meas else ''} {ing.strip()}".strip())
                instructions = [s.strip() for s in meal.get('strInstructions', '').split('.') if s.strip()]
                if instructions: instructions[-1] = instructions[-1] + "."
                return {"ingredients": ingredients, "instructions": instructions}
        except Exception:
            pass

        # 2. Dynamic Generic Fallback Engine based on words in recipe name
        base_ingredients = ["1 tbsp olive oil", "1 tsp salt", "1/2 tsp black pepper"]
        
        if "oat" in q or "porridge" in q:
            base_ingredients = ["1 cup oats", "2 cups milk or water", "1 tbsp honey or maple syrup", "1 sliced banana", "1 pinch cinnamon"]
        elif "pancake" in q or "waffle" in q:
            base_ingredients = ["1 cup all-purpose flour", "1 cup milk", "1 large egg", "2 tbsp melted butter", "2 tbsp sugar", "1 tsp baking powder"]
        elif "taco" in q or "fajita" in q or "burrito" in q or "quesadilla" in q:
            base_ingredients = ["4 flour or corn tortillas", "1 cup black beans", "1/2 cup shredded cheddar cheese", "1 chopped tomato", "1/2 jar salsa"]
            if "chicken" in q: base_ingredients.append("2 chicken breasts, sliced")
            if "beef" in q: base_ingredients.append("500g ground beef")
        elif "curry" in q or "dahl" in q or "dal" in q or "masala" in q:
            base_ingredients.extend(["1 cup red lentils or chickpeas", "1 can full-fat coconut milk", "2 tbsp curry powder", "1 yellow onion, diced", "2 cloves garlic, minced", "1 cup basmati rice"])
        elif "salad" in q or "greens" in q:
            base_ingredients = ["2 cups mixed greens or spinach", "1 cucumber, sliced", "1 cup cherry tomatoes", "2 tbsp vinaigrette dressing", "1/4 red onion, thinly sliced"]
            if "bean" in q or "lentil" in q: base_ingredients.append("1 cup cooked beans or lentils")
        elif "pasta" in q or "spaghetti" in q or "gnocchi" in q or "macaroni" in q or "noodle" in q:
            base_ingredients.extend(["400g pasta", "1 jar marinara or cream sauce", "1/4 cup grated parmesan", "2 cloves garlic"])
            if "lentil" in q: base_ingredients.append("1 cup brown lentils")
            if "meat" in q: base_ingredients.append("300g meatballs or ground meat")
        elif "rice" in q or "risotto" in q:
            base_ingredients.extend(["1.5 cups arborio or jasmine rice", "3 cups vegetable broth", "1 cup frozen peas", "1 diced onion"])
        elif "soup" in q or "stew" in q or "chili" in q or "broth" in q:
            base_ingredients.extend(["4 cups vegetable broth", "2 carrots, diced", "2 stalks celery, diced", "1 can crushed tomatoes", "1 can kidney beans"])
            if "peanut" in q: base_ingredients.extend(["1/2 cup creamy peanut butter", "1 sweet potato, cubed"])
        elif "egg" in q or "scramble" in q or "shakshuka" in q:
            base_ingredients = ["4 large eggs", "1 bell pepper, diced", "1 cup spinach", "2 slices whole wheat toast", "1 tbsp butter"]
            if "tofu" in q or "vegan" in q: base_ingredients[0] = "1 block firm tofu, crumbled"
        elif "chicken" in q:
            base_ingredients.extend(["2 chicken thighs or breasts", "1 cup white rice", "1 cup broccoli florets", "1 fresh lemon"])
        elif "beef" in q or "pork" in q or "sausage" in q or "steak" in q:
            base_ingredients.extend(["400g meat of choice", "2 russet potatoes, cubed", "1 cup green beans", "1 tbsp garlic powder"])
        else:
            base_ingredients.extend([f"250g main ingredient for {recipe_query}", "1 cup mixed vegetables", "1 cup rice, noodles, or potatoes", "1 yellow onion, sliced"])

        instructions = [
            f"Gather and prep all ingredients for your {recipe_query.title()}.",
            "Heat oil or butter in a large pan or pot over medium heat.",
            "Add the base aromatic ingredients (like onions and garlic) and cook until soft and fragrant.",
            "Stir in the main components, vegetables, and seasonings, and cook thoroughly.",
            "Combine any broths, sauces, or liquids and bring to a gentle simmer if needed.",
            "Cook until everything is tender and fully heated through.",
            "Garnish with a pinch of salt, pepper, or fresh herbs before serving hot."
        ]
        
        return {
            "ingredients": base_ingredients,
            "instructions": instructions
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
        raw_text = raw_text.strip().removeprefix('```json').removesuffix('```').strip()
        raw_text = raw_text.removeprefix('```').strip()

        # Try to parse it as JSON
        recipe_data = json.loads(raw_text)
        if isinstance(recipe_data, dict) and "ingredients" in recipe_data and "instructions" in recipe_data:
            return recipe_data
        # Fallback if structure is wrong but somehow parsed
        return fallback_details()
    except Exception as e:
        print(f"Error connecting to Gemini API or parsing response: {e}. Falling back to mock data.")
        return fallback_details()

def get_budget_meal_ideas(budget_str, preference="any", max_time="any"):
    """
    Uses Gemini to suggest 6 cheap meal ideas that roughly fit the given budget and dietary preference.
    Returns a strict JSON array of dicts: [{"name": "Meal Name", "time": "20 mins"}]
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        all_options = {
            "vegetarian": [
                {"name": "Lentil Soup", "time": "30 mins", "ingredients_range": "4-6"}, 
                {"name": "Cheese Quesadillas", "time": "10 mins", "ingredients_range": "2-4"}, 
                {"name": "Veggie Stir Fry", "time": "15 mins", "ingredients_range": "6-9"}, 
                {"name": "Potato Gnocchi", "time": "20 mins", "ingredients_range": "4-5"}, 
                {"name": "Eggplant Parm", "time": "45 mins", "ingredients_range": "5-8"}, 
                {"name": "Mushroom Risotto", "time": "40 mins", "ingredients_range": "6-8"},
                {"name": "Zucchini Fritters", "time": "25 mins", "ingredients_range": "5-7"},
                {"name": "Tomato Basil Soup", "time": "30 mins", "ingredients_range": "4-6"},
                {"name": "Sweet Potato Noodles", "time": "20 mins", "ingredients_range": "3-5"}
            ],
            "vegan": [
                {"name": "Chickpea Curry", "time": "25 mins", "ingredients_range": "6-9"}, 
                {"name": "Black Bean Tacos", "time": "15 mins", "ingredients_range": "5-7"}, 
                {"name": "Tomato Rice", "time": "20 mins", "ingredients_range": "3-5"}, 
                {"name": "Tofu Scramble", "time": "12 mins", "ingredients_range": "4-6"}, 
                {"name": "Lentil Pasta", "time": "15 mins", "ingredients_range": "2-4"}, 
                {"name": "Vegan Chili", "time": "35 mins", "ingredients_range": "8-12"},
                {"name": "Peanut Stew", "time": "30 mins", "ingredients_range": "6-8"},
                {"name": "Avocado Salad", "time": "10 mins", "ingredients_range": "3-5"},
                {"name": "Mushroom Tacos", "time": "20 mins", "ingredients_range": "4-6"}
            ],
            "any": [
                {"name": "Tomato Pasta", "time": "15 mins", "ingredients_range": "3-5"}, 
                {"name": "Fried Rice with Eggs", "time": "10 mins", "ingredients_range": "4-7"}, 
                {"name": "Lentil Soup", "time": "30 mins", "ingredients_range": "4-6"}, 
                {"name": "Potato Bake", "time": "50 mins", "ingredients_range": "3-5"}, 
                {"name": "Oatmeal", "time": "5 mins", "ingredients_range": "2-4"}, 
                {"name": "Bean Burritos", "time": "10 mins", "ingredients_range": "4-6"},
                {"name": "Roast Chicken Thighs", "time": "45 mins", "ingredients_range": "3-5"},
                {"name": "Pork Chops & Apples", "time": "30 mins", "ingredients_range": "4-6"},
                {"name": "Sausage and Peppers", "time": "25 mins", "ingredients_range": "3-5"}
            ]
        }
        return all_options.get(preference, all_options["any"])
        
    pref_instruction = f"The user prefers {preference} meals." if preference != "any" else ""
    time_instruction = f"The maximum preparation time should be {max_time} minutes." if max_time != "any" else ""
    
    prompt = f"""
    You are a strict, ultra-frugal budget culinary assistant. The user has a STRICT maximum budget of {budget_str}.
    {pref_instruction}
    {time_instruction}

    You MUST provide exactly 9 distinct, radically cheap meal ideas where the TOTAL COMBINED COST of all ingredients is GUARANTEED to be UNDER {budget_str}.
    
    Return a STRICT JSON array of objects. Each object MUST have THESE EXACT 3 KEYS:
    1. 'name': The name of the meal.
    2. 'time': Estimated time to cook (e.g. '20 mins').
    3. 'ingredients_range': A realistic range of unique ingredients needed (e.g. '7-12' or '5-8' or '10-12').
    
    CRITICAL REQUIREMENTS:
    - Generate a DIVERSE list of EXACTLY 9 items every time. Do not stop early.
    - Avoid common recipes like 'Pasta with Tomato Sauce' unless it's the only option. 
    - If the user specified 'Quick', focus on meals under 15 minutes.
    - MAKE SURE EVERY single object has the "ingredients_range" property.
    
    Do NOT return any markdown formatting, just the raw JSON array containing 9 objects.
    Example: 
    [
      {{"name": "Spaghetti Aglio e Olio", "time": "12 mins", "ingredients_range": "4-6"}}, 
      {{"name": "Lentil Stew", "time": "35 mins", "ingredients_range": "7-10"}},
      {{"name": "Egg Fried Rice", "time": "10 mins", "ingredients_range": "5-7"}}
    ]
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        raw_text = raw_text.strip().removeprefix('```json').removesuffix('```').strip()
        raw_text = raw_text.removeprefix('```').strip()
        meals = json.loads(raw_text)
        if isinstance(meals, list):
            return meals
        return []
    except Exception as e:
        print(f"Error connecting to Gemini API for budget meals: {e}")
        
        all_options = {
            "vegetarian": [
                {"name": "Lentil Soup", "time": "30 mins", "ingredients_range": "4-6"},
                {"name": "Cheese Quesadillas", "time": "10 mins", "ingredients_range": "2-4"},
                {"name": "Veggie Stir Fry", "time": "15 mins", "ingredients_range": "6-9"},
                {"name": "Potato Gnocchi", "time": "20 mins", "ingredients_range": "4-5"},
                {"name": "Eggplant Parm", "time": "45 mins", "ingredients_range": "5-8"},
                {"name": "Mushroom Risotto", "time": "40 mins", "ingredients_range": "6-8"},
                {"name": "Zucchini Fritters", "time": "25 mins", "ingredients_range": "5-7"},
                {"name": "Tomato Basil Soup", "time": "30 mins", "ingredients_range": "4-6"},
                {"name": "Sweet Potato Noodles", "time": "20 mins", "ingredients_range": "3-5"}
            ],
            "vegan": [
                {"name": "Chickpea Curry", "time": "25 mins", "ingredients_range": "6-9"},
                {"name": "Black Bean Tacos", "time": "15 mins", "ingredients_range": "5-7"},
                {"name": "Tomato Rice", "time": "20 mins", "ingredients_range": "3-5"},
                {"name": "Tofu Scramble", "time": "12 mins", "ingredients_range": "4-6"},
                {"name": "Lentil Pasta", "time": "15 mins", "ingredients_range": "2-4"},
                {"name": "Vegan Chili", "time": "35 mins", "ingredients_range": "8-12"},
                {"name": "Peanut Stew", "time": "30 mins", "ingredients_range": "6-8"},
                {"name": "Avocado Salad", "time": "10 mins", "ingredients_range": "3-5"},
                {"name": "Mushroom Tacos", "time": "20 mins", "ingredients_range": "4-6"}
            ],
            "any": [
                {"name": "Tomato Pasta", "time": "15 mins", "ingredients_range": "3-5"}, 
                {"name": "Fried Rice with Eggs", "time": "10 mins", "ingredients_range": "4-7"}, 
                {"name": "Lentil Soup", "time": "30 mins", "ingredients_range": "4-6"}, 
                {"name": "Potato Bake", "time": "50 mins", "ingredients_range": "3-5"}, 
                {"name": "Oatmeal", "time": "5 mins", "ingredients_range": "2-4"}, 
                {"name": "Bean Burritos", "time": "10 mins", "ingredients_range": "4-6"},
                {"name": "Roast Chicken Thighs", "time": "45 mins", "ingredients_range": "3-5"},
                {"name": "Pork Chops & Apples", "time": "30 mins", "ingredients_range": "4-6"},
                {"name": "Sausage and Peppers", "time": "25 mins", "ingredients_range": "3-5"}
            ]
        }
        return all_options.get(preference, all_options["any"])

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
        raw_text = raw_text.strip().removeprefix('```json').removesuffix('```').strip()
        raw_text = raw_text.removeprefix('```').strip()
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
