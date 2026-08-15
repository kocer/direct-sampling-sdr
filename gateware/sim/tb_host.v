// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// UART + host arayuzu testi — uctan uca.
//
// Gercek bir seri hat gibi surulyor: bayt bayt, tam bit sureleriyle.
// Modulleri dogrudan birbirine baglayip "gecerli" darbeleri elle
// uretmek testi kendi varsayimini dogrular hale getirirdi; UART
// cerceve hatasi ya da baud hatasi hic gorunmezdi.

`timescale 1ns/1ps
`default_nettype none

module tb_host;

    localparam BOLEN = 80;              // 80 MHz / 1 Mbaud
    localparam BIT_NS = 1000;           // 1 us

    reg clk = 1'b0;
    always #6.25 clk = ~clk;            // 80 MHz
    reg rst = 1'b1;

    reg  hat_rx = 1'b1;
    wire hat_tx;

    wire [7:0]  al_bayt, ver_bayt;
    wire        al_gecerli, ver_gonder, ver_mesgul;
    wire [7:0]  kayit_adr;
    wire [31:0] kayit_veri;
    wire        kayit_yaz;
    wire [31:0] kayit_oku;

    uart_al #(.BOLEN(BOLEN)) u_al (
        .clk(clk), .rst(rst), .rx(hat_rx),
        .bayt(al_bayt), .gecerli(al_gecerli));

    uart_ver #(.BOLEN(BOLEN)) u_ver (
        .clk(clk), .rst(rst),
        .bayt(ver_bayt), .gonder(ver_gonder),
        .tx(hat_tx), .mesgul(ver_mesgul));

    host_arayuz #(.ZAMAN_ASIMI(8000)) u_host (   // 100 us, test kisalsin
        .clk(clk), .rst(rst),
        .al_bayt(al_bayt), .al_gecerli(al_gecerli),
        .ver_bayt(ver_bayt), .ver_gonder(ver_gonder),
        .ver_mesgul(ver_mesgul),
        .kayit_adr(kayit_adr), .kayit_veri(kayit_veri),
        .kayit_yaz(kayit_yaz), .kayit_oku(kayit_oku));

    // gercek kayit dosyasi — arayuzu de birlikte sinaniyor
    wire        alis_ac, veris_ac, yazilim_rst, nco_yukle;
    wire [3:0]  kanal_maske;
    wire [11:0] azalt_orani, tx_oran;
    wire [31:0] nco_artis, ofs0, ofs1, ofs2, ofs3, tx_artis;
    wire [4:0]  zincir_uzun, zincir_adr;
    wire        zincir_gonder, zincir_yaz;
    wire [7:0]  zincir_veri;
    wire [13:0] desen_a, desen_b;
    wire        desen_dene;

    kayit u_kayit (
        .clk(clk), .rst(rst),
        .adr(kayit_adr), .veri(kayit_veri), .yaz(kayit_yaz),
        .oku_veri(kayit_oku), .oku_adr(kayit_adr),
        .pll_kilit(1'b1), .adc_hizali(1'b1), .tasma(1'b0),
        .alis_ac(alis_ac), .veris_ac(veris_ac),
        .yazilim_rst(yazilim_rst),
        .kanal_maske(kanal_maske), .azalt_orani(azalt_orani),
        .nco_artis(nco_artis),
        .nco_ofset0(ofs0), .nco_ofset1(ofs1),
        .nco_ofset2(ofs2), .nco_ofset3(ofs3),
        .nco_yukle(nco_yukle),
        .tx_artis(tx_artis), .tx_oran(tx_oran),
        .zincir_uzun(zincir_uzun), .zincir_gonder(zincir_gonder),
        .zincir_veri(zincir_veri), .zincir_adr(zincir_adr),
        .zincir_yaz(zincir_yaz),
        .adc_desen_a(desen_a), .adc_desen_b(desen_b),
        .adc_desen_dene(desen_dene),
        .adc_takas(2'b00));

    integer hata = 0;

    // ---------------------------------------------------------------
    // Seri surucu ve alici — bit suresi ile
    // ---------------------------------------------------------------
    task seri_yolla;
        input [7:0] b;
        integer i;
        begin
            hat_rx = 1'b0;                 // baslangic
            #(BIT_NS);
            for (i = 0; i < 8; i = i + 1) begin
                hat_rx = b[i];             // LSB once
                #(BIT_NS);
            end
            hat_rx = 1'b1;                 // dur
            #(BIT_NS);
        end
    endtask

    // KENDI DONGU DEGISKENI. Cagiranin degiskenini yeniden kullanan
    // bir task daha once testi sessizce yanlis yapmisti.
    task seri_al;
        output [7:0] b;
        integer j;
        begin
            @(negedge hat_tx);             // baslangic biti
            #(BIT_NS + BIT_NS/2);          // ilk verinin ortasi
            for (j = 0; j < 8; j = j + 1) begin
                b[j] = hat_tx;
                #(BIT_NS);
            end
        end
    endtask

    task yaz_komut;
        input [7:0]  adr;
        input [31:0] veri;
        begin
            seri_yolla(8'hA5);
            seri_yolla(adr);
            seri_yolla(veri[31:24]);
            seri_yolla(veri[23:16]);
            seri_yolla(veri[15:8]);
            seri_yolla(veri[7:0]);
            seri_yolla(adr ^ veri[31:24] ^ veri[23:16] ^
                       veri[15:8] ^ veri[7:0]);
        end
    endtask

    reg [7:0]  yanit;
    reg [31:0] okunan;

    initial begin
        $display("host arayuzu testi");
        repeat (10) @(posedge clk);
        rst = 1'b0;
        repeat (10) @(posedge clk);

        // ---- 1. gecerli yazma: NCO artisi ----
        fork
            yaz_komut(8'h03, 32'h1234_5678);
            seri_al(yanit);
        join
        if (yanit !== 8'h06) begin
            $display("  HATA: kabul beklendi, gelen %h", yanit);
            hata = hata + 1;
        end else $display("  yazma kabul edildi");

        #(BIT_NS*2);
        if (nco_artis !== 32'h1234_5678) begin
            $display("  HATA: nco_artis=%h, beklenen 12345678", nco_artis);
            hata = hata + 1;
        end else $display("  kayit dogru yazildi");

        // ---- 2. bozuk denetim baytina RET ----
        #(BIT_NS*4);
        fork
            begin
                seri_yolla(8'hA5); seri_yolla(8'h02);
                seri_yolla(8'h00); seri_yolla(8'h00);
                seri_yolla(8'h00); seri_yolla(8'h20);
                seri_yolla(8'hFF);           // yanlis xor
            end
            seri_al(yanit);
        join
        if (yanit !== 8'h15) begin
            $display("  HATA: ret beklendi, gelen %h", yanit);
            hata = hata + 1;
        end else $display("  bozuk denetim reddedildi");

        #(BIT_NS*2);
        if (azalt_orani === 12'h020) begin
            $display("  HATA: reddedilen komut yine de yazilmis");
            hata = hata + 1;
        end else $display("  reddedilen komut kayda gitmedi");

        // ---- 3. okuma ----
        #(BIT_NS*4);
        fork
            begin
                seri_yolla(8'hA6); seri_yolla(8'h03); seri_yolla(8'h03);
            end
            begin
                seri_al(okunan[31:24]); seri_al(okunan[23:16]);
                seri_al(okunan[15:8]);  seri_al(okunan[7:0]);
            end
        join
        if (okunan !== 32'h1234_5678) begin
            $display("  HATA: okunan %h, beklenen 12345678", okunan);
            hata = hata + 1;
        end else $display("  okuma dogru: %h", okunan);

        // ---- 4. yarim cerceve sonrasi zaman asimi ile toparlanma ----
        #(BIT_NS*4);
        seri_yolla(8'hA5); seri_yolla(8'h04); seri_yolla(8'hAA);
        #(150_000);                        // zaman asimindan uzun
        fork
            yaz_komut(8'h05, 32'hDEAD_BEEF);
            seri_al(yanit);
        join
        if (yanit !== 8'h06 || ofs1 !== 32'hDEAD_BEEF) begin
            $display("  HATA: zaman asimindan sonra toparlanmadi (yanit %h, ofs1 %h)",
                     yanit, ofs1);
            hata = hata + 1;
        end else $display("  yarim cerceveden sonra toparlandi");

        if (hata == 0) $display("host arayuzu testi GECTI");
        else           $display("host arayuzu testi KALDI: %0d hata", hata);
        $finish;
    end

    initial begin
        #20_000_000;
        $display("host arayuzu testi KALDI: zaman asimi");
        $finish;
    end

endmodule

`default_nettype wire
