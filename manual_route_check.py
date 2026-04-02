from app import app
for rule in app.url_map.iter_rules():
    if 'remove' in str(rule): print(repr(rule), rule.methods)
