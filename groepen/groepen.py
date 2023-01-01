# from app import db, Product_record
# from flask import Flask, flash, render_template, g, request, redirect, url_for, session, Blueprint
# from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import UniqueConstraint, or_, exc, and_,not_

from flask import  Blueprint, request, flash, render_template
from flask_login import login_required,current_user
from database import Product_record, Groep_record, db
import urllib

groepen_route = Blueprint('groepen', __name__, template_folder='templates')

@groepen_route.route('/groepen', methods=['POST', 'GET'])
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

        return render_template('toevoegen_groepen.html', current_user=current_user, groepen=groepen,
                               url_param=active_date)

@groepen_route.route('/verwijder-groep', methods=['POST', 'GET'])
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

@groepen_route.route('/artikelen-in-groepen', methods=['POST', 'GET'])
@login_required
def artikelen_in_groepen():

    artikelen = Product_record.query.filter_by(gebruiker=current_user.idi).order_by('omschrijving').all()

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

    return render_template('groepen.html', current_user=current_user, artikelen=artikelen, groep=groep_record,
                           groep_artikelen=groep_artikelen, groep_artikelen_ids=groep_artikelen_ids,
                           url_param=active_date)

@groepen_route.route('/save-groep', methods=['POST'])
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

