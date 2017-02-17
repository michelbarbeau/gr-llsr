#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# ---------------------------------------
# Location-free Link State Routing (LLSR)
# --------------------------------------- 
# Copyright 2016 Michel Barbeau, Wenqian Wang, Carleton University.
# Version: Feb 9, 2017
# 
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 
# Re-using file simple_mac.py by:
# Copyright 2013 John Malsbury
# Copyright 2014 Balint Seeber <balint256@gmail.com>
#
# ----------------------------------------------------------------------
# The module implements the protocol originally described in:
# Michel Barbeau, Stephane Blouin, Gimer Cervera, Joaquin Garcia-Alfaro
# and Evangelos Kranakis, "Location-free Link State Routing for Underwater
# Acoustic Sensor Networks," 8th annual IEEE Canadian Conference on 
# Electrical and Computer Engineering (CCECE), May 2015, Halifax, NS, 
# Canada. 
#
# The program has four entry points:
# 1. "Constructor": __init__()
# 2. Handler: radio_rx()
#    Handles a message from the radio.
#    Call sequence: _radio_rx() -> 
#        [SelectNextHop() | _app_rx() | run_fsm() ]
# 3. Handler: app_rx()
#    Accepts a PDU from the application and sends it.
#    Call sequence: _app_rx() -> dispatch_app_rx() -> tx_no_arq() ->
#        send_pkt_radio()
# 4. Handler: app_rx_arq()
#    Accepts a PDU from the application and sends using the ARQ protocol.
#    Call sequence: _app_rx() -> dispatch_app_rx() -> queue.put() -> 
#        run_fsm() -> tx_arq() -> send_pkt_radio()
# 5. Handler: ctrl_rx()
#    Handles a control signal.
#    Calls: send_beacon_pkt(), check_nodes(), run_fsm()
# ----------------------------------------------------------------------

from __future__ import with_statement
import numpy
from gnuradio import gr
import pmt
from gnuradio.digital import packet_utils
import gnuradio.digital as gr_digital
import sys, time, random, struct, threading, hashlib, struct, collections
from datetime import datetime
from math import pi
import Queue
from constants import *
import llsrHandler


# Neighbor node information
# -------------------------
class Node():
    def __init__(self,time,hc,pq):
        # last time a beacon received
        self.last_heard=time
        # hop count
        self.hc=hc
        # path quality
        self.pq=pq
        # last packet number
        self.lpn = -1
    def update(self,time,hc,pq):
        # last time a beacon received
        self.last_heard=time
        # hop count
        self.hc=hc
        # path quality
        self.pq=pq
    def setLpn(self,lpn):
        # set last packet number
        self.lpn = lpn

