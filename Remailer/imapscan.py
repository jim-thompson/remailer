'''
Created on Jan 31, 2021

@author: jct
'''

from creds import RemailerCreds
from imap import IMAPInterface

from message import dumpHeaders
from message import mutateHeaders
from message import scanMessageForRemailTags
from message import messageBytesAsObject

incoming_folder = 'INBOX'
exception_folder = 'INBOX.remailer-exception'
sent_folder = 'INBOX.remailer-sent'
original_folder = 'INBOX.remailer-original'
notag_folder = 'INBOX.remailer-original-notag'

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
            
    def doThemAll(self):
        
        message_uids = self.getAllFolderUIDs(incoming_folder)
        
        print("%d unread messages in <%s>" %(len(message_uids), incoming_folder))
        
        # Loop through all the messages in the inbox.
        for message_uid in message_uids:
            
            message_bytes = self.fetchMessageUIDAsBytes(message_uid)
#             print(message_bytes.decode('utf-8'))
            
            message_bytes, remail_addresses = \
                scanMessageForRemailTags(message_bytes)
                
            if len(remail_addresses) > 0:
                
                # We found at least one valid remail-to tag, so the original
                # message should be move to the originals folder.
                self.copyMessageUID(message_uid, original_folder)
                
                # The message in message_bytes has already had the tags
                # removed from it. That's the first step to constructing
                # the base message. The second part is to strip most of
                # the original headers and add our new headers. That's
                # easiest to do with a message object. Create one now.
                message_obj = messageBytesAsObject(message_bytes)
                
                mutateHeaders(message_obj)
                dumpHeaders(message_obj)
                
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
        # Finish up by doing some cleanup of the IMAP connection. These
        # operations don't need to have their results checked because we
        # don't much care if they succeed or fail.
        
        # Expunge any messages we deleted.
        cxn.expunge()
 
        # Close the context and log out.
        cxn.close()
        cxn.logout()
