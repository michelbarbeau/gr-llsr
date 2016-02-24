#!/usr/bin/env python2
##################################################
# GNU Radio Python Flow Graph
# Title: Top Block
# Generated: Tue Feb 23 22:54:52 2016
##################################################

if __name__ == '__main__':
    import ctypes
    import sys
    if sys.platform.startswith('linux'):
        try:
            x11 = ctypes.cdll.LoadLibrary('libX11.so')
            x11.XInitThreads()
        except:
            print "Warning: failed to XInitThreads()"

from PyQt4 import Qt
from gnuradio import audio
from gnuradio import blocks
from gnuradio import digital
from gnuradio import eng_notation
from gnuradio import filter
from gnuradio import gr
from gnuradio import qtgui
from gnuradio.eng_option import eng_option
from gnuradio.filter import firdes
from optparse import OptionParser
import llsr
import pmt
import sip
import sys


class top_block(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Top Block")
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Top Block")
        try:
             self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except:
             pass
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "top_block")
        self.restoreGeometry(self.settings.value("geometry").toByteArray())

        ##################################################
        # Variables
        ##################################################
        self.transistion = transistion = 220
        self.sps = sps = 9
        self.sideband_rx = sideband_rx = 1000
        self.sideband = sideband = 1000
        self.samp_rate = samp_rate = 44100
        self.payload = payload = 5
        self.packet_len_0 = packet_len_0 = 5
        self.packet_len = packet_len = 5
        self.interpolation = interpolation = 220
        self.carrier2 = carrier2 = 21050-11000
        self.carrier = carrier = 21050-13000

        ##################################################
        # Blocks
        ##################################################
        self.rational_resampler_xxx_1 = filter.rational_resampler_ccc(
                interpolation=1,
                decimation=interpolation,
                taps=None,
                fractional_bw=None,
        )
        self.rational_resampler_xxx_0 = filter.rational_resampler_ccc(
                interpolation=interpolation,
                decimation=1,
                taps=None,
                fractional_bw=None,
        )
        self.qtgui_sink_x_0_0_0_0_0_0 = qtgui.sink_c(
        	1024, #fftsize
        	firdes.WIN_BLACKMAN_hARRIS, #wintype
        	0, #fc
        	samp_rate, #bw
        	"", #name
        	True, #plotfreq
        	True, #plotwaterfall
        	True, #plottime
        	True, #plotconst
        )
        self.qtgui_sink_x_0_0_0_0_0_0.set_update_time(1.0/10)
        self._qtgui_sink_x_0_0_0_0_0_0_win = sip.wrapinstance(self.qtgui_sink_x_0_0_0_0_0_0.pyqwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qtgui_sink_x_0_0_0_0_0_0_win, 1,0)
        
        self.qtgui_sink_x_0_0_0_0_0_0.enable_rf_freq(False)
        
        
          
        self.llsr_llsr_mac_0 = llsr.llsr_mac(
              0,
              5000,
              5,
              2.0,
              True,
              0.05,
              60.0,
              10,
              False,
              False)
          
        self.llsr_framer_pb_0 = llsr.framer_pb("anonymous", 8)
        self.freq_xlating_fir_filter_xxx_0_0 = filter.freq_xlating_fir_filter_ccc(1, (filter.firdes.low_pass(1, samp_rate, sideband_rx,100)), carrier, samp_rate)
        self.freq_xlating_fir_filter_xxx_0 = filter.freq_xlating_fir_filter_ccc(1, (firdes.band_pass (0.5,samp_rate,carrier2-sideband,carrier2+sideband,transistion)), -carrier2, samp_rate)
        self.digital_hdlc_deframer_bp_1 = digital.hdlc_deframer_bp(5, 500)
        self.digital_gfsk_mod_0 = digital.gfsk_mod(
        	samples_per_symbol=9,
        	sensitivity=1.0,
        	bt=0.35,
        	verbose=False,
        	log=False,
        )
        self.digital_gfsk_demod_0 = digital.gfsk_demod(
        	samples_per_symbol=9,
        	sensitivity=1.0,
        	gain_mu=0.175,
        	mu=0.5,
        	omega_relative_limit=0.005,
        	freq_error=0.0,
        	verbose=False,
        	log=False,
        )
        self.blocks_unpacked_to_packed_xx_1 = blocks.unpacked_to_packed_bb(1, gr.GR_MSB_FIRST)
        self.blocks_random_pdu_0 = blocks.random_pdu(5, 10, chr(0xFF), 2)
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_vff((10, ))
        self.blocks_message_strobe_2 = blocks.message_strobe(pmt.intern("TEST"), 30000)
        self.blocks_message_strobe_0 = blocks.message_strobe(pmt.intern("TEST"), 5000)
        self.blocks_float_to_complex_0 = blocks.float_to_complex(1)
        self.blocks_complex_to_real_0 = blocks.complex_to_real(1)
        self.audio_source_0 = audio.source(44100, "", True)
        self.audio_sink_0 = audio.sink(44100, "", True)

        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.blocks_message_strobe_0, 'strobe'), (self.llsr_llsr_mac_0, 'ctrl_in'))    
        self.msg_connect((self.blocks_message_strobe_2, 'strobe'), (self.blocks_random_pdu_0, 'generate'))    
        self.msg_connect((self.digital_hdlc_deframer_bp_1, 'out'), (self.llsr_llsr_mac_0, 'from_radio'))    
        self.msg_connect((self.llsr_llsr_mac_0, 'to_radio'), (self.llsr_framer_pb_0, 'in'))    
        self.connect((self.audio_source_0, 0), (self.blocks_float_to_complex_0, 0))    
        self.connect((self.blocks_complex_to_real_0, 0), (self.blocks_multiply_const_vxx_0, 0))    
        self.connect((self.blocks_float_to_complex_0, 0), (self.freq_xlating_fir_filter_xxx_0_0, 0))    
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.audio_sink_0, 0))    
        self.connect((self.blocks_unpacked_to_packed_xx_1, 0), (self.digital_gfsk_mod_0, 0))    
        self.connect((self.digital_gfsk_demod_0, 0), (self.digital_hdlc_deframer_bp_1, 0))    
        self.connect((self.digital_gfsk_mod_0, 0), (self.rational_resampler_xxx_0, 0))    
        self.connect((self.freq_xlating_fir_filter_xxx_0, 0), (self.blocks_complex_to_real_0, 0))    
        self.connect((self.freq_xlating_fir_filter_xxx_0_0, 0), (self.qtgui_sink_x_0_0_0_0_0_0, 0))    
        self.connect((self.freq_xlating_fir_filter_xxx_0_0, 0), (self.rational_resampler_xxx_1, 0))    
        self.connect((self.llsr_framer_pb_0, 0), (self.blocks_unpacked_to_packed_xx_1, 0))    
        self.connect((self.rational_resampler_xxx_0, 0), (self.freq_xlating_fir_filter_xxx_0, 0))    
        self.connect((self.rational_resampler_xxx_1, 0), (self.digital_gfsk_demod_0, 0))    

    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "top_block")
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()

    def get_transistion(self):
        return self.transistion

    def set_transistion(self, transistion):
        self.transistion = transistion
        self.freq_xlating_fir_filter_xxx_0.set_taps((firdes.band_pass (0.5,self.samp_rate,self.carrier2-self.sideband,self.carrier2+self.sideband,self.transistion)))

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps

    def get_sideband_rx(self):
        return self.sideband_rx

    def set_sideband_rx(self, sideband_rx):
        self.sideband_rx = sideband_rx
        self.freq_xlating_fir_filter_xxx_0_0.set_taps((filter.firdes.low_pass(1, self.samp_rate, self.sideband_rx,100)))

    def get_sideband(self):
        return self.sideband

    def set_sideband(self, sideband):
        self.sideband = sideband
        self.freq_xlating_fir_filter_xxx_0.set_taps((firdes.band_pass (0.5,self.samp_rate,self.carrier2-self.sideband,self.carrier2+self.sideband,self.transistion)))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.freq_xlating_fir_filter_xxx_0.set_taps((firdes.band_pass (0.5,self.samp_rate,self.carrier2-self.sideband,self.carrier2+self.sideband,self.transistion)))
        self.freq_xlating_fir_filter_xxx_0_0.set_taps((filter.firdes.low_pass(1, self.samp_rate, self.sideband_rx,100)))
        self.qtgui_sink_x_0_0_0_0_0_0.set_frequency_range(0, self.samp_rate)

    def get_payload(self):
        return self.payload

    def set_payload(self, payload):
        self.payload = payload

    def get_packet_len_0(self):
        return self.packet_len_0

    def set_packet_len_0(self, packet_len_0):
        self.packet_len_0 = packet_len_0

    def get_packet_len(self):
        return self.packet_len

    def set_packet_len(self, packet_len):
        self.packet_len = packet_len

    def get_interpolation(self):
        return self.interpolation

    def set_interpolation(self, interpolation):
        self.interpolation = interpolation

    def get_carrier2(self):
        return self.carrier2

    def set_carrier2(self, carrier2):
        self.carrier2 = carrier2
        self.freq_xlating_fir_filter_xxx_0.set_taps((firdes.band_pass (0.5,self.samp_rate,self.carrier2-self.sideband,self.carrier2+self.sideband,self.transistion)))
        self.freq_xlating_fir_filter_xxx_0.set_center_freq(-self.carrier2)

    def get_carrier(self):
        return self.carrier

    def set_carrier(self, carrier):
        self.carrier = carrier
        self.freq_xlating_fir_filter_xxx_0_0.set_center_freq(self.carrier)


if __name__ == '__main__':
    parser = OptionParser(option_class=eng_option, usage="%prog: [options]")
    (options, args) = parser.parse_args()
    from distutils.version import StrictVersion
    if StrictVersion(Qt.qVersion()) >= StrictVersion("4.5.0"):
        Qt.QApplication.setGraphicsSystem(gr.prefs().get_string('qtgui','style','raster'))
    qapp = Qt.QApplication(sys.argv)
    tb = top_block()
    tb.start()
    tb.show()

    def quitting():
        tb.stop()
        tb.wait()
    qapp.connect(qapp, Qt.SIGNAL("aboutToQuit()"), quitting)
    qapp.exec_()
    tb = None  # to clean up Qt widgets
