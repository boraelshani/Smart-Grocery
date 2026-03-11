import re

def get_navbar(filename):
    with open(filename, 'r') as f:
        content = f.read()
    match = re.search(r'<nav.*?</nav>', content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(0)
    return None

base_nav = get_navbar('templates/home.html')
if not base_nav:
    print("Could not find base nav")
    exit(1)

for template in ['templates/product_detail.html', 'templates/featured_deal_detail.html', 'templates/product_info.html']:
    with open(template, 'r') as f:
        content = f.read()
    
    new_content = re.sub(r'<nav.*?</nav>', base_nav.replace('\\', '\\\\'), content, flags=re.DOTALL | re.IGNORECASE, count=1)
    
    with open(template, 'w') as f:
        f.write(new_content)
    print(f"Fixed {template}")

