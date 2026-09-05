`timescale 1ns/1ps
`default_nettype none
module tef_add_full_chain_tb;
  localparam integer MANT_W=9, OFF_W=7, TERMS=32;
  reg as, bs; reg [OFF_W-1:0] ao, bo; reg [MANT_W-1:0] am, bm;
  wire os_; wire [OFF_W-1:0] oo; wire [MANT_W-1:0] om;
  reg acc_s; reg [OFF_W-1:0] acc_o; reg [MANT_W-1:0] acc_m;
  integer fd, code, i, errors, checks, done;
  integer xs, xo, xm, es, eo, em;
  tef_add_full #(.MANT_W(MANT_W), .OFF_W(OFF_W), .OFFSET_MAX(80)) dut(
    .a_sign(as), .a_off(ao), .a_mant(am),
    .b_sign(bs), .b_off(bo), .b_mant(bm),
    .out_sign(os_), .out_off(oo), .out_mant(om));
  initial begin
    errors=0; checks=0; done=0;
    fd=$fopen("/tmp/chain_vec.txt","r");
    if (fd==0) begin $display("  no vectors"); $finish; end
    while (done==0) begin
      code=$fscanf(fd, "%d %d %d", xs, xo, xm);
      if (code!=3) done=1;
      else begin
        acc_s=xs[0]; acc_o=xo[OFF_W-1:0]; acc_m=xm[MANT_W-1:0];
        for (i=1;i<TERMS;i=i+1) begin
          code=$fscanf(fd, "%d %d %d", xs, xo, xm);
          as=acc_s; ao=acc_o; am=acc_m;
          bs=xs[0]; bo=xo[OFF_W-1:0]; bm=xm[MANT_W-1:0];
          #1;
          acc_s=os_; acc_o=oo; acc_m=om;
        end
        code=$fscanf(fd, "%d %d %d\n", es, eo, em);
        checks=checks+1;
        if (acc_o!==eo[OFF_W-1:0] || acc_m!==em[MANT_W-1:0] || acc_s!==es[0]) begin
          errors=errors+1;
          if (errors<=3)
            $display("  CHAIN MISMATCH #%0d: got (%0d,%0d,%0d) want (%0d,%0d,%0d)",
                     checks, acc_s, acc_o, acc_m, es, eo, em);
        end
      end
    end
    $fclose(fd);
    $display("  %0d chains of %0d terms, %0d errors", checks, TERMS, errors);
    $finish;
  end
endmodule
