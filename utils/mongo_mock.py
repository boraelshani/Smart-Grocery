"""
PostgreSQL-backed MongoDB-compatible query interface.

Maps MongoDB-style queries (e.g. db.products.find({"productId": "..."}))
to SQLAlchemy queries against the Neon PostgreSQL schema.
"""
from datetime import datetime, timezone
from sqlalchemy import or_, and_, desc, asc, func
from models.postgres_models import (
    db, Product, Category, Store, Brand, Offer, User,
    ShoppingList, ListItem, Feedback,
    CommunityPriceReport, PriceHistory, PendingProduct,
    PublicList, Favorite, SavedRecipe, PriceFeedback, Notification,
)

# ── Field name mapping: MongoDB name -> SQLAlchemy column name ─────
FIELD_MAP = {
    # Products
    "productId": "fingerprint",
    "name": "name_de",
    "name_en": "name_de",
    "brandId": "brand",
    "categoryId": "category_id",
    "categoryPath": None,
    "unitSize": "unit_normalized",
    "defaultImageUrl": "default_image_url",
    "image_url": "default_image_url",
    "image": "default_image_url",
    "createdAt": "created_at",
    "updatedAt": "updated_at",
    # Categories
    "imageUrl": "image_url",
    "parentId": "parent_id",
    # Stores
    "storeId": "store_id",
    "logoUrl": "logo_url",
    "apiAvailable": "api_available",
    "scrapingRequired": "scraping_required",
    # Brands
    "brand_id": "brand_id",
    # Users
    "userId": "user_id",
    "password": "password_hash",
    # ShoppingLists
    "listId": "list_id",
    # FeaturedDeals
    "category": "category_slug",
    # Offers (store_products)
    "storeProductId": "id",
    "isAvailable": "is_available",
    "basePrice": "price",
    "promoPrice": None,
    "productPageUrl": "product_url",
    "lastPriceUpdate": "last_seen",
    # Favorites (legacy int cols renamed)
    "userId": "user_email",
    # PendingProducts
    # Notifications
    "is_toasted": "is_toasted",
    # PriceHistory
    "price": "new_price",
    "recorded_at": "changed_at",
}


def _map_field(field):
    """Return the SQLAlchemy column name for a MongoDB-style field name."""
    return FIELD_MAP.get(field, field)


def _get_col(model, field):
    """Get the SQLAlchemy column object for a field name on a model."""
    mapped = _map_field(field)
    if mapped is None:
        return None
    return getattr(model, mapped, None)


def _build_regex_filter(col, value):
    """Build an ILIKE filter for a MongoDB $regex condition."""
    if isinstance(value, dict):
        pattern = value.get("$regex", "")
        options = value.get("$options", "")
        if "i" in options:
            return col.ilike(f"%{pattern}%")
        return col.like(f"%{pattern}%")
    return col.ilike(f"%{value}%")


def _build_filter(model, query_dict):
    """Convert a MongoDB-style query dict to SQLAlchemy filters."""
    if not query_dict:
        return []
    filters = []
    for key, value in query_dict.items():
        if key == "$or":
            or_clauses = []
            for sub in value:
                sub_filters = _build_filter(model, sub)
                if sub_filters:
                    or_clauses.append(and_(*sub_filters))
            if or_clauses:
                filters.append(or_(*or_clauses))
            continue
        if key == "$and":
            and_clauses = []
            for sub in value:
                sub_filters = _build_filter(model, sub)
                and_clauses.extend(sub_filters)
            if and_clauses:
                filters.append(and_(*and_clauses))
            continue
        col = _get_col(model, key)
        if col is None:
            continue
        if isinstance(value, dict):
            if "$regex" in value:
                filters.append(_build_regex_filter(col, value))
            elif "$ne" in value:
                filters.append(col != value["$ne"])
            elif "$in" in value:
                filters.append(col.in_(value["$in"]))
            elif "$gt" in value:
                filters.append(col > value["$gt"])
            elif "$gte" in value:
                filters.append(col >= value["$gte"])
            elif "$lt" in value:
                filters.append(col < value["$lt"])
            elif "$lte" in value:
                filters.append(col <= value["$lte"])
            elif "$exists" in value:
                if value["$exists"]:
                    filters.append(col.isnot(None))
                else:
                    filters.append(col.is_(None))
            else:
                filters.append(col == value)
        else:
            filters.append(col == value)
    return filters


