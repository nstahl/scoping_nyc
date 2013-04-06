from datetime import datetime, timedelta
import json
import logging
import pprint
import random
import urllib
import webapp2
import tagfilter

from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch

CLIENT_ID = 'd209925240954901a02b12b038ecf63f'
CLIENT_SECRET = '1e29ffe684604f3fa6fd04baaaafab78'
SUBSCRIPTION_URL = 'https://api.instagram.com/v1/subscriptions'
VERIFY_TOKEN = "snapcity02"
GEOCODES = { 
  "newyork": ["40.7474","-73.9915"], 
  "chicago": ["41.877","-87.663"],
}  
MATCHERS = {
  "newyork": tagfilter.TagFilter("data/newyork_pois.json"),
  "chicago": tagfilter.TagFilter("data/chicago_pois.json")
}
DEBUG = False

class InstagramMedia(db.Model):
  """ Models an instagram media."""
  low = db.StringProperty()
  high = db.StringProperty()
  loc = db.StringProperty(indexed = True)
  created = db.IntegerProperty(indexed = True)
  link = db.StringProperty()
  lat = db.FloatProperty()
  lon = db.FloatProperty()
  text = db.StringProperty()
  
  def to_dict(self):
    return dict([(p, unicode(getattr(self, p))) for p in self.properties()])  

class LocationInfo(db.Model):
  """ Models a location and everything we want to keep about it """
  object_id = db.StringProperty()  # Object Id of the subscription
  id = db.StringProperty()  # id of the subscription
  loc = db.StringProperty()
  
  def to_dict(self):
    return dict([(p, unicode(getattr(self, p))) for p in self.properties()])  
  

