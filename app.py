from flask import Flask, flash, render_template, g, request, redirect, url_for, session, send_from_directory, json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, or_, exc, and_,not_
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired

from datetime import datetime
from database import check_if_db_exists, open_db_connection, close_db_connection

import locale
from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email, EmailNotValidError

import smtplib

from fpdf import FPDF
from sendpdf import verzend_email

import os
from platform import platform

from dotenv import load_dotenv

import secrets
import urllib

load_dotenv()

linux = 'Linux' in platform()

if linux:
    connection_type = 'mariadb+mariadbconnector'
else:
    connection_type = 'mysql+pymysql'

if not check_if_db_exists():
    exit()

app = Flask(__name__)

mysql_user =  os.environ['SQLALCHEMY_URI_SECRETS_USER']
mysql_pwd =  os.environ['SQLALCHEMY_URI_SECRETS_PWD']
mysql_host =  os.environ['SQLALCHEMY_URI_SECRETS_HOST']
mysql_db = os.environ['SQLALCHEMY_URI_SECRETS_DB']

app.config['SQLALCHEMY_DATABASE_URI'] = f"{connection_type}://{ mysql_user }:{ mysql_pwd }@{mysql_host}/{mysql_db}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 60,
    'pool_pre_ping': True
}

app.config['SECRET_KEY'] = os.environ['SHOPPING_LIST_SECRET_KEY']
app.config['TIME_TO_EXPIRE'] = 3600*7

db = SQLAlchemy(app)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = 'login'
login_manager.login_message = 'Voor deze aktie moet je ingelogd zijn'

serializer = URLSafeTimedSerializer(app.secret_key)

linux = 'Linux' in platform()

if linux:
    locale.setlocale(locale.LC_TIME, 'nl_NL.utf8')
    pretty_date_format = '%-d %B %Y'
else:
    locale.setlocale(locale.LC_TIME, 'nl_NL')
    pretty_date_format = '%#d %B %Y'

class PDF(FPDF):
    def lines(self):
        self.rect(5.0, 5.0, 200.0, 287.0)
        # self.rect(8.0, 8.0, 194.0, 282.0)


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
                result.append(Product_record.query.filter_by(id=id).first())

        return result

@login_manager.user_loader
def load_user(session_token):

    # print(f"In load_user 1: {session_token}")
    user = Gebruiker_record.query.filter_by(session_token=session_token).first()
    if not user:
        return None

    # print(f"In load_user uit user record: {user.session_token}")
    try:
        serializer.loads(session_token, max_age=app.config['TIME_TO_EXPIRE'])
    except SignatureExpired:
        user.session_token = None
        db.session.commit()
        return None

    return user


def is_valid_email_address(email_address):
    """
    Check that the string specified appears to be a valid email address.
    :param str email_address: The email address to validate.
    :return: Whether the email address appears to be valid or not.
    :rtype: bool
    """

    if email_address is None:
        return False
    try:
        validate_email(email_address, allow_empty_local=False, check_deliverability=False)
    except EmailNotValidError:
        return False
    return True


default_date = datetime.now()
default_date_url_parameter = datetime.strftime(default_date, '%Y%m%d')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


