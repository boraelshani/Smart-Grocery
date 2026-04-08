
import re

def parse_req(text):
    m = re.match(r'^\s*([\d\.]+)\s*([a-zA-Z]+)', text)
    if m:
        return float(m.group(1)), m.group(2).lower()
    m2 = re.match(r'^\s*([\d\.]+)', text)
    if m2:
        return float(m2.group(1)), ''
    return None, None

def parse_prod(unit_text):
    if not unit_text: return None, None
    m = re.match(r'^\s*([\d\.]+)\s*([a-zA-Z]+)', str(unit_text))
    if m:
        return float(m.group(1)), m.group(2).lower()
    return None, None

def calculate_proportion(req_text, prod_unit, price):
    req_q, req_u = parse_req(req_text)
    prod_q, prod_u = parse_prod(prod_unit)
    if not req_q or not prod_q or not req_u or not prod_u: return None
    
    # basic normalizations
    if req_u == 'kg': req_q *= 1000; req_u = 'g'
    if req_u == 'l': req_q *= 1000; req_u = 'ml'
    if prod_u == 'kg': prod_q *= 1000; prod_u = 'g'
    if prod_u == 'l': prod_q *= 1000; prod_u = 'ml'
    
    if req_u != prod_u: return None
    
    prop = req_q / prod_q
    if prop >= 1.0: return None # You need at least 1 whole item or more, let's keep it mostly for partial usage. Wait, user said "using 50 ml of that oi; how much cents are u using per m;
