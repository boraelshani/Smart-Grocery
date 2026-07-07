from flask import render_template, session, request, redirect, url_for, jsonify
from .. import main_bp
from models.products_model import products_model
from models.featured_deals_model import featured_deals_model
from models.multibuy_offers_model import multibuy_offers_model
from models.quantity_discounts_model import quantity_discounts_model
from models.favorites_model import favorites_model
from models.stores_model import stores_model
from models.postgres_models import db, Product, ProductStore, Category, PriceAlert, PriceFeedback, Notification
from comparison.comparison_engine import build_compare_product_payload, build_best_price_summary
from comparison.store_matcher import build_store_meta_map
from utils.menu_data import get_mega_menu
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
    
    # Featured deals table removed - promotions are now handled via deals_compat layer
    # This enrichment is no longer needed as promotions are queried separately
    # Products will show promotional pricing through the product_store and promotion_targets tables

@main_bp.route('/product-info/<product_id>')
@main_bp.route('/product/<product_id>')
@main_bp.route('/featured-deal/<product_id>')
def product_detail(product_id):
    """Detailed product comparison page."""
    product = products_model.get_product_by_id(product_id)
    price_history = products_model.get_price_history(product_id, limit=8)
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
    
    # Convert best_price_value from string to float for template calculations
    if best_price_value is not None:
        try:
            best_price_value = float(best_price_value)
        except (ValueError, TypeError):
            best_price_value = None
    
    # Similar products (same category, different product)
    similar_products = []
    raw_cat_id = product.get('category_id') or product.get('categoryId')
    try:
        cat_id = int(raw_cat_id) if raw_cat_id else None
    except (ValueError, TypeError):
        cat_id = None

    if cat_id:
        try:
            sim_rows = (Product.query
                        .filter(Product.category_id == cat_id, Product.id != int(product.get('id', 0)))
                        .limit(12).all())
            similar_products = products_model._hydrate_products_bulk(sim_rows)[:6]
        except Exception:
            pass

    # Category breadcrumb path
    category_path = []
    if cat_id:
        try:
            cat = db.session.get(Category, cat_id)
            while cat:
                category_path.insert(0, {'name': cat.name_en or cat.name_de, 'slug': cat.slug or ''})
                cat = db.session.get(Category, cat.parent_id) if cat.parent_id else None
        except Exception:
            pass

    # Existing price alert for this user+product
    existing_alert = None
    pid_int = int(product.get('id', 0)) if product.get('id') else None
    if user_email and pid_int:
        try:
            existing_alert = PriceAlert.query.filter_by(
                user_email=user_email, product_id=pid_int, is_active=True
            ).first()
        except Exception:
            pass

    return render_template('product_detail.html',
                         product=payload,
                         best_price_value=best_price_value,
                         best_price_stores=best_price_stores,
                         is_favorited=is_favorited,
                         price_history=price_history,
                         similar_products=similar_products,
                         category_path=category_path,
                         existing_alert=existing_alert)

