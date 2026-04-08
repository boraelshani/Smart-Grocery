from utils.db import get_db
from core.utils import now_utc

class ProductService:
    @staticmethod
    def get_db():
        return get_db()

    @staticmethod
    def recompute_product_state(product_id):
        db = get_db()
        product = db.products.find_one({"productId": product_id})
        if not product:
            return

        offers = list(db.store_products.find({"productId": product_id, "isAvailable": True}))
        cheapest = None
        for offer in offers:
            price = offer.get("promoPrice") if offer.get("promoPrice") is not None else offer.get("basePrice")
            if price is None:
                continue
            if cheapest is None or float(price) < float(cheapest["price"]):
                cheapest = {"price": float(price), "storeProductId": offer.get("storeProductId")}

        update = {
            "updatedAt": now_utc(),
            "hasOffers": len(offers) > 0,
            "bestPrice": cheapest["price"] if cheapest else None,
            "bestStoreProductId": cheapest["storeProductId"] if cheapest else None
        }
        db.products.update_one({"productId": product_id}, {"$set": update})

    @staticmethod
    def delete_product(product_id):
        db = get_db()
        db.products.delete_one({"productId": product_id})
        db.store_products.delete_many({"productId": product_id})
        db.lists.update_many(
            {"items.productId": product_id},
            {"$pull": {"items": {"productId": product_id}}}
        )
