"""
NEW ORM MODELS — Normalized schema for Smart Grocery
Maps the restructured PostgreSQL schema to Python objects.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

def _now():
    return datetime.now(timezone.utc)

# ══════════════════════════════════════════════════════════════════════════════
# STORES
# ══════════════════════════════════════════════════════════════════════════════

class Store(db.Model):
    __tablename__ = 'stores'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Text, unique=True, index=True, nullable=False)
    name = db.Column(db.Text, nullable=False)
    website = db.Column(db.Text)
    logo_url = db.Column(db.Text)
    country = db.Column(db.Text, default='AT')
    api_available = db.Column(db.Boolean, default=False)
    scraping_required = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=True)
    
    # Relationships
    product_stores = db.relationship('ProductStore', backref='store', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.store_id,
            'storeId': self.store_id,
            'name': self.name,
            'image': self.logo_url,
            'logoUrl': self.logo_url,
            'url': self.website,
            'website': self.website,
            'country': self.country,
            'active': self.active
        }

# ══════════════════════════════════════════════════════════════════════════════
# CATEGORIES
# ══════════════════════════════════════════════════════════════════════════════

class Category(db.Model):
    __tablename__ = 'categories'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.Text)
    name_en = db.Column(db.Text)
    name_de = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    level = db.Column(db.Integer)
    icon = db.Column(db.Text)
    image_url = db.Column(db.Text)
    
    # Relationships
    products = db.relationship('Product', backref='category', lazy='dynamic')

    def to_dict(self):
        return {
            'categoryId': str(self.id),
            'name_en': self.name_en,
            'name_de': self.name_de,
            'slug': self.slug,
            'imageUrl': self.image_url,
            'parentId': self.parent_id,
            'icon': self.icon,
            'level': self.level
        }

# ══════════════════════════════════════════════════════════════════════════════
# PRODUCTS - Global product catalog (store-independent)
# ══════════════════════════════════════════════════════════════════════════════

class Product(db.Model):
    __tablename__ = 'products'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    fingerprint = db.Column(db.Text, unique=True, index=True)
    name = db.Column(db.Text, nullable=False)  # Global product name
    name_de = db.Column(db.Text)  # German name (for compatibility)
    brand = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    unit_normalized = db.Column(db.Text)  # kg, l, ml, etc.
    size_normalized = db.Column(db.Numeric)  # Amount
    default_image_url = db.Column(db.Text)
    barcode = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now)
    
    # Relationships
    product_stores = db.relationship('ProductStore', backref='product', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'productId': str(self.id),
            'id': str(self.id),
            '_id': str(self.id),
            'fingerprint': self.fingerprint,
            'name': self.name,
            'name_en': self.name,
            'name_de': self.name_de or self.name,
            'brand': self.brand,
            'brandId': self.brand,
            'categoryId': str(self.category_id) if self.category_id else None,
            'unitSize': self.unit_normalized,
            'sizeNormalized': float(self.size_normalized) if self.size_normalized else None,
            'barcode': self.barcode,
            'defaultImageUrl': self.default_image_url,
            'image': self.default_image_url,
            'createdAt': self.created_at,
            'updatedAt': self.updated_at
        }
    
    def get_stores(self):
        """Get all stores selling this product"""
        return [ps.store for ps in self.product_stores]
    
    def get_price_at_store(self, store_id):
        """Get price at a specific store"""
        ps = self.product_stores.filter_by(store_id=store_id).first()
        return ps.base_price if ps else None

# ══════════════════════════════════════════════════════════════════════════════
# PRODUCT_STORE - Store-specific product data (pricing, availability)
# ══════════════════════════════════════════════════════════════════════════════

class ProductStore(db.Model):
    __tablename__ = 'product_store'
    __table_args__ = {'extend_existing': True}
    
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), primary_key=True)
    store_id = db.Column(db.Text, db.ForeignKey('stores.store_id', ondelete='CASCADE'), primary_key=True)
    base_price = db.Column(db.Numeric(10, 2), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    product_url = db.Column(db.Text)
    last_seen = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_now)
    
    # Relationships
    promotion_targets = db.relationship('PromotionTarget', backref='product_store', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'productId': str(self.product_id),
            'storeId': self.store_id,
            'basePrice': float(self.base_price) if self.base_price else None,
            'isAvailable': self.is_available,
            'productUrl': self.product_url,
            'lastSeen': self.last_seen,
            'createdAt': self.created_at,
            'updatedAt': self.updated_at
        }
    
    def get_final_price(self):
        """Calculate final price with active promotions"""
        # Get active promotions for this product-store
        active_promotions = self.promotion_targets.join(Promotion).filter(
            Promotion.is_active == True,
            Promotion.start_date <= datetime.now(timezone.utc).date(),
            db.or_(
                Promotion.end_date == None,
                Promotion.end_date >= datetime.now(timezone.utc).date()
            )
        ).all()
        
        if not active_promotions:
            return float(self.base_price)
        
        # Apply best discount
        best_price = float(self.base_price)
        for pt in active_promotions:
            if pt.promotion.offer:
                discounted_price = pt.promotion.offer.apply_discount(float(self.base_price))
                best_price = min(best_price, discounted_price)
        
        return best_price

# ══════════════════════════════════════════════════════════════════════════════
# OFFERS - Reusable discount rules
# ══════════════════════════════════════════════════════════════════════════════

class Offer(db.Model):
    __tablename__ = 'offers'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    discount_type = db.Column(db.Text, nullable=False)
    discount_value = db.Column(db.Numeric(10, 2), nullable=False)
    min_quantity = db.Column(db.Integer, default=1)
    max_quantity = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'discountType': self.discount_type,
            'discountValue': float(self.discount_value) if self.discount_value else None,
            'isActive': self.is_active,
            'createdAt': self.created_at,
        }

# ══════════════════════════════════════════════════════════════════════════════
# PROMOTIONS - Time-bound campaigns
# ══════════════════════════════════════════════════════════════════════════════

class Promotion(db.Model):
    __tablename__ = 'promotions'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    offer_id = db.Column(db.Integer, db.ForeignKey('offers.id', ondelete='SET NULL'))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_now)
    
    # Relationships
    targets = db.relationship('PromotionTarget', backref='promotion', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'promotionId': str(self.id),
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'offerId': str(self.offer_id) if self.offer_id else None,
            'startDate': str(self.start_date) if self.start_date else None,
            'endDate': str(self.end_date) if self.end_date else None,
            'isActive': self.is_active,
            'createdAt': self.created_at,
            'updatedAt': self.updated_at
        }
    
    def is_currently_active(self):
        """Check if promotion is active right now"""
        if not self.is_active:
            return False
        
        today = datetime.now(timezone.utc).date()
        
        if self.start_date and today < self.start_date:
            return False
        
        if self.end_date and today > self.end_date:
            return False
        
        return True

# ══════════════════════════════════════════════════════════════════════════════
# PROMOTION_TARGETS - Links promotions to specific product-store combinations
# ══════════════════════════════════════════════════════════════════════════════

class PromotionTarget(db.Model):
    __tablename__ = 'promotion_targets'
    __table_args__ = {'extend_existing': True}
    
    promotion_id = db.Column(db.Integer, db.ForeignKey('promotions.id', ondelete='CASCADE'), primary_key=True)
    product_id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Text, primary_key=True)
    created_at = db.Column(db.DateTime, default=_now)
    
    # Composite foreign key to product_store
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['product_id', 'store_id'],
            ['product_store.product_id', 'product_store.store_id'],
            ondelete='CASCADE'
        ),
        {'extend_existing': True}
    )

    def to_dict(self):
        return {
            'promotionId': str(self.promotion_id),
            'productId': str(self.product_id),
            'storeId': self.store_id,
            'createdAt': self.created_at
        }

# ══════════════════════════════════════════════════════════════════════════════
# PRICE HISTORY - Track price changes over time
# ══════════════════════════════════════════════════════════════════════════════

class PriceHistory(db.Model):
    __tablename__ = 'price_history'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer)
    store_id = db.Column(db.Text)
    old_price = db.Column(db.Numeric)
    new_price = db.Column(db.Numeric)
    changed_at = db.Column(db.DateTime, default=_now)
    source = db.Column(db.Text)
    
    # Legacy fields for compatibility
    offer_id = db.Column(db.Integer)
    price = db.Column(db.Numeric)
    recorded_at = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id': str(self.id),
            'productId': str(self.product_id) if self.product_id else None,
            'storeId': self.store_id,
            'oldPrice': float(self.old_price) if self.old_price else None,
            'newPrice': float(self.new_price) if self.new_price else None,
            'price': float(self.new_price or self.price) if (self.new_price or self.price) else None,
            'changedAt': (self.changed_at or self.recorded_at).isoformat() if (self.changed_at or self.recorded_at) else None,
            'source': self.source
        }

# ══════════════════════════════════════════════════════════════════════════════
# USERS, SHOPPING LISTS, AND OTHER TABLES (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Text, unique=True, index=True)
    email = db.Column(db.Text, unique=True, nullable=False, index=True)
    password_hash = db.Column(db.Text)
    name = db.Column(db.Text)
    avatar = db.Column(db.Text)
    language = db.Column(db.Text, default='en')
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            'id': str(self.id),
            'userId': self.user_id or str(self.id),
            'email': self.email,
            'name': self.name,
            'avatar': self.avatar,
            'isAdmin': bool(self.is_admin),
            'createdAt': self.created_at,
            'updatedAt': self.updated_at
        }

class ShoppingList(db.Model):
    __tablename__ = 'shopping_lists'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Text, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.Text, default='My List')
    share_code = db.Column(db.Text)
    shared = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now)
    
    items = db.relationship('ListItem', backref='shopping_list', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        items_list = [item.to_dict() for item in self.items.all()]
        return {
            'id': self.list_id,
            'listId': self.list_id,
            'userId': str(self.user_id),
            'name': self.name or 'My List',
            'items': items_list,
            'totalPrice': sum(float(i.get('price', 0) or 0) * int(i.get('qty', 1) or 1) for i in items_list),
            'shared': bool(self.shared),
            'shareCode': self.share_code,
            'createdAt': self.created_at,
            'updatedAt': self.updated_at
        }

class ListItem(db.Model):
    __tablename__ = 'list_items'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('shopping_lists.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer)
    product_name = db.Column(db.Text)
    quantity = db.Column(db.Numeric, default=1)
    checked = db.Column(db.Boolean, default=False)
    is_new = db.Column(db.Boolean, default=True)
    added_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            'name': self.product_name,
            'productId': str(self.product_id) if self.product_id else None,
            'qty': int(self.quantity or 1),
            'quantity': int(self.quantity or 1),
            'checked': bool(self.checked),
            'addedAt': self.added_at
        }

# Additional models (Notification, Favorite, Feedback, etc.) remain unchanged
# ... (include all other models from original file)

# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER RUNS
# ══════════════════════════════════════════════════════════════════════════════

class ScraperRun(db.Model):
    __tablename__ = 'scraper_runs'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Text)
    products_processed = db.Column(db.Integer, default=0)
    offers_updated = db.Column(db.Integer, default=0)
    errors = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════

class Notification(db.Model):
    __tablename__ = 'notifications'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.Text, index=True)
    type = db.Column(db.Text)
    title = db.Column(db.Text)
    message = db.Column(db.Text)
    action_url = db.Column(db.Text)
    priority = db.Column(db.Text, default='normal')
    read = db.Column(db.Boolean, default=False, index=True)
    product_id = db.Column(db.Text)
    deal_id = db.Column(db.Text)
    store_name = db.Column(db.Text)
    is_toasted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_now, index=True)

    def to_dict(self):
        return {
            'id': str(self.id),
            '_id': str(self.id),
            'user_email': self.user_email,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'action_url': self.action_url,
            'priority': self.priority,
            'read': self.read,
            'product_id': self.product_id,
            'deal_id': self.deal_id,
            'store_name': self.store_name,
            'is_toasted': self.is_toasted,
            'created_at': self.created_at
        }

# ══════════════════════════════════════════════════════════════════════════════
# FAVORITES
# ══════════════════════════════════════════════════════════════════════════════

class Favorite(db.Model):
    __tablename__ = 'favorites'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.Text, index=True)
    product_id = db.Column(db.Text)
    product_name = db.Column(db.Text)
    product_image = db.Column(db.Text)
    category = db.Column(db.Text)
    best_price = db.Column(db.Numeric)
    store = db.Column(db.Text)
    discount_tiers = db.Column(db.JSON)
    offer = db.Column(db.Text)
    added_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {
            'id': str(self.id),
            'user_email': self.user_email,
            'product_id': self.product_id,
            'product_name': self.product_name,
            'product_image': self.product_image,
            'category': self.category,
            'best_price': float(self.best_price) if self.best_price else None,
            'store': self.store,
            'added_at': self.added_at
        }

# ══════════════════════════════════════════════════════════════════════════════
# FEEDBACK
# ══════════════════════════════════════════════════════════════════════════════

class Feedback(db.Model):
    __tablename__ = 'feedback'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    feedback_id = db.Column(db.Text, unique=True)
    user_email = db.Column(db.Text)
    type = db.Column(db.Text)
    subject = db.Column(db.Text)
    message = db.Column(db.Text)
    status = db.Column(db.Text, default='pending')
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now)

class PriceFeedback(db.Model):
    __tablename__ = 'price_feedback'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text)
    store = db.Column(db.Text)
    user_email = db.Column(db.Text)
    is_correct = db.Column(db.Boolean)
    reported_price = db.Column(db.Numeric)
    timestamp = db.Column(db.DateTime, default=_now)

# ══════════════════════════════════════════════════════════════════════════════
# SAVED RECIPES
# ══════════════════════════════════════════════════════════════════════════════

class SavedRecipe(db.Model):
    __tablename__ = 'saved_recipes'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.Text, index=True)
    title = db.Column(db.Text)
    ingredients = db.Column(db.JSON)
    instructions = db.Column(db.JSON)
    total_items = db.Column(db.Integer, default=0)
    matched_items = db.Column(db.Integer, default=0)
    total_price = db.Column(db.Numeric, default=0)
    created_at = db.Column(db.DateTime, default=_now)

# ══════════════════════════════════════════════════════════════════════════════
# COMMUNITY PRICE REPORTS
# ══════════════════════════════════════════════════════════════════════════════

class CommunityPriceReport(db.Model):
    __tablename__ = 'community_price_reports'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    product_id_int = db.Column(db.Integer)
    product_id = db.Column(db.Text)
    store_name = db.Column(db.Text)
    observed_price = db.Column(db.Numeric)
    note = db.Column(db.Text)
    reporter_type = db.Column(db.Text)
    reporter_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=_now)

# ══════════════════════════════════════════════════════════════════════════════
# PENDING PRODUCTS
# ══════════════════════════════════════════════════════════════════════════════

class PendingProduct(db.Model):
    __tablename__ = 'pending_products'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.Text, unique=True, index=True)
    name = db.Column(db.Text)
    image = db.Column(db.Text)
    status = db.Column(db.Text, default='pending')
    submitted_by = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)

# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC LISTS
# ══════════════════════════════════════════════════════════════════════════════

class PublicList(db.Model):
    __tablename__ = 'public_lists'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Text, unique=True)
    name = db.Column(db.Text)
    items = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=_now)

# ══════════════════════════════════════════════════════════════════════════════
# BRANDS
# ══════════════════════════════════════════════════════════════════════════════

class Brand(db.Model):
    __tablename__ = 'brands'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    brand_id = db.Column(db.Text, unique=True)
    name = db.Column(db.Text)
    name_en = db.Column(db.Text)
    name_de = db.Column(db.Text)
    image_url = db.Column(db.Text)
    website = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now)
