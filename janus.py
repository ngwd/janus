from __future__ import annotations
import socket
import asyncore
import logging
import sys
'''
                                    __  __  _
             _.-._ _.-`-._  _   _.-  .-' -'   `-._
          .-`-- ._`-._`-. `-.`-._..-`__.-'  _.-`   `-.
       .-' `-._ `-._    `-._ `-. _    _.--'     _/   ``-.
    .-'"`-._.. \_      _                    _.-'  _.-'  _\
  .'        \_          \_      `-._/_.-`  _.-   /__.- `  \
 |       _.'        `-._    `-._  _ _.-` _/      _.-`   _.'(
 \`-._ .'         )               _/     __/       _.-'/ _.'
  `._  \_     _.'  `-._/  -._  _.'      _/     _/ / __.-'(
      \`-._`-.)_         ._       _.-`_/    _(_ _.'      )
      (    `-.__`-.  `-.   `--.__.          _.'          |
      /         (`-.      `-._      __/   _.'    .;:::=. |
     (   .-===.  (`-.          `-._  _/  _/     /  .-.   )
      ` ' .-.  \  ``-.   `-._           _.'       '-._) (
       ) (_.-'  :   `-.         _.'     _/'      `--=.   `.
     .'  `---= '     `-. \_       _.-`    '          )     `.
    ;       .'       `-.    ._          _.)         /        \
   '      (          `-.          _/     _'        /    _.--  )
  /        \         `-.    `-.  )`-._  `.-.     .'   .` __.-`
 (  -._   '.\        `-. `-._  -.`-._   _`-.    (   _.-'.-'
  `-.__`---' \       `-.   . `_`(`        _.\   _.-'  ___)
     '-.'-.._ \      `-.   `-.` ) _.-'   _.-``'./`._ '._)
     '-.'-.'-. )    `-.     `( ) )   _.-'   .-'`-.__`-.-'
     ('__\ `-.    `-.     `-.))_\ _.'   _.-'  _.-'_.-'.-'
      (_.'`-._`-.`-.`-.``-._`  `-.  _.-'  _.-'  _.'-.'_.'
       `-.`-.`-.`-.`-._`-._`     `-. _.-'   _.-'  ).-'_.'
      `-.`-.`-_.`-.`-.`-._`         `-._ _.'_.).-' _.-'
     `-.`-.`-.`-.`-.`-._`              `-.__.-'_.--' 
    `-._`-.`-.`-.`-.`-.  
     `-.`-.`-.`-.`-.`
       `-.`-.`-.`-`

Janus server, reside in linux side, contains 2 async sockets server, one is bluetooth RFCOMM socket, 
the other is TCP, each socket accept incoming connection, and will forward those data read, write to the
other socket
                                                write               ┌─────────────────────────────┐
                              ┌────────────────────────────────────►│queue belongs to TCP socket  │
                              │                                     └─────────┬───────────────────┘
                              │                                               │read
                              │                                               │
             ┌────────────────┴────┐                               ┌──────────▼──────────────┐
     write   │                     │                               │                         │  write
─────────────► RFCCOMM socket      │                               │     TCP socket          ◄───────────
             │                     │                               │                         │  read
     read    │                     │                               │                         ├────────────►
◄────────────┤                     │                               │                         │
             └──────▲──────────────┘                               └───────────┬─────────────┘
                    │read                                                      │
                    │                                                          │
           ┌────────┴────────────────────────┐            write                │
           │queue belongs to RFCOMM socket   ◄──────────────────────────────-──┘
           └─────────────────────────────────┘
	   
  
                                                                                                 
TODO:
system call splice() moves data between two file descriptors without copying between kernel address 
space and user address space. It transfers up to len bytes of data from the file descriptor fd_in 
to the file descriptor fd_out, where one of the descriptors must refer to a pipe.
'''

class RelayServer(asyncore.dispatcher):
    """
    Receives connections and establishes handlers for each client.
    """
     
    def __init__(self, address, address_family=socket.AF_INET):
        self.logger = logging.getLogger('Janus on RaspberryPi')
        asyncore.dispatcher.__init__(self)

        if address_family == socket.AF_BLUETOOTH:
            self.family_and_type = socket.AF_BLUETOOTH, socket.SOCK_STREAM
            sock = socket.socket(*self.family_and_type, socket.BTPROTO_RFCOMM)
            sock.setblocking(False)
            self.set_socket(sock)
        else:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)

        self.bind(address)
        self.address = self.socket.getsockname()
        self.logger.info('binding to %s', self.address)
        self.listen(1)
        self.data_to_write = []
        return

    def set_slicer(self, slicer:RelayServer):
        self.slicer = slicer

    def handle_accept(self):
        # Called when a client connects to our socket

        client_info = self.accept()
        self.logger.info('accept %s', client_info[1])
        RelayHandler(sock=client_info[0], owner=self, slicer=self.slicer)

        # We only want to deal with one client at a time,
        # so close as soon as we set up the handler.
        # Normally you would not do this and the server
        # would run forever or until it received instructions
        # to stop.
        # self.handle_close()
        return
    
    def handle_close(self):
        self.logger.info('%s close', self.address)
        self.close()
        return

