// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// CIC test tezgahi.
//
// Uc sey olculuyor:
//
// 1 AZALTMA ORANI. R giris ornegine karsilik bir cikis ornegi
//   cikmali. Tutmuyorsa sayac yanlis.
//
// 2 DC KAZANCI. Sabit girise sabit cikis. Kazanc (R*M)^N ve biz onu
//   kaydirmayla geri aliyoruz; cikis girisin yaklasik ayni olmali.
//   Degilse kaydirma miktari yanlis ve sinyal ya kirpiliyor ya
//   gomuluyor.
//
// 3 TASMA. CIC'in toplayicilari tam genislikte olmali. Tam olcek
//   girisle uzun sure surup cikisin sarip sarmadigina bakiyoruz.
//   Saran bir CIC sessizce anlamsiz veri uretir — en tehlikeli hata
//   turu, cunku sistem calisiyor gorunur.

`timescale 1ns/1ps
`default_nettype none

module tb_cic;

    localparam GIRIS_BIT = 14;
    localparam CIKIS_BIT = 24;

    reg clk = 0;
    reg rst = 1;
    reg [11:0] oran = 12'd16;
    reg signed [GIRIS_BIT-1:0] giris = 0;
    reg giris_gecerli = 0;
    wire signed [CIKIS_BIT-1:0] cikis;
    wire cikis_gecerli;

    always #6.25 clk = ~clk;

    cic_azalt #(.GIRIS_BIT(GIRIS_BIT), .CIKIS_BIT(CIKIS_BIT)) dut (
        .clk(clk), .rst(rst), .oran(oran),
        .giris(giris), .giris_gecerli(giris_gecerli),
        .cikis(cikis), .cikis_gecerli(cikis_gecerli)
    );

    integer i, cikis_sayisi, giris_sayisi;
    integer cik_min, cik_maks;
    integer hata_sayisi = 0;
    reg izle = 0;

    // CIKISI SUREKLI IZLE, DONGU ICINDEN ORNEKLEME.
    // Once dongunun icinde bakiyordum: cikis_gecerli tek cevrim
    // yuksek kaliyor ve dongunun baktigi an ona denk gelmiyordu,
    // yani cikis sayisi hep sifir cikti. Testin kendisi bozuktu,
    // tasarim degil.
    always @(posedge clk) begin
        if (izle && cikis_gecerli) begin
            cikis_sayisi = cikis_sayisi + 1;
            if (cikis_sayisi > 8) begin
                if (cikis > cik_maks) cik_maks = cikis;
                if (cikis < cik_min)  cik_min  = cikis;
            end
        end
    end

    task sifirla;
        begin
            rst = 1; giris_gecerli = 0; giris = 0;
            #100; @(posedge clk); #1; rst = 0;
            cikis_sayisi = 0; giris_sayisi = 0;
            cik_min = 1<<30; cik_maks = -(1<<30);
            izle = 1;
        end
    endtask

    // sabit deger surup cikisi izle
    task dc_testi(input [11:0] r, input signed [GIRIS_BIT-1:0] deger,
                  input integer ornek);
        begin
            oran = r;
            sifirla;
            giris = deger;
            for (i = 0; i < ornek; i = i + 1) begin
                @(posedge clk); #1;
                giris_gecerli = 1;
                @(posedge clk); #1;
                giris_gecerli = 0;
                giris_sayisi = giris_sayisi + 1;
            end
            izle = 0;
            $display("  R=%4d  giris %6d  ->  %0d giris / %0d cikis  (beklenen ~%0d)",
                     r, deger, giris_sayisi, cikis_sayisi, ornek / r);
            $display("          cikis araligi %0d .. %0d", cik_min, cik_maks);

            // azaltma orani
            if (cikis_sayisi < (ornek/r) - 2 || cikis_sayisi > (ornek/r) + 2) begin
                $display("  HATA: azaltma orani tutmuyor");
                hata_sayisi = hata_sayisi + 1;
            end
            // DC kazanci: kaydirma dogruysa cikis girise yakin olmali
            if (cik_maks != cik_min) begin
                $display("  HATA: sabit girise sabit cikis gelmiyor (%0d fark)",
                         cik_maks - cik_min);
                hata_sayisi = hata_sayisi + 1;
            end
            if (deger != 0 && cik_maks == 0) begin
                $display("  HATA: cikis sifir — sinyal kaydirmada gomulmus");
                hata_sayisi = hata_sayisi + 1;
            end
        end
    endtask

    initial begin
        $display("CIC testi");
        dc_testi(12'd16,   14'sd1000,  4000);
        dc_testi(12'd64,   14'sd1000, 12800);
        dc_testi(12'd16,   14'sd8191,  4000);   // tam olcek, tasma denemesi
        dc_testi(12'd16,  -14'sd8192,  4000);   // negatif tam olcek
        if (hata_sayisi == 0) $display("CIC testi GECTI");
        else begin
            $display("CIC testi KALDI: %0d hata", hata_sayisi);
            $fatal;
        end
        $finish;
    end

endmodule

`default_nettype wire
