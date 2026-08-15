// DAC arayuzu testi — ofset ikili donusumu ve WRT zamanlamasi.
//
// Iki sey olculuyor:
//
// 1 OFSET IKILI. Isaretli -8192 -> 0, 0 -> 8192, +8191 -> 16383.
//   Yanlissa cikis orta noktadan tam olcek kaydirilir ve sinyal
//   surekli kirpilir.
//
// 2 WRT VERIDEN SONRA. Veri bir cevrim once cikmali, WRT sonraki
//   cevrimde. Ayni kenarda degisirlerse kurulum suresi ihlal edilir
//   ve DAC yanlis deger alir — osiloskopta gorunmez, yalnizca
//   spektrumda gurultu olarak cikar.
`timescale 1ns/1ps
`default_nettype none
module tb_dac;
    reg clk=0, rst=1; always #6.25 clk=~clk;
    reg signed [13:0] a=0, b=0; reg gv=0;
    wire [13:0] da, db; wire wa, wb, dclk;
    dac_cikis dut(.clk(clk),.rst(rst),.ornek_a(a),.ornek_b(b),
                  .ornek_gecerli(gv),.dac_a(da),.dac_b(db),
                  .wrt_a(wa),.wrt_b(wb),.dac_clk(dclk));
    integer hata=0, k;
    reg [13:0] veri_wrt_aninda;

    task ver(input signed [13:0] v, input [13:0] bekle);
        begin
            a=v; b=v;
            @(posedge clk); #1; gv=1;
            @(posedge clk); #1; gv=0;
            @(posedge clk); #1;
            if (da !== bekle) begin
                $display("  HATA: %0d -> %0d, %0d beklenen", v, da, bekle);
                hata=hata+1;
            end
            if (!wa) begin
                $display("  HATA: %0d icin WRT gelmedi", v);
                hata=hata+1;
            end
            @(posedge clk); #1;
        end
    endtask

    initial begin
        $display("DAC arayuzu testi");
        #100; @(posedge clk); #1; rst=0;
        ver(-14'sd8192, 14'd0);
        ver(14'sd0,     14'd8192);
        ver(14'sd8191,  14'd16383);
        ver(14'sd4096,  14'd12288);
        if (hata==0) $display("  ofset ikili donusumu dogru");
        // WRT veriden SONRA mi
        a=14'sd1000; @(posedge clk); #1; gv=1; @(posedge clk); #1;
        if (wa) begin
            $display("  HATA: WRT veriyle ayni cevrimde yukseldi");
            hata=hata+1;
        end else
            $display("  WRT veriden bir cevrim sonra");
        gv=0;
        if (hata==0) $display("DAC arayuzu testi GECTI");
        else begin $display("DAC arayuzu testi KALDI: %0d hata", hata); $fatal; end
        $finish;
    end
endmodule
`default_nettype wire
