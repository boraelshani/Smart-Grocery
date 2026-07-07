import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app
from models.postgres_models import db
from sqlalchemy import text

with app.app_context():
    total = db.session.execute(text('SELECT COUNT(*) FROM products')).scalar()
    with_cat = db.session.execute(text('SELECT COUNT(*) FROM products WHERE category_id IS NOT NULL')).scalar()
    print(f'Total products:    {total}')
    print(f'With category:     {with_cat}')
    print(f'Without category:  {total - with_cat}')
    print()

    urls = db.session.execute(text(
        "SELECT product_url FROM product_store WHERE store_id='spar' AND product_url IS NOT NULL LIMIT 5"
    )).fetchall()
    print('Sample product URLs:')
    for r in urls:
        print(f'  {r[0]}')
    print()

    cats = db.session.execute(text('''
        SELECT c.name_de, c.slug, c.level, COUNT(p.id) as cnt
        FROM categories c
        JOIN products p ON p.category_id = c.id
        GROUP BY c.id, c.name_de, c.slug, c.level
        ORDER BY cnt DESC
        LIMIT 20
    ''')).fetchall()
    print('Categories assigned (top 20):')
    for r in cats:
        print(f'  [L{r[2]}] {r[0]:<40} {r[1]:<40} {r[3]} products')
    print()

    # Sample products with categories to verify correctness
    samples = db.session.execute(text('''
        SELECT p.name, c.name_de
        FROM products p
        JOIN categories c ON p.category_id = c.id
        LIMIT 15
    ''')).fetchall()
    print('Sample assigned products:')
    for r in samples:
        print(f'  {r[0]:<50} → {r[1]}')
