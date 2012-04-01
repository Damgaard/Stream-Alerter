#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
# vi:ts=4:et
# $Id: test.py,v 1.17 2007/04/10 13:25:17 kjetilja Exp $
#
# ##################################
#              INFO
# ##################################
#
# Andreas Damgaard Pedersen
# 3 December 2011
# 
# Program to retrieve all online starcraft streams from JustinTv and Own3d.
# Notify people either through posting a tweet or pop up on screen, 
# when either a great streamer starts streaming or any stream hit a noteworthy
# stream viewer amount. Thus allowing for easy discovery of events,
#
#
# ##################################
#         Would - be - nice
# ################################### 
# 
# Clean up imports
# Insert user agent to pycurl request
#
# Write a "Am I rate blocked" function, to call in case of not getting any Justin Streams
#   - http://support.twitch.tv/discussion/39/api-rate-limit/p1
#
# Maybe something similair for Own3d Streams
#
# Differentiate between great strem coming online and ungreat strem hitting bottom view tier
# Fewer but more significant messages sounds like a good idea

import sys, os, re, time, pycurl, StringIO

# Twitter related
import twitter

# For pop-up messages
import commands

# Url Shortener
import gflags
import httplib2
import logging

# For error-bandling
import urllib2

# ###################
#  Global Variables
# ###################

user_agent = "StreamAlertSC2 From: kontakt@kneat.dk"

# Twitter authentication values
from twitterAut import *

# Views required to get a tweet
twitViews = [2000, 4000, 6000, 8000, 10000, 12500, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000, 999999999]

# How long can the tweets be? How long can the title be? How many seconds sleep between cycles?
maxTweetLen, maxTitle, runTime = 130, 60, 60

# ErrorTime = How long we have had an error. = 0 if no error
# OfflineTime = How many seconds must a stream be offline, before we can declare it has "just started streaming?"
# greatStreamLevel = Number of views to be declared great stream
errorTime, offlineTime, greatStreamLevel = 0, 900, 4000

# Streams great enough to notify everyone when they go online, irrespectives of view count
# Should make it auto retrieve values from the output file
greatStreams = eval(open('twitOutput.txt', 'r').readlines()[0])

# Streamers and last acheived benchmarcks
knownStreams = eval(open('twitOutput.txt', 'r').readlines()[2])

cookieFile = ""

# ###################
#
#  Functions
#
# ###################

def getCookie((url, postData)):
    curlobj=pycurl.Curl()
    curlobj.setopt(pycurl.URL, url)
    curlobj.setopt(pycurl.POSTFIELDS, postData)
    curlobj.setopt(pycurl.COOKIEFILE, cookieFile)
    curlobj.setopt(pycurl.COOKIEJAR, cookieFile)
    curlobj.perform()
    curlobj.close()
    return True

def getHTML(url):
    strio=StringIO.StringIO()
    curlobj=pycurl.Curl()
    curlobj.setopt(pycurl.URL, url)
#   curlobj.setopt(pycurl.COOKIEFILE, cookieFile)
    curlobj.setopt(pycurl.WRITEFUNCTION, strio.write)
    curlobj.perform()
    curlobj.close()
    return strio.getvalue()

def urlShortener(end_url):
    storage = Storage('urlshortener.dat')
    credentials = storage.get()
    if credentials is None or credentials.invalid:
    	credentials = run(FLOW, storage)
    # Create an httplib2.Http object to handle our HTTP requests and authorize it
    # with our good Credentials.
    http = httplib2.Http()
    http = credentials.authorize(http)
    service = build("urlshortener", "v1", http=http)

    try:
    	url = service.url()

    	# Create a shortened URL by inserting the URL into the url collection.
    	body = {"longUrl": end_url }
    	resp = url.insert(body=body).execute()

    	short_url = resp['id']
    	return short_url

    except AccessTokenRefreshError:
    	print ("The credentials have been revoked or expired, please re-run"
          "the application to re-authorize")
        return None

# ##################
#    Main Loop
# ##################

tweetMessage = False;
popMessage = True;

def tweetMes(toTweet):
    streamStart = " is now streaming! Click on the link to watch! "
    streamIncrease1 = " has now hit "
    streamIncrease2 = " viewers! Click on the link to watch! "
    
    for stream in toTweet:
        shortUrl = urlShortener(stream[2])
        tweet = ""
        if twitViews.index(stream[1]) == 0:
            tweet += streamStart + shortUrl
        else:
            tweet += streamIncrease1 + str(stream[1]) + streamIncrease2 + shortUrl

        if (maxTweetLen - len(tweet)) < maxTitle: remainder = maxTweetLen - len(tweet)
        else: remainder = maxTitle

        name = stream[0][:remainder]
        if len(stream[0]) > remainder:
            name = str(stream[:remainder-3])+"..."

        # Streamer using default naming ಠ_ಠ
        if "Broadcasting LIVE" in name or "Untitled Broadcast" in name:
            name = stream[3]

        print "Tweeting:", eval('u"'+(stream[0][:remainder] + tweet) + '"')
        status = api.PostUpdate(eval('u"'+(stream[0][:remainder] + tweet) + '"'))

