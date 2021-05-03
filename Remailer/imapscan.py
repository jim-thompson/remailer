'''
Created on Jan 31, 2021

@author: jct
'''

# System and language imports
import sys
import traceback

# Standard library imports
import logging
import time
from time import sleep
import re
from quopri import decodestring
from imaplib import Time2Internaldate

# Imports from local libraries elsewhere on the PYTHONPATH
from creds import RemailerBotCreds
from creds import SMTPCreds

# Imports from the Enroller project
from macros import macro_substitute

from imap import IMAPInterface
from smtp import SMTPInterface

from centraltime import centraltime_str
from macros import macro_substitute

# Imports from elsewhere in this project 
from message import dumpHeaders
from message import mutateHeaders
from message import scanPartForTruncateTags
from message import scanPartForRemailTags
from message import messageBytesAsObject
from message import showMessageSubject

# Unused local imports
# from url_mappings import infusionlink_url_mappings
# from url_redirect import get_redirect_for

# Names of the five folders used by the Remailer
# The inbox is where messages to us are delivered
incoming_folder = 'INBOX'

# Incoming (original) messages are filtered into one
# if these two folders. 
original_folder = 'INBOX/remailer-original'
notag_folder = 'INBOX/remailer-original-notag'

exception_folder = 'INBOX/remailer-exception'
sent_folder = 'INBOX/remailer-sent'

global_from_addr = 'da@delligattiassociates.com'

def info(str_):
    logging.info("Remailer: " + str_)
    print("Remailer: " + str_)

