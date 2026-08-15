// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// CIC azaltici — Hogenauer, N kademe, R oranli.
//
// NEDEN CIC: 80 MSPS'ten 48 kSPS'e inmek 1666 kat azaltma. Tek FIR
// ile bu binlerce carpan isterdi; ECP5-25F'te 28 carpan var.
//
// CIC'in carpani YOK. Sadece toplayici (integrator) ve fark alici
// (comb). Kaba azaltmayi o yapiyor, ince isi kucuk bir FIR bitiriyor.
//
// BEDELI: gecirme bandinda sin(x)/x egimi. N kademe icin bant
// kenarinda kayip
//     |sin(pi*f/R) / (pi*f/R)|^N
// R=1024, N=4'te bant kenarinda ~1.7 dB. cic_telafi.v bunu duzeltiyor.
//
// BUYUME: her kademe ve her azaltma biti isaret genisletiyor.
// Hogenauer'in kurali:
//     buyume = N * log2(R * M)
// N=4, R=2048, M=1 icin 44 bit. Girise 14 bit eklenince 58 bit.
// KIRPMAK YASAK: tasan bir toplayici sessizce sarar ve cikis
// tamamen anlamsizlasir. Toplayicilar tam genislikte tutuluyor,
// kirpma yalnizca EN SONDA ve yuvarlayarak yapiliyor.

