from flask import render_template, session, request, current_app, url_for, redirect
from .. import main_bp
from models.products_model import products_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.quantity_discounts_model import quantity_discounts_model
from models.favorites_model import favorites_model
from models.notifications_model import notifications_model
from utils import helpers

# Standard category list
STANDARD_CATEGORIES = [
    "Produce", "Pantry", "Dairy", "Meat", "Frozen",
    "Bakery", "Baby food", "Snacks", "Fast Food & To Go",
    "Household", "Beverages"
]

def _mark_list_metadata(items, fav_ids=None):
    if not items:
        return items
    multibuy_offers_model.attach_offers_to_products(items)
    quantity_discounts_model.attach_discounts_to_products(items)
    if fav_ids is not None:
        for item in items:
            if isinstance(item, dict):
                item_id = str(item.get('id') or item.get('_id', ''))
                item['is_favorited'] = item_id in fav_ids
    return items

def load_featured_deals_fallback():
    import os, json
    try:
        path = os.path.join(current_app.root_path, 'data', 'featured_deals.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

@main_bp.route('/featured-deals')
def featured_deals_page():
    """Deals & Offers Page."""
    per_page = 30
    page = int(request.args.get('page', 1))
    category_filter = (request.args.get('category') or '').strip()
    search_query = (request.args.get('search') or '').strip()
    user_email = session.get('user')
    
    using_fallback = False
    try:
        deals = featured_deals_model.list_featured_deals() + \
                multibuy_offers_model.list_active_offers() + \
                quantity_discounts_model.list_active_discounts()
    except:
        using_fallback = True
        deals = load_featured_deals_fallback()

    if category_filter:
        deals = [d for d in deals if category_filter.lower() in (d.get('category') or '').lower()]
    if search_query:
        sq = search_query.lower()
        deals = [d for d in deals if sq in (d.get('title') or d.get('name') or '').lower() or 
                sq in (d.get('store') or '').lower()]

    fav_ids = set()
    if user_email:
        try:
            user_favs = favorites_model.get_user_favorites(user_email)
            fav_ids = {str(f.get('product_id')) for f in user_favs}
        except: pass
    
    _mark_list_metadata(deals, fav_ids)
    
    # Sort by discount
    def get_discount(d):
        try: return float(d.get('discount_percent', 0))
        except: return 0
    deals.sort(key=get_discount, reverse=True)

    total_products = len(deals)
    total_pages = (total_products + per_page - 1) // per_page if total_products else 1
    page = max(1, min(page, total_pages))
    
    paginated_deals = deals[(page - 1) * per_page: page * per_page]
    
    category_options = [{"name": cat} for cat in STANDARD_CATEGORIES]
    
    return render_template('featured_deals.html', 
                          deals=helpers.sanitize_mongo_doc(paginated_deals), 
                          total_products=total_products,
                          total_pages=total_pages,
                          current_page=page,
                          category_filter=category_filter,
                          category_options=category_options,
                          search_query=search_query,
                          using_fallback=using_fallback)

@main_bp.route('/featured-deal/<deal_id>')
def featured_deal_detail(deal_id):
    """Display a single featured deal."""
    deal = featured_deals_model.get_deal_by_id(deal_id) or \
           multibuy_offers_model.get_offer_by_id(deal_id) or \
           quantity_discounts_model.get_discount_by_id(deal_id)
    
    if not deal:
        fallbacks = load_featured_deals_fallback()
        deal = next((d for d in fallbacks if str(d.get('id')) == str(deal_id)), None)

    if not deal:
        return render_template('404.html'), 404

    # Normalize
    if not deal.get('title'): deal['title'] = deal.get('name') or "Special Offer"
    if deal.get('price') is None: deal['price'] = deal.get('new_price')
    
    is_favorited = False
    user_email = session.get('user')
    if user_email:
        try: is_favorited = favorites_model.is_favorited(user_email, str(deal.get('_id') or deal.get('id')))
        except: pass

    return render_template('featured_deal_detail.html', deal=helpers.sanitize_mongo_doc(deal), is_favorited=is_favorited)
