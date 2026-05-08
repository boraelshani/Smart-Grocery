"""
Category service for PostgreSQL.
Provides category CRUD operations and tree building.
"""
from models.postgres_models import db, Category


def get_all_categories():
    """Get all categories as dicts, sorted by name."""
    cats = Category.query.order_by(Category.name_en).all()
    return [c.to_dict() for c in cats]


def get_category_by_id(cat_id):
    """Get a single category by its database ID."""
    try:
        cat = db.session.get(Category, int(cat_id))
        return cat.to_dict() if cat else None
    except (ValueError, TypeError):
        return None


def get_category_by_slug(slug):
    """Get a single category by slug."""
    cat = Category.query.filter_by(slug=slug).first()
    return cat.to_dict() if cat else None


def get_categories_tree():
    """Build a hierarchical category tree."""
    cats = Category.query.order_by(Category.name_en).all()
    nodes = {}
    roots = []

    for c in cats:
        node = c.to_dict()
        node["children"] = []
        nodes[str(c.id)] = node

    for cid, node in nodes.items():
        pid = node.get("parentId")
        if pid and str(pid) in nodes:
            nodes[str(pid)]["children"].append(node)
        else:
            roots.append(node)

    return roots


def get_category_path(cat_id):
    """Get the full path from root to a category."""
    path = []
    current = db.session.get(Category, int(cat_id))
    visited = set()

    while current and current.id not in visited:
        visited.add(current.id)
        path.insert(0, current.to_dict())
        if current.parent_id:
            current = db.session.get(Category, current.parent_id)
        else:
            break

    return path


def create_category(slug, name_en=None, name_de=None, parent_id=None,
                    level=1, icon=None, image_url=None):
    """Create a new category."""
    cat = Category(
        slug=slug,
        name_en=name_en,
        name_de=name_de,
        parent_id=parent_id,
        level=level,
        icon=icon,
        image_url=image_url,
    )
    db.session.add(cat)
    db.session.commit()
    return cat.to_dict()


def update_category(cat_id, **kwargs):
    """Update an existing category."""
    cat = db.session.get(Category, int(cat_id))
    if not cat:
        return None
    for key, val in kwargs.items():
        if hasattr(cat, key):
            setattr(cat, key, val)
    db.session.commit()
    return cat.to_dict()


def delete_category(cat_id):
    """Delete a category (fails if it has children or products)."""
    cat = db.session.get(Category, int(cat_id))
    if not cat:
        return False

    from models.postgres_models import Product
    has_children = Category.query.filter_by(parent_id=cat.id).first()
    has_products = Product.query.filter_by(category_id=cat.id).first()

    if has_children or has_products:
        return False

    db.session.delete(cat)
    db.session.commit()
    return True


def search_categories(query):
    """Search categories by name."""
    pattern = f"%{query}%"
    cats = Category.query.filter(
        Category.name_en.ilike(pattern) | Category.name_de.ilike(pattern)
    ).order_by(Category.name_en).all()
    return [c.to_dict() for c in cats]


def get_root_categories():
    """Get top-level categories (no parent)."""
    cats = Category.query.filter_by(parent_id=None).order_by(Category.name_en).all()
    return [c.to_dict() for c in cats]


def get_child_categories(parent_id):
    """Get direct children of a category."""
    cats = Category.query.filter_by(parent_id=parent_id).order_by(Category.name_en).all()
    return [c.to_dict() for c in cats]
