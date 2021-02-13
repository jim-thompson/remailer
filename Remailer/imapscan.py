'''
Created on Jan 31, 2021

@author: jct
'''

import re
from quopri import decodestring

from creds import RemailerBotCreds
from creds import SMTPCreds

from macros import macro_substitute

from imap import IMAPInterface
from smtp import SMTPInterface
 
from message import dumpHeaders
from message import mutateHeaders
from message import scanPartForRemailTags
from message import messageBytesAsObject
from message import showMessageSubject

from macros import macro_substitute
# from url_mappings import infusionlink_url_mappings
from url_redirect import get_redirect_for

incoming_folder = 'INBOX'
exception_folder = 'INBOX/remailer-exception'
sent_folder = 'INBOX/remailer-sent'
original_folder = 'INBOX/remailer-original'
notag_folder = 'INBOX/remailer-original-notag'

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
        self._validateFolder(sent_folder)
        self._validateFolder(exception_folder)
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
            
    
    http_url_regex = 'https://ei194.infusion-links.com/[a-zA-Z0-9/]+'
    http_url_prog = re.compile(http_url_regex)
                
    def remapURLs(self, message_part_str):
        
        # See if there is an infusionlinks URL
        match = self.http_url_prog.search(message_part_str)
        
        while match is not None:
            matched_url = match.group(0)
            print()
            print("  Found infusionlinks url <%s>" % matched_url)
            
            # This will throw an exception if the matched URL has no mapping.
            # That's OK because it's an unrecoverable error. We know we cannot
            # allow an infusionlinks URL to be sent to a user because it is
            # likely to be either flagged as spam or to be blocked outright.
            # But if we don't know what its mapping is, then we would have
            # to send a malformed message. We cannot do that either, so this
            # is truly an exceptional situation. Let the exception fly!
#             mapped_url = infusionlink_url_mappings[matched_url]
#             
#             print("Found url mapping <%s>" % mapped_url)

            mapped_url = get_redirect_for(matched_url)
            
            message_part_str = macro_substitute(message_part_str, match, mapped_url)
        
            # Find the next infusionlinks URL
            match = self.http_url_prog.search(message_part_str)
            
        return message_part_str
    
    tracking_pixel_url_regex = "https://is-tracking-pixel-api-prod.appspot.com/[a-zA-Z0-9/]+"
    tracking_pixel_url_prog = re.compile(tracking_pixel_url_regex)
    
    def suppressTrackingPixels(self, message_part_str):
        
        # See if there is an infusionlinks URL
        match = self.tracking_pixel_url_prog.search(message_part_str)
        
        while match is not None:
            matched_url = match.group(0)
            print()
            print("  Found tracking pixel url <%s>" % matched_url)
            
            # Delete the URL.
            message_part_str = macro_substitute(message_part_str, match, "")
        
            # Find the next tracking pixel URL
            match = self.tracking_pixel_url_prog.search(message_part_str)
            
        return message_part_str
    
    
    def performSubstitutionOnMessageParts(self, obj):
        
        remail_addresses_set = set()
        
        # Loop over all the message parts.
        for part in obj.walk():
            
            # Spit out some diagnostic messages.
            print()
            print("  Content-Type:", part.get_content_type())
            print("  Content-Charset:", part.get_content_charset())
            print("  Content-Disposition:", part.get_content_disposition())
            
            # Multipart parts are basically containers, so we don't process
            # them. But we process all others.
            if not part.is_multipart():
                
                # Get the message_part_str of this part of the message.
                # If this part of the message was encoded in (possibly)
                # MIME quoted-printable, it will be decoded into a string
                # in (proabably) UTF-8 unicode. (Which is good, because
                # it's easier to deal with in this form.)
                message_part_str = part.get_content()
                
                # More diagnostic: print the entire message_part_str
#                 print("-----------------------------------")
#                 print(message_part_str)
                
                # Now some real processing...
                
                # Scan the part for remail-to: tags, replace them,
                # and accumulate the recipient addresses.
                maybe_modified_content_str, more_remail_addresses_set = \
                    scanPartForRemailTags(message_part_str)
                    
                # Get the union of the two sets.
                remail_addresses_set |= more_remail_addresses_set
                
                # Now perform mapping of any infusion-link URLs to their
                # direct link conterparts.
                message_part_str = self.remapURLs(message_part_str)
                
                # Finally, nuke any tracking pixel URLs
                message_part_str = self.suppressTrackingPixels(message_part_str)

                # If any of these steps have modified the content of this
                # part of the message, then replace that part of the
                # message object.                
                if maybe_modified_content_str != message_part_str:
                    
                    # A little more diagnostic output.
#                     print("===================================")
#                     print(maybe_modified_content_str)
                    
                    part.set_content(message_part_str)

        # Return any remail-to addresses we found. (It's not
        # to return the message object. It's passed by reference,
        # and the caller's reference will retain any changes
        # we've made here.)
        return remail_addresses_set
 
    def doThemAll(self):
        
        message_uids = self.getAllFolderUIDs(incoming_folder)
        
        print("%d messages in %s" %(len(message_uids), incoming_folder))
        
        # Loop through all the messages in the inbox.
        for message_uid in message_uids:
            
            # Wrap this processing in a try block so
            # that if a message fails we may still be
            # able to process others.
            try:
                        
                message_bytes = self.fetchMessageUIDAsBytes(message_uid)
    
                # Emit some messages to show progress.
                print()
                print("Message %s" % self.msgId(message_uid))
                showMessageSubject(message_bytes)
                
    #             message_bytes, remail_addresses_set = \
    #                 scanMessageForRemailTags(message_bytes)
                    
    
                message_obj = messageBytesAsObject(message_bytes)
                remail_addresses_set = self.performSubstitutionOnMessageParts(message_obj)
                    
                if len(remail_addresses_set) > 0:
                    
                    # We found at least one valid remail-to tag, so the original
                    # message should be move to the originals folder.
                    #self.moveMessageUID(message_uid, original_folder)
                    
                    # The message in message_bytes has already had its body
                    # modified (remail-to tags removed, infusionlinks URLs
                    # replaced, tracking pixel URLs deleted). Now we modify
                    # the headers to make the message look like a brand new
                    # message, not something that's been bounced around the
                    # Internet already.
                    mutateHeaders(message_obj)
                    
                    # Construct a single To: header with all of the email
                    # addresses in it.
                    to_header_str = ', '.join(remail_addresses_set)
                    message_obj.add_header("To", to_header_str)
                    
                    print("Base message headers:")
                    dumpHeaders(message_obj)
                    
                    # message_obj now contains the base message, which we
                    # send to each of the recipients in turn.
                    
                    for recipient_address in remail_addresses_set:
                        print("Remailing to <%s>" % recipient_address)
                        
                
                else:
                    # No addresses to remail to - move the original message to the
                    # original-notag folder
    #                 self.moveMessageUID(message_uid, notag_folder)
                    
                    # print("%s" % message_obj['Subject'])
                    pass
            except:
                print("*** Error processing message - skipping.")

if __name__ == '__main__':
    # Set up the IMAP server connection
    imap_creds = RemailerBotCreds()
    
    imap_service = { "server_addr": "imap.gmail.com",
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
