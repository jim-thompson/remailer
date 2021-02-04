'''
Created on Jan 31, 2021

@author: jct
'''

import re
from imap import IMAPInterface

from email.parser import Parser
from email.policy import default

from creds import RemailerCreds

from tagscan import scan_for_tags
from rfc5322 import email_regex_str

incoming_folder = 'INBOX'
exception_folder = 'INBOX.remailer-exception'
sent_folder = 'INBOX.remailer-sent'
original_folder = 'INBOX.remailer-original'
notag_folder = 'INBOX.remailer-original-notag'

email_prog = re.compile(email_regex_str)

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
    
    def fetchMessageUIDAsString(self, message_uid):
        
        # Fetch the contents of the message
        typ, data = self._cxn.uid('fetch', message_uid, '(RFC822)')

        if typ != 'OK':
            raise RuntimeError(data)

        # The message date comes in as a bytestring. Convert to a UTF-8
        # string.
        message_str = data[0][1].decode("utf-8")
        
        return message_str
        
    def messagStringAsObject(self, message_str):
        # Parse the message string into a message object for easier
        # handling. 
        message_obj = Parser(policy=default).parsestr(message_str)
     
        return message_obj
    
    def scanMessageForRemailTags(self, message_str):
        
        print(message_str)
        remail_addresses = []
        message_str, tags = scan_for_tags(message_str)
        
        for tag_tuple in tags:
            
            # Break the tuple into tag and value
            tag, value = tag_tuple
            
            # We're only interested in remail-to tags.
            if tag == "remail-to":
                
                # Test the value of the tag to see if it looks like an email
                # address.
                match = email_prog.match(value)
                
                if match is not None:
                    
                    # We have a remail-to tag with a valid email address. Now
                    # we simply append the email address to the list of
                    # remail addresses.
                    remail_addresses.append(match.group(0))
                    
        return message_str, remail_addresses


    def doThemAll(self):
        
        message_uids = self.getAllFolderUIDs(incoming_folder)
        
        print("%d unread messages in <%s>" %(len(message_uids), incoming_folder))
        
        # Loop through all the messages in the inbox.
        for message_uid in message_uids:
            
            message_str = self.fetchMessageUIDAsString(message_uid)
            
            self.scanMessageForRemailTags(message_str)
#             print("%s" % message_obj['Subject'])

        pass
        

if __name__ == '__main__':
    imap_creds = RemailerCreds() # These SMTP credentials will work for Domain IMAP
    
    imap_service = { "server_addr": "imap.domain.com",
                     "port": 993 }

    imap_interface = IMAPInterface()
    imap_interface.readyService(imap_service, imap_creds)
    
    cxn = imap_interface.getServer()
    remailer = Remailer(cxn)
    
    remailer.validateFolderStructure()

    try:
        remailer.doThemAll()
        
        raise RuntimeError("Oops")
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
