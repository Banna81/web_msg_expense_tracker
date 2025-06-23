from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(100), unique=True, nullable = False)
    password = db.Column(db.String(200), nullable = False )

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200))
    expenses = db.relationship('Expense', backref='category', lazy=True)
    subcategories = db.relationship('SubCategory', backref='category', lazy=True)

class SubCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    expenses = db.relationship('Expense', backref='subcategory', lazy=True)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # Add this line for the primary key
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    msg_unparsed = db.Column(db.String(255))
    amount = db.Column(db.Float)
    merchant = db.Column(db.String(100))
    hashtags = db.Column(db.PickleType)
    description = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    subcategory_id = db.Column(db.Integer, db.ForeignKey('sub_category.id'))
    timestamp = db.Column(db.DateTime)