"""
═══════════════════════════════════════════════════════════════════════════
FEEDBACK MODEL — PostgreSQL / SQLAlchemy
═══════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, timezone
from models.postgres_models import db, PriceFeedback


class FeedbackModel:
    @staticmethod
    def add_price_report(product_id, store, user_email, is_correct, reported_price=None):
        try:
            report = PriceFeedback(
                product_id=product_id,
                store=store,
                user_email=user_email,
                is_correct=is_correct,
                reported_price=float(reported_price) if reported_price else None,
            )
            db.session.add(report)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False
