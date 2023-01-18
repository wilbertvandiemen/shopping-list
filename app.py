from flask import Flask, flash, render_template, g, request, redirect, url_for, session, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, or_, exc, and_,not_
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired

from datetime import datetime
from database import db, check_if_db_exists, open_db_connection, close_db_connection, Groep_record,Gebruiker_record,Organisatie_record,Product_record,Datum_record,Datum_product_record

import os

from fpdf import FPDF
from sendpdf import verzend_email

import secrets

from config_ import config_

from artikelen.artikelen import artikelen
from groepen.groepen import groepen_route
from organisaties.organisaties import organisaties_route
from gebruikers.gebruikers import gebruikers_route

app = Flask(__name__)
app.register_blueprint(artikelen)
app.register_blueprint(groepen_route)
app.register_blueprint(organisaties_route)
app.register_blueprint(gebruikers_route)

# config init
config_ = config_()

if not check_if_db_exists():
    exit()

app = config_.app_init(app=app)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = 'gebruikers.login'
login_manager.login_message = 'Log a.u.b. eerst in'

serializer = URLSafeTimedSerializer(app.secret_key)


class PDF(FPDF):
    def lines(self):
        self.rect(5.0, 5.0, 200.0, 287.0)
        # self.rect(8.0, 8.0, 194.0, 282.0)

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

    # check for default organisatie
    org = Organisatie_record.query.filter_by(gebruiker=user.idi, standaard=True).first()
    if not org:
        org = Organisatie_record()
        org.gebruiker = user.idi
        org.standaard = True
        org.omschrijving = 'Geen organisatie'

        db.session.add(org)
        db.session.commit()

    artikelen  = Product_record.query.filter_by(gebruiker=user.idi, organisatie=None)
    for artikel in artikelen:
        artikel.organisatie = org.id
        db.session.commit()

    return user


def get_default_date():
    default_date = datetime.now()
    return datetime.strftime(default_date, '%Y%m%d')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/', methods=['POST', 'GET'])
@login_required
def index():

    user = current_user

    if 'd' in  request.args:
        active_date = request.args['d']
    else:
        active_date = get_default_date()

    select_items_ = getSelect_items()
    # print(select_items_)

    try:
        date = datetime.strptime(active_date, '%Y%m%d')
    except ValueError:
        flash('Ongeldige datum. Gebruik yyyymmdd. Huidige datum gebruikt.')
        return redirect(url_for('index', d=active_date))

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

    organisaties = Organisatie_record.query.filter_by(gebruiker=current_user.idi).order_by(Organisatie_record.omschrijving)

    organisaties_selected = ''
    organisaties_selected_array = []

    if request.method == 'POST':

        selected = int(request.form['select_artikel'])

        organisaties_selected = request.form['orgs_selected'].strip()
        # print(organisaties_selected)

        if organisaties_selected != '':
            organisaties_selected_array = organisaties_selected.split(',')

        # print(organisaties_selected_array)
        if len(organisaties_selected_array):
            organisaties_selected_array = [int(item) for item in organisaties_selected_array]

        if organisaties_selected.strip() != '':
            select_items_ = [item for item in select_items_ if item['organisatie'] in organisaties_selected_array]

        # groep bijvoorbeeld `pasta`
        if selected < 0:
            groep = Groep_record.query.filter_by(id=abs(selected)).first()
            items = groep.artikelen.split(',')
            for item in items:
                # print(int(item))
                # print(ids)
                if int(item) not in ids:
                    try:
                        datum_product = Datum_product_record()
                        datum_product.datum = datum_id
                        datum_product.product = int(item)

                        db.session.add(datum_product)
                        db.session.commit()
                    except:
                        db.session.rollback()

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

                    # print(organisaties_selected_array)

                    return render_template("index.html", datum=pretty_date,
                                           artikelen=select_items_,
                                           reeds_gekozen=reeds_gekozen,
                                           datum_id=datum_id,
                                           url_param=active_date,
                                           current_user=user,
                                           organisaties=organisaties,
                                           organisaties_selected = organisaties_selected_array,
                                           hidden_input = organisaties_selected)

    reeds_gekozen = collect_reeds_gekozen(datum_id)

    pretty_date = datetime.strftime(date, config_.pretty_date_format)

    return render_template(
                                "index.html",
                                datum=pretty_date,
                                artikelen=select_items_,
                                url_param=active_date,
                                reeds_gekozen=reeds_gekozen,
                                datum_id=datum_id,
                                current_user=user,
                                organisaties=organisaties,
                                organisaties_selected = organisaties_selected_array,
                                hidden_input=organisaties_selected)



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


# ajax-route
@app.route('/update_select', methods=['POST'])
def update_select():
    if not current_user.is_authenticated:
        return "3"

    status = request.form['keuze'].split(',')
    # print(status)
    status_int = []
    if status != ['']:
        status_int = [int(item) for item in status]

    # print(status_int)

    all_select_items = getSelect_items()

    # artikelen = Product_record.query.filter_by(gebruiker=current_user.idi).order_by("volgorde", "omschrijving").all()

    return_arr = []
    for artikel in all_select_items:
        # print(artikel.organisatie)
        if status_int == [] or artikel['organisatie'] in status_int:
            return_arr.append({'id':artikel['id'], 'omschrijving': artikel['omschrijving']})


    return jsonify(return_arr)


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
        pretty_date = datetime.strftime(date, config_.pretty_date_format)

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

def get_omschrijving(artikel):
    return artikel.get('omschrijving')

def getSelect_items():

    # artikelen en groepen van gebruiker; groep met negatieve id
    select_items_ = []
    artikelen_gebruiker = Product_record.query.filter_by(gebruiker=current_user.idi).all()

    for artikel in artikelen_gebruiker:
        select_items_.append({'id': artikel.id, 'omschrijving': artikel.omschrijving, 'organisatie': artikel.organisatie})

    groepen = Groep_record.query.filter_by(gebruiker=current_user.idi).all()
    for groep in groepen:
        if groep.artikelen != None:
            select_items_.append({'id': -groep.id, 'omschrijving': groep.omschrijving, 'organisatie': -1})

    select_items_.sort(key=get_omschrijving)
    # print(select_items_)
    return select_items_

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')



# with app.app_context():
#     db.create_all()
