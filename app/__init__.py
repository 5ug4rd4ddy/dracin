from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from config import Config
from app.models import db, User

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
migrate = Migrate()
csrf = CSRFProtect()
cache = Cache()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app(config_class=Config):
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    cache.init_app(app)

    @app.context_processor
    def inject_global_vars():
        from datetime import datetime
        from app.models import SiteSettings
        return {
            'now': datetime.now(),
            'site_settings': SiteSettings.query.first()
        }

    # Register Blueprints
    from app.blueprints.main import main_bp
    from app.blueprints.auth import auth_bp, configure_oauth
    from app.blueprints.admin import admin_bp
    from app.blueprints.payment import payment_bp
    from app.blueprints.webhook import webhook_bp

    configure_oauth(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(payment_bp, url_prefix='/payment')
    app.register_blueprint(webhook_bp, url_prefix='/webhook')

    return app
