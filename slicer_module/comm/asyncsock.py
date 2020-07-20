"""
@author: Georgi Talmazov

"""


# REFERENCES:
# https://pymotw.com/2/asynchat/
# tuple unpacking https://stackoverflow.com/questions/1993727/expanding-tuples-into-arguments
# https://pymotw.com/2/asyncore/

import asyncore

import logging
import socket
import threading #would multiprocessing be better?
import zlib
import time


packet_terminator = '\nEND_TRANSMISSION\n\n'
socket_obj = None
thread = None
address = ('127.0.0.1', 5959)
compression = 8

class SlicerComm():
    # https://github.com/pieper/SlicerWeb/blob/master/WebServer/WebServer.py#L1479 adapted from, using QSocketNotifier class
    # https://stackoverflow.com/questions/55494422/python-qtcpsocket-and-qtcpserver-receiving-message QtTcpSocket example
    # https://python.hotexamples.com/examples/PyQt4.QtNetwork/QTcpSocket/-/python-qtcpsocket-class-examples.html 
    class EchoClient():
        """3D Slicer send and receive/handle data from TCP server via Qt event loop.
        """
        
        def __init__(self, host, port, handle = None):
            from __main__ import qt
            self.received_data = [] #socket buffer
            self.write_buffer = ""
            self.connected = False
            self.cmd_ops = {"TERM" : [self.handle_close,[]]} #dict stores packet command, corresponding function call, and the number of arguments needed to be passed
            self.socket = qt.QTcpSocket()
            try:
                self.socket.connectToHost(host, port)
            except:
                return
            self.socket.readyRead.connect(self.handle_read)
            self.socket.connected.connect(self.handle_connected)
            self.socket.disconnected.connect(self.handle_close)
            if handle is not None: 
                for CMD, handler in handle:
                    self.cmd_ops[CMD] = handler
            return

        def handle_connected(self):
            self.connected = True

        def handle_close(self):
            self.connected = False
            self.socket.close()
            print("DISCONNECTED")

        def handle_read(self):
            data = self.socket.readAll()
            #print(data)
            self.received_data.append(data)
            for i in range(0, len(self.received_data)):
                try: self.received_data[i] = self.received_data[i].data().decode()
                except: pass
            data = ''.join(self.received_data)
            if packet_terminator in data:
                self._process_data()
                self.received_data = []

        def _process_data(self):
            """We have the full ECHO command"""
            data = ''.join(self.received_data)
            #print(data)
            data = data[:-len(packet_terminator)]
            data = data.split(' net_packet: ')
            self.received_data = [] #empty buffer
            try:
                #print(data[1])
                data[1] = eval(str(data[1]))
                data[1] = zlib.decompress(data[1]).decode()
                #print(data[1])
                if data[0] in self.cmd_ops: self.cmd_ops[data[0]](data[1]) #call stored function, pass stored arguments from tuple
                elif data[0] in self.cmd_ops and len(data) > 2: self.cmd_ops[data[0]][0](data[1], *self.cmd_ops[data[0]][1]) # call stored function this way if more args exist - not tested
                else: pass
            except: pass
            return

        def send_data(self, cmd, data):
            data = str(zlib.compress(str.encode(data, encoding='UTF-8'), compression))
            self.write_buffer = str.encode(cmd.upper() + " net_packet: " + data + packet_terminator)
            self.socket.write(self.write_buffer)
            self.write_buffer = ""

