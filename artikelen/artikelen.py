# from app import db, Product_record
# from flask import Flask, flash, render_template, g, request, redirect, url_for, session, Blueprint
# from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import UniqueConstraint, or_, exc, and_,not_

from flask import  Blueprint, request, flash, render_template
from flask_login import login_required,current_user
from database import Product_record, Datum_product_record, db, Organisatie_record
import urllib

artikelen = Blueprint('artikelen', __name__, template_folder='templates')


@artikelen.route('/toevoegen', methods=['POST', 'GET'])
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

@artikelen.route('/bewerk-artikel', methods=['POST', 'GET'])
@login_required
def bewerk_artikel():
    # 0 = omschrijving
    form_validation = [["", ""]]

    id = request.args['id']
    active_date = request.args['d']

    #  eerst product record ophalen
    artikel = Product_record.query.filter_by(id=id, gebruiker=current_user.idi).first()

    if request.method == "POST":
        if request.form['omschrijving']:

            print(request.form['organisatie'])
            artikel.omschrijving = request.form['omschrijving'].strip()
            artikel.organisatie = request.form['organisatie']
            db.session.commit()

            results = Product_record.query.filter_by(gebruiker=current_user.idi).order_by("volgorde",
                                                                                          "omschrijving").all()

            return render_template('toevoegen.html', results=results, current_user=current_user, url_param=active_date)

        else:
            form_validation[0] = ['is-invalid', 'Een omschrijving is verplicht voor een product']

    # organisaties
    orgs = Organisatie_record.query.filter_by(gebruiker=current_user.idi).order_by(Organisatie_record.standaard.desc(), Organisatie_record.omschrijving).all()

    return render_template('product-edit.html', product=artikel, select=orgs, fv=form_validation, url_param=active_date)


# AJAX route
@artikelen.route('/verwijder_artikel', methods=['POST'])
def verwijder_artikel():
    """ Hiermee verwijder je een artikel van de gebruiker en de bijbehorende bestellingen """

    if not current_user.is_authenticated:
        return '3'

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
@artikelen.route('/reorder', methods=['POST'])
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
