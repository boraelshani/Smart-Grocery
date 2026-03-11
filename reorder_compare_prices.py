import re

with open('templates/compare_prices.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Store
store_pattern = r'(\s*<!-- Supplementary Results: Matching Retailers -->.*?{% endif %}\n)'
m_store = re.search(store_pattern, html, re.DOTALL)
store_sec = m_store.group(1) if m_store else ""
html = html.replace(store_sec, "")

# Deals
deal_pattern = r'(\s*<!-- Supplementary Results: Promotional Content -->.*?{% endif %}\n)'
m_deal = re.search(deal_pattern, html, re.DOTALL)
deal_sec = m_deal.group(1) if m_deal else ""
html = html.replace(deal_sec, "")

if deal_sec:
    # Restructure Deals section card
    deal_sec = re.sub(
        r'<div class="card-body" style="background-color: #ffffff;">',
        r'<div class="card-body" style="background-color: #ffffff; z-index: 2; position: relative;">',
        deal_sec
    )
    # Make whole card clickable except for buttons
    deal_sec = re.sub(
        r'(<div class="card h-100 shadow-sm" style="background-color: import re

with open('templates/compare_<a
with op{ u    html = f.read()

# Store
store_pattern = r'(\s*<!-- Supplementary .g
# Store
store_patlasstore_itm_store = re.search(store_pattern, html, re.DOTALL)
store_sec = m_store.group(1) if m_sto)
store_sec = m_store.group(1) if m_store else ""
ht hhtml = html.replace(store_sec, "")

# Deals
de'.
# Deals
deal_pattern = r'(\s*<!-  mdeal_p rm_deal = re.search(deal_pattern, html, re.DOTALL)
deal_sec = m_deal.group(1) if m_deal el</deal_sec = m_deal.group(1) if m_deal else ""
htmewhtml = html.replace(deal_sec, "")

if deal_(1
if deal_sec:
    # Restructure 1)
    # Restrl_    deal_sec = re.sub(
        r'<d)
        r'<div class=al        r'<div class="card-body" style="background-color: #ffffff; z-'m        deal_sec
    )
    # Make whole card clickable except for buttons
    deal_sec = re.sub(
    rt    )
    # Mak D    le    deal_sec = re.sub(
        r'(<div clas                r'(<div classep
with open('templates/compare_<a
with op{ u    html = f.read()

# Store
store_   with op{ u    html = f.read()
in
# Store
store_pattern = r'(-->store_  # Store
store_patlasstore_itm_store = re.s <store_tastore_sec = m_store.group(1) if m_sto)
store_sec = m_store.group(1) ifw_store_sec = m_store.group(1) if m_stoctht hhtml = html.replace(store_sec, "")

# Dealfy
# Deals
de'.
# Deals
deal_pattern = b-4de'.
#wr# Dgadeal_p'
deal_= re.sub(target, store_sec + deal_sec + r'\n      \1', html)

with open('templathtmewhtml = html.replace(deal_sec, "")

if deal_(1
if     f.write(html)
