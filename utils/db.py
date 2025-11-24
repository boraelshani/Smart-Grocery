from flask_pymongo import PyMongo

# PyMongo instance; call mongo.init_app(app) in application factory / app.py
mongo = PyMongo()
