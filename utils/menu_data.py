import time
import os
import re
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SUBCAT_IMAGE = 'https://images.unsplash.com/photo-1542838132-92c53300491e?q=80&w=200&auto=format&fit=crop'

# Updated category icons with better Bootstrap Icons
CAT_ICONS = {
    'Fruits & Vegetables': 'bi-apple',
    'Meat & Seafood': 'bi-egg-fried',
    'Dairy & Eggs': 'bi-cup',
    'Pantry': 'bi-basket-fill',
    'Frozen Foods': 'bi-snow',
    'Bakery': 'bi-cake2',
    'Snacks & Sweets': 'bi-cookie',
    'Beverages': 'bi-cup-straw',
    'Household & Cleaning': 'bi-house-heart',
    'Baby & Kids': 'bi-heart',
    'Fast Food & To Go': 'bi-truck',
    'Pets': 'bi-heart-pulse',
    'Personal Care & Health': 'bi-heart-pulse-fill',
    'Produce': 'bi-apple',
    'Meat': 'bi-egg-fried',
    'Dairy': 'bi-cup',
    'Frozen': 'bi-snow',
    'Diapers & Wipes': 'bi-heart',
}

# Category display order (most important first)
CATEGORY_ORDER = [
    'Fruits & Vegetables',
    'Meat & Seafood',
    'Dairy & Eggs',
    'Bakery',
    'Pantry',
    'Frozen Foods',
    'Beverages',
    'Snacks & Sweets',
    'Personal Care & Health',
    'Household & Cleaning',
    'Baby & Kids',
    'Diapers & Wipes',
    'Pets',
    'Fast Food & To Go',
]


def get_mega_menu():
    import flask
    cache_key = '_mega_menu_data'
    app = None
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

        # Fetch all categories with proper ordering
        cur.execute('''
            SELECT id, slug, name_en, name_de, image_url, parent_id, level 
            FROM categories 
            ORDER BY level ASC, name_de ASC
        ''')
        rows = cur.fetchall()

        # Build lookup maps
        cat_by_id = {}
        parent_children = {}
        images = {}
        
        for cid, slug, name_en, name_de, image_url, parent_id, level in rows:
            # Use German name as primary (since data is in German)
            display_name = name_de or name_en or 'Unknown'
            cat_by_id[cid] = {
                'id': cid,
                'slug': slug,
                'name_en': name_en,
                'name_de': name_de,
                'display_name': display_name,
                'image_url': image_url,
                'parent_id': parent_id,
                'level': level
            }
            
            if parent_id is not None:
                parent_children.setdefault(parent_id, []).append(cid)
            
            if display_name and image_url:
                images[display_name] = image_url

        # Fetch brands separately so the Browse > Brands tab can reflect saved brand rows.
        cur.execute('''
            SELECT id, brand_id, name, name_en, name_de, image_url, website
            FROM brands
            ORDER BY COALESCE(name, name_en, name_de, brand_id, id::text) ASC
        ''')
        brand_rows = cur.fetchall()

        def _brand_display_name(name, name_en, name_de, brand_id, row_id):
            for value in (name, name_en, name_de, brand_id, str(row_id) if row_id is not None else ''):
                if value and str(value).strip():
                    return str(value).strip()
            return 'Unknown'

        def _brand_initials(label):
            parts = [part for part in re.split(r'\s+', label.strip()) if part]
            if not parts:
                return 'BR'
            if len(parts) == 1:
                token = parts[0][:2].upper()
                return token if len(token) == 2 else (token + 'R')[:2]
            return ''.join(part[0] for part in parts[:2]).upper()

        brands = []
        for row_id, brand_id, name, name_en, name_de, image_url, website in brand_rows:
            display_name = _brand_display_name(name, name_en, name_de, brand_id, row_id)
            brands.append({
                'brandId': brand_id or str(row_id),
                'name': name or display_name,
                'display_name': display_name,
                'image': image_url or '',
                'website': website or '',
                'initials': _brand_initials(display_name),
            })

        conn.close()

        # Get root categories (level 1, parent_id is NULL)
        roots = [cat_by_id[cid] for cid in cat_by_id if cat_by_id[cid]['parent_id'] is None and cat_by_id[cid]['level'] == 1]
        
        # Build hierarchical structure
        categories = {}
        for root in roots:
            root_name = root['display_name']
            
            # Get level 2 children
            l2_children_ids = parent_children.get(root['id'], [])
            subcats_dict = {}
            
            for l2_id in l2_children_ids:
                if l2_id not in cat_by_id:
                    continue
                l2_cat = cat_by_id[l2_id]
                l2_name = l2_cat['display_name']
                
                # Get level 3 children
                l3_children_ids = parent_children.get(l2_id, [])
                l3_names = []
                for l3_id in l3_children_ids:
                    if l3_id in cat_by_id:
                        l3_names.append(cat_by_id[l3_id]['display_name'])
                
                # Only add subcategory if it has a valid name
                if l2_name and l2_name != 'Unknown':
                    subcats_dict[l2_name] = l3_names
            
            # Determine icon - try to match by name similarity
            icon = 'bi-grid'
            for eng_name, eng_icon in CAT_ICONS.items():
                # Check if English name is in German name or vice versa (case insensitive)
                if (eng_name.lower() in root_name.lower() or 
                    root_name.lower() in eng_name.lower() or
                    any(word in root_name.lower() for word in eng_name.lower().split())):
                    icon = eng_icon
                    break
            
            # Only add category if it has a valid name
            if root_name and root_name != 'Unknown':
                categories[root_name] = {
                    'icon': icon,
                    'subcats': subcats_dict,
                    'count': len(l2_children_ids),
                    'image': root['image_url'],
                    'id': root['id']
                }
        
        # Sort categories by predefined order, then alphabetically
        def category_sort_key(item):
            cat_name = item[0]
            # Try to find in predefined order
            for idx, order_name in enumerate(CATEGORY_ORDER):
                if order_name.lower() in cat_name.lower() or cat_name.lower() in order_name.lower():
                    return (0, idx, cat_name)
            # Not in predefined order, sort alphabetically after
            return (1, 999, cat_name)
        
        sorted_categories = dict(sorted(categories.items(), key=category_sort_key))

        data = {
            "categories": sorted_categories,
            "brands": brands,
            "images": images,
            "fallback_image": DEFAULT_SUBCAT_IMAGE
        }
        
        if app is not None:
            try:
                app.config[cache_key] = {'_data': data, '_ts': time.time()}
            except RuntimeError:
                globals()['_module_menu_cache'] = {'_data': data, '_ts': time.time()}
        else:
            globals()['_module_menu_cache'] = {'_data': data, '_ts': time.time()}
        
        return data
        
    except Exception as e:
        print("Error fetching mega menu data:", e)
        import traceback
        traceback.print_exc()
        return {"categories": {}, "brands": [], "images": {}, "fallback_image": ""}

