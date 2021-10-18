# Ikke
Easily find back all your data!

# Features

Ikke produces a local backup of your (social) data, with fast local search,
visualizing the connections between de data across various sources.

Why the name Ikke?

    Ikke is a Dutch colloquial/slang word, meaning "I", "Me", or "Myself".  It is pronounced as "ik-kuh", and is mainly used in the Dutch pseudo-narcist phrase "Ikke, ikke, ikke, en de rest kan stikken", translated roughly into "Me, me, me, and screw all others".

When [pronounced correctly](https://upload.wikimedia.org/wikipedia/commons/3/39/Nl-ikke.ogg),
Ikke sounds a lot like the English word "ticket", if you remove the leading and trailing t's.

# How it works

<table><tr><td>
    <img src="/images/architecture.png" />
</td></tr></table>

Ikke consists of various components:
 * Importers for data sources such as browser history, local downloads, gmail, git, etc.
 * A Chrome browser extension that:
   * collects a thumbnail image of websites you visited to find them back quickly.
   * shows related items to the current "Essence" of the site being viewed, see the yellow Dot in web pages.
 * A statusbar icon showing the number of related items with a menu.
 * A super-fast freetext search backend that runs on your local machine, not needing any cloud access.
 * Smooth graph visualizations that show relationships between various data sources.
 * A [Settings UI](http://localhost:1964/settings) to control the index and indicate if you want to use the Dot or not.
 
# Installation

Setup Ikke:
 * Clone the repo and cd to its root
 ```
 git clone https://github.com/laffra/Ikke
 cd Ikke
 ```
 * Set up a virtualenv
 ```
 python3 -m pip install virtualenv
 python3 -m venv env_ikke
 ```
 * Activate the virtualenv you just created 
 ```
 source env_ikke/bin/activate
 ```
 * Run 
 ```
 python3 setup.py install
 ```
 * Visit "chrome://extensions" in your browser
 * Load the unpacked extension from the repo's "extension" folder.

The first time Ikke runs, it performs post-setup tasks. One of the things Ikke needs is your approval to index your Google data, such as gmail, calendar, etc. Things that happen during the first run:
   * A Google dialog is shown to give "Ikke Graph" access to your data.
   * The "Ikke graph" app is not verified by Google, so you may get a scary warning. This is OK. Click on the 
   "advanced" link and provide access. See below what happens next.
   * The auth token received from Google is stored on your local machine under ~/IKKE.

Your privacy is preserved:
   * The "Ikke Graph" app can only access your data using the locally stored token. Therefore, it can only index your data on your local machine. 
   * The token and all your indexed data are stored locally only. No one will have access to it, unless they run a program on your local machine and use the token.
   * You will get an email and/or notification from Google saying "Ikke Graph was granted access to your Google Account"

# Usage

Run Ikke:
```
python3 main.py
```

Visit your settings:
* Click on the statusbar number icon or see [Settings](http://localhost:1964/settings):

<table><tr><td>
<img src="images/screenshot-ikke-settings.png">
</td></tr></table>

* By default, Ikke will index your browser history.
* To load other sources, such as gmail, hit the corresponding "Load" button. 
* Optional: Enable the browser extension's "Dot".
* Click on the IKKE logo to start a new search on the currently indexed data.

# Using the Dot

Use the "Dot" to show related items:
* Enable the feature in your settings (see above).
* Go to a website and notice the dot appear, such as the one shown below next to Elon Musk saying "12":

<table><tr><td>
<img src="images/screenshot-ikke-dot.png">
</td></tr></table>

* Click on the dot to discover the 12 related items to Elon Musk (this list is different for every user, of course):

<table><tr><td>
<img src="images/screenshot-ikke-related.png">
</td></tr></table>

# Showing an Ikke Graph

You can show an Ikke Graph from the Dot, the statusbar, and from its UI:

<table><tr><td>
<img src="images/screenshot-ikke-graph.png">
</td></tr></table>

# Showing an Ikke Grid

The graph is great to see a quick overview of the relationships between the data. 
If you want to focus more on time and recency, the Ikke Grid may be a better UI:

<table><tr><td>
<img src="images/screenshot-grid.png">
</td></tr></table>

The Grid and the Graph show the same information, sorted differently.

# Using the status bar icon

You can always use the statusbar icon to explore related items as well:

<table><tr><td>
<img src="images/screenshot-ikke-statusbar.png">
</td></tr></table>

# Using the context menu

Inside Chrome, the Ikke Dot tries to guess the current "essence" of the page. It favors words
that appear in the top-middle of the page and that have more "weight" than others.
Sometimes, however, you will want to search for a word nearby. Simply right-mouse click on it,
or select some text first, and activate the context menu to use the Ikke menu item:

<table><tr><td>
<img src="images/screenshot-context-menu.png">
</td></tr></table>

# Uninstall

Uninstall takes three steps:
* Visit [Settings](http://localhost:1964/settings) and delete all data.
* Remove ~/IKKE entirely
* Remove the local repo you cloned during startup

# Future Work

Some things that could improve Ikke:
* Add authentication to elasticsearch
* Add an ML model to the Essence finder
* Finish up the py2app bundling (see build.py)
* Distribute as a Mac app in the AppStore with a real installer
* Handle possible port number conflicts
* Add more importers, such as TikTok, FB, IG, and WhatsApp...
* Consider extensions for other browsers, such as IE, Firefox
* Add a plugin to standalone tools, such as VSCode.

# Privacy

You privacy is key. Ikke does not upload ANY data. Everything being indexed is stored on your local machine. Ikke does not use your data for marketing purposes or ads. No logging is ever uploaded. Your data is yours and stays yours.
