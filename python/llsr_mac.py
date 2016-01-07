#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# ---------------------------------------
# Location-free Link State Routing (LLSR)
# --------------------------------------- 
# Copyright 2016 Michel Barbeau, Carleton University.
# Version: January 6, 2016
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
# 1. Handler: radio_rx()
#    Handles a message from the radio.
#    Call sequence: _radio_rx() -> 
#        [SelectNextHop() | _app_rx() | run_fsm() ]
# 2. Handler: app_rx()
#    Accepts a PDU from the application and sends and sends it.
#    Call sequence: _app_rx() -> dispatch_app_rx() -> tx_no_arq() ->
#        send_pkt_radio()
# 3. Handler: app_rx_arq()
#    Accepts a PDU from the application and sends using the ARQ protocol.
#    Call sequence: _app_rx() -> dispatch_app_rx() -> queue.put() -> 
#        run_fsm() -> tx_arq() -> send_pkt_radio()
# 4. Handler: ctrl_rx()
#    Handles a control signal.
#    Calls: send_beacon_pkt(), check_nodes(), run_fsm()
# ----------------------------------------------------------------------

from __future__ import with_statement
import numpy
from gnuradio import gr
import pmt
from gnuradio.digital import packet_utils
import gnuradio.digital as gr_digital
import sys, time, random, struct, threading
from math import pi
import Queue
from constants import *

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
    def update(self,time,hc,pq):
        # last time a beacon received
        self.last_heard=time
        # hop count
        self.hc=hc
        # path quality
        self.pq=pq