# @app.route('/', defaults={'active_date': default_date_url_parameter}, methods=['POST', 'GET'])
# @app.route('/<active_date>', methods=['POST', 'GET'])
@app.route('/', methods=['POST', 'GET'])
@login_required
def index():
    def get_omschrijving(artikel):
        return artikel.get('omschrijving')

    user = current_user

    if 'd' in  request.args:
        active_date = request.args['d']
    else:
        active_date = default_date_url_parameter

    artikelen_gebruiker = Product_record.query.filter_by(gebruiker=current_user.idi).all()
    select_items = []
    for artikel in artikelen_gebruiker:
        select_items.append({'id':artikel.id, 'omschrijving':artikel.omschrijving})

    groepen = Groep_record.query.filter_by(gebruiker=current_user.idi).all()
    for groep in groepen:
        if groep.artikelen != None:
            select_items.append({'id':-groep.id, 'omschrijving':groep.omschrijving})

    select_items.sort(key=get_omschrijving)

    try:
        date = datetime.strptime(active_date, '%Y%m%d')
    except ValueError:
        flash('Ongeldige datum. Gebruik yyyymmdd. Huidige datum gebruikt.')
        pretty_date = datetime.strftime(default_date, pretty_date_format)
        return redirect(url_for('index', d=default_date_url_parameter))

    # bestaat datum record al?
    datum_record = Datum_record.query.filter_by(datum=active_date, gebruiker=user.idi).first()

    if datum_record:
        datum_id = datum_record.id
    else:
        datum_record = Datum_record()
        datum_record.datum = active_date
        datum_record.gebruiker = user.idi

        db.session.add(datum_record)
        db.session.commit()

        datum_id = datum_record.id

    # welke producten zijn reeds gekozen
    ids = collect_reeds_gekozen_ids(datum_id)
    # print(ids)
    reeds_gekozen = collect_reeds_gekozen(datum_id)

    if request.method == 'POST':

        selected = int(request.form['select_artikel'])

        if selected < 0:
            groep = Groep_record.query.filter_by(id=abs(selected)).first()
            items = groep.artikelen.split(',')
            for item in items:
                # print(int(item))
                # print(ids)
                if int(item) not in ids:
                    datum_product = Datum_product_record()
                    datum_product.datum = datum_id
                    datum_product.product = int(item)

                    db.session.add(datum_product)
                    db.session.commit()

        else:

           if selected not in ids:
                try:
                    datum_product = Datum_product_record()
                    datum_product.datum = datum_id
                    datum_product.product = selected

                    db.session.add(datum_product)
                    db.session.commit()

                except:
                    db.session.rollback()
                    flash('Je kunt een artikel per dag slechts eenmaal toevoegen')
                    pretty_date = datetime.strftime(date, '%#d %B %Y')
                    return render_template("index.html", datum=pretty_date,
                                           artikelen=select_items,
                                           reeds_gekozen=reeds_gekozen,
                                           datum_id=datum_id,
                                           url_param=active_date,
                                           current_user=user)

    reeds_gekozen = collect_reeds_gekozen(datum_id)

    pretty_date = datetime.strftime(date, pretty_date_format)
    return render_template(
                                "index.html",
                                datum=pretty_date,
                                artikelen=select_items,
                                url_param=active_date,
                                reeds_gekozen=reeds_gekozen,
                                datum_id=datum_id,
                                current_user=user)


@app.route('/toevoegen', methods=['POST', 'GET'])
@login_required
def toevoegen():

    user = current_user
    active_date = request.args['d']

    if request.method == 'POST':

        name = request.form['product'].capitalize().strip()

        if name != '':
            try:
                product = Product_record()
                product.gebruiker = user.idi
                product.omschrijving = name
                db.session.add(product)
                db.session.commit()

            except exc.IntegrityError:
                db.session.rollback()
                flash('Je kunt een artikel slechts eenmaal toevoegen')

    results = Product_record.query.filter_by(gebruiker=current_user.idi).order_by("volgorde", "omschrijving").all()

    return render_template('toevoegen.html', results=results, current_user=user, url_param=active_date)


@app.route('/groepen', methods=['POST', 'GET'])
@login_required
def groepen():

    user = current_user
    active_date = request.args['d']

    if request.method == 'POST':

        name = request.form['groep'].capitalize().strip()

        if name != '':
            try:
                groep = Groep_record()
                groep.gebruiker = user.idi
                groep.omschrijving = name
                db.session.add(groep)
                db.session.commit()

            except exc.IntegrityError:
                db.session.rollback()
                flash('Je kunt een groep slechts eenmaal toevoegen')


    groepen = Groep_record.query.filter_by(gebruiker=current_user.idi).order_by("omschrijving").all()

    # print(groepen)

    return render_template('toevoegen_groepen.html', current_user=current_user, groepen=groepen, url_param=active_date)

@app.route('/verwijder-groep', methods=['POST', 'GET'])
def verwijder_groep():
    """ Hiermee verwijder je een artikel van de gebruiker en de bijbehorende bestellingen """

    if not current_user.is_authenticated:
        return "3"

    id = request.form['id']

    #  eerst product record ophalen
    groep = Groep_record.query.filter_by(id=id, gebruiker=current_user.idi).first()
    # print(groep.omschrijving)
    if groep:
        db.session.delete(groep)
        db.session.commit()

    return "1"