`default_nettype none

module cic_azalt #(
    parameter GIRIS_BIT = 14,
    parameter KADEME    = 4,      // N
    parameter MAKS_R    = 2048,
    parameter CIKIS_BIT = 24
) (
    input  wire                        clk,
    input  wire                        rst,
    input  wire [11:0]                 oran,        // R, 1..MAKS_R
    input  wire signed [GIRIS_BIT-1:0] giris,
    input  wire                        giris_gecerli,
    output reg  signed [CIKIS_BIT-1:0] cikis,
    output reg                         cikis_gecerli
);

    // Hogenauer buyumesi: N * ceil(log2(R*M)), M = 1
    localparam LOG2R   = $clog2(MAKS_R);
    localparam IC_BIT  = GIRIS_BIT + (KADEME * LOG2R);

    // ---------------------------------------------------------------
    // Toplayici zinciri — giris hizinda kosuyor
    // ---------------------------------------------------------------
    reg signed [IC_BIT-1:0] topla [0:KADEME-1];

    // HER ALWAYS BLOGUNUN KENDI DONGU DEGISKENI VAR.
    // Tek bir "integer k"yi iki blokta kullanmak sentezde iki
    // surucu demek: yosys "multiple conflicting drivers" veriyordu.
    // Donguler acildigi icin sonuc simdilik dogru cikiyor, ama
    // degisken sentezciye birakilmis bir kaza — ayni hatanin bir
    // baska turu test tezgahinda gercekten yanlis sonuc uretmisti.
    integer k;   // integratorler / birinci blok
    integer m;   // fark kademeleri / ikinci blok
    always @(posedge clk) begin
        if (rst) begin
            for (k = 0; k < KADEME; k = k + 1)
                topla[k] <= {IC_BIT{1'b0}};
        end else if (giris_gecerli) begin
            topla[0] <= topla[0] + {{(IC_BIT-GIRIS_BIT){giris[GIRIS_BIT-1]}},
                                    giris};
            for (k = 1; k < KADEME; k = k + 1)
                topla[k] <= topla[k] + topla[k-1];
        end
    end

    // ---------------------------------------------------------------
    // Azaltma sayaci
    // ---------------------------------------------------------------
    reg [11:0] sayac;
    reg        azalt_darbe;

    always @(posedge clk) begin
        if (rst) begin
            sayac       <= 12'd0;
            azalt_darbe <= 1'b0;
        end else if (giris_gecerli) begin
            if (sayac >= oran - 1) begin
                sayac       <= 12'd0;
                azalt_darbe <= 1'b1;
            end else begin
                sayac       <= sayac + 1'b1;
                azalt_darbe <= 1'b0;
            end
        end else begin
            azalt_darbe <= 1'b0;
        end
    end

    // ---------------------------------------------------------------
    // Fark alici zinciri — azaltilmis hizda kosuyor
    // ---------------------------------------------------------------
    reg signed [IC_BIT-1:0] fark_g [0:KADEME-1];   // gecikme
    reg signed [IC_BIT-1:0] fark_c [0:KADEME-1];   // cikis

    always @(posedge clk) begin
        if (rst) begin
            for (m = 0; m < KADEME; m = m + 1) begin
                fark_g[m] <= {IC_BIT{1'b0}};
                fark_c[m] <= {IC_BIT{1'b0}};
            end
            cikis_gecerli <= 1'b0;
        end else if (azalt_darbe) begin
            fark_g[0] <= topla[KADEME-1];
            fark_c[0] <= topla[KADEME-1] - fark_g[0];
            for (m = 1; m < KADEME; m = m + 1) begin
                fark_g[m] <= fark_c[m-1];
                fark_c[m] <= fark_c[m-1] - fark_g[m];
            end
            cikis_gecerli <= 1'b1;
        end else begin
            cikis_gecerli <= 1'b0;
        end
    end

    // ---------------------------------------------------------------
    // Kirpma — YALNIZCA BURADA, ve yuvarlayarak.
    //
    // CIC'in kazanci (R*M)^N. R degisince kazanc degisiyor, yani
    // sabit bir kaydirma yetmiyor. Dogru olan R'ye gore kaydirmak
    // ama bolme pahali; onun yerine kaydirma miktarini disaridan
    // gelen R'nin log2'sinden turetiyoruz.
    //
    // Kesilen bitin en ustune bakip yuvarliyoruz. Duz kirpma her
    // ornekte asagi yonlu bir hata birakir ve o hata DC ofset olarak
    // gorunur — dogrudan ornekleme alicisinda DC ofset spektrumun
    // ortasinda bir cizgi demek.
    // ---------------------------------------------------------------
    // KAYDIRMA SUREKLI ATAMA, always @(*) DEGIL.
    // Once always @(*) blogunda hesapliyordum. O blok yalnizca
    // duyarlilik listesindeki bir sinyal DEGISINCE calisiyor; 'oran'
    // basta bir kez kurulup hic degismeyince blok hic kosmadi ve
    // kaydir X kaldi. X ile kaydirinca cikis da X oldu — ve
    // simulasyonda X gorunur ama sentezde bu "ne olursa olsun"
    // demektir, yani donanimda sessizce yanlis calisirdi.
    function [5:0] kaydirma;
        input [11:0] r;
        begin
            if      (r <= 12'd1)    kaydirma = 6'd0;
            else if (r <= 12'd2)    kaydirma = KADEME * 1;
            else if (r <= 12'd4)    kaydirma = KADEME * 2;
            else if (r <= 12'd8)    kaydirma = KADEME * 3;
            else if (r <= 12'd16)   kaydirma = KADEME * 4;
            else if (r <= 12'd32)   kaydirma = KADEME * 5;
            else if (r <= 12'd64)   kaydirma = KADEME * 6;
            else if (r <= 12'd128)  kaydirma = KADEME * 7;
            else if (r <= 12'd256)  kaydirma = KADEME * 8;
            else if (r <= 12'd512)  kaydirma = KADEME * 9;
            else if (r <= 12'd1024) kaydirma = KADEME * 10;
            else                    kaydirma = KADEME * 11;
        end
    endfunction

    // KAYDIRMA MIKTARI YAZMACTA.
    //
    // kaydirma() on iki kademeli bir oncelik zinciri, ve dogrudan
    // barrel shifter'i suruyordu. Zincir + kaydirici tek cevrime
    // sigmiyordu: nextpnr clk_sys'i 53.5 MHz olctu, 80 gerekiyor.
    // Kritik yol dort kanalin dordunde de buydu.
    //
    // Oysa 'oran' host bir kayit YAZMADIKCA degismiyor. Her cevrim
    // yeniden cozmenin bedeli var, faydasi yok. Yazmaca alinca
    // zincir kritik yoldan tamamen cikiyor, geriye sadece kaydirici
    // kaliyor.
    //
    // Bir cevrimlik gecikme zararsiz: oran degistiginde bir ornek
    // eski kazancla cikiyor, ve zaten oran degistiginde CIC'in
    // kendi gecici cevabi onlarca ornek suruyor.
    reg [5:0] kaydir;
    always @(posedge clk)
        if (rst) kaydir <= 6'd0;
        else     kaydir <= kaydirma(oran);

    wire signed [IC_BIT-1:0] ham = fark_c[KADEME-1];
    wire signed [IC_BIT-1:0] kaydirilmis = ham >>> kaydir;

    always @(posedge clk) begin
        if (rst)
            cikis <= {CIKIS_BIT{1'b0}};
        else if (azalt_darbe)
            cikis <= kaydirilmis[CIKIS_BIT-1:0];
    end

endmodule

`default_nettype wire
