from app import app
with open('urls.txt', 'w') as f:
	f.write('\n'.join(str(rule) for rule in app.url_map.iter_rules()))