"""/"""
class MainPage(webapp2.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.write('Hello, webapp2 World!!!')

"""listsubscriptions"""
class ListSubscriptions(webapp2.RequestHandler):
  def get(self):
    form_fields = {
      'client_id': CLIENT_ID,
      'client_secret' : CLIENT_SECRET
      }
    form_data = urllib.urlencode(form_fields)
    result = urlfetch.fetch(url='%s?%s'%(SUBSCRIPTION_URL,form_data),
                            method=urlfetch.GET)
    json_data = json.loads(result.content)
    logging.info("List of subscribers:%s", result.content)
    self.response.write("<pre>")
    pprint.pprint(json.dumps(json_data), self.response.out)
    self.response.write("</pre>")

"""
/stream
This is instagram's callback url
"""
class Subscription(webapp2.RequestHandler):
  # Get: checks if we are subscribing, if so, writes back
  # the challenge.
  def get(self):
    logging.info("Instagram checking that we exist!")
    challenge = self.request.get("hub.challenge")
    mode = self.request.get("hub.mode")
    verify_token = self.request.get("hub.verify_token")
    logging.info("Received: mode:%s challenge:%s token:%s\n",
                 mode, challenge, verify_token)
    if mode == "subscribe" and verify_token == VERIFY_TOKEN:
      logging.info("Request is:%s", self.request)
      logging.info("Yes, we want to subscribe!")
      self.response.write(challenge)
      
  # Post: gets an image.
  def post(self):
    """Process instagram data"""
    
    body = self.request.body
    json_data = json.loads(body)
    
    #we need to design this for multiple update objs
    object_id = json_data[0]["object_id"]
    
    if not object_id:
      logging.info("Possibly empty content:%s", body)
      return
    
    logging.info("Got instagram post with object id " + object_id)
    
    #if not DEBUG:
    self._get_media(object_id)
  
  def _get_media(self, object_id):
    loc = memcache.get(object_id + ":loc")

    if not loc:   # there is nothing in memcache, try out datastore
      results = db.GqlQuery("SELECT * FROM LocationInfo WHERE object_id = :1", object_id)
      if not results:
        logging.info("Cannot find object_id:%s in LocationInfo DB", object_id)
        logging.info("Skipping media retrieval!")
        return
      loc = results[0].loc

    form_fields = {
      'client_id': CLIENT_ID,
      }

    min_id = memcache.get(object_id + ":min_id")
    if min_id:
      form_fields["min_id"] = min_id 
    form_data = urllib.urlencode(form_fields)
    
    logging.info(form_data)
    url_str = url='https://api.instagram.com/v1/geographies/%s/media/recent?%s'%(object_id,form_data)
    logging.info(url_str)
    
    result = urlfetch.fetch(url_str,
                            method=urlfetch.GET)
    json_data = json.loads(result.content)
    
    if json_data["meta"]["code"] is not 200:
      logging.error("Error getting media!")
      return

    if json_data["pagination"]:
      min_id = json_data["pagination"]["next_min_id"]
      if min_id:
        memcache.add(object_id + ":min_id", min_id, 3600)

    for media in json_data["data"]:
      logging.info( media )
      if media["caption"]:
        media_text = media["caption"]["text"] 
        if True:#MATCHERS[loc].match(media_text):
          
          db_id = long(media["created_time"])
          new_key = db.Key.from_path('InstagramMedia', db_id)
          instance = InstagramMedia(key=new_key)
          
          #previously
          instance.created = long(media["created_time"])
          instance.loc = loc
          instance.link = media["link"]
          instance.low = media["images"]["thumbnail"]["url"]
          instance.high = media["images"]["standard_resolution"]["url"]
          instance.lat = media["location"]["latitude"]
          instance.lon = media["location"]["longitude"]
          instance.text = media_text
          #store
          instance.put()
          logging.info("%s at %s", media_text, instance.high)

"""delete"""  
class Delete(webapp2.RequestHandler):
  def post(self): # we only get a post request from our taskqueue
    loc = self.request.get('loc').lower()
    if loc == "all":
      if (self._delete_subscriber("all")):
        db.delete(db.LocationInfo())
        memcache.flush_all()
        logging.info("All deleted")
      
    results = db.GqlQuery("SELECT * FROM LocationInfo WHERE loc = :1", loc)
    if not results:
      logging.info("Empty result in LocationInfo for: %s", loc)
      logging.info("Cannot delete anything bc we don't have loc")
      return
    
    for item in results:
      logging.info("Found:%s", item.to_dict())
      if (self._delete_subscriber(item.id)):
        logging.info("Subscriber being deleted loc(%s) and object_id(%s)", 
                     item.loc, item.object_id)
        memcache.delete(item.object_id + ":min_id")
        memcache.delete(item.object_id + ":loc")
        db.delete(item)
      else:
        logging.info("Could not delete subscriber:%s", loc)

  """ Deletes a subscriber for the given id_object_id
      id_object_id can be "all", which deletes everything
  """
  def _delete_subscriber(self, id):
    if id!="all" and id is None:
      logging.info("Cannot delete id:%s", id)
      return False
    form_fields = {
      'client_id': CLIENT_ID,
      'client_secret' : CLIENT_SECRET,
      }
    if id == "all":
      form_fields["object"] = "all"
    else:
      form_fields['id'] = id
 
    form_data = urllib.urlencode(form_fields)
    logging.info("Calling delete with: %s", form_data)
    result = urlfetch.fetch(url='%s?%s'%(SUBSCRIPTION_URL, form_data),
                            method=urlfetch.DELETE)
    json_data = json.loads(result.content)
    if json_data["meta"]["code"]!= 200 :
      logging.info("Status code not 200: %s", result.content)
      return False
    return True

"""retrieve"""  
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
    if not GEOCODES.has_key(loc):
      logging.info('Location not found')
      return  # we can change this later on, only support newyork or chicago
    
    #Check that we have a subscription for the city
    if self._check_subscription(loc, duration):
      logging.info('Returning results...')
      self._return_results(loc, lastseen)
    
  # checks if we are listening for this location
  # if we are not, it registers a subscriber, and queues a deletion for the subscriber
  def _check_subscription(self, loc, duration):
    data = db.GqlQuery("SELECT * FROM LocationInfo WHERE loc = :1", loc)
    if data.count():  # we have a listener
      logging.info("Cannot add stuff, we already have a listener for it")
      return False
    # Otherwise we register a subscriber to this location
    id = self._register_subscriber(loc)
    
    if id is None:
      # error, we could not register a subscriber
      logging.error("Could not register a subscriber for location:%s", loc)
      return False
    value_to_be_added = LocationInfo()
    value_to_be_added.loc = loc
    value_to_be_added.object_id = id[1]  # Post pubsub requests come with object_id.
    value_to_be_added.id = id[0]  # When deleting, you delete using the id.
    value_to_be_added.put()
    # for fast lookups
    memcache.add(id[1] + ":loc", loc, 3600)
    #adds a deleter
    self._add_deleter_to_queue(loc, duration)
    return True

  def _return_results(self, loc, lastseen):
    logging.info("Querying for %s:%s", loc, lastseen)
    q = db.GqlQuery("SELECT * FROM InstagramMedia " +
                    "WHERE loc = :1 AND created >= :2 " +
                    "ORDER BY created ASC",
                    loc, long(lastseen))
    # Query is not executed until results are accessed
    for p in q:
      logging.info("Found:%s", p.to_dict())
    
    self.response.headers.add_header("Access-Control-Allow-Origin", "*")
    self.response.out.write(json.dumps({'results': [p.to_dict() for p in q]}))

  def _add_deleter_to_queue(self, loc, duration):
    now = datetime.now()
    delete_mins = 33
    if duration and int(duration):
      delete_mins = int(duration)
    delete_date = now + timedelta(minutes=delete_mins)
    taskqueue.add( url = '/delete', params = {'loc': loc}, eta = delete_date)
    logging.info("Now is:%s, Added deleter for location:%s at %s", now, loc, delete_date)

  # registers a subscriber
  def _register_subscriber(self, loc):
    form_fields = {
      'client_id': CLIENT_ID,
      'client_secret' : CLIENT_SECRET,
      'verify_token' : VERIFY_TOKEN, 
      'object' : 'geography',
      'aspect' : 'media',
      'lat' : GEOCODES[loc][0], 
      'lng' : GEOCODES[loc][1],
      'radius' : '5000',
      'callback_url' : 'http://snapcity02.appspot.com/stream'
      }
    form_data = urllib.urlencode(form_fields)
    #post to instagram
    result = urlfetch.fetch(url=SUBSCRIPTION_URL,
                            payload=form_data,
                            method=urlfetch.POST)
          
    if result.status_code != 200:
      logging.info("Status code not 200, it is %s: %s", result.status_code, result.content)
      return
    data = json.loads(result.content)
    
    object_id = data["data"]["object_id"]
    id = data["data"]["id"]
    logging.info("Registered subscriber for loc:%s, id:%s and object_id:%s", loc, id, object_id)
    
    return [id, object_id]

class GetMedia(webapp2.RequestHandler):
  def get(self):
    self.response.write("This is a test")

"""dbTest"""
class DbTest(webapp2.RequestHandler):
  def get(self):
    my_id = random.randint(0,1000000)
    new_key = db.Key.from_path('InstagramMedia', my_id)
    instance = InstagramMedia(key=new_key)
    instance.loc = 'test'
    instance.created = 1
    instance.link = 'test'
    instance.low = 'test'
    instance.high = 'test'
    instance.lat = 43.1
    instance.lon = -73.1
    #store
    instance.put()
    self.response.write("Wrote a test doc")

"""utility functions"""
def media_key(media_name= None):
  """ Constructs a media key for media."""
  return db.Key.from_path("Media", media_name or "default_media")

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/delete', Delete),
                               ('/listsubscriptions', ListSubscriptions),
                               ('/retrieve', Retrieve),
                               ('/stream', Subscription),
                               ('/getmedia', GetMedia),
                               ('/dbtest', DbTest)
                               ],
                              debug=True)