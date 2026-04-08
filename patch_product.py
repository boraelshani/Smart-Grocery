import re

with open("routes/ui/product.py", "r") as f:
    text = f.read()

replacement = """    # Favorites mark
    user_email = session.get('user')
    fav_ids = set()
    if user_email:
        try:
            from models.favorites_model import favorites_model
            user_favs = favorites_model.get_user_favorites(user_email)
            fav_ids = {str(f.get('product_id')) for f in user_favs}
        except: pass
    
    for p in products:
        p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids
        
    featured_deals = []
    if not search_query and not category_filter:
        try:
            from models.featured_deals_model import featured_deals_model
            from models.multibuy_offers_model import multibuy_offers_model
            base_deals = featured_deals_model.list_featured_deals() or []
            base_deals += multibuy_offers_model.list_active_offers() or []
            import random
            random.shuffle(base_deals)
            featured_deals = base_deals[:12]
        except Exception as e:
            pass

    category_options = [{"name": cat} for cat in ["Produce", "Pantry", "Dairy", "Meat", "Frozen", "Bakery", "Baby food", "Snacks", "Fast Food & To Go", "Household", "Beverages"]]
    
    return render_template('compare_prices.html',
                         products=helpers.sanitize_mongo_doc(products),
                         featured_deals=helpers.sanitize_mongo_doc(featured_deals),
                         page=page,"""

text = re.sub(r"    # Favorites mark.*?page=page,", replacement, text, flags=re.DOTALL)

with open("routes/ui/product.py", "w") as f:
    f.write(text)
