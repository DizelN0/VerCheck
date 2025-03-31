from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, static_folder='../static')
    app.config.from_object('app.config.Config')

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = ''

    with app.app_context():
        # Импортируем модели для регистрации в SQLAlchemy
        from . import models
        db.create_all()

        # Создаём администратора, если он не существует
        from werkzeug.security import generate_password_hash
        from .models import User, Product
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                password=generate_password_hash('admin'),
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()
            db.session.commit()

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.audit import audit_bp
    from app.routes.settings import settings_bp
    from app.routes.update import update_bp
    from app.routes.profile import profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(update_bp)
    app.register_blueprint(profile_bp)

    return app
