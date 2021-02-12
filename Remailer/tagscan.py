'''
Created on Feb 2, 2021

@author: jct
'''
import re
from macros import macro_substitute

prog = re.compile("\${(([a-zA-Z0-9-]+):)?([^}]*)}")

def scan_for_tags(bytes_):
    found_tags = []
    
    # Find the first macro
    match = prog.search(bytes_)

    # Loop through every macro we find.
    while match is not None:

        # Extract the tag name and value from the match. The name is the
        # substring defined by group 2 of the regex.
        tag_name = match.group(2)

        # The tag value is the substring matched by group 3 of the regex.
        tag_value = match.group(3)
        
        # Make a tuple for the tag, because it's easier to append 
        # to the return list.
        tag_tuple = (tag_name, tag_value)
        
        # Record the tag tuple in the return list
        found_tags.append(tag_tuple)

        # Substitute the macro with an empty bytestring
        bytes_ = macro_substitute(bytes_, match, "")

        # Find the next match
        match = prog.search(bytes_)

    # Finally, return the macro-substituted bytes_ and list of tags.    
    return bytes_, found_tags

if __name__ == '__main__':
    # Test code
    test_strings = [
        "this is ${foobar} surrounding text",
        'this is also ${foo:bar} surrounding text',
        "Oh no! This one won't match! ${foo:bar",
        '${remail-to:albert.troutflap@gmail.com}',
        'here is some more${t1:v1}${t2:v2} surrounding text'
        ]
    
    for s in test_strings:
        print("\nSearching in %s" % s)
        match = prog.search(s)
        
        if match is not None:
            g0 = match.group(0)
            tag = match.group(2)
            value = match.group(3)
            print("Matched %s" % g0)
            print("tag <%s> value <%s>" % (tag, value))
          
            s, tags = scan_for_tags(s)
            print("Result of tag scan: <%s>" % s)
            for tuple_ in tags:
                print("tag <%s> value <%s>" % tuple_)
            
            
            