class llsr_mac(gr.basic_block):
    """
    Location-free Link State Routing
    """
    def __init__(self,addr,timeout,max_attempts,broadcast_interval=2.0,
                 exp_backoff=True,backoff_randomness=0.05,node_expiry_delay=10.0):
        gr.basic_block.__init__(self,
            name="llsr_mac",
            in_sig=None,
            out_sig=None)
        # lock for exclusive access
        self.lock=threading.RLock()
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
        # routing state
        # -------------------------------------------------
        # sink node?
        if self.addr==SINK_ADDR:
            # yes!
            self.hc=0 # hop count
            self.pq=255 # path quality, max value
        else:
            # no!
            self.hc=255 # hop count, 255=infinity
            self.pq=0 # path quality, 0=not connected to sink
        self.next_hop=UNDEF_ADDR # 255=undefined
        # dictionary of neighbor nodes
        self.nodes={}
        self.node_expiry_delay=node_expiry_delay
        # beacon broadcast period
        self.broadcast_interval=broadcast_interval
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
            self.next_hop=UNDEF_ADDR
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
            # get the maximum path quality
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
           sys.stderr.write("in send_beacon_pkt(): sending beacon packet:\n")
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
        sys.stderr.write("CNT: %d\n" % pkt[PKT_CNT])

    # ---------------------------------------------
    # transmit ack packet
    # ack_addr = destination address
    # ack_pkt_cnt = acknowledged data packet number
    # ---------------------------------------------
    def send_ack(self,ack_addr,ack_pkt_cnt):
        # data packet header structure
        data = [ARQ_PROTO,self.addr,ack_addr,ack_pkt_cnt]
        # debug mode enabled?
        if self.debug_stderr:
           # yes! log the packet
           sys.stderr.write("in send_ack(): sending ack packet:\n")
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
    # transmit a data packet
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
                sys.stderr.write("send_pkt_radio(): packet dropped\n") 
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
           sys.stderr.write("in send_pkt_radio(): sending packet:\n")
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
    
   # ------------------------
   # push data to application
   # ------------------------
    def output_user_data(self, pdu_tuple):
        self.message_port_pub(pmt.intern('to_app'), \
             pmt.cons(pmt.to_pmt(pdu_tuple[1]), \
                      pmt.init_u8vector(len(pdu_tuple[0][PKT_MIN:]), \
                                        pdu_tuple[0][PKT_MIN:])))
    
    # -----------------------------------
    # scan and update the node dictionary
    # -----------------------------------
    def check_nodes(self):
        # get current time
        time_now = time.time()
        # take a copy of neighbor list
        keys=self.nodes.keys() 
        for k in keys:
            # get time since this node has been heard
            diff=time_now-self.nodes[k].last_heard
            # lost link with tha node?
            if diff > self.node_expiry_delay:
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
        # validation
        # ----------
        # determine result of CRC evaluation
        crc_ok = True # default
        if 'CRC_OK' in meta_dict.keys():
            crc_ok = meta_dict['CRC_OK']  
        # valid CRC?
        if not crc_ok:
            # no! debug mode enabled?
            if self.debug_stderr:
                # log the error
                sys.stderr.write("in _radio_rx(): packet CRC error\n" )
            # do nothing!
            return
        # valid protocol ID?
        if not data[PKT_PROT_ID] in [ARQ_PROTO,DATA_PROTO,BEACON_PROTO]:
            # no! log the error
            if self.debug_stderr: 
                sys.stderr.write("in _radio_rx(): invalid protocol ID: %d\n" % \
                    (data[PKT_PROT_ID]))
        # valid packet length?
        if (data[PKT_PROT_ID]==ARQ_PROTO and len(data) != ACK_PKT_LENGTH) or \
            (data[PKT_PROT_ID]==DATA_PROTO and len(data) < PKT_MIN) or \
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
            sys.stderr.write("in _radio_rx(): receiving packet:\n")
            if data[PKT_PROT_ID]==ARQ_PROTO:
                self.print_ack_pkt(data)
            elif data[PKT_PROT_ID]==DATA_PROTO:
                self.print_pkt(data)
            elif data[PKT_PROT_ID]==BEACON_PROTO:
                self.print_beacon_pkt(data)
        # save source address in dictionary of meta data
        meta_dict['EM_SRC_ID'] = data[PKT_SRC]       
        # packet from self?
        if data[PKT_SRC]==self.addr:
            # debug mode enabled?
            if self.debug_stderr:
                # yes! log the error
                sys.stderr.write("in _radio_rx(): heard myself\n")
            # do nothing!
            return  
        # update received byte count
        self.rx_byte_count += len(data)
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
            # debug mode enabled?
            if self.debug_stderr:
                sys.stderr.write("in _radio_rx(): node %d is alive\n" % \
                     (data[PKT_SRC]))
            # select next hop and update routing metrics
            self.SelectNextHop()
            # done!
            return
        # ack or data packet destined to self?
        if data[PKT_DEST]!=self.addr:
            # no! done!
            return   
        # data packet processing
        # ----------------------
        if data[PKT_PROT_ID]==DATA_PROTO:
            # valid control field?
            if not data[PKT_CTRL] in [ARQ, NO_ARQ]:
                # no! log the error
                if self.debug_stderr:
                    sys.stderr.write("in _radio_rx(): bad control field: %d\n" % (data[PKT_CTRL]))
                # do nothing!
                return      
            # is the ARQ protocol used?
            if data[PKT_CTRL]==ARQ:
                # yes! send an acknowledgement
                self.send_ack(data[PKT_SRC], data[PKT_CNT]) 
            # this node is a sink?
            if self.addr==SINK_ADDR:
                # yes! deliver upper layer protocol
                self.output_user_data((data, meta_dict))
            # else, forward to next hop
            else:
                self._app_rx(self,data[PKT_MIN:],data[PKT_CTRL])
            return
        # ack packet processing
        # ---------------------  
        if data[PKT_PROT_ID]==ARQ_PROTO:
            # channel idle?
            if self.CHANNEL_state==CHANNEL_IDLE:
                # yes! in debug mode?
                if self.debug_stderr: 
                    sys.stderr.write("in _radio_rx(): got ack %d while idle\n" % \
                    (data[PKT_CNT]))
                return
            # channel is busy! received expected acknowlegement number?
            elif data[PKT_CNT]==self.expected_ack: 
                # transition to idle state
                self.CHANNEL_state=CHANNEL_IDLE
                if self.debug_stderr: 
                    sys.stderr.write("in _radio_rx(): got ack %d\n" % \
                    (data[PKT_CNT]))
                else:
                    if self.debug_stderr: 
                        sys.stderr.write("in _radio_rx(): bad ack %d (exp.: %d)\n" % \
                        (data[PKT_CNT], self.expected_ack))
                    return
            # run the protocol finite state machine
            self.run_fsm()
            return

    # ---------------------------------------------------
    # Handle a message from the application, ARQ not used
    # ---------------------------------------------------
    def app_rx(self, msg):
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
            meta = pmt.car(msg)
            data =  pmt.cdr(msg)
        except:
            if self.debug_stderr: 
                sys.stderr.write("in _app_rx(): message is not a PDU\n")
            return 
        # is data a vector of unsigned chars?
        if pmt.is_u8vector(data):
            # yes! convert to python data tpe
            data = pmt.u8vector_elements(data)
        else:
            # no!
            if self.debug_stderr: 
                sys.stderr.write("in _app_rx(): data is not a u8vector\n")
            # do nothing!
            return   
        # convert meta data to a Python dictionary
        meta_dict = pmt.to_python(meta)
        if not (type(meta_dict) is dict):
            meta_dict = {}
        if not (type(meta_dict) is dict):
            meta_dict = {}    
        self.dispatch_app_rx(data,meta_dict,arq)

    # --------------------------------------------------------
    # Push a packet 
    # data = packet
    # meta_dict = meta dictionary
    # arq = True when ARQ protocol is selected, False otherwise
    # --------------------------------------------------------
    def dispatch_app_rx(self, data, meta_dict,arq): 
        # assign tx path depending on whether PMT_BOOL EM_USE_ARQ is true or false
        if arq:
             self.queue.put((data, meta_dict))
             self.run_fsm()
        else:
           # transmit with the no ARQ protocol
           self.tx_no_arq((data, meta_dict), DATA_PROTO)
    
    # -----------------------
    # Handle a control signal
    # -----------------------
    def ctrl_rx(self,msg):
        # not sink node and connected to sink?
        if self.addr!=SINK_ADDR and self.pq==0:
            # do nothing
            return
        with self.lock:
            if (self.broadcast_interval > 0) and \
                (self.last_tx_time is None or \
                (time.time() - self.last_tx_time) >= self.broadcast_interval):
                # send a hello message
                self.send_beacon_pkt() 
            # update the neighbor dictionary 
            self.check_nodes()
            # run the protocol FSM
            self.run_fsm() 

    # ---------------------------------------   
    # ARQ protocol Finite State Machine (FSM)
    # ---------------------------------------
    def run_fsm(self):
        # conected to sink?
        if self.pq==0:
            if self.debug_stderr: 
                sys.stderr.write("in run_fsm(): not connected!\n")
            # do nothing!
            return
        # IDLE state
        # ----------
        if self.CHANNEL_state==CHANNEL_IDLE: 
            # an ARQ packet queued for transmission?
            if not self.queue.empty(): 
                # get the packet
                self.arq_pdu_tuple=self.queue.get()
                # save the current packet number 
                self.expected_ack=self.pkt_cnt 
                if self.debug_stderr: 
                    sys.stderr.write("in run_fsm(): sending packet %d\n" % (self.pkt_cnt))
                # transmit the packet
                self.tx_arq(self.arq_pdu_tuple, DATA_PROTO)
                # save the trasnmission time
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
                        sys.stderr.write("in run_fsm(): ARQ failed after %d attempts\n" % \
                        (self.retries))
                    # reset the retry count
                    self.retries=0
                    # transition to the idle state
                    self.CHANNEL_state=CHANNEL_IDLE
                    # update the failed transmitted packet count
                    self.failed_arq+=1 
                # retry transmission!
                else:
                    # increment retry count
                    self.retries+=1
                    time_now=time.time()
                    # re-transmit the packet
                    if self.debug_stderr: 
                        sys.stderr.write("in run_fsm(): retransmission after %d retries\n" % \
                        (self.retries))
                    self.tx_arq(self.arq_pdu_tuple, DATA_PROTO)
                    # save the trasnmission time
                    self.time_of_tx=time_now
                    # determine the new backoff percentage
                    self.next_random_backoff_percentage=self.backoff_randomness*random.random()
                    # increment the packet retransmission count
                    self.arq_retxed+=1
