import re

with open("routes/admin/common.py", "r") as f:
    code = f.read()

code = code.replace('db = get_db()', 'from models.postgres_models import db, Product, Category, Store, Brand, Offer, User, ShoppingList, ListItem, FeaturedDeal\n    pass')
code = code.replace('db.products.count_documents(q)', 'Product.query.count()')
code = code.replace('db.users.count_documents(q)', 'User.query.count()')
code = code.replace('db.categories.count_documents(q)', 'Category.query.count()')

with open("routes/admin/common.py", "w") as f:
    f.write(code)
print("Did a naive replacement.")
