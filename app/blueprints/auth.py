from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError
from app.models import User, db
import os

auth_bp = Blueprint('auth', __name__)
oauth = OAuth()

# Configure Google OAuth
def configure_oauth(app):
    oauth.init_app(app)
    
    client_id = app.config.get('GOOGLE_CLIENT_ID')
    client_secret = app.config.get('GOOGLE_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("WARNING: Google OAuth credentials not found in app config!")
    else:
        print(f"Google OAuth initialized with Client ID: {client_id[:10]}...")

    oauth.register(
        name='google',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        },
        client_id=client_id,
        client_secret=client_secret
    )

@auth_bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    # In a real app with valid credentials, this would redirect to Google
    # For now, we can implement a dev login or placeholder
    google = oauth.create_client('google')
    if not google:
        # Fallback if oauth not configured properly in this context
        return "Google Client not configured"
    redirect_uri = url_for('auth.authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@auth_bp.route('/google/callback')
def authorize():
    try:
        google = oauth.create_client('google')
        token = google.authorize_access_token()
    except MismatchingStateError:
        flash('Login session expired. Please try again.')
        return redirect(url_for('main.index'))
    except (OAuthError, Exception) as e:
        flash(f'Login failed: {str(e)}')
        return redirect(url_for('main.index'))

    user_info = token.get('userinfo')
    
    if user_info:
        email = user_info['email']
        name = user_info['name']
        google_id = user_info['sub']
        profile_pic = user_info.get('picture')

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                name=name,
                google_id=google_id,
                profile_pic=profile_pic,
                role='customer' # Default role
            )
            db.session.add(user)
            db.session.commit()
        
        login_user(user)
        return redirect(url_for('main.index'))
    
    flash('Authorization failed.')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('main.index'))

import hmac
import hashlib
import json
from flask import current_app

@auth_bp.route('/telegram/auth', methods=['POST'])
def telegram_auth():
    try:
        data = request.json
        init_data = data.get('initData')
        
        if not init_data:
            return {'status': 'error', 'message': 'No initData provided'}, 400
            
        # Extract user data
        parsed_data = data.get('parsedData')
        if not parsed_data or 'user' not in parsed_data:
             return {'status': 'error', 'message': 'Invalid data structure'}, 400
             
        tg_user = parsed_data['user']
        tg_id = str(tg_user.get('id'))
        first_name = tg_user.get('first_name', '')
        last_name = tg_user.get('last_name', '')
        username = tg_user.get('username', '')
        photo_url = tg_user.get('photo_url')
        
        # Construct name/email
        full_name = f"{first_name} {last_name}".strip()
        if not full_name:
            full_name = username
            
        # Fake email for DB constraint
        email = f"{tg_id}@telegram.user"
        
        user = User.query.filter_by(telegram_id=tg_id).first()
        
        if not user:
            # Check if email exists (conflict from other auth?)
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                 # Merge or handle conflict. For now, just login.
                 user = existing_email
                 user.telegram_id = tg_id
            else:
                user = User(
                    email=email,
                    name=full_name,
                    telegram_id=tg_id,
                    profile_pic=photo_url,
                    role='customer'
                )
                db.session.add(user)
                db.session.commit()
        else:
            # Update info if changed
            if user.name != full_name:
                user.name = full_name
            if photo_url and user.profile_pic != photo_url:
                user.profile_pic = photo_url
            db.session.commit()
                
        login_user(user, remember=True)
        
        # Set session flag for TMA
        session['is_tma'] = True
        
        # Clear any pending flash messages (like "Please log in") since we just logged in automatically
        session.pop('_flashes', None)
        
        return {'status': 'success'}
        
    except Exception as e:
        print(f"Telegram Auth Error: {e}")
        return {'status': 'error', 'message': str(e)}, 500