@main_bp.route('/api/price-alert/set', methods=['POST'])
def set_price_alert():
    user_email = session.get('user')
    if not user_email:
        return jsonify({'error': 'Login required'}), 401
    data = request.get_json() or {}
    try:
        product_id = int(data.get('product_id', 0))
        target_price = float(data.get('target_price', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid data'}), 400
    if not product_id or target_price <= 0:
        return jsonify({'error': 'Invalid product or price'}), 400
    # Upsert: deactivate old alert, create new one
    PriceAlert.query.filter_by(user_email=user_email, product_id=product_id, is_active=True).update({'is_active': False})
    alert = PriceAlert(user_email=user_email, product_id=product_id, target_price=target_price)
    db.session.add(alert)
    db.session.commit()
    return jsonify({'ok': True, 'target_price': float(alert.target_price)})


@main_bp.route('/api/price-alert/delete', methods=['POST'])
def delete_price_alert():
    user_email = session.get('user')
    if not user_email:
        return jsonify({'error': 'Login required'}), 401
    data = request.get_json() or {}
    try:
        product_id = int(data.get('product_id', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid data'}), 400
    PriceAlert.query.filter_by(user_email=user_email, product_id=product_id, is_active=True).update({'is_active': False})
    db.session.commit()
    return jsonify({'ok': True})


@main_bp.route('/api/report-price', methods=['POST'])
def report_price():
    user_email = session.get('user')
    data = request.get_json() or {}
    try:
        fb = PriceFeedback(
            product_id=str(data.get('product_id', '')),
            store=data.get('store', ''),
            user_email=user_email or 'anonymous',
            is_correct=False,
            reported_price=data.get('reported_price') or None,
        )
        db.session.add(fb)
        db.session.commit()
    except Exception:
        db.session.rollback()
    return jsonify({'ok': True})


@main_bp.route('/compare')
@main_bp.route('/compare-prices')
def compare_prices():
    """Price Comparison Engine - Search and Categories."""
    per_page = 32
    page = int(request.args.get('page', 1))
    category_filter = (request.args.get('category') or '').strip()
    search_query = (request.args.get('search') or '').strip()
    sort_filter = (request.args.get('sort') or 'default').strip()
    store_filters = {s.strip().lower() for s in (request.args.get('store') or '').split(',') if s.strip()}
    brand_filters = {b.strip().lower() for b in (request.args.get('brand') or '').split(',') if b.strip()}

    def _parse_price(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    import re
    query = {'is_placeholder': {'$ne': True}}
    and_clauses = []
    
    if category_filter:
        and_clauses.append({
            '$or': [
                {'category': {'$regex': f"^{re.escape(category_filter)}$", '$options': 'i'}},
                {'category_path': {'$regex': f"^{re.escape(category_filter)}$", '$options': 'i'}}
            ]
        })
    
    if search_query:
        search_regex = {'$regex': re.escape(search_query), '$options': 'i'}
        and_clauses.append({
            '$or': [{'name': search_regex}, {'title': search_regex}, {'category': search_regex}, {'brand': search_regex}]
        })
        
    if and_clauses:
        query['$and'] = and_clauses

    total_products = products_model.count_products(query)
    raw_products = products_model.list_products(query=query, skip=0, limit=total_products) if total_products else []

    min_price = _parse_price(request.args.get('min_price'))
    max_price = _parse_price(request.args.get('max_price'))

    def _matches_store(product):
        if not store_filters:
            return True
        values = {str(product.get('store') or '').strip().lower()}
        for store in product.get('stores') or []:
            store_name = str(store.get('store') or store.get('name') or '').strip().lower()
            if store_name:
                values.add(store_name)
        return bool(values & store_filters)

    def _matches_brand(product):
        if not brand_filters:
            return True
        brand_value = str(product.get('brand') or product.get('brandId') or '').strip().lower()
        if not brand_value:
            return False
        return any(brand_value == brand or brand in brand_value or brand_value in brand for brand in brand_filters)

    def _matches_price(product):
        if min_price is None and max_price is None:
            return True
        price = _parse_price(product.get('price') or (product.get('cheapest') or {}).get('price'))
        if price is None:
            return False
        if min_price is not None and price < min_price:
            return False
        if max_price is not None and price > max_price:
            return False
        return True

    products = [p for p in raw_products if _matches_store(p) and _matches_brand(p) and _matches_price(p)]

    if sort_filter == 'price_asc':
        products.sort(key=lambda x: _parse_price(x.get('price')) if _parse_price(x.get('price')) is not None else float('inf'))
    elif sort_filter == 'price_desc':
        products.sort(key=lambda x: _parse_price(x.get('price')) if _parse_price(x.get('price')) is not None else float('-inf'), reverse=True)
    elif sort_filter == 'name_asc':
        products.sort(key=lambda x: str(x.get('name') or x.get('title') or '').lower())
    elif sort_filter == 'name_desc':
        products.sort(key=lambda x: str(x.get('name') or x.get('title') or '').lower(), reverse=True)

    total_products = len(products)
    total_pages = (total_products + per_page - 1) // per_page if total_products else 1
    page = max(1, min(page, total_pages))
    products = products[(page - 1) * per_page: page * per_page]

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

    price_max_limit = products_model.get_max_product_price_ceiling()

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
            
        # Add the selected subcategory to the chips dynamically so it shows as active/selected if not found
        if not found_in_tree:
            pass # Keep it simple, breadcrumb empty path

    return render_template('compare_prices.html',
                         products=helpers.sanitize_mongo_doc(products),
                         page=page,
                         total_pages=total_pages,
                         total_products=total_products,
                         price_max_limit=price_max_limit,
                         category_filter=category_filter,
                         search_query=search_query,
                         sort_filter=sort_filter,
                         category_options=category_options,
                         brand_options=brand_options,
                         breadcrumb_path=breadcrumb_path,
                         visual_categories=visual_categories)
