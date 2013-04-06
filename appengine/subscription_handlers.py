import app_constants

import json
import logging
import time
import urllib
import webapp2

from google.appengine.ext import db
from google.appengine.api import urlfetch

class LocationInfo(db.Model):
  """ Models a location and everything we want to keep about it """
  object_id = db.StringProperty(indexed = False)  # Object Id of the subscription
  id = db.StringProperty(indexed = False)  # id of the subscription
  loc = db.StringProperty(indexed = False)
  date = db.DateTimeProperty(auto_now_add=True, indexed = False)
  def to_dict(self):
    return dict([(p, unicode(getattr(self, p))) for p in self.properties()])  

class ListSubscriptions(webapp2.RequestHandler):
  """ Lists the subscriptions that SnapCity app has on the Instagram Server.
      The response is the response that we get from Instagram.

      Example usage: http://localhost:8080/listsubscriptions
  """
  def get(self):
    form_fields = {
      'client_id': app_constants.CLIENT_ID,
      'client_secret' : app_constants.CLIENT_SECRET
      }
    form_data = urllib.urlencode(form_fields)
    result = urlfetch.fetch(url='%s?%s'%(app_constants.SUBSCRIPTION_URL,form_data),
                            method=urlfetch.GET)
    json_data = json.loads(result.content)
    logging.info("List of subscribers:%s", json.dumps(json_data,indent=2))
    self.response.write("<pre>")
    self.response.write(json.dumps(json_data,indent=2))
    self.response.write("</pre>")

class DeleteSubscriptions(webapp2.RequestHandler):
  """ Deletes subscriptions both from Instagram and from the DB we keep.
      You can delete single subscriptions by providing the id, or
      you can delete all the subscriptions.
      Parameters:
      id : id of the subscription you want to delete.
           if you omit id, or set id to all, it will delete all subscriptions.

      Example usage: http://localhost:8080/deletesubscriptions?id=all
    
      This class does the same thing both for get or post requests.
  """
  def get(self):
    return self.post()

  def post(self):
    id = self.request.get('id').lower()
    if not id:
      id = 'all'    
    self.response.headers['Content-Type'] = 'text/plain'
    if self._delete_subscriber(id):
      self.response.write('Deleted subscriptions for %s'%id)
    else:
      self.response.write('Failed to delete subscriptions for %s'%id)
  
  def _delete_subscriber(self, id):
    form_fields = {
      'client_id': app_constants.CLIENT_ID,
      'client_secret' : app_constants.CLIENT_SECRET,
      }
    if id == "all":
      form_fields["object"] = "all"
    else:
      form_fields['id'] = id
 
    form_data = urllib.urlencode(form_fields)
    logging.info("Calling delete with: %s", form_data)
    result = urlfetch.fetch(url='%s?%s'%(app_constants.SUBSCRIPTION_URL, form_data),
                            method=urlfetch.DELETE)
    json_data = json.loads(result.content)
    logging.info("Delete returned:%s", json.dumps(json_data,indent=2))
    if json_data["meta"]["code"]!= 200 :
      logging.info("Status code not 200: %s", result.content)
      return False
    return True

class MakeSubscription(webapp2.RequestHandler):
  """ Makes a subscription for a location. 
      Only certain locations are supported.

      Example usage:
      http://localhost/makesubsciption?loc=newyork
  """
  def get(self):
    loc = self.request.get('loc').lower()
    return_msg = ''
    if loc not in app_constants.GEOCODES:
      return_msg = 'Error: \'%s\' is not a recognized location\n'%loc
      return_msg += 'This app only works with %s'%app_constants.MATCHERS.keys()
    else:
      response_arr = self._register_subscriber(loc)
      if response_arr:
        #store it
        db_id = int(time.mktime(time.gmtime()))
        new_key = db.Key.from_path('LocationInfo', db_id)
        locsub = LocationInfo(key=new_key)
        locsub.id = response_arr[0]
        locsub.object_id = response_arr[1]
        locsub.loc = loc
        locsub.put()
        return_msg = 'Made subscription with id:%s for loc:%s '%(str(response_arr[0]),loc) 
      else:
        return_msg = 'Failed to make subscription'
    self.response.headers['Content-Type'] = 'text/plain' 
    self.response.write(return_msg)

  def _register_subscriber(self, loc):
    form_fields = {
      'client_id': app_constants.CLIENT_ID,
      'client_secret' : app_constants.CLIENT_SECRET,
      'verify_token' : app_constants.VERIFY_TOKEN, 
      'object' : 'geography',
      'aspect' : 'media',
      'lat' : app_constants.GEOCODES[loc][0], 
      'lng' : app_constants.GEOCODES[loc][1],
      'radius' : '5000',
      'callback_url' : 'http://snapcity02.appspot.com/stream'
      }
    form_data = urllib.urlencode(form_fields)
    #post to instagram
    result = urlfetch.fetch(url=app_constants.SUBSCRIPTION_URL,
                            payload=form_data,
                            method=urlfetch.POST)
          
    if result.status_code != 200:
      logging.info("Status code not 200, it is %s: %s", result.status_code, result.content)
      return
    #success,some info about the subscription follows
    data = json.loads(result.content)
    object_id = data["data"]["object_id"]
    id = data["data"]["id"]
    logging.info("Registered subscriber for loc:%s, id:%s and object_id:%s", loc, id, object_id)
    return [id, object_id]

class Helper(object):
  @staticmethod  
  def getLocation():
    locsubs = db.GqlQuery("SELECT * FROM LocationInfo")
    if not locsubs.count():
      logging.error('Cannot fetch. No current subscription')
      return
    return locsubs[0]