class BlenderComm():

    #blender_main_thread = None

    def start():
        try:
            asyncore.loop()
        except asyncore.ExitNow as e:
            #print(e)
            pass
        #asyncore.loop()

    def init_thread(server_instance, socket_obj):
        blender_thread = threading.current_thread()
        new_thread = threading.Thread()
        new_thread.run = server_instance
        new_thread.start()
        check_thread = threading.Thread(target=BlenderComm.check_main_thread, args=(blender_thread, new_thread, socket_obj,))
        check_thread.start()
        return new_thread
    
    def stop_thread(my_thread):
        my_thread.join()
        #raise asyncore.ExitNow('Server is quitting!')
        
    def check_main_thread (main_thread, server_thread, socket_obj):
        while main_thread.is_alive() and server_thread.is_alive():
            time.sleep(2)
        socket_obj.stop_server(socket_obj)
        BlenderComm.stop_thread(server_thread)
        exit()
            



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
            data[1] = zlib.decompress(data[1]).decode()
            if data[0] in self.cmd_ops: self.cmd_ops[data[0]](data[1]) #call stored function, pass stored arguments from tuple
            elif data[0] in self.cmd_ops and len(data) > 2: self.cmd_ops[data[0]][0](data[1], *self.cmd_ops[data[0]][1])
            else: pass

        def send_data(self, cmd, data):
            data = zlib.compress(str.encode(data), compression)
            self.send(str.encode(cmd.upper() + " net_packet: " + data + packet_terminator))


    class EchoHandler(asyncore.dispatcher_with_send):

        def init(self, instance, cmd_handle = None):
            self.instance = instance
            self.received_data = [] #socket buffer
            self.write_buffer = ""
            self.connected = False
            self.cmd_ops_client = {"TERM" : [self.handle_close,[]]}
            if cmd_handle is not None: 
                self.cmd_ops_client.update(cmd_handle)

        def handle_connect(self):
            self.connected = True

        def handle_close(self):
            self.connected = False
            self.close()
            for client in self.instance.sock_handler:
                if client == self:
                    del self.instance.sock_handler[self.instance.sock_handler.index(self)]
                    print("client instance deleted")
            print("disconnected")

        def handle_read(self):
            data = self.recv(8192)
            #print(data)
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
            #print(data)
            data = data.split(' net_packet: ')
            #print(data)
            self.received_data = [] #empty buffer
            try:
                data[1] = eval(str(data[1]))
                data[1] = zlib.decompress(data[1]).decode()
            
                if data[0] in self.cmd_ops_client: self.cmd_ops_client[data[0]](data[1]) #call stored function, pass stored arguments from tuple
                elif data[0] in self.cmd_ops_client and len(data) > 2: self.cmd_ops_client[data[0]][0](data[1], *self.cmd_ops_client[data[0]][1])
                else: pass
            except: pass

        def send_data(self, cmd, data):
            data = str(zlib.compress(str.encode(data, encoding='UTF-8'), compression))
            self.send(str.encode(cmd.upper() + " net_packet: " + data + packet_terminator))

    class EchoServer(asyncore.dispatcher):

        def __init__(self, host, port, cmd_handle = None):
            asyncore.dispatcher.__init__(self)
            self.instance = self
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            #self.set_reuse_addr()
            self.bind((host, port))
            self.listen(5) #max number of connected clients
            self.sock_handler = []
            self.cmd_ops = {}
            if cmd_handle is not None: 
                for CMD, handler in cmd_handle:
                    self.cmd_ops[CMD] = handler

        def handle_accepted(self, sock, addr):
            print('Incoming connection from %s' % repr(addr))
            self.sock_handler.append(BlenderComm.EchoHandler(sock))
            self.sock_handler[-1].init(self.instance, self.cmd_ops)
            self.sock_handler[-1].connected = True

        def stop_server(self, socket_obj):
            for connected_client in socket_obj.sock_handler:
                connected_client.handle_close()
            self.close()
            #socket_obj = None
            print("server stopped")
        

if __name__ == "__main__":
    #socket_obj = EchoClient(address[0], address[1])
    #init_thread(start)
    socket_obj = BlenderComm.EchoClient(address[0], address[1])
    BlenderComm.init_thread(BlenderComm.start)
    #BlenderComm.start()
    time.sleep(10)
    socket_obj.send_data("TEST", "bogus string from GIL CLIENT")
    time.sleep(10)
    
