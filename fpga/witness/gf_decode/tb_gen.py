#!/usr/bin/env python3
# Emits tb_<name>.v instantiating gf_decode_param for a given format. argv:
# builddir name N E M BIAS
import sys
builddir=sys.argv[1]; name=sys.argv[2]; N=sys.argv[3]; E=sys.argv[4]; M=sys.argv[5]; BIAS=sys.argv[6]
Nw=int(N)-1
tpl=f"""`timescale 1ns/1ps
module tb_{name};
    reg  [{Nw}:0] raw;
    wire [31:0] dut;
    reg  [31:0] expected;
    integer fd, r, pass, fail, total;
    reg exp_is_nan, dut_is_nan;
    gf_decode_param #(.N({N}),.E({E}),.M({M}),.BIAS({BIAS}),.OUT_REG(0)) dut0 (
        .clk(1'b0),.rst_n(1'b1),.gf_in(raw),.fp32_out(dut),
        .is_nan_o(),.is_inf_o(),.is_zero_o(),.is_subnormal_o());
    initial begin
        fd=$fopen("{builddir}/vectors_{name}.txt","r");
        if(fd==0) begin $display("ERROR open"); $finish; end
        pass=0;fail=0;total=0;
        r=$fscanf(fd,"%h %h",raw,expected);
        while(r==2) begin
            #1;
            exp_is_nan=(expected[30:23]==8'hFF)&&(expected[22:0]!=0);
            dut_is_nan=(dut[30:23]==8'hFF)&&(dut[22:0]!=0);
            total=total+1;
            if((exp_is_nan&&dut_is_nan)||(!exp_is_nan&&(dut==expected))) pass=pass+1;
            else begin
                fail=fail+1;
                if(fail<=12) $display("MISMATCH raw=%h golden=%h dut=%h",raw,expected,dut);
            end
            r=$fscanf(fd,"%h %h",raw,expected);
        end
        $fclose(fd);
        $display("HW RESULT: %0d/%0d bit-exact (fails=%0d) [{name}]",pass,total,fail);
        if(fail==0) $display("PASS {name}"); else $display("FAIL {name}");
        $finish;
    end
endmodule
"""
open(f"{builddir}/tb_{name}.v","w").write(tpl)
