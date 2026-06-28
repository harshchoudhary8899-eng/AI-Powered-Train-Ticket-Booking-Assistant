import os

from flask import Flask

from .config import Config
from .extensions import db, login_manager
from .models import User


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["TICKET_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from .routes import main_bp

    app.register_blueprint(main_bp)

    @app.cli.command("init-db")
    def init_db_command():
        from .seed import init_db

        init_db(reset=True)
        print("Initialized database with sample stations, trains, and demo users.")

    if app.config.get("AUTO_INIT_DB"):
        with app.app_context():
            from .seed import init_db

            init_db(reset=False)

    return app

