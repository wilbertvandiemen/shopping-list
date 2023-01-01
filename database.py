import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, or_, exc, and_,not_
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
from config_ import config_

load_dotenv()

config_= config_()

if config_.linux:
    import mariadb
else:
    import mysql.connector

db = SQLAlchemy()

def check_if_db_exists():

    retries = 5
    while retries > 0:

        try:

            if config_.linux:
                db =  mariadb.connect(
                  host=config_.mysql_host,
                  user=config_.mysql_user,
                  password=config_.mysql_pwd
                )
            else:
                db = mysql.connector.connect(
                  host=config_.mysql_host,
                  user=config_.mysql_user,
                  password=config_.mysql_pwd
                )

            retries = -1
        except:
            retries = retries - 1

    if retries != -1:
        return False

    db_cursor = db.cursor()

    try:
      db_cursor.execute(f"CREATE DATABASE {config_.mysql_db}")
    except:
      pass

    return True

def open_db_connection():

    if config_.linux:

        connection = mariadb.connect(
            host=config_.mysql_host,
            user=config_.mysql_user,
            password=config_.mysql_pwd,
            database=config_.mysql_db
        )

    else:

        connection = mysql.connector.connect(
            host=config_.mysql_host,
            user=config_.mysql_user,
            password=config_.mysql_pwd,
            database=config_.mysql_db
        )


    return connection

def close_db_connection(connection):
    connection.close()

class Gebruiker_record(UserMixin, db.Model):

    __tablename__ = 'gebruiker'

    idi = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(75), nullable=False, unique=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)
    validation_key = db.Column(db.String(256))
    validation_date = db.Column(db.String(12))
    password_recovery = db.Column(db.String(256))
    pwd_recovery_date = db.Column(db.String(12))
    session_token = db.Column(db.String(200), unique=True)

    # aangemaakte artikelen voor gebruiker
    producten = db.relationship('Product_record', backref='gebruiker_record')
    datums = db.relationship('Datum_record', backref='gebruiker_record')



    def get_id(self):
        # print(f"In get_id: {self.session_token}")
        return self.session_token

    def get_default_org(self):
        org = Organisatie_record.query.filter_by(gebruiker=self.idi, standaard=1).first()
        return org.id


class Datum_record(db.Model):

    __tablename__ = 'datum'

    id = db.Column(db.Integer, primary_key=True)
    datum = db.Column(db.String(8), nullable=False)
    gebruiker = db.Column(db.Integer, db.ForeignKey('gebruiker.idi'), nullable=False)

    UniqueConstraint(datum, gebruiker, name='datum_gebruiker')

    # gebruiker_record = db.relationship('Gebruiker', back_populates='datum')
    bestellingen = db.relationship('Datum_product_record', backref='datum_record')

    def bestellingen_ordered(self):
        if current_user and current_user.is_authenticated:

            connection = open_db_connection()

            cursor = connection.cursor(dictionary=True)

            # print(f"id = {self.id} en gebruiker id = {current_user.idi}")
            sql = """select datum.datum as str_datum, datum_product.id as dp_id, p.id as product_id, p.omschrijving as omschrijving, datum_product.gevonden, datum_product.datum 
                                from datum_product 
                                inner join datum on datum.id = datum_product.datum 
                                inner join product p on p.id = datum_product.product
                                where datum_product.datum = %s and datum.gebruiker = %s
                                order by p.volgorde, p.omschrijving"""

            cursor.execute(sql, (self.id, current_user.idi) )
            result = cursor.fetchall()

            # print(result)

            cursor.close()
            close_db_connection(connection)

            return result
        else:
            return []


class Product_record(db.Model):

    __tablename__ = 'product'

    id = db.Column(db.Integer, primary_key=True)
    gebruiker = db.Column(db.Integer, db.ForeignKey('gebruiker.idi'), nullable=False)
    omschrijving = db.Column(db.String(256), nullable=False)
    volgorde = db.Column(db.Integer, nullable=False, default=0)
    organisatie = db.Column(db.Integer, db.ForeignKey('organisatie.id'))

    UniqueConstraint(gebruiker, omschrijving, name='gebruiker_product')

    # gebruiker_record = db.relationship('Gebruiker', back_populates='Product')
    datum_producten = db.relationship('Datum_product_record', backref='product_record')


class Datum_product_record(db.Model):

    __tablename__ = 'datum_product'

    id = db.Column(db.Integer, primary_key=True)
    datum = db.Column(db.Integer, db.ForeignKey('datum.id'), nullable=False)
    product = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    gevonden =  db.Column(db.Integer, nullable=False, default=0)


class Groep_record(db.Model):
    __tablename__ = 'groep'

    id = db.Column(db.Integer, primary_key=True)
    omschrijving = db.Column(db.String(32), nullable=False)
    gebruiker = db.Column(db.Integer, db.ForeignKey('gebruiker.idi'), nullable=False)
    artikelen = db.Column(db.String(60))

    UniqueConstraint(omschrijving, gebruiker, name='omschrijving_gebruiker')

    def getProductRecords(self):
        result = []
        if self.artikelen:
            artikelen_ids = self.artikelen.split(",")
            for id in artikelen_ids:
                product = Product_record.query.filter_by(id=id).first()
                if product:
                    result.append(product)

        return result

class Organisatie_record(db.Model):
    __tablename__ = 'organisatie'

    id = db.Column(db.Integer, primary_key=True)
    omschrijving = db.Column(db.String(32), nullable=False)
    gebruiker = db.Column(db.Integer, db.ForeignKey('gebruiker.idi'), nullable=False)
    standaard = db.Column(db.Boolean, default = False, nullable=False)

    UniqueConstraint(omschrijving, gebruiker, name='organisatie_gebruiker')
