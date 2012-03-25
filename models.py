__author__ = 'Dan'
import os
# dummy config to enable registering django template filters
os.environ['DJANGO_SETTINGS_MODULE'] = 'conf'


import json
from google.appengine.api import urlfetch
from google.appengine.ext import db
import base64
import conf
import hashlib
import hmac
import time
import urllib
import logging

_USER_FIELDS = 'name,email,picture,friends'
class User(db.Model):
    user_id = db.StringProperty(required=True)
    access_token = db.StringProperty(required=True)
    name = db.StringProperty(required=True)
    picture = db.StringProperty(required=True)
    email = db.StringProperty()
    friends = db.StringListProperty()
    dirty = db.BooleanProperty()
    locale = db.StringProperty()

    def refresh_data(self):
        """Refresh this user's data using the Facebook Graph API"""
        me = Facebook().api('/me',
                {'fields': _USER_FIELDS, 'access_token': self.access_token})
        self.dirty = False
        self.name = me['name']
        self.email = me.get('email')
        self.picture = me['picture']
        self.friends = [user['id'] for user in me['friends']['data']]
        return self.put()

class Snippet(db.Model):
    parent_id = db.StringProperty(required=True)
    text = db.StringProperty(required=True)
    props = db.IntegerProperty()
    blocks = db.IntegerProperty()
    branch_ids = db.ListProperty(item_type=long)
    author_id = db.StringProperty();
    author_name = db.StringProperty();
    language = db.StringProperty();
    is_end = db.BooleanProperty();


class Run(db.Model):
    user_id = db.StringProperty(required=True)
    location = db.StringProperty(required=True)
    distance = db.FloatProperty(required=True)
    date = db.DateProperty(required=True)

    @staticmethod
    def find_by_user_ids(user_ids, limit=50):
        if user_ids:
            return Run.gql('WHERE user_id IN :1', user_ids).fetch(limit)
        else:
            return []

    @property
    def pretty_distance(self):
        return '%.2f' % self.distance


class RunException(Exception):
    pass


class FacebookApiError(Exception):
    def __init__(self, result):
        self.result = result

    def __str__(self):
        return self.__class__.__name__ + ': ' + json.dumps(self.result)


class Facebook(object):
    """Wraps the Facebook specific logic"""
    def __init__(self, app_id=conf.FACEBOOK_APP_ID,
                 app_secret=conf.FACEBOOK_APP_SECRET):
        self.app_id = app_id
        self.app_secret = app_secret
        self.user_id = None
        self.access_token = None
        self.locale = None
        self.signed_request = {}

    def api(self, path, params=None, method='GET', domain='graph'):
        """Make API calls"""
        if not params:
            params = {}
        params['method'] = method
        if 'access_token' not in params and self.access_token:
            params['access_token'] = self.access_token
        result = json.loads(urlfetch.fetch(
            url='https://' + domain + '.facebook.com' + path,
            payload=urllib.urlencode(params),
            method=urlfetch.POST,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'})
        .content)
        if isinstance(result, dict) and 'error' in result:
            raise FacebookApiError(result)
        return result

    def load_signed_request(self, signed_request):
        """Load the user state from a signed_request value"""
        try:
            sig, payload = signed_request.split('.', 1)
            sig = self.base64_url_decode(sig)
            data = json.loads(self.base64_url_decode(payload))

            expected_sig = hmac.new(
                self.app_secret, msg=payload, digestmod=hashlib.sha256).digest()

            # allow the signed_request to function for upto 1 day
            if sig == expected_sig and\
               data['issued_at'] > (time.time() - 86400):
                self.signed_request = data
                self.user_id = data.get('user_id')
                self.access_token = data.get('oauth_token')
        except ValueError, ex:
            pass # ignore if can't split on dot

    @property
    def user_cookie(self):
        """Generate a signed_request value based on current state"""
        if not self.user_id:
            return
        payload = self.base64_url_encode(json.dumps({
            'user_id': self.user_id,
            'issued_at': str(int(time.time())),
            }))
        sig = self.base64_url_encode(hmac.new(
            self.app_secret, msg=payload, digestmod=hashlib.sha256).digest())
        return sig + '.' + payload

    @staticmethod
    def base64_url_decode(data):
        data = data.encode('ascii')
        data += '=' * (4 - (len(data) % 4))
        return base64.urlsafe_b64decode(data)

    @staticmethod
    def base64_url_encode(data):
        return base64.urlsafe_b64encode(data).rstrip('=')


class CsrfException(Exception):
    pass