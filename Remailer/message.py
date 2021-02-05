'''
Created on Feb 4, 2021

@author: jct
'''

import re

from quopri import decodestring
from email.parser import BytesParser
from email.policy import default

from rfc5322 import email_regex_bytes
from tagscan import scan_for_tags

email_prog = re.compile(email_regex_bytes)

def messageBytesAsObject(message_bytes):
    # Parse the message string into a message object for easier
    # handling. 
    message_obj = BytesParser(policy=default).parsebytes(message_bytes)
 
    return message_obj

def maybeQuotedPrintableToBytestring(bytes_):
    if bytes_ is not None:
        return decodestring(bytes_)
    return ""

def scanMessageForRemailTags(message_bytes):
    
    # This list will be used to return the found email addresses.
    remail_addresses = []
    
    # Find all the tags in the message.
    message_bytes, tags = scan_for_tags(message_bytes)
    
    for tag_tuple in tags:
        
        # Break the tuple into tag and value
        tag, value = tag_tuple
        
        # Because these might be quoted-printable encoded, decode into
        # plain bytestrings
        tag = maybeQuotedPrintableToBytestring(tag)
        value = maybeQuotedPrintableToBytestring(value)
        
        # We're only interested in remail-to tags.
        if tag == b'remail-to':
            
            # Test the value of the tag to see if it looks like an email
            # address.
            match = email_prog.match(value)
            
            if match is not None:
                
                # We have a remail-to tag with a valid email address. Now
                # we simply append the email address to the list of
                # remail addresses.
                remail_addresses.append(match.group(0))
                
    return message_bytes, remail_addresses

def dumpHeaders(message_obj):
    print("-------------------------------------------------------------")
    headers = message_obj.items()
    
    for (key, value) in headers:
        print("%s: %s" % (key, value))
        
def maybeSetHeader(message_obj, key, value):
    if value is not None:
        message_obj[key] = value
    
def deleteAllHeaders(message_obj):
    keys = message_obj.keys()
     
    for k in keys:
        del message_obj[k]
        
def mutateHeaders(message_obj):
    
    date = message_obj["Date"]
    subject = message_obj["Subject"]
    mime_version = message_obj["MIME-Version"]
    content_type = message_obj["Content-Type"]
    x_infapp = message_obj["X-InfApp"]
    x_infcontact = message_obj["X-InfContact"]
    x_campaignid = message_obj["X-campaignid"]

    deleteAllHeaders(message_obj)
    
    maybeSetHeader(message_obj, "Date", date)
    maybeSetHeader(message_obj, "Subject", subject)
    maybeSetHeader(message_obj, "MIME-Version", mime_version)
    maybeSetHeader(message_obj, "Content-Type", content_type)
    maybeSetHeader(message_obj, "X-InfApp", x_infapp)
    maybeSetHeader(message_obj, "X-InfContact", x_infcontact)
    maybeSetHeader(message_obj, "X-campaignid", x_campaignid)
        