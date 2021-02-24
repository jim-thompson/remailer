'''
Created on Feb 4, 2021

@author: jct
'''

import re

from quopri import decodestring
from email.parser import BytesParser
from email.policy import default

from rfc5322 import email_prog
from centraltime import centraltime_str
from tagscan import scan_for_tags

def messageBytesAsObject(message_bytes):
    # Parse the message string into a message object for easier
    # handling. 
    message_obj = BytesParser(policy = default).parsebytes(message_bytes)
 
    return message_obj

def showMessageSubject(message_bytes):
    message_obj = messageBytesAsObject(message_bytes)
    print("Subject:", message_obj["Subject"])

def maybeQuotedPrintableToBytestring(bytes_):
    if bytes_ is not None:
        return decodestring(bytes_)
    return ""

def scanPartForTruncateTags(message_str):
    
    tag_index = message_str.find('${message-ends}')

    if (tag_index) != -1:
        message_str = message_str[0:tag_index]
        
    return message_str

def scanPartForRemailTags(message_str):
    
    # This list will be used to return the found email addresses.
    remail_addresses_set = set()
    
    # Find all the tags in the message.
    message_str, tags = scan_for_tags(message_str)
    
    for tag_tuple in tags:
        
        # Break the tuple into tag and value
        tag, value = tag_tuple
        
        # Because these might be quoted-printable encoded, decode into
        # plain bytestrings
#         tag = maybeQuotedPrintableToBytestring(tag)
#         value = maybeQuotedPrintableToBytestring(value)
        
        # We're only interested in remail-to tags.
        if tag == 'remail-to':
            
            # Test the value of the tag to see if it looks like an email
            # address.
            match = email_prog.match(value)
            
            if match is not None:
                
                # We have a remail-to tag with a valid email address. Now
                # we simply append the email address to the list of
                # remail addresses.
                remail_addresses_set.add(match.group(0))
                
    return message_str, remail_addresses_set

def dumpHeaders(message_obj):
    print("  -------------------------------------------------------------")
    headers = message_obj.items()
    
    for (key, value) in headers:
        print("  %s: %s" % (key, value))
        
def maybeSetHeader(message_obj, key, value):
    if value is not None:
        message_obj[key] = value
    
def deleteAllHeaders(message_obj):
    keys = message_obj.keys()
     
    for k in keys:
        del message_obj[k]
        
def mutateHeaders(message_obj, from_str):
    
#     date = message_obj["Date"]
    date = centraltime_str()
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
    
    message_obj["From"] = from_str
        