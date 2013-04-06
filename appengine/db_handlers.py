import time
import webapp2

from google.appengine.ext import db

class DBFlushMedia(webapp2.RequestHandler):
  def get(self):
    count_before = db.GqlQuery("SELECT * FROM InstagramMedia").count()
    imedias = db.GqlQuery("SELECT * FROM InstagramMedia")
    db.delete( imedias )
    count_after = db.GqlQuery("SELECT * FROM InstagramMedia").count()
    self.response.write('Before: %d AND After: %d' % ( count_before, count_after)) 

class DBTestMedia(webapp2.RequestHandler):
  def get(self):
    db_id = int(time.mktime(time.gmtime()))
    new_key = db.Key.from_path('InstagramMedia', db_id)
    instance = InstagramMedia(key=new_key)
    instance.low = 'test'
    instance.high = 'test'
    instance.loc = 'test'
    instance.created = db_id
    instance.link = 'test'
    instance.lat = 3.0
    instance.lon = 4.0
    instance.text = 'test'
    instance.put()
    self.response.write('Wrote test doc')
    
class DBTestLocation(webapp2.RequestHandler):
  def get(self):
    db_id = int(time.mktime(time.gmtime()))
    new_key = db.Key.from_path('LocationInfo', db_id)
    locsub = LocationInfo(key=new_key)
    locsub.id = '3011990'
    locsub.object_id = '2884044'
    locsub.loc = 'newyork'
    locsub.put()
    self.response.write('Wrote test doc')
