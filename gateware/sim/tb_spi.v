// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// spi_ana testi — karsisina GERCEK bir cihaz modeli konuyor.
//
// Modul kendi kendini dogrulayamaz: "sekiz kenar urettim" demek,
// cihazin dogru biti dogru anda gordugu anlamina gelmiyor. Bu yuzden
// karsi tarafta SPI mod 0 kurallarina gore YUKSELEN kenarda ornekleyen
// bir model duruyor. Kenar polaritesi ters olsaydi hat osiloskopta
// kusursuz gorunur, cihaz cop okurdu — o hatayi ancak boyle bir model
// yakalar.

`timescale 1ns/1ps
`default_nettype none

module tb_spi;

    localparam BOLEN = 4;

    reg clk = 1'b0;
    always #6.25 clk = ~clk;          // 80 MHz
    reg rst = 1'b1;

    reg  [31:0] veri = 0;
    reg  [5:0]  uzunluk = 0, oku_bit = 0;
    reg  [2:0]  cihaz = 0;
    reg         basla = 0;
    wire [31:0] okunan;
    wire        mesgul;

    wire        sclk, sdio_o, sdio_yon;
    wire [3:0]  csb, le;

    // ---------------------------------------------------------------
    // Cift yonlu hat modeli. Ana birim birakinca cihaz suruyor.
    // ---------------------------------------------------------------
    wire sdio;
    wire cihaz_surer;
    reg  cihaz_bit   = 1'b0;
    assign sdio = sdio_yon  ? sdio_o :
                  cihaz_surer ? cihaz_bit : 1'b1;   // bosta cekme

    spi_ana #(.BOLEN(BOLEN), .CIHAZ(4)) dut (
        .clk(clk), .rst(rst),
        .veri(veri), .uzunluk(uzunluk), .oku_bit(oku_bit),
        .cihaz(cihaz), .basla(basla),
        .okunan(okunan), .mesgul(mesgul),
        .sclk(sclk), .sdio_o(sdio_o), .sdio_yon(sdio_yon),
        .sdio_i(sdio), .csb(csb), .le(le));

    // ---------------------------------------------------------------
    // Cihaz modeli: CSB dusukken SCLK'nin YUKSELEN kenarinda ornekler.
    // ---------------------------------------------------------------
    reg [31:0] alinan = 0;
    integer    alinan_bit = 0;

    always @(posedge sclk)
        if (!csb[0] || !csb[1]) begin
            alinan     <= {alinan[30:0], sdio};
            alinan_bit <= alinan_bit + 1;
        end

    // ---------------------------------------------------------------
    // MODEL KENDI KENARLARINI SAYIYOR, ANA BIRIMIN YON PININI IZLEMIYOR.
    //
    // Once "cihaz_surer" @(negedge sdio_yon) ile aciliyordu. Ayni
    // simulasyon aninda hem cihazin negedge blogu hem yon degisimi
    // olusuyor ve sira belirsiz: model bir kenar GEC devreye giriyor,
    // ana birim ilk okuma kenarinda bosluk gorüyordu. Sonuc 0x5A
    // yerine 0x2D — yani 0x5A'nin bir bit kaydirilmisi. DUT dogruydu,
    // olcen yanlisti.
    //
    // Gercek cihaz komut evresinin bittigini KENDI saydigi bitlerden
    // biliyor. Model de oyle: 16 komut biti gectikten sonra, her
    // dusen kenarda bir sonraki veri bitini suruyor.
    // ---------------------------------------------------------------
    localparam KOMUT_BIT = 16;
    reg [7:0] yanit = 8'h5A;
    reg okuma_kipi = 1'b0;
    assign cihaz_surer = okuma_kipi && (alinan_bit >= KOMUT_BIT);

    always @(negedge sclk)
        if (cihaz_surer && alinan_bit - KOMUT_BIT < 8)
            cihaz_bit <= yanit[7 - (alinan_bit - KOMUT_BIT)];

    integer hata = 0;

    task komut(input [31:0] d, input [5:0] u, input [5:0] o, input [2:0] c);
        begin
            @(posedge clk);
            veri = d; uzunluk = u; oku_bit = o; cihaz = c; basla = 1;
            @(posedge clk); basla = 0;
            wait (mesgul);
            wait (!mesgul);
            @(posedge clk);
        end
    endtask

    initial begin
        $display("spi_ana testi");
        repeat (5) @(posedge clk);
        rst = 0;
        repeat (5) @(posedge clk);

        // ---- 1. saf yazma: AD9251 komut cercevesi ----
        // 16 bit komut (R/W=0, W=00, adres 0x014) + 8 bit veri 0x20
        alinan = 0; alinan_bit = 0;
        komut({8'h00, 16'h0014, 8'h20}, 6'd24, 6'd0, 3'd0);

        if (alinan_bit !== 24) begin
            $display("  HATA: %0d bit saatlendi, 24 olmali", alinan_bit);
            hata = hata + 1;
        end else $display("  24 bit saatlendi");

        if (alinan[23:0] !== 24'h0014_20) begin
            $display("  HATA: cihaz %06h aldi, 001420 beklendi", alinan[23:0]);
            hata = hata + 1;
        end else $display("  cihaz dogru cerceveyi aldi (001420)");

        if (csb !== 4'b1111) begin
            $display("  HATA: CSB birakilmadi: %b", csb); hata = hata + 1;
        end else $display("  CSB birakildi");

        // ---- 2. ikinci cihaz secimi ----
        alinan = 0; alinan_bit = 0;
        komut({8'h00, 16'h000D, 8'hFF}, 6'd24, 6'd0, 3'd1);
        if (alinan[23:0] !== 24'h000D_FF) begin
            $display("  HATA: 2. cihaz %06h aldi", alinan[23:0]); hata = hata + 1;
        end else $display("  ikinci cihaz da dogru aldi");

        // ---- 3. okuma: son 8 bit cihazdan ----
        alinan = 0; alinan_bit = 0; yanit = 8'h5A; okuma_kipi = 1'b1;
        komut({8'h00, 16'h8014, 8'h00}, 6'd24, 6'd8, 3'd0);
        okuma_kipi = 1'b0;

        if (okunan[7:0] !== 8'h5A) begin
            $display("  HATA: okunan %02h, 5A beklendi", okunan[7:0]);
            hata = hata + 1;
        end else $display("  okuma dogru: %02h", okunan[7:0]);

        // ---- 4. LE darbesi: aktarim sonunda, secili hatta ----
        begin : le_denetim
            integer gorulen; gorulen = 0;
            fork
                komut({8'h00, 16'h0001, 8'h02}, 6'd24, 6'd0, 3'd2);
                begin
                    // MESGUL YUKSELENE KADAR BEKLE.
                    // Once dogrudan "while (mesgul)" yaziyordum: fork
                    // dallari ayni anda basliyor, o anda mesgul HENUZ
                    // 0 ve dongu hic donmeden cikiyordu. Test LE'yi
                    // "hic gelmedi" diye rapor etti — bakilan yer
                    // yanlisti, cikan sinyal degil.
                    wait (mesgul);
                    while (mesgul) begin
                        @(posedge clk);
                        if (le[2]) gorulen = 1;
                        if (le & ~4'b0100) begin
                            $display("  HATA: yanlis hatta LE darbesi: %b", le);
                            hata = hata + 1;
                        end
                    end
                end
            join
            if (!gorulen) begin
                $display("  HATA: LE darbesi hic gelmedi");
                hata = hata + 1;
            end else $display("  LE darbesi dogru hatta geldi");
        end

        if (hata == 0) $display("spi_ana testi GECTI");
        else           $display("spi_ana testi KALDI: %0d hata", hata);
        $finish;
    end

    initial begin
        #500_000;
        $display("spi_ana testi KALDI: zaman asimi");
        $finish;
    end

endmodule

`default_nettype wire