def _model_to_dict(obj, model_type):
    """Convert a SQLAlchemy model instance to a MongoDB-style dict."""
    if obj is None:
        return None
    result = {}
    for col in model_type.__table__.columns:
        val = getattr(obj, col.name, None)
        result[col.name] = val
    # Add MongoDB-style aliases
    if isinstance(obj, Product):
        result["productId"] = obj.fingerprint
        result["name"] = obj.name_de
        result["name_en"] = obj.name_de
        result["brandId"] = obj.brand
        if obj.category_id:
            result["categoryId"] = str(obj.category_id)
        result["defaultImageUrl"] = obj.default_image_url
        result["image"] = obj.default_image_url
        result["image_url"] = obj.default_image_url
        result["createdAt"] = obj.created_at
        result["updatedAt"] = obj.updated_at
    elif isinstance(obj, Category):
        result["categoryId"] = str(obj.id)
        result["imageUrl"] = obj.image_url
        result["parentId"] = obj.parent_id
    elif isinstance(obj, Store):
        result["storeId"] = obj.store_id
        result["logoUrl"] = obj.logo_url
        result["apiAvailable"] = obj.api_available
        result["scrapingRequired"] = obj.scraping_required
    elif isinstance(obj, Brand):
        result["brandId"] = obj.brand_id
    elif isinstance(obj, User):
        result["userId"] = obj.user_id
        result["is_admin"] = bool(obj.is_admin)
    elif isinstance(obj, ShoppingList):
        result["listId"] = obj.list_id
    elif isinstance(obj, Offer):
        result["storeProductId"] = str(obj.id)
        result["productId"] = obj.product_id
        result["storeId"] = obj.store_id
        result["productPageUrl"] = obj.product_url
        result["basePrice"] = float(obj.price) if obj.price else None
        result["promoPrice"] = None
        result["isAvailable"] = obj.is_available
        result["lastPriceUpdate"] = obj.last_seen
        result["offerDetails"] = None
    elif isinstance(obj, PendingProduct):
        result["created_at"] = obj.created_at
    return result


# ── Sort direction mapping ─────────────────────────────────────────
def _apply_sort(query, model, sort_spec):
    """Apply MongoDB-style sort to a SQLAlchemy query."""
    if not sort_spec:
        return query
    if isinstance(sort_spec, list):
        for field, direction in sort_spec:
            col = _get_col(model, field)
            if col is not None:
                query = query.order_by(desc(col) if direction == -1 else asc(col))
    elif isinstance(sort_spec, tuple):
        field, direction = sort_spec
        col = _get_col(model, field)
        if col is not None:
            query = query.order_by(desc(col) if direction == -1 else asc(col))
    return query


# ── MockCursor ─────────────────────────────────────────────────────
class MockCursor:
    def __init__(self, query, model):
        self.q = query
        self.model = model
        self._offset = 0
        self._limit = None

    def sort(self, field, direction=1):
        if isinstance(field, list):
            for f, d in field:
                col = _get_col(self.model, f)
                if col is not None:
                    self.q = self.q.order_by(desc(col) if d == -1 else asc(col))
        else:
            col = _get_col(self.model, field)
            if col is not None:
                self.q = self.q.order_by(desc(col) if direction == -1 else asc(col))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def skip(self, n):
        self._offset = n
        return self

    def __iter__(self):
        q = self.q.offset(self._offset)
        if self._limit is not None:
            q = q.limit(self._limit)
        for item in q.all():
            yield _model_to_dict(item, self.model)

    def __len__(self):
        return self.q.count()


