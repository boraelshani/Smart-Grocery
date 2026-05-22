from flask import render_template, session, request, current_app, url_for, redirect
from .. import main_bp
from models.products_model import products_model
from models.deals_compat import list_active_promotions, get_promotion_by_id
from models.multibuy_offers_model import multibuy_offers_model
from models.quantity_discounts_model import quantity_discounts_model
from models.favorites_model import favorites_model
from models.notifications_model import notifications_model
from utils.menu_data import get_mega_menu
from utils import helpers
import math

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
    per_page = 32
    page = int(request.args.get('page', 1))
    category_filter = (request.args.get('category') or '').strip()
    search_query = (request.args.get('search') or '').strip()
    store_filters = {s.strip().lower() for s in (request.args.get('store') or '').split(',') if s.strip()}
    brand_filters = {b.strip().lower() for b in (request.args.get('brand') or '').split(',') if b.strip()}
    user_email = session.get('user')

    def _parse_price(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _deal_price(deal):
        price = _parse_price(deal.get('price'))
        if price is not None:
            return price
        return _parse_price(deal.get('original_price'))
    
    using_fallback = False
    try:
        deals = list_active_promotions() + \
                multibuy_offers_model.list_active_offers() + \
                quantity_discounts_model.list_active_discounts()
    except Exception as e:
        print(f'Error loading deals: {e}')
        using_fallback = True
        deals = load_featured_deals_fallback()

    price_values_all = [_parse_price(d.get('price')) or _parse_price(d.get('original_price')) for d in deals]
    price_values_all = [p for p in price_values_all if p is not None]
    price_max_limit = int(math.ceil(max(price_values_all))) if price_values_all else 0

    if category_filter:
        deals = [d for d in deals if category_filter.lower() in (d.get('category') or '').lower()]
    if search_query:
        sq = search_query.lower()
        deals = [d for d in deals if sq in (d.get('title') or d.get('name') or '').lower() or 
                sq in (d.get('store') or '').lower()]

    if store_filters:
        deals = [d for d in deals if any(
            str(v).strip().lower() in store_filters
            for v in [d.get('store'), d.get('source'), d.get('store_name')]
            if v
        )]

    if brand_filters:
        deals = [d for d in deals if any(
            str(v).strip().lower() in brand_filters
            for v in [d.get('brand'), d.get('brand_name'), d.get('brandName')]
            if v
        )]

    min_price = _parse_price(request.args.get('min_price'))
    max_price = _parse_price(request.args.get('max_price'))
    if min_price is not None or max_price is not None:
        filtered = []
        for deal in deals:
            price = _deal_price(deal)
            if price is None:
                continue
            if min_price is not None and price < min_price:
                continue
            if max_price is not None and price > max_price:
                continue
            filtered.append(deal)
        deals = filtered

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
    
    category_options = helpers.get_category_options()
    brand_options = get_mega_menu().get('brands', [])

    # Calculate breadcrumb path and visual categories based on the full tree
    breadcrumb_path = []
    visual_categories = category_options  # Default to roots
    
    if category_filter:
        cf_lower = category_filter.lower()
        found_in_tree = False
        
        for l1 in category_options:
            if l1.get('name', '').lower() == cf_lower:
                breadcrumb_path = [l1]
                if l1.get('subcategories'):
                    visual_categories = l1['subcategories']
                else:
                    visual_categories = category_options
                found_in_tree = True
                break
                
            for l2 in l1.get('subcategories', []):
                if l2.get('name', '').lower() == cf_lower:
                    breadcrumb_path = [l1, l2]
                    if l2.get('subcategories'):
                        visual_categories = l2['subcategories']
                    else:
                        visual_categories = l1['subcategories']
                    found_in_tree = True
                    break
                    
                for l3 in l2.get('subcategories', []):
                    if l3.get('name', '').lower() == cf_lower:
                        breadcrumb_path = [l1, l2, l3]
                        # l3 usually has no subcategories in our depth-3 tree
                        visual_categories = l2['subcategories']
                        found_in_tree = True
                        break
                if found_in_tree: break
            if found_in_tree: break

    if category_filter:
        if not any(category_filter.lower() == c['name'].lower() for c in category_options):
            category_options.append({"name": category_filter.title()})
            
    return render_template('featured_deals.html', 
                          deals=helpers.sanitize_mongo_doc(paginated_deals), 
                          total_products=total_products,
                          total_pages=total_pages,
                          page=page,
                          current_page=page,
                          price_max_limit=price_max_limit,
                          category_filter=category_filter,
                          category_options=category_options,
                          brand_options=brand_options,
                          breadcrumb_path=breadcrumb_path,
                          visual_categories=visual_categories,
                          search_query=search_query,
                          using_fallback=using_fallback)

