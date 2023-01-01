import os
import locale
from platform import platform

from dotenv import load_dotenv

load_dotenv()

class config_():

    def __init__(self):

        self.linux = 'Linux' in platform()

        if self.linux:
            self.connection_type = 'mariadb+mariadbconnector'
            locale.setlocale(locale.LC_TIME, 'nl_NL.utf8')
            self.pretty_date_format = '%-d %B %Y'
        else:
            self.connection_type = 'mysql+pymysql'
            locale.setlocale(locale.LC_TIME, 'nl_NL')
            self.pretty_date_format = '%#d %B %Y'

        self.mysql_user =  os.environ['SQLALCHEMY_URI_SECRETS_USER']
        self.mysql_pwd =  os.environ['SQLALCHEMY_URI_SECRETS_PWD']
        self.mysql_host =  os.environ['SQLALCHEMY_URI_SECRETS_HOST']
        self.mysql_db = os.environ['SQLALCHEMY_URI_SECRETS_DB']

    def app_init(self,app):

        app.config[
            'SQLALCHEMY_DATABASE_URI'] = f"{self.connection_type}://{self.mysql_user}:{self.mysql_pwd}@{self.mysql_host}/{self.mysql_db}"
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 10,
            'pool_recycle': 60,
            'pool_pre_ping': True
        }

        app.config['SECRET_KEY'] = os.environ['SHOPPING_LIST_SECRET_KEY']
        app.config['TIME_TO_EXPIRE'] = 3600 * 7

        return app