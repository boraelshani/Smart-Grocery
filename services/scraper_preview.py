import re
from typing import List, Dict


def generate_fingerprint(name: str, brand: str = "", unit: str = "", size: float = 0) -> str:
    if not name:
        return ""
    name_norm = re.sub(r"[^\w\s]", "", name.lower()).strip()
    brand_norm = re.sub(r"[^\w\s]", "", (brand or "").lower()).strip()
    unit_norm = (unit or "").lower()
    size_norm = f"{float(size):.2f}" if size else ""
    parts = [p for p in [brand_norm, name_norm, size_norm, unit_norm] if p]
    return "_".join(parts)


def compare_scraped_to_db(scraped_products: List[Dict], db_session, store_id: str) -> Dict:
    """Compare a list of scraped products to the DB and return a preview of changes.

    Returns dict with keys: to_create (products not in DB), to_update (existing with price change), no_change
    """
    from models.postgres_models import Product, ProductStore
    out = {"to_create": [], "to_update": [], "no_change": []}

    # Build fingerprints for scraped
    fps = []
    scraped_map = {}
    for p in scraped_products:
        fp = p.get("fingerprint") or generate_fingerprint(p.get("name"), p.get("brand", ""), p.get("unit", ""), p.get("size_normalized") or p.get("size") or 0)
        p["_fp"] = fp
        fps.append(fp)
        scraped_map[fp] = p

    # Query existing products with those fingerprints
    existing = {}
    if fps:
        rows = Product.query.filter(Product.fingerprint.in_(fps)).all()
        for r in rows:
            existing[r.fingerprint] = r

    existing_store_rows = {}
    product_ids = [prod.id for prod in existing.values()]
    if product_ids:
        store_rows = ProductStore.query.filter(
            ProductStore.product_id.in_(product_ids),
            ProductStore.store_id == store_id,
        ).all()
        for row in store_rows:
            existing_store_rows[(row.product_id, row.store_id)] = row

    for fp, sp in scraped_map.items():
        prod = existing.get(fp)
        price = float(sp.get("price") or 0)
        target_store = str((sp.get("store") or store_id or "")).lower()

        if not prod:
            out["to_create"].append({"fingerprint": fp, "product": sp})
            continue

        # Check store-specific price
        ps = existing_store_rows.get((prod.id, target_store))
        if not ps:
            out["to_create"].append({"fingerprint": fp, "product": sp, "reason": "new_store_listing"})
            continue

        old_price = float(ps.base_price) if ps.base_price is not None else None
        # Consider tiny rounding differences as no-change
        if old_price is None or abs(old_price - price) > 0.005:
            out["to_update"].append({"fingerprint": fp, "product_id": prod.id, "old_price": old_price, "new_price": price, "product": sp})
        else:
            out["no_change"].append({"fingerprint": fp, "product_id": prod.id})

    return out


def apply_scraped_products(scraped_products: List[Dict], db_session, store_id: str) -> Dict:
    """Apply scraped product changes using bulk lookups to avoid N+1 queries."""
    from models.postgres_models import Product, ProductStore, PriceHistory

    stats = {"created": 0, "updated": 0, "unchanged": 0}
    if not scraped_products:
        return stats

    normalized = []
    fingerprints = []
    for p in scraped_products:
        fp = p.get("fingerprint") or generate_fingerprint(
            p.get("name"), p.get("brand", ""), p.get("unit", ""), p.get("size_normalized") or p.get("size") or 0
        )
        p["_fp"] = fp
        normalized.append(p)
        if fp:
            fingerprints.append(fp)

    existing_products = {}
    if fingerprints:
        for prod in Product.query.filter(Product.fingerprint.in_(fingerprints)).all():
            existing_products[prod.fingerprint] = prod

    product_ids = [prod.id for prod in existing_products.values()]
    existing_store_rows = {}
    if product_ids:
        store_rows = ProductStore.query.filter(
            ProductStore.product_id.in_(product_ids),
            ProductStore.store_id == store_id,
        ).all()
        for row in store_rows:
            existing_store_rows[(row.product_id, row.store_id)] = row

    for sp in normalized:
        fp = sp["_fp"]
        price = float(sp.get("price") or 0)
        prod = existing_products.get(fp)

        if not prod:
            prod = Product(
                fingerprint=fp,
                name=sp.get("name") or "",
                name_de=sp.get("name") or "",
                brand=sp.get("brand"),
                unit_normalized=sp.get("unit"),
                size_normalized=sp.get("size_normalized") or None,
                default_image_url=sp.get("image") or sp.get("image_url") or None,
            )
            db_session.add(prod)
            db_session.flush()
            existing_products[fp] = prod

        key = (prod.id, store_id)
        ps = existing_store_rows.get(key)
        if not ps:
            ps = ProductStore(product_id=prod.id, store_id=store_id, base_price=price)
            db_session.add(ps)
            existing_store_rows[key] = ps
            stats["created"] += 1
            continue

        old_price = float(ps.base_price) if ps.base_price is not None else None
        if old_price is None or abs(old_price - price) > 0.005:
            db_session.add(
                PriceHistory(
                    product_id=prod.id,
                    store_id=store_id,
                    old_price=old_price,
                    new_price=price,
                    source="scraper_preview",
                )
            )
            ps.base_price = price
            stats["updated"] += 1
        else:
            stats["unchanged"] += 1

    db_session.commit()
    return stats
