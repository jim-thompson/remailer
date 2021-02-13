'''
Created on Feb 12, 2021

@author: jct
'''

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_redirect_for(url):
    print("  Finding redirect for %s" % url)
    result = requests.get(url, verify = False, allow_redirects = False)
    print("  Result code = %d" % result.status_code)
    location = result.headers.get('location')
    print("  Redirects to: %s" % location)
    return location
    