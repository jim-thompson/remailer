'''
Created on Jan 31, 2021

@author: jct
'''

import re
from imap import IMAPInterface
from quopri import decodestring
from email.parser import BytesParser
from email.policy import default

from creds import RemailerCreds

from tagscan import scan_for_tags
from rfc5322 import email_regex_bytes

incoming_folder = 'INBOX'
exception_folder = 'INBOX.remailer-exception'
sent_folder = 'INBOX.remailer-sent'
original_folder = 'INBOX.remailer-original'
notag_folder = 'INBOX.remailer-original-notag'

email_prog = re.compile(email_regex_bytes)

class Remailer:
    def __init__(self, connection):
        self._cxn = connection
        
    def _validateFolder(self, folder_name):
        typ, [response] = self._cxn.select(folder_name)
        if typ != 'OK':
            raise RuntimeError(response)
    
    def validateFolderStructure(self):
        self._validateFolder(incoming_folder)
        self._validateFolder(exception_folder)
        self._validateFolder(sent_folder)
        self._validateFolder(original_folder)
        self._validateFolder(notag_folder)
        
    def getAllFolderUIDs(self, folder):
        typ, [response] = self._cxn.select(folder)
        if typ != 'OK':
            raise RuntimeError(response)
        
        typ, response = self._cxn.uid('search', None, 'ALL')
        
        if typ != 'OK':
            raise RuntimeError(response)
        
        message_uids = response[0].split()
        
        return message_uids
    
    def fetchMessageUIDAsBytes(self, message_uid):
        
        # Fetch the contents of the message
        typ, data = self._cxn.uid('fetch', message_uid, '(RFC822)')

        if typ != 'OK':
            raise RuntimeError(data)

        # The message date comes in as a bytestring. Resist the temptation
        # to decode it into a UTF-8 string.
        message_bytes = data[0][1]
        
        return message_bytes
    
    def checkIMAPResponse(self, code, response):
        if code != 'OK':
            raise RuntimeError(response)
    
    def copyMessageUID(self, message_uid, destination_folder):
        print('Copying message <%s> to folder <%s>' % (message_uid, destination_folder))

        typ, [response] = self._cxn.uid('copy', message_uid, destination_folder)
        self.checkIMAPResponse(typ, response)
         
        typ, [response] = self._cxn.uid('store', message_uid, '+FLAGS', r'(\Deleted)')
        self.checkIMAPResponse(typ, response)
    
        typ, [response] = self._cxn.expunge()
        self.checkIMAPResponse(typ, response)
 
        
    def messagBytesAsObject(self, message_bytes):
        # Parse the message string into a message object for easier
        # handling. 
        message_obj = BytesParser(policy=default).parsebytes(message_bytes)
     
        return message_obj
    
    def maybeQuotedPrintableToBytestring(self, bytes_):
        if bytes_ is not None:
            return decodestring(bytes_)
        return ""
    
    def scanMessageForRemailTags(self, message_bytes):
        
        # This list will be used to return the found email addresses.
        remail_addresses = []
        
        # Find all the tags in the message.
        message_bytes, tags = scan_for_tags(message_bytes)
        
        for tag_tuple in tags:
            
            # Break the tuple into tag and value
            tag, value = tag_tuple
            
            # Because these might be quoted-printable encoded, decode into
            # plain bytestrings
            tag = self.maybeQuotedPrintableToBytestring(tag)
            value = self.maybeQuotedPrintableToBytestring(value)
            
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
    
    def dumpHeaders(self, message_obj):
        print("-------------------------------------------------------------")
        headers = message_obj.items()
        
        for (key, value) in headers:
            print("key <%s>: value <%s>" % (key, value))
            
    def maybeSetHeader(self, message_obj, key, value):
        if value is not None:
            message_obj[key] = value
        
    def deleteAllHeaders(self, message_obj):
        keys = message_obj.keys()
         
        for k in keys:
            del message_obj[k]
            
    def mutateHeaders(self, message_obj):
        
        date = message_obj["Date"]
        subject = message_obj["Subject"]
        mime_version = message_obj["MIME-Version"]
        content_type = message_obj["Content-Type"]
        x_infapp = message_obj["X-InfApp"]
        x_infcontact = message_obj["X-InfContact"]
        x_campaignid = message_obj["X-campaignid"]

        self.deleteAllHeaders(message_obj)
        
        self.maybeSetHeader(message_obj, "Date", date)
        self.maybeSetHeader(message_obj, "Subject", subject)
        self.maybeSetHeader(message_obj, "MIME-Version", mime_version)
        self.maybeSetHeader(message_obj, "Content-Type", content_type)
        self.maybeSetHeader(message_obj, "X-InfApp", x_infapp)
        self.maybeSetHeader(message_obj, "X-InfContact", x_infcontact)
        self.maybeSetHeader(message_obj, "X-campaignid", x_campaignid)
        
    def doThemAll(self):
        
        message_uids = self.getAllFolderUIDs(incoming_folder)
        
        print("%d unread messages in <%s>" %(len(message_uids), incoming_folder))
        
        # Loop through all the messages in the inbox.
        for message_uid in message_uids:
            
            message_bytes = self.fetchMessageUIDAsBytes(message_uid)
