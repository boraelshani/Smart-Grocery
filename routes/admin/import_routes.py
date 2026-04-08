from flask import render_template, request, flash, redirect, url_for, jsonify
from . import admin_bp
from core.auth import require_admin
from utils.db import get_db
from core.utils import now_utc, prettify_slug

@admin_bp.route("/products/smart-import", methods=["GET"])
def admin_smart_import_page():
    require_admin()
    return render_template("admin_smart_import.html")

@admin_bp.route("/api/products/smart-extract", methods=["POST"])
def admin_smart_extract():
    require_admin()
    if not request.is_json:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400
    
    url = request.json.get("url")
    if not url:
        return jsonify({"success": False, "error": "URL required"}), 400

    from scripts.ai_product_fetcher import fetch_product_from_url
    result = fetch_product_from_url(url)
    return jsonify(result)

@admin_bp.route("/scraper/run", methods=["GET"])
def run_scraper_manual():
    require_admin()
    try:
        import subprocess
        subprocess.Popen(["python3", "scripts/cron_pipeline.py"])
        flash("Price update engine triggered in background. Store catalog will sync shortly.", "success")
    except Exception as e:
        flash(f"Failed to start price updates: {str(e)}", "danger")
    return redirect(url_for("admin.admin_dashboard"))
