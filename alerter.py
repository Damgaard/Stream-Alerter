#!/usr/bin/env python

"""
Notifies when great or unknown popular SC2 streamers go online

Created by Andreas Damgaard Pedersen
27 April 2012
"""

import commands
import cPickle
import httplib2
import sys
import time
from itertools import chain
from os.path import exists

import requests
import logging
import twitter
from bs4 import BeautifulSoup
# Google id required imports
from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools import run

from twitterAut import (cKey, cSecret, aT, aTs, FLOW)
from settings import (DB_FILE, DELAY_BETWEEN_RUNS, MIN_VIEWERS,
                      TWEET_LEN, WAIT_TIME)

api = twitter.Api(consumer_key=cKey, consumer_secret=cSecret, 
                  access_token_key=aT, access_token_secret=aTs)
great_streams = []
online_streams = []

def urlShortener(end_url):
    """Takes a url and return a url that will redirect a user to the real url
       using re-direct. This redirection (and the code) is provided by google"""
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

def justin_streams():
    """Generator that returns Justin.Tv streams in a dictionary"""
    # The Justin and Own3d generators could be combined into one 
    # Generator, but it would be at a too steep readability cost.
    xml = requests.get("http://api.justin.tv/api/stream/list.xml?meta_game=StarCraft%20II:%20Wings%20of%20Liberty")
    soup = BeautifulSoup(xml.text)
    for stream in soup.findAll('stream'):
        new_stream = {}
        new_stream['id'] = "J-"+stream.id.text
        new_stream['author'] = stream.channel.login.text
        new_stream['title'] = stream.title.text
        new_stream['viewers'] = int(stream.channel_count.text)
        new_stream['url'] = stream.channel.channel_url.text
        new_stream['host'] = 'justin'
        yield new_stream

def own3d_streams():
    """Generator that returns own3d streams in a dictionary"""
    xml = requests.get("http://api.own3d.tv/live?game=sc2")
    soup = BeautifulSoup(xml.text)
    for stream in soup.findAll('item'):
        new_stream = {}
        new_stream['id'] = "O-"+stream.link.text.split('/')[-1]
        new_stream['author'] = stream.title.text
        new_stream['title'] = ""
        new_stream['viewers'] = int(stream.misc['viewers'])
        new_stream['url'] = stream.link.text
        new_stream['host'] = 'own3d'
        yield new_stream

def is_notify_worthy(stream):
    """Finds out whether this stream is worthy of notifying me"""
    return (stream['id'] in great_streams or
            stream['viewers'] > MIN_VIEWERS)

def already_notified(stream):
    """Find out if theres already been sent out a notification"""
    for known_stream, last_seen in online_streams:
        if known_stream['id'] == stream['id']:
            return time.time() -  last_seen < WAIT_TIME
    return False

def clean(message):
    """Take a string, return it without error causing chars and in proper
       ascii encoding"""
    bad_chars = "'\"`"
    message = "".join(c for c in message if c not in bad_chars)
    return (message.encode('ascii', 'replace'))

def notify(stream, msg_tweet=False, msg_popup=True):
    """Notify using either yad or twitter

       the bools msg_tweet and msg_popup dictate whether we
       are going to notify over twitter / yad respectively
       """
    if stream['title'] != "":
        message = clean("%s by %s." % (stream['title'], stream['author']))
    else:
        message = clean("%s now streaming." % stream['author'])
    if msg_popup:
        text = "yad --title='Stream Online' --text='%s'" % message
        print text
        status, output = commands.getstatusoutput(text)
    if msg_tweet:
        text = "%s" % message
        shorturl = urlShortener(stream['url'])
        if shorturl != None:
            text = text[:TWEET_LEN-len(shorturl)+1] + " " + shorturl
        else:
            print >> sys.stderr, "WARNING! Googles urlShortener is not working!"
            text = text[:TWEET_LEN]
        status = api.PostUpdate(text)
    print message

def main():
    if exists(DB_FILE):
        with open(DB_FILE, 'rb') as db_file:
            great_streams = pickle.load(db_file)
    while True:
        start = time.time()
        for stream in chain(justin_streams(), own3d_streams()):
            if is_notify_worthy(stream) and not already_notified(stream):
                notify(stream)
                online_streams.append((stream, time.time()))
        print "Iteration done. Waiting %d seconds" % (start + DELAY_BETWEEN_RUNS
                                                            - time.time())
        time.sleep(start + DELAY_BETWEEN_RUNS - time.time())

if __name__ == "__main__":
    main()
