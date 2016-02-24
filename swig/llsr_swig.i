/* -*- c++ -*- */

#define LLSR_API

%include "gnuradio.i"			// the common stuff

//load generated python docstrings
%include "llsr_swig_doc.i"

%{
#include "llsr/framer_pb.h"
%}


%include "llsr/framer_pb.h"
GR_SWIG_BLOCK_MAGIC2(llsr, framer_pb);
