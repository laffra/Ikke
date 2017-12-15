import dothis
from importers import browser
import logging
import graph
import poller
from settings import settings
from storage import Storage

import sys
if sys.version_info >= (3,):
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer
    from socketserver import ThreadingMixIn
    from urllib.parse import parse_qs
else:
    from BaseHTTPServer import BaseHTTPRequestHandler
    from BaseHTTPServer import HTTPServer
    from SocketServer import ThreadingMixIn
    from urlparse import parse_qs

from importlib import import_module
import jinja2
import json
import os
import webbrowser

PORT_NUMBER = 8081
SERVER_ADDRESS = ('127.0.0.1', PORT_NUMBER)

MAIN_URL = 'http://localhost:%s' % PORT_NUMBER


class Server(BaseHTTPRequestHandler):
    jinja2_env = jinja2.Environment(
        loader = jinja2.FileSystemLoader(os.path.join(os.path.dirname(graph.__file__), 'html'))
    )
    graphs = {}
    path = ''
    args = {}

    def do_GET(self):
        routes = {
            '/': self.get_index,
            '/clear': self.clear,
            '/history': self.history,
            '/load': self.load,
            '/stopload': self.stop_loading,
            '/track': self.track,
            '/dothis': self.dothis,
            '/extensions': self.extensions,
            '/get': self.get_resource,
            '/open': self.open_local,
            '/settings': self.settings,
            '/setup': self.handle_setup,
            '/jquery.js': self.get_jquery,
            '/search': self.search,
            '/graph': self.get_graph,
            '/poll': self.poll,
        }
        self.parse_args()
        routes.get(self.path, self.get_file)()

    def log_message(self, format, *args):
        message = format % args
        if not 'search_poll' in message:
            logging.debug(message)

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
            'location': os.path.dirname(os.path.realpath(__file__)),
            'kinds': graph.ALL_ITEM_KINDS[1:],
            'can_load_more': { kind: Storage.can_load_more(kind) for kind in graph.ALL_ITEM_KINDS[1:]},
            'gmail_needed': 'gu' not in settings,
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
            logging.error('Client went away: %s' % e)

    def get_index(self):
        if not 'gu' in settings:
            dothis.activate('myaccount.google.com/apppasswords')
            return self.settings()

        html = self.jinja2_env.get_template('index.html').render({
            'query': self.args.get('q', ''),
            'kinds': graph.ALL_ITEM_KINDS,
            'kinds_string': repr(graph.ALL_ITEM_KINDS),
            'premium': graph.PREMIUM_ITEM_KINDS,
        })
        self.respond(html)

    def clear(self):
        kind = self.args.get('kind', '')
        logging.info('Clearing all history for %s' % kind)
        if Storage.delete_all(kind):
            self.respond('OK')

    def history(self):
        kind = self.args.get('kind', '')
        try:
            self.respond(json.dumps({
                'is_loading': Storage.is_loading(kind),
                'history': Storage.get_history(kind)
            }), content_type='application/json')
        except Exception as e:
            logging.debug('No history for %s' % kind)


    def search(self):
        query = self.args.get('q', '')
        settings['query'] = query
        duration = self.args.get('duration', 'year')
        logging.info('search %s %s' % (duration, query))
        self.graphs[query] = graph.Graph(query, duration)
        self.respond('OK')

    def stop_loading(self):
        Storage.stop_loading(self.args['kind'])
        self.respond('OK')

    def load(self):
        Storage.load(self.args['kind'])
        self.respond('OK')

    def poll(self):
        poller.poll()

    def get_graph(self):
        query = self.args.get('q')
        keep_duplicates = self.args.get('d', '0') == '1'
        kind = self.args['kind']
        graph = self.graphs[query].get_graph(kind, keep_duplicates)
        for node in graph['nodes']:
            if node['kind'] == 'contact' and node['label'].lower() == query.lower():
                node['fixed'] = True
        self.respond(json.dumps(graph))

    def get_resource(self):
        path = os.path.join(os.path.join(os.path.dirname(__file__), 'html'), self.args['path'])
        query = self.args.get('query', '')
        obj = Storage.resolve(path)
        if obj:
            handler = import_module('importers.%s' % obj['kind'])
            if hasattr(handler, 'render'):
                html = handler.render(handler.deserialize(obj), query)
                self.respond(html, 'text/html')
            else:
                with open(obj['path'], 'rb') as f:
                    self.respond(f.read())
        else:
            self.respond(self.load_resource(path, 'rb'))

    def get_jquery(self):
        self.respond(self.load_resource('jquery.js', 'rb'))

    def extensions(self):
        html = self.jinja2_env.get_template('extensions.html').render({
            'location': os.path.join(os.path.dirname(os.path.realpath(__file__)), 'extension')
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

    def handle_setup(self):
        settings['gu'] = self.args['gu']
        settings['gp'] = self.args['gp']
        html = '<script>document.location="/?q=ikke";</script>'
        self.respond(html)
        poller.poll()

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
            logging.error('Fail on %s: %s' % (self.path, e))
            self.send_response(404)

    def load_resource(self, filename, format='r'):
        dirname = os.path.dirname(filename).replace(' ', '+')
        basename = os.path.basename(filename)
        filename = os.path.join(dirname, basename)
        dirpath = os.path.dirname(os.path.realpath(__file__))
        path = os.path.join(dirpath, os.path.join('html', filename))
        with open(path, format) as fp:
            return fp.read()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


if __name__ == '__main__':
    threaded_server = ThreadedHTTPServer(SERVER_ADDRESS, Server)
    webbrowser.open(MAIN_URL, autoraise=False)
    poller.start()
    try:
        threaded_server.serve_forever()
    finally:
        poller.stop()
