from flask import render_template
from . import main_bp

@main_bp.route('/discover')
def discover_page():
    return render_template('discover.html')
