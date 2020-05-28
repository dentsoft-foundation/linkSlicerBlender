# REFERENCES:
# https://pymotw.com/2/asynchat/
# tuple unpacking https://stackoverflow.com/questions/1993727/expanding-tuples-into-arguments
# https://pymotw.com/2/asyncore/

import asyncore

import logging
import socket
import threading #would multiprocessing be better?
import time


packet_terminator = '\nEND_TRANSMISSION\n\n'
socket_obj = None
thread = None
address = ('localhost', 5959)

class SlicerComm():
    #https://github.com/pieper/SlicerWeb/blob/master/WebServer/WebServer.py#L1479 adapted from, using QSocketNotifier class
    class EchoClient():
        """3D Slicer send and receive/handle data from TCP server via Qt event loop.
        """
        
        def __init__(self, host, port, handle = None):
            from __main__ import qt
            self.received_data = [] #socket buffer
            self.write_buffer = ""
            self.connected = False
            self.cmd_ops = {"TERM" : [self.handle_close,[]]} #dict stores packet command, corresponding function call, and the number of arguments needed to be passed
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.socket.connect((host, port))
                self.connected = True
            except:
                return
            self.notifier_read = qt.QSocketNotifier(self.socket.fileno(),qt.QSocketNotifier.Read)
            self.notifier_read.connect('activated(int)', self.handle_read)
            self.notifier_write = qt.QSocketNotifier(self.socket.fileno(),qt.QSocketNotifier.Write)
            #self.notifier_write.connect('activated(int)', self.handle_write)
            if handle is not None: 
                for CMD, handler in handle:
                    self.cmd_ops[CMD] = handler
            return

        def handle_close(self):
            self.connected = False
            self.socket.close()
            self.notifier_read.disconnect('activated(int)', self.handle_read)
            del self.notifier_read
            self.notifier_write.disconnect('activated(int)', self.handle_write)
            del self.notifier_write

        def handle_write(self):
            print("SENDING!")
            print(self.write_buffer)
            sent = self.socket.send(self.write_buffer)
            self.write_buffer = self.write_buffer[sent:]
            if len(self.write_buffer) == 0:
                self.notifier_write.disconnect('activated(int)', self.handle_write)

        def handle_read(self):
            data = self.socket.recv(8192)
            print("READING DATA:")
            print(data)
            self.received_data.append(data)
            for i in range(0, len(self.received_data)):
                try: self.received_data[i] = self.received_data[i].decode()
                except: pass
            data = ''.join(self.received_data)
            if packet_terminator in data:
                self._process_data()
                self.received_data = []
                self.notifier_read.disconnect('activated(int)', self.handle_read)
                self.notifier_read.connect('activated(int)', self.handle_read)

        def _process_data(self):
            """We have the full ECHO command"""
            data = ''.join(self.received_data)
            data = data[:-len(packet_terminator)]
            data = data.split(' net_packet: ')
            self.received_data = [] #empty buffer
            if data[0] in self.cmd_ops: self.cmd_ops[data[0]](data[1]) #call stored function, pass stored arguments from tuple
            elif data[0] in self.cmd_ops and len(data) > 2: self.cmd_ops[data[0]][0](data[1], *self.cmd_ops[data[0]][1]) # call stored function this way if more args exist - not tested
            else: pass
            return

        def send_data(self, cmd, data):
            self.write_buffer = str.encode(cmd.upper() + " net_packet: " + data + packet_terminator)
            self.notifier_write.connect('activated(int)', self.handle_write)

