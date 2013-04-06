from datetime import datetime, timedelta

import app_constants
import client_query
import db_handlers
import subscription_handlers

import os.path
import json
import logging
import pprint
import random
import time
import urllib
import webapp2

from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch


"""db models"""
class InstagramMedia(db.Model):
  """ Models an instagram media."""
  low = db.StringProperty(indexed=False)
  high = db.StringProperty(indexed=False)
  loc = db.StringProperty(indexed=False)
  created = db.IntegerProperty(indexed = False)
  link = db.StringProperty(indexed=False)
  lat = db.FloatProperty(indexed=False)
  lon = db.FloatProperty(indexed=False)
  text = db.StringProperty(indexed=False)
  
  def to_dict(self):
    return dict([(p, unicode(getattr(self, p))) for p in self.properties()])  


"""handlers"""
class Fetch(webapp2.RequestHandler):
  def get(self):
    curr_locsub = subscription_handlers.Helper.getLocation()
    if not curr_locsub:
      return
    url_str_frame = 'https://api.instagram.com/v1/geographies/%s/media/recent?client_id=%s'
    url_str = url_str_frame%(curr_locsub.object_id, app_constants.CLIENT_ID)
    result = urlfetch.fetch(url_str,
                            method=urlfetch.GET)
    json_data = json.loads(result.content)
    imedias = db.GqlQuery("SELECT * FROM InstagramMedia")
    
    last_time = 0
    #find latest time
    for imedia in imedias:
      if imedia.created > last_time:
        last_time = imedia.created
    
    logging.info("Last time: %d", last_time)  
    new_media = [ m for m in json_data['data'] if int(m['created_time']) > last_time ]
    
    db_instances = []
    for media in new_media:
      db_id = int(media["created_time"])
      new_key = db.Key.from_path('InstagramMedia', db_id)
      instance = InstagramMedia(key=new_key)
      instance.created = int(media["created_time"])
      instance.loc = "newyork"
      instance.link = media["link"]
      instance.low = media["images"]["thumbnail"]["url"]
      instance.high = media["images"]["standard_resolution"]["url"]
      instance.lat = media["location"]["latitude"]
      instance.lon = media["location"]["longitude"]
      instance.text = ''
      if media["caption"]:
        try:
          instance.text = media["caption"]["text"]
        except:
          pass
      db_instances += [instance]
    
    db.put( db_instances )
    if not new_media:
      self.response.out.write('No new media')
      return
    
    self.response.out.write(json.dumps({'count': len(new_media), 'out': new_media}))

class Flush(webapp2.RequestHandler):
  def get(self):
    count_before = db.GqlQuery("SELECT * FROM InstagramMedia").count()
    expiration_date = int(time.time()) - 30*60
    imedias = db.GqlQuery("SELECT * FROM InstagramMedia")
    imedia_to_delete = [ m for m in imdedias if m.created < expiration_date ]
    db.delete( imedia_to_delete )
    count_after = db.GqlQuery("SELECT * FROM InstagramMedia").count()
    self.response.write('Before: %d AND After: %d' % ( count_before, count_after))            

class MainPage(webapp2.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.write('Welcome to Snapcity\n')
    self.response.write("last modified: %s" % time.ctime(os.path.getmtime('server_w_cron.py')))

class Retrieve(webapp2.RequestHandler):
  # Get: 
  # loc: location for the request
  # lastseen: last successful time this client did a request
  """Example:
  localhost:8000/retrieve?loc=newyork&lastseen=1361405226
  """
  def get(self):
    loc = self.request.get("loc").lower()
    lastseen = self.request.get("lastseen")
    duration = self.request.get("duration")

    logging.info('Location:%s, Lastseen:%s Duration:%s', loc, lastseen, duration)

    # Check that we can locate the city
    if not app_constants.GEOCODES.has_key(loc):
      logging.info('Location not found')
      return  # we can change this later on, only support newyork or chicago
    
    self._return_results(loc, lastseen)
  
  def _return_results(self, loc, lastseen):
    logging.info("Querying for %s:%s", loc, lastseen)
    q = db.GqlQuery("SELECT * FROM InstagramMedia " +
                    "WHERE ID >= :1 " +
                    "ORDER BY ID ASC", long(lastseen))
    # Query is not executed until results are accessed
    for p in q:
      logging.info("Found:%s", p.to_dict())
    
    self.response.headers.add_header("Access-Control-Allow-Origin", "*")
    self.response.out.write(json.dumps({'results': [p.to_dict() for p in q]}))

class Query(webapp2.RequestHandler):
  # Get: 
  # loc: location for the request
  # lastseen: last successful time this client did a request
  """Example:
  http://snapcity02.appspot.com/query?loc=newyork&lb=1362296026&ub=1362300391
  """
  def get(self):
    loc = self.request.get("loc").lower()
    lb = long(self.request.get("lb"))
    ub = long(self.request.get("ub"))
    self._return_results(loc, lb, ub)
    
  def _return_results(self, loc, lb, ub):
    logging.info("Querying for %s: lb %d and ub %d", loc, lb, ub)
    q = db.GqlQuery("SELECT * FROM InstagramMedia " +
                    "WHERE ID >= :1 AND ID < :2 " +
                    "ORDER BY ID ASC",
                    lb, ub)
    # Query is not executed until results are accessed
    for p in q:
      logging.info("Found:%s", p.to_dict())
    
    self.response.headers.add_header("Access-Control-Allow-Origin", "*")
    self.response.out.write(json.dumps({'results': [p.to_dict() for p in q]}))
    
class Stream(webapp2.RequestHandler):
  def get(self):
    challenge = self.request.get("hub.challenge")
    mode = self.request.get("hub.mode")
    verify_token = self.request.get("hub.verify_token")
    logging.info("Received: mode:%s challenge:%s token:%s\n",
                 mode, challenge, verify_token)
    if mode == "subscribe" and verify_token == app_constants.VERIFY_TOKEN:
      logging.info("Request is:%s", self.request)
      logging.info("Yes, we want to subscribe!")
      self.response.write(challenge)

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/dbflushmedia', db_handlers.DBFlushMedia),
                               ('/dbtestlocation', db_handlers.DBTestLocation),
                               ('/dbtestmedia', db_handlers.DBTestMedia),
                               ('/deletesubscriptions', subscription_handlers.DeleteSubscriptions),
                               ('/listsubscriptions', subscription_handlers.ListSubscriptions),
                               ('/makesubscription', subscription_handlers.MakeSubscription),
                               ('/getmedia', client_query.RetrieveMedia),
                               ('/flush', Flush),
                               ('/fetch', Fetch),
                               ('/query', Query),
                               ('/retrieve', Retrieve),
                               ('/stream', Stream)
                               ],
                              debug=True)
