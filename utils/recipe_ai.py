import os
import requests
import json

def get_recipe_details(recipe_query, budget_str=None):
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
            
            # First try exact match
            r = requests.get(f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(recipe_query)}", timeout=3).json()
            
            # If no match, try the last main word (e.g., "Creamy Lemon Spaghetti" -> try "Spaghetti" or "Lemon")
            if not r or not r.get('meals'):
                words = [w for w in recipe_query.split() if len(w) > 2]
                for word in reversed(words):
                    r_word = requests.get(f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(word)}", timeout=3).json()
                    if r_word and r_word.get('meals'):
                        r = r_word
                        break

            if r and r.get('meals') and r['meals']:
                import random
                # Try to find a meal that somewhat matches, or pick a random one from the results 
                # (seeded by recipe name so it's consistent for the same specific recipe)
                meals = r['meals']
                random.seed(recipe_query)
                meal = random.choice(meals)
                random.seed() # reset

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

        # Add variation based on common adjectives
        if "spicy" in q: base_ingredients.extend(["1 tbsp red chili flakes", "1 diced jalapeño"])
        if "creamy" in q: base_ingredients.extend(["1/2 cup heavy cream or coconut cream", "1/4 cup parmesan or nutritional yeast"])
        if "garlic" in q: base_ingredients.extend(["4 extra cloves garlic, minced", "2 tbsp butter or olive oil"])
        if "healthy" in q or "salad" in q or "bowl" in q: base_ingredients.extend(["2 cups fresh spinach", "1 sliced avocado", "1 tbsp lemon juice"])
        if "baked" in q or "cheese" in q: base_ingredients.extend(["1 cup shredded mozzarella", "1/2 cup breadcrumbs"])
        if "one-pot" in q or "quick" in q: base_ingredients.extend(["2 cups vegetable broth", "1 cup cherry tomatoes"])
        if "vegetarian" in q or "vegan" in q: base_ingredients.extend(["1 diced zucchini", "1 sliced bell pepper"])

        # Add generic random variation using hash of query to ensure different meals have different ingredients lengths and styles
        import hashlib
        h = int(hashlib.md5(recipe_query.encode()).hexdigest(), 16)
        extra_options = ["1 tsp smoked paprika", "1/2 cup chopped mushrooms", "1 tbsp soy sauce", "1/4 cup chopped parsley", "1/2 diced red onion", "1 lime, juiced"]
        base_ingredients.append(extra_options[h % len(extra_options)])
        if h % 2 == 0:
            base_ingredients.append(extra_options[(h+1) % len(extra_options)])

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
    
    budget_instruction = ""
    if budget_str:
        budget_instruction = f"The user is on a STRICT budget of {budget_str}. You MUST modify the {recipe_query} to be as cheap as possible by using fewer, more affordable ingredients, while remaining delicious."

    prompt = f"""
    You are a culinary assistant. I will give you a recipe name or a description.
    You must return a STRICT JSON object representing the recipe details. The object MUST have two keys:
    1. 'ingredients': A JSON array of strings representing raw ingredients and quantities.
    2. 'instructions': A JSON array of strings representing the step-by-step cooking instructions.
    {budget_instruction}
    Do NOT return any markdown formatting, bullet points, or conversation. Just the raw JSON object.
    Example output: {{"ingredients": ["500g tomatoes", "1 onion", "200ml pasta water"], "instructions": ["Chop onion.", "Fry onion.", "Add tomatoes and simmer.", "Serve hot."]}}

    Recipe: {recipe_query}
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
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

def get_budget_meal_ideas(query, budget_str="any", preference="any", max_time="any", max_ingredients="any"):
    """
    Uses Gemini to suggest meal ideas that roughly fit the given requirements.
    Returns a strict JSON array of dicts: [{"name": "Meal Name", "time": "20 mins", "ingredients_range": "4-6"}]
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        import random
        # Fallback simulation of filters
        base_list = []
        if query and query.lower() not in ["budget meals", "cheap meals", "deals", ""]:
            base_list = [
                {"name": f"Classic {query.title()}", "time": "20 mins", "ingredients_range": "5-8"},
                {"name": f"Spicy {query.title()}", "time": "25 mins", "ingredients_range": "6-9"},
                {"name": f"Creamy {query.title()}", "time": "30 mins", "ingredients_range": "5-7"},
                {"name": f"Vegetarian {query.title()}", "time": "20 mins", "ingredients_range": "4-8", "diet": "vegetarian"},
                {"name": f"One-Pot {query.title()}", "time": "15 mins", "ingredients_range": "4-6"},
                {"name": f"Garlic Butter {query.title()}", "time": "15 mins", "ingredients_range": "4-7"},
                {"name": f"Healthy {query.title()} Bowl", "time": "25 mins", "ingredients_range": "6-10", "diet": "vegan"},
                {"name": f"Baked {query.title()}", "time": "40 mins", "ingredients_range": "5-9"},
                {"name": f"Quick {query.title()} Salad", "time": "10 mins", "ingredients_range": "3-6", "diet": "vegan"}
            ]
        else:
            base_list = [
                {"name": "Tomato Pasta", "time": "15 mins", "ingredients_range": "3-5", "diet": "vegetarian"}, 
                {"name": "Fried Rice with Eggs", "time": "10 mins", "ingredients_range": "4-7", "diet": "vegetarian"}, 
                {"name": "Lentil Soup", "time": "30 mins", "ingredients_range": "4-6", "diet": "vegan"},
                {"name": "Potato Gnocchi", "time": "20 mins", "ingredients_range": "4-5", "diet": "vegetarian"},
                {"name": "Chickpea Curry", "time": "25 mins", "ingredients_range": "6-9", "diet": "vegan"},
                {"name": "Black Bean Tacos", "time": "15 mins", "ingredients_range": "5-7", "diet": "vegan"},
                {"name": "Zucchini Fritters", "time": "25 mins", "ingredients_range": "5-7", "diet": "vegetarian"},
                {"name": "Tomato Basil Soup", "time": "30 mins", "ingredients_range": "4-6", "diet": "vegan"},
                {"name": "Sweet Potato Noodles", "time": "20 mins", "ingredients_range": "3-5", "diet": "vegan"}
            ]
            
        filtered = []
        for m in base_list:
            # check diet
            if preference != "any":
                if preference == "vegan" and m.get("diet") != "vegan": continue
                if preference == "vegetarian" and m.get("diet") not in ["vegan", "vegetarian"]: continue
                if preference == "meat-based" and m.get("diet") in ["vegan", "vegetarian"]: continue
            
            # check time
            if max_time != "any":
                try:
                    time_val = int(m['time'].split()[0])
                    if time_val > int(max_time): continue
                except: pass
                
            # check ingredients limit
            if max_ingredients != "any":
                try:
                    max_val = int(m['ingredients_range'].split('-')[1])
                    if max_val > int(max_ingredients): continue
                except: pass
            
            # assign fake price for UI
            budget_val = 15.0
            if budget_str and budget_str != "any":
                try: budget_val = float(''.join(c for c in budget_str if c.isdigit() or c=='.'))
                except: pass
            fake_price = round(random.uniform(3.0, budget_val), 2)
            m['price_estimation'] = f"Est. {fake_price}€"
            filtered.append(m)
            
        if not filtered:
            # Instead of ignoring filters when no matches found, we dynamically create highly tailored suggestions
            t = "15 mins" if max_time == "any" else f"{max_time} mins"
            rng = "3-5" if max_ingredients == "any" else f"2-{max_ingredients}"
            d = ""
            if preference != "any" and preference != "meat-based":
                d = preference
                
            budget_val = 15.0
            if budget_str and budget_str != "any":
                try: budget_val = float(''.join(c for c in budget_str if c.isdigit() or c=='.'))
                except: pass
            
            import random
            def get_price():
                return f"Est. {round(random.uniform(3.0, budget_val), 2)}€"

            return [
                {"name": f"Rapid {preference.title() if preference != 'any' else 'Fresh'} {query.title() if query else 'Meal'}", "time": t, "ingredients_range": rng, "diet": d, "price_estimation": get_price()},
                {"name": f"Minimalist {query.title() if query else 'Bowl'}", "time": t, "ingredients_range": rng, "diet": d, "price_estimation": get_price()},
                {"name": f"Chef's Special {query.title() if query else 'Plate'}", "time": t, "ingredients_range": rng, "diet": d, "price_estimation": get_price()},
            ]
        return filtered
    pref_instruction = f"The user prefers {preference} meals." if preference != "any" else ""
    time_instruction = f"The maximum preparation time should be {max_time} minutes." if max_time != "any" else ""
    ingredients_instruction = f"The meal MUST use a maximum of {max_ingredients} ingredients." if max_ingredients != "any" else ""
    
    query_instruction = f"The user wants ideas specifically related to: '{query}'." if query and query.lower() not in ["budget meals", "cheap meals", "deals", ""] else "The user wants general budget meal ideas."
    budget_instruction = f"The user has a STRICT maximum budget of {budget_str}." if budget_str and budget_str != "any" else "Suggest generally affordable meals."

    prompt = f"""
    You are a culinary assistant. {query_instruction}
    {budget_instruction}
    {pref_instruction}
    {time_instruction}
    {ingredients_instruction}

    You MUST provide exactly 9 distinct meal ideas. If a budget is specified, the TOTAL COMBINED COST of all ingredients MUST be GUARANTEED to be UNDER {budget_str}.
    
    Return a STRICT JSON array of objects. Each object MUST have THESE EXACT 3 KEYS:
    1. 'name': The name of the meal.
    2. 'time': Estimated time to cook (e.g. '20 mins').
    3. 'ingredients_range': A realistic range of unique ingredients needed.
    4. 'price_estimation': Give an estimated realistic price for this meal under the budget constraints (e.g. 'Est. 8.50€').
    
    CRITICAL REQUIREMENTS:
    - Generate a DIVERSE list of EXACTLY 9 items every time. Do not stop early.
    - Avoid common recipes like 'Pasta with Tomato Sauce' unless it's the only option. 
    - If the user specified 'Quick', focus on meals under 15 minutes.
    - {ingredients_instruction}
    - MAKE SURE EVERY single object has the "ingredients_range" property.
    
    Do NOT return any markdown formatting, just the raw JSON array containing 9 objects.
    Example: 
    [
      {{"name": "Spaghetti Aglio e Olio", "time": "12 mins", "ingredients_range": "4-6"}}, 
      {{"name": "Lentil Stew", "time": "35 mins", "ingredients_range": "7-10"}},
      {{"name": "Egg Fried Rice", "time": "10 mins", "ingredients_range": "5-7"}}
    ]
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
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
        
    if not api_key:
        # If there's a specific query, try to mock some responses based on it
        if query and query.lower() not in ["budget meals", "cheap meals", "deals", ""]:
            return [
                {"name": f"Classic {query.title()}", "time": "20 mins", "ingredients_range": "5-8"},
                {"name": f"Spicy {query.title()}", "time": "25 mins", "ingredients_range": "6-9"},
                {"name": f"Creamy {query.title()}", "time": "30 mins", "ingredients_range": "5-7"},
                {"name": f"Vegetarian {query.title()}", "time": "20 mins", "ingredients_range": "4-8"},
                {"name": f"One-Pot {query.title()}", "time": "15 mins", "ingredients_range": "4-6"},
                {"name": f"Healthy {query.title()} Bowl", "time": "25 mins", "ingredients_range": "6-10"},
                {"name": f"Garlic Butter {query.title()}", "time": "15 mins", "ingredients_range": "4-7"},
                {"name": f"Baked {query.title()}", "time": "40 mins", "ingredients_range": "5-9"},
                {"name": f"Quick {query.title()} Salad", "time": "10 mins", "ingredients_range": "3-6"}
            ]
        return []

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