#             print(message_bytes.decode('utf-8'))
            
            message_bytes, remail_addresses = \
                self.scanMessageForRemailTags(message_bytes)
                
            if len(remail_addresses) > 0:
                
                # We found at least one valid remail-to tag, so the original
                # message should be move to the originals folder.
                self.copyMessageUID(message_uid, original_folder)
                
                # The message in message_bytes has already had the tags
                # removed from it. That's the first step to constructing
                # the base message. The second part is to strip most of
                # the original headers and add our new headers. That's
                # easiest to do with a message object. Create one now.
                message_obj = self.messagBytesAsObject(message_bytes)
                
                self.mutateHeaders(message_obj)
                self.dumpHeaders(message_obj)
                
                # re-mail to the addresses
                
            
            else:
                # No addresse to remail to - move the original message to the
                # original-notag folder
                self.copyMessageUID(message_uid, notag_folder)
                
                # print("%s" % message_obj['Subject'])
                pass

if __name__ == '__main__':
    imap_creds = RemailerCreds()
    
    imap_service = { "server_addr": "imap.domain.com",
                     "port": 993 }

    imap_interface = IMAPInterface()
    imap_interface.readyService(imap_service, imap_creds)
    
    cxn = imap_interface.getServer()
    remailer = Remailer(cxn)
    
    remailer.validateFolderStructure()

    try:
        remailer.doThemAll()
        
        print("Done.")
        # Find the "SEEN" messages in INBOX
#         typ, [response] = cxn.select(incoming_folder)
#         if typ != 'OK':
#             raise RuntimeError(response)
#          
#         typ, response = cxn.uid('search', None, 'UNSEEN')
#          
#         if typ != 'OK':
#             raise RuntimeError(response)
#          
#         message_ids = response[0].split()
#         print("%d unread messages in <%s>" %(len(message_ids), incoming_folder))
         
#         for message_id in response[0].split():
#         for message_id in message_ids:
#             typ, data = cxn.fetch(message_id, '(RFC822)')
#             typ, data = cxn.uid('fetch', message_id, '(RFC822)')
#             print(b'Message %s\n%s\n' % (message_id, data[0][1]))
 
#             message_str = data[0][1].decode("utf-8")
#             message_obj = Parser(policy=default).parsestr(message_str)
#             print("%s" % message_obj['Subject'])
             
            # Create a new mailbox, "Archive.Today"
#             msg_ids = b','.join(response.split(b' '))
             
#             # Copy the messages
#             print('Copying:', msg_ids)
#             typ, [response] = cxn.uid('copy', message_id, sent_folder)
#               
#             typ, response = cxn.uid('store', message_id, '+FLAGS', r'(\Deleted)')
#             typ, response = cxn.expunge()
 
         
    finally:   
        cxn.close()
        cxn.logout()
