/* -*- c++ -*- */
/* 
 * ----------------------------------------
 * Framer for Hydro Acoustic Communications
 * ----------------------------------------
 * Copyright 2016 Michel Barbeau, Carleton University.
 * Version: February 23, 2016
 *
 * Using file: hdlc_framer_pb from module digital
 * 
 * This is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * This software is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this software; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

#ifndef INCLUDED_LLSR_FRAMER_PB_IMPL_H
#define INCLUDED_LLSR_FRAMER_PB_IMPL_H

#include <llsr/framer_pb.h>

namespace gr {
  namespace llsr {

    class framer_pb_impl : public framer_pb
    {
     private:
        std::vector<std::vector<unsigned char> > d_leftovers;
        pmt::pmt_t d_frame_tag, d_me;
        std::string delay_b;
        unsigned int crc_ccitt(std::vector<unsigned char> &data);
        std::vector<unsigned char> unpack(std::vector<unsigned char> &pkt);
        void stuff(std::vector<unsigned char> &pkt);
        unsigned char * sframing; // preamble
        int sframing_l; // length of sframing

     public:
      framer_pb_impl(const std::string frame_tag_name, int tx_delay);
      ~framer_pb_impl();

      // Where all the action really happens
      int work(int noutput_items,
	       gr_vector_const_void_star &input_items,
	       gr_vector_void_star &output_items);
    };

  } // namespace llsr
} // namespace gr

#endif /* INCLUDED_LLSR_FRAMER_PB_IMPL_H */

