from flask import render_template, session, request, redirect, url_for
from .. import main_bp
from models.products_model import products_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.quantity_discounts_model import quantity_discounts_model
from models.favorites_model import favorites_model
from models.stores_model import stores_model
from comparison.comparison_engine import build_compare_product_payload, build_best_price_summary
from comparison.store_matcher import build_store_meta_map
from utils import helpers

def attach_deals_to_product(product_doc):
    """Find deals matching the product and inject them into the stores array."""
    if not isinstance(product_doc, dict): return
    store_list = product_doc.get('stores', [])
    if not store_list:
        # If it's a stand-alone deal/offer, wrap it in a store array so it looks like a product
        store_name = product_doc.get('store') or product_doc.get('source')
        if store_name:
            store_entry = {
                'store': store_name,
                'price': product_doc.get('price'),
                'has_deal': True,
                'deal_info': None
            }
            if product_doc.get('original_price'): store_entry['original_price'] = product_doc['original_price']
            if product_doc.get('discount_label'): store_entry['discount_label'] = product_doc['discount_label']
            if product_doc.get('valid_until'): store_entry['valid_until'] = product_doc['valid_until']
            product_doc['stores'] = [store_entry]
        return

    name = product_doc.get('name') or product_doc.get('title')
    if not name: return
    
    try:
        from models.featured_deals_model import featured_deals_model
        # Simple exact name or regex match for deals
        deal = featured_deals_model.collection.find_one({"$or": [{"title": name}, {"name": name}]})
        if not deal:
            # try case-insensitive regex
            deal = featured_deals_model.collection.find_one({"$or": [{"title": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}, {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}]})
        
        if deal:
            deal_store = (deal.get('store') or deal.get('source') or '').lower()
            for s in store_list:
                s_name = (s.get('store') or s.get('name') or '').lower()
                if deal_store and s_name == deal_store:
                    s['has_deal'] = True
                    s['deal_info'] = deal
                    if deal.get('price'): s['price'] = deal['price']
                    if deal.get('original_price'): s['original_price'] = deal['original_price']
                    if deal.get('discount_label'): s['discount_label'] = deal['discount_label']
                    if deal.get('valid_until'): s['valid_until'] = deal['valid_until']
    except Exception as e:
        print("Error attaching deals:", e)

@main_bp.route('/product-info/<product_id>')
@main_bp.route('/product/<product_id>')
@main_bp.route('/featured-deal/<product_id>')
def product_detail(product_id):
    """Detailed product comparison page."""
    product = products_model.get_product_by_id(product_id)
    is_deal_direct = False
    
    if not product:
        # Check deals
        deal = featured_deals_model.get_deal_by_id(product_id) or                multibuy_offers_model.get_offer_by_id(product_id) or                quantity_discounts_model.get_discount_by_id(product_id)
        if deal:
            # attempt to find master product by name
            name = deal.get('title') or deal.get('name')
            if name:
                matches = products_model.search_by_name(name, limit=1)
                if matches:
                    product = matches[0]
            if not product:
                product = deal
                is_deal_direct = True
    
    if not product:
        return render_template('404.html'), 404
        
    attach_deals_to_product(product)

    
    is_favorited = False
    user_email = session.get('user')
    if user_email:
        try:
            is_favorited = favorites_model.is_favorited(user_email, str(product.get('id') or product.get('_id', '')))
        except: pass
    
    # Build comparison payload
    store_meta = build_store_meta_map(stores_model.list_stores())
    payload = build_compare_product_payload(helpers.sanitize_mongo_doc(product), store_meta_map=store_meta)
    best_price_value, best_price_stores = build_best_price_summary(payload)
    
    return render_template('product_detail.html', 
                         product=payload, 
                         best_price_value=best_price_value,
                         best_price_stores=best_price_stores,
                         is_favorited=is_favorited)

@main_bp.route('/compare')
@main_bp.route('/compare-prices')
def compare_prices():
    """Price Comparison Engine - Search and Categories."""
    per_page = 30
    page = int(request.args.get('page', 1))
    category_filter = (request.args.get('category') or '').strip()
    search_query = (request.args.get('search') or '').strip()
    sort_filter = (request.args.get('sort') or 'default').strip()

    import re
    query = {'is_placeholder': {'$ne': True}}
    and_clauses = []
    
    if category_filter:
        and_clauses.append({
            '$or': [
                {'category': {'$regex': f"^{re.escape(category_filter)}$", '$options': 'i'}},
                {'category_path': {'$elemMatch': {'$regex': f"^{re.escape(category_filter)}$", '$options': 'i'}}}
            ]
        })
    
    if search_query:
        search_regex = {'$regex': re.escape(search_query), '$options': 'i'}
        and_clauses.append({
            '$or': [{'name': search_regex}, {'title': search_regex}, {'category': search_regex}, {'brand': search_regex}]
        })
        
    if and_clauses:
        query['$and'] = and_clauses

    sort_config = None
    if sort_filter == 'price_asc':
        sort_config = [('price', 1)]
    elif sort_filter == 'price_desc':
        sort_config = [('price', -1)]
    elif sort_filter == 'name_asc':
        sort_config = [('name', 1)]
    elif sort_filter == 'name_desc':
        sort_config = [('name', -1)]

    total_products = products_model.count_products(query)
    total_pages = (total_products + per_page - 1) // per_page if total_products else 1
    page = max(1, min(page, total_pages))
    
    products = products_model.list_products(query=query, skip=(page - 1) * per_page, limit=per_page, sort=sort_config)

    
    # Favorites mark
    user_email = session.get('user')
    fav_ids = set()
    if user_email:
        try:
            user_favs = favorites_model.get_user_favorites(user_email)
            fav_ids = {str(f.get('product_id')) for f in user_favs}
        except: pass
    
    for p in products:
        p['is_favorited'] = str(p.get('id') or p.get('_id', '')) in fav_ids

    category_options = helpers.get_category_options()

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
            
        # Add the selected subcategory to the chips dynamically so it shows as active/selected if not found
        if not found_in_tree:
            pass # Keep it simple, breadcrumb empty path

    return render_template('compare_prices.html',
                         products=helpers.sanitize_mongo_doc(products),
                         page=page,
                         total_pages=total_pages,
                         total_products=total_products,
                         category_filter=category_filter,
                         search_query=search_query,
                         sort_filter=sort_filter,
                         category_options=category_options,
                         breadcrumb_path=breadcrumb_path,
                         visual_categories=visual_categories)
