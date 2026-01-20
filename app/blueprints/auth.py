from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required
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
    return redirect(url_for('main.index'))
