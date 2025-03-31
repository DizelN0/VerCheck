import datetime
from flask_login import UserMixin
from . import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')
    full_name = db.Column(db.String(100))
    profession = db.Column(db.String(100))
    notify = db.Column(db.Boolean, default=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    latest_version = db.Column(db.String(50))
    last_updated = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    error = db.Column(db.String(200))

class UserProduct(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    accepted_version = db.Column(db.String(50))
    accepted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255))
    read = db.Column(db.Boolean, default=False)

class ProductVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    version = db.Column(db.String(50), nullable=False)
    release_date = db.Column(db.String(50))
    full_title = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class AuditItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    user_version = db.Column(db.String(50), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
