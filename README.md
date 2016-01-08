Location-free Link State Routing (LLSR) Implementation for GNU Radio
--------------------------------------------------------------------

The module implements the protocol originally described in:
Michel Barbeau, Stephane Blouin, Gimer Cervera, Joaquin Garcia-Alfaro
and Evangelos Kranakis, "Location-free Link State Routing for Underwater
Acoustic Sensor Networks," 8th annual IEEE Canadian Conference on 
Electrical and Computer Engineering (CCECE), May 2015, Halifax, NS, 
Canada. 

Installing

git clone https://github.com/michelbarbeau/gr-llsr

cd gr-llsr

make build

cd build 

cmake ../

make

sudo make install

To run within gnuradio-companion

Open the flow graph  gr-llsr/examples/loopback.grc
