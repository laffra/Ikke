import jinja2
import logging
import os
import utils
from urllib.parse import urlparse

work = {}

jinja2_env = jinja2.Environment(
    loader = jinja2.FileSystemLoader(os.path.join(utils.INSTALL_FOLDER, 'html', 'dothis'))
)


def get_key(url):
    return '%s/%s' % (urlparse(url).netloc, urlparse(url).path.split('/')[1])


def activate(key):
    logging.info('dothis: activate %s' % key)
    work[key] = tasks[key]


def deactivate(key):
    logging.info('dothis: deactivate %s' % key)
    del work[key]


def get_work(url):
    key = get_key(url)
    if key in work:
        response = work[key]
        deactivate(key)
        return response
    return ''


tasks = {
    'myaccount.google.com/apppasswords': jinja2_env.get_template('google.html').render({}),
    'developers.facebook.com/apps': jinja2_env.get_template('facebook_apps.html').render({}),
    'developers.facebook.com/quickstarts': jinja2_env.get_template('facebook_quickstart.html').render({}),
    'settings/searchEngines': jinja2_env.get_template('search_engines.html').render({}),
}

