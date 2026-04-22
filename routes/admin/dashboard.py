from flask import render_template, request, flash, redirect, url_for, jsonify
from . import admin_bp
from core.auth import require_admin
from utils.db import get_db
from core.utils import now_utc, generate_id, to_bool
from services.product_service import ProductService

def _dashboard_payload(db):
    collections = ["stores", "brands", "categories", "products", "users", "feedback", "community_price_reports"]
    counts = {name: db[name].count_documents({}) for name in collections}
    stats = {
        "total_products": counts.get("products", 0),
        "total_stores": counts.get("stores", 0),
        "total_users": counts.get("users", 0),
        "pending_feedback": db.feedback.count_documents({"resolved": {"$ne": True}}),
    }
    recent_feedback = list(db.feedback.find().sort("timestamp", -1).limit(5))
    
    recent_reports = list(db.community_price_reports.find().sort("created_at", -1).limit(5))
    for r in recent_reports:
        # Convert ObjectId & datetime to strings for template rendering just in case.
        if '_id' in r:
            r['_id'] = str(r['_id'])
        if 'created_at' in r:
            r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(r['created_at'], 'strftime') else str(r['created_at'])

    return {"stats": stats, "recent_feedback": recent_feedback, "recent_reports": recent_reports, "counts": counts}

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
