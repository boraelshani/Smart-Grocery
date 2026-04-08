from flask import render_template, request, flash, redirect, url_for, jsonify
from . import admin_bp
from core.auth import require_admin
from utils.db import get_db
from core.utils import now_utc, generate_id, to_bool
from services.product_service import ProductService

def _dashboard_payload(db):
    collections = ["stores", "brands", "categories", "products", "users", "feedback"]
    counts = {name: db[name].count_documents({}) for name in collections}
    stats = {
        "total_products": counts.get("products", 0),
        "total_stores": counts.get("stores", 0),
        "total_users": counts.get("users", 0),
        "pending_feedback": db.feedback.count_documents({"resolved": {"$ne": True}}),
    }
    recent_feedback = list(db.feedback.find().sort("timestamp", -1).limit(5))
    return {"stats": stats, "recent_feedback": recent_feedback, "counts": counts}

@admin_bp.route("/admin/", methods=["GET"])
@admin_bp.route("/admin", methods=["GET"])
def admin_dashboard():
    allowed, result = require_admin()
    if not allowed: return result
    db = get_db()
    if db is None:
        return render_template("admin_dashboard.html", error="Database unavailable", data={})
    data = _dashboard_payload(db)
    return render_template("admin_dashboard.html", data=data, user_email=result)