@app.route('/artikelen-in-groepen', methods=['POST', 'GET'])
@login_required
def artikelen_in_groepen():

    artikelen = Product_record.query.filter_by(gebruiker=current_user.idi).all()

    groep = request.args['id']

    # print(groep)

    groep_record = Groep_record.query.filter_by(id=groep).first()

    # print(groep_record)

    groep_artikelen = groep_record.getProductRecords()
    if groep_artikelen:
        groep_artikelen_ids = groep_record.artikelen.split(',')
        groep_artikelen_ids = [int(item) for item in groep_artikelen_ids]
    else:
        groep_artikelen_ids = []

    # print(groep_artikelen_ids)

    active_date = request.args['d']

    return render_template('groepen.html', current_user=current_user, artikelen=artikelen, groep=groep_record, groep_artikelen=groep_artikelen, groep_artikelen_ids = groep_artikelen_ids, url_param=active_date)

@app.route('/save-groep', methods=['POST'])
def save_groep():

    if not current_user.is_authenticated:
        return "3"

    # print(request.json)

    data = request.json
    artikelen = data['data']
    reeks = []
    for artikel in artikelen:
        reeks.append(str(artikel['id']))

    # print(reeks)
    # print(current_user.idi)

    groep = Groep_record.query.filter_by(id=data['groep'], gebruiker=current_user.idi).first()
    groep.artikelen = ",".join(reeks)
    db.session.commit()

    return "1"


# AJAX route
@app.route('/update_status', methods=['POST'])
def update_status():

    if not current_user.is_authenticated:
        return "3"

    status = request.form['status']

    if status == "0":
        nieuwe_status = 1
    else:
        nieuwe_status = 0

    id = request.form['id']

    datum_product = Datum_product_record.query.filter_by(id=id).first()
    if datum_product:
        # print('gevonden')
        datum_product.gevonden = nieuwe_status
        db.session.commit()

    return "1"


# AJAX route
@app.route('/delete', methods=['POST'])

def delete():

    if not current_user.is_authenticated:
        return "3"

    datum_product = Datum_product_record.query.filter_by(id=request.form['id']).first()

    if datum_product:
        db.session.delete(datum_product)
        db.session.commit()

    return "1"

# AJAX route
@app.route('/reorder', methods=['POST'])
def reorder():

    if not current_user.is_authenticated:
        return '2'

    content = eval(urllib.parse.unquote(request.data))
    teller = 0
    for item in content:
        produkt = Product_record.query.filter_by(id=item['id']).first()
        if produkt and produkt.gebruiker == current_user.idi:
            teller +=1
            produkt.volgorde = teller
            db.session.commit()

    return '1'

# AJAX route
@app.route('/verwijder_artikel', methods=['POST'])
def verwijder_artikel():
    """ Hiermee verwijder je een artikel van de gebruiker en de bijbehorende bestellingen """

    if not current_user.is_authenticated:
        return '2'

    id = request.form['id']

    #  eerst product record ophalen
    artikel = Product_record.query.filter_by(id=id, gebruiker=current_user.idi).first()
    if artikel:
        # eventuele bestellingen met dit product
        artikel_bestellingen = Datum_product_record.query.filter_by(product=id).all()

        for bestelling in artikel_bestellingen:
            db.session.delete(bestelling)
            db.session.commit()

        db.session.delete(artikel)
        db.session.commit()

    return "1"

# AJAX route
@app.route('/pdfmailen', methods=["POST"])
def pdfmailen():

    if not current_user.is_authenticated:
        return "2"

    datum = request.form['datum']
    if datum == None or datum == "":
        return "2"



    boodschappen = collect_reeds_gekozen(datum)

    if boodschappen:
        gekozen_datum = boodschappen[0]['str_datum']
        date = datetime.strptime(gekozen_datum, '%Y%m%d')
        pretty_date = datetime.strftime(date, '%#d %B %Y')

    else:
        return "9"

    # variable pdf
    pdf = PDF()

    pdf.add_font('DejaVu', '', 'dejavu-fonts/ttf/DejaVuSansCondensed.ttf', True)

    # Add a page
    pdf.add_page()
    pdf.set_margin(20)
    # set style and size of font
    # that you want in the pdf
    pdf.set_font("Helvetica", size=18)
    pdf.set_text_color(0, 0, 0)

    pdf.cell(w=0, h=14, align='C', txt=f"Boodschappenlijstje { current_user.fullname }")
    pdf.ln()
    pdf.set_font("Helvetica", size=14)
    pdf.cell(w=0, h=18, align='C', txt=f"d.d. {pretty_date} ")
    pdf.ln()
    pdf.ln()

    pdf.set_font("Arial", size=15)

    for artikel in boodschappen:
        # pdf.cell(w=10, h=8, txt=str(artikel['gevonden']) )
        if artikel['gevonden'] == 1:
            pdf.set_font('DejaVu', size=20)
            pdf.cell(w=10, h=8, txt=u"✓")
            pdf.set_font("Arial", size=15)

        else:
            pdf.cell(w=10, h=8, txt="")

        pdf.cell(40, 8, artikel['omschrijving'])
        pdf.ln()

    pdf.lines()
    pdf.image('images/IMG_0022.JPG', 50, 200, 100)
    # save the pdf with name .pdf
    pdf.output(f"boodschappen-{ current_user.idi }.pdf")

    verzend_email(current_user)

    return "1"


