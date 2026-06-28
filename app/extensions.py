from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
login_manager = LoginManager()
setattr(login_manager, "login_view", "main.login")
setattr(login_manager, "login_message_category", "warning")
