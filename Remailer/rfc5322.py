'''
Created on Feb 3, 2021

@author: jct
'''


# The regular expression below will recognize most valid email address.
# Source: https://emailregex.com
email_regex_str = '(?:[a-z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&\'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])'

if __name__ == '__main__':
    import re

    email_prog = re.compile(email_regex_str)
    
    print("hello, email")
    test_strings = [ "jtoftx@gmail.com",
                     "Jim Thompson <jtoftx@gmail.com>",
                     "Jim Thompson <jtoftx+test1@gmail.com>",
                     'jtoftx+test_2@gmail.com "Jim Thompson"',
                     "jt of tx at gmail dot com"]
    
    for test_string in test_strings:
        match = email_prog.search(test_string)
        
        if match is not None:
            g0 = match.group(0)
            print('Found "%s"' % g0)
        else:
            print('Found no match in "%s"' % test_string)