from pysnmp.entity import engine, config
from pysnmp import debug
from pysnmp.entity.rfc3413 import cmdrsp, context
from pysnmp.carrier.asynsock.dgram import udp
from pysnmp.smi import builder
import threading
import collections
import time
import datetime
import struct
import llsrRequester

MIB = 'LLSR-MIB'
# row structure
RowObject = collections.namedtuple('RowObject',
                                   ['mibname',
                                    'columnname',
                                    'getColumn',
                                    'setColumn'])


# Implementation of the EntryHandler
class EntryObject(object):
    def __init__(self):
        self._rowRequester = llsrRequester.TableRequester('localhost')

    def _getColumn(self, idx, name):
        try:
            return self._rowRequester.getColumn(idx, name)
        except Exception as e:
            print('Get request failed: %s' % e)
            return None

    def getTableSize(self):
        try:
            return self._rowRequester.getTableSize()
        except Exception as e:
            print('Get TableSize %s ' % e)
        return 0

    def getnodeAddr(self, idx):
        return self._getColumn(idx, 'nodeAddr')

    def getmaxAttempts(self, idx):
        return self._getColumn(idx, 'maxAttempts')

    def getbroadcastInterval(self, idx):
        return self._getColumn(idx, 'broadcastInterval')

    def getmgmtMode(self, idx):
        return self._getColumn(idx, 'mgmtMode')

    def getlastUpdated(self, idx):
        return self._getColumn(idx, 'lastUpdated')

    def getlastUpdatedTime(self, idx):
        return self._getColumn(idx, 'lastUpdatedTime')

    def getmgmtInfo(self, idx):
        return self._getColumn(idx, 'mgmtInfo')

    def setmaxAttempts(self, idx, val):
        self._rowRequester.setColumn(idx, 'maxAttempts', val)

    def setbroadcastInterval(self, idx, val):
        self._rowRequester.setColumn(idx, 'broadcastInterval', val)

    def setmgmtMode(self, idx, val):
        self._rowRequester.setColumn(idx, 'mgmtMode', val)


# public method
def createColumn(SuperClass, getValue, setValue, idx, *args):
    class Var(SuperClass):
        def readGet(self, name, *args):
                return name, self.syntax.clone(getValue(idx))

        def writeCommit(self, name, val, *args):
                setValue(idx, val)

    return Var(*args)


def timeStampPrint():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S+%s')


# Implements an Agent that serves the custom MIB and can send a trap.
class SNMPAgent(object):
    # mibObjects - a list of MibObject tuples that this agent will serve
    def __init__(self, mibObjects):
        # Each SNMP-based application has an engine
        self._snmpEngine = engine.SnmpEngine()

        # Open a UDP socket to listen for snmp requests (requset sudo command)
        config.addSocketTransport(self._snmpEngine,
                                  udp.domainName,
                                  udp.UdpTransport().openServerMode(('', 161)))
        config.addV1System(self._snmpEngine, 'agent', 'public')
        # add a v2 user with the community string public
        config.addVacmUser(self._snmpEngine, 2, 'agent', 'noAuthNoPriv',
                           readSubTree=(1, 3, 6, 1, 4, 1),
                           writeSubTree=(1, 3, 6, 1, 4, 1))
        # each app has one or more contexts
        self._snmpContext = context.SnmpContext(self._snmpEngine)
        # the builder is used to load mibs. tell it to look in the
        # current directory for our new MIB. We'll also use it to
        # export our symbols later
        mibBuilder = self._snmpContext.getMibInstrum().getMibBuilder()
        mibSources = mibBuilder.getMibSources() + (builder.DirMibSource('.'),)
        mibBuilder.setMibSources(*mibSources)
        # our variables will subclass this since we only have scalar types
        # can't load this type directly, need to import it
        (MibTable, MibTableRow, MibTableColumn,
         MibScalarInstance) = mibBuilder.importSymbols('SNMPv2-SMI',
                                                       'MibTable',
                                                       'MibTableRow',
                                                       'MibTableColumn',
                                                       'MibScalarInstance')
        # import and maintain Table
        maintaintable = maintainTableThread(0, mibObjects, mibBuilder,
                                            MibScalarInstance)
        maintaintable.start()
        # tell pysnmp to respotd to get, getnext, and getbulk
        cmdrsp.GetCommandResponder(self._snmpEngine, self._snmpContext)
        cmdrsp.SetCommandResponder(self._snmpEngine, self._snmpContext)
        cmdrsp.NextCommandResponder(self._snmpEngine, self._snmpContext)
        cmdrsp.BulkCommandResponder(self._snmpEngine, self._snmpContext)

    # Send traps to the host using community string community
    def setTrapReceiver(self, host, community):
        config.addV1System(self._snmpEngine, 'nms-area', community)
        config.addVacmUser(self._snmpEngine, 2, 'nms-area', 'noAuthNoPriv',
                           notifySubTree=(1, 3, 6, 1, 4, 1))
        config.addTargetParams(self._snmpEngine,
                               'nms-creds', 'nms-area', 'noAuthNoPriv', 1)
        config.addTargetAddr(self._snmpEngine, 'my-nms', udp.domainName,
                             (host, 162), 'nms-creds',
                             tagList='all-my-managers')
        # set last parameter to 'notification' to have it send
        # informs rather than unacknowledged traps
        config.addNotificationTarget(
                                     self._snmpEngine,
                                     'test-notification', 'my-filter',
                                     'all-my-managers', 'trap')

    def sendTrap(self):
        return

    def serve_forever(self):
            print "Agent Start..."
            self._snmpEngine.transportDispatcher.jobStarted(1)
            try:
                self._snmpEngine.transportDispatcher.runDispatcher()
            except Exception:
                self._snmpEngine.transportDispatcher.closeDispatcher()
            raise


