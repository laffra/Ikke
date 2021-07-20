import json
import os


def get_preferences_path():
    if os.name == 'nt':
        return ['AppData', 'Local', 'Google', 'Chrome', 'User Data', 'Default', 'preferences']
    else:
        return ['Library', 'Application Support', 'Google', 'Chrome', 'Default', 'Preferences']


class ChromePreferences:
    def __init__(self):
        home = os.path.expanduser("~")
        preferences_path = os.path.join(home, *get_preferences_path())
        with open(preferences_path) as fin:
            self.preferences = json.load(fin)
        print("Loaded Chrome preferences from", preferences_path, self.preferences['account_info'])

    def get_language_profile(self):
        return [(l['language'], l['probability']) for l in self.get('language_profile').get('reading').get('preference')]

    def get_google_url(self):
        return self.get('browser').get('last_known_google_url')

    def get_top_sites(self):
        sites = self.get('profile').get('content_settings').get('exceptions').get('site_engagement')
        return sorted([
            (url.split(',')[0], data['setting']['rawScore'])
            for url, data in sites.items()
        ], key=lambda pair: -pair[1])

    def get_account_info(self):
        return self.get('account_info')[-1]

    def get_email(self):
        return self.get_account_info()['email']

    def get_custom_handlers(self):
        return {
            handler['protocol']: handler['url']
            for handler in self.get('custom_handlers').get('registered_protocol_handlers')
        }

    def get_account_infos(self):
        return self.get('account_info')

    def get_chrome_version(self):
        return self.get('extensions').get('last_chrome_version')

    def get_download_folder(self):
        return self.get('savefile').get('default_directory')

    def get(self, key):
        return self.preferences[key]

    def __str__(self):
        return json.dumps(self.preferences, indent=4)


if __name__ == '__main__':
    p = ChromePreferences()
    print('language_profile:', p.get_language_profile())
    print('custom_handlers:', p.get_custom_handlers())
    print('top_sites[:10]:')
    for n, (url, score) in enumerate(p.get_top_sites()[:10]):
        print('   ', n+1, url, score)
    print('full_name:', p.get_account_info().get('full_name'))
    print('account_info:',json.dumps(p.get_account_info(), indent=4))

    import hosts
    hosts.setup_as_administrator()

