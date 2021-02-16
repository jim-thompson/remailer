'''
Created on Jan 13, 2021

@author: jct

A simple and not-to-be-maintained program to test exchanges with smtp
servers.
'''
import time
import smtplib
from creds import SMTPCreds

# recipient_list = [ "jthompson@delligattiassociates.com", "jtoftx@gmail.com", "jim.thompson@pobox.com"]
# recipient_list = [ "earljllama@protonmail.com" ]
recipient_list = [ "Scott.Schmidt@L3Harris.com",
                   "Sherrie.Hughes@leidos.com>",
                   "Rachel.Gaines@ManTech.com>",
                   "lapierre_michael@bah.com>",
                   "leslie.thomas@navy.mil",
                   "erin.m.bootle@navy.mil",
                   "john.e.wilson@navy.mil",
                   "abeachy@learnspectrum.com" ]

if __name__ == '__main__':
    creds = SMTPCreds()
    
    fromaddr = "jthompson@delligattiassociates.com"
    
    base_msg = """To: %s
Subject: Remailer connectivity test
From: Jim Thompson <jthompson@delligattiassociates.com>

This is a connectivity test of the Delligatti Associates remailer.
The purpose of this test is to determine whether we can send email
from a python script and successfully receive the email at clients
that typically block our automated emails.

If you receive this email, please forward it back to me. Thank you! 

Best,
JT
"""
    
    print("Using SMTP user = <%s>, password = <%s>" % (creds.username, creds.password))
    
#     print("Message length is", len(msg))
#     print("----> message follows:\n", msg)
    
    print("---> connect")
    server = smtplib.SMTP(host = 'smtp.domain.com', port = 587, local_hostname = 'delligattiassociates.com')
    
    #server.set_debuglevel(1)
    print("---> starttls")
    server.starttls()
    
    print ("---> login with user=<%s>, pass=<%s>" % (creds.username, creds.password))
    server.login(creds.username, creds.password)
    
    for recipient in recipient_list:
        msg = base_msg % recipient
        print("----> message follows:")
        print(msg)
        print("----> sendmail to <%s>" % recipient)
        server.sendmail(fromaddr, recipient, msg)
    
    print("---> quit")
    server.quit()
    
    print("***> done")
