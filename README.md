# Location-free Link State Routing (LLSR) Implementation for GNU Radio

The module implements the protocol originally described in:
Michel Barbeau, Stephane Blouin, Gimer Cervera, Joaquin Garcia-Alfaro
and Evangelos Kranakis, "Location-free Link State Routing for Underwater
Acoustic Sensor Networks," 8th annual IEEE Canadian Conference on
Electrical and Computer Engineering (CCECE), May 2015, Halifax, NS,
Canada.

The project includes the following contributions (see gr-llsr/docs):

Zach Renaud, "Network Management for Software Defined Radio Applications", Bachelor of Computer Science Honours Project, School of Computer Science, Carleton University, April 2016. (see the llsr-snmp branch)

Wenqian Wang, "Performance Management of Hydroacoustic Surveillance Networks", Master of Computer Science, Graduate Project, School of Computer Science, Carleton University, May 2016.

# Copyright 2016 Michel Barbeau, Zach Renaud and Wenqian Wang, Carleton University.
# Version: March 6, 2017

## Installing

###### Fetching the project code from this remote repository
`git clone https://github.com/michelbarbeau/gr-llsr`

###### Optional installation for enabling SNMP function

**Install libsmi on the node side**

```
  sudo easy_install pysnmp
  sudo apt-get install python-pysnmp4
```

**Setting up environment for remote control**

You need to install SNMP and some of the standard MIBs.

```
sudo apt-get update
sudo apt-get install snmp snmp-mibs-downloader
```

Copy the MIB folder in LLSR_SNMP folder to following location:

`~/.snmp/mibs`
and
`/usr/local/share/snmp/mibs`

You may need to make sure port 161 is not occupied by your system.
This usually is caused by your running SNMP Daemon.

## Building

```
cd gr-llsr

mkdir build

cd build

cmake ../

make

sudo make install

sudo ldconfig

```

## Running

###### Running LLSR_MAC module example.

![Loopback Example](https://github.com/michelbarbeau/gr-llsr/blob/master/loopback.png)

To run within gnuradio-companion

Open the flow graph  gr-llsr/examples/loopback.grc

To run outside gnuradio-companion

cd gr-llsr/examples

python top_block.py

###### Running SNMP Agent to support remote network management (SNMP)

Place the LLSR_SNMP folder to user directory.

Unless you setting up the files to be accessible under system control scope,

you may need root permission execute the agent script by using command:

`sudo python llsrSnmpAgent.py`


## More examples withe using this module

see: https://github.com/michelbarbeau/gr-splash