# support function
def collect_reeds_gekozen(datum_id):

    user = current_user
    datum_record = Datum_record.query.filter_by(id=datum_id).first()

    # sql_reeds_gekozen = """select data.datum as str_datum, datum_product.id as dp_id, p.omschrijving, datum_product.gevonden, datum_product.datum
    #                         from datum_product
    #                         inner join data on data.id = datum_product.datum
    #                         inner join producten p on p.id = datum_product.product
    #                         where datum_product.datum = ? and data.user = ?
    #                         order by p.omschrijving"""

    artikelen_gekozen = datum_record.bestellingen_ordered()

    gekozen_array = []
    i = 0
    for item in artikelen_gekozen:
        box = 'checkbox-blank'
        # print(item['gevonden'])
        if item['gevonden'] == 1:
            box = 'checkbox'
        i = i + 1
        gekozen_array.append({
            'dp_id': item['dp_id'],
            'datum': item['datum'],
            'str_datum': item['str_datum'],
            'nummer': i,
            'omschrijving': item['omschrijving'],
            'box': box,
            'gevonden': item['gevonden']}
        )

    return gekozen_array

def collect_reeds_gekozen_ids(datum_id):

    user = current_user
    datum_record = Datum_record.query.filter_by(id=datum_id).first()

    artikelen_gekozen = datum_record.bestellingen_ordered()

    gekozen_array = []
    for item in artikelen_gekozen:
        gekozen_array.append(item['product_id'])

    return gekozen_array


@app.route('/register', methods=['GET', 'POST'])
def register():
    # 0 = volledige naam, 1 = email, 2 = username, 3 = password
    form_validation = [["", ""], ["", ""], ["", ""], ["", ""]]

    if request.method == 'POST':

        gebruiker =  Gebruiker_record.query.filter(or_(Gebruiker_record.username == request.form['username'], Gebruiker_record.email ==  request.form['email'])).first()

        errors = False
        if gebruiker:
            form_validation[1] = ['is-invalid', 'E-mail en/of gebruikersnaam bestaat al']
            form_validation[2] = ['is-invalid', 'E-mail en/of gebruikersnaam bestaat al']
            errors = True

        if request.form['fullname'].strip() == '':
            errors = True
            form_validation[0] = ['is-invalid', 'Volledige naam ontbreekt']

        password = request.form['password'].strip()
        if len(password) < 8:
            errors = True
            form_validation[3] = ['is-invalid', 'Password moet minimaal 8 karakters lang zijn']

        if request.form['email'].strip() == '' or is_valid_email_address(request.form['email']) == False:
            errors = True
            form_validation[1] = ['is-invalid', 'E-mailadres ontbreekt of onjuist']

        if not errors:
            hashed_password = generate_password_hash(password, method='sha256')

            gebruiker = Gebruiker_record()
            gebruiker.fullname = request.form['fullname']
            gebruiker.username = request.form['username']
            gebruiker.password = hashed_password
            gebruiker.email = request.form['email'].strip()
            gebruiker.session_token = serializer.dumps([request.form['username'], hashed_password])

            # cur = db.execute('insert into users (fullname, username, password, email) values (?, ?, ?, ?)',
            #                  [request.form['fullname'], request.form['username'], hashed_password,
            #                   request.form['email'].strip()])
            # db.commit()

            # session['user'] = request.form['name']

            db.session.add(gebruiker)
            db.session.commit()

            verzend_email_confirmation_email(gebruiker.idi)

            flash("Check je mailbox voor een e-mail waarmee je je e-mailadres kunt bevestigen.")

            return redirect(url_for('login'))

    return render_template('register.html', user=current_user, fv=form_validation)


