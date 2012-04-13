#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# ##################################
#              INFO
# ##################################
#
# Created by Andreas Damgaard Pedersen
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
# Differentiate between great strem coming online and ungreat strem hitting bottom view tier
# Fewer but more significant messages

import commands
import os
import pycurl
import re
import StringIO
import sys
import time
import urllib2

import httplib2
import logging
import twitter

user_agent = "StreamAlertSC2 From: andreas@diku.dk"
# Twitter authentication values
from twitterAut import *
# Views required to get a tweet
twitViews = [2000, 4000, 6000, 8000, 10000, 12500, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000, 999999999]
# How long can the tweets be? How long can the title be? How many seconds sleep between cycles?
max_tweet_len, maxTitle, run_time = 130, 60, 60
# OfflineTime = How many seconds must a stream be offline, before we can declare it has "just started streaming?"
# great_stream_level = Number of views to be declared great stream
offlineTime, great_stream_level = 900, 400
# Streams great enough to notify everyone when they go online, irrespectives of view count
# Should make it auto retrieve values from the output file
greatStreams = eval(open('twitOutput.txt', 'r').readlines()[0])
# Streamers and last acheived benchmarcks
known_streams = eval(open('twitOutput.txt', 'r').readlines()[2])

def get_HTML(url):
    strio=StringIO.StringIO()
    curlobj=pycurl.Curl()
    curlobj.setopt(pycurl.URL, url)
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

def tweet_mes(to_tweet):
    """Tweet the string to_tweet after adding header/footer and link to stream"""
    msg_start = " is now streaming! Click on the link to watch! "
    msg_inc_1 = " has now hit "
    msg_inc_2 = " viewers! Click on the link to watch! "
    
    for stream in to_tweet:
        shortUrl = urlShortener(stream[2])
        tweet = ""
        if twitViews.index(stream[1]) == 0:
            tweet += msg_start + shortUrl
        else:
            tweet += msg_inc_1 + str(stream[1]) + msg_inc_2 + shortUrl
        if (max_tweet_len - len(tweet)) < maxTitle: remainder = max_tweet_len - len(tweet)
        else: remainder = maxTitle
        name = stream[0][:remainder]
        if len(stream[0]) > remainder:
            name = str(stream[:remainder-3])+"..."
        # Streamer using default naming ಠ_ಠ
        if "Broadcasting LIVE" in name or "Untitled Broadcast" in name:
            name = stream[3]
        print "Tweeting:", eval('u"'+(stream[0][:remainder] + tweet) + '"')
        status = api.PostUpdate(eval('u"'+(stream[0][:remainder] + tweet) + '"'))

def pop_mes(to_pop):
    """Pop up the string to_pop using zenity after adding header/footer
       Linux only""" 
    msg_start = " is now streaming!! "
    msg_inc_1 = " has now hit "
    msg_inc_2 = " viewers!! "
   
    for stream in to_pop:
        tweet = ""
        if twitViews.index(stream[1]) == 0:
            tweet += msg_start
        else:
            tweet += msg_inc_1 + str(stream[1]) + msg_inc_2
        # Remove quotes to prevent messups in the command
        tweet = "%s %s" % (stream[0], tweet)
        tweet = re.sub("['\"]", "", tweet)

    	command = "zenity --info --text '%s'" % tweet
        print command
    	commands.getstatusoutput(command)  

