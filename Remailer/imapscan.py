'''
Created on Jan 31, 2021

@author: jct
'''

from creds import RemailerCreds
from creds import SMTPCreds

from imap import IMAPInterface
from smtp import SMTPInterface
 
from message import dumpHeaders
from message import mutateHeaders
from message import scanMessageForRemailTags
from message import messageBytesAsObject
from message import showMessageSubject

incoming_folder = 'INBOX'
exception_folder = 'INBOX.remailer-exception'
sent_folder = 'INBOX.remailer-sent'
original_folder = 'INBOX.remailer-original'
notag_folder = 'INBOX.remailer-original-notag'

class Remailer:
    def __init__(self, imap_connection, smtp_service):
        self._imap_cxn = imap_connection
        self._smtp_service = smtp_service
        
        # Check the connection capabilities to see if it supports
        # the MOVE command
        typ, capabilities_str = self._imap_cxn.capability()
        capabilities = capabilities_str[0].split()
        
        if b'MOVE' in capabilities:
            self._imap_has_move = True
        else:
            self._imap_has_move = False
    
        
    def _validateFolder(self, folder_name):
        typ, [response] = self._imap_cxn.select(folder_name)
        if typ != 'OK':
            raise RuntimeError(response)
    
    def validateFolderStructure(self):
        self._validateFolder(incoming_folder)
        self._validateFolder(exception_folder)
        self._validateFolder(sent_folder)
        self._validateFolder(original_folder)
        self._validateFolder(notag_folder)
        
    def getAllFolderUIDs(self, folder):
        typ, [response] = self._imap_cxn.select(folder)
        if typ != 'OK':
            raise RuntimeError(response)
        
        typ, response = self._imap_cxn.uid('search', None, 'ALL')
        
        if typ != 'OK':
            raise RuntimeError(response)
        
        message_uids = response[0].split()
        
        return message_uids
    
    def fetchMessageUIDAsBytes(self, message_uid):
        
        # Fetch the contents of the message
        typ, data = self._imap_cxn.uid('fetch', message_uid, '(RFC822)')

        if typ != 'OK':
            raise RuntimeError(data)

        # The message date comes in as a bytestring. Resist the temptation
        # to decode it into a UTF-8 string.
        message_bytes = data[0][1]
        
        return message_bytes
    
    def checkIMAPResponse(self, code, response):
        if code != 'OK':
            raise RuntimeError(response)
        
    def msgId(self, message_uid):
        message_id = 'ID(' + message_uid.decode('utf-8') + ')'
        return message_id
    
    def moveMessageUID(self, message_uid, destination_folder):
        
        message_id = self.msgId(message_uid)
        print('Moving message %s to %s' % (message_id, destination_folder))
    
        # If our IMAP server supports the MOVE command, then we simply
        # call it directly. If not, we do it the hard way.
        if self._imap_has_move:
            typ, [response] = self._imap_cxn.uid('move', message_uid, destination_folder)

        else:
            # Here's the hard way: copy the message to the folder...
            typ, [response] = self._imap_cxn.uid('copy', message_uid, destination_folder)
            self.checkIMAPResponse(typ, response)
             
            # ...then delete the original.
            typ, [response] = self._imap_cxn.uid('store', message_uid, '+FLAGS', r'(\Deleted)')
            self.checkIMAPResponse(typ, response)
            
    def doThemAll(self):
        
        message_uids = self.getAllFolderUIDs(incoming_folder)
        
        print("%d messages in %s" %(len(message_uids), incoming_folder))
        
        # Loop through all the messages in the inbox.
        for message_uid in message_uids:
                        
            message_bytes = self.fetchMessageUIDAsBytes(message_uid)

            print()
            print("Message %s" % self.msgId(message_uid))
            showMessageSubject(message_bytes)
            
            message_bytes, remail_addresses = \
                scanMessageForRemailTags(message_bytes)
                
            if len(remail_addresses) > 0:
                
                # We found at least one valid remail-to tag, so the original
                # message should be move to the originals folder.
                self.moveMessageUID(message_uid, original_folder)
                
                # The message in message_bytes has already had the tags
                # removed from it. That's the first step to constructing
                # the base message. The second part is to strip most of
                # the original headers and add our new headers. That's
                # easiest to do with a message object. Create one now.
                message_obj = messageBytesAsObject(message_bytes)
                
                mutateHeaders(message_obj)
                
                # Construct a single To: header with all of the email
                # addresses in it.
                to_header_bytes = b', '.join(remail_addresses)
                to_header_string = to_header_bytes.decode('utf-8')
                message_obj.add_header("To", to_header_string)
                
                print("Base message headers:")
                dumpHeaders(message_obj)
                
                # message_obj now contains the base message, which we
                # send to each of the recipients in turn.
                
#                 for recipient_address in remail_addresses:
                    
            
            else:
                # No addresse to remail to - move the original message to the
                # original-notag folder
                self.moveMessageUID(message_uid, notag_folder)
                
                # print("%s" % message_obj['Subject'])
                pass

if __name__ == '__main__':
    # Set up the IMAP server connection
    imap_creds = RemailerCreds()
    
    imap_service = { "server_addr": "imap.domain.com",
                     "port": 993 }

    imap_interface = IMAPInterface()
    imap_interface.readyService(imap_service, imap_creds)
    
    imap_cxn = imap_interface.getServer()
    
    # Set up the SMTP server connection
    smtp_creds = SMTPCreds()
    
    smtp_service = { "server_addr": "smtp.domain.com",
                      "port": 587,
                      'local_hostname': 'delligattiassociates.com' }
    
    smtp_interface = SMTPInterface()
    smtp_interface.readyService(smtp_service, smtp_creds)
    
    remailer = Remailer(imap_cxn, smtp_interface)
    
    remailer.validateFolderStructure()

    try:
        remailer.doThemAll()
        
        print("*** Done ***")
         
    finally:   
        # Finish up by doing some cleanup of the IMAP connection. These
        # operations don't need to have their results checked because we
        # don't much care if they succeed or fail.
        
        # Expunge any messages we deleted.
        imap_cxn.expunge()
 
        # Close the context and log out.
        imap_cxn.close()
        imap_cxn.logout()