@app.route('/login', methods=['GET', 'POST'])
def login():

    gebruiker = current_user

    form_validation = [["", ""], ["", ""]]

    if request.method == 'POST':

        name = request.form['name']
        password = request.form['password']

        gebruiker = Gebruiker_record.query.filter_by(username=name, validation_key=None, validation_date=None ).first()

        if gebruiker:

            if check_password_hash(gebruiker.password, password):

                session_token = serializer.dumps([gebruiker.username, gebruiker.password])
                gebruiker.session_token = session_token
                db.session.commit()

                # print("pwd correct")
                login_user(gebruiker, remember=True)
                return redirect(url_for('index'))
            else:
                # print("pwd incorrect")
                form_validation[1] = ['is-invalid', 'The password is incorrect.']
        else:
            # print("name incorrect")
            form_validation[0] = ['is-invalid', 'The name is incorrect.']

    # print(form_validation[0])
    return render_template('login.html', user=gebruiker, fv=form_validation)


@app.route('/confirm/', defaults={'confirm': ""}, methods=['GET'])
@app.route('/confirm/<string:confirm>', methods=['GET'])
def confirm(confirm):

    if current_user.is_authenticated:
        flash('U bent reeds ingelogd')
        return redirect(url_for('index'))

    # confirm zonder validatie sleutel
    if confirm == "":
        flash('Onjuiste bevestigings e-mail link')
        return redirect(url_for('login'))

    gebruiker = Gebruiker_record.query.filter_by(validation_key=confirm).first()

    if not gebruiker:
        flash('Onjuiste of verlopen bevestigingslink')
        return redirect(url_for('login'))

    # check de datum van de validatielink yyyymmddhhuu
    datum = gebruiker.validation_date

    if not datum:
        flash('Gebruiker reeds bevestigd')
        return redirect(url_for('login'))

    date = datetime.strptime(datum, "%Y%m%d%H%M")

    # 2 uur
    max_minutes = 60 * 2

    age = (datetime.now() - date).total_seconds() / 60.0

    # print(age)

    if age > max_minutes:
        flash('Bevestigings link is maximaal 2 uur geldig')
        return redirect(url_for('login'))

    # return "Alles OK - gebruiker aktiveren"

    gebruiker.validation_key = None
    gebruiker.validation_date = None

    db.session.commit()

    flash('E-mailadres is bevestigd. U kunt nu inloggen')
    return redirect(url_for('login'))


@app.route('/new-pwd/', methods=['GET', 'POST'])
def new_pwd():
    # twee parameters in url
    id = request.args['id']
    token = request.args['token']

    form_validation = [["", ""]]

    gebruiker = Gebruiker_record.query.filter_by(idi=id, password_recovery = token).first()

    if not gebruiker:
        flash('Onjuiste of verlopen wachtwoord herstel link')
        return redirect(url_for('login'))

    # check de datum van de validatielink yyyymmddhhuu
    datum = gebruiker.pwd_recovery_date

    if not datum:
        flash('Deze wachtwoord herstel link is al eerder gebruikt')
        return redirect(url_for('login'))

    date = datetime.strptime(datum, "%Y%m%d%H%M")

    # 2 uur
    max_minutes = 60 * 2

    age = (datetime.now() - date).total_seconds() / 60.0

    # print(age)

    if age > max_minutes:
        flash('Deze wachtwoord herstel link is maximaal 2 uur geldig')
        return redirect(url_for('login'))

    # everything fine, now proces post
    if request.method == 'POST':

        form_validation = [["", ""]]

        password1 = request.form['password1']
        password2 = request.form['password2']

        if password1 != password2:
            form_validation[0] = ['is-invalid', 'De ingevoerde waarden zijn niet aan elkaar gelijk']
            return render_template('herstel_wachtwoord.html', fv=form_validation)

        if len(password1) < 8:
            form_validation[0] = ['is-invalid', 'Maak je wachtwoord minimaal 8 lang']
            return render_template('herstel_wachtwoord.html', fv=form_validation)

        hashed_password = generate_password_hash(password1, method='sha256')

        # alles ok, opslaan

        gebruiker.password = hashed_password
        gebruiker.password_recovery = None
        gebruiker.pwd_recovery_date = None

        db.session.commit()

        flash('Je wachtwoord is gewijzigd. Je kunt nu inloggen.')
        return redirect(url_for('login'))

    return render_template('herstel_wachtwoord.html', fv=form_validation)