def popMes(toTweet):
    streamStart = " is now streaming!! "
    streamIncrease1 = " has now hit "
    streamIncrease2 = " viewers!! "
   
    for stream in toTweet:
        tweet = ""
        if twitViews.index(stream[1]) == 0:
            tweet += streamStart
        else:
            tweet += streamIncrease1 + str(stream[1]) + streamIncrease2

        # Remove quotes to prevent messups in the command
        tweet = "%s %s" % (stream[0], tweet)
        tweet = tweet.replace('"', "")
        tweet = tweet.replace("'", "")

    	command = "zenity --info --text '%s'" % tweet
        print command
    	commands.getstatusoutput(command)  

def detectStream():
    global knownStreams
    try:
        # No Error. Resetting error time
        errorTime = 0
        result = []

        # Step 1
        # Retrieve streamer list from JustinTv ( TwitchTV )
        xml = getHTML("http://api.justin.tv/api/stream/list.xml?meta_game=StarCraft%20II:%20Wings%20of%20Liberty")
        Jstreams = xml.split("<stream>")[1:]
        for stream in Jstreams:
            a = re.search("(?<=<title>)(.*?)(?=</title>)", stream)
            b = re.search("(?<=<channel_count>)(.*?)(?=</channel_count>)", stream)
            c = re.search("(?<=<login>)(.*?)(?=</login>)", stream)
            if a != None and b != None and c != None:
                result.append([a.groups()[0], eval(b.groups()[0]), "http://www.twitch.tv/" + c.groups()[0], c.groups()[0], time.time()])

        lenJStream = len(result)

        # Step 2
        # Retrieve streamer list from Own3d
        xml = getHTML("http://api.own3d.tv/live?game=sc2")
        Ostreams = xml.split("<item>")[1:]
    
        for stream in Ostreams:
            a = re.search("(?<=<title><\!\[CDATA\[)(.*?)(\]\])", stream)
            b = re.search('(?<=viewers=")(\d*?)(")', stream)
            c = re.search('(?<=<link>)(.*?)(</link>)', stream)
            d = re.search('(?<=<media:credit>)(.*?)(</media:credit>)', stream)
            if a != None and b != None and c != None and d != None:
                result.append([a.groups()[0], eval(b.groups()[0]), c.groups()[0], d.groups()[0], time.time()])

        # Step 3
        # Join the two list together and sort them by viewers
        result = sorted(result, key=lambda resul : resul[1], reverse=True)

        print "JStreams Found: ", lenJStream
        print "OStreams Found: ", len(result) - lenJStream

        # Step 4
        # Test if any of the streams fulfill requirements to make a tweet
        knownStreamsLink = []
        for stream in knownStreams: 
            knownStreamsLink.append(stream[2])

        toTweet = []
        newKnownStreams = []
    
        for stream in result:
            onlineLast = False
            if stream[2] in knownStreamsLink:
                onlineLast = knownStreams[knownStreamsLink.index(stream[2])][4]  + offlineTime > stream[4]
            if stream[2] in greatStreams and not onlineLast:
                toTweet.append([stream[0], twitViews[0]] + stream[2:])
                newKnownStreams.append([stream[0], twitViews[0]] + stream[2:])
            elif onlineLast:
                lastBench = knownStreams[knownStreamsLink.index(stream[2])][1]
                if stream[1] > greatStreamLevel and stream[2] not in greatStreams: 
                    greatStreams.append(stream[2])
                 # Stream crashed within offlineTime
                if lastBench == 0:                     
                    # Maybe start with their last acheived view count?
                    newKnownStreams.append([stream[0], twitViews[0]] + stream[2:])
                elif stream[1] > twitViews[twitViews.index(lastBench)+1]:
                    toTweet.append([stream[0], twitViews[twitViews.index(lastBench)+1]] + stream[2:])
                    newKnownStreams.append([stream[0], twitViews[twitViews.index(lastBench)+1]] + stream[2:])
                else:
                    newKnownStreams.append([stream[0], lastBench] + stream[2:])
            else:
                # Bottom tier broken
                if stream[1] > twitViews[0]:
                    toTweet.append([stream[0], twitViews[0]] + stream[2:])
                    newKnownStreams.append([stream[0], twitViews[0]] + stream[2:])
    
        onStream = []
        for stream in newKnownStreams:
            onStream.append(stream[2])

        for stream in knownStreams:
            if stream[2] not in onStream:
                newKnownStreams.append([stream[0], 0] + stream[2:])

        knownStreams = newKnownStreams
  
        # Step 6.
        # Either/or tweet/message the information
        if tweetMessage: 
            tweetMes(toTweet)

        if popMessage:
            popMes(toTweet)
   
    except urllib2.URLError as error:
        if errorTime == 0:
            print error
            print "Urllib Error. Eg Problem with the internet"
        else:
            print "Error has been ongoing for %d minutes." % errorTime

    except pycurl.error as error:
        if errorTime == 0:
            print error
            print "Pycurl error. Eg problem with the internet"
        else:
            print "Error has been ongoing for %d minutes." % errorTime

    # Step 7
    # Save variables to protect from crashes, wait some time, then go to step 1
    with open("twitOutput.txt", "w") as output:
        output.write(str(greatStreams)+"\n\n")
        output.write(str(knownStreams))

    print "Sleeping %d seconds" % runTime
    time.sleep(runTime)

if __name__ == "__main__":
    api = twitter.Api(consumer_key=cKey, consumer_secret=cSecret, access_token_key=aT, access_token_secret=aTs)
    while 1:
        detectStream()
    
