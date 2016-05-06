# Location-free Link State Routing (LLSR) Implementation for GNU Radio

The module implements the protocol originally described in:
Michel Barbeau, Stephane Blouin, Gimer Cervera, Joaquin Garcia-Alfaro
and Evangelos Kranakis, "Location-free Link State Routing for Underwater
Acoustic Sensor Networks," 8th annual IEEE Canadian Conference on 
Electrical and Computer Engineering (CCECE), May 2015, Halifax, NS, 
Canada. 

The project includes the following contributions(see gr-llsr/docs):

Zach Renaud, "Network Management for Software Defined Radio Applications", Bachelor of Computer Science Honours Project, School of Computer Science, Carleton University, April 2016.

Wenqian Wang, "Performance Management of Hydroacoustic Surveillance Networks", Master of Computer Science, Graduate Project, School of Computer Science, Carleton University, May 2016.


## Installing 

`git clone https://github.com/michelbarbeau/gr-llsr`

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

To run within gnuradio-companion

Open the flow graph  gr-llsr/examples/loopback.grc

To run outside gnuradio-companion

cd gr-llsr/examples

python top_block.py
