import socket
import sys
import struct
import os
from socket import error as SocketError
import errno
import time
import datetime


class TableRequester():

    def __init__(self, host):
        self._socketpath = "/tmp/udscommunicate"
        self._sock = None

    def _sendInt(self, val):
        if self._sock:
            self._sock.send(struct.pack('I', val))
        else:
            return

    def _sendStr(self, val):
        if self._sock:
            self._sendInt(len(val))
            self._sock.send(val)
        else:
            return

    def _recvInt(self):
        if self._sock:
            return struct.unpack('I', self._sock.recv(4))[0]
        else:
            return

    def _recvStr(self):
        if self._sock:
            length = self._recvInt()
            return self._sock.recv(length)
        else:
            return

    def _connect(self):
        # check the socketfile if it exists
        if os.path.exists(self._socketpath):
            # Connect to the socket
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.connect(self._socketpath)
        else:
            return

    def _close(self):
        if self._sock:
            self._sock.close()
        else:
            return

    def setColumn(self, idx, name, val):
        try:
            self._connect()
            self._sendInt(2)
            self._sendInt(idx)
            self._sendStr(name)
            self._sendInt(val)
            self._close()
        except ValueError as e:
            print('Failed to set int, error: %s' % e)

    def getColumn(self, idx, name):
        try:
            self._connect()
            self._sendInt(0)
            self._sendInt(idx)
            self._sendStr(name)
            val = self._recvStr()
            self._close()
        except SocketError as e:
            print('%s: Connection Lost %s ' % (timeStampPrint(), e))
            return '0'
        if val is None:
            print("Got None for variable '%s' from item %d" % (name, idx))
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
            print('%s: Connection Lost %s ' % (timeStampPrint(), e))
            return 0
        if val is None:
            print("Get 0 item from table")
            return 0
        else:
            return val

    def timeStampPrint():
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S+%s')
# if __name__ == '__main__':
#    requester = TableRequester()
#    print ("Getting v1: %s" % requester.getColumn(0, "v1"))
