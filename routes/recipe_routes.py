from flask import render_template, request, jsonify, session
from routes import recipe_bp
from utils.recipe_ai import get_recipe_details, get_budget_meal_ideas, get_ingredient_alternatives
from utils.recipe_matcher import match_ingredients_to_products
from utils.recipe_image_fetcher import fetch_bing_image
from models.saved_recipes_model import get_saved_recipes, save_recipe, delete_recipe
import traceback

@recipe_bp.route('/recipe-planner')
def recipe_planner():
    """Render the recipe planner page."""
    user_email = session.get('user')
    saved_recipes = get_saved_recipes(user_email) if user_email else []
    return render_template('recipe_planner.html', saved_recipes=saved_recipes)

@recipe_bp.route('/api/recipe/generate', methods=['POST'])
def generate_recipe_plan():
    """
    Generate an ingredient list from a recipe query and map it to products in the DB.
    """
    try:
        data = request.get_json()
        if not data or 'recipe' not in data:
            return jsonify({'success': False, 'error': 'Missing recipe name in request.'}), 400

        recipe_query = data['recipe'].strip()
        if not recipe_query:
            return jsonify({'success': False, 'error': 'Recipe name cannot be empty.'}), 400

        # Phase 1: Call Google Gemini (or fallback) to get generic ingredients and instructions
        print(f"Generating recipe details for: {recipe_query}")
        recipe_data = get_recipe_details(recipe_query)
        
        raw_ingredients = recipe_data.get("ingredients", [])
        instructions = recipe_data.get("instructions", [])
        
        if not raw_ingredients:
             return jsonify({'success': False, 'error': 'Failed to generate ingredients.'}), 500

        # Phase 2: Match generic ingredients against actual store products in MongoDB
        print(f"Matching {len(raw_ingredients)} ingredients to products...")
        matched_results = match_ingredients_to_products(raw_ingredients)
        
        # Phase 3: Retry missing ingredients with alternatives
        unmatched_indices = []
        missing_ing_texts = []
        for i, item in enumerate(matched_results):
            if not item.get('matches'):
                unmatched_indices.append(i)
                missing_ing_texts.append(item['original_request'])

        if missing_ing_texts:
            print(f"Found {len(missing_ing_texts)} unmatched items: {missing_ing_texts}")
            print("Asking AI for alternatives...")
            alternatives = get_ingredient_alternatives(recipe_query, missing_ing_texts)
            print(f"Proposed alternatives: {alternatives}")
            alt_matched_results = match_ingredients_to_products(alternatives)
            
            for idx, alt_res in zip(unmatched_indices, alt_matched_results):
                if alt_res.get('matches'):
                    orig = missing_ing_texts[unmatched_indices.index(idx)]
                    alt_res['original_request'] = f"{alt_res['original_request']} (Alt for {orig})"
                    matched_results[idx] = alt_res

        # We will keep all results so the UI can list them neutrally
        final_results = matched_results

        # --- BASKET-LEVEL OPTIMIZATION (Convenience Threshold) ---
        # 1. Determine the primary store for this recipe basket
        store_counts = {}
        for item in final_results:
            matches = item.get('matches', [])
            if matches:
                # The first match is the absolute cheapest for this ingredient
                cheapest_obj = matches[0].get('cheapest', {})
                s = cheapest_obj.get('store')
                if s:
                    store_counts[s] = store_counts.get(s, 0) + 1
        
        primary_store = None
        if store_counts:
            # Find the store with the most items
            primary_store = max(store_counts, key=store_counts.get)
            
        CONVENIENCE_THRESHOLD = 0.50

        # Structure the results exactly how the UI expects them
        formatted_results = []
        for item in final_results:
            matches = item.get('matches', [])
            matched_product = matches[0] if matches else None
            
            # 2. Check if we should override with a convenience pick from the primary store
            if matched_product and primary_store:
                cheapest_obj = matched_product.get('cheapest', {})
                current_store = cheapest_obj.get('store')
                current_price = float(cheapest_obj.get('price', 0))
                
                if current_store and current_store != primary_store:
                    found_convenience_pick = False
                    
                    # Look through all matched products for this ingredient
                    for alt_match in matches:
                        if found_convenience_pick:
                            break
                            
                        # Case A: Same product is sold at the primary store
                        for st in alt_match.get('stores', []):
                            s_name = st.get('store', st.get('name'))
                            s_price = st.get('price')
                            
                            if s_name == primary_store and s_price is not None:
                                price_diff = float(s_price) - current_price
                                if 0 <= price_diff <= CONVENIENCE_THRESHOLD:
                                    matched_product = alt_match.copy()
                                    matched_product['cheapest'] = {
                                        'store': primary_store,
                                        'price': float(s_price),
                                        'convenience_pick': True,
                                        'original_cheapest_store': current_store,
                                        'original_cheapest_price': current_price
                                    }
                                    found_convenience_pick = True
                                    break
                                    
                        # Case B: Primary store's cheapest overall product is different but within threshold
                        if not found_convenience_pick:
                            alt_cheapest = alt_match.get('cheapest', {})
                            alt_store = alt_cheapest.get('store')
                            alt_price = float(alt_cheapest.get('price', 0))
                            
                            if alt_store == primary_store:
                                price_diff = alt_price - current_price
                                if 0 <= price_diff <= CONVENIENCE_THRESHOLD:
                                    matched_product = alt_match.copy()
                                    matched_product['cheapest'] = {
                                        'store': primary_store,
                                        'price': alt_price,
                                        'convenience_pick': True,
                                        'original_cheapest_store': current_store,
                                        'original_cheapest_price': current_price
                                    }
                                    found_convenience_pick = True

            formatted_results.append({
                'original': item.get('original_request', ''),
                'cleaned': item.get('search_term', ''),
                'matched_product': matched_product
            })

        # Calculate total price for matched results
        total_price = 0.0
        for item in formatted_results:
            prod = item.get('matched_product')
            if prod:
                cheapest_obj = prod.get('cheapest')
                if cheapest_obj and 'price' in cheapest_obj:
                    total_price += float(cheapest_obj['price'])
                else:
                    total_price += float(prod.get('price_val', prod.get('price', 0)))

        return jsonify({
            'success': True,
            'recipe': recipe_query,
            'results': formatted_results,
            'instructions': instructions,
            'total_items': len(formatted_results),
            'matched_items': len([i for i in formatted_results if i.get('matched_product')]),
            'total_price': total_price
        })

    except Exception as e:
        print(f"Error generating recipe plan: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@recipe_bp.route('/api/recipe/budget', methods=['POST'])
def generate_budget_ideas():
    """Generates a list of meal titles that conceptually fit a given budget."""
    try:
        data = request.get_json()
        budget = data.get('budget', '').strip()
        preference = data.get('preference', 'any').strip()
        max_time = data.get('max_time', 'any').strip()
        if not budget:
            return jsonify({'success': False, 'error': 'Missing budget.'}), 400
        
        meals = get_budget_meal_ideas(budget, preference, max_time)
        return jsonify({'success': True, 'meals': meals})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@recipe_bp.route('/api/recipe/image', methods=['GET'])
def get_recipe_image_proxy():
    """Returns a highly relevant dynamic food image URL for a given meal name."""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'success': False, 'url': None}), 400
    try:
        url = fetch_bing_image(query)
        if url:
            return jsonify({'success': True, 'url': url})
        return jsonify({'success': False, 'url': None})
    except Exception as e:
        return jsonify({'success': False, 'url': None, 'error': str(e)}), 500

@recipe_bp.route('/api/recipe/save', methods=['POST'])
def api_save_recipe():
    user_email = session.get('user')
    if not user_email:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        success, recipe_doc = save_recipe(user_email, data)
        if success:
            return jsonify({'success': True, 'recipe': recipe_doc})
        else:
            return jsonify({'success': False, 'error': recipe_doc}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@recipe_bp.route('/api/recipe/delete/<recipe_id>', methods=['DELETE'])
def api_delete_recipe(recipe_id):
    user_email = session.get('user')
    if not user_email:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    try:
        success, err = delete_recipe(user_email, recipe_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': err}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

