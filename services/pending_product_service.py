from models.postgres_models import PendingProduct


class PendingProductService:
    @staticmethod
    def get_by_barcode(barcode):
        if not barcode:
            return None
        return PendingProduct.query.filter_by(barcode=barcode).first()
