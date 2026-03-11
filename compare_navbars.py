import re
import glob

def get_navbar(filename):
    with open(filename, 'r') as f:
        content = f.read()
    match = re.search(r'<nav.*?</nav>', content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(0)
    return None

base_nav = get_navbar('templates/home.html')

for template in ['templates/product_detail.html', 'templates/featured_deal_detail.html', 'templates/product_info.html']:
    nav = get_navbar(template)
    if nav:
        print(f"--- {template} ---")
        if base_nav == nav:
            print("IDENTICAL to home.html")
        else:
            print("DIFFERENT from home.html")
            print("Length base:", len(base_nav), "Length current:", len(nav))
            
