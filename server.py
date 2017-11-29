import dothis
from importers import browser
import graph
import poller
from settings import settings
from storage import Storage

from http import server
from importlib import import_module
import jinja2
import json
import os
import socketserver
import urllib.parse
import webbrowser

PORT_NUMBER = 8081
SERVER_ADDRESS = ('127.0.0.1', PORT_NUMBER)

MAIN_URL = 'http://localhost:%s' % PORT_NUMBER


class Server(server.BaseHTTPRequestHandler):
    jinja2_env = jinja2.Environment(
        loader = jinja2.FileSystemLoader(os.path.join(os.path.dirname(graph.__file__), 'html')),
        autoescape = jinja2.select_autoescape(['html', 'xml'])
    )
    graphs = {}
    path = ''
    args = {}

    def do_GET(self):
        routes = {
            '/': self.get_index,
            '/load': self.load,
            '/track': self.track,
            '/dothis': self.dothis,
            '/extensions': self.extensions,
            '/get': self.get_resource,
            '/open': self.open_local,
            '/install': self.install,
            '/setup': self.handle_setup,
            '/jquery.js': self.get_jquery,
            '/search': self.search,
            '/graph': self.get_graph,
        }
        self.parse_args()
        routes.get(self.path, self.get_file)()

    def log_message(self, format, *args):
        message = format % args
        if not 'search_poll' in message:
            print('SERVER:', message)

    def parse_args(self):
        try:
            index = self.path.index('?')
            self.args = urllib.parse.parse_qs(self.path[index + 1:])
            for k,v in self.args.items():
                self.args[k] = v[0] if len(v) == 1 else v
            self.path = self.path[:index]
        except ValueError:
            self.args = {}

    def install(self):
        self.send_response(200)
        self.end_headers()
        html = self.jinja2_env.get_template('setup.html').render({
            'location': os.path.dirname(os.path.realpath(__file__)),
        });
        self.wfile.write(bytes(html, 'utf8'))

    def get_index(self):
        if not 'gu' in settings:
            dothis.activate('myaccount.google.com/apppasswords')
            return self.install()

        self.send_response(200)
        self.end_headers()
        html = self.jinja2_env.get_template('index.html').render({
            'query': self.args.get('q', ''),
            'kinds': graph.ALL_ITEM_KINDS,
            'kinds_string': repr(graph.ALL_ITEM_KINDS),
            'premium': graph.PREMIUM_ITEM_KINDS,
        })
        self.wfile.write(bytes(html, 'utf8'))

    def search(self):
        self.send_response(200)
        self.end_headers()
        query = self.args.get('q', '')
        settings['query'] = query
        duration = self.args.get('duration', 'year')
        print('SERVER: search', duration, query)
        self.graphs[query] = graph.Graph(query, duration)

    def get_graph(self):
        query = self.args.get('q')
        keep_duplicates = self.args.get('d', '0') == '1'
        kind = self.args['kind']
        self.send_response(200)
        self.end_headers()
        json_text = json.dumps(self.graphs[query].get_graph(kind, keep_duplicates))
        try:
            self.wfile.write(bytes(json_text, 'utf8'))
        except Exception as e:
            print('SERVER: Client went away', e)

    def get_resource(self):
        self.send_response(200)
        path = self.args['path']
        query = self.args.get('query', '')
        # print('SERVER: get', repr(query), repr(path))
        obj = Storage.resolve(path.replace(' ', '%20'))
        if obj:
            handler = import_module('importers.%s' % obj['kind'])
            if hasattr(handler, 'render'):
                html = handler.render(handler.deserialize(obj), query)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(bytes(html, 'utf8'))
            else:
                self.end_headers()
                with open(obj['path'], 'rb') as f:
                    self.wfile.write(f.read())
        else:
            self.end_headers()
            self.wfile.write(self.load_resource(path.replace(' ', '%20'), 'rb'))

    def get_jquery(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.load_resource('jquery.js', 'rb'))

    def extensions(self):
        self.send_response(200)
        self.end_headers()
        html = self.jinja2_env.get_template('extensions.html').render({
            'location': os.path.join(os.path.dirname(os.path.realpath(__file__)), 'extension')
        })
        self.wfile.write(bytes(html, 'utf8'))

    def load(self):
        self.send_response(200)
        self.end_headers()
        items = Storage.search_file('"%s"' % self.args['uid'])
        print('Found', len(items), 'items for', self.args['uid'])
        for n, item in enumerate(items):
            if 'path' in item and os.path.exists(item['path']):
                path = os.path.realpath(item['path'])
                url = 'file://%s' % path
                webbrowser.open(url)
                print('webbrowser opened', n, url)
        html = '<html><script></script></html>'
        self.wfile.write(bytes(html, 'utf8'))

    def open_local(self):
        webbrowser.open('file://%s' % self.args['path'].replace(' ', '\\ '))

    def dothis(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(bytes(dothis.get_work(self.args['url']), 'utf8'))

    def handle_setup(self):
        self.send_response(200)
        self.end_headers()
        settings['gu'] = self.args['gu']
        settings['gp'] = self.args['gp']
        html = '<script>document.location="/?q=ikke";</script>'
        self.wfile.write(bytes(html, 'utf8'))
        poller.poll()

    def track(self):
        browser.track(
            self.args.get('url', ''),
            self.args.get('title', ''),
            self.args.get('image', ''),
            self.args.get('favicon', ''),
            self.args.get('selection', '')
        )
        self.send_response(200)
        self.end_headers()
        self.wfile.write(bytes('OK', 'utf8'))

    def get_file(self):
        try:
            payload = bytes(self.load_resource(self.path[1:]), 'utf8')
            self.send_response(200)
            self.end_headers()
            self.wfile.write(payload)
        except:
            self.send_response(404)

    def load_resource(self, filename, format='r'):
        dirpath = os.path.dirname(os.path.realpath(__file__))
        path = os.path.join(dirpath, os.path.join('html', filename))
        with open(path, format) as fp:
            return fp.read()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, server.HTTPServer):
    """Handle requests in a separate thread."""


if __name__ == '__main__':
    poller.start()
    threaded_server = ThreadedHTTPServer(SERVER_ADDRESS, Server)
    webbrowser.open(MAIN_URL, autoraise=False)
    print('SERVER: running on', MAIN_URL)
    try:
        threaded_server.serve_forever()
    except KeyboardInterrupt:
        poller.stop()
