from utils.db import mongo
from datetime import datetime

class FeedbackModel:
    @staticmethod
    def add_price_report(product_id, store, user_email, is_correct, reported_price=None):
        collection = mongo.db.price_feedback if mongo and mongo.db else None
        if not collection:
            return False
            
        report = {
            "product_id": product_id,
            "store": store,
            "user_email": user_email,
            "is_correct": is_correct,
            "reported_price": reported_price,
            "timestamp": datetime.utcnow()
        }
        collection.insert_one(report)
        return True
