"""
USERS MODEL — PostgreSQL / SQLAlchemy (matches Neon schema)
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
import bcrypt
from sqlalchemy import func
from models.postgres_models import db, User, ShoppingList, ListItem

class UsersModel:
    def authenticate(self, email: str, password: str) -> bool:
        if not email or not password:
            return False
        user = User.query.filter_by(email=email).first()
        if not user or not user.password_hash:
            return False
        try:
            pw = user.password_hash
            if isinstance(pw, str):
                pw = pw.encode('utf-8')
            return bcrypt.checkpw(password.encode('utf-8'), pw)
        except Exception:
            return user.password_hash == password

    def get_user_by_email(self, email: str) -> Optional[dict]:
        if not email:
            return None
        user = User.query.filter_by(email=email).first()
        return user.to_dict() if user else None

    def create_user(self, user_doc: dict) -> str:
        email = user_doc.get('email')
        if not email:
            raise ValueError('email required')
        raw_pw = user_doc.get('password', '')
        if raw_pw and not raw_pw.startswith('$2'):
            hashed = bcrypt.hashpw(raw_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        else:
            hashed = raw_pw
        uid = user_doc.get('userId') or f"user_{uuid.uuid4().hex[:12]}"
        user = User(user_id=uid, email=email, password_hash=hashed, name=user_doc.get('name') or email)
        db.session.add(user)
        db.session.commit()
        return uid

    def update_user(self, email: str, update_data: dict) -> bool:
        user = User.query.filter_by(email=email).first()
        if not user:
            return False
        for key, val in update_data.items():
            if hasattr(user, key):
                setattr(user, key, val)
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return True

    def update_shopping_list(self, email: str, items: list):
        ld = get_user_lists(email)
        aid = ld.get('active_list_id')
        if not aid:
            aid = create_shopping_list(email, 'My List')
            set_active_list(email, aid)
        update_list_items(email, aid, items)

    def remove_from_shopping_list(self, email: str, item_name):
        ld = get_user_lists(email)
        aid = ld.get('active_list_id')
        if not aid:
            return False
        name = item_name if isinstance(item_name, str) else (item_name.get('name') if isinstance(item_name, dict) else str(item_name))
        return remove_item_from_list(email, aid, name)

    def share_list_with_user(self, owner_email, list_id, target_email, role='view'):
        user = User.query.filter_by(email=owner_email).first()
        if not user:
            return False
        lst = ShoppingList.query.filter_by(list_id=list_id, user_id=user.id).first()
        if not lst:
            return False
        lst.shared = True
        db.session.commit()
        return True

    def remove_collaborator(self, owner_email, list_id, target_email):
        return True

    def mark_dynamic_notifications_read(self, email, notification_ids):
        pass


users_model = UsersModel()

def get_user_by_email(email):
    return users_model.get_user_by_email(email)

def update_user(email, data):
    return users_model.update_user(email, data)

def update_user_profile(email, data):
    return users_model.update_user(email, data)

def _get_user_obj(email):
    return User.query.filter_by(email=email).first()

def get_user_lists(email: str) -> dict:
    user = _get_user_obj(email)
    if not user:
        return {'lists': [], 'active_list_id': None}
    lists = ShoppingList.query.filter_by(user_id=user.id).order_by(ShoppingList.updated_at.desc()).all()
    active_id = lists[0].list_id if lists else None
    return {'lists': [lst.to_dict() for lst in lists], 'active_list_id': active_id}

def create_shopping_list(email: str, name: str) -> Optional[str]:
    user = _get_user_obj(email)
    if not user:
        return None
    list_id = f"list_{uuid.uuid4().hex[:12]}"
    lst = ShoppingList(list_id=list_id, user_id=user.id, name=name or 'My List')
    db.session.add(lst)
    db.session.commit()
    return list_id

def set_active_list(email: str, list_id: str) -> bool:
    return True  # Active list is just the most recent one

def rename_shopping_list(email: str, list_id: str, new_name: str) -> bool:
    user = _get_user_obj(email)
    if not user:
        return False
    lst = ShoppingList.query.filter_by(list_id=list_id, user_id=user.id).first()
    if not lst:
        return False
    lst.name = new_name
    lst.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return True

def delete_shopping_list(email: str, list_id: str) -> bool:
    user = _get_user_obj(email)
    if not user:
        return False
    lst = ShoppingList.query.filter_by(list_id=list_id, user_id=user.id).first()
    if not lst:
        return False
    db.session.delete(lst)
    db.session.commit()
    return True

def update_list_items(email: str, list_id: str, items: list) -> bool:
    lst = ShoppingList.query.filter_by(list_id=list_id).first()
    if not lst:
        return False
    ListItem.query.filter_by(list_id=lst.id).delete()
    for item in items:
        if isinstance(item, dict):
            li = ListItem(list_id=lst.id,
                         product_name=item.get('name') or item.get('product_name') or '',
                         quantity=int(item.get('qty') or item.get('quantity') or 1),
                         checked=bool(item.get('purchased') or item.get('checked')))
        else:
            li = ListItem(list_id=lst.id, product_name=str(item), quantity=1)
        db.session.add(li)
    lst.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return True

def add_item_to_list(email: str, list_id: str, item) -> bool:
    lst = ShoppingList.query.filter_by(list_id=list_id).first()
    if not lst:
        return False
    if isinstance(item, dict):
        li = ListItem(list_id=lst.id,
                     product_name=item.get('name') or item.get('product_name') or '',
                     quantity=int(item.get('qty') or item.get('quantity') or 1))
    else:
        li = ListItem(list_id=lst.id, product_name=str(item), quantity=1)
    db.session.add(li)
    lst.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return True

def remove_item_from_list(email: str, list_id: str, item_name: str) -> bool:
    lst = ShoppingList.query.filter_by(list_id=list_id).first()
    if not lst:
        return False
    li = ListItem.query.filter_by(list_id=lst.id, product_name=item_name).first()
    if not li:
        return False
    db.session.delete(li)
    lst.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return True

def mark_items_as_seen(email: str, list_id: str) -> bool:
    return True
