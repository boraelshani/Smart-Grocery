from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship

db = SQLAlchemy()

class Store(db.Model):
    __tablename__ = 'stores'
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.String, unique=True, nullable=False)
    name = db.Column(db.String)
    website = db.Column(db.String)
    logo_url = db.Column(db.String)
    country = db.Column(db.String, default='AT')
    api_available = db.Column(db.Boolean)
    scraping_required = db.Column(db.Boolean)
    active = db.Column(db.Boolean, default=True)

    offers = relationship("Offer", back_populates="store")
    featured_deals = relationship("FeaturedDeal", back_populates="store")

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String, unique=True, nullable=False)
    name_en = db.Column(db.String)
    name_de = db.Column(db.String)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    level = db.Column(db.Integer)
    icon = db.Column(db.String)
    image_url = db.Column(db.String)

    products = relationship("Product", back_populates="category")

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    fingerprint = db.Column(db.String, unique=True, nullable=False)
    name_de = db.Column(db.String, nullable=False)
    brand = db.Column(db.String)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    unit_normalized = db.Column(db.String)
    size_normalized = db.Column(db.Numeric)
    default_image_url = db.Column(db.String)
    barcode = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("Category", back_populates="products")
    offers = relationship("Offer", back_populates="product", cascade="all, delete-orphan")

class Offer(db.Model):
    __tablename__ = 'offers'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete="CASCADE"))
    store_id = db.Column(db.String, db.ForeignKey('stores.store_id', ondelete="CASCADE"))
    price = db.Column(db.Numeric(10, 2))
    product_url = db.Column(db.String)
    is_available = db.Column(db.Boolean, default=True)
    last_seen = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="offers")
    store = relationship("Store", back_populates="offers")
    price_history = relationship("PriceHistory", back_populates="offer", cascade="all, delete-orphan")
    promotions = relationship("Promotion", back_populates="offer", cascade="all, delete-orphan")

class PriceHistory(db.Model):
    __tablename__ = 'price_history'
    id = db.Column(db.Integer, primary_key=True)
    offer_id = db.Column(db.Integer, db.ForeignKey('offers.id', ondelete="CASCADE"))
    price = db.Column(db.Numeric(10, 2))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)

    offer = relationship("Offer", back_populates="price_history")

class Promotion(db.Model):
    __tablename__ = 'promotions'
    id = db.Column(db.Integer, primary_key=True)
    offer_id = db.Column(db.Integer, db.ForeignKey('offers.id', ondelete="CASCADE"))
    type = db.Column(db.String)
    value = db.Column(db.String)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    offer = relationship("Offer", back_populates="promotions")

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, unique=True)
    email = db.Column(db.String, unique=True)
    password_hash = db.Column(db.String)
    name = db.Column(db.String)
    avatar = db.Column(db.String)
    language = db.Column(db.String, default='de')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    shopping_lists = relationship("ShoppingList", back_populates="user", cascade="all, delete-orphan")
    recipes = relationship("Recipe", back_populates="user", cascade="all, delete-orphan")

class ShoppingList(db.Model):
    __tablename__ = 'shopping_lists'
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.String, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    name = db.Column(db.String)
    share_code = db.Column(db.String, unique=True)
    shared = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="shopping_lists")
    items = relationship("ListItem", back_populates="shopping_list", cascade="all, delete-orphan")

class ListItem(db.Model):
    __tablename__ = 'list_items'
    id = db.Column(db.Integer, primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('shopping_lists.id', ondelete="CASCADE"))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete="SET NULL"))
    product_name = db.Column(db.String)
    quantity = db.Column(db.Numeric, default=1)
    checked = db.Column(db.Boolean, default=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    shopping_list = relationship("ShoppingList", back_populates="items")
    product = relationship("Product")

class Recipe(db.Model):
    __tablename__ = 'recipes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    title = db.Column(db.String)
    instructions = db.Column(db.String)
    image_url = db.Column(db.String)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="recipes")
    ingredients = relationship("RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan")

class RecipeIngredient(db.Model):
    __tablename__ = 'recipe_ingredients'
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id', ondelete="CASCADE"))
    product_fingerprint = db.Column(db.String)
    ingredient_name = db.Column(db.String)
    quantity = db.Column(db.Numeric)
    unit = db.Column(db.String)

    recipe = relationship("Recipe", back_populates="ingredients")

class Favorite(db.Model):
    __tablename__ = 'favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete="CASCADE"))
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete="CASCADE"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FeaturedDeal(db.Model):
    __tablename__ = 'featured_deals'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    description = db.Column(db.String)
    price = db.Column(db.Numeric)
    original_price = db.Column(db.Numeric)
    discount_percent = db.Column(db.Integer)
    store_id = db.Column(db.String, db.ForeignKey('stores.store_id', ondelete="CASCADE"))
    image_url = db.Column(db.String)
    url = db.Column(db.String)
    category_slug = db.Column(db.String, db.ForeignKey('categories.slug', ondelete="SET NULL"))
    active = db.Column(db.Boolean, default=True)
    valid_until = db.Column(db.Date)

    store = relationship("Store", back_populates="featured_deals")
    category = relationship("Category")
