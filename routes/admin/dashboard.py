from flask import render_template, request, flash, redirect, url_for, jsonify
from . import admin_bp
from core.auth import require_admin
from utils.db import get_db
from core.utils import now_utc, generate_id, to_bool
from models.postgres_models import db, Store, Brand, Category, Product, User, Feedback, CommunityPriceReport, Offer, ScraperRun
from datetime import datetime, timedelta, timezone

def _dashboard_payload():
    now = datetime.now(timezone.utc)
    three_days_ago = now - timedelta(days=3)
    
    total_products = Product.query.count()
    active_offers = Offer.query.filter_by(is_available=True).count()
    total_stores = Store.query.count()
    total_users = User.query.count()
    
    stale_offers = Offer.query.filter(Offer.last_seen < three_days_ago).count()
    unmatched_products = 0 
    
    recent_runs = [r for r in ScraperRun.query.order_by(ScraperRun.created_at.desc()).limit(5).all()]
    
    stats = {
        "total_products": total_products,
        "active_offers": active_offers,
        "total_stores": total_stores,
        "total_users": total_users,
        "stale_offers": stale_offers,
        "unmatched_products": unmatched_products
    }
    
    chart_data = {
        "labels": [(now - timedelta(days=i)).strftime('%a') for i in range(6, -1, -1)],
        "data": [0,0,0,0,0,0,0] 
    }

    return {"stats": stats, "recent_runs": recent_runs, "chart_data": chart_data}

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
