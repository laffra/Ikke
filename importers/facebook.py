from dateutil import parser
import facebooksdk
import json
import logging
import storage
import stopwords
import time
import traceback
from settings import settings

DOMAINS = {'web.whatsapp.com', 'www.messenger.com', 'www.facebook.com'}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

keys = ('uid', 'label', 'name', 'story', 'place', 'timestamp')
path_keys = ('label', 'uid', 'icon', 'image', 'words')


def get_access_token():
    return settings['facebook/access_token']


def deserialize(obj):
    return obj if isinstance(obj, FacebookNode) else FacebookNode('facebook', obj)


def get_status():
    return '%d facebook posts' % settings['facebook/count']


def poll():
    load()


def delete_all():
    pass


def get_oauth_url():
    return 'https://developers.facebook.com/apps/%s/fb-login/' % settings['facebook/appid']

def get_login_url():
    args = 'scope=%s&client_id=%s&redirect_uri=%s' % (
        PERMISSIONS,
        settings['facebook/appid'],
        'http://localhost:1964/fb'
    )
    args += '&auth_type=rerequest'
    return 'https://www.facebook.com/v2.11/dialog/oauth?%s' % args

settings['facebook/can_load_more'] = True
settings['facebook/pending'] = 'facebook/appsecret' not in settings


FACEBOOK_GRAPH_EDGES = {
    'accounts': 'Facebook Pages this person administers/is an admin for',
    'achievements': 'Achievements made in Facebook games',
    'ad_studies': 'Ad studies that this person can view',
    'adaccounts': 'The advertising accounts to which this person has access',
    'adcontracts': 'The person\'s ad contracts',
    'adnetworkanalytics': 'Insights data for the person\'s Audience Network apps',
    'albums': 'The photo albums this person has created',
    'apprequestformerrecipients': 'App requests',
    'apprequests': 'This person\'s pending requests from an app',
    'asset3ds': 'The 3D assets owned by the user',
    'assigned_ad_accounts': 'assigned_ad_accounts',
    'assigned_monetization_properties': 'assigned_monetization_properties',
    'assigned_pages': 'assigned_pages',
    'assigned_product_catalogs': 'assigned_product_catalogs',
    'books': 'The books listed on this person\'s profile',
    'business_activities': 'The business activities related to this user',
    'business_users': 'Business users corresponding to the user',
    'businesses': 'Businesses associated with the user',
    'conversations': 'Facebook Messenger conversation',
    'curated_collections': 'The curated collections created by this user',
    'custom_labels': 'custom labels',
    'domains': 'The domains the user admins',
    'events': 'Events for this person. By default this does not include events the person has declined or not replied to',
    'family': 'This person\'s family relationships.',
    'favorite_requests': 'Developers\' favorite requests to the Graph API',
    'friendlists': 'The person\'s custom friend lists',
    'friends': 'A person\'s friends.',
    'games': 'Games this person likes',
    'groups': 'The Facebook Groups that the person is a member of',
    'ids_for_apps': 'Businesses can claim ownership of multiple apps using Business Manager. This edge returns the list of IDs that this user has in any of those other apps',
    'ids_for_business': 'Businesses can claim ownership of multiple apps using Business Manager. This edge returns the list of IDs that this user has in any of those other apps',
    'ids_for_pages': 'Businesses can claim ownership of apps and pages using Business Manager. This edge returns the list of IDs that this user has in any of the pages owned by this business.',
    'invitable_friends': 'A list of friends that can be invited to install a Facebook Canvas app',
    'leadgen_forms': 'A list of lead generation forms belonging to Pages that the user has advertiser permissions on',
    'likes': 'All the Pages this person has liked',
    'live_encoders': 'Live encoders owned by this person',
    'live_videos': 'Live videos from this person',
    'movies': 'Movies this person likes',
    'music': 'Music this person likes',
    'objects': 'Objects',
    'permissions': 'The permissions that the person has granted this app',
    'personal_ad_accounts': 'The advertising accounts to which this person has personal access',
    'photos': 'Photos the person is tagged in or has uploaded',
    'picture': 'The person\'s profile picture',
    'promotable_domains': 'All the domains user can promote',
    'promotable_events': 'All the events which user can promote.',
    'request_history': 'Developers\' Graph API request history',
    'rich_media_documents': 'A list of rich media documents belonging to Pages that the user has advertiser permissions on',
    'session_keys': 'Any session keys that the app knows the user by',
    'stream_filters': 'A list of filters that can be applied to the News Feed edge',
    'taggable_friends': 'Friends that can be tagged in content published via the Graph API',
    'tagged_places': 'List of tagged places for this person. It can include tags on videos, posts, statuses or links',
    'television': 'TV shows this person likes',
    'threads': 'A message conversation thread',
    'video_broadcasts': 'Video broadcasts from this person',
    'videos': 'Videos the person is tagged in or uploaded',
    'checkins': 'The checkins this person has made.',
    'feed': 'The feed of posts (including status updates) and links published by this person.',
    'friendrequests': 'A person\'s pending friend requests.',
    'home': 'A person\'s Facebook homepage feed.',
    'inbox': 'A person\'s Facebook Messages inbox.',
    'locations': 'A feed of posts and photos that include location information and in which this person has been tagged. This is useful for constructing a chronology of places that the person has visited.',
    'mutualfriends': 'The list of mutual friends between two people.',
    'notifications': 'The unread Facebook notifications that a person has.',
    'outbox': 'A person\'s Facebook Messages outbox.',
    'questions': 'The questions that a person has created.',
    'scores': 'The scores this person has received from Facebook Games that they\'ve played.',
    'subscribers': 'The profiles that are following this person.',
    'subscribedto': 'The pofile that this person is following.',
}
EDGES = [
    'music', 'movies', 'books', 'family', 'friends', 'groups', 'taggable_friends',
    'locations', 'television', 'threads', 'albums', 'photos', 'events', 'inbox', 'feed', 'likes',
]
PERMISSIONS = [
    'email', 'public_profile', 'read_custom_friendlists', 'user_about_me', 'user_birthday',
    'user_actions.books', 'user_actions.fitness', 'user_actions.music', 'user_actions.news',
    'user_actions.video', 'user_friends', 'user_hometown', 'user_location', 'user_work_history',
    'user_tagged_places', 'user_videos', 'user_website', 'user_posts', 'user_photos',
    'user_likes', 'user_events', 'pages_messaging', 'user_managed_groups'
]



