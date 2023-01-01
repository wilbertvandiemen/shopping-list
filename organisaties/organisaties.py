# from app import db, Product_record
# from flask import Flask, flash, render_template, g, request, redirect, url_for, session, Blueprint
# from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import UniqueConstraint, or_, exc, and_,not_

from flask import  Blueprint, request, flash, render_template
from flask_login import login_required,current_user
from database import Product_record, Organisatie_record, db
import urllib

organisaties_route = Blueprint('organisaties', __name__, template_folder='templates')


@organisaties_route.route('/organisaties', methods=['POST', 'GET'])
@login_required
def organisaties():

    user = current_user
    active_date = request.args['d']

    if request.method == 'POST':

        name = request.form['organisatie'].capitalize().strip()

        if name != '':
            try:
                org = Organisatie_record()
                org.gebruiker = user.idi
                org.omschrijving = name
                db.session.add(org)
                db.session.commit()

            except exc.IntegrityError:
                db.session.rollback()
                flash('Je kunt een organisatie slechts eenmaal toevoegen')


    orgs = Organisatie_record.query.filter_by(gebruiker=current_user.idi).order_by("omschrijving").all()

    # print(groepen)

    return render_template('toevoegen_organisaties.html', current_user=current_user, organisaties=orgs, url_param=active_date)

# ajax routine
@organisaties_route.route('/verwijder-organisatie', methods=['POST'])
def verwijder_organisatie():
    """ Hiermee verwijder je een organisatie van de gebruiker en plaats
        de bij de gebruiker horende producten in de organisatie algemeen
    """

    if not current_user.is_authenticated:
        return "3"

    id = request.form['id']

    #  eerst product record ophalen
    organisatie = Organisatie_record.query.filter_by(id=id, gebruiker=current_user.idi).first()
    # print(groep.omschrijving)
    if organisatie:
        if organisatie.standaard != 0:
            # wat is de standaard voor deze gebruiker
            standaard = current_user.standaard()
            #  zoek artikelen met deze organisatie
            artikelen = Product_record.query.filter_by(gebruiker=current_user.idi, organisatie=organisatie.id).all()
            for artikel in artikelen:
                artikel.organisatie = standaard
                db.session.commit()

            db.session.delete(organisatie)
            db.session.commit()

    return "1"

# ajax routine
@organisaties_route.route('/wijzig-organisatie', methods=['POST'])
def wijzig_organisatie():
    """ Hiermee pas je de naam van een organisatie van de gebruiker aan """

    if not current_user.is_authenticated:
        return "3"

    id = request.form['id']
    naam = ''
    if 'naam' in request.form:
        naam = request.form['naam'].strip()

    if len(naam):
        #  eerst organisatie record ophalen
        organisatie = Organisatie_record.query.filter_by(id=id, gebruiker=current_user.idi).first()
        organisatie.omschrijving = naam
        db.session.commit()

    return "1"