class BlenderComm():

    def start():
        asyncore.loop()

    def init_thread(run):
        new_thread = threading.Thread()
        new_thread.run = run
        new_thread.start()
        return new_thread
    
    def stop_thread(self, my_thread):
        my_thread.join()


    class EchoClient(asyncore.dispatcher):
        """Sends messages to the server and receives responses.
        """

        # Artificially reduce buffer sizes to illustrate
        # sending and receiving partial messages.
        #ac_in_buffer_size = 64
        #ac_out_buffer_size = 64
        
        def __init__(self, host, port):
            asyncore.dispatcher.__init__(self)
            self.received_data = [] #socket buffer
            self.connected = False
            self.cmd_ops = {"TERM" : [self.handle_close,[]]} #dict stores packet command, corresponding function call, and the number of arguments needed to be passed
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connect((host, port))

        def handle_connect(self):
            self.connected = True
            print("client connected!")

        def handle_close(self):
            self.connected = False
            self.close()

        def handle_read(self):
            data = self.recv(8192)
            print("INCOMING RAW DATA:")
            print(data)
            self.received_data.append(data)
            for i in range(0, len(self.received_data)):
                try: self.received_data[i] = self.received_data[i].decode()
                except: pass
            data = ''.join(self.received_data)
            if packet_terminator in data:
                self._process_data()
                self.received_data = []

        def _process_data(self):
            """We have the full ECHO command"""
            data = ''.join(self.received_data)
            data = data[:-len(packet_terminator)]
            data = data.split(' net_packet: ')
            self.received_data = [] #empty buffer
            if data[0] in self.cmd_ops: self.cmd_ops[data[0]](data[1]) #call stored function, pass stored arguments from tuple
            elif data[0] in self.cmd_ops and len(data) > 2: self.cmd_ops[data[0]][0](data[1], *self.cmd_ops[data[0]][1])
            else: pass

        def send_data(self, cmd, data):
            self.send(str.encode(cmd.upper() + " net_packet: " + data + packet_terminator))


    class EchoHandler(asyncore.dispatcher_with_send):

        def init(self, cmd_handle = None):
            self.received_data = [] #socket buffer
            self.write_buffer = ""
            self.connected = False
            self.cmd_ops = {"TERM" : [self.handle_close,[]]}
            if cmd_handle is not None: 
                for CMD, handler in handle:
                    self.cmd_ops[CMD] = handler

        def handle_connect(self):
            self.connected = True

        def handle_close(self):
            self.connected = False
            self.close()

        def handle_read(self):
            data = self.recv(8192)
            print(data)
            #self.logger.debug('handle_read() -> %d bytes', len(data))
            self.received_data.append(data)
            for i in range(0, len(self.received_data)):
                try: self.received_data[i] = self.received_data[i].decode()
                except: pass
            data = ''.join(self.received_data)
            if packet_terminator in data:
                self._process_data()
                self.received_data = []

        def _process_data(self):
            """We have the full ECHO command"""
            data = ''.join(self.received_data)
            data = data[:-len(packet_terminator)]
            print(data)
            data = data.split(' net_packet: ')
            #print(data)
            self.received_data = [] #empty buffer
            if data[0] in self.cmd_ops: self.cmd_ops[data[0]](data[1]) #call stored function, pass stored arguments from tuple
            elif data[0] in self.cmd_ops and len(data) > 2: self.cmd_ops[data[0]][0](data[1], *self.cmd_ops[data[0]][1])
            else: pass

        def send_data(self, cmd, data):
            self.send(str.encode(cmd.upper() + " net_packet: " + data + packet_terminator))

    class EchoServer(asyncore.dispatcher):

        def __init__(self, host, port, cmd_handle = None):
            asyncore.dispatcher.__init__(self)
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            #self.set_reuse_addr()
            self.bind((host, port))
            self.listen(5)
            self.sock_handler = []
            self.cmd_handle = cmd_handle

        def handle_accepted(self, sock, addr):
            print('Incoming connection from %s' % repr(addr))
            self.sock_handler.append(BlenderComm.EchoHandler(sock))
            self.sock_handler[0].init(self.cmd_handle)
            self.sock_handler[0].connected = True
        

if __name__ == "__main__":
    #socket_obj = EchoClient(address[0], address[1])
    #init_thread(start)
    socket_obj = BlenderComm.EchoClient(address[0], address[1])
    BlenderComm.init_thread(BlenderComm.start)
    #BlenderComm.start()
    time.sleep(10)
    socket_obj.send_data("TEST", "bogus string from GIL CLIENT")
    time.sleep(10)
    
