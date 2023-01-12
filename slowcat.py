'''
A lazy cat which sleeps in-between lines
'''

import sys
import time

SLEEP_TIME = 0.05

def main(fd): #pylint: disable-msg=W0621,C0103
    '''Main, what else'''

    for line in fd:
        print (line)
        sys.stdout.flush()
        time.sleep(SLEEP_TIME)

if __name__ == '__main__':
    with open(sys.argv[1], 'r') as fd:
        main(fd)
