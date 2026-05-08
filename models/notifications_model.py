"""
═══════════════════════════════════════════════════════════════════════════
NOTIFICATIONS MODEL — PostgreSQL / SQLAlchemy
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timezone, timedelta
from models.postgres_models import db, Notification
from sqlalchemy import desc


class NotificationsModel:

    def create_notification(self, data: dict) -> bool:
        n = Notification(
            user_email=data.get('user_email'),
            type=data.get('type'),
            title=data.get('title'),
            message=data.get('message'),
            action_url=data.get('action_url'),
            priority=data.get('priority', 'normal'),
            product_id=data.get('product_id'),
            deal_id=data.get('deal_id'),
            store_name=data.get('store_name'),
        )
        db.session.add(n)
        db.session.commit()
        return True

    def get_user_notifications(self, email: str, unread_only=False, limit=50):
        q = Notification.query.filter_by(user_email=email)
        if unread_only:
            q = q.filter_by(read=False)
        rows = q.order_by(desc(Notification.created_at)).limit(limit).all()
        return [r.to_dict() for r in rows]

    def mark_as_read(self, notification_id, email: str) -> bool:
        try:
            n = Notification.query.filter_by(id=int(notification_id), user_email=email).first()
            if not n:
                return False
            n.read = True
            db.session.commit()
            return True
        except (ValueError, TypeError):
            return False

    def mark_all_as_read(self, email: str):
        Notification.query.filter_by(user_email=email, read=False).update({'read': True})
        db.session.commit()

    def delete_notification(self, notification_id, email: str) -> bool:
        try:
            n = Notification.query.filter_by(id=int(notification_id), user_email=email).first()
            if not n:
                return False
            db.session.delete(n)
            db.session.commit()
            return True
        except (ValueError, TypeError):
            return False

    def delete_all_notifications(self, email: str) -> bool:
        count = Notification.query.filter_by(user_email=email).delete()
        db.session.commit()
        return count > 0

    def cleanup_old_notifications(self, days=7):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        Notification.query.filter(
            Notification.read == True,
            Notification.created_at < cutoff,
        ).delete()
        db.session.commit()


notifications_model = NotificationsModel()


# Module-level convenience functions used by routes
def get_user_notifications(email, unread_only=False, limit=50):
    return notifications_model.get_user_notifications(email, unread_only, limit)


def mark_as_read(notification_id, email):
    return notifications_model.mark_as_read(notification_id, email)


def delete_notification(notification_id, email):
    return notifications_model.delete_notification(notification_id, email)
