`timescale 1ns / 1ps
// RX_ER injection for the E3 bench. It is a second top module beside eth_arp_icmp_tb and forces
// that testbench's RGMII receive nets. No pinned file is edited: the TB, the KSZ9031 frame model
// and the RTL are the ones specs/trinet/eth_arp_icmp_e3_ax7203.t27 pins by sha.
//
// RGMII carries RX_DV on the rising RXC edge and RX_DV xor RX_ER on the falling one. The frame
// model has no RX_ER, so this module makes one for a single nibble by forcing RX_CTL for half a
// cycle around one falling edge (released 5 ns after it, well before the next rising edge).
//
// Plusargs (all decimal):
//   +RXER_MODE=1  in-frame error: after the RXER_FRAME-th RX_DV rise, the nibble RXER_NIBBLE
//                 (0 = the first preamble nibble) gets RX_CTL=0 at its falling edge (DV=1, ER=1)
//   +RXER_MODE=2  false carrier: RXER_NIBBLE nibbles after the RXER_FRAME-th RX_DV fall,
//                 RXER_COUNT nibbles of RXD=E with RX_CTL=1 at the falling edge only (DV=0, ER=1)
// Every forced falling edge prints an INJ line with the RTL's falling-edge sample one ns later,
// so a run in which nothing was injected, or the RTL did not see it, says so.
module eth_rxer_inject;
    integer mode = 0, frame = 1, nibble = 0, count = 1, k, seen;

    task one_edge(input v);
        begin
            #10 if (v) force eth_arp_icmp_tb.eth_rxctl = 1'b1;
                else force eth_arp_icmp_tb.eth_rxctl = 1'b0;
            @(negedge eth_arp_icmp_tb.eth_rxc);
            #1 seen = eth_arp_icmp_tb.dut.rxctl_n;
            $display("INJ t=%0d rxctl=%0d rtl_falling_sample=%0d", $time, v, seen);
            #4 release eth_arp_icmp_tb.eth_rxctl;
        end
    endtask

    initial begin
        if ($value$plusargs("RXER_MODE=%d", mode)) ;
        if ($value$plusargs("RXER_FRAME=%d", frame)) ;
        if ($value$plusargs("RXER_NIBBLE=%d", nibble)) ;
        if ($value$plusargs("RXER_COUNT=%d", count)) ;
        $display("INJ mode=%0d frame=%0d nibble=%0d count=%0d", mode, frame, nibble, count);
        if (mode == 1) begin
            repeat (frame) @(posedge eth_arp_icmp_tb.eth_rxctl);
            repeat (nibble + 1) @(posedge eth_arp_icmp_tb.eth_rxc);
            one_edge(1'b0);
        end else if (mode == 2) begin
            repeat (frame) @(negedge eth_arp_icmp_tb.eth_rxctl);
            repeat (nibble + 1) @(posedge eth_arp_icmp_tb.eth_rxc);
            #2 force eth_arp_icmp_tb.eth_rxd = 4'hE;
            for (k = 0; k < count; k = k + 1) begin
                one_edge(1'b1);
                if (k + 1 < count) @(posedge eth_arp_icmp_tb.eth_rxc);
            end
            release eth_arp_icmp_tb.eth_rxd;            // before the next rising edge: idle again
        end
    end
endmodule
