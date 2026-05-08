from flask import render_template, request, flash, redirect, url_for, jsonify
from . import admin_bp
from core.auth import require_admin
from utils.db import get_db
from core.utils import now_utc, generate_id, to_bool
from models.postgres_models import db, Store, Brand, Category, Product, User, Feedback, CommunityPriceReport

def _dashboard_payload():
    counts = {
        "stores": Store.query.count(),
        "brands": Brand.query.count(),
        "categories": Category.query.count(),
        "products": Product.query.count(),
        "users": User.query.count(),
        "feedback": Feedback.query.count(),
        "community_price_reports": CommunityPriceReport.query.count()
    }
    stats = {
        "total_products": counts["products"],
        "total_stores": counts["stores"],
        "total_users": counts["users"],
        "pending_feedback": Feedback.query.filter_by(status="pending").count(),
    }
    recent_feedback = [f.to_dict() for f in Feedback.query.order_by(Feedback.created_at.desc()).limit(5).all()]
    recent_reports = [r.to_dict() for r in CommunityPriceReport.query.order_by(CommunityPriceReport.created_at.desc()).limit(5).all()]

    return {"stats": stats, "recent_feedback": recent_feedback, "recent_reports": recent_reports, "counts": counts}

@admin_bp.route("/admin/", methods=["GET"])
@admin_bp.route("/admin", methods=["GET"])
def admin_dashboard():
    allowed, result = require_admin()
    if not allowed: return result
    try:
        data = _dashboard_payload()
        return render_template("admin_dashboard.html", data=data, user_email=result)
    except Exception as e:
        return render_template("admin_dashboard.html", error=f"Database error: {str(e)}", data={})
