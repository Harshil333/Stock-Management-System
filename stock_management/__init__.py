import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail

app = Flask(__name__)

app.config['SECRET_KEY'] = '5791628bb0b13ce0c676dfde280ba245'
# SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
# DATABASE_URL = sqlite:///site.db
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['WHOOSH_BASE'] = 'whoosh'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'harshildoshi6333@gmail.com'
app.config['MAIL_PASSWORD'] = 'harshil007'
mail = Mail(app)

from commands import cmd
app.register_blueprint(cmd)

from stock_management import routes