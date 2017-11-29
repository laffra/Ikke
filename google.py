from importers import browser
import urllib.request
import urllib.error
import json
import stopwords
import storage
import time
import traceback

API_KEY = 'AIzaSyCSpLiDh0oSrahlxAIUyxQWfbiaYH1mcIM'

CUSTOM_SEARCH_ENGINE_CX = '016758290502969410251:urp4ckauus8'
SEARCH_FIELDS = 'items(title,link,displayLink,snippet,pagemap/cse_thumbnail/src)'
SEARCH_URL = 'https://www.googleapis.com/customsearch/v1?start=%d&key=%s&fields=%s&cx=%s&q=%s'

NO_PAGEMAP = { 'cse_thumbnail': [ { 'src': '' } ] }


def search(query, start):
    if not query:
        return []
    items = []
    try:
        response = urllib.request.urlopen(SEARCH_URL % (
            start,
            API_KEY,
            SEARCH_FIELDS,
            CUSTOM_SEARCH_ENGINE_CX,
            urllib.request.quote(query)
        )).read()
    except urllib.error.HTTPError as e:
        print('GOOGLE: No results, throttling?', e)
    else:
        try:
            items = [
                GoogleResult(convert_google_result(query, item))
                for item in json.loads(response.decode())['items']
            ]
        except Exception as e:
            print('GOOGLE: Error while running search "%s"' % query, e)
            print('GOOGLE:', response.decode())
            traceback.print_exc()
    return items


class GoogleResult(browser.BrowserItem):
    def __init__(self, obj):
        super(GoogleResult, self).__init__(obj)
        self.kind = 'google'


def convert_google_result(query, obj):
    obj['image'] = obj.get('pagemap', NO_PAGEMAP)['cse_thumbnail'][0]['src']
    obj['label'] = 'Google: %s' % obj['title']
    obj['words'] = stopwords.remove_stopwords('%s %s' % (query, obj['snippet']))
    obj['title'] = obj['domain'] = obj['displayLink']
    obj['url'] = obj['uid'] = obj['link']
    obj['timestamp'] = time.time()

    filename = storage.Storage.get_filename('browser', obj['link'])
    items = list(storage.Storage.search_file(filename))
    if items:
        # user has seen this URL before, update attributes
        item = items[0]
        item.words = list(set(item.words + obj['words']))
        item.image = obj['image']
        item.label = obj['label']
        item.save()
        obj['domain'] = obj['displayLink']
        print('GOOGLE: Update existing url attributes', obj['domain'], item.label)
    return obj


if __name__ == '__main__':
    for node in search('golfbaan'):
        for k,v in vars(node).items():
            print(k, v)
