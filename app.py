from flask import Flask
import os
from routes import main_bp, auth_bp
from utils.db import mongo

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# MongoDB configuration
# Use `MONGO_URI` environment variable when available (Atlas or custom),
# otherwise default to a local DB named `smart_grocery`.
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/smart_grocery')

# Initialize PyMongo with the Flask app
mongo.init_app(app)

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)

# Error Handling
@app.errorhandler(404)
def not_found(error):
    from flask import render_template
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    from flask import render_template
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)
