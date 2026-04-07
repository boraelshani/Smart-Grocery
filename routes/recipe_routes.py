from flask import render_template, request, jsonify, session
from routes import recipe_bp
from utils.recipe_ai import get_recipe_details, get_budget_meal_ideas, get_ingredient_alternatives
from utils.recipe_matcher import match_ingredients_to_products
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

        # Filter out ingredients that STILL have no matches
        # (user requested: "when there is not a ingrediant dont show it")
        final_results = [m for m in matched_results if m.get('matches')]

        # Structure the results exactly how the UI expects them
        formatted_results = []
        for item in final_results:
            matched_product = item['matches'][0] if item.get('matches') else None
            formatted_results.append({
                'original': item.get('original_request', ''),
                'cleaned': item.get('search_term', ''),
                'matched_product': matched_product
            })

        # Calculate total price for matched results
        total_price = sum(float(item['matched_product'].get('price_val', item['matched_product'].get('price', 0))) for item in formatted_results if item.get('matched_product'))

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
        if not budget:
            return jsonify({'success': False, 'error': 'Missing budget.'}), 400
        
        meals = get_budget_meal_ideas(budget)
        return jsonify({'success': True, 'meals': meals})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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

