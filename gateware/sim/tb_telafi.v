// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// Telafi filtresi testi — durtme cevabi ve doyurma.
//
// DURTME CEVABI: girise tek bir 1 verip cikisi izliyoruz. Cikan dizi
// katsayilarin ta kendisi olmali. Tutmuyorsa RTL, Python'da
// tasarladigimiz filtreyi kurmuyor demektir — katsayilar dogru ama
// baglanti yanlis olabilir, ve o fark ancak boyle gorunur.
//
// DOYURMA: telafi filtresi bant kenarinda 1'den buyuk kazanc veriyor.
// Tam olcege yakin bir giris cikista tasabilir. Tasan sayi sarip
// isaret degistirirse bozulma kirpmadan cok daha kotu olur — kirpma
// harmonik verir, sarma genis bantli gurultu verir. Doyurmanin
// calistigini gormek gerek.

`timescale 1ns/1ps
`default_nettype none

module tb_telafi;

    localparam GIRIS_BIT = 17;

    reg clk = 0, rst = 1;
    reg signed [16:0] giris = 0;
    reg giris_gecerli = 0;
    wire signed [23:0] cikis;
    wire cikis_gecerli;

    always #6.25 clk = ~clk;

    fir_telafi dut (.clk(clk), .rst(rst),
                    .giris(giris), .giris_gecerli(giris_gecerli),
                    .cikis(cikis), .cikis_gecerli(cikis_gecerli));

    // beklenen durtme cevabi: katsayilar / 2^15 * durtme genligi
    integer bekle [0:10];
    integer i, n, hata;

    // durtme genligi 32768 secildi: katsayi/32768*32768 = katsayi,
    // yani cikis dogrudan katsayiyi vermeli. Boylece yuvarlama
    // hatasini da goruyoruz.
    localparam DURTME = 32768;

    initial begin
        bekle[0] =    -19; bekle[1] =    200; bekle[2] =  -1140;
        bekle[3] =   4721; bekle[4] = -16826; bekle[5] =  58896;
        bekle[6] = -16826; bekle[7] =   4721; bekle[8] =  -1140;
        bekle[9] =    200; bekle[10] =   -19;
        hata = 0;

        $display("Telafi filtresi testi");
        #100; @(posedge clk); #1; rst = 0;

        // ---------------- durtme cevabi
        @(posedge clk); #1;
        giris = DURTME; giris_gecerli = 1;
        @(posedge clk); #1;
        giris = 0; giris_gecerli = 1;

        // BORU HATTI GECIKMESI. Ilk gecerli cikis, girisin kendisi
        // henuz kaydirmali hatta girmeden once uretilen degerdir;
        // katsayilar ondan SONRA baslar. Test once bunu saymayi
        // unutmustu ve butun dizi bir kayik gorundu — tasarim
        // dogruydu, hizalama yanlisti.
        n = -1;
        while (n < 11) begin
            @(posedge clk); #1;
            if (cikis_gecerli) begin
                if (n >= 0 && n < 11) begin
                    if (cikis != bekle[n]) begin
                        // +-1 yuvarlama farki kabul
                        if (cikis > bekle[n] + 1 || cikis < bekle[n] - 1) begin
                            $display("  h[%0d] beklenen %0d, gelen %0d",
                                     n, bekle[n], cikis);
                            hata = hata + 1;
                        end
                    end
                end
                n = n + 1;
            end
        end
        if (hata == 0)
            $display("  durtme cevabi katsayilarla ayni (11 katsayi)");

        // ---------------- doyurma
        giris_gecerli = 0;
        @(posedge clk); #1;
        rst = 1; @(posedge clk); #1; rst = 0;
        giris = 17'sh0FFFF;      // tam olcek pozitif
        giris_gecerli = 1;
        for (i = 0; i < 40; i = i + 1) @(posedge clk);
        #1;
        $display("  tam olcek girise cikis: %0d (tavan %0d)",
                 cikis, (1<<23)-1);
        if (cikis < 0) begin
            $display("  HATA: cikis isaret degistirdi — doyurma calismiyor");
            hata = hata + 1;
        end

        if (hata == 0) $display("Telafi filtresi testi GECTI");
        else begin
            $display("Telafi filtresi testi KALDI: %0d hata", hata);
            $fatal;
        end
        $finish;
    end

endmodule

`default_nettype wire
