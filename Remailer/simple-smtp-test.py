'''
Created on Jan 13, 2021

@author: jct

A simple and not-to-be-maintained program to test exchanges with smtp
servers.
'''
import time
import smtplib
from centraltime import centraltime_str
from creds import SMTPCreds

# recipient_list = [ "jthompson@delligattiassociates.com",
#                   "Jim Thompson Gmail <jtoftx@gmail.com>",
#                   "Jim Thompson Pobox <jim.thompson@pobox.com>",
#                   "Earl J Llama <earljllama@protonmail.com>" ]

recipient_list = [ "jthompson@delligattiassociates.com",
                   "Scott.Schmidt@L3Harris.com",
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
    
    base_msg = """Return-Path: <jthompson@delligattiassociates.com>
X-DA-Remailer: v0.0.2
To: %s
Date: %s
Subject: Second remailer test
From: Jim Thompson <jthompson@delligattiassociates.com>

Hello. If you receive this message, please forward a copy to me. If you found it in your spam or junk folder, please note "Spam". Thanks!

Best,
JT
"""
#User-Agent: Delligatti Associates Remailer 0.0.1

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
        date = centraltime_str()
        msg = base_msg % (recipient, date)
        print("----> message follows:")
        print(msg)
        print("----> sendmail to %s" % recipient)
        server.sendmail(fromaddr, recipient, msg)
    
    print("---> quit")
    server.quit()
    
    print("***> done")
