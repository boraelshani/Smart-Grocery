from flask import render_template, request, redirect, url_for, session
from . import auth_bp
from models.models import users

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email in users and users[email]['password'] == password:
            session['user'] = email
            return redirect(url_for('main.home'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        if email not in users:
            users[email] = {"password": password, "name": name, "shopping_list": [], "total_cost": 0.0}
            session['user'] = email
            return redirect(url_for('main.home'))
        else:
            return render_template('signup.html', error="Email already exists")
    return render_template('signup.html')

@auth_bp.route('/profile', methods=['POST'])
def update_profile():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    email = session['user']
    new_list = request.form.getlist('shopping_list')
    users[email]['shopping_list'] = new_list
    return redirect(url_for('main.profile'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.home'))
