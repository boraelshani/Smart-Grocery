"""
ORM MODELS — Maps the actual Neon PostgreSQL schema to Python objects.
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

def _now():
    return datetime.now(timezone.utc)

# ── STORES ──────────────────────────────────────────────────
class Store(db.Model):
    __tablename__ = 'stores'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Text, unique=True, index=True)
    name = db.Column(db.Text)
    website = db.Column(db.Text)
    logo_url = db.Column(db.Text)
    country = db.Column(db.Text, default='AT')
    api_available = db.Column(db.Boolean, default=False)
    scraping_required = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {'id': self.store_id, 'storeId': self.store_id, 'name': self.name,
                'image': self.logo_url, 'logoUrl': self.logo_url, 'url': self.website,
                'website': self.website, 'country': self.country}

# ── CATEGORIES ──────────────────────────────────────────────
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

    def to_dict(self):
        return {'categoryId': str(self.id), 'name_en': self.name_en, 'name_de': self.name_de,
                'slug': self.slug, 'imageUrl': self.image_url, 'parentId': self.parent_id,
                'icon': self.icon, 'level': self.level}

# ── PRODUCTS ────────────────────────────────────────────────
class Product(db.Model):
    __tablename__ = 'products'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    fingerprint = db.Column(db.Text, unique=True, index=True)
    name_de = db.Column(db.Text)
    brand = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    unit_normalized = db.Column(db.Text)
    size_normalized = db.Column(db.Numeric)
    default_image_url = db.Column(db.Text)
    barcode = db.Column(db.Text)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    offers = db.relationship('Offer', backref='product', lazy='dynamic')

    def to_dict(self):
        return {'productId': str(self.id), 'id': str(self.id), '_id': str(self.id),
                'fingerprint': self.fingerprint,
                'name': self.name_de, 'name_en': self.name_de, 'name_de': self.name_de,
                'brand': self.brand, 'brandId': self.brand,
                'categoryId': str(self.category_id) if self.category_id else None,
                'unitSize': self.unit_normalized, 'barcode': self.barcode,
                'defaultImageUrl': self.default_image_url, 'image': self.default_image_url,
                'createdAt': self.created_at, 'updatedAt': self.updated_at}

# ── OFFERS ──────────────────────────────────────────────────
class Offer(db.Model):
    __tablename__ = 'offers'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    store_id = db.Column(db.Text, index=True)
    price = db.Column(db.Numeric(10, 2))
    product_url = db.Column(db.Text)
    is_available = db.Column(db.Boolean, default=True)
    last_seen = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    def effective_price(self):
        return float(self.price) if self.price is not None else None

    def to_dict(self):
        return {'storeProductId': str(self.id), 'productId': str(self.product_id),
                'storeId': self.store_id, 'productPageUrl': self.product_url,
                'basePrice': float(self.price) if self.price else None,
                'price': float(self.price) if self.price else None,
                'isAvailable': self.is_available}

# ── PRICE HISTORY ───────────────────────────────────────────
class PriceHistory(db.Model):
    __tablename__ = 'price_history'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    offer_id = db.Column(db.Integer, db.ForeignKey('offers.id'))
    old_price = db.Column(db.Numeric)
    new_price = db.Column(db.Numeric)
    changed_at = db.Column(db.DateTime)
    source = db.Column(db.Text)

# ── FEATURED DEALS ──────────────────────────────────────────
class FeaturedDeal(db.Model):
    __tablename__ = 'featured_deals'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric)
    original_price = db.Column(db.Numeric)
    discount_percent = db.Column(db.Integer)
    store_id = db.Column(db.Text)
    image_url = db.Column(db.Text)
    url = db.Column(db.Text)
    category_slug = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    valid_until = db.Column(db.Date)

    def to_dict(self):
        return {'id': str(self.id), '_id': str(self.id),
                'title': self.title, 'name': self.title,
                'store': self.store_id, 'storeName': self.store_id,
                'price': float(self.price) if self.price else None,
                'priceText': str(self.price) if self.price else None,
                'original_price': float(self.original_price) if self.original_price else None,
                'image': self.image_url, 'category': self.category_slug,
                'discount_percent': self.discount_percent,
                'discount_label': f"{self.discount_percent}% OFF" if self.discount_percent else None,
                'description': self.description, 'source': self.store_id,
                'valid_until': str(self.valid_until) if self.valid_until else None,
                'status': 'active' if self.active else 'inactive',
                'active': bool(self.active), 'product_name': self.title}

# ── USERS ───────────────────────────────────────────────────
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
    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {'id': str(self.id), 'userId': self.user_id or str(self.id),
                'email': self.email, 'name': self.name, 'avatar': self.avatar,
                'password': self.password_hash, 'is_admin': False,
                'preferred_stores': [], 'preferred_categories': [],
                'active_list_id': None, 'seen_deals': [],
                'read_dynamic_notifications': [], 'total_cost': 0.0}

# ── SHOPPING LISTS ──────────────────────────────────────────
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

    items = db.relationship('ListItem', backref='shopping_list', lazy='dynamic',
                            cascade='all, delete-orphan')

    def to_dict(self):
        items_list = [item.to_dict() for item in self.items.all()]
        return {'id': self.list_id, 'listId': self.list_id, 'userId': str(self.user_id),
                'name': self.name or 'My List', 'items': items_list,
                'totalPrice': sum(float(i.get('price', 0) or 0) * int(i.get('qty', 1) or 1) for i in items_list),
                'shared': bool(self.shared), 'shareCode': self.share_code,
                'collaborators': [], 'created_at': self.created_at,
                'updated_at': self.updated_at}

# ── LIST ITEMS ──────────────────────────────────────────────
class ListItem(db.Model):
    __tablename__ = 'list_items'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('shopping_lists.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer)
    product_name = db.Column(db.Text)
    quantity = db.Column(db.Numeric, default=1)
    checked = db.Column(db.Boolean, default=False)
    added_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {'name': self.product_name, 'productId': str(self.product_id) if self.product_id else None,
                'qty': int(self.quantity or 1), 'quantity': int(self.quantity or 1),
                'price': 0, 'price_val': 0, 'unitPrice': 0, 'lineTotal': 0,
                'purchased': bool(self.checked), 'checked': bool(self.checked),
                'is_new': False, 'image': None}

# ── NOTIFICATIONS ───────────────────────────────────────────
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
        return {'id': str(self.id), '_id': str(self.id), 'user_email': self.user_email,
                'type': self.type, 'title': self.title, 'message': self.message,
                'action_url': self.action_url, 'priority': self.priority,
                'read': self.read, 'product_id': self.product_id,
                'deal_id': self.deal_id, 'store_name': self.store_name,
                'is_toasted': self.is_toasted, 'created_at': self.created_at}

# ── FAVORITES ───────────────────────────────────────────────
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
    added_at = db.Column(db.DateTime, default=_now)

    def to_dict(self):
        return {'id': str(self.id), 'user_email': self.user_email,
                'product_id': self.product_id, 'product_name': self.product_name,
                'product_image': self.product_image, 'category': self.category,
                'best_price': float(self.best_price) if self.best_price else None,
                'store': self.store, 'added_at': self.added_at}

# ── FEEDBACK / PRICE FEEDBACK ──────────────────────────────
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

# ── SAVED RECIPES ───────────────────────────────────────────
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

# ── COMMUNITY PRICE REPORTS ─────────────────────────────────
class CommunityPriceReport(db.Model):
    __tablename__ = 'community_price_reports'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Text)
    store_name = db.Column(db.Text)
    observed_price = db.Column(db.Numeric)
    created_at = db.Column(db.DateTime, default=_now)

# ── PENDING PRODUCTS ────────────────────────────────────────
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

# ── PUBLIC LISTS ────────────────────────────────────────────
class PublicList(db.Model):
    __tablename__ = 'public_lists'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Text, unique=True)
    name = db.Column(db.Text)
    items = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=_now)

# ── BRANDS ──────────────────────────────────────────────────
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
