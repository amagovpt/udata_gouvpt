# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from udata import theme, mail, i18n
from udata.i18n import I18nBlueprint
from flask import url_for, redirect, abort, Markup, render_template, request, current_app, g
from jinja2.exceptions import TemplateNotFound
import markdown, urllib2
import redis

from urlparse import urlparse
from flask_wtf import FlaskForm, recaptcha
from wtforms.fields.html5 import EmailField
from udata.forms import fields, validators
from flask_mail import Message
from flask_security.utils import do_flash

from udata.models import Dataset, Organization

class ContactForm(FlaskForm):
    name = fields.StringField("Name", [validators.Required()])
    email = EmailField("Email", [validators.Required(), validators.Email()])
    subject = fields.StringField("Subject", [validators.Required()])
    message = fields.TextAreaField("Message", [validators.Required()])
    recaptcha = recaptcha.RecaptchaField()

def get_redis_connection():
    parsed_url = urlparse(current_app.config['CELERY_BROKER_URL'])
    db = parsed_url.path[1:] if parsed_url.path else 0
    return redis.StrictRedis(host=parsed_url.hostname, port=parsed_url.port,
                             db=db)

blueprint = I18nBlueprint('gouvpt', __name__,
                          template_folder='../theme/templates/custom',
                          static_folder='../theme/static')


#Dynamic FAQ's pages cached in redis
@blueprint.route('/docs/', defaults={'section': 'index'})
@blueprint.route('/docs/<string:section>/')
def faq(section):
    r = get_redis_connection()
    lang_code = g.get('lang_code', current_app.config['DEFAULT_LANGUAGE'])
    lang = lang_code if lang_code == current_app.config['DEFAULT_LANGUAGE'] else 'en'
    try:
        giturl = "https://raw.githubusercontent.com/amagovpt/docs.dados.gov.pt/master/faqs_{0}/{1}.md".format(lang,section)
        response = urllib2.urlopen(giturl, timeout = 2).read().decode('utf-8')
        content = Markup(markdown.markdown(response))
    except urllib2.URLError:
        cached_page = r.get(section+lang)
        if cached_page:
            response = cached_page.decode('utf-8')
            content = Markup(markdown.markdown(response))
            do_flash("Viewing cached content.", 'info')
            return theme.render('faqs.html', page_name=section, content=content)
        else:
            abort(404)
    else:
        r.set(section+lang, response.encode('utf-8'))
        return theme.render('faqs.html', page_name=section, content=content)

#Credits page
@blueprint.route('/credits/')
def credits():
    return theme.render('credits.html')

#Contact Form page
@blueprint.route('/contact/', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if request.method == 'POST':
        if form.validate_on_submit() == False:
            for field, errors in form.errors.items():
                for error in errors:
                    do_flash(i18n.gettext(error),'danger')
        else:
            msg = Message(form.subject.data, sender=current_app.config.get('MAIL_DEFAULT_SENDER'), recipients=[current_app.config.get('MAIL_DEFAULT_RECEIVER')])
            msg.body = """
            From: %s <%s>
            %s
            """ % (form.name.data, form.email.data, form.message.data)
            try:
                mail = current_app.extensions.get('mail')
                mail.send(msg)
            except Exception, e:
                do_flash("Server Error : " + str(e), 'danger')
            else:
                do_flash(i18n.gettext(u"Thank you for your message. We'll get back to you shortly."), 'success')
    return theme.render('contact.html', form=form)

#Keep old API online
@blueprint.route('/v1/<string:org_slug>/<string:file_id>/', subdomain="servico")
def dadosGovOld_API(org_slug, file_id):
    format = 'json' if request.args.get('format','xml').lower() == 'json' else 'xml'
    dataset = Dataset.objects(__raw__={'extras.harvest:remote_id': file_id}).first()
    if dataset:
        for resource in dataset.resources:
            if resource.format == format:
                return redirect(resource.url)
    #Everything else return 404               
    return abort(404)


@blueprint.route('/organization/<org>/')
def redirect_organizations(org):
    '''Route legacy CKAN organizations'''
    return redirect(url_for('organizations.show', org=org))

#Add Acessibilidade page
@blueprint.route('/acessibilidade/')
def redirect_acessibilidade():
    return redirect(url_for('gouvpt.faq', section='acessibilidade'))

#Add docapi
@blueprint.route('/docapi/')
def docapi():
    organizations = Organization.objects.all()
    return theme.render('api.html', organizations=organizations)

#Data Analysis with PivotTable page
@blueprint.route('/pivot_table/')
def pivot_table():
    return theme.render('pivot_table.html')

#Data Analysis with rawgraphs page
@blueprint.route('/rawgraphs/')
def rawgraphs():
    return theme.render('rawgraphs.html')