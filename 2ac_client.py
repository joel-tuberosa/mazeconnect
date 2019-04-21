#!/usr/bin/env python3

'''
USAGE
    2ac_client.py [OPTION] [FILE...]

DESCRIPTION
    Send information to a running instance of '2ac_server.py'.

OPTIONS
    --help
        Display this message

'''

import getopt, sys, fileinput, socket
from os import path

HOST = '127.0.0.1'  # localhost
PORT = 13013       # listen port

class Options(dict):

    def __init__(self, argv):
        
        # set default
        self.set_default()
        
        # handle options with getopt
        try:
            opts, args = getopt.getopt(argv[1:], "", ['help'])
        except (getopt.GetoptError, e):
            sys.stderr.write(str(e) + '\n\n' + __doc__)
            sys.exit(1)

        for o, a in opts:
            if o == '--help':
                sys.stdout.write(__doc__)
                sys.exit(0)

        self.args = args
    
    def set_default(self):
    
        # default parameter value
        pass
    
def main(argv=sys.argv):
    
    # read options and remove options strings from argv (avoid option 
    # names and arguments to be handled as file names by
    # fileinput.input().
    options = Options(argv)
    sys.argv[1:] = options.args
    
    # flags
    flags = {
             "STOP"            : b'0',
             "MOUSE_IN"        : b'1',
             "MOUSE_OUT"       : b'2',
             "LEFT_NOSE_POKE"  : b'3',
             "RIGHT_NOSE_POKE" : b'4' }
    
    # open the connection
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(flags[options.args[0]])
        data = s.recv(1024)
            
    # return 0 if everything succeeded
    return 0

# does not execute main if the script is imported as a module
if __name__ == '__main__': sys.exit(main())