# ── MockCollection ─────────────────────────────────────────────────
class MockCollection:
    def __init__(self, model):
        self.model = model

    def find(self, query=None, projection=None, sort=None):
        query = query or {}
        # Special handling: if querying store_products by productId (fingerprint),
        # resolve to the actual product PK first
        if self.model == Offer and "productId" in query:
            pid_val = query.get("productId")
            if isinstance(pid_val, str):
                from models.postgres_models import Product
                prod = Product.query.filter_by(fingerprint=pid_val).first()
                if prod:
                    query = dict(query)
                    query["productId"] = prod.id
                else:
                    return MockCursor(self.model.query.filter(False), self.model)
        filters = _build_filter(self.model, query)
        q = self.model.query.filter(*filters)
        cursor = MockCursor(q, self.model)
        if sort:
            cursor = cursor.sort(sort)
        return cursor

    def find_one(self, query=None, projection=None, sort=None):
        query = query or {}
        # Special handling: if querying store_products by productId (fingerprint)
        if self.model == Offer and "productId" in query:
            pid_val = query.get("productId")
            if isinstance(pid_val, str):
                from models.postgres_models import Product
                prod = Product.query.filter_by(fingerprint=pid_val).first()
                if prod:
                    query = dict(query)
                    query["productId"] = prod.id
                else:
                    return None
        filters = _build_filter(self.model, query)
        q = self.model.query.filter(*filters)
        if sort:
            if isinstance(sort, list):
                for f, d in sort:
                    col = _get_col(self.model, f)
                    if col is not None:
                        q = q.order_by(desc(col) if d == -1 else asc(col))
            else:
                field, direction = sort
                col = _get_col(self.model, field)
                if col is not None:
                    q = q.order_by(desc(col) if direction == -1 else asc(col))
        res = q.first()
        return _model_to_dict(res, self.model) if res else None

    def count_documents(self, query=None):
        query = query or {}
        filters = _build_filter(self.model, query)
        return self.model.query.filter(*filters).count()

    def update_one(self, query, update, upsert=False):
        filters = _build_filter(self.model, query)
        item = self.model.query.filter(*filters).first()
        if item:
            if "$set" in update:
                for k, v in update["$set"].items():
                    col_name = _map_field(k)
                    if col_name and hasattr(item, col_name):
                        setattr(item, col_name, v)
            db.session.commit()
            return type("result", (), {"matched_count": 1, "modified_count": 1})()
        elif upsert:
            new_item = self.model()
            if "$set" in update:
                for k, v in update["$set"].items():
                    col_name = _map_field(k)
                    if col_name and hasattr(new_item, col_name):
                        setattr(new_item, col_name, v)
            if "$setOnInsert" in update:
                for k, v in update["$setOnInsert"].items():
                    col_name = _map_field(k)
                    if col_name and hasattr(new_item, col_name):
                        setattr(new_item, col_name, v)
            db.session.add(new_item)
            db.session.commit()
            return type("result", (), {"matched_count": 0, "modified_count": 0, "upserted_id": new_item.id})()
        return type("result", (), {"matched_count": 0, "modified_count": 0})()

    def update_many(self, query, update, upsert=False):
        filters = _build_filter(self.model, query)
        items = self.model.query.filter(*filters).all()
        count = 0
        if "$set" in update:
            for item in items:
                for k, v in update["$set"].items():
                    col_name = _map_field(k)
                    if col_name and hasattr(item, col_name):
                        setattr(item, col_name, v)
                count += 1
            if count:
                db.session.commit()
        return type("result", (), {"matched_count": count, "modified_count": count})()

    def insert_one(self, doc):
        item = self.model()
        for k, v in doc.items():
            col_name = _map_field(k)
            if col_name and hasattr(item, col_name):
                setattr(item, col_name, v)
        db.session.add(item)
        db.session.commit()
        return type("result", (), {"inserted_id": item.id})()

    def insert_many(self, docs):
        ids = []
        for doc in docs:
            item = self.model()
            for k, v in doc.items():
                col_name = _map_field(k)
                if col_name and hasattr(item, col_name):
                    setattr(item, col_name, v)
            db.session.add(item)
            ids.append(item.id)
        db.session.commit()
        return type("result", (), {"inserted_ids": ids})()

    def delete_one(self, query):
        filters = _build_filter(self.model, query)
        item = self.model.query.filter(*filters).first()
        if item:
            db.session.delete(item)
            db.session.commit()
            return type("result", (), {"deleted_count": 1})()
        return type("result", (), {"deleted_count": 0})()

    def delete_many(self, query):
        filters = _build_filter(self.model, query)
        count = self.model.query.filter(*filters).delete()
        db.session.commit()
        return type("result", (), {"deleted_count": count})()


# ── MockDb ─────────────────────────────────────────────────────────
class MockDb:
    """MongoDB-style database interface backed by PostgreSQL."""
    def __init__(self):
        self.products = MockCollection(Product)
        self.categories = MockCollection(Category)
        self.users = MockCollection(User)
        self.stores = MockCollection(Store)
        self.brands = MockCollection(Brand)
        self.store_products = MockCollection(Offer)
        self.lists = MockCollection(ShoppingList)
        self.list_items = MockCollection(ListItem)
        self.feedback = MockCollection(Feedback)
        self.community_price_reports = MockCollection(CommunityPriceReport)
        # featured_deals table was removed - use deals_compat layer instead
        self.price_history = MockCollection(PriceHistory)
        self.pending_products = MockCollection(PendingProduct)
        self.public_lists = MockCollection(PublicList)
        self.favorites = MockCollection(Favorite)
        self.saved_recipes = MockCollection(SavedRecipe)
        self.price_feedback = MockCollection(PriceFeedback)
        self.notifications = MockCollection(Notification)
