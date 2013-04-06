
/**
 * Module dependencies.
 */

var express = require('express')
  , routes = require('./routes')
  , user = require('./routes/user')
  , http = require('http')
  , twitter = require('ntwitter')
  , path = require('path');


/**
 * Server.
 */

var app = express();

app.configure(function(){
  app.set('port', process.env.PORT || 3000);
  app.use(express.favicon());
  app.use(express.logger('dev'));
  app.use(express.bodyParser());
  app.use(express.methodOverride());
  app.use(app.router);
  app.use(express.static(path.join(__dirname, 'public')));
});

app.configure('development', function(){
  app.use(express.errorHandler());
});

app.get('/', function(req, res)
    {
      res.sendfile("map.html");
    });

var server = http.createServer(app).listen(app.get('port'), function(){
  console.log("Express server listening on port " + app.get('port'));
});

/**
 * Twitter Stream
 */
var io = require('socket.io').listen(server);


io.sockets.on('connection', function (socket) {

  console.log("CONNECTION OPENED");
  
  socket.on('changeTweetBoundingBox', function (data) {
    twitterStream.destroy();
    locationJSON['locations'] = [ data["west"], data["south"], data["east"], data["north"] ].join(',');
    console.log(locationJSON);
    setupStream();
  });

});

//insert credentials here
var twit = new twitter({
  consumer_key: 'hcsmaFNG3R7Kvf3BLkrOg',
  consumer_secret: 'vunmX4lbDYaslRb6oPfayvQ5C1A9JqAYgZhA1erSY0',
  access_token_key: '703310240-qOg6hW963sTRwIKwbFVKyIKULsO4t5GyPzYyUpAo',
  access_token_secret: 'tfnC8fR9FtyEPiaPnPVboAWLcg29se5AO65Usx7lUME'
});


//nyc bounding box
var locationJSON = {'locations':'-74.036,40.67,-73.9,40.84'};

var twitterStream;
setupStream();


function setupStream() {
//define stream
twit.stream('statuses/filter', locationJSON, function(stream) {
  twitterStream = stream;
  stream.on('data', function (data) {

    //prep for regex
    var text = data.text.toLowerCase();
    //check that coordinate data is in fact included
    //var regex = /I\'m at|http|street|block|dark|light|loud|quiet|walk|park|city|neighborhood|building|creative/;

    if((data.geo !== null)) { //&& (regex.exec(data.text) !== null)) {
      var newTweetObj = { 
        user: data.user.screen_name, 
        text: data.text,
        lat: data.geo.coordinates[0],
        lon: data.geo.coordinates[1],
        time: data.created_at
      };
      console.log(newTweetObj);
      io.sockets.volatile.emit('tweet', newTweetObj);
    }
  });

  stream.on('end', function (response) {
    console.log("\n====================================================");
    console.log("DESTROYING");
    console.log("====================================================\n");
  });

});





}

