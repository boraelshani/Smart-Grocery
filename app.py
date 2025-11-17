from flask import Flask
import os
from routes import main_bp, auth_bp

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

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
