"""
Compatibility layer for deals/promotions
Provides the same interface as the old featured_deals_model but uses the new normalized schema
"""
from models.postgres_models import db, Product, ProductStore, Promotion, PromotionTarget, Offer, Store
from sqlalchemy import and_, or_
from datetime import datetime, timezone

def list_active_promotions():
    """
    Get all active promotions with their products and pricing
    Returns a list of dicts compatible with the old featured_deals format
    """
    today = datetime.now(timezone.utc).date()
    
    # Query active promotions with their targets
    query = db.session.query(
        Promotion, PromotionTarget, Product, ProductStore, Store, Offer
    ).join(
        PromotionTarget, Promotion.id == PromotionTarget.promotion_id
    ).join(
        Product, PromotionTarget.product_id == Product.id
    ).join(
        ProductStore, and_(
            ProductStore.product_id == PromotionTarget.product_id,
            ProductStore.store_id == PromotionTarget.store_id
        )
    ).join(
        Store, Store.store_id == PromotionTarget.store_id
    ).outerjoin(
        Offer, Promotion.offer_id == Offer.id
    ).filter(
        Promotion.is_active == True,
        Promotion.start_date <= today,
        or_(Promotion.end_date == None, Promotion.end_date >= today)
    )
    
    results = query.all()
    
    deals = []
    for promo, target, product, product_store, store, offer in results:
        base_price = float(product_store.base_price) if product_store.base_price else None
        
        # Calculate discounted price
        discounted_price = base_price
        discount_percent = 0
        
        if offer and base_price:
            if offer.discount_type == 'percentage':
                discount_percent = int(offer.discount_value)
                discounted_price = base_price * (1 - float(offer.discount_value) / 100)
            elif offer.discount_type == 'fixed':
                discounted_price = base_price - float(offer.discount_value)
                if base_price > 0:
                    discount_percent = int((float(offer.discount_value) / base_price) * 100)
        
        # Format as old featured_deals format
        # Use actual product ID so clicking on deal goes to correct product page
        deal = {
            'id': str(product.id),
            '_id': str(product.id),
            'title': product.name or product.name_de,
            'name': product.name or product.name_de,
            'description': promo.description or promo.name,
            'price': discounted_price,
            'priceText': f'€{discounted_price:.2f}' if discounted_price else None,
            'original_price': base_price,
            'discount_percent': discount_percent,
            'discount_label': f'{discount_percent}% OFF' if discount_percent else None,
            'store': store.name,
            'storeName': store.name,
            'store_id': store.store_id,
            'storeId': store.store_id,
            'image': product.default_image_url,
            'category': product.category.name_en if product.category else None,
            'category_slug': product.category.slug if product.category else None,
            'valid_until': str(promo.end_date) if promo.end_date else None,
            'status': 'active',
            'active': True,
            'product_name': product.name or product.name_de,
            'productId': str(product.id),
            'product_id': str(product.id),
            'brand': product.brand,
            'offer_details': promo.name,
            'source': store.store_id
        }
        deals.append(deal)
    
    return deals

def get_promotion_by_id(promo_id):
    """Get a single promotion by ID"""
    # Handle composite IDs like 'promo_1_123' or just product IDs
    product_id = None
    promotion_id = None
    
    if isinstance(promo_id, str) and promo_id.startswith('promo_'):
        parts = promo_id.split('_')
        if len(parts) >= 3:
            promotion_id = int(parts[1])
            product_id = int(parts[2])
    else:
        # If it's just a number, treat it as a product ID
        try:
            product_id = int(promo_id)
        except (ValueError, TypeError):
            return None
    
    today = datetime.now(timezone.utc).date()
    
    # Build query
    query = db.session.query(
        Promotion, PromotionTarget, Product, ProductStore, Store, Offer
    ).join(
        PromotionTarget, Promotion.id == PromotionTarget.promotion_id
    ).join(
        Product, PromotionTarget.product_id == Product.id
    ).join(
        ProductStore, and_(
            ProductStore.product_id == PromotionTarget.product_id,
            ProductStore.store_id == PromotionTarget.store_id
        )
    ).join(
        Store, Store.store_id == PromotionTarget.store_id
    ).outerjoin(
        Offer, Promotion.offer_id == Offer.id
    )
    
    # Filter by both promotion_id and product_id if we have both
    if promotion_id and product_id:
        query = query.filter(
            Promotion.id == promotion_id,
            Product.id == product_id
        )
    elif product_id:
        # Just filter by product_id and get any active promotion for it
        query = query.filter(
            Product.id == product_id,
            Promotion.is_active == True,
            Promotion.start_date <= today,
            or_(Promotion.end_date == None, Promotion.end_date >= today)
        )
    else:
        return None
    
    result = query.first()
    
    if not result:
        return None
    
    promo, target, product, product_store, store, offer = result
    base_price = float(product_store.base_price) if product_store.base_price else None
    
    # Calculate discounted price
    discounted_price = base_price
    discount_percent = 0
    
    if offer and base_price:
        if offer.discount_type == 'percentage':
            discount_percent = int(offer.discount_value)
            discounted_price = base_price * (1 - float(offer.discount_value) / 100)
        elif offer.discount_type == 'fixed':
            discounted_price = base_price - float(offer.discount_value)
            if base_price > 0:
                discount_percent = int((float(offer.discount_value) / base_price) * 100)
    
    return {
        'id': str(product.id),  # Use actual product ID for routing
        '_id': str(product.id),
        'productId': str(product.id),
        'product_id': str(product.id),
        'title': product.name or product.name_de,
        'name': product.name or product.name_de,
        'description': promo.description or promo.name,
        'price': discounted_price,
        'original_price': base_price,
        'discount_percent': discount_percent,
        'store': store.name,
        'store_id': store.store_id,
        'image': product.default_image_url,
        'category': product.category.name_en if product.category else None,
        'valid_until': str(promo.end_date) if promo.end_date else None,
        'active': True,
        'brand': product.brand,
        'offer_details': promo.name
    }
