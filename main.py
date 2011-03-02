#!/usr/bin/env python

import wsgiref.handlers
import os
import datetime
import logging
import random

import facebook
from django.utils import simplejson

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.ext.webapp import util
from google.appengine.api import memcache

FACEBOOK_APPLICATION_ID = '195966860432493'
FACEBOOK_API_KEY = '76509dd840f63e4b92f9242f11c395a1'
FACEBOOK_SECRET_KEY = '01ad26b1a6c1ad9be7d7f1356817767b'

logging.getLogger().setLevel(logging.DEBUG)

# Models

class User(db.Expando):
    id = db.StringProperty(required=True)
    name = db.StringProperty(required=True)
    profile_url = db.StringProperty(required=True)
    picture = db.StringProperty(required=True)
    access_token = db.StringProperty()
    facetime_email = db.StringProperty(default='')
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)
    
    def first_name(self):
        return self.name.split(' ')[0]   
    
    def get_location(self):
        if self.location:
            return self.location
        else:
            return ''
            
    def set_facetime_email(self, email):
        if email == self.facetime_email:
            return email
        else:
            self.facetime_email = email
            self.put()
        return self.facetime_email

# Controllers

class BaseHandler(webapp.RequestHandler):
    
    @property
    def current_user(self):
        if not hasattr(self, "_current_user"):
            self._current_user = None
            cookie = facebook.get_user_from_cookie(self.request.cookies, FACEBOOK_APPLICATION_ID, FACEBOOK_SECRET_KEY)
            if cookie:
                user = User.get_by_key_name(cookie["uid"])
                if not user:
                    graph = facebook.GraphAPI(cookie["access_token"])
                    profile = graph.get_object("me", fields='id,name,link,picture')
                    user = User(key_name=str(profile["id"]),
                                id=str(profile["id"]),
                                name=profile["name"],
                                profile_url=profile["link"],
                                picture=profile["picture"],
                                facetime_email=profile["email"],
                                access_token=cookie["access_token"])
                    user.put()
                elif user.access_token != cookie["access_token"]:
                    user.access_token = cookie["access_token"]
                    user.put()
                self._current_user = user
        return self._current_user

class IndexHandler(BaseHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), "templates/index.html")
        
        facetime_friends = []
        if self.current_user:
            friend_list = facebook.GraphAPI(self.current_user.access_token).get_appusers()
            # friend_list = facebook.GraphAPI(self.current_user.access_token).get_connections("me", "friends.getAppUsers")            
            for f_id in friend_list:
                f_id = str(f_id)
                try:
                    if self.current_user.id != f_id:
                        friend = User.get_by_key_name(f_id)
                        if friend:
                            facetime_friends.append(friend)
                except:
                    logging.error('User not found in local DB with ID: %s' % f_id)
                                    
        args = dict(current_user=self.current_user, facetime_friends=facetime_friends, facebook_app_id=FACEBOOK_APPLICATION_ID, facebook_api_key=FACEBOOK_API_KEY)
        self.response.out.write(template.render(path, args))

class AjaxHandler(BaseHandler):
    """ Base AJAX request handler, requires logged-in user and AJAX request header """
    def process(self):
        raise NotImplementedError()
    
    def get(self):
        # must be logged in
        if self.current_user is None:
            return self.error(403)
        # must be ajax request
        if 'X-Requested-With' not in self.request.headers.keys() or self.request.headers['X-Requested-With'] != 'XMLHttpRequest':
            return self.error(403)
        self.process()

# class AjaxFriendListHandler(AjaxHandler):
#     def process(self):
#         friends = facebook.GraphAPI(self.current_user.access_token).get_connections("me", "friends")
#         if friends and 'data' in friends:
#             res = simplejson.dumps([ { 'value':f['id'], 'label':f['name'] } for f in friends['data'] ])
#             self.response.out.write(res)

class AjaxUpdateEmailHandler(AjaxHandler):
    def process(self):
        facetime_email = self.request.get("email")
        email = self.current_user.set_facetime_email(facetime_email)
        self.response.out.write(simplejson.dumps({ "email": email }))
   
def main():
    application = webapp.WSGIApplication([
                        ('/', IndexHandler),
                        ('/ajax/update_email', AjaxUpdateEmailHandler),
                        # ('/ajax/friend_list', AjaxFriendListHandler),
                    ], debug=True)
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()
