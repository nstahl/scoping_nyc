from datetime import datetime, timedelta
import json
import logging
import time
import urllib
import webapp2

from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api import urlfetch

class RetrieveMedia(webapp2.RequestHandler):
  # Get: 
  # loc: location for the request
  # lastseen: last successful time this client did a request
  """Example:
  localhost:8000/getmedia?loc=newyork&lastseen=1361405226
  """
  def get(self):
    loc = self.request.get("loc").lower()
    lastseen = int(self.request.get("lastseen"))
    logging.info('Location: %s, Lastseen: %s', loc, lastseen)
    q = db.GqlQuery("SELECT * FROM InstagramMedia LIMIT 500")
    self.response.headers.add_header("Access-Control-Allow-Origin", "*")
    self.response.out.write(json.dumps({'results': [p.to_dict() for p in q if p.created > lastseen]}))