class RelayHandler(asyncore.dispatcher):
    """
    Handles messages from a single client.
    """
    def __init__(self, sock, owner:RelayServer, slicer:RelayServer, chunk_size=256):
        self.chunk_size = chunk_size
        self.logger = logging.getLogger('Janus %s' % str(sock.getsockname()))
        asyncore.dispatcher.__init__(self, sock=sock)
        self.owner = owner
        self.slicer = slicer  
        return

    def writable(self):
        """We want to write if we have received data."""
        response = bool(self.owner.data_to_write)
        self.logger.debug('writable %s', response)
        return response

    def handle_write(self):
        """Write as much as possible of the most recent message we have received."""
        data = self.owner.data_to_write.pop()
        sent = self.send(data[:self.chunk_size])
        if sent < len(data):
            remaining = data[sent:]
            self.data.to_write.append(remaining)
        self.logger.info('write (%d) "%s"', sent, data[:sent])
        # if not self.writable():
        #    self.handle_close()

    def handle_read(self):
        """Read an incoming message from the client and put it into our outgoing queue."""
        data = self.recv(self.chunk_size)
        self.logger.info('read (%d) "%s"', len(data), data)
        # self.owner.data_to_write.insert(0, data)
        self.slicer.data_to_write.insert(0, data)
    
    def handle_close(self):
        self.logger.debug('close')
        self.close()

class RelayClient(asyncore.dispatcher):
    """
    Sends messages to the server and receives responses.
    """
    def __init__(self, host, port, message, address_family=socket.AF_INET, chunk_size=512):
        self.message = message
        self.to_send = message
        self.received_data = []
        self.chunk_size = chunk_size
        self.logger = logging.getLogger('Jansu Client')
        asyncore.dispatcher.__init__(self)

        if address_family == socket.AF_BLUETOOTH:
            self.family_and_type = socket.AF_BLUETOOTH, socket.SOCK_STREAM
            sock = socket.socket(*self.family_and_type, socket.BTPROTO_RFCOMM)
            sock.setblocking(False)
            self.set_socket(sock)
        else:
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)

        self.logger.debug('connecting to %s', (host, port))
        self.connect((host, port))
        return
        
    def handle_connect(self):
        self.logger.debug('connect')
    
    def handle_close(self):
        self.logger.debug('close()')
        self.close()
        # received_message = ''.join(self.received_data)
        received_message = ''.join([x.decode('utf-8') for x in self.received_data])
        if received_message == self.message:
            self.logger.debug('RECEIVED COPY OF MESSAGE')
        else:
            self.logger.debug('ERROR IN TRANSMISSION')
            self.logger.debug('EXPECTED "%s"', self.message)
            self.logger.debug('RECEIVED "%s"', received_message)
        return
    
    def writable(self):
        self.logger.debug('writable -> %s', bool(self.to_send))
        return bool(self.to_send)

    def handle_write(self):
        sent = self.send(bytes(self.to_send[:self.chunk_size], 'UTF-8'))
        # sent = self.send(self.to_send[:self.chunk_size])
        self.logger.debug('write (%d) "%s"', sent, self.to_send[:sent])
        self.to_send = self.to_send[sent:]

    def handle_read(self):
        data = self.recv(self.chunk_size)
        self.logger.debug('read (%d) "%s"', len(data), data)
        self.received_data.append(data)
        
def init_logging(log_file=None, append=False, console_loglevel=logging.INFO):
    """Set up logging to file and console."""
    if log_file is not None:
        if append:
            filemode_val = 'a'
        else:
            filemode_val = 'w'
        logging.basicConfig(level=logging.DEBUG,
                            format="%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s",
                            # datefmt='%m-%d %H:%M',
                            filename=log_file,
                            filemode=filemode_val)
    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(console_loglevel)
    # set a format which is simpler for console use
    formatter = logging.Formatter("%(message)s")
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)
    global LOG
    LOG = logging.getLogger(__name__) 

if __name__ == '__main__':
    logging.basicConfig(filename="janus.log", level=logging.DEBUG, format='%(name)s: %(message)s',)
    # role = sys.argv[1]   # S server    C client
    role = 'S'             # S server    C client
    BT_MAC_ADDRESS = 'E4:5F:01:7D:8E:18'  # CCS
    BT_PORT = 4
    TCP_PORT = 10000

    if role.startswith('S'):

        tcp_address = ('localhost', TCP_PORT)
        tcp_server = RelayServer(tcp_address, socket.AF_INET) 
        bluetooth_address = (BT_MAC_ADDRESS, BT_PORT) 
        rfcomm_server = RelayServer(bluetooth_address, socket.AF_BLUETOOTH)

        rfcomm_server.set_slicer(tcp_server)
        tcp_server.set_slicer(rfcomm_server)

        # ip_addr, tcp_port = tcp_server.address
        # mac_addr, bt_port = rfcomm_server.address # find out what port we were given
    else:
        # client = RelayClient(ip_addr, tcp_port, message=open('command.txt', 'r').read(), address_family=socket.AF_BLUETOOTH)
        client = RelayClient(BT_MAC_ADDRESS, BT_PORT, message=open('command.txt', 'r').read(), address_family=socket.AF_BLUETOOTH)
    asyncore.loop()
