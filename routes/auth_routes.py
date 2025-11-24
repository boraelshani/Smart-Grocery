from flask import render_template, request, redirect, url_for, session
from . import auth_bp
from models.models import get_user_by_email, create_user
from utils.db import mongo


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = get_user_by_email(email)
        if user and user.get('password') == password:
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
        existing = get_user_by_email(email)
        if not existing:
            user_doc = {"email": email, "password": password, "name": name, "shopping_list": [], "total_cost": 0.0}
            create_user(user_doc)
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
    # update shopping list in DB if available, otherwise the fallback in models will handle it
    try:
        if mongo and mongo.db:
            mongo.db.users.update_one({'email': email}, {'$set': {'shopping_list': new_list}})
        else:
            # fallback: update in-memory users dict via models helper
            from models import models as m
            if email in m.users:
                m.users[email]['shopping_list'] = new_list
    except Exception:
        pass
    return redirect(url_for('main.profile'))


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.home'))
