import re

with open("comparison/store_matcher.py", "r") as f:
    text = f.read()

replacement = """        'store_image': entry.get('store_image') or entry.get('store_display_image'),
        'offer': entry.get('offer'),
        'has_deal': entry.get('has_deal'),
        'original_price': entry.get('original_price'),
        'discount_label': entry.get('discount_label'),
        'valid_until': entry.get('valid_until'),
        'deal_info': entry.get('deal_info'),
    }"""

text = re.sub(r"        'store_image': entry\.get\('store_image'\) or entry\.get\('store_display_image'\),\n        'offer': entry\.get\('offer'\),\n    }", replacement, text)

with open("comparison/store_matcher.py", "w") as f:
    f.write(text)