def debug(str_):
    logging.debug("Remailer: " + str_)

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
        debug('Moving message %s to %s' % (message_id, destination_folder))
    
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
            # print()
            # print("  Found infusionlinks url <%s>" % matched_url)
            
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
            # print()
            # print("  Found tracking pixel url <%s>" % matched_url)
            
            # Delete the URL.
            message_part_str = macro_substitute(message_part_str, match, "")
        
            # Find the next tracking pixel URL
            match = self.tracking_pixel_url_prog.search(message_part_str)
            
        return message_part_str
    
    mime_pattern = "([a-z]+)/([a-z]+)"
    mime_prog = re.compile(mime_pattern)
    
    def typeAndSubtype(self, mime_type_str):
        match = self.mime_prog.match(mime_type_str)
        if match is not None:
            main_type = match.group(1)
            sub_type = match.group(2)
            return main_type, sub_type
        return "", mim_type_str
    
    delete_html_parts = True
    
    def performSubstitutionOnMessageParts(self, obj):
        
        remail_addresses_set = set()
        
        # Loop over all the message parts.
        for part in obj.walk():
            
            content_type = part.get_content_type()
            content_charset = part.get_content_charset()
            content_disposition = part.get_content_disposition()
            
            # Spit out some diagnostic messages.
            debug("Content-Type: %s" % content_type)
            debug("Content-Charset: %s" % content_charset)
            debug("Content-Disposition: %s" % content_disposition)
            
            # Multipart parts are basically containers, so we don't process
            # them. But we process all others.
            if not part.is_multipart():
                main_type, sub_type = self.typeAndSubtype(content_type)
                
                # Optional configuration: just delete all HTML parts because
                # something in them is causing emails to get filed as SPAM.
                if self.delete_html_parts and sub_type == "html":
                    pl = obj.get_payload()
                    pl.remove(part)
                    
                    # This part has been deleted - no further processing
                    # needed for this part.
                    continue
                    
                debug("main_type = <%s>, sub_type = <%s>" % (main_type, sub_type))
                
                # Get the message_part_str of this part of the message.
                # If this part of the message was encoded in (possibly)
                # MIME quoted-printable, it will be decoded into a string
                # in (proabably) UTF-8 unicode. (Which is good, because
                # it's easier to deal with in this form.)
                message_part_str = part.get_content()
                
                # Now some real processing...
                
                maybe_modified_content_str = scanPartForTruncateTags(message_part_str)
                
                # Scan the part for remail-to: tags, replace them,
                # and accumulate the recipient addresses.
                maybe_modified_content_str, more_remail_addresses_set = \
                    scanPartForRemailTags(maybe_modified_content_str)
                    
                # Get the union of the two sets.
                remail_addresses_set |= more_remail_addresses_set
                
                # # Now perform mapping of any infusion-link URLs to their
                # # direct link conterparts.
                # maybe_modified_content_str = self.remapURLs(maybe_modified_content_str)
                #
                # # Finally, nuke any tracking pixel URLs
                # maybe_modified_content_str = self.suppressTrackingPixels(maybe_modified_content_str)

                # If any of these steps have modified the content of this
                # part of the message, then replace that part of the
                # message object.                
                if maybe_modified_content_str != message_part_str:
                    
                    part.set_content(maybe_modified_content_str, subtype = sub_type,
                                        charset = content_charset,
                                        disposition = content_disposition)

        # Return any remail-to addresses we found. (It's not
        # to return the message object. It's passed by reference,
        # and the caller's reference will retain any changes
        # we've made here.)
        return remail_addresses_set
    
    from email.policy import default
    MHTMLPolicy = default.clone(linesep='\r\n', max_line_length=0)
 
    def doThemAll(self):
        first_send_this_iteration = True
        
        # Get the UIDs of all the messages in our Inbox and compute
        # the number of messages, which we key off of for some
        # info messages and housekeeping.
        message_uids = self.getAllFolderUIDs(incoming_folder)
        message_count = len(message_uids)
        
        # Report the number of messages in the Inbox.
        mc_suffix = "" if message_count == 1 else "s"
        info("%d message%s in %s" %(message_count, mc_suffix, incoming_folder))
        
        if message_count > 0:
            print('################################################################################')
        
        # Loop through all the messages in the inbox.
        for message_uid in message_uids:
            
            # Wrap this processing in a try block so
            # that if a message fails we may still be
            # able to process others.
            try:
                        
                message_bytes = self.fetchMessageUIDAsBytes(message_uid)
    
                # Emit some messages to show progress.
                print()
                info("Message %s" % self.msgId(message_uid))
                showMessageSubject(message_bytes)
                                
                message_obj = messageBytesAsObject(message_bytes)
                
                remail_addresses_set = self.performSubstitutionOnMessageParts(message_obj)
                
                remail_count = len(remail_addresses_set)
                if remail_count > 0:
                    rm_suffix = "" if remail_count == 1 else "es"
                    info("Found %d remail address%s" % (remail_count, rm_suffix))
                    
                    # We found at least one valid remail-to tag, so the original
                    # message should be move to the originals folder.
                    self.moveMessageUID(message_uid, original_folder)
                    
                    # The message in message_bytes has already had its body
                    # modified (remail-to tags removed, infusionlinks URLs
                    # replaced, tracking pixel URLs deleted). Now we modify
                    # the headers to make the message look like a brand new
                    # message, not something that's been bounced around the
                    # Internet already.
                    mutateHeaders(message_obj, global_from_addr)
                    
                    # Construct a single To: header with all of the email
                    # addresses in it.
                    to_header_str = ', '.join(remail_addresses_set)
                    message_obj.add_header("To", to_header_str)
                    
                    # debug("Base message headers:")
                    # dumpHeaders(message_obj)
                    
                    # Save the base message to IMAP so it can easily be resent
                    # later.
                    now = Time2Internaldate(time.time())
                    message_bytes = self._smtp_service.message_bytes(message_obj)
                    typ, data = self._imap_cxn.append(sent_folder, '', now, message_bytes)
                    
                    # message_obj now contains the base message, which we
                    # send to each of the recipients in turn.

                    # We're about to send an email. If it's the first email
                    # for this iteration, then we need to get the SMTP server
                    # ready.                    
                    if first_send_this_iteration:
                        debug("Readying SMTP service.")
                        self._smtp_service.readyService()
                    
                    # Send the email to each of its recipients.
                    for recipient_address in remail_addresses_set:
                        info("Sending to <%s>" % recipient_address)
                        self._smtp_service.send_message(global_from_addr,
                                                        recipient_address,
                                                        message_obj)
                
                else:
                    # No addresses to remail to - move the original message to the
                    # original-notag folder
                    debug("No remail addresses! Moving to no-tag folder.")
                    self.moveMessageUID(message_uid, notag_folder)
                    
            except Exception as e:
                traceback.print_tb(e.__traceback__)
                print("*** Error processing message - skipping.")
                
        # If we had some messages to process, then do some cleanup...
        if message_count > 0:
            
            # Close the connection to the SMTP server. SMTP servers don't
            # like it when connections to them remain open too long, so
            # we close the connection. This call is harmless if the connection
            # was never opened.
            debug("Terminating SMTP service.")
            self._smtp_service.terminateService()

            info('*** Done ***')
        

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(filename = 'remailer.log',
                        format = '%(asctime)s:%(levelname)s:%(message)s',
                        level = logging.DEBUG)
    
    logging.info("-----------------------------------------------------------")
    info("initializing...")
    
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
    
    smtp_interface = SMTPInterface(smtp_service, smtp_creds)
    # smtp_interface.readyService()
    
    remailer = Remailer(imap_cxn, smtp_interface)
    
    remailer.validateFolderStructure()

    try:
        while True:
            remailer.doThemAll()
                        
            sleep(60)
         
    finally:   
        # Finish up by doing some cleanup of the IMAP connection. These
        # operations don't need to have their results checked because we
        # don't much care if they succeed or fail.
        
        # Expunge any messages we deleted.
        imap_cxn.expunge()
 
        # Close the context and log out.
        imap_cxn.close()
        imap_cxn.logout()
