# from app import db, Product_record
# from flask import Flask, flash, render_template, g, request, redirect, url_for, session, Blueprint
# from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import or_

from flask import Blueprint, request, flash, render_template, redirect, url_for
from flask_login import login_required, current_user, login_user, logout_user
from database import Gebruiker_record, db

from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email, EmailNotValidError

from itsdangerous import URLSafeTimedSerializer
import os
from dotenv import load_dotenv

import smtplib
from urllib.parse import urlparse, urljoin
from datetime import datetime

import secrets

load_dotenv()

gebruikers_route = Blueprint('gebruikers', __name__, template_folder='templates')

serializer = URLSafeTimedSerializer(os.environ['SHOPPING_LIST_SECRET_KEY'])


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@gebruikers_route.route('/register', methods=['GET', 'POST'])
def register():
    # 0 = volledige naam, 1 = email, 2 = username, 3 = password
    form_validation = [["", ""], ["", ""], ["", ""], ["", ""]]

    if request.method == 'POST':

        gebruiker = Gebruiker_record.query.filter(or_(Gebruiker_record.username == request.form['username'],
                                                      Gebruiker_record.email == request.form['email'])).first()

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

        if request.form['email'].strip() == '' or not is_valid_email_address(request.form['email']):
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

            db.session.add(gebruiker)
            db.session.commit()

            verzend_email_confirmation_email(gebruiker.idi)

            flash("Check je mailbox voor een e-mail waarmee je je e-mailadres kunt bevestigen.")

            return redirect(url_for('gebruikers.login'))

    return render_template('register.html', user=current_user, fv=form_validation)


@gebruikers_route.route('/login', methods=['GET', 'POST'])
def login():

    gebruiker = current_user

    form_validation = [["", ""], ["", ""]]

    if request.method == 'POST':

        name = request.form['name']
        password = request.form['password']

        gebruiker = Gebruiker_record.query.filter_by(username=name, validation_key=None,
                                                     validation_date=None).first()

        if gebruiker:

            if check_password_hash(gebruiker.password, password):

                session_token = serializer.dumps([gebruiker.username, gebruiker.password])
                gebruiker.session_token = session_token
                db.session.commit()

                # print("pwd correct")
                login_user(gebruiker, remember=True)
                if 'next' in request.args:
                    next_ = request.args['next']
                    if not is_safe_url(next_):
                        return redirect(url_for('index'))

                    return redirect(next_)

                return redirect(url_for('index'))
            else:
                # print("pwd incorrect")
                form_validation[1] = ['is-invalid', 'The password is incorrect.']
        else:
            # print("name incorrect")
            form_validation[0] = ['is-invalid', 'The name is incorrect.']

    # print(form_validation[0])
    return render_template('login.html', user=gebruiker, fv=form_validation)


@gebruikers_route.route('/confirm/', defaults={'confirm': ""}, methods=['GET'])
@gebruikers_route.route('/confirm/<string:confirm>', methods=['GET'])
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
        return redirect(url_for('gebruikers.login'))

    # check de datum van de validatielink yyyymmddhhuu
    datum = gebruiker.validation_date

    if not datum:
        flash('Gebruiker reeds bevestigd')
        return redirect(url_for('gebruikers.login'))

    date = datetime.strptime(datum, "%Y%m%d%H%M")

    # 2 uur
    max_minutes = 60 * 2

    age = (datetime.now() - date).total_seconds() / 60.0

    # print(age)

    if age > max_minutes:
        flash('Bevestigings link is maximaal 2 uur geldig')
        return redirect(url_for('gebruikers.login'))

    # return "Alles OK - gebruiker aktiveren"

    gebruiker.validation_key = None
    gebruiker.validation_date = None

    db.session.commit()

    flash('E-mailadres is bevestigd. U kunt nu inloggen')
    return redirect(url_for('gebruikers.login'))

@gebruikers_route.route('/new-pwd/', methods=['GET', 'POST'])
def new_pwd():
    # twee parameters in url
    id = request.args['id']
    token = request.args['token']

    form_validation = [["", ""]]

    gebruiker = Gebruiker_record.query.filter_by(idi=id, password_recovery=token).first()

    if not gebruiker:
        flash('Onjuiste of verlopen wachtwoord herstel link')
        return redirect(url_for('gebruikers.login'))

    # check de datum van de validatielink yyyymmddhhuu
    datum = gebruiker.pwd_recovery_date

    if not datum:
        flash('Deze wachtwoord herstel link is al eerder gebruikt')
        return redirect(url_for('gebruikers.login'))

    date = datetime.strptime(datum, "%Y%m%d%H%M")

    # 2 uur
    max_minutes = 60 * 2

    age = (datetime.now() - date).total_seconds() / 60.0

    # print(age)

    if age > max_minutes:
        flash('Deze wachtwoord herstel link is maximaal 2 uur geldig')
        return redirect(url_for('gebruikers.login'))

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
        return redirect(url_for('gebruikers.login'))

    return render_template('herstel_wachtwoord.html', fv=form_validation)

@gebruikers_route.route('/pw_recovery/', methods=['GET', 'POST'])
def pw_recovery():

    errors = False
    form_validation = [["", ""]]

    if request.method == "POST":

        email = request.form['email'].strip()

        if email == '' or not is_valid_email_address(email):
            errors = True
            form_validation[0] = ['is-invalid', 'E-mailadres ontbreekt of onjuist']
        else:

            existing_user = Gebruiker_record.query.filter_by(email=email, validation_key=None,
                                                             validation_date=None).first()

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

    gebruiker = Gebruiker_record.query.filter_by(idi=id).first()
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

@gebruikers_route.route('/logout')
@login_required
def logout():

    current_user.session_token = None
    db.session.commit()

    logout_user()

    flash('Je bent nu uitgelogd')

    form_validation = [["", ""], ["", ""]]

    return render_template('login.html', user=None, fv=form_validation)


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