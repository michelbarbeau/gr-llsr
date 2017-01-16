import socket
import sys
import struct

class TableRequester():
	def __init__(self,host):
		self._addr=(host, 8585)
		self._sock=None

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
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sock.connect(self._addr)

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
                self._connect()
	    	self._sendInt(0)
	        self._sendInt(idx)
	    	self._sendStr(name)
	    	val = self._recvStr()
		self._close()
		if val == 'None':
			print("Got None for variable '%s'" % name)
			return '0'
	        return val

	def getTableSize(self):
		self._connect()
		self._sendInt(1)
		val = self._recvInt()
		self._close()
	        if val == 'None':
		        print("Got None from Table")
			return 0
		return val
