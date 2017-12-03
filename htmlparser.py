
import sys
if sys.version_info >= (3,):
    from html.parser import HTMLParser
else:
    from HTMLParser import HTMLParser

from re import sub
from sys import stderr
from traceback import print_exc


class HTMLTextParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.__text = []
        self.__skip = False

    def handle_data(self, data):
        if not self.__skip:
            text = data.strip()
            if len(text) > 0:
                text = sub('[ \t\r\n]+', ' ', text)
                self.__text.append(text + ' ')

    def handle_starttag(self, tag, attrs):
        self.__skip = False
        if tag == 'p':
            self.__text.append('\n\n')
        elif tag == 'br':
            self.__text.append('\n')
        elif tag == 'style':
            self.__skip = True

    def handle_startendtag(self, tag, attrs):
        if tag == 'br':
            self.__text.append('\n\n')
        self.__skip = False

    def text(self):
        return ''.join(self.__text).strip()


import re
REMOVE_STYLE_RE = re.compile('<style.*</style>', re.IGNORECASE)

def get_text(html):
    try:
        parser = HTMLTextParser()
        parser.feed(re.sub(REMOVE_STYLE_RE, '', html))
        parser.close()
        return parser.text()
    except:
        print_exc(file=stderr)
        return html


def main():
    text = r'''
        <html>
            <body>
                <b>Project:</b> DeHTML<br>
                <b>Description</b>:<br>
                This small script is intended to allow conversion from HTML markup to 
                plain text.
            </body>
        </html>
    '''
    print(get_text(text))


if __name__ == '__main__':
    main()