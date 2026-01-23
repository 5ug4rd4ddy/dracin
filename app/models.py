from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    google_id = db.Column(db.String(255))
    telegram_id = db.Column(db.String(50), unique=True, nullable=True)
    profile_pic = db.Column(db.String(255))
    role = db.Column(db.Enum('admin', 'customer'), default='customer')
    subscription_end_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Movie(db.Model):
    __tablename__ = 'movies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    poster_url = db.Column(db.Text)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    episodes = db.relationship('Episode', backref='movie', lazy=True)

class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    id = db.Column(db.Integer, primary_key=True)
    site_title = db.Column(db.String(255), default='DracinLovers')
    site_description = db.Column(db.Text)
    meta_keywords = db.Column(db.Text)
    google_analytics_id = db.Column(db.String(50))
    google_search_console_id = db.Column(db.String(100))
    favicon_url = db.Column(db.Text)
    logo_url = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Episode(db.Model):
    __tablename__ = 'episodes'
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    title = db.Column(db.String(255))
    episode_number = db.Column(db.Integer)
    video_url = db.Column(db.Text)
    subtitle_url = db.Column(db.Text)
    is_free = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    __table_args__ = (
        db.Index('idx_transaction_user_created', 'user_id', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.Integer) # Optional link to plan
    amount = db.Column(db.Numeric(10, 2))
    status = db.Column(db.Enum('pending', 'paid', 'failed'), default='pending')
    payment_proof = db.Column(db.Text)
    qris_content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Favorite(db.Model):
    __tablename__ = 'favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
