import tagfilter

CLIENT_ID = 'YOUR INSTAGRAM CLIENT ID'
CLIENT_SECRET = 'YOUR INSTAGRAM CLIENT SECRET'
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
