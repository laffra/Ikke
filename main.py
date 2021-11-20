import rumps
import faulthandler
import logging
import os
import threading
import webbrowser
import pubsub
import pynsights
from server import startServer

faulthandler.enable()

logger = logging.getLogger('main')
lock = threading.Lock()

class App(rumps.App):
    '''
        The main UI for Ikke. Places a menu item in the MacOS statusbar.
    '''
    def __init__(self):
        super(App, self).__init__("ⓘ")
        self.menu = [ ]
        self.menu._menu.setDelegate_(self)
        self.related_items = []
        self.query = ""
        startServer(self.show_related)
        pubsub.register("related", self.show_related)
        pubsub.register("search", self.search_started)
        threading.Timer(1, self.create_menu).start()
        rumps.notification("Ikke", "Welcome", "See the number in the statusbar for related items")

    def show_related(self, query, related_items):
        '''
        Show related items to a given query in the MacOS statusbar
        '''
        with lock:
            logger.info("Show related %d items for '%s'", len(related_items), query)
            if not query:
                return
            self.query = query.replace("Chris Laffra", "")
            self.related_items = related_items
            self.create_menu()

    def search_started(self, query, _):
        '''
        Handle a new search
        '''
        if not query:
            return
        self.title = "ⓘ"
        logger.info("Search started for '%s'", query)

    @classmethod
    def open_url(cls, url):
        '''
        Open a given URL in the default web browser
        '''
        logger.info("Open URL: %s", url)
        webbrowser.open(url)

    def search_ikke(self):
        '''
        Run the current search query in the Ikke graph UI.
        This will open a new browser page.
        '''
        App.open_url("http://localhost:1964/?q=" + self.query)

    def settings(self):
        '''
        Open the settings UI for Ikke.
        '''
        App.open_url("http://localhost:1964/settings")

    def help(self):
        '''
        Open the documentation for Ikke.
        '''
        App.open_url("https://github.com/laffra/Ikke")

    def problem(self):
        '''
        Open the issues page for Ikke.
        '''
        App.open_url("https://github.com/laffra/Ikke/issues")

    def search_google(self):
        '''
        Open a browser window to Google to search for the current query.
        '''
        App.open_url("https://google.com/search?q=" + self.query)

    def get_icon(self, item):
        '''
        Return the relative path for the icon in the given menu item.
        '''
        file = ""
        if item.icon.startswith("get"):
            file = "html/" + item.icon.replace("get?path=", "")
        if item.icon == "undefined":
            file = "html/icons/blue-circle.png"
        return file if os.path.exists(file) else "html/icons/browser-web-icon.png"

    def create_menu_item(self, item):
        '''
        Create a new menu item to be shown in the MacOS statusbar.
        '''
        return rumps.MenuItem(
            item.label or item.title,
            icon = self.get_icon(item),
            callback = lambda menuItem: self.open_related(item),
        )

    def create_menu(self):
        '''
        Create the menu to be shown in the MacOS statusbar.
        '''
        self.menu.clear()
        self.title = "%d" % (len(self.related_items))
        short_query = " ".join(self.query.split()[:5])
        menu_items = [
            rumps.MenuItem('Search Ikke for "%s"' % short_query, lambda _: self.search_ikke()),
            rumps.MenuItem('Search Google for "%s"' % short_query, lambda _: self.search_google()),
            None,
        ] if short_query else [] 
        menu_items += [
            self.create_menu_item(item)
            for item in self.related_items
        ] + [
            None,
            rumps.MenuItem("Ikke Settings", lambda _: self.settings()),
            rumps.MenuItem("Help", lambda _: self.help()),
            rumps.MenuItem("Report a Problem", lambda _: self.problem()),
            rumps.MenuItem("Quit", self.quit),
        ]
        self.menu = menu_items
    
    def quit(self, sender=None):
        pynsights.stop_tracing()
        rumps.quit_application()
    
    def open_related(self, item):
        '''
        The user clicked on a related item. Open it now.
        '''
        self.open_url("http://localhost:1964/render?query=%s&%s" % (
            self.query,
            "&".join("%s=%s" % (key, item) for key, item in item.items()),
        ))

    def menuWillOpen_(self):
        self.create_menu()

    def handleRelated(self):
        rumps.notification("Ikke", "Related Items", "Based on your history, this item is related")


if __name__ == "__main__":
    App().run()
