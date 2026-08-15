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
    reg       darbe_kip = 0;
    reg [7:0] darbe_ms = 8'd2;
    reg       maske_bank = 0;
    wire      ser, srclk, rclk, mesgul;

    kontrol_zinciri #(.MS_CEVRIM(80)) dut (
        .clk(clk), .rst(rst),
        .yaz_veri(yaz_veri), .yaz_adr(yaz_adr), .yaz_darbe(yaz_darbe),
        .zincir_bayt(5'd3), .gonder(gonder),
        .darbe_kip(darbe_kip), .darbe_ms(darbe_ms),
        .maske_bank(maske_bank),
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
            maske_bank = 0;
            yaz_adr = a; yaz_veri = d; yaz_darbe = 1;
            @(posedge clk); #1; yaz_darbe = 0;
        end
    endtask

    task yaz_maske(input [4:0] a, input [7:0] d);
        begin
            @(posedge clk); #1;
            maske_bank = 1;
            yaz_adr = a; yaz_veri = d; yaz_darbe = 1;
            @(posedge clk); #1; yaz_darbe = 0; maske_bank = 0;
        end
    endtask

    task sur;
        begin
            @(posedge clk); #1; gonder = 1;
            @(posedge clk); #1; gonder = 0;
            k = 0;
            while (mesgul && k < 200000) begin @(posedge clk); k = k + 1; end
            for (k = 0; k < 20; k = k + 1) @(posedge clk);
        end
    endtask

    initial begin
        $display("Kontrol zinciri testi");
        #100; @(posedge clk); #1; rst = 0;

        // tampon[0] ilk 595'e, tampon[2] sonuncuya gitmeli
        yaz(5'd0, 8'hA1);
        yaz(5'd1, 8'hB2);
        yaz(5'd2, 8'hC3);

        sur;

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

        // ---- DARBE KIPI ----
        //
        // Kilitlenen role bobini surekli enerji kaldirmaz. Darbe
        // kipinde modul once TAM deseni suruyor, darbe_ms kadar
        // bekliyor, sonra SADECE tutma maskesindeki bitleri birakip
        // otekileri dusuruyor.
        //
        // Testin isi tam da bu: darbeden SONRA anlik bitlerin dustugunu
        // gormek. Sadece "desen dogru gitti" demek yetmez — su anki
        // hatanin ta kendisi buydu, desen gidiyordu ve hic dusmuyordu.
        $display("  --- darbe kipi");
        yaz(5'd0, 8'hFF);          // hepsi enerjili
        yaz(5'd1, 8'hFF);
        yaz(5'd2, 8'hFF);
        yaz_maske(5'd0, 8'h81);    // sadece bit0 ve bit7 tutulacak
        yaz_maske(5'd1, 8'h00);
        yaz_maske(5'd2, 8'h00);
        darbe_kip = 1;
        sur;

        $display("  darbe sonrasi q0=%02x q1=%02x q2=%02x", q0, q1, q2);
        if (q0 !== 8'h81) begin
            $display("  HATA: q0 maskeye dusmeliydi (81), %02x var", q0);
            hata = hata + 1;
        end
        if (q1 !== 8'h00 || q2 !== 8'h00) begin
            $display("  HATA: maskesiz baytlar sifirlanmali, q1=%02x q2=%02x", q1, q2);
            hata = hata + 1;
        end
        if (hata == 0) $display("  darbe sonrasi sadece tutulan bitler kaldi");

        // ---- darbe kipi KAPALI iken desen ayakta kalmali ----
        darbe_kip = 0;
        yaz(5'd0, 8'h5A); yaz(5'd1, 8'h5A); yaz(5'd2, 8'h5A);
        sur;
        if (q0 !== 8'h5A || q1 !== 8'h5A || q2 !== 8'h5A) begin
            $display("  HATA: darbe kapaliyken desen dusmemeliydi: %02x %02x %02x", q0,q1,q2);
            hata = hata + 1;
        end else $display("  darbe kapali: desen ayakta kaldi");

        if (hata == 0) $display("Kontrol zinciri testi GECTI");
        else begin
            $display("Kontrol zinciri testi KALDI: %0d hata", hata);
            $fatal;
        end
        $finish;
    end

endmodule

`default_nettype wire
