from flask import render_template, request, jsonify, session
from routes import recipe_bp
from utils.recipe_ai import get_recipe_ingredients
from utils.recipe_matcher import match_ingredients_to_products
import traceback

@recipe_bp.route('/recipe-planner')
def recipe_planner():
    """Render the recipe planner page."""
    return render_template('recipe_planner.html')

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

        # Phase 1: Call OpenAI (or fallback) to get generic ingredients
        print(f"Generating ingredients for recipe: {recipe_query}")
        raw_ingredients = get_recipe_ingredients(recipe_query)
        
        if not raw_ingredients:
             return jsonify({'success': False, 'error': 'Failed to generate ingredients.'}), 500

        # Phase 2: Match generic ingredients against actual store products in MongoDB
        print(f"Matching {len(raw_ingredients)} ingredients to products...")
        matched_results = match_ingredients_to_products(raw_ingredients)
        
        # Calculate total price for matched results
        total_price = sum(item['matched_product']['price_val'] for item in matched_results if item.get('matched_product'))

        return jsonify({
            'success': True,
            'recipe': recipe_query,
            'results': matched_results, # List of dicts: {'original': ..., 'cleaned': ..., 'matched_product': ...}
            'total_items': len(matched_results),
            'matched_items': len([i for i in matched_results if i.get('matched_product')]),
            'total_price': total_price
        })

    except Exception as e:
        print(f"Error generating recipe plan: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
