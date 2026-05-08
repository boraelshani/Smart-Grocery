import time
import os
import re
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SUBCAT_IMAGE = 'https://images.unsplash.com/photo-1542838132-92c53300491e?q=80&w=200&auto=format&fit=crop'

CAT_ICONS = {
    'Fruits & Vegetables': 'bi-apple',
    'Meat & Seafood': 'bi-egg-fried',
    'Dairy & Eggs': 'bi-cup',
    'Pantry': 'bi-basket-fill',
    'Frozen Foods': 'bi-snow',
    'Bakery': 'bi-cupcake',
    'Snacks & Sweets': 'bi-cookie',
    'Beverages': 'bi-cup-straw',
    'Household & Cleaning': 'bi-house-heart',
    'Baby & Kids': 'bi-cart',
    'Fast Food & To Go': 'bi-truck',
    'Pets': 'bi-github',
    'Personal Care & Health': 'bi-heart-pulse',
    'Produce': 'bi-apple',
    'Meat': 'bi-egg-fried',
    'Dairy': 'bi-cup',
    'Frozen': 'bi-snow',
}


def get_mega_menu():
    import flask
    cache_key = '_mega_menu_data'
    try:
        app = flask.current_app._get_current_object()
        cached = app.config.get(cache_key)
        if cached and time.time() - cached['_ts'] < 300:
            return cached['_data']
    except RuntimeError:
        cached = globals().get('_module_menu_cache')
        if cached and time.time() - cached['_ts'] < 300:
            return cached['_data']

    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()

        cur.execute(
            'SELECT id, slug, name_en, image_url, parent_id, level FROM categories ORDER BY name_en'
        )
        rows = cur.fetchall()
        conn.close()

        parent_children = {}
        images = {}
        for cid, slug, name_en, image_url, parent_id, level in rows:
            if parent_id is not None:
                parent_children.setdefault(parent_id, []).append((cid, name_en))
            if name_en and image_url:
                images[name_en] = image_url

        roots = [r for r in rows if r[4] is None]
        categories = {}
        for idx, (cid, slug, name_en, image_url, parent_id, level) in enumerate(roots):
            l2_list = parent_children.get(cid, [])
            subcats_dict = {}
            for l2_cid, l2_name in l2_list:
                l3_list = [r[1] for r in parent_children.get(l2_cid, [])]
                subcats_dict[l2_name or 'Unknown'] = l3_list
            icon = CAT_ICONS.get(name_en, 'bi-grid')
            categories[name_en or 'Unknown'] = {
                'icon': icon,
                'subcats': subcats_dict,
                'count': 100 - idx
            }

        data = {
            "categories": categories,
            "brands": [],
            "images": images,
            "fallback_image": DEFAULT_SUBCAT_IMAGE
        }
        try:
            app.config[cache_key] = {'_data': data, '_ts': time.time()}
        except RuntimeError:
            globals()['_module_menu_cache'] = {'_data': data, '_ts': time.time()}
        return data
    except Exception as e:
        print("Error fetching mega menu data:", e)
        return {"categories": {}, "brands": [], "images": {}, "fallback_image": ""}
