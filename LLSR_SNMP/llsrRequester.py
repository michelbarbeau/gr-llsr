import socket
import sys
import struct
import os
from socket import error as SocketError
import errno

class TableRequester():
	def __init__(self,host):
	    self._socketpath = "/tmp/udscommunicate"
	    self._sock = None

	def _sendInt(self, val):
	    self._sock.send(struct.pack('I', val))

	def _sendStr(self, val):
	    self._sendInt(len(val))
	    self._sock.send(val)

	def _recvInt(self):
	    return struct.unpack('I', self._sock.recv(4))[0]
	
	def _recvStr(self):
	    length = self._recvInt()
            return self._sock.recv(length)
	
	def _connect(self):
	    # check the socketfile if it exists
	    if os.path.exists(self._socketpath):
	       #Connect to the socket
	       self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
	       self._sock.connect(self._socketpath)

	def _close(self):
            self._sock.close()

	def setColumn(self, idx, name, val):
	    try:
	        self._connect()
		self._sendInt(2)
		self._sendInt(idx)
		self._sendStr(name)
	        self._sendInt(val)
		self._close()
	    except ValueError as e:
		print('Failed to set int: %s' % e)
	
	def getColumn(self, idx, name):
	    try:
               self._connect()
	       self._sendInt(0)
	       self._sendInt(idx)
	       self._sendStr(name)
	       val = self._recvStr()
	       self._close()
	    except SocketError as e:
	       print('Connection Error' % e)
	       return '0'
	    if val == None:
	       print("Got None for variable '%s'" % name)
	       return '0'
	    else:
	       return val

	def getTableSize(self):
	    try:
	       self._connect()
	       self._sendInt(1)
	       val = self._recvInt()
	       self._close()
	    except SocketError as e:
	       print('Connection Error %s' % e)
	       return 0
	    if val == None:
	       print("Got None from Table")
	       return 0
	    else:
	       return val

# if __name__ == '__main__':
#    requester = TableRequester()
#    print ("Getting v1: %s" % requester.getColumn(0, "v1"))
