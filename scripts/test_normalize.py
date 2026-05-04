import re
from pymongo import MongoClient
import os
from collections import defaultdict
from bson import ObjectId

def get_db():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    client = MongoClient(uri)
    return client.get_database("smart_grocery")

def normalize_title(title):
    t = str(title).lower()
    # Replace special chars with space
    t = re.sub(r'[^a-z0-9öäüß]', ' ', t)
    # Collapse spaces
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def extract_volume(title):
    # Look for patterns like 1.5l, 1,5 l, 500ml, 500 ml, 100g, 1 kg
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(ml|l|g|kg|cl|dl)', title.lower().replace(' ', ''))
    if match:
        val = match.group(1).replace(',', '.')
        unit = match.group(2)
        if unit == 'kg':
            return float(val) * 1000, 'g'
        if unit == 'l':
            return float(val) * 1000, 'ml'
        if unit == 'dl':
            return float(val) * 100, 'ml'
        if unit == 'cl':
            return float(val) * 10, 'ml'
        return float(val), unit
    return None, None

def strip_volume(title):
    # Remove volume strings from title
    t = re.sub(r'\d+(?:[.,]\d+)?\s*(ml|l|g|kg|cl|dl)\b', '', title.lower())
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def get_base_key(title):
    norm = normalize_title(title)
    vol_val, vol_unit = extract_volume(norm)
    base_name = strip_volume(norm)
    return f"{base_name}::{vol_val}{vol_unit}"

db = get_db()
print(f"Total products: {db.products.count_documents({})}")

# Let's test it on a sample of 1000 items from HeissePrices
sample = list(db.products.find({'is_placeholder': {'$ne': True}}))
groups = defaultdict(list)
for p in sample:
    name = p.get('name', '')
    key = get_base_key(name)
    groups[key].append(p)

merged_count = 0
examples = 0
for k, items in groups.items():
    if len(items) > 1:
        merged_count += 1
        if examples < 10:
            print(f"Group: {k}")
            for i in items:
                print(f"  - {i.get('name')} (stores: {len(i.get('stores', []))}) [{i.get('category')}]")
            examples += 1
print(f"Total over-mergable groups: {merged_count}")
