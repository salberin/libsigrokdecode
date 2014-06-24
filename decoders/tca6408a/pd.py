##
## This file is part of the libsigrokdecode project.
## 
## Copyright (C) 2012 Uwe Hermann <uwe@hermann-uwe.de>
## Copyright (C) 2013 Matt Ranostay <mranostay@gmail.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
##

import sigrokdecode as srd

class Decoder(srd.Decoder):
    api_version = 2
    id = 'tca6408a'
    name = 'TCA6408a'
    longname = 'TI TCA6408a'
    desc = 'I/O expander.'
    license = 'gplv2+'
    inputs = ['i2c']
    outputs = ['tca6408a']
    annotations = (
        ('register', 'Register type'),
        ('reg value', 'Human-readable text'),
        ('warnings', 'Warning messages'),
    )

    def __init__(self, **kwargs):
        self.state = 'IDLE'
        self.chip = -1

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putx(self, data):
        self.put(self.ss, self.es, self.out_ann, data)

    def handle_reg_0x00(self, b): # Seconds
        self.putx([1, ['State of inputs: %d' % b]])

    def handle_reg_0x01(self, b): # Minutes
        self.putx([1, ['Outputs set: %d' % b ]])

    def handle_reg_0x02(self, b): # Hours
        self.putx([1, ['Polarity inverted: %d' % b]])

    def handle_reg_0x03(self, b): # Day of week
        self.putx([1, ['Configuration: %d' % b]])

    def handle_write_reg(self, b): # Write to I/O chip
        if b == 0:
            
            self.putx([0, ['Input port', 'INP', 'I']])
        elif b == 1:
            self.putx([0, ['Output port', 'OP', 'O']])
        elif b == 2:
            self.putx([0, ['Polarity inversion register', 'Pol', 'P']])
        elif b == 3:
            self.putx([0, ['Configuration register', 'Conf', 'C']])
        
    def check_correct_chip(self, addr): # Check if we are decoding a io expander
        if  not (addr == 0x20 or addr == 0x21): 
            self.putx([2, ['Warning: I²C slave 0x%02x not an TCA6408a compatible chip.' % addr]])
            self.state = 'IDLE'

    def decode(self, ss, es, data):
        cmd, databyte = data

        # Store the start/end samples of this I²C packet.
        self.ss, self.es = ss, es

        # State machine.
        if self.state == 'IDLE':
            # Wait for an I²C START condition.
            if cmd != 'START':
                return
            self.state = 'GET SLAVE ADDR'
            self.block_start_sample = ss
        elif self.state == 'GET SLAVE ADDR':
            # Wait for an address write operation.
            # TODO: We should only handle packets to the RTC slave (0x68).
            self.chip = databyte  
            self.state = 'GET REG ADDR'
        elif self.state == 'GET REG ADDR':
            # Wait for a data write (master selects the slave register).
            if (cmd == 'ADDRESS READ' or cmd == 'ADDRESS WRITE'):
              self.check_correct_chip(databyte)
            if cmd != 'DATA WRITE':
                return
            self.reg = databyte
            self.handle_write_reg(self.reg)
            self.state = 'WRITE IO REGS'
        elif self.state == 'WRITE IO REGS':
            # If we see a Repeated Start here, it's probably an RTC read.
            if cmd == 'START REPEAT':
                self.state = 'READ IO REGS'
                return
            # Otherwise: Get data bytes until a STOP condition occurs.
            if cmd == 'DATA WRITE':
                handle_reg = getattr(self, 'handle_reg_0x%02x' % self.reg)
                handle_reg(databyte)
                # TODO: Check for NACK!
            elif cmd == 'STOP':
                # self.put(self.block_start_sample, es, self.out_ann,
                #         [0, ['Written date/time: %s' % d]])
                self.state = 'IDLE'
                self.chip = -1
            else:
                pass # TODO
        elif self.state == 'READ IO REGS':
            # Wait for an address read operation.
            # TODO: We should only handle packets to the RTC slave (0x68).
            if cmd == 'ADDRESS READ':
                self.state = 'READ IO REGS2'
                self.chip = databyte
                return
            else:
                pass # TODO
        elif self.state == 'READ IO REGS2':
            if cmd == 'DATA READ':
                handle_reg = getattr(self, 'handle_reg_0x%02x' % self.reg)
                handle_reg(databyte)
                # TODO: Check for NACK!
            elif cmd == 'STOP':
                self.state = 'IDLE'
            else:
                pass # TODO?
        else:
            raise Exception('Invalid state: %s' % self.state)

