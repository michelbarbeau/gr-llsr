#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# --------------------------------
# Location-free Link State Routing
# --------------------------------
# Author: Michel Barbeau, Carleton University
# Version: January 1, 2016
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
#  

CHAN_FLAG_NONE = 0x00

# Data/acknowledgement packet  definition
PKT_PROT_ID = 0
PKT_SRC = 1
PKT_DEST = 2
PKT_CNT = 3
PKT_CTRL = 4
PKT_MIN = 5 # packet minimum length
ACK_PKT_LENGTH = 4 # packet length

# Beacon packet defnition
# PKT_INDEX_PROT_ID = 0
# PKT_INDEX_SRC = 1
PKT_HC = 2 # hop count
PKT_PQ = 3 # path quality
BEACON_PKT_LENGTH = 4 # packet length

# Protocol ID field
ARQ_PROTO = 0 # unicast acknowledgement packet
DATA_PROTO = 1 # unicast user data packet
BEACON_PROTO = 2 # beacon protocol

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
