from sqlalchemy import or_, desc, asc
from models.postgres_models import db, Product, Category, Store, Brand, Offer, User, ShoppingList, ListItem, FeaturedDeal, Feedback, CommunityPriceReport, PriceHistory

class MockCursor:
    def __init__(self, query):
        self.q = query
    def sort(self, field, direction=1):
        if isinstance(field, list):
            for f, d in field:
                col = self._get_col(f)
                if col is not None:
                    self.q = self.q.order_by(desc(col) if d == -1 else asc(col))
        else:
            col = self._get_col(field)
            if col is not None:
                self.q = self.q.order_by(desc(col) if direction == -1 else asc(col))
        return self
    def limit(self, n):
        self.q = self.q.limit(n)
        return self
    def skip(self, n):
        self.q = self.q.offset(n)
        return self
    def _get_col(self, field_name):
        model = self.q.column_descriptions[0]['type']
        if field_name == 'createdAt': return getattr(model, 'created_at', None)
        if field_name == 'updatedAt': return getattr(model, 'updated_at', None)
        if field_name == 'name_en': return getattr(model, 'name_en', getattr(model, 'name', None))
        if field_name == 'timestamp': return getattr(model, 'created_at', getattr(model, 'timestamp', None))
        return getattr(model, field_name, None)
    def __iter__(self):
        for item in self.q.all():
            yield item.to_dict() if hasattr(item, 'to_dict') else vars(item)
    def __len__(self):
        return self.q.count()

class MockCollection:
    def __init__(self, model):
        self.model = model
    def _build_filter(self, query_dict):
        filters = []
        for k, v in query_dict.items():
            if k == '_id': continue
            if k == '$or':
                or_conds = []
                for subq in v:
                    or_conds.extend(self._build_filter(subq))
                if or_conds: filters.append(or_(*or_conds))
                continue
            if isinstance(v, dict) and '$regex' in v:
                col = getattr(self.model, k, None)
                if col is not None:
                    val = v['$regex']
                    if v.get('$options') == 'i':
                        filters.append(col.ilike(f'%{val}%'))
                    else:
                        filters.append(col.like(f'%{val}%'))
                continue
            col = getattr(self.model, k, None)
            if col is not None:
                filters.append(col == v)
        return filters

    def find(self, query=None, projection=None, sort=None):
        query = query or {}
        filters = self._build_filter(query)
        q = self.model.query.filter(*filters)
        cursor = MockCursor(q)
        if sort: cursor = cursor.sort(sort)
        return cursor

    def find_one(self, query=None, projection=None, sort=None):
        cursor = self.find(query, projection, sort)
        res = cursor.q.first()
        if res: return res.to_dict() if hasattr(res, 'to_dict') else vars(res)
        return None

    def count_documents(self, query=None):
        query = query or {}
        filters = self._build_filter(query)
        return self.model.query.filter(*filters).count()
        
    def update_one(self, query, update, upsert=False):
        item = self.model.query.filter(*self._build_filter(query)).first()
        if item and '$set' in update:
            for k, v in update['$set'].items():
                if k in ['updatedAt', 'createdAt']: continue
                if hasattr(item, k): setattr(item, k, v)
            db.session.commit()

class MockDb:
    def __init__(self):
        self.products = MockCollection(Product)
        self.categories = MockCollection(Category)
        self.users = MockCollection(User)
        self.stores = MockCollection(Store)
        self.brands = MockCollection(Brand)
        self.store_products = MockCollection(Offer)
        self.lists = MockCollection(ShoppingList)
        self.feedback = MockCollection(Feedback)
        self.community_price_reports = MockCollection(CommunityPriceReport)
        self.featured_deals = MockCollection(FeaturedDeal)
        self.price_history = MockCollection(PriceHistory)
