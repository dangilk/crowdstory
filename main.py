#!/usr/bin/env python
# coding: utf-8
# Copyright 2011 Facebook, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import os
# dummy config to enable registering django template filters
os.environ['DJANGO_SETTINGS_MODULE'] = 'conf'

from google.appengine.ext.webapp import util
import webapp2
from init import *


class WelcomeHandler(BaseHandler):
    def get(self):
        self.render('welcome')

class RecentRunsHandler(BaseHandler):
    """Show recent runs for the user and friends"""
    def get(self):
        #snip = Snippet(parent_id='0',text='hello',author_id='0',author_name='dan',blocks=0,props=0,language='en',is_end=False)
        #snip.put()
        if self.user:
            friends = {}
            for friend in select_random(
                    User.get_by_key_name(self.user.friends), 30):
                friends[friend.user_id] = friend

            #get all base snippets
            q = Snippet.all()
            logging.info('user id '+self.user.user_id);
            q.filter('language =',locale_to_lang(self.user.locale))
            q.filter('parent_id =','0');
            objects = q.fetch(100);
            snips = []
            for snip in objects:
                s = to_dict(snip)
                s['id'] = snip.key().id()
                s['children'] = []
                snips.append(s)
            snips = json.dumps(snips)
            #logging.info('token: '+self.user.access_token)

            self.render('runs',
                friends=friends,
                user_recent_runs=Run.find_by_user_ids(
                    [self.user.user_id], limit=5),
                friends_runs=Run.find_by_user_ids(friends.keys()),
                first_snips=snips,
                user_name = self.user.name,
                user_id = self.user.user_id,
                user_locale = self.user.locale,
                token = self.user.access_token
            )
        else:
            #self.render('welcome')

            redirect = urllib.quote_plus('http://apps.facebook.com/'+conf.FACEBOOK_CANVAS_NAME+"/");
            auth = "https://www.facebook.com/dialog/oauth?client_id="+conf.FACEBOOK_APP_ID+"&redirect_uri="+redirect
            logging.info('redirecting to '+ auth)
            self.response.out.write("<script>top.location.href=\""+auth+"\";</script>")



class UserRunsHandler(BaseHandler):
    """Show a specific user's runs, ensure friendship with the logged in user"""
    @user_required
    def get(self, user_id):
        if self.user.friends.count(user_id) or self.user.user_id == user_id:
            user = User.get_by_key_name(user_id)
            if not user:
                self.set_message(type='error',
                    content='That user does not use Run with Friends.')
                self.redirect('/')
                return

            self.render('user',
                user=user,
                runs=Run.find_by_user_ids([user_id]),
            )
        else:
            self.set_message(type='error',
                content='You are not allowed to see that.')
            self.redirect('/')


class RunHandler(BaseHandler):
    """Add a run"""
    @user_required
    def post(self):
        try:
            location = self.request.POST['location'].strip()
            if not location:
                raise RunException('Please specify a location.')

            distance = float(self.request.POST['distance'].strip())
            if distance < 0:
                raise RunException('Invalid distance.')

            date_year = int(self.request.POST['date_year'].strip())
            date_month = int(self.request.POST['date_month'].strip())
            date_day = int(self.request.POST['date_day'].strip())
            if date_year < 0 or date_month < 0 or date_day < 0:
                raise RunException('Invalid date.')
            date = datetime.date(date_year, date_month, date_day)

            run = Run(
                user_id=self.user.user_id,
                location=location,
                distance=distance,
                date=date,
            )
            run.put()

            title = run.pretty_distance + ' miles @' + location
            publish = '<a onclick=\'publishRun(' + \
                    json.dumps(htmlescape(title)) + ')\'>Post to facebook.</a>'
            self.set_message(type='success',
                content='Added your run. ' + publish)
        except RunException, e:
            self.set_message(type='error', content=unicode(e))
        except KeyError:
            self.set_message(type='error',
                content='Please specify location, distance & date.')
        except ValueError:
            self.set_message(type='error',
                content='Please specify a valid distance & date.')
        except Exception, e:
            self.set_message(type='error',
                content='Unknown error occured. (' + unicode(e) + ')')
        self.redirect('/')


class RealtimeHandler(BaseHandler):
    """Handles Facebook Real-time API interactions"""
    csrf_protect = False

    def get(self):
        if (self.request.GET.get('setup') == '1' and
            self.user and conf.ADMIN_USER_IDS.count(self.user.user_id)):
            self.setup_subscription()
            self.set_message(type='success',
                content='Successfully setup Real-time subscription.')
        elif (self.request.GET.get('hub.mode') == 'subscribe' and
              self.request.GET.get('hub.verify_token') ==
                  conf.FACEBOOK_REALTIME_VERIFY_TOKEN):
            self.response.out.write(self.request.GET.get('hub.challenge'))
            logging.info(
                'Successful Real-time subscription confirmation ping.')
            return
        else:
            self.set_message(type='error',
                content='You are not allowed to do that.')
        self.redirect('/')

    def post(self):
        body = self.request.body
        if self.request.headers['X-Hub-Signature'] != ('sha1=' + hmac.new(
            self.facebook.app_secret,
            msg=body,
            digestmod=hashlib.sha1).hexdigest()):
            logging.error(
                'Real-time signature check failed: ' + unicode(self.request))
            return
        data = json.loads(body)

        if data['object'] == 'user':
            for entry in data['entry']:
                taskqueue.add(url='/task/refresh-user/' + entry['id'])
                logging.info('Added task to queue to refresh user data.')
        else:
            logging.warn('Unhandled Real-time ping: ' + body)

    def setup_subscription(self):
        path = '/' + conf.FACEBOOK_APP_ID + '/subscriptions'
        params = {
            'access_token': conf.FACEBOOK_APP_ID + '|' +
                             conf.FACEBOOK_APP_SECRET,
            'object': 'user',
            'fields': _USER_FIELDS,
            'callback_url': conf.EXTERNAL_HREF + 'realtime',
            'verify_token': conf.FACEBOOK_REALTIME_VERIFY_TOKEN,
        }
        response = self.facebook.api(path, params, 'POST')
        logging.info('Real-time setup API call response: ' + unicode(response))


class RefreshUserHandler(BaseHandler):
    """Used as an App Engine Task to refresh a single user's data if possible"""
    csrf_protect = False

    def post(self, user_id):
        logging.info('Refreshing user data for ' + user_id)
        user = User.get_by_key_name(user_id)
        if not user:
            return
        try:
            user.refresh_data()
        except FacebookApiError:
            user.dirty = True
            user.put()


#def main():
#    routes = [
#        (r'/', RecentRunsHandler),
#        (r'/user/(.*)', UserRunsHandler),
#        (r'/run', RunHandler),
#        (r'/realtime', RealtimeHandler),
#        (r'/welcome',WelcomeHandler),
#
#        (r'/task/refresh-user/(.*)', RefreshUserHandler),
#    ]
#    application = webapp.WSGIApplication(routes,
#        debug=os.environ.get('SERVER_SOFTWARE', '').startswith('Dev'))
#    util.run_wsgi_app(application)


#if __name__ == '__main__':
#    main()
routes = [
    (r'/', RecentRunsHandler),
    (r'/user/(.*)', UserRunsHandler),
    (r'/run', RunHandler),
    (r'/realtime', RealtimeHandler),
    (r'/welcome',WelcomeHandler),

    (r'/task/refresh-user/(.*)', RefreshUserHandler),
]
app = webapp2.WSGIApplication(routes,debug=os.environ.get('SERVER_SOFTWARE', '').startswith('Dev'))
