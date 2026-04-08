import re
print(re.search(r'(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|liter|lite|piece|stk|stück|gramm|milliliter)(?!\w)', 'Test 500g product', re.IGNORECASE).groups())
print(re.search(r'(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|liter|lite|piece|stk|stück|gramm|milliliter)(?!\w)', 'Milk 1l', re.IGNORECASE).groups())
print(re.search(r'(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|liter|lite|piece|stk|stück|gramm|milliliter)(?!\w)', 'Cheese 400 g slice', re.IGNORECASE).groups())
