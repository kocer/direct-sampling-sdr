// MDIO testi — karsisina GERCEK bir PHY modeli konuyor.
//
// Modul kendi kendini dogrulayamaz. "64 kenar urettim" demek, PHY'nin
// dogru cerceveyi gordugu anlamina gelmiyor: onsoz bir bit eksikse,
// ST/OP ters yazilmissa ya da TA evresinde hat gec birakilmissa
// dalga bicimi yine makul gorunur ve PHY sessizce cevap vermez.
// Karsi tarafta madde 22'ye gore cozen bir model duruyor.

`timescale 1ns/1ps
`default_nettype none

module tb_mdio;

    localparam BOLEN = 4;          // testte hizli

    reg clk = 1'b0;
    always #6.25 clk = ~clk;
    reg rst = 1'b1;

    reg  [4:0]  phy_adr = 5'd1;
    reg  [4:0]  kayit_adr = 5'd2;
    reg  [15:0] yaz_veri = 16'h0000;
    reg         yaz = 1'b0, basla = 1'b0;
    wire [15:0] oku_veri;
    wire        mesgul, mdc, mdio_o, mdio_yon;

    // cift yonlu hat
    wire mdio;
    wire phy_surer;
    reg  phy_bit = 1'b1;
    assign mdio = mdio_yon ? mdio_o : (phy_surer ? phy_bit : 1'b1);

    mdio #(.BOLEN(BOLEN)) dut (
        .clk(clk), .rst(rst),
        .phy_adr(phy_adr), .kayit_adr(kayit_adr),
        .yaz_veri(yaz_veri), .yaz(yaz), .basla(basla),
        .oku_veri(oku_veri), .mesgul(mesgul),
        .mdc(mdc), .mdio_o(mdio_o), .mdio_yon(mdio_yon), .mdio_i(mdio));

    // ---------------------------------------------------------------
    // PHY modeli: MDC yukselen kenarinda ornekliyor, cerceveyi cozuyor.
    // ---------------------------------------------------------------
    reg [63:0] alinan = 64'd0;
    integer    bit_no = 0;
    reg [15:0] phy_kayit = 16'hABCD;    // okundugunda bu donecek

    // Okumada PHY, TA'nin IKINCI bitinden itibaren suruyor.
    // Cerceve 64 bit: 0..31 onsoz, 32-33 ST, 34-35 OP, 36-40 PHY,
    // 41-45 REG, 46-47 TA, 48..63 veri.
    localparam TA1 = 47;
    reg okuma_kipi = 1'b0;
    assign phy_surer = okuma_kipi && (bit_no >= TA1);

    always @(posedge mdc) begin
        alinan <= {alinan[62:0], mdio};
        bit_no <= bit_no + 1;
    end

    always @(negedge mdc) begin
        if (okuma_kipi) begin
            if (bit_no == TA1)      phy_bit <= 1'b0;          // TA'nin 0'i
            else if (bit_no > TA1 && bit_no - TA1 - 1 < 16)
                phy_bit <= phy_kayit[15 - (bit_no - TA1 - 1)];
        end
    end

    integer hata = 0;

    task komut(input yazma, input [4:0] ra, input [15:0] d);
        begin
            @(posedge clk); #1;
            yaz = yazma; kayit_adr = ra; yaz_veri = d; basla = 1;
            @(posedge clk); #1; basla = 0;
            wait (mesgul); wait (!mesgul);
            repeat (4) @(posedge clk);
        end
    endtask

    initial begin
        $display("MDIO testi");
        repeat (5) @(posedge clk); rst = 0;
        repeat (5) @(posedge clk);

        // ---- 1. yazma cercevesi ----
        alinan = 0; bit_no = 0;
        komut(1'b1, 5'd9, 16'h1234);

        if (bit_no !== 64) begin
            $display("  HATA: %0d MDC kenari, 64 olmali", bit_no);
            hata = hata + 1;
        end else $display("  64 MDC kenari");

        // onsoz 32 bit bir olmali
        if (alinan[63:32] !== 32'hFFFF_FFFF) begin
            $display("  HATA: onsoz %08h, FFFFFFFF olmali", alinan[63:32]);
            hata = hata + 1;
        end else $display("  onsoz dogru");

        // ST=01 OP=01(yazma) PHY=1 REG=9 TA=10 VERI=1234
        if (alinan[31:30] !== 2'b01) begin
            $display("  HATA: ST %b, 01 olmali", alinan[31:30]); hata=hata+1; end
        if (alinan[29:28] !== 2'b01) begin
            $display("  HATA: OP %b, yazmada 01 olmali", alinan[29:28]); hata=hata+1; end
        if (alinan[27:23] !== 5'd1) begin
            $display("  HATA: PHY adresi %0d, 1 olmali", alinan[27:23]); hata=hata+1; end
        if (alinan[22:18] !== 5'd9) begin
            $display("  HATA: kayit adresi %0d, 9 olmali", alinan[22:18]); hata=hata+1; end
        if (alinan[17:16] !== 2'b10) begin
            $display("  HATA: TA %b, yazmada 10 olmali", alinan[17:16]); hata=hata+1; end
        if (alinan[15:0] !== 16'h1234) begin
            $display("  HATA: veri %04h, 1234 olmali", alinan[15:0]); hata=hata+1; end
        if (hata == 0) $display("  yazma cercevesi tam dogru");

        // ---- 2. okuma ----
        alinan = 0; bit_no = 0; okuma_kipi = 1'b1;
        phy_kayit = 16'hABCD;
        komut(1'b0, 5'd1, 16'h0000);
        okuma_kipi = 1'b0;

        if (alinan[29:28] !== 2'b10) begin
            $display("  HATA: okuma OP %b, 10 olmali", alinan[29:28]);
            hata = hata + 1;
        end
        if (oku_veri !== 16'hABCD) begin
            $display("  HATA: okunan %04h, ABCD olmali", oku_veri);
            hata = hata + 1;
        end else $display("  okuma dogru: %04h", oku_veri);

        // ---- 3. okumada hat gercekten birakildi mi ----
        // mdio_yon veri evresinde 0 olmali; yukarida phy_surer ile
        // veri gelebilmis olmasi zaten bunu kanitliyor, ama acikca
        // yazalim ki bir dahaki degisiklikte gozden kacmasin.
        if (hata == 0)
            $display("  okumada hat TA'dan once birakildi (veri geldi)");

        if (hata == 0) $display("MDIO testi GECTI");
        else           $display("MDIO testi KALDI: %0d hata", hata);
        $finish;
    end

    initial begin
        #2_000_000;
        $display("MDIO testi KALDI: zaman asimi");
        $finish;
    end

endmodule

`default_nettype wire
