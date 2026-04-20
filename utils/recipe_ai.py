import os
import requests
import json

def get_recipe_details(recipe_query, budget_str=None):
    """
    Calls the Google Gemini API (or fallback) to extract ingredients and step-by-step instructions.
    
    Returns a dict: {"ingredients": ["500g tomatoes", "1 onion"], "instructions": ["Chop tomatoes", "Fry onion"]}
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    def filter_ingredients(ing_list):
        # Filter out anything that is just water or salt
        filtered = []
        for ing in ing_list:
            filtered.append(ing)
        return filtered

    def fallback_details():
        q = recipe_query.lower()
        
        # 1. Try TheMealDB dynamically for actual matching ingredients/instructions
        try:
            import requests, urllib.parse
            
            # Autocorrect typos for fallback as well
            try:
                dm = requests.get(f"https://api.datamuse.com/sug?s={urllib.parse.quote(q)}", timeout=2).json()
                if dm and len(dm) > 0 and dm[0].get('score', 0) > 100:
                    q_corrected = dm[0]['word']
                else:
                    q_corrected = q
            except:
                q_corrected = q

            # First try exact match
            r = requests.get(f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(q_corrected)}", timeout=3).json()
            
            if not r or not r.get('meals'):
                r = requests.get(f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(q)}", timeout=3).json()
                
            # If no match, try the last main word (e.g., "Creamy Lemon Spaghetti" -> try "Spaghetti" or "Lemon")
            if not r or not r.get('meals'):
                words = [w for w in q_corrected.split() if len(w) > 2]
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
                
                # Filter out water / salt
                filtered_ingredients = []
                for item in ingredients:
                    filtered_ingredients.append(item)
                    
                instructions = [s.strip() for s in meal.get('strInstructions', '').split('.') if s.strip()]
                if instructions: instructions[-1] = instructions[-1] + "."
                return {"ingredients": filtered_ingredients, "instructions": instructions}
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
        elif any(w in q for w in ["cookie", "cake", "dessert", "sweet", "pie", "muffin", "brownie"]):
            base_ingredients = ["1 cup flour", "1/2 cup sugar", "1/2 cup butter, softened", "1 organic egg", "1 tsp vanilla extract", "1/2 tsp baking powder"]
            if "chocolate" in q: base_ingredients.append("1 cup chocolate chips")
            if "fruit" in q or "apple" in q or "berry" in q: base_ingredients.append("1 cup diced fruit")
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

        is_sweet = any(w in q for w in ["cookie", "cake", "dessert", "sweet", "pie", "muffin", "brownie", "pancake", "waffle", "oat", "porridge"])
        
        if is_sweet:
            instructions = [
                f"Preheat your oven or prepare your cooking surface for making {recipe_query.title()}.",
                "Gather and measure all dry ingredients (flour, sugar, baking powder) into a large bowl.",
                "In a separate bowl, mix the wet ingredients (butter, eggs, vanilla) until smooth.",
                "Gradually combine the wet and dry mixtures, stirring to form an even batter or dough.",
                "Add any extra mix-ins like chocolate chips or fruit.",
                "Portion the dough or pour the batter as needed.",
                "Bake or cook until golden brown and a toothpick inserted comes out clean.",
                "Allow to cool slightly before serving. Enjoy your sweet treat!"
            ]
        else:
            instructions = [
                f"Gather and prep all ingredients for your {recipe_query.title()}.",
                "Heat oil or butter in a large pan or pot over medium heat.",
                "Add the base aromatic ingredients (like onions and garlic) and cook until soft and fragrant.",
                "Stir in the main components, vegetables, and seasonings, and cook thoroughly.",
                "Combine any broths, sauces, or liquids and bring to a gentle simmer if needed.",
                "Cook until everything is tender and fully heated through.",
                "Garnish with a pinch of salt, pepper, or fresh herbs before serving hot."
            ]
        
        # Keep base ingredients as they are
        filtered_base_ingredients = []
        for item in base_ingredients:
            filtered_base_ingredients.append(item)

        return {
            "ingredients": filtered_base_ingredients,
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
            filtered_ing = []
            for item in recipe_data["ingredients"]:
                filtered_ing.append(item)
            recipe_data["ingredients"] = filtered_ing
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
    
    def fallback_ideas():
        import random
        import requests
        import urllib.parse
        
        q = query.lower().strip() if query else ""
        
        # 1. Autocorrect typos to significantly improve TheMealDB hits
        if q and q not in ["budget meals", "cheap meals", "deals"]:
            try:
                dm = requests.get(f"https://api.datamuse.com/sug?s={urllib.parse.quote(q)}", timeout=2).json()
                if dm and len(dm) > 0 and dm[0].get('score', 0) > 100:
                    q = dm[0]['word']
            except: pass
            
        # Determine category for better fallbacks
        base_category = "Miscellaneous"
        if any(w in q for w in ["cookie", "cake", "sweet", "chocolate", "pie", "dessert", "brownie", "pancake", "waffle"]):
            base_category = "Dessert"
        elif any(w in q for w in ["beef", "steak", "burger", "meat"]):
            base_category = "Beef"
        elif any(w in q for w in ["chicken", "poultry", "wing"]):
            base_category = "Chicken"
        elif any(w in q for w in ["veg", "salad", "plant", "beans", "lentils"]):
            base_category = "Vegetarian"
            
        real_meals = []
        
        try:
            # Try to get actual recipes from TheMealDB matching the query
            if q and q not in ["budget meals", "cheap meals", "deals"]:
                search_url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(q)}"
                r = requests.get(search_url, timeout=3).json()
                if r and r.get('meals'):
                    real_meals.extend(r['meals'])
                
                # If we didn't find much, search the last meaningful word
                if len(real_meals) < 3:
                    words = [w for w in q.split() if len(w) > 2]
                    for w in reversed(words):
                        r2 = requests.get(f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(w)}", timeout=3).json()
                        if r2 and r2.get('meals'):
                            for meal in r2['meals']:
                                if not any(m['idMeal'] == meal['idMeal'] for m in real_meals):
                                    real_meals.append(meal)
                            break
            
            # If still empty or no query, get random meals from a relevant category
            if len(real_meals) < 6:
                cat_url = f"https://www.themealdb.com/api/json/v1/1/filter.php?c={base_category}"
                r_cat = requests.get(cat_url, timeout=3).json()
                if r_cat and r_cat.get('meals'):
                    cat_meals = r_cat['meals']
                    random.shuffle(cat_meals)
                    
                    # We need the full details for the ingredients count constraint
                    for m_stub in cat_meals[:6]:
                        if not any(m['idMeal'] == m_stub['idMeal'] for m in real_meals):
                            detail_r = requests.get(f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={m_stub['idMeal']}", timeout=2).json()
                            if detail_r and detail_r.get('meals'):
                                real_meals.append(detail_r['meals'][0])
                                
        except Exception as e:
            print(f"TheMealDB fallback failed: {e}")
            pass
            
        # Format the actual recipes retrieved into the expected response format
        formatted_list = []
        for meal in real_meals[:9]:
            # Count actual ingredients
            ing_count = 0
            for i in range(1, 21):
                ing = meal.get(f"strIngredient{i}")
                if ing and ing.strip():
                    ing_count += 1
                    
            budget_val = 15.0
            if budget_str and budget_str != "any":
                try: budget_val = float(''.join(c for c in budget_str if c.isdigit() or c=='.'))
                except: pass
            
            formatted_list.append({
                "name": meal['strMeal'],
                "time": "30 mins",  # TheMealDB doesn't provide prep time 
                "ingredients_range": f"{max(3, ing_count-2)}-{ing_count+1}",
                "price_estimation": f"Est. {round(random.uniform(4.0, budget_val), 2)}€",
                "image_url": meal.get("strMealThumb") # Include real high-res picture
            })
            
        if formatted_list:
            # Apply time and ingredients filters to the real meals if possible
            filtered = []
            for m in formatted_list:
                if max_ingredients != "any":
                    try:
                        max_val = int(m['ingredients_range'].split('-')[1])
                        if max_val > int(max_ingredients): continue
                    except: pass
                filtered.append(m)
            
            if filtered:
                return filtered
            return formatted_list # if filters wiped everything out, ignore filters rather than returning nothing

        # Absolute last resort if APIs are fully broken (no internet connection) or no search results
        base_list = []
        is_sweet = base_category == "Dessert"
        if q and q not in ["budget meals", "cheap meals", "deals", ""]:
            # Reached a dead end, return empty list so the frontend can display 'Could not find...'
            return []
        else:
            base_list = [
                {"name": "Tomato Pasta", "time": "15 mins", "ingredients_range": "3-5", "diet": "vegetarian"}, 
                {"name": "Fried Rice with Eggs", "time": "10 mins", "ingredients_range": "4-7", "diet": "vegetarian"}, 
                {"name": "Lentil Soup", "time": "30 mins", "ingredients_range": "4-6", "diet": "vegan"}
            ]
            
        for m in base_list:
            budget_val = 15.0
            if budget_str and budget_str != "any":
                try: budget_val = float(''.join(c for c in budget_str if c.isdigit() or c=='.'))
                except: pass
            m['price_estimation'] = f"Est. {round(random.uniform(3.0, budget_val), 2)}€"
            
        return base_list
            
    if not api_key:
        return fallback_ideas()
        
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
        
    return fallback_ideas()

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