class maintainTableThread(threading.Thread):
    def __init__(self, startIdx, columnObjects, mibBuilder, MibScalarInstance):
        threading.Thread.__init__(self)
        self.startIdx = startIdx
        self.columnObjects = columnObjects
        self.mibBuilder = mibBuilder
        self.MibScalarInstance = MibScalarInstance
        self.setDaemon(True)

    def run(self):
        print "Table Status Fetching FUNC Start"
        while True:
            time.sleep(1)
            tableSize = EntryObject().getTableSize()
            # print ("threading runing table size: %d" % tableSize)
            # print ("%s : " % (timeStampPrint()))
            if tableSize > self.startIdx:
                self.updateTable(self.startIdx,
                                 tableSize,
                                 self.columnObjects,
                                 self.mibBuilder,
                                 self.MibScalarInstance)
                self.startIdx = tableSize
                print ("%s : Table Size: %d\n" % (timeStampPrint(), tableSize))
                print "====================\n"
                self.printTable()
            elif tableSize == self.startIdx:
                self.printTable()

    def updateTable(self, startIdx, tableSize, columnObjects,
                    mibBuilder, MibScalarInstance):
        for idx in range(startIdx, tableSize):
            # print ("index: % d, lastIndex: % d, tableSize: % d"
            # % (idx, startIdx, tableSize))
            for columnObject in columnObjects:
                nextVar, = mibBuilder.importSymbols(columnObject.mibname,
                                                    columnObject.columnname)
                instance = createColumn(MibScalarInstance,
                                        columnObject.getColumn,
                                        columnObject.setColumn,
                                        idx,
                                        nextVar.name, (idx,),
                                        nextVar.syntax)
                instanceDict = {str(nextVar.name)+str(idx): instance}
                mibBuilder.exportSymbols(columnObject.mibname, **instanceDict)

    def printTable(self):
        entry = EntryObject()
        for i in range(entry.getTableSize()):
            print ("%s : nodeAddress: %s \n" % (timeStampPrint(),
                   entry.getnodeAddr(i)))
            print ("---MaxAttempts: %s\n" % entry.getmaxAttempts(i))
            print ("---BroadcastInterval: %s\n"
                   % entry.getbroadcastInterval(i))
            print ("---MgmtMode: %s\n" % entry.getmgmtMode(i))
            print ("---LastUpdated: %s\n" % entry.getlastUpdated(i))
            print ("---LastUpdatedTime(UTC) %s \n"
                   % datetime.datetime(*struct.unpack('>HBBBBBB',
                                       entry.getlastUpdatedTime(i))))
            print ("---MgmtInfo: %s\n" % entry.getmgmtInfo(i))
            print "====================\n"


if __name__ == '__main__':
    entry = EntryObject()
    # list[index, RowObjects]
    objects = [
        RowObject(MIB, 'nodeAddr', entry.getnodeAddr, ''),
        RowObject(MIB, 'maxAttempts', entry.getmaxAttempts,
                  entry.setmaxAttempts),
        RowObject(MIB, 'broadcastInterval', entry.getbroadcastInterval,
                  entry.setbroadcastInterval),
        RowObject(MIB, 'mgmtMode', entry.getmgmtMode, entry.setmgmtMode),
        RowObject(MIB, 'lastUpdated', entry.getlastUpdated, ''),
        RowObject(MIB, 'lastUpdatedTime', entry.getlastUpdatedTime, ''),
        RowObject(MIB, 'mgmtInfo', entry.getmgmtInfo, '')
          ]
    agent = SNMPAgent(objects)
    agent.setTrapReceiver('127.0.0.1', 'traps')
    # Worker(agent, entry).start()
    try:
        agent.serve_forever()
    except KeyboardInterrupt:
        print "Shutting down"
