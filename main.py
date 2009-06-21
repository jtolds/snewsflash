#!/usr/bin/env python

MINIMUM_RECHECK_TIME = 600 # 10 minutes, in seconds

import cgi, os, datetime, wsgiref.handlers

from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api.labs.taskqueue import Task
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

class Feed(db.Model):
  url = db.StringProperty()
  last_content = db.Text()

def adminonly(handler_method):
  """Decorator that requires the requesting user to be an admin."""
  def decorate(myself, *args, **kwargs):
    if ('HTTP_X_APPENGINE_TASKNAME' in os.environ
        or users.is_current_user_admin()):
      handler_method(myself, *args, **kwargs)
    elif users.get_current_user() is None:
      myself.redirect(users.create_login_url(myself.request.url))
    else:
      myself.response.set_status(401)
  return decorate

class Root(webapp.RequestHandler):
  def get(self):
    self.response.out.write('''<html><body><center><h1>SnewsFlash</h1> <p>coming soon!</p></center></body></html>''')

class Admin(webapp.RequestHandler):
  @adminonly
  def get(self):
    self.response.out.write(template.render('templates/admin.html',
        {"feeds": Feed.all()}))
  @adminonly
  def post(self):
    action = self.request.get('action')
    if action == 'add feed':
      assert self.request.get('url', '')
      feed = Feed(url = self.request.get('url'))
      feed.put()
      Task(url='/admin/task/updatefeed/',
           params={'feed_id': feed.key().id()},
           countdown=0).add('feedpull')
    elif action == 'delete':
      assert self.request.get('id', '')
      Feed.get_by_id(int(self.request.get('id', ''))).delete()
    self.redirect('/admin/')

class FeedPullWorker(webapp.RequestHandler):
  @adminonly
  def post(self):
    def txn():
      try:
        feed = Feed.get_by_id(int(self.request.get('feed_id', '')))
        assert feed
      except: return
      Task(url='/admin/task/updatefeed/',
           params={'feed_id': feed.key().id()},
           countdown=MINIMUM_RECHECK_TIME).add('feedpull')
      result = urlfetch.fetch(feed.url, follow_redirects=True)
      if result.status_code != 200: return
      feed.last_content = result.content
      feed.put()
    db.run_in_transaction(txn)

def redirect(target):
  class Redirect(webapp.RequestHandler):
    def get(self):
      self.redirect(target)
  return Redirect

application = webapp.WSGIApplication([
  ('/ing/soon/', Root),
  ('/admin/task/updatefeed/', FeedPullWorker),
  ('/admin/', Admin),
  ('.*', redirect('/ing/soon/')),
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
