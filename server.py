from storage import Storage

import compressor
import dothis
from importers import browser
from importers import contact
from importers import download
from importers import facebook
from importers import file
from importers import gmail
import installer
import logging
import graph
import poller
from preferences import ChromePreferences
from settings import settings
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs
from urllib.request import urlopen
import jinja2
import json
import os
import traceback
import threading
import utils
import webbrowser


logger = logging.getLogger('server')

PORT_NUMBER = 1964
SERVER_ADDRESS = '127.0.0.1'


class Server(BaseHTTPRequestHandler):
    jinja2_env = jinja2.Environment(
        loader = jinja2.FileSystemLoader(os.path.join(utils.INSTALL_FOLDER, 'html'))
    )
    graphs = {}
    path = ''
    args = {}
    preferences = ChromePreferences()

    def do_GET(self):
        routes = {
            '/': self.get_index,
            '/clear': self.clear,
            '/stopclear': self.stop_deleting,
            '/status': self.status,
            '/load': self.load,
            '/stopload': self.stop_loading,
            '/track': self.track,
            '/dothis': self.dothis,
            '/extensions': self.extensions,
            '/get': self.get_resource,
            '/render': self.render,
            '/open': self.open_local,
            '/settings': self.settings,
            '/continuesetup': self.continue_setup,
            '/setupgmail': self.setup_gmail,
            '/setupfacebook': self.setup_facebook,
            '/jquery.js': self.get_jquery,
            '/search': self.search,
            '/graph': self.get_graph,
            '/poll': self.poll,
            '/fb': self.fb,
        }
        logger.debug('GET %s' % self.path)
        self.parse_args()
        routes.get(self.path, self.get_file)()

    def log_message(self, format, *args):
        message = format % args
        if not 'search_poll' in message:
            logger.debug(message)

    def parse_args(self):
        try:
            index = self.path.index('?')
            self.args = parse_qs(self.path[index + 1:])
            for k,v in self.args.items():
                self.args[k] = v[0] if len(v) == 1 else v
            self.path = self.path[:index]
        except ValueError:
            self.args = {}

    def settings(self):
        html = self.jinja2_env.get_template('settings.html').render({
            'location': utils.INSTALL_FOLDER,
            'kinds': graph.ALL_ITEM_KINDS[1:],
            'can_load_more': { kind: Storage.can_load_more(kind) for kind in graph.ALL_ITEM_KINDS[1:]},
            'can_delete': { kind: Storage.can_delete(kind) for kind in graph.ALL_ITEM_KINDS[1:]},
        })
        self.respond(html)

    def respond(self, html, content_type=None):
        self.send_response(200)
        if content_type:
            self.send_header('Content-type', content_type)
        self.end_headers()
        try:
            message = bytes(html, 'utf8')
        except:
            message = html
        try:
            self.wfile.write(message)
        except Exception as e:
            logger.error('Client went away: %s' % e)

    def get_index(self):
        html = self.jinja2_env.get_template('index.html').render({
            'query': self.args.get('q', ''),
            'kinds': graph.ALL_ITEM_KINDS,
            'kinds_string': repr(graph.ALL_ITEM_KINDS),
            'profile': self.preferences.get_account_info(),
        })
        self.respond(html)

    def clear(self):
        kind = self.args.get('kind', '')
        logger.info('Clearing all history for %s' % kind)
        if Storage.delete_all(kind):
            self.respond('OK')

    def stop_deleting(self):
        Storage.stop_deleting(self.args['kind'])
        self.respond('OK')

    def status(self):
        self.respond(json.dumps(Storage.get_status()))

    def search(self):
        query = self.args.get('q', '')
        settings['query'] = query
        duration = self.args.get('duration', 'year')
        logger.info('search %s %s' % (duration, query))
        self.graphs[query] = graph.Graph(query, duration)
        self.respond('OK')

    def stop_loading(self):
        Storage.stop_loading(self.args['kind'])
        self.respond('OK')

    def load(self):
        Storage.load(self.args['kind'])
        self.respond('OK')

    def fb(self):
        code = self.args.get('code')
        if code:
            logger.info('Exchange code for access token')
            redirect_uri = 'http://localhost:%d/fb' % settings['port']
            client_secret = settings['facebook/appsecret']
            client_id = settings['facebook/appid']
            url = 'https://graph.facebook.com/v2.11/oauth/access_token?client_id=%s&redirect_uri=%s' \
                   '&client_secret=%s&code=%s' % (client_id, redirect_uri, client_secret, code)
            logger.info('Load URL: %s' % url)
            response = json.loads(urlopen(url).read().decode())
            settings['facebook/access_token'] = response['access_token']
        self.settings()

    def poll(self):
        poller.poll()

    def get_graph(self):
        query = self.args.get('q')
        keep_duplicates = self.args.get('d', '0') == '1'
        kind = self.args['kind']
        logger.info('get graph for %s: %s', kind, query)
        graph = self.graphs[query].get_graph(kind, keep_duplicates)
        self.respond(json.dumps(graph))

    def get_resource(self):
        path = os.path.join(utils.INSTALL_FOLDER, 'html', self.args['path'])
        self.respond(self.load_resource(path, 'rb'))

    def render(self):
        try:
            item = Storage.load_item(self.args.get('path'))
            self.respond('<html>%s<p>Key:<pre>%s</pre><p>Value:<pre>%s</pre>' % (
                item.render(self.args['query']),
                json.dumps(compressor.deserialize(compressor.serialize(item)), indent=4),
                json.dumps(item, indent=4)
            ))
        except:
            msg = 'Cannot render: %s' % traceback.format_exc()
            logging.error(msg)
            self.respond(self.get_resource())

    def get_jquery(self):
        self.respond(self.load_resource('jquery.js', 'rb'))

    def extensions(self):
        html = self.jinja2_env.get_template('extensions.html').render({
            'location': os.path.join(utils.INSTALL_FOLDER, 'extension')
        })
        self.respond(html)

    def load_items(self):
        items = Storage.search_file('"%s"' % self.args['uid'])
        for n, item in enumerate(items):
            if 'path' in item and os.path.exists(item['path']):
                path = os.path.realpath(item['path'])
                url = 'file://%s' % path
                webbrowser.open(url)
        html = '<html><script></script></html>'
        self.respond(html)

    def open_local(self):
        webbrowser.open('file://%s' % self.args['path'].replace(' ', '\\ '))

    def dothis(self):
        self.respond(dothis.get_work(self.args['url']))

    def continue_setup(self):
        url = self.args.get('url')
        args = self.args.get('args')
        dothis.activate(url)
        html = '<script>document.location="https://%s/%s";</script>' % (url, args)
        self.respond(html)

    def setup_gmail(self):
        settings['gmail/username'] = self.args['gu']
        settings['gmail/password'] = self.args['gp']
        threading.Thread(target=lambda: Storage.load('gmail')).start()
        self.respond("OK")

    def setup_facebook(self):
        if self.args.get('appid'):
            settings['facebook/appid'] = self.args['appid']
            settings['facebook/appsecret'] = self.args['appsecret']
            dothis.activate('developers.facebook.com/apps')
            url = facebook.get_oauth_url()
        else:
            url = facebook.get_login_url()
        html = '<script>document.location="%s";</script>' % url
        self.respond(html)

    def track(self):
        browser.track(
            self.args.get('url', ''),
            self.args.get('title', ''),
            self.args.get('image', ''),
            self.args.get('favicon', ''),
            self.args.get('selection', '')
        )
        self.respond('OK')

    def get_file(self):
        try:
            payload = self.load_resource(self.path[1:])
            try:
                payload = bytes(payload, 'utf8')
            except:
                pass
            self.respond(payload)
        except Exception as e:
            logger.debug('Fail on %s: %s' % (self.path, e))
            self.send_response(404)

    def load_resource(self, filename, format='r'):
        dirname = os.path.dirname(filename).replace(' ', '+')
        basename = os.path.basename(filename)
        filename = os.path.join(dirname, basename)
        path = os.path.join(utils.INSTALL_FOLDER, os.path.join('html', filename))
        with open(path, format) as fp:
            return fp.read()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    installer.install()
    port = settings.get('port', PORT_NUMBER)
    threaded_server = ThreadedHTTPServer(('localhost', port), Server)
    # poller.start()
    url = 'http://localhost:%d/settings' % port
    webbrowser.open(url, autoraise=False)
    settings['port'] = port
    if settings['browser/count'] < 100:
        threading.Thread(target=lambda: Storage.load('browser')).start()
    try:
        threaded_server.serve_forever()
    finally:
        poller.stop()
        for kind in graph.ALL_ITEM_KINDS[1:]:
            Storage.stop_loading(kind)
