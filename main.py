import json
import os
import threading
import rumps
import pubsub
import webbrowser
from functools import partialmethod
from server import startServer
import logging
import faulthandler

faulthandler.enable()

logger = logging.getLogger('main')

class App(rumps.App):
    def __init__(self):
        super(App, self).__init__("ⓘ")
        self.menu = [ ]
        self.menu._menu.setDelegate_(self)
        self.relatedItems = []
        self.query = ""
        startServer(self.showRelated)
        pubsub.register("related", self.showRelated)
        pubsub.register("search", self.searchStarted)
        threading.Timer(1, self.createMenu).start()

    def showRelated(self, query, relatedItems):
        logger.info("Show related %d items for '%s'" % (len(relatedItems), query))
        if not query:
            return
        self.query = query.replace("Chris Laffra", "")
        self.relatedItems = relatedItems
        self.createMenu()

    def searchStarted(self, query, days):
        if not query:
            return
        self.title = "ⓘ"
        logger.info("Search started for '%s'" % query)

    def openUrl(self, url):
        logger.info("Open URL: %s" % url)
        webbrowser.open(url)

    def searchIkke(self):
        self.openUrl("http://localhost:1964/?q=" + self.query)

    def settings(self):
        self.openUrl("http://localhost:1964/settings")

    def searchGoogle(self):
        self.openUrl("https://google.com/search?q=" + self.query)

    def getIcon(self, item):
        file = ""
        if item.icon.startswith("get"):
            file = "html/" + item.icon.replace("get?path=", "")
        if item.icon == "undefined":
            file = "html/icons/blue-circle.png"
        return file if os.path.exists(file) else "html/icons/browser-web-icon.png"

    def createMenuItem(self, item):
        return rumps.MenuItem(
            item.label or item.title,
            icon = self.getIcon(item),
            callback = lambda menuItem: self.openRelated(item),
        )

    def createMenu(self):
        self.menu.clear()
        self.title = "%d" % (len(self.relatedItems) + 2)
        shortenedQuery = " ".join(self.query.split()[:5])
        menuItems = [
            rumps.MenuItem('Search Ikke for "%s"' % shortenedQuery, lambda menuItem: self.searchIkke()),
            rumps.MenuItem('Search Google for "%s"' % shortenedQuery, lambda menuItem: self.searchGoogle()),
            None,
        ] if shortenedQuery else [] 
        menuItems += [
            self.createMenuItem(item)
            for item in self.relatedItems
        ] + [
            None,
            rumps.MenuItem("Settings", lambda menuItem: self.settings()),
            rumps.MenuItem("Quit", rumps.quit_application)
        ]
        self.menu = menuItems
    
    def openRelated(self, item):
        self.openUrl("http://localhost:1964/render?query=%s&%s" % (
            self.query,
            "&".join("%s=%s" % (key, item) for key, item in item.items()),
        ))

    def menuWillOpen_(self):
        self.createMenu()

    def handleRelated(self, menuItem):
        rumps.alert("Ikke", "Based on your history, this item is related")


if __name__ == "__main__":
    App().run()