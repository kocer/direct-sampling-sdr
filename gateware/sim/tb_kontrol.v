// Kontrol zinciri testi — 595 modeli ile ucdan uca.
//
// Zincirdeki 595'leri gercekten modelleyip cikislarina bakiyoruz.
// Sadece dalga bicimine bakmak yetmez: bit sirasi ya da bayt sirasi
// ters olursa dalga bicimi yine dogru gorunur, ama YANLIS ROLE
// calisir. O hata sahada "yanlis bant seciliyor" olarak cikar ve
// nedenini bulmak gunler alir.

`timescale 1ns/1ps
`default_nettype none

module hc595 (
    input  wire       ser,
    input  wire       srclk,
    input  wire       rclk,
    output reg  [7:0] q,
    output wire       qh_    // zincirin devami
);
    reg [7:0] kaydir;
    assign qh_ = kaydir[7];
    always @(posedge srclk) kaydir <= {kaydir[6:0], ser};
    always @(posedge rclk)  q      <= kaydir;
endmodule


module tb_kontrol;

    reg clk = 0, rst = 1;
    always #6.25 clk = ~clk;

    reg [7:0] yaz_veri = 0;
    reg [4:0] yaz_adr  = 0;
    reg       yaz_darbe = 0;
    reg       gonder = 0;
    wire      ser, srclk, rclk, mesgul;

    kontrol_zinciri dut (
        .clk(clk), .rst(rst),
        .yaz_veri(yaz_veri), .yaz_adr(yaz_adr), .yaz_darbe(yaz_darbe),
        .zincir_bayt(5'd3), .gonder(gonder),
        .rly_ser(ser), .rly_srclk(srclk), .rly_rclk(rclk),
        .mesgul(mesgul)
    );

    // uc 595, zincir halinde
    wire [7:0] q0, q1, q2;
    wire ara0, ara1, ara2;
    hc595 u0 (.ser(ser),  .srclk(srclk), .rclk(rclk), .q(q0), .qh_(ara0));
    hc595 u1 (.ser(ara0), .srclk(srclk), .rclk(rclk), .q(q1), .qh_(ara1));
    hc595 u2 (.ser(ara1), .srclk(srclk), .rclk(rclk), .q(q2), .qh_(ara2));

    integer k, hata = 0;

    task yaz(input [4:0] a, input [7:0] d);
        begin
            @(posedge clk); #1;
            yaz_adr = a; yaz_veri = d; yaz_darbe = 1;
            @(posedge clk); #1; yaz_darbe = 0;
        end
    endtask

    initial begin
        $display("Kontrol zinciri testi");
        #100; @(posedge clk); #1; rst = 0;

        // tampon[0] ilk 595'e, tampon[2] sonuncuya gitmeli
        yaz(5'd0, 8'hA1);
        yaz(5'd1, 8'hB2);
        yaz(5'd2, 8'hC3);

        @(posedge clk); #1; gonder = 1;
        @(posedge clk); #1; gonder = 0;

        // zincirin bosalmasini bekle
        k = 0;
        while (mesgul && k < 5000) begin @(posedge clk); k = k + 1; end
        for (k = 0; k < 20; k = k + 1) @(posedge clk);

        $display("  q0=%02x  q1=%02x  q2=%02x", q0, q1, q2);

        if (q0 !== 8'hA1) begin
            $display("  HATA: ilk 595'te A1 olmali, %02x var", q0);
            hata = hata + 1;
        end
        if (q1 !== 8'hB2) begin
            $display("  HATA: ikinci 595'te B2 olmali, %02x var", q1);
            hata = hata + 1;
        end
        if (q2 !== 8'hC3) begin
            $display("  HATA: ucuncu 595'te C3 olmali, %02x var", q2);
            hata = hata + 1;
        end

        if (hata == 0)
            $display("  bayt sirasi ve bit sirasi dogru");

        if (hata == 0) $display("Kontrol zinciri testi GECTI");
        else begin
            $display("Kontrol zinciri testi KALDI: %0d hata", hata);
            $fatal;
        end
        $finish;
    end

endmodule

`default_nettype wire
