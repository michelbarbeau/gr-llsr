#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# --------------------------------
# Location-free Link State Routing
# --------------------------------
# Author: Michel Barbeau, Carleton University
# Version: January 21, 2016
# Re-using:
#
#  File: constants.py
#  
#  Copyright 2014 Balint Seeber <balint256@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#------------------------------------------
#  MGMT INFO AND ERROR CODE 
#------------------------------------------
# 0 : SET OPT SUCCESS
# 1 : OID SET FAIL
# 2 : DEST NOT FOUND
# 3 : AUTHENTICATION FAIL
# 4 : SINK NO NEIGHBOUR NODES DETECTED
#------------------------------------------

# Data/acknowledgement packet  definition
PKT_PROT_ID = 0
PKT_SRC = 1
PKT_DEST = 2
PKT_CNT = 3

PROTO_ACK = 4

PKT_CTRL = 4

PKT_MIN = 5 # packet minimum length
MGMT_MIN = 3 # MGMT packet minimum lenghth
MGMT_RESP_MIN = 4 # MGMT RESP packet minimum length
ACK_PKT_LENGTH = 5 # packet length
MGMT_PKT_LENGTH = 9 # MGMT packet length
MGMT_RESP_LENGTH = 9 # MGMT resp packet length
# MGMT packet definition
MGMT_TRACK = 2
MGMT_ORG=3
MGMT_VAL = 4
MGMT_DEST = 5
MGMT_OPT = 6
MGMT_OID = 7
MGMT_HASH = 8
# MGMT ACK packet definition
MGMT_RESP_FLAG=4 # ERROR CODE 1 NORMAL MSG 0
MGMT_RESP_SRC=5
MGMT_RESP_TRACK=6
MGMT_RESP_VAL=7 # ERROR CODE/ NORMAL MSG
MGMT_RESP_HASH=8

# Beacon packet definition
# PKT_INDEX_PROT_ID = 0
# PKT_INDEX_SRC = 1
PKT_HC = 2 # hop count
PKT_PQ = 3 # path quality
BEACON_PKT_LENGTH = 4 # packet length

# Protocol ID field
ARQ_PROTO = 0 # unicast acknowledgement packet
DATA_PROTO = 1 # unicast user data packet
BEACON_PROTO = 2 # beacon protocol
MGMT_PROTO = 3 # management protocol
MGMT_RESP_PROTO = 4 # management resp protocol
# sink address
SINK_ADDR = 0
# undefined address
UNDEF_ADDR = -1

# Control field
NO_ARQ = 0 # ARQ protocol is not applied
ARQ = 1 # ARQ protocol is applied

# FSM ARQ states
CHANNEL_BUSY = 0
CHANNEL_IDLE = 1
