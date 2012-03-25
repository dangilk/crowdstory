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
import simplejson

from init import *
import webapp2




class RPCHandler(webapp2.RequestHandler):
    """ Allows the functions defined in the RPCMethods class to be RPCed."""

    def __init__(self,request,response):
        self.initialize(request, response)
        self.methods = RPCMethods()
        self.response.headers['P3P'] = 'CP=HONK'  # iframe cookies in IE

    def get(self):
        func = None

        action = self.request.get('action')
        if action:
            if action[0] == '_':
                self.error(403) # access denied
                return
            else:
                func = getattr(self.methods, action, None)

        if not func:
            self.error(404) # file not found
            return

        args = ()
        while True:
            key = 'arg%d' % len(args)
            val = self.request.get(key)
            if val:
                args += (simplejson.loads(val),)
            else:
                break
        result = func(*args)
        self.response.out.write(simplejson.dumps(result))

class RPCMethods:
    """ Defines the methods that can be RPCed.
    NOTE: Do not allow remote callers access to private/protected "_*" methods.
    """
    def Add(self, *args):
        # The JSON encoding may have encoded integers as strings.
        # Be sure to convert args to any mandatory type(s).
        ints = [int(arg) for arg in args]
        return sum(ints)

    def getSnips(self, *args):
        if len(args)==2:
            pid = str(args[0])
            locale = str(args[1])
            q = Snippet.all()
            q.filter('parent_id =',pid)
            q.filter('language =',locale_to_lang(locale))
            snips = q.fetch(100)
            ret = []
            for s in snips:
                snip = to_dict(s)
                snip['children'] = []
                snip['id'] = s.key().id()
                ret.append(snip)
            return ret
        return False

    def writeSnip(self, *args):
        if len(args)==5:
            pid = str(args[0])
            text = str(args[1])
            author_id = str(args[2])
            author_name = str(args[3])
            locale = str(args[4])

            snip = Snippet(
                parent_id=pid,
                author_id=author_id,
                author_name=author_name,
                blocks=0,
                is_end=True,
                language=locale_to_lang(locale),
                props=0,
                text=text
            )
            snip.put()

            parent = Snippet.get_by_id(int(pid))
            if parent:
                parent.is_end = False
                parent.put()

            return snip.key().id()



#def main():
#    routes = [
#        (r'/rpc', RPCHandler),
#    ]
#    application = webapp.WSGIApplication(routes,
#        debug=os.environ.get('SERVER_SOFTWARE', '').startswith('Dev'))
#    util.run_wsgi_app(application)
#
#
#if __name__ == '__main__':
#    main()
routes = [(r'/rpc', RPCHandler)]
app = webapp2.WSGIApplication(routes,debug=os.environ.get('SERVER_SOFTWARE', '').startswith('Dev'))