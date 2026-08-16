// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
//
// CRC32 BAYT ADIMI — DUZLESTIRILMIS BICIM OZGUNUYLE AYNI MI.
//
// rgmii_veris.v'deki CRC bit-seri dongu olarak yaziliydi ve nextpnr
// olcumune gore clk_eth'in kritik yolu tam orasiydi (azami frekans
// tohuma gore 112-138 MHz, hedef 125). Fonksiyon dogrusal oldugu
// icin dengeli bir XOR agacina duzlestirildi (rtl/crc32_uret.py).
//
// DUZLESTIRME SESSIZCE YANLIS OLABILIR. Bir CRC hatasi kartta
// "butun cerceveler bozuk" diye gorunur ve insan once PHY'de,
// kabloda, saatte arar. O yuzden esdegerlik burada kanitlaniyor:
//
//   - butun 256 bayt degeri, cok sayida rastgele CRC durumuyla
//   - taban vektorleri (her giris biti tek basina)
//   - bilinen bir cerceve uzerinde tam FCS karsilastirmasi
//
// Fonksiyon dogrusal oldugu icin taban vektorlerinde ve sabit
// terimde eslesme, BUTUN girisler icin eslesme demektir. Rastgele
// kosu onun ustune bir kat daha koyuyor.

`timescale 1ns/1ps
`default_nettype none

module tb_crc32;

    integer hata = 0;

    // ---- OZGUN BICIM: bit-seri dongu (rgmii_veris.v'nin eski hali)
    function [31:0] crc_ozgun;
        input [31:0] c;
        input [7:0]  d;
        integer i;
        reg [31:0] t;
        begin
            t = c ^ {24'd0, d};
            for (i = 0; i < 8; i = i + 1)
                t = t[0] ? ((t >> 1) ^ 32'hEDB88320) : (t >> 1);
            crc_ozgun = t;
        end
    endfunction

    // ---- DUZLESTIRILMIS BICIM
`include "crc32_bayt.vh"

    integer i, j;
    reg [31:0] c;
    reg [7:0]  d;
    reg [31:0] a, b;

    initial begin
        $display("CRC32 duzlestirme esdegerlik testi");

        // ---- 1. TABAN VEKTORLERI
        //
        // Dogrusal bir fonksiyon taban vektorlerinde ve sabit
        // teriminde esitse HER girdide esittir. Asil ispat bu.
        begin : taban
            integer yanlis;
            yanlis = 0;
            // sabit terim
            if (crc_ozgun(32'd0, 8'd0) !== crc_bayt(32'd0, 8'd0))
                yanlis = yanlis + 1;
            for (i = 0; i < 32; i = i + 1)
                if (crc_ozgun(32'd1 << i, 8'd0) !==
                    crc_bayt(32'd1 << i, 8'd0))
                    yanlis = yanlis + 1;
            for (i = 0; i < 8; i = i + 1)
                if (crc_ozgun(32'd0, 8'd1 << i) !==
                    crc_bayt(32'd0, 8'd1 << i))
                    yanlis = yanlis + 1;
            if (yanlis) begin
                $display("  HATA: %0d taban vektorunde ayrisma", yanlis);
                hata = hata + 1;
            end else
                $display("  41 taban vektorunun hepsi ayni (dogrusal ispat)");
        end

        // ---- 2. BUTUN BAYT DEGERLERI x rastgele CRC durumlari
        begin : genis
            integer yanlis;
            yanlis = 0;
            c = 32'hFFFFFFFF;
            for (j = 0; j < 400; j = j + 1) begin
                for (i = 0; i < 256; i = i + 1) begin
                    d = i[7:0];
                    a = crc_ozgun(c, d);
                    b = crc_bayt(c, d);
                    if (a !== b) yanlis = yanlis + 1;
                end
                c = crc_ozgun(c, j[7:0]);   // durumu ilerlet
            end
            if (yanlis) begin
                $display("  HATA: %0d ayrisma (256 bayt x 400 durum)",
                         yanlis);
                hata = hata + 1;
            end else
                $display("  102400 karsilastirmanin hepsi ayni");
        end

        // ---- 3. GERCEK CERCEVE UZERINDE FCS
        //
        // Iki bicim ayni FCS'i uretiyor mu — kartta gorunecek sey bu.
        begin : cerceve
            reg [31:0] c1, c2;
            c1 = 32'hFFFFFFFF; c2 = 32'hFFFFFFFF;
            for (i = 0; i < 60; i = i + 1) begin
                c1 = crc_ozgun(c1, i[7:0] + 8'h10);
                c2 = crc_bayt (c2, i[7:0] + 8'h10);
            end
            if (~c1 !== ~c2) begin
                $display("  HATA: 60 baytlik cercevede FCS ayri:");
                $display("        ozgun %08h, duzlestirilmis %08h", ~c1, ~c2);
                hata = hata + 1;
            end else
                $display("  60 baytlik cercevede FCS ayni: %08h", ~c1);
        end

        if (hata == 0) $display("CRC32 esdegerlik testi GECTI");
        else           $display("CRC32 esdegerlik testi KALDI: %0d hata", hata);
        $finish;
    end

endmodule

`default_nettype wire
