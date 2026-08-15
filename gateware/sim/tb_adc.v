// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// adc_giris testi — AD9251 cogullanmis paralel CMOS.
//
// ADC'yi kenar bazinda taklit ediyoruz: DCO 80 MHz, veri yolu her
// yarim cevrimde degisiyor, ve VERI DCO KENARLARININ ARASINDA
// DEGISIYOR. Gercek parca DCO'yu goz merkezine getiriyor; testi
// kenar-hizali surersek modul yanlislikla gecer ve kartta duser.
//
// Uc sey sinaniyor:
//   1 duz polarite (once = A) bulunuyor mu
//   2 ters polarite otomatik yakalaniyor mu
//   3 desen bozulunca hizali dusuyor mu

`timescale 1ns/1ps
`default_nettype none

module tb_adc;

    localparam BIT   = 14;
    localparam YARIM = 6.25;            // 80 MHz DCO -> 12.5 ns

    reg              dco = 1'b0;
    reg  [BIT-1:0]   d   = 0;
    reg              asim = 1'b0;

    reg  [BIT-1:0]   desen_a = 14'h1555;
    reg  [BIT-1:0]   desen_b = 14'h2AAA;
    reg              desen_dene = 1'b0;

    wire [BIT-1:0]   ornek_a, ornek_b;
    wire             asim_a, asim_b, ornek_gecerli, takas, hizali, clk_adc;

    adc_giris #(.BIT(BIT)) dut (
        .dco(dco), .d(d), .asim(asim),
        .desen_a(desen_a), .desen_b(desen_b), .desen_dene(desen_dene),
        .clk_adc(clk_adc),
        .ornek_a(ornek_a), .ornek_b(ornek_b),
        .asim_a(asim_a), .asim_b(asim_b),
        .ornek_gecerli(ornek_gecerli),
        .takas(takas), .hizali(hizali)
    );

    always #(YARIM) dco = ~dco;

    integer hata = 0;

    task denetle;
        input [255:0] ad;
        input         beklenen;
        input         gercek;
        begin
            if (beklenen !== gercek) begin
                $display("  HATA: %0s — beklenen %b, gercek %b",
                         ad, beklenen, gercek);
                hata = hata + 1;
            end else begin
                $display("  %0s tamam", ad);
            end
        end
    endtask

    // ---------------------------------------------------------------
    // ADC surucusu.
    //
    // ters=0: A ornegi dusen kenardan SONRA suruluyor, yani sonraki
    //         YUKSELEN kenarda yakalaniyor; B bunun tersi.
    // Veri, yakalayacak kenardan yarim cevrimin yarisi kadar once
    // degisiyor — goz merkezi kenara denk geliyor.
    //
    // TAKAS BITININ MUTLAK POLARITESI TESTIN ISI DEGIL. Hangi
    // kenarin A oldugu kartta ADC'nin SPI ayarina ve yol
    // gecikmesine bagli; modulun isi onu BULMAK. Test ikisini de
    // surup her ikisinde de dogru kanal eslemesi cikiyor mu ona
    // bakiyor, takas ise sadece tutarli olmali (= ~ters).
    // ---------------------------------------------------------------
    reg ters = 1'b0;
    reg boz  = 1'b0;

    initial begin
        forever begin
            // dusen kenardan once surulen ornek
            @(negedge dco);
            #(YARIM/2) d <= boz  ? 14'h3FFF :
                            ters ? desen_b  : desen_a;
                       asim <= 1'b0;
            // yukselen kenardan once surulen ornek
            @(posedge dco);
            #(YARIM/2) d <= boz  ? 14'h0001 :
                            ters ? desen_a  : desen_b;
                       asim <= 1'b1;
        end
    end

    initial begin
        $display("adc_giris testi");

        repeat (4) @(posedge dco);
        desen_dene = 1'b1;

        // 256 ardisik eslesme + pay
        repeat (300) @(posedge dco);
        denetle("duz polarite hizalandi", 1'b1, hizali);
        denetle("takas biti tutarli",     1'b1, takas);

        // ornekler dogru kanala gitti mi
        @(posedge dco);
        if (ornek_a !== desen_a || ornek_b !== desen_b) begin
            $display("  HATA: ornek_a=%h (bekl %h), ornek_b=%h (bekl %h)",
                     ornek_a, desen_a, ornek_b, desen_b);
            hata = hata + 1;
        end else $display("  kanal esleme tamam");

        // ---- ters polarite ----
        ters = 1'b1;
        repeat (300) @(posedge dco);
        denetle("ters polarite hizalandi", 1'b1, hizali);
        denetle("ters takas biti tutarli", 1'b0, takas);

        @(posedge dco);
        if (ornek_a !== desen_a || ornek_b !== desen_b) begin
            $display("  HATA (ters): ornek_a=%h, ornek_b=%h", ornek_a, ornek_b);
            hata = hata + 1;
        end else $display("  ters kanal esleme tamam");

        // ---- desen bozuk ----
        boz = 1'b1;
        repeat (20) @(posedge dco);
        denetle("bozuk desende hizali dustu", 1'b0, hizali);

        // ---- denetim kapaninca polarite duruyor mu ----
        boz = 1'b0;
        repeat (300) @(posedge dco);
        desen_dene = 1'b0;
        repeat (50) @(posedge dco);
        denetle("denetim kapali, hizali duruyor", 1'b1, hizali);
        denetle("denetim kapali, takas duruyor",  1'b0, takas);

        if (hata == 0) $display("adc_giris testi GECTI");
        else           $display("adc_giris testi KALDI: %0d hata", hata);
        $finish;
    end

endmodule

`default_nettype wire
