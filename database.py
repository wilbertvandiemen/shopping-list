from dotenv import load_dotenv

from platform import platform
import os

load_dotenv()

linux = 'Linux' in platform()

if linux:
    import mariadb
else:
    import mysql.connector

def check_if_db_exists():

    retries = 5
    while retries > 0:

        try:

            if linux:
                db =  mariadb.connect(
                  host=os.environ['SQLALCHEMY_URI_SECRETS_HOST'],
                  user=os.environ['SQLALCHEMY_URI_SECRETS_USER'],
                  password=os.environ['SQLALCHEMY_URI_SECRETS_PWD']
                )
            else:
                db = mysql.connector.connect(
                  host=os.environ['SQLALCHEMY_URI_SECRETS_HOST'],
                  user=os.environ['SQLALCHEMY_URI_SECRETS_USER'],
                  password=os.environ['SQLALCHEMY_URI_SECRETS_PWD']
                )

            retries = -1
        except:
            retries = retries - 1

    if retries != -1:
        return False

    db_cursor = db.cursor()

    try:
      db_cursor.execute(f"CREATE DATABASE {os.environ['SQLALCHEMY_URI_SECRETS_DB']}")
    except:
      pass

    return True

def open_db_connection():

    if linux:
        print("IsLinux")
        connection = mariadb.connect(
          host=os.environ['SQLALCHEMY_URI_SECRETS_HOST'],
          user=os.environ['SQLALCHEMY_URI_SECRETS_USER'],
          password=os.environ['SQLALCHEMY_URI_SECRETS_PWD'],
          database=os.environ['SQLALCHEMY_URI_SECRETS_DB']
        )

    else:
        print("IsWindows")
        connection = mysql.connector.connect(
          host=os.environ['SQLALCHEMY_URI_SECRETS_HOST'],
          user=os.environ['SQLALCHEMY_URI_SECRETS_USER'],
          password=os.environ['SQLALCHEMY_URI_SECRETS_PWD'],
          database=os.environ['SQLALCHEMY_URI_SECRETS_DB']
        )


    return connection

def close_db_connection(connection):
    connection.close()