def detect_stream(pop_message,tweet_message):
    global known_streams
    try:
        result = []
        # Step 1
        # Retrieve streamer list from JustinTv ( TwitchTV )
        xml = get_HTML("http://api.justin.tv/api/stream/list.xml?meta_game=StarCraft%20II:%20Wings%20of%20Liberty")
        streams_justin = xml.split("<stream>")[1:]
        for stream in streams_justin:
            a = re.search("(?<=<title>)(.*?)(?=</title>)", stream)
            b = re.search("(?<=<channel_count>)(.*?)(?=</channel_count>)", stream)
            c = re.search("(?<=<login>)(.*?)(?=</login>)", stream)
            if a != None and b != None and c != None:
                result.append([a.groups()[0], eval(b.groups()[0]), "http://www.twitch.tv/" + c.groups()[0], c.groups()[0], time.time()])

        J_streams_len = len(result)

        # Step 2
        # Retrieve streamer list from Own3d
        xml = get_HTML("http://api.own3d.tv/live?game=sc2")
        streams_own3d = xml.split("<item>")[1:]
    
        for stream in streams_own3d:
            a = re.search("(?<=<title><\!\[CDATA\[)(.*?)(\]\])", stream)
            b = re.search('(?<=viewers=")(\d*?)(")', stream)
            c = re.search('(?<=<link>)(.*?)(</link>)', stream)
            d = re.search('(?<=<media:credit>)(.*?)(</media:credit>)', stream)
            if a != None and b != None and c != None and d != None:
                result.append([a.groups()[0], eval(b.groups()[0]), c.groups()[0], d.groups()[0], time.time()])

        # Step 3
        # Join the two list together and sort them by viewers
        result = sorted(result, key=lambda resul : resul[1], reverse=True)

        print "JustinTV / TwitchTV streams Found: ", J_streams_len
        print "Own3d streams Found: ", len(result) - J_streams_len

        # Step 4
        # Test if any of the streams fulfill requirements to make a tweet
        known_streams_link = []
        for stream in known_streams: 
            known_streams_link.append(stream[2])
        to_tweet = []
        new_known_streams = []
        for stream in result:
            onlineLast = False
            if stream[2] in known_streams_link:
                onlineLast = known_streams[known_streams_link.index(stream[2])][4]  + offlineTime > stream[4]
            if stream[2] in greatStreams and not onlineLast:
                to_tweet.append([stream[0], twitViews[0]] + stream[2:])
                new_known_streams.append([stream[0], twitViews[0]] + stream[2:])
            elif onlineLast:
                lastBench = known_streams[known_streams_link.index(stream[2])][1]
                if stream[1] > great_stream_level and stream[2] not in greatStreams: 
                    greatStreams.append(stream[2])
                 # Stream crashed within offlineTime
                if lastBench == 0:                     
                    # Maybe start with their last acheived view count?
                    new_known_streams.append([stream[0], twitViews[0]] + stream[2:])
                elif stream[1] > twitViews[twitViews.index(lastBench)+1]:
                    to_tweet.append([stream[0], twitViews[twitViews.index(lastBench)+1]] + stream[2:])
                    new_known_streams.append([stream[0], twitViews[twitViews.index(lastBench)+1]] + stream[2:])
                else:
                    new_known_streams.append([stream[0], lastBench] + stream[2:])
            else:
                # Bottom tier broken
                if stream[1] > twitViews[0]:
                    to_tweet.append([stream[0], twitViews[0]] + stream[2:])
                    new_known_streams.append([stream[0], twitViews[0]] + stream[2:])
    
        streams_on = []
        for stream in new_known_streams:
            streams_on.append(stream[2])

        for stream in known_streams:
            if stream[2] not in streams_on:
                new_known_streams.append([stream[0], 0] + stream[2:])
        known_streams = new_known_streams
        # Step 6.
        # Either/or tweet/message the information
        if tweet_message: 
            tweet_mes(to_tweet)
        if pop_message:
            pop_mes(to_tweet)
   
    except urllib2.URLError as error:
            print "Problem with the internet"
            raise error
    except pycurl.error as error:
            print "Problem with the internet"
            raise error

    # Step 7
    # Save variables to protect from crashes
    with open("twitOutput.txt", "w") as output:
        output.write(str(greatStreams)+"\n\n")
        output.write(str(known_streams))

if __name__ == "__main__":
    api = twitter.Api(consumer_key=cKey, consumer_secret=cSecret, access_token_key=aT, access_token_secret=aTs)
    while 1:
        start_time = time.time()
        detect_stream(True, False)
        sleep_time = start_time + run_time - time.time()
        print "Sleeping %d seconds" % sleep_time
        time.sleep(sleep_time)
