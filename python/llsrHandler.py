import SocketServer
import struct
import time
import sys
import os

class llsrHandler(SocketServer.BaseRequestHandler):
    mgmttable = None  

    def getColumn(self, idx, name):
        try:
           value = self.mgmttable.getColumn(idx, name)
	   return value
        except Exception as e:
           sys.stderr.write("Failed to get value: %s" % e)
           return 'error'

    def getTableSize(self):
	value=self.mgmttable.getTableSize()
	print ("current table size: %d " % value)
	return value
	
    def setColumn(self, idx, name, value):
        self.mgmttable.setColumn(idx, name, value)

    def _recvInt(self):
        return struct.unpack('I', self.request.recv(4))[0]

    def _recvStr(self):
        length = self._recvInt()
        return self.request.recv(length)

    def _sendInt(self, val):
        self.request.send(struct.pack('I', val))

    def _sendStr(self, val):
        self._sendInt(len(val))
        self.request.send(val)

    def handle(self):
        # self.request is the TCP socket connected to the client
        rtype = self._recvInt()
	    # get Column
        if rtype == 0:
	   idx = self._recvInt()
	   name = self._recvStr()
           val = self.getColumn(idx, name)
           self._sendStr(str(val))
	    # get tableSize
        elif rtype == 1:
	   val = self.getTableSize()
	   self._sendInt(val)
	    # set Column
	elif rtype == 2:
	   idx = self._recvInt()
	   name = self._recvStr()
           val = self._recvInt()
           self.setColumn(idx, name, val)
        # error type
        else:
           print("Unrecognized request type %d" % rtype)
           return

class ManagerServer(SocketServer.UnixStreamServer):
    if os.path.exists("/tmp/udscommunicate"):
       os.remove("/tmp/udscommunicate")

    def __init__(self, tableclass, socketfile = "/tmp/udscommunicate", timeout=10):
       SocketServer.UnixStreamServer.__init__(self, 
                                        socketfile,
                                        llsrHandler)
       self.socket.settimeout(timeout)
       self.RequestHandlerClass.mgmttable = tableclass

# class Test():
#     def __init__(self, v1, v2):
#         self.v1 = v1
#         self.v2 = v2

#     def __str__(self):
#         return ("{ %s, %d }" % (self.v1, self.v2))

# def runTest():
#     test = Test("Hello", 4)

#     # Create the server, binding to localhost on port 9999
#     #server = SocketServer.TCPServer((host, port), StateManager)
#     #server.socket.settimeout(0)
#     #server.RequestHandlerClass.managedObject = test
#     server = ManagerServer(test)

#     #server.serve_forever()
#     while True:
#         time.sleep(1)
#         print("Doing other work...")
#         server.handle_request()
#         print("Test: %s" % test)


# if __name__ == "__main__":
#     runTest()
