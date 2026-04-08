import sys
lines = open('routes/lists_routes.py', encoding='utf-8').readlines()
found = False
for l in lines:
  if 'def remove_item_from_list_api' in l: found = True
  if found:
    sys.stdout.write(l)
    if 'return' in l and ('500' in l or 'except' in l): break