def load():
    try:
        logger.info('Load facebook')
        settings['facebook/loading'] = True
        graph = facebooksdk.GraphAPI(get_access_token())
        for edge in EDGES:
            try:
                for obj in graph.get_all_connections('me', edge):
                    storage.Storage.add_data(FacebookNode(edge, add_words(obj)))
                    logger.info('Add %s: "%s"', edge, obj['words'])
                    settings.increment('facebook/count')
            except facebooksdk.GraphAPIError:
                logging.error(traceback.format_exc())
                pass
    finally:
        settings['facebook/loading'] = False


def get(obj, path):
    for p in path.split('/'):
        if obj:
            obj = obj.get(p)
    return obj


def get_text(obj):
    if isinstance(obj, str):
        return obj
    elif isinstance(obj, dict):
        return ' '.join(map(get_text, [value for key,value in obj.items() if key not in ['uid', 'id']]))
    else:
        return ''


def add_words(obj):
    obj['words'] = stopwords.remove_stopwords(get_text(obj))
    return obj


class FacebookNode(storage.Data):
    def __init__(self, edge, obj):
        super(FacebookNode, self).__init__(obj.get('label') or obj.get('name') or obj.get('story') or '')
        self.uid = 'facebook-%s' % (obj.get('uid') or obj.get('id'))
        self.kind = 'facebook'
        self.edge = edge
        self.image = get(obj, 'picture/data/url')   # friend
        self.color = '#888'
        self.icon = 'get?path=icons/facebook.png'
        self.icon_size = 24
        self.font_size = 10
        self.zoomed_icon_size = 24
        self.words = obj['words']

        self.story = obj.get('story', '')
        self.place = obj.get('place', '')

        self.persons = []
        when = obj.get('created_time') or obj.get('start_time')
        self.timestamp = parser.parse(when).timestamp() if when else time.time()

        dict.update(self, vars(self))

    def __hash__(self):
        return hash(self.uid)

    def is_related_item(self, other):
        return other.kind == 'facebook'

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.uid == other.uid
        else:
            return False

    def is_duplicate(self, duplicates):
        if self.label in duplicates:
            self.duplicate = True
            return True
        duplicates.add(self.label)
        return False

    def render(self, query):
        url = 'https://www.facebook.com/search/top?q=%s' % (self.label or '+'.join(self.words))
        return '<html><a href="%s">view in facebook</a>' % url




if __name__ == '__main__':
    load()
