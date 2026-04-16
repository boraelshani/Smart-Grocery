with open('routes/admin/common.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
text = text.replace('''query = {'': [{'_id': {'': object_ids}}, {'productId': {'': object_ids}}]}''', '''query = {'\': [{'_id': {'\': object_ids}}, {'productId': {'\': object_ids}}]}'''.replace('\\$', '$'))

with open('routes/admin/common.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed the query string missing dollars')