# Monitoring Table for SINK 
# --------------------
class MGMTTable(object):
    def __init__(self):
	# nodes kept for management
	self.MGMTTable=[]
	# dict for keeping the cmd
	self.cmddict={}
	# track pack index
	self.mgmttrackIndex=0
	self.oidRef={'nodeAddr':1, 'maxAttempts':2, 'broadcastInterval':3, 'mgmtMode':4}
	# global Queue for putting MGMT CMD	
	self.pktforsent=Queue.Queue()

    def getTableSize(self):
	return len(self.MGMTTable)

    def getColumn(self, idx, name):
	if self.MGMTTable[idx]['mgmtInfo']!=4:
	   return self.MGMTTable[idx][name]
	else:
	   return None

    # generate cmd msg for in-band management VALUE DEST OPT OID
    def setColumn(self, idx, name, value):
	#check the status of mgmtInfo of this node
	if self.MGMTTable[idx]['mgmtInfo']!=4:
	   # set mgmtInfo to be create and go
	   self.MGMTTable[idx]['mgmtInfo']=1
	   # store the cmd in the cmd table
	   destNode=self.MGMTTable[idx]['nodeAddr']
	   mgmtmsg=[value, destNode, 1, self.oidRef.get(name)]
           # cmd stored for resp msg processing 
	   storedcmd=[destNode, idx, name, value]
	   # putting into the cmd dict
	   self.cmddict.update({self.mgmttrackIndex:storedcmd})
	   # putting msg into queue ready for sent
	   self.pktforsent.put(self._pdupacker(mgmtmsg))
	   # check and reset the mgmttrackIndex
	   self.mgmttrackIndex=(self.mgmttrackIndex+1)%256
	else:
	   sys.stderr.write("SET failed, SNMP MGMT Node is deactivated:\n" % addr )

    # processing RESP MSG from In-Band #FLAG, PKT_SOURCE, TRACK NUMBER, CODE/VALUE
    def processingColumn(self, respmsg):
	flag=respmsg[0]
	pktsrc=respmsg[1]
	tracknumber=respmsg[2]
	val=respmsg[3]
	if tracknumber in self.cmddict.keys():
	   cmd=self.cmddict.get(tracknumber)
	   if self.MGMTTable[cmd[1]]['nodeAddr'] == pktsrc:
	      # SET SUCCESS
	      if flag ==1 and val == 0:
	         self.MGMTTable[cmd[1]][cmd[2]]=cmd[3]
	         #mgmt info : 0 node alive, 1 request send, 2 item updated 3 mgmtError 4 node deactivated
		 self.MGMTTable[cmd[1]]['mgmtInfo']=2
		 self.MGMTTable[cmd[1]]['lastUpdated']=cmd[2]
		 self.MGMTTable[cmd[1]]['lastUpdatedTime']=self._GetUTCTime()
	      # OPT FAILED
	      elif flag==1 and val!=0:
                 #ERROR mgmtInfo
	         self.MGMTTable[cmd[1]]['mgmtInfo']=3
		 self.MGMTTable[cmd[1]][cmd[2]]=val
		 self.MGMTTable[cmd[1]]['lastUpdated']=cmd[2]
		 self.MGMTTable[cmd[1]]['lastUpdatedTime']=self._GetUTCTime()
	      elif flag==0:
	         self.MGMTTable[cmd[1]]['mgmtInfo']=2
		 self.MGMTTable[cmd[1]][cmd[2]]=val
		 self.MGMTTable[cmd[1]]['lastUpdated']=cmd[2]
		 self.MGMTTable[cmd[1]]['lastUpdatedTime']=self._GetUTCTime()
	   else:
	      sys.stderr.write("wrong id matching in the MGMTTable nodeAddr: %d pktsrc: %d" %())
	else:
	   sys.stderr.write("track number %d is not existed in the cmd dict\n")
	
    # add row
    def addRow(self, row):
	flag=self._checkNode(row['nodeAddr'])
	# new node
	if flag==-1:
	   self.MGMTTable.append(row)
           sys.stderr.write("SNMP MGMT Node %d added:\n" % row['nodeAddr'])	 
	# not new
	else:
	   if self.MGMTTable[flag]['mgmtInfo']==4:
	      self.MGMTTable[flag]['mgmtInfo']=0
              sys.stderr.write("SNMP MGMT Node %d activated :\n" % row['nodeAddr'])
	   else:
	      sys.stderr.write("SNMP MGMT Node %d is already activated :\n" % row['nodeAddr'])	   
    # deactivated
    def deactivateNode(self, addr):
	if self._checkNode(addr)!=-1:
	   idx=self._checkNode(addr)
	   if self.MGMTTable[idx]['mgmtInfo']!=4:
	      self.MGMTTable[idx]['mgmtInfo']==4	
	      sys.stderr.write("SNMP MGMT Node %d deactivated :\n" % addr)
	   else:
	      sys.stderr.write("SNMP MGMT Node %d deactivated is already deactivated :\n" % addr)
    	else:
	   sys.stderr.write("SNMP MGMT Node %d not existed:\n" % addr) 

    # -------------------------
    # PDU packing for SINK MGMT MSG(SAME IN LLSR_MAC)
    # -------------------------
    def _pdupacker(self, data):
	pdu = pmt.cons( \
        pmt.to_pmt({}), \
        pmt.init_u8vector(len(data), data))		
        return pdu

    # ------------------------------
    # UTC Time for SNMP
    # ------------------------------
    def _GetUTCTime(self):
	temp=(datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S,%f"))[:-5].split(',')
	timestr=map(int,temp)
	final=struct.pack('>HBBBBBB', *timestr)
	return final
 
    # ------------------------------
    # check node 
    # ------------------------------   
    def _checkNode(self, addr):
	for r in self.MGMTTable:
	    if r['nodeAddr']==addr:
		return self.MGMTTable.index(r)
	return -1


class llsr_mac(gr.basic_block):
    """
    Location-free Link State Routing
    """
    def __init__(self,addr,timeout,max_attempts,broadcast_interval=2,
                 exp_backoff=True,backoff_randomness=0.05,
                 node_expiry_delay=60.0,
		 max_queue_size=10,
		 errors_to_file=False,
		 data_to_file=False,
	         debug_info=0):
        gr.basic_block.__init__(self,
            name="llsr_mac",
            in_sig=None,
            out_sig=None)
        # lock for exclusive access
        self.lock=threading.RLock()
#	self.errors_to_file=errors_to_file
#	self.data_to_file=data_to_file
#	if errors_to_file or data_to_file:
#	   formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')	
	if errors_to_file:
#		self.logdebuginfo = logging.getLogger('simple logger_debug')
#		hdlr_1 = logging.FileHandler('errors_'+str(addr)+'.log')
#		hdlr_1.setFormatter(formatter)
#		self.logdebuginfo.addHandler(hdlr_1)
		# redirect standard error stream to a file
           errorFilename="errors_"+str(addr)+".txt"
	   sys.stderr=open(errorFilename,"w")
	   sys.stderr.write("*** START: "+time.asctime(time.localtime(time.time()))+"\n")
	if data_to_file:
#		self.logdatainfo = logging.getLogger('simple logger_data')
#		hdlr_2 = logging.FileHandler('data_'+str(addr)+'.log')
#		hdlr_2.setFormatter(formatter)
#		self.logdatainfo.addHandler(hdlr_2)		
		# redirect standard output stream to a file
	   dataFilename="data_"+str(addr)+".txt"
           sys.stdout=open(dataFilename,"w")
	   sys.stdout.write("***START: "+time.asctime(time.localtime(time.time()))+"\n")
	   sys.stdout.flush()
        # debug mode flag
        self.debug_stderr=True
        # node address
        self.addr = addr                               
        # packet number
        self.pkt_cnt=0                    
        # number of transmitted ARQ packets
        self.arq_pkts_txed=0 
        # number of retransmitted ARQ packets                          
        self.arq_retxed=0  
        # number of failed ARQ retransmissions                              
        self.failed_arq=0
        # maximum number of retransmission attempts
        self.max_attempts=max_attempts
        # total number of received bytes
        self.rx_byte_count=0
        # initial channel state
        self.CHANNEL_state=CHANNEL_IDLE
        # packet number expected in an ack
        self.expected_ack=-1  
        # retransmission timeout
        self.timeout=timeout
        # time of transmission
        self.time_of_tx=0.0  
        # time of last transmission
        self.last_tx_time = None
        # True whe exponential backoff is enbaled                          
        self.exp_backoff=exp_backoff
        # random factor used in backoff calculation
        self.backoff_randomness=backoff_randomness
        # percentage used in backoff calculation
        self.next_random_backoff_percentage = 0.0
        # queue of packets waiting to be transmitted
        self.queue = Queue.Queue()
	self.mgmt_queue = Queue.Queue()
	# queue of mgmt resp packets waiting to be transmitted
	self.mgmt_resp_queue = Queue.Queue()
	# number of mgmt pkt 
	self.mgmt_track=0
	# number of expected mgmt pkt
	self.mgmt_expected_ack=-1
	# max queue size for both data mgmt and mgmt resp
        self.max_queue_size=max_queue_size
	#pkt type using fsm (0 data, 1 mgmt, 2 mgmt resp)
	self.pkttype=-1 # default
	#table of time stamp and mgmt pkt
	self.lasttrack={}
	# secret key
	self.secretkey="12345"
        # dictionary of neighbor nodes
        self.nodes={}
        self.node_expiry_delay=node_expiry_delay
        # beacon broadcast period
        self.broadcast_interval=broadcast_interval
	# debug information
	self.debug_info=debug_info
	# MGMTMODE
	self.mgmtMode = 0
	# SNMP mgmt table for sink
	self.snmpmgmttable=None
	# MIB
	self.mib={1:self.addr, 2:self.max_attempts, 3:self.broadcast_interval, 4: self.mgmtMode}
        # routing state
        # -------------------------------------------------
        # sink node?
        if self.addr==SINK_ADDR:
            # yes!
            self.hc=0 # hop count
            self.pq=255 # path quality, max value
            self.next_hop=SINK_ADDR
	    self.snmpmgmttable=MGMTTable()
	    # mgmttable added SINK
	    self.snmpmgmttable.addRow(self.createdefaultNewrow(self.addr))
	    sys.stderr.write("SNMP_Table Size: %d, Added new Node: %d \n" % (self.snmpmgmttable.getTableSize(), self.snmpmgmttable.getColumn(-1, 'nodeAddr')))
            # Start SNMP TCP-Request Service
  	    try:
	       self._snmpManager = llsrHandler.ManagerServer(self.snmpmgmttable)
	    except Exception as e:
	       sys.stderr.write("Failed to create llsrhander '%s'" % e)
	       self._snmpManager = None
        else:
            # no!
            self.hc=255 # hop count, 255=infinity
            self.pq=0 # path quality, 0=not connected to sink
            self.next_hop=UNDEF_ADDR # 255=undefined	
        # -------------------------------------------------
        # message i/o for radio interface
        self.message_port_register_out(pmt.intern('to_radio'))
        self.message_port_register_in(pmt.intern('from_radio'))
        self.set_msg_handler(pmt.intern('from_radio'), self.radio_rx)  
        # message i/o for app interface
        self.message_port_register_out(pmt.intern('to_app'))
        self.message_port_register_in(pmt.intern('from_app'))
        self.set_msg_handler(pmt.intern('from_app'), self.app_rx)
        self.message_port_register_in(pmt.intern('from_app_arq'))
        self.set_msg_handler(pmt.intern('from_app_arq'), self.app_rx_arq) 
        # message i/o for ctrl interface
        self.message_port_register_out(pmt.intern('ctrl_out'))
        self.message_port_register_in(pmt.intern('ctrl_in'))
        self.set_msg_handler(pmt.intern('ctrl_in'), self.ctrl_rx)
    
    # ------------------------------------------
    # debug info print out
    # ------------------------------------------
#    def DebugInfoPrinting(self, infotype, debugmsg, *args):	
#	if args:
#	   output=debugmsg.format(*args)
#	else:
#	   output=debugmsg
#	if output is not None:
#	# infotype 2 is error, 1 is debug info, 0 is data
#	   if infotype==1:
#	      if self.errors_to_file:
#		 self.logdebuginfo.info(output)
#	      else:
#		 sys.stderr.write(output)
#	   elif infotype==2:
#	      if self.errors_to_file:
#		 self.logdebuginfo.error(output)
#	   elif infotype==0:
#	      if self.data_to_file:
#		 self.logdatainfo.info(output)
#	      else:
#		 sys.stdout.write(output)
#	else:
#	   return
	
    def get_rx_byte_count(self):
        return self.rx_byte_count

    # ------------------------------------------
    # select next hop and update routing metrics
    # ------------------------------------------
    def SelectNextHop(self):
        # this node is the sink?
        if self.addr==SINK_ADDR:
            self.hc=0 # hop count
            self.pq=255 # path quality (max value)
            self.next_hop=SINK_ADDR
        # there are neighbor nodes?
        elif len(self.nodes)>0:
            # get the minimum hop count
            min=255 # init with max value
            for k in self.nodes.keys():
                if self.nodes[k].hc<min:
                    min=self.nodes[k].hc
            # define the self hop count
            self.hc=min+1
            # get the corresponding neighbors
            min_nodes=[]
            for k in self.nodes.keys():
                if self.nodes[k].hc==min:
                   min_nodes.append(k)
            # get the maximum path qualityself.secretky
            max=0 # init with the min value
            for k in min_nodes:
                if self.nodes[k].pq>max:
                    max=self.nodes[k].pq
            # get the corresponding neighbors
            max_nodes=[]
            for k in min_nodes:
                if self.nodes[k].pq==max:
                   max_nodes.append(k)
            # define the path quality
            self.pq=len(max_nodes) # num of neighbors with max quality
            # define the next hop
            self.next_hop=max_nodes[0]
        # there are no neighbors!
        else:
            self.hc=255 # infinity
            self.pq=0 # not connected to sink
            self.next_hop=UNDEF_ADDR
        if self.debug_stderr: 
           # log the packet
           sys.stderr.write("in SelectNextHop(): addr: %d, hc: %d, pq: %d, next hop: %d\n" % \
                (self.addr,self.hc,self.pq,self.next_hop))
#	self.DebugInfoPrinting(self, 1, "Node {0}: in SelectNextHop(): hc: {1}, pq: {2}, next hop: {3}\n", self.addr, self.hc, self.pq, self.next_hop)

    # ----------------------------------
    # pretty printing of a beacon packet
    # ----------------------------------
    def print_beacon_pkt(self, pkt):
        # valid beacon packet length?
        if (len(pkt)!=BEACON_PKT_LENGTH): 
            # yes!
            sys.stderr.write("in print_beacon_pkt(): beacon packet invalid length!\n")
            return
        # no!
        # print protocol id
        sys.stderr.write("PROT ID: %d " % pkt[PKT_PROT_ID])
        # print source address
        sys.stderr.write("SRC: %d " % pkt[PKT_SRC])
        # print hop count
        sys.stderr.write("HC: %d " % pkt[PKT_HC])
        # print path quality
        sys.stderr.write("PQ: %d\n" % pkt[PKT_PQ])
    
    # ------------------------
    # transmit a beacon packet
    # ------------------------
    def send_beacon_pkt(self): 	
        # beacon packet structure
        data = [BEACON_PROTO,self.addr,self.hc,self.pq]
        # debug mode enabled?
        if self.debug_stderr: # Yes!
           # log the packet
           sys.stderr.write("%d:in send_beacon_pkt(): sending beacon packet:\n" % self.addr)
           self.print_beacon_pkt(data)      
        # conversion to PMT PDU (meta data, data)
        pdu = pmt.cons( \
            pmt.to_pmt({}), \
            pmt.init_u8vector(len(data), data))
        # push to radio msg port
        self.message_port_pub(pmt.intern('to_radio'),pdu)      
        # save current transmit time
        with self.lock:
            self.last_tx_time = time.time()

    # --------------------------------------------
    # pretty printing of an acknowledgement packet
    # --------------------------------------------
    def print_ack_pkt(self, pkt):
        # valid beacon packet length?
        if (len(pkt)!=ACK_PKT_LENGTH): 
           # yes!
           sys.stderr.write("in print_beacon_pkt(): ack packet invalid length!\n")
           return
        # no! print protocol id
        sys.stderr.write("PROT ID: %d " % pkt[PKT_PROT_ID])
        # print source address
        sys.stderr.write("SRC: %d " % pkt[PKT_SRC])
        # print destination address
        sys.stderr.write("DEST: %d " % pkt[PKT_DEST])
        # print packet count
        sys.stderr.write("CNT: %d " % pkt[PKT_CNT])
	# print protocol using the ack
	sys.stderr.write("ACK for PROT: %d \n" % pkt[PROTO_ACK])

    # ---------------------------------------------
    # transmit ack packet
    # ack_addr = destination address
    # ack_pkt_cnt = acknowledged data packet number
    # ---------------------------------------------
    def send_ack(self,ack_addr,ack_pkt_cnt,protocol_id):
        # data packet header structure
        data = [ARQ_PROTO,self.addr,ack_addr,ack_pkt_cnt,protocol_id]
        # debug mode enabled?
        if self.debug_stderr:
           # yes! log the packet
           sys.stderr.write("%d:in send_ack(): sending ack packet for protocol %d:\n" % (self.addr, protocol_id))
           self.print_ack_pkt(data)
        # conversion to PMT PDU (meta data, data)
        pdu = pmt.cons( \
            pmt.to_pmt({}), \
            pmt.init_u8vector(len(data), data))
        # push to radio msg port
        self.message_port_pub(pmt.intern('to_radio'),pdu)
        # save current transmit time
        with self.lock:
            self.last_tx_time = time.time()
    
    # ------------------------------------------
    # transmit a packet with the no ARQ protocol  
    # ------------------------------------------  
    def tx_no_arq(self, pdu_tuple, protocol_id):
        # send the packet
        self.send_pkt_radio(pdu_tuple,self.pkt_cnt,protocol_id,NO_ARQ)
        # increment packet number
        self.pkt_cnt=(self.pkt_cnt+1) % 256
    
    # --------------------------------
    # pretty printing of a data packet
    # --------------------------------
    def print_pkt(self, pkt):
        # is packet length valid?
        if (len(pkt)<PKT_MIN): # no!
           sys.stderr.write("in print_pkt(): packet too short!\n")
           return
        # yes! print protocol id
        sys.stderr.write("PROT ID: %d " % pkt[PKT_PROT_ID])
        # print source address
        sys.stderr.write("SRC: %d " % pkt[PKT_SRC])
        # print destination address
        sys.stderr.write("DEST: %d " % pkt[PKT_DEST])
        # print packet count
        sys.stderr.write("CNT: %d " % pkt[PKT_CNT])
        # print control
        sys.stderr.write("CTRL: %d\n" % pkt[PKT_CTRL])
        # packet has payload?
        if (len(pkt)>PKT_MIN): # Yes!
           # print data
           sys.stderr.write("DATA: ")
           for i in range (PKT_MIN,len(pkt)):
               sys.stderr.write("%d " % pkt[i])
           sys.stderr.write("\n") 
    
    # ---------------------------------------------------------
    # Transmit a data packet
    # pdu_tuple = PDU pair (payload,meta data)
    # pkt_cnt = packet number
    # protocol_id in { ARQ_PROTO, DATA_PROTO, BEACON_PROTO } 
    # control in { ARQ, NO_ARQ }
    # ---------------------------------------------------------
    def send_pkt_radio(self, pdu_tuple, pkt_cnt, protocol_id, control): 
        # connected to sink?
        if self.pq==0:
            # no! drop the packet
            if self.debug_stderr: 
                sys.stderr.write("%d:in send_pkt_radio(): packet dropped (not connected)\n" %
                    self.addr) 
            return  
        # packet to self?
        if self.addr==self.next_hop:
            # no! drop the packet
            if self.debug_stderr: 
                sys.stderr.write("%d:in send_pkt_radio(): packet dropped (packet to self)\n" %
                    self.addr) 
            return  
        # yes! data packet header structure
        data = [protocol_id,self.addr,self.next_hop,pkt_cnt,control]
        # add payload
        payload = pdu_tuple[0]
        if payload is None:
            payload = []
        elif isinstance(payload, str):
            payload = map(ord, list(payload))
        elif not isinstance(payload, list):
            payload = list(payload)
        data += payload
        # debug mode enabled?
        if self.debug_stderr:
           # yes! log the packet
           sys.stderr.write("%d:in send_pkt_radio(): sending packet:\n" % self.addr)
           self.print_pkt(data)
        # conversion to PMT PDU (meta data, data)
        pdu = pmt.cons( \
            pmt.to_pmt({}), \
            pmt.init_u8vector(len(data), data))
        # push to radio msg port
        self.message_port_pub(pmt.intern('to_radio'),pdu)
        # save current transmit time
        with self.lock:
            self.last_tx_time = time.time()
    
    # --------------------------------------------
    # transmit a data packet with the ARQ protocol
    # --------------------------------------------
    def tx_arq(self, pdu_tuple, protocol_id):
        # send the packet
        self.send_pkt_radio(pdu_tuple, self.pkt_cnt, protocol_id, ARQ)
        # increment packet number
        self.pkt_cnt=(self.pkt_cnt+1) % 256 

    # --------------------------------------------
    # transmit a data packet with the ARQ protocol
    # --------------------------------------------
    def retx_arq(self, pdu_tuple, protocol_id):
        # send the packet
        self.send_pkt_radio(pdu_tuple, self.pkt_cnt-1 if self.pkt_cnt != 0 else 255, protocol_id, ARQ)  
    # ------------------------
    # push data to application
    # ------------------------
    def output_user_data(self, pdu_tuple):
        self.message_port_pub(pmt.intern('to_app'), \
            pmt.cons(pmt.to_pmt(pdu_tuple[1]), \
            pmt.init_u8vector(len(pdu_tuple[0][PKT_MIN:]), \
            pdu_tuple[0][PKT_MIN:])))
	# write packet to standard output
	sys.stdout.write(time.asctime(time.localtime(time.time()))+" : ");
        # print data
        for i in range (0,len(pdu_tuple[0])):
            sys.stdout.write("%d " % pdu_tuple[0][i])
        sys.stdout.write("\n")
	sys.stdout.flush() 

    # -----------------------------------
    # scan and update the node dictionary
    # -----------------------------------
    def check_nodes(self):
        # get current time
        time_now = time.time()
        # take a copy of neighbor list
        keys=self.nodes.keys()
	# update management packet track number table
	self.updatetracktable()
	# update node table
        for k in keys:
            # get time since this node has been heard
            diff=time_now-self.nodes[k].last_heard
            # lost link with tha node?
            if diff > self.node_expiry_delay:
		# SINK_NODE
		if self.addr == SINK_ADDR:
		   self.snmpmgmttable.deactivateNode(k)
                # yes! remove the node
                self.nodes.pop(k, None)
                # log the change
                if self.debug_stderr:
                    sys.stderr.write("in check_nodes(): link lost with node: %d\n" %\
                         k)
    
    # -------------------------------
    # Handle a message from the radio
    # -------------------------------
    def radio_rx(self, msg):
        # message structureis a meta data-data?
        try:
            meta = pmt.car(msg)
            data =  pmt.cdr(msg)
        except:
            if self.debug_stderr:
                #log the error
                sys.stderr.write("in radio_rx(): message is not a PDU\n")
            return    
        # data is a vector of unsigned chars?
        if pmt.is_u8vector(data):
            data = pmt.u8vector_elements(data)
        else:
            if self.debug_stderr:
                #log the error
                sys.stderr.write("in radio_rx(): data is not a u8vector\n")
            return
        # convert meta data dictionary from PMT to Python type
        meta_dict = pmt.to_python(meta)
        if not (type(meta_dict) is dict):
            meta_dict = {}
        # Get exclusive access
        with self.lock: 
            self._radio_rx(data, meta_dict)
    
    # ------------------------------------------------------------
    # Handle a message from the radio, exclusive access is assumed
    # data = message content
    # meta_dict = dictionary of meta data, in Python type
    # ------------------------------------------------------------
    def _radio_rx(self, data, meta_dict):  
        # check msg size
	if len(data) < 1:
	   if self.debug_stderr:
	       sys.stderr.write("in _radio_rx(): message size 0\n")
           return	
        # valid protocol ID?
        if not data[PKT_PROT_ID] in [ARQ_PROTO,DATA_PROTO,BEACON_PROTO,MGMT_PROTO,MGMT_RESP_PROTO]:
            # no! log the error
            if self.debug_stderr: 
                sys.stderr.write("in _radio_rx(): invalid protocol ID: %d\n" % \
                    (data[PKT_PROT_ID]))
        # valid packet length?
        if (data[PKT_PROT_ID]==ARQ_PROTO and len(data) != ACK_PKT_LENGTH) or \
           (data[PKT_PROT_ID]==DATA_PROTO and len(data) < PKT_MIN) or \
	   (data[PKT_PROT_ID]==MGMT_PROTO and len(data)!= MGMT_PKT_LENGTH) or \
	   (data[PKT_PROT_ID]==MGMT_RESP_PROTO and len(data)!=MGMT_RESP_LENGTH) or \
           (data[PKT_PROT_ID]==BEACON_PROTO and len(data) != BEACON_PKT_LENGTH):
            # no! log the error
            if self.debug_stderr: 
                sys.stderr.write("in _radio_rx(): invalid packet length: %d\n" % \
                (len(data)))
            # do nothing!
            return
        # debug mode enabled?
        if self.debug_stderr: 
            # log the packet!
            sys.stderr.write("%d:in _radio_rx(): receiving packet:\n" % self.addr)
            if data[PKT_PROT_ID]==ARQ_PROTO:
                self.print_ack_pkt(data)
            elif data[PKT_PROT_ID]==DATA_PROTO:
                self.print_pkt(data)
            elif data[PKT_PROT_ID]==BEACON_PROTO:
                self.print_beacon_pkt(data)
	    elif data[PKT_PROT_ID]==MGMT_PROTO:
		self.print_mgmt_pkt(data)
	    elif data[PKT_PROT_ID]==MGMT_RESP_PROTO:
		self.print_mgmt_resp_pkt(data)
        # save source address in dictionary of meta data
        meta_dict['EM_SRC_ID'] = data[PKT_SRC]       
        # packet from self?
        if data[PKT_SRC]==self.addr:
            # debug mode enabled?
            if self.debug_stderr:
                # yes! log the error
                sys.stderr.write("%d:in _radio_rx(): heard myself\n" % self.addr)
            # do nothing!
            return  
        # update received byte count
        self.rx_byte_count += len(data)
	# ------------------------
        # beacon packet processing
        # ------------------------
        if data[PKT_PROT_ID]==BEACON_PROTO:
            # yes! source a known neighbor?
            node=None
            if data[PKT_SRC] in self.nodes.keys():
                # yes! get corresponding node entry
                node=self.nodes[data[PKT_SRC]]
                # update neighbor node status
                node.update(time.time(),data[PKT_HC],data[PKT_PQ])
            else:
                # no! create a new node entry
                node=Node(time.time(),data[PKT_HC],data[PKT_PQ])
                self.nodes[data[PKT_SRC]]=node
		# add to mgmttable
		if self.addr==SINK_ADDR:
		   self.snmpmgmttable.addRow(self.createdefaultNewrow(data[PKT_SRC]))
	           if self.debug_stderr:
		      sys.stderr.write("SNMP_Table Size: %d, Added new Node: %d \n" %\
		      (self.snmpmgmttable.getTableSize(), self.snmpmgmttable.getColumn(-1, 'nodeAddr')))           
            # debug mode enabled?
            if self.debug_stderr:
                sys.stderr.write("%d:in _radio_rx(): node %d is alive\n" % \
                (self.addr,data[PKT_SRC]))
            # select next hop and update routing metrics
            self.SelectNextHop()
            # done!
            return
        # ack or data packet destined to self?
        #if data[PKT_PROT_ID]!= MGMT_PROTO and data[PKT_DEST]!=self.addr:
            # no! done!
           # return   
	# ----------------------
        # data packet processing
        # ----------------------
        if data[PKT_PROT_ID]==DATA_PROTO:
            # valid control field?
            if not data[PKT_CTRL] in [ARQ, NO_ARQ]:
                # no! log the error	
                if self.debug_stderr:
                    sys.stderr.write("%d:in _radio_rx(): bad control field: %d\n" % 
                         (self.addr,data[PKT_CTRL]))
                # do nothing!
                return      
            # is the ARQ protocol used?
            new_packet=False
            if data[PKT_CTRL]==ARQ:
                # source in neighbor dictionary?
		#if self.nodes[data[PKT_SRC]]:
		if data[PKT_SRC] in self.nodes.keys():
                        # last packet number and new packet number different?
			new_packet=self.nodes[data[PKT_SRC]].lpn!=data[PKT_CNT] 
			# save last packet number from that neighbor
                	self.nodes[data[PKT_SRC]].setLpn(data[PKT_CNT])
                        # yes! send an acknowledgement
                        self.send_ack(data[PKT_SRC], data[PKT_CNT],data[PKT_PROT_ID])
		else:
		    if self.debug_stderr:
		       sys.stderr.write("%d:in_radio_rx(): data from unknown neighbour" % self.addr) 
	    #  ARQ protocol not used or packet is new
            if data[PKT_CTRL]==NO_ARQ or new_packet:
                # this node is a sink?
                if self.addr==SINK_ADDR:
		    sys.stderr.write("SNMP_Table Size: %d, Added new Node: %d \n" % (self.snmpmgmttable.getTableSize(),self.snmpmgmttable.getColumn(-1, 'nodeAddr')))
                    # yes! deliver upper layer protocol
                    self.output_user_data((data, meta_dict))
 		    # add row if the PKT_SRC is not in the table
		    self.snmpmgmttable.addRow(self.createdefaultNewrow(data[PKT_SRC]))
                # else, forward to next hop
                else:
                    self._app_rx(self.pdupacker(data[PKT_MIN:]),data[PKT_CTRL])
            return
	# ----------------------------------------
        # mgmt packet processing for non-SINK node
        # ----------------------------------------
        if data[PKT_PROT_ID]==MGMT_PROTO:
	    message=[]
	    temp={}	    
	    # check if the packet is a old packet 
	    if not data[MGMT_ORG] in self.lasttrack:
	       self.lasttrack.update({data[MGMT_ORG]:{data[MGMT_TRACK]:time.time()}})
	    else:
	      if not data[MGMT_TRACK] in self.lasttrack[data[MGMT_ORG]]:
		 temp=self.lasttrack[data[MGMT_ORG]]
	         temp.update({data[MGMT_TRACK]:time.time()})
	         self.lasttrack.update({data[MGMT_ORG]:temp})
	      else:
	         if self.debug_stderr: 
		    sys.stderr.write("%d: Receive former mgmt packet, drop" % self.addr)
	         return         
	    self.send_ack(data[PKT_SRC], data[MGMT_TRACK], data[PKT_PROT_ID])
            # this node is the destination
            if self.addr==data[MGMT_DEST]:
	       checkload=[data[PKT_PROT_ID]]+list(data[2:8])
	       if self.checkhash(checkload, data[MGMT_HASH])==False:
		  self._mgmt_resp_rx(self.mgmt_resp_pdu(1, data[MGMT_TRACK], 3))
	          if self.debug_stderr: 
		     sys.stderr.write("%d: MGMT TRACK:Hash Wrong\n" % self.addr)
	          return
               else:# yes! processing
                  message=self.agent(data[MGMT_OPT],data[MGMT_OID],data[MGMT_VAL])
		  self._mgmt_resp_rx(self.mgmt_resp_pdu(message[0], data[MGMT_TRACK], message[1]))            
            # else, if the packet is not for this node
            else:   	 			    
               self._mgmt_rx(self.pdupacker(data[MGMT_MIN:MGMT_PKT_LENGTH]))
            return
	# ----------------------
        # mgmt resp packet processing
        # ----------------------
        if data[PKT_PROT_ID]==MGMT_RESP_PROTO:
            new_packet=False
            # source in neighbor dictionary?
	    #if self.nodes[data[PKT_SRC]]:
	    if data[PKT_SRC] in self.nodes.keys():
               # last packet number and new packet number different?
	       new_packet=self.nodes[data[PKT_SRC]].lpn!=data[PKT_CNT] 
	       # save last packet number from that neighbor
               self.nodes[data[PKT_SRC]].setLpn(data[PKT_CNT])
               # yes! send an acknowledgement
               self.send_ack(data[PKT_SRC], data[PKT_CNT],data[PKT_PROT_ID])
	    else:
		# the packet from an unknown source
	       if self.debug_stderr: 
		  sys.stderr.write("%d: Receive a mgmt resp packet from unknown source %d\n" % (self.addr, data[PKT_SRC]))
	       return
	    #  packet is new
            if new_packet:
                # this node is a sink?
                if self.addr==SINK_ADDR:
                    # yes! deliver to be processed
                    self.mgmt_data_processing((data[MGMT_RESP_MIN:MGMT_RESP_LENGTH-1]))
                # else, forward to next hop
                else:
                    self._mgmt_resp_rx(self.pdupacker(data[MGMT_RESP_MIN:]))
            return	
	# ---------------------
        # ack packet processing
        # ---------------------  
        if data[PKT_PROT_ID]==ARQ_PROTO:
            # channel idle?
            if self.addr==data[PKT_DEST] and self.CHANNEL_state==CHANNEL_IDLE:
		# data packet arq
		if data[PROTO_ACK]==DATA_PROTO:
		   # yes! in debug mode?
		   if self.debug_stderr: 
		      sys.stderr.write("%d:in _radio_rx(): got data ack %d while idle\n" % \
		      (self.addr,data[PKT_CNT]))
		   return
		# mgmt packet
		elif data[PROTO_ACK]==MGMT_PROTO:
	           # yes! in debug mode?
		   if self.debug_stderr: 
		      sys.stderr.write("%d:in _radio_rx(): got mgmt ack %d while idle\n" % \
		      (self.addr,data[PKT_CNT]))
		   return
		# mgmt resp packet
		elif data[PROTO_ACK]==MGMT_RESP_PROTO:
	           # yes! in debug mode?
		   if self.debug_stderr: 
		      sys.stderr.write("%d:in _radio_rx(): got mgmt resp ack %d while idle\n" % \
		      (self.addr,data[PKT_CNT]))
		   return
            # channel is busy! received expected acknowlegement number?
            elif self.addr==data[PKT_DEST] and self.CHANNEL_state==CHANNEL_BUSY:
		if data[PROTO_ACK]==DATA_PROTO:
		   if data[PKT_CNT]==self.expected_ack: 
                      # transition to idle state
                      self.CHANNEL_state=CHANNEL_IDLE
                      if self.debug_stderr: 
                         sys.stderr.write("%d:in _radio_rx(): got data ack: %d and recover to IDLE\n" % \
                         (self.addr,data[PKT_CNT]))
                   else:
                      if self.debug_stderr: 
                         sys.stderr.write("%d:in _radio_rx(): bad data ack %d (exp.: %d)\n" % \
                         (self.addr,data[PKT_CNT], self.expected_ack))
                      return
		elif data[PROTO_ACK]==MGMT_PROTO:
		     if data[PKT_CNT]==self.mgmt_expected_ack:
			# transition to idle state
			self.CHANNEL_state=CHANNEL_IDLE
			if self.debug_stderr:
			   sys.stderr.write("%d:in_radio_rx(): got mgmt ack %d and recover to IDLE\n" % \
			   (self.addr,data[PKT_CNT]))
	             else:
			if self.debug_stderr:
		           sys.stderr.write("%d:in_radio_rx(): bad mgmt ack %d (exp.: %d)\n" % \
		           (self.addr, data[PKT_CNT], self.mgmt_expected_ack))
			return
		elif data[PROTO_ACK]==MGMT_RESP_PROTO:
		     if data[PKT_CNT]==self.expected_ack:
			# transition to idle state
			self.CHANNEL_state=CHANNEL_IDLE
			if self.debug_stderr:
			   sys.stderr.write("%d:in_radio_rx(): got mgmt resp ack %d and recover to IDLE\n" % \
			   (self.addr,data[PKT_CNT]))
	             else:
			if self.debug_stderr:
		           sys.stderr.write("%d:in_radio_rx(): bad mgmt resp ack %d (exp.:%d)\n" % \
		           (self.addr,data[PKT_CNT]), self.expected_ack)
			return
            # run the protocol finite state machine
            self.run_fsm()
            return 
    # ---------------------------------------------------
    # Handle a message from the application, ARQ not used
    # ---------------------------------------------------
    def app_rx(self, msg):
      if len(self.nodes)>0:
        with self.lock:
            self._app_rx(msg, False)
    
    # ---------------------------------------------------
    # Handle a message from the application, ARQ is used
    # ---------------------------------------------------
    def app_rx_arq(self, msg):
        with self.lock:
            self._app_rx(msg, True)

    # ---------------------------------------------------------------
    # Handle a message from the application, exclusive access assumed
    # msg = message from the application
    # arq = True when ARQ protocol is selected, False otherwise
    # ---------------------------------------------------------------
    def _app_rx(self, msg, arq):
        # verify structure, must be meta-data pair
        try:
            meta=pmt.car(msg)
            data=pmt.cdr(msg)
        except:
            # wrong structure!
            if self.debug_stderr: 
                sys.stderr.write("in _app_rx(): message is not a PDU\n")
            # do nothing!
            return 
        # is data a vector of unsigned chars?
        if pmt.is_u8vector(data):
            # yes! convert to python data type
            data=pmt.u8vector_elements(data)
        else:
            # no!
            if self.debug_stderr: 
                sys.stderr.write("in _app_rx(): data is not a u8vector\n")
            # do nothing!
            return   
        # convert meta data to a Python dictionary
        meta_dict=pmt.to_python(meta)
        if not (type(meta_dict) is dict):
            meta_dict={}   
        # push the packet
        self.dispatch_app_rx(data,meta_dict,arq)

    # --------------------------------------------------------
    # Push a packet 
    # data = packet
    # meta_dict = meta dictionary
    # arq = True when ARQ protocol is selected, False otherwise
    # --------------------------------------------------------
    def dispatch_app_rx(self, data, meta_dict,arq): 
        # ARQ selected?
        if arq:
            # transmit with the ARQ protocol!
            # packet queue is full)
            if self.queue.qsize()>=self.max_queue_size:
               # pop one packet
               self.queue.get()
            self.queue.put((data, meta_dict))
            self.run_fsm()
        else:
            # transmit with the no ARQ protocol!
            self.tx_no_arq((data, meta_dict), DATA_PROTO)
    
    # ----------------------------------------------------------
    # Handle a control signal
    # Handler triggered on a periodic basis by a Message Strobe.
    # Sends hello messages. Updates the neighbor dictionary.
    # Runs the FSM.
    # ----------------------------------------------------------
    def ctrl_rx(self, msg):
	with self.lock:
            # if sink node or connected to sink (path quality>0)?
            if self.addr==SINK_ADDR or self.pq>0:
                if (self.broadcast_interval > 0) and \
                    (self.last_tx_time is None or \
                    (time.time() - self.last_tx_time) >= \
                     self.broadcast_interval*2*random.random()): # randomization
                    # send a hello message
                    self.send_beacon_pkt() 
            # update the neighbor dictionary 
            self.check_nodes()
	    # check if the manager is online and handle a snmp request 
	    if self.addr == SINK_ADDR:
	       self._snmpManager.handle_request()  
	    # send IN-BAND mgmt pkt if queue is not empty
	    if self.addr == SINK_ADDR:
	       while self.snmpmgmttable.pktforsent.qsize()!=0:
	          self.mgmt_rx(self.snmpmgmttable.pktforsent.get())	
            # run the protocol FSM	
            self.run_fsm() 
    # ---------------------------------------   
    # ARQ protocol Finite State Machine (FSM)
    # ---------------------------------------
    def run_fsm(self):
        # conected to sink?
        if self.pq==0: # no!
           if self.debug_stderr: 
              sys.stderr.write("FSM init: %d:in run_fsm(): not connected!\n" % self.addr)
            # do nothing!
           return
        # IDLE state
        # ----------
        if self.CHANNEL_state==CHANNEL_IDLE: 
           # A mgmt resp packet queued for transmission?
           if not self.mgmt_resp_queue.empty(): 
                # get the packet
                self.arq_pdu_tuple=self.mgmt_resp_queue.get()
                # save the current packet number 
                self.expected_ack=self.pkt_cnt 
                if self.debug_stderr: 
                   sys.stderr.write("%d:in run_fsm(): sending management resp packet %d\n" % \
                   (self.addr,self.pkt_cnt))
                # record packet type
		self.pkttype=2
		# transmitting the data packet
                self.mgmt_resp_tx(self.arq_pdu_tuple)
		if self.debug_stderr:
		   sys.stderr.write("pkttype:%d\n" % self.pkttype)
                # save the transmission time
                self.time_of_tx=time.time() 
                # transition to the busy state
                self.CHANNEL_state=CHANNEL_BUSY
                # update the transmitted packet count
                self.arq_pkts_txed+=1
                # reset the retry count
                self.retries=0
                # determine the new backoff percentage
                self.next_random_backoff_percentage = self.backoff_randomness * random.random()
           # A mgmt packet queued for transmission?
	   elif not self.mgmt_queue.empty(): 
	        self.arq_pdu_tuple=self.mgmt_queue.get()
		self.mgmt_expected_ack=self.mgmt_track
	        if self.debug_stderr:
	       	   sys.stderr.write("%d:in run_fsm(): sending mgmt packet, pkt track No: %d\n" % \
                   (self.addr,self.mgmt_track))
		# record packet type
		self.pkttype=1
		# transimitting the mgmt packet
		self.mgmt_tx(self.arq_pdu_tuple)
		if self.debug_stderr:
		   sys.stderr.write("pkttype:%d\n" % self.pkttype)
		self.time_of_tx=time.time() 
                # transition to the busy state
                self.CHANNEL_state=CHANNEL_BUSY
                # update the transmitted packet count
                self.arq_pkts_txed+=1
                # reset the retry count
                self.retries=0
                # determine the new backoff percentage
                self.next_random_backoff_percentage = self.backoff_randomness * random.random()
	    # A data packet queued for transmission?
           elif not self.queue.empty(): 
                # get the packet
                self.arq_pdu_tuple=self.queue.get()
                # save the current packet number 
                self.expected_ack=self.pkt_cnt 
                if self.debug_stderr: 
                   sys.stderr.write("%d:in run_fsm(): sending data packet %d\n" % \
                   (self.addr,self.pkt_cnt))
                # record packet type
		self.pkttype=0
		# transmitting the data packet
                self.tx_arq(self.arq_pdu_tuple, DATA_PROTO)
		if self.debug_stderr:
		   sys.stderr.write("pkttype:%d\n" % self.pkttype)
                # save the transmission time
                self.time_of_tx=time.time() 
                # transition to the busy state
                self.CHANNEL_state=CHANNEL_BUSY
                # update the transmitted packet count
                self.arq_pkts_txed+=1
                # reset the retry count
                self.retries=0
                # determine the new backoff percentage
                self.next_random_backoff_percentage = self.backoff_randomness * random.random()
	   	 
        # BUSY state
        # ----------
        if self.CHANNEL_state==CHANNEL_BUSY: 
            # timeout?
            if self.exp_backoff:
                backedoff_timeout=self.timeout * (2**self.retries)
            else:
                backedoff_timeout=self.timeout * (self.retries + 1)
            backedoff_timeout*=(1.0 + self.next_random_backoff_percentage) 
            if (time.time() - self.time_of_tx) > backedoff_timeout:
                # maximum number of retries reached?
                if self.retries==self.max_attempts:            
                    if self.debug_stderr: 
                        sys.stderr.write("%d: in run_fsm(): ARQ failed after %d attempts\n" % \
                        (self.addr, self.retries))
                    # reset the retry count
                    self.retries=0
                    # transition to the idle state
                    self.CHANNEL_state=CHANNEL_IDLE
                    # update the failed transmitted packet count
                    self.failed_arq+=1 
		    if self.addr!=SINK_ADDR and self.pkttype==1:
			# track number problem
			resppdu=self.mgmt_resp_pdu(1, self.mgmt_track-1 if self.mgmt_track != 0 else 255, 2)		        
			self._mgmt_resp_rx(resppdu)
			if self.debug_stderr:
			   sys.stderr.write("%d: No arq pkt receive. Warning: this node is on the edge of the network and mgmt_pkt not reach the dest\n" % self.addr)
			   sys.stderr.write("%d: sending error message to sink node\n" % self.addr)		
                # retry transmission!
                else:
                    # increment retry count
                    self.retries+=1
                    time_now=time.time()
                    # re-transmit the packet
                    if self.debug_stderr: 
                        sys.stderr.write("%d: CHANNEL-BUSYin run_fsm(): retransmission after %d retries\n" % \
                        (self.addr, self.retries))
			sys.stderr.write("current retransmission pkttype: %d\n" % self.pkttype)
	 	    # check the type of last packet that use the fsm
		    if self.pkttype==0:
                       self.retx_arq(self.arq_pdu_tuple, DATA_PROTO)
		    elif self.pkttype==1:
		       self.mgmt_retx(self.arq_pdu_tuple)
		    elif self.pkttype==2:
		       self.mgmt_resp_retx(self.arq_pdu_tuple)
                    # save the trasnmission time
                    self.time_of_tx=time_now
                    # determine the new backoff percentage
                    self.next_random_backoff_percentage=self.backoff_randomness*random.random()
                    # increment the packet retransmission count
                    self.arq_retxed+=1

    # ---------------------------------------   
    # Network Management Function 
    # ---------------------------------------
    
    # ---------------------------------------
    # OUT-BAND Management
    # ---------------------------------------
    # ------------------------------
    # createNewrow
    # ------------------------------   
    def createdefaultNewrow(self, addr):
	timestamp=self._GetUTCTime()
	return {'nodeAddr':addr, 'maxAttempts':self.max_attempts, 
		'broadcastInterval':self.broadcast_interval, 'mgmtMode':self.mgmtMode,
		 'lastUpdated':'nodeAddr', 'lastUpdatedTime':timestamp, 'mgmtInfo':0}

    # -----------------------------
    # Processing feed back of mgmt
    # -----------------------------
    def mgmt_data_processing(self, data):
	self.snmpmgmttable.processingColumn(data)
	# write packet to standard output
	sys.stdout.write(time.asctime(time.localtime(time.time()))+" : ");
        # print data
        for i in range (0,len(data)):
            sys.stdout.write("%d " % data[i])
        sys.stdout.write("\n") 

    #--------IN-BAND Management PKT DOWNward Passing--------
    #--MGMT_APP Passing Format: VALUE|DEST|OPT|OID--
    #-------------------------------------------------------

    # ---------------------------------------------------
    # Handle a management message from the application, ARQ default
    # ---------------------------------------------------
    # msg is a pdu
    def mgmt_rx(self, msg):
       # SINK will not flush down the mgmt packet unless there exists neighbour nodes
       # May need adding extra procedure to ask app for resend 
       # if the network is not ready
       temp={}
       if len(self.nodes)>0:
        with self.lock:
	    if not bool(self.lasttrack):
		self.lasttrack.update({self.addr:{self.mgmt_track:time.time()}})
		self._mgmt_rx(msg)
	    else:
		temp=self.lasttrack[self.addr]
	        temp.update({self.mgmt_track:time.time()})
	        self.lasttrack.update({self.addr:temp})
                self._mgmt_rx(msg)	

    # ---------------------------------------
    # Handle a message from the SNMP command
    # msg = message from the management app 
    # ---------------------------------------  
    def _mgmt_rx(self, msg):
	try:
	    meta=pmt.car(msg)
	    data=pmt.cdr(msg)
	except:
	    if self.debug_stderr:
		sys.stderr.write("%d: in _mgmt_rx(): MGMT message is not a PDU \n" % self.addr) 		    
	    return
	if pmt.is_u8vector(data):
	    data=pmt.u8vector_elements(data)
	else:
            if self.debug_stderr:
		sys.stderr.write("in _mgmt_rx(): data is not a u8vcetor\n")
	    return
	meta_dict=pmt.to_python(meta)
	if not (type(meta_dict) is dict):
	    meta_dict={}
	self.dispatch_mgmt_rx(data,meta_dict)

    # --------------------------------------------------------
    # Push a mgmt packet 
    # data = mgmt packet
    # meta_dict = meta dictionary
    # --------------------------------------------------------
    def dispatch_mgmt_rx(self, data, meta_dict): 
        if self.mgmt_queue.qsize()>=self.max_queue_size:
           self.mgmt_queue.get()
        self.mgmt_queue.put((data, meta_dict))
        self.run_fsm()

    # --------------------------------------------
    # transmit a management data packet
    # --------------------------------------------
    def mgmt_tx(self, pdu_tuple):
	if len(self.nodes)>0:
	   self.send_mgmt_pkt(pdu_tuple, self.mgmt_track)
	   self.mgmt_track=(self.mgmt_track+1) % 256

    # --------------------------------------------
    # retransmit a management data packet
    # --------------------------------------------
    def mgmt_retx(self, pdu_tuple):
	if len(self.nodes)>0:
	   self.send_mgmt_pkt(pdu_tuple, self.mgmt_track-1 if self.mgmt_track != 0 else 255)

    # ---------------------------------------------------------
    # Transmit a mgmt packet
    # pdu_tuple = PDU pair (payload,meta data)
    # ---------------------------------------------------------
    def send_mgmt_pkt(self, pdu_tuple, mgmt_track):
        # connected to sink?
        if self.pq==0:
            # no! drop the packet
            if self.debug_stderr: 
                sys.stderr.write("%d:in send_mgmt_pkt_radio(): packet dropped (not connected)\n" %
                    self.addr) 
            return  	
        data=[MGMT_PROTO, self.addr, mgmt_track]
	# if sink add orginal sender address (Done Once)
	if self.addr==SINK_ADDR:
	   data+=[self.addr]
	payload = pdu_tuple[0]
        if payload is None:
           payload = []
        elif isinstance(payload, str):
           payload = map(ord, list(payload))
        elif not isinstance(payload, list):
           payload = list(payload)
	if payload[1]==SINK_ADDR:
	   if self.CHANNEL_state==CHANNEL_BUSY:
	      self.CHANNEL_state==CHANNEL_IDLE
	   msg=self.agent(payload[2],payload[3],payload[0])
	   resppkt=[msg[0], self.addr, mgmt_track, msg[1]]
	   self.mgmt_data_processing(resppkt)
	   return
        data += payload
	# if sink add hash value (Done Once)
	if self.addr==SINK_ADDR:
	  # add hash value at the end
          data += [self.addhash([data[0]]+data[2:], self.secretkey)]
        # debug mode enabled?
        if self.debug_stderr:
           # yes! log the packet
           sys.stderr.write("%d: send_mgmt_pkt_radio(): sending mgmt packet:\n" % self.addr)
           self.print_mgmt_pkt(data)
        # conversion to PMT PDU (meta data, data)
        pdu = pmt.cons( \
            pmt.to_pmt({}), \
            pmt.init_u8vector(len(data), data))
        # push to radio msg port
        self.message_port_pub(pmt.intern('to_radio'),pdu)
        # save current transmit time
        with self.lock:
            self.last_tx_time = time.time()

    # ---------------------------------------------------------
    # Print a mgmt pkt
    # ---------------------------------------------------------	
    def print_mgmt_pkt(self, pkt):
	    # invalid mgmt packet length?
	if len(pkt)!=MGMT_PKT_LENGTH:
	    # yes!
	    sys.stderr.write("in print_mgmt_pkt(): mgmt packet invalid length!\n")
	    return
	    # no!
	sys.stderr.write("PROT ID: %d " % pkt[PKT_PROT_ID])
	sys.stderr.write("PKT TEMP FROM: %d " % pkt[PKT_SRC])
	sys.stderr.write("TRACK :%d " % pkt[MGMT_TRACK])
	sys.stderr.write("PKT ORG FROM: %d " % pkt[MGMT_ORG])
	sys.stderr.write("VALUE :%d " % pkt[MGMT_VAL])
	sys.stderr.write("DEST: %d " % pkt[MGMT_DEST])
	sys.stderr.write("OPT: %d " % pkt[MGMT_OPT])
	sys.stderr.write("OID: %d " % pkt[MGMT_OID])
	sys.stderr.write("HASH: %d\n" % pkt[MGMT_HASH])

    # ---------------------------------------
    # Network management Agent
    # ---------------------------------------
    def agent(self, opt, oid, value):
	#FLAG/VALUE&CODE
        self.message=[]
	# check oid valid
	if oid in self.mib:
	   # GET
           if opt == 0:
	      message=[0, self.mib[oid]]
	   # SET
	   elif opt == 1:
	      self.mib[oid]=value
	      self.message= [1,0]
	else:
	# wrong id
	   self.message= [1,1]  	
        # return result
        return self.message

    #--------Management Response PKT UPward Passing--------
    #--MGMT_RESP Passing Format: TRACKNUM|VALUE--
    #-------------------------------------------------

    #--------------------
    # mgmt response using arq
    #--------------------
    def _mgmt_resp_rx(self, msg):
	try:
	    meta=pmt.car(msg)
	    data=pmt.cdr(msg)
	except:
	    if self.debug_stderr:
		sys.stderr.write("%d: in _mgmt_resp_rx(): MGMT RESP message is not a PDU \n" % self.addr) 		    
	    return
	if pmt.is_u8vector(data):
	    data=pmt.u8vector_elements(data)
	else:
            if self.debug_stderr:
		sys.stderr.write("in _mgmt_resp_rx(): data is not a u8vcetor\n")
	    return
	meta_dict=pmt.to_python(meta)
	if not (type(meta_dict) is dict):
	    meta_dict={}
	self.dispatch_mgmt_resp_rx(data,meta_dict)

    #---------------------
    # mgmt resp dispatch
    #---------------------
    def dispatch_mgmt_resp_rx(self, data, meta_dict): 
        if self.mgmt_resp_queue.qsize()>=self.max_queue_size:
           self.mgmt_resp_queue.get()
        self.mgmt_resp_queue.put((data, meta_dict))
        self.run_fsm()

    #--------------------------------------------
    # transmit a management resp packet
    #--------------------------------------------
    def mgmt_resp_tx(self, pdu_tuple):
	if len(self.nodes)>0:
	   self.send_mgmt_resp_pkt(pdu_tuple, self.pkt_cnt)
	   self.pkt_cnt=(self.pkt_cnt+1) % 256	

    #--------------------------------------------
    # transmit a management resp packet
    #--------------------------------------------
    def mgmt_resp_retx(self, pdu_tuple):
	if len(self.nodes)>0:
	   self.send_mgmt_resp_pkt(pdu_tuple, self.pkt_cnt-1 if self.pkt_cnt != 0 else 255)

    #--------------------------------------------
    # send a mgmt resp packet
    #-------------------------------------------- 
    def send_mgmt_resp_pkt(self, pdu_tuple, pkt_cnt): 
        # connected to sink?
        if self.pq==0:
            # no! drop the packet
            if self.debug_stderr: 
                sys.stderr.write("%d:in send_mgmt_resp_radio(): packet dropped (not connected)\n" %
                    self.addr) 
            return  
        # packet to self?
        if self.addr==self.next_hop:
            # no! drop the packet
            if self.debug_stderr: 
                sys.stderr.write("%d:in send_mgmt_resp_radio(): packet dropped (packet to self)\n" % self.addr) 
            return  
        # yes! data packet header structure
        data = [MGMT_RESP_PROTO, self.addr, self.next_hop, pkt_cnt]
        # add payload
        payload = pdu_tuple[0]
        if payload is None:
            payload = []
        elif isinstance(payload, str):
            payload = map(ord, list(payload))
        elif not isinstance(payload, list):
            payload = list(payload)
        data += payload
	if self.addr== data[MGMT_RESP_SRC]:
	   data+=[self.addhash(data[MGMT_RESP_LENGTH:], self.secretkey)]
        # debug mode enabled?
        if self.debug_stderr:
           # yes! log the packet
           sys.stderr.write("%d:in send_mgmt_resp_radio(): sending packet:\n" % self.addr)
           self.print_mgmt_resp_pkt(data)
        # conversion to PMT PDU (meta data, data)
        pdu = pmt.cons( \
            pmt.to_pmt({}), \
            pmt.init_u8vector(len(data), data))
        # push to radio msg port
        self.message_port_pub(pmt.intern('to_radio'),pdu)
        # save current transmit time
        with self.lock:
            self.last_tx_time = time.time()
    #--------------------------
    # print mgmt_resp pkt
    #--------------------------
    def print_mgmt_resp_pkt(self, pkt):
	    # invalid mgmt packet length?
	if len(pkt)!=MGMT_RESP_LENGTH:
	    # yes!
	    sys.stderr.write("in print_mgmt_resp_pkt(): mgmt resp packet invalid length!\n")
	    return
	    # no!
	sys.stderr.write("PROT ID: %d " % pkt[PKT_PROT_ID])
	sys.stderr.write("MGMT RESP PKT FROM: %d " % pkt[PKT_SRC])
	sys.stderr.write("MGMT RESP PKT TO :%d " % pkt[PKT_DEST])
	sys.stderr.write("MGMT RESP PKT CNT :%d " % pkt[PKT_CNT])
	sys.stderr.write("MGMT RESP FLAG: %d " % pkt[MGMT_RESP_FLAG])
	sys.stderr.write("MGMT RESP SRC: %d " % pkt[MGMT_RESP_SRC])
	sys.stderr.write("MGMT RESP TRACK: %d " % pkt[MGMT_RESP_TRACK])
	sys.stderr.write("MGMT RESP VALUE: %d " % pkt[MGMT_RESP_VAL])
	sys.stderr.write("MGMT RESP HASH: %d " % pkt[MGMT_RESP_HASH]+"\n")

    #---------------------------------------
    # generate mgmt_resp pdu
    #---------------------------------------
    def mgmt_resp_pdu(self, mgmtflag, mgmt_track, message):
        data=[mgmtflag, self.addr, mgmt_track, message]
        return self.pdupacker(data)

    # ---------------------------------------   
    # Utility Functions 
    # ---------------------------------------

    #--------------------------
    # Hash
    #--------------------------

    #-------add hash-----------	
    def addhash(self, data, key):
	#convert list to full string
	hashstr=" ".join(str(i) for i in data)
	hashstr+=key
	# using sha256
	hashed_value = hashlib.sha256(hashstr)
	# return a integer hash value
	return int(hashed_value.hexdigest()[0:2],16)

    #-------check hash---------
    def checkhash(self, data, hashvalue):
	localmsg=self.addhash(data, self.secretkey)
	if localmsg==hashvalue:
	   return True
	else:
	   return False

    # -------------------------
    # PDU packing
    # -------------------------
    def pdupacker(self, data):
	pdu = pmt.cons( \
        pmt.to_pmt({}), \
        pmt.init_u8vector(len(data), data))		
        return pdu

    # -------------------------
    # Maintain MGMT Track Table
    # -------------------------
    def updatetracktable(self):
       if bool(self.lasttrack)==True:
	#out loop for node
	for n in self.lasttrack:
	#inner loop for tracknumber
	 for key, value in self.lasttrack[n].items():
	     if	value<=time.time()-120:
		del self.lasttrack[n][key]


    # ------------------------------
    # UTC Time for SNMP
    # ------------------------------
    def _GetUTCTime(self):
	temp=(datetime.utcnow().strftime("%Y,%m,%d,%H,%M,%S,%f"))[:-5].split(',')
	timestr=map(int,temp)
	final=struct.pack('>HBBBBBB', *timestr)
	return final
	