@app.route('/pw_recovery/', methods=['GET', 'POST'])
def pw_recovery():

    errors = False
    form_validation = [["", ""]]

    if request.method == "POST":

        email = request.form['email'].strip()

        if email == '' or not is_valid_email_address(email):
            errors = True
            form_validation[0] = ['is-invalid', 'E-mailadres ontbreekt of onjuist']
        else:

            existing_user = Gebruiker_record.query.filter_by(email=email, validation_key = None, validation_date = None).first()

            if existing_user:
                verzend_pwd_recovery_email(existing_user.idi)
            else:
                pass
                # we verklappen niet dat dit e-mailadres niet bestaat in de app
                # dus geen foutmelding

        if not errors:
            user = current_user

            form_validation = [["", ""], ["", ""]]

            flash('Controleer je e-mail voor de herstellink')
            return render_template('login.html', user=user, fv=form_validation)

    return render_template('pw-recovery.html', fv=form_validation)


def verzend_email_confirmation_email(id):

    base_url = request.base_url
    temp_array = base_url.split('/')
    base_url = temp_array[0] + "//" + temp_array[2] + '/'

    token = secrets.token_urlsafe(32)

    confirmation_url = base_url + "confirm/" + token
    date = datetime.now().strftime('%Y%m%d%H%M')

    gebruiker = Gebruiker_record.query.filter_by(idi = id).first()
    gebruiker.validation_key = token
    gebruiker.validation_date = date

    db.session.commit()

    msg = "Subject: Verifieer je e-mailadres\r\n\r\n"
    msg = msg + f"""
        Hi {gebruiker.fullname},

        De boodschappenman hier.

        Je account wordt pas aktief als je je e-mailadres bevestigd.
        Dat kan door op deze link te klikken:

        {confirmation_url}

        Veel succes met de boodschappenlijst app!
    """

    sender_email_address = os.environ['SENDER_EMAIL_ADDRESS']
    sender_email_password = os.environ['SENDER_EMAIL_PASSWORD']

    mailto = gebruiker.email

    mailServer = smtplib.SMTP('smtp.gmail.com', 587)
    mailServer.starttls()
    mailServer.login(sender_email_address, sender_email_password)
    mailServer.sendmail(sender_email_address, mailto, msg)
    # print(" \n Sent!")
    mailServer.quit()


def verzend_pwd_recovery_email(id):

    base_url = request.base_url
    temp_array = base_url.split('/')
    base_url = temp_array[0] + "//" + temp_array[2] + '/'

    token = secrets.token_urlsafe(32)

    recovery_url = base_url + f"new-pwd?id={id}&token={token}"

    date = datetime.now().strftime('%Y%m%d%H%M')

    gebruiker = Gebruiker_record.query.filter_by(idi=id).first()
    gebruiker.password_recovery = token
    gebruiker.pwd_recovery_date = date

    db.session.commit()

    msg = "Subject: Je wachtwoord herstel link\r\n\r\n"
    msg = msg + f"""
            Hi {gebruiker.fullname},

            De boodschappenman hier.

            Door op deze link te klikken wordt je naar een pagina geleidt waar je een nieuw wachtwoord kunt invoeren:

            {recovery_url}

            Deze link is 2 uur geldig.

            Veel succes met de boodschappenlijst app!
        """

    sender_email_address = os.environ['SENDER_EMAIL_ADDRESS']
    sender_email_password = os.environ['SENDER_EMAIL_PASSWORD']

    mailto = gebruiker.email

    mailServer = smtplib.SMTP('smtp.gmail.com', 587)
    mailServer.starttls()
    mailServer.login(sender_email_address, sender_email_password)
    mailServer.sendmail(sender_email_address, mailto, msg)

    mailServer.quit()


@app.route('/logout')
@login_required
def logout():

    current_user.session_token = None
    db.session.commit()

    logout_user()

    flash('Je bent nu uitgelogd')

    form_validation = [["", ""], ["", ""]]

    return render_template('login.html', user=None, fv=form_validation)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')



# with app.app_context():
#     db.create_all()

