'''
Demonstration of using `splice` with non-blocking IO

Lots of code is similar to 'splice.py', take a look at that module for more
documentation.
'''

import os
import os.path
import errno
import fcntl
import socket
import select
import subprocess
import splice

def set_nonblock(fd): #pylint: disable-msg=C0103
    '''Set a file descriptor in non-blocking mode'''

    flags = fcntl.fcntl(fd, fcntl.F_GETFL, 0)
    flags |= os.O_NONBLOCK
    fcntl.fcntl(fd, fcntl.F_SETFL, flags)


def main(host, port, path): #pylint: disable-msg=R0914
    '''Server implementation'''

    # Set up server socket
    # ====================
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(1)

    # Wait for client
    # ===============
    conn, addr = sock.accept()
    print ('Connection from: {0}'.format(addr))

    # Launch subprocess
    argv = ['python', 'slowcat.py', path]
    proc = subprocess.Popen(argv, close_fds=True, stdout=subprocess.PIPE)

    # Set up source and sink FDs
    # ==========================
    pipe_fd = proc.stdout.fileno()
    set_nonblock(pipe_fd)

    conn_fd = conn.fileno() #pylint: disable-msg=E1101
    set_nonblock(conn_fd)

    print ('Will splice data from FD %s to %s'%(pipe_fd, conn_fd))

    # Blah blah
    # =========
    transferred = 0

    chunksize = 32 * 1024 * 1024
    flags = \
        splice.SPLICE_F_MOVE | splice.SPLICE_F_MORE | splice.SPLICE_F_NONBLOCK

    # Run transfer
    # ============
    # The whole read/write-set and select code below is extremely bare-bone,
    # this is not how you should implement a 'serious' event-loop.
    # You shouldn't implement your own event-loop anyway most likely, there are
    # tons of good ones (using different approaches) out there.

    read_set = [pipe_fd]
    write_set = [conn_fd]

    while True:
        # Wait until (most likely) the subprocess pipe is readable, and the
        # output socket is writable.
        readable_set, writable_set, _ = select.select(read_set, write_set, [])

        # This is terrible. Don't do this. Seriously.
        if pipe_fd in readable_set:
            read_set = []
        if conn_fd in writable_set:
            write_set = []

        if read_set or write_set:
            # At least one of the FDs we need isn't ready
            continue

        # Jay, both file descriptors might be usable!

        # Reset for the next iteration...
        read_set = [pipe_fd]
        write_set = [conn_fd]

        try:
            # Splice!
            done = splice.splice(pipe_fd, None, conn_fd, None, chunksize, flags)
        except IOError as exc:
            if exc.errno in [errno.EAGAIN, errno.EWOULDBLOCK]:
                # Oops, looks like one of the FDs blocks again. Retry!
                continue

            raise

        if done == 0:
            break

        transferred += done

    print ('Bytes transferred:%s'%transferred)

    # Clean up
    # ========
    conn.close()
    sock.close()

    proc.wait()


if __name__ == '__main__':
    main('', 9009, os.path.abspath(__file__))
