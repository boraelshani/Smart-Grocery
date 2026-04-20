from flask import render_template, request, jsonify, session
from . import recipe_bp
from utils.recipe_ai import get_recipe_details, get_budget_meal_ideas, get_ingredient_alternatives
from utils.recipe_matcher import match_ingredients_to_products
from utils.recipe_image_fetcher import fetch_bing_image
from models.saved_recipes_model import get_saved_recipes, save_recipe, delete_recipe
import traceback

@recipe_bp.route('/recipe-planner')
def recipe_planner():
    user_email = session.get('user')
    saved_recipes = get_saved_recipes(user_email) if user_email else []
    return render_template('recipe_planner.html', saved_recipes=saved_recipes)

@recipe_bp.route('/api/recipe/generate', methods=['POST'])
def generate_recipe_plan():
    try:
        data = request.get_json()
        if not data or 'recipe' not in data: return jsonify({'success': False, 'error': 'Missing recipe name.'}), 400
        recipe_query = data['recipe'].strip()
        if not recipe_query: return jsonify({'success': False, 'error': 'Recipe name empty.'}), 400
        recipe_data = get_recipe_details(recipe_query)
        raw_ingredients = recipe_data.get("ingredients", [])
        instructions = recipe_data.get("instructions", [])
        if not raw_ingredients: return jsonify({'success': False, 'error': 'Failed to generate ingredients.'}), 500
        matched_results = match_ingredients_to_products(raw_ingredients)
        unmatched_indices = []; missing_ing_texts = []
        for i, item in enumerate(matched_results):
            if not item.get('matches'): unmatched_indices.append(i); missing_ing_texts.append(item['original_request'])
        if missing_ing_texts:
            alternatives = get_ingredient_alternatives(recipe_query, missing_ing_texts)
            alt_matched_results = match_ingredients_to_products(alternatives)
            for idx, alt_res in zip(unmatched_indices, alt_matched_results):
                if alt_res.get('matches'):
                    orig = missing_ing_texts[unmatched_indices.index(idx)]
                    alt_res['original_request'] = f"{alt_res['original_request']} (Alt for {orig})"
                    matched_results[idx] = alt_res
        formatted_results = []
        for item in matched_results:
            matched_product = item['matches'][0] if item.get('matches') else None
            formatted_results.append({'original': item.get('original_request', ''), 'cleaned': item.get('search_term', ''), 'matched_product': matched_product})
        total_price = sum(float(item['matched_product'].get('price_val', item['matched_product'].get('price', 0))) for item in formatted_results if item.get('matched_product'))
        return jsonify({
            'success': True, 'recipe': recipe_query, 'results': formatted_results, 'instructions': instructions,
            'total_items': len(formatted_results), 'matched_items': len([i for i in formatted_results if i.get('matched_product')]),
            'total_price': total_price
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@recipe_bp.route('/api/recipe/budget', methods=['POST'])
def generate_budget_ideas():
    try:
        data = request.get_json()
        budget = data.get('budget', '').strip()
        preference = data.get('preference', 'any').strip()
        max_time = data.get('max_time', 'any').strip()
        if not budget: return jsonify({'success': False, 'error': 'Missing budget.'}), 400
        meals = get_budget_meal_ideas(budget, preference, max_time)
        return jsonify({'success': True, 'meals': meals})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@recipe_bp.route('/api/recipe/image', methods=['GET'])
def get_recipe_image_proxy():
    query = request.args.get('q', '').strip()
    if not query: return jsonify({'success': False, 'url': None}), 400
    try:
        url = fetch_bing_image(query)
        return jsonify({'success': True, 'url': url})
    except Exception as e:
        return jsonify({'success': False, 'url': None, 'error': str(e)}), 500

@recipe_bp.route('/api/recipe/save', methods=['POST'])
def api_save_recipe():
    user_email = session.get('user')
    if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    try:
        data = request.get_json()
        success, recipe_doc = save_recipe(user_email, data)
        return jsonify({'success': success, 'recipe': recipe_doc if success else None, 'error': recipe_doc if not success else None})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@recipe_bp.route('/api/recipe/delete/<recipe_id>', methods=['DELETE'])
def api_delete_recipe(recipe_id):
    user_email = session.get('user')
    if not user_email: return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    try:
        success, err = delete_recipe(user_email, recipe_id)
        return jsonify({'success': success, 'error': err if not success else None})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@recipe_bp.route('/api/recipe/smart', methods=['POST'])

def smart_search():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        query = data.get('query', '')
        budget_filter = data.get('budget', '')
        preference = data.get('preference', 'any')
        max_time = data.get('max_time', 'any')
        max_ingredients = data.get('max_ingredients', 'any')
        exact = data.get('exact', False)
        
        import re
        
        # If user put price inside the main search (e.g. "Spaghetti 15$" or "15$ chicken")
        # Let's extract the budget part if budget_filter is empty.
        if not budget_filter:
            money_match = re.search(r'(\d+(\.\d+)?)\s*(€|\$|euro|dollar|euros|dollars)?\b', query.lower())
            if money_match:
                budget_filter = money_match.group(0).strip()
                # Remove the money part from the query
                query = query.replace(money_match.group(0), "").replace(money_match.group(0).upper(), "").replace(money_match.group(0).title(), "").strip()
        
        # Check if the query is *only* a budget now (meaning it was purely "15$" before)
        if not query or query.lower() in ["budget meals", "cheap meals", "deals", "ideas"]:
            if not budget_filter:
                budget_filter = "15 euros"
            query = ""


        # IDEA MODE - Return 9 meal options to choose from
        if not exact:
            try:
                ai_budget = f"{budget_filter} euros/dollars" if re.match(r'^\d+(\.\d+)?$', budget_filter) else (budget_filter if budget_filter else "any")
                from utils.recipe_ai import get_budget_meal_ideas
                meals = get_budget_meal_ideas(query, ai_budget, preference, max_time, max_ingredients)
                return jsonify({
                    'success': True,
                    'type': 'budget',
                    'meals': meals
                })
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500
                
        # EXACT MODE - Return real ingredients and instructions for a specific meal
        from utils.recipe_ai import get_recipe_details
        from utils.recipe_matcher import match_ingredients_to_products
        
        recipe_data = get_recipe_details(query, budget_str=budget_filter)
        if not recipe_data or not recipe_data.get("ingredients"):
            return jsonify({'success': False, 'error': f"Could not generate ingredients for '{query}'."}), 500
        
        raw_ingredients = recipe_data.get("ingredients", [])
        instructions = recipe_data.get("instructions", [])
        
        matched_results = match_ingredients_to_products(raw_ingredients)
        
        for item in matched_results:
            if 'matches' in item and item['matches']:
                for m in item['matches']:
                    if 'image' in m and 'image_url' not in m:
                        m['image_url'] = m['image']
                        
        return jsonify({
            'success': True,
            'type': 'recipe',
            'recipe': query,
            'ingredients': matched_results,
            'instructions': instructions
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
