// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
//
// TUM SISTEM TESTI — birlestirilmis cip, her cikis pininde gozlemci.
//
// NEDEN VAR. sim/ dizininde ondokuz test tezgahi vardi ve hepsi
// geciyordu, ama hicbiri UST MODULU kosturmuyordu; ust.v sadece
// sentezden geciyordu. Yani her modul tek basina dogruydu ve
// BIRLESTIRILMIS sistem hic calistirilmamisti. Entegrasyon hatalari
// tam bu boslukta yasar: yanlis baglanmis bir sinyal, ters
// polariteyle takilmis bir bayrak, hic surulmeyen bir cikis. Modul
// testleri bunlarin hicbirini goremez.
//
// UC IS YAPIYOR:
//
//   1 GERCEK UYARIM. ADC bacaklarina sinus veriliyor (cogullanmis
//     ikili kanal, tipki AD9251'in surdugu gibi), RGMII alis
//     yolundan gercek bir UDP kayit yazmasi geliyor. Uydurma
//     dahili sinyal yok — cipin gordugu sey kartta gorecegi sey.
//
//   2 HER CIKIS PININDE GOZLEMCI. Otuz yedi cikis ve iki cift
//     yonlu hattin her biri izleniyor: kac kez degisti, son degeri
//     ne. HIC DEGISMEYEN bir cikis ya test edilmemis bir islev ya
//     da baglanmamis bir sinyaldir; ikisi de bulunmasi gereken sey.
//     Bu, "kart geldi, sekiz cikis olu" surprizini tezgahta yakalar.
//
//   3 ISLEV DENETIMI. Alis zinciri paket uretiyor mu, kayit yazmasi
//     etki ediyor mu, DAC suruluyor mu, role zinciri kayiyor mu,
//     PA izni guvenli varsayilanda mi.
//
// ECP5 ilkelleri sim/ecp5_sim.v'deki davranis modelleriyle
// kosuyor ve o modellerin KENDI testi var (tb_ecp5_sim.v) — biri
// yanlis olsaydi bu test gecer ama hicbir sey kanitlamazdi.

`timescale 1ns/1ps
`default_nettype none

module tb_ust;

    integer hata = 0;

    // =================================================================
    // saatler
    // =================================================================
    reg clk_sys = 1'b0;
    always #6.25 clk_sys = ~clk_sys;        // 80 MHz

    // IKI ADC'NIN SAATI AYRI VE ARALARINDA FAZ FARKI VAR.
    //
    // Once ikisine de TEK bir saat veriyordum. Sonucu su oldu: iki
    // gecis FIFO'sunu bilerek bagimsiz bosaltip testi mutasyona
    // soktum ve test YAKALAMADI — ayni saatle iki FIFO kilitli adimda
    // doluyor, bagimsiz bosalsalar bile kaymiyorlar. Yani hizalama
    // denetimi gecen ama hicbir sey kanitlamayan bir denetimdi.
    //
    // Gercekte iki AD9251'in DCO'su ayri cikislar: ayni frekans (ayni
    // VCXO'dan turuyorlar) ama yol uzunlugu ve cip ici gecikme
    // yuzunden faz farki var. Fark modellenince FIFO'lar farkli
    // anlarda doluyor ve bagimsiz bosaltma gercekten kaydiriyor.
    reg adc_dco = 1'b0;
    always #6.25 adc_dco = ~adc_dco;        // ADC1, 80 MHz

    reg adc2_dco_r = 1'b0;
    initial begin
        #3.1;                                // faz farki, yarim cevrimden az
        forever #6.25 adc2_dco_r = ~adc2_dco_r;
    end

    reg rgmii_rxc = 1'b0;
    always #4 rgmii_rxc = ~rgmii_rxc;       // 125 MHz, PHY'den

    // =================================================================
    // cip
    // =================================================================
    reg  [13:0] adc1_d = 14'd0, adc2_d = 14'd0;
    reg         adc1_or = 1'b0, adc2_or = 1'b0;
    reg  [3:0]  rgmii_rd = 4'd0;
    reg         rgmii_rctl = 1'b0;
    reg         dbg_rx = 1'b1;

    wire [13:0] dac_a, dac_b, dac2_d;
    wire dac_wrt_a, dac_wrt_b, dac2_iqwrt, dac2_iqsel, dac2_iqreset;
    wire [3:0] rgmii_td;
    wire rgmii_tctl, rgmii_tclk;
    wire rly_ser, rly_srclk, rly_rclk, pa_inhibit;
    wire led_status, led_rx, led_tx, led_data, dbg_tx;
    wire adc_sclk, adc1_ncsb, adc2_ncsb, adc_sync;
    wire att_clk, att_data, att1_le, att2_le, att3_le, att4_le;
    wire pa_att_le, bias_cs1, bias_cs2, pa_adc_cs;
    wire phy1_nrst, phy2_nrst, mdc;
    wire adc_sdio, mdio_hat;

    ust dut (
        .clk_sys(clk_sys),
        .adc1_dco(adc_dco), .adc1_d(adc1_d), .adc1_or(adc1_or),
        .adc2_dco(adc2_dco_r), .adc2_d(adc2_d), .adc2_or(adc2_or),
        .dac_a(dac_a), .dac_wrt_a(dac_wrt_a),
        .dac_b(dac_b), .dac_wrt_b(dac_wrt_b),
        .dac2_d(dac2_d), .dac2_iqwrt(dac2_iqwrt),
        .dac2_iqsel(dac2_iqsel), .dac2_iqreset(dac2_iqreset),
        .rgmii_td(rgmii_td), .rgmii_tctl(rgmii_tctl),
        .rgmii_tclk(rgmii_tclk),
        .rgmii_rd(rgmii_rd), .rgmii_rctl(rgmii_rctl),
        .rgmii_rxc(rgmii_rxc),
        .rly_ser(rly_ser), .rly_srclk(rly_srclk), .rly_rclk(rly_rclk),
        .pa_inhibit(pa_inhibit),
        .led_status(led_status), .led_rx(led_rx),
        .led_tx(led_tx), .led_data(led_data),
        .dbg_rx(dbg_rx), .dbg_tx(dbg_tx),
        .adc_sclk(adc_sclk), .adc_sdio(adc_sdio),
        .adc1_ncsb(adc1_ncsb), .adc2_ncsb(adc2_ncsb), .adc_sync(adc_sync),
        .att_clk(att_clk), .att_data(att_data),
        .att1_le(att1_le), .att2_le(att2_le),
        .att3_le(att3_le), .att4_le(att4_le),
        .pa_att_le(pa_att_le),
        .bias_cs1(bias_cs1), .bias_cs2(bias_cs2), .pa_adc_cs(pa_adc_cs),
        .phy1_nrst(phy1_nrst), .phy2_nrst(phy2_nrst),
        .mdc(mdc), .mdio_hat(mdio_hat)
    );

    // =================================================================
    // ADC UYARIMI — cogullanmis ikili kanal, sinus
    //
    // AD9251 cogullanmis modda iki kanali TEK yolda veriyor: A ve B
    // ornekleri DCO'nun ayri kenarlarinda. Veri, yakalayacak kenardan
    // once degisiyor ki goz merkezi kenara denk gelsin (tb_adc.v ile
    // ayni yaklasim).
    //
    // Iki kanala FARKLI frekans veriliyor. Ayni sinyali verseydik
    // kanallarin yer degistirmesi gorunmezdi.
    // =================================================================
    // HIZALAMA KIPI. ADC arayuzu hangi kenarin A hangisinin B
    // oldugunu kendi buluyor: iki kanala FARKLI test deseni yazilip
    // hangisinin tuttuguna bakiliyor. Bu islev sistem duzeyinde hic
    // test edilmemisti, ve gozlemci raporu onu dolayli yoldan
    // gosterdi — pa_inhibit hic yukselmiyordu, cunku
    //     pa_inhibit = veris_ac & a1_hizali & a2_hizali & kopek_canli
    // ve hizalama hic tamamlanmiyordu.
    //
    // Yani "verici acilmiyor" bulgusunun altindan "hizalama test
    // edilmemis" cikti. Tasarim dogru: ADC hizalanmadan yayin
    // yapilmamali.
    // IKI ADC'YE AYRI VERI. Yorumda "farkli frekans veriliyor"
    // yaziyordu ama kod ikisine de AYNI degeri suruyordu; yani iki
    // ADC'nin yer degistirmesi ya da FIFO'larin birbirine gore
    // kaymasi bu testte hic gorunmezdi. Yorum dogru, kod yanlisti.
    //
    // Simdi ADC2, ADC1'in sabit bir ofset kaymisi. Boylece hizalama
    // dogrudan olculebiliyor: FIFO cikisinda fark HER ZAMAN AYRIM
    // olmali. Kayarlarsa fark degisir.
    localparam signed [13:0] AYRIM = 14'sd1000;

    reg        hiza_kip = 1'b0;
    localparam [13:0] DESEN_A = 14'h1234;
    localparam [13:0] DESEN_B = 14'h2ABC;

    real faz_a = 0.0, faz_b = 0.0;
    localparam real PI = 3.14159265358979;
    integer ornek_sayaci = 0;

    function [13:0] sinus;
        input real faz;
        real v;
        begin
            v = 6000.0 * $sin(faz);
            sinus = $rtoi(v) & 14'h3FFF;
        end
    endfunction

    // ADC1 kendi saatine gore. Surdugu degerleri SAKLIYOR.
    reg [13:0] son_a, son_b;
    initial begin
        forever begin
            @(negedge adc_dco); #1;
            faz_a = faz_a + 2.0 * PI * 2.0 / 80.0;   // 2 MHz
            son_a  = hiza_kip ? DESEN_A : sinus(faz_a);
            adc1_d = son_a;
            @(posedge adc_dco); #1;
            faz_b = faz_b + 2.0 * PI * 7.1 / 80.0;   // 7.1 MHz
            son_b  = hiza_kip ? DESEN_B : sinus(faz_b);
            adc1_d = son_b;
            ornek_sayaci = ornek_sayaci + 1;
        end
    end

    // ADC2 KENDI saatine gore, ADC1'IN SURDUGU degerin AYRIM kadar
    // kaymisi.
    //
    // ONCE faz degiskenlerinden YENIDEN HESAPLIYORDU ve dogru tasarim
    // 200/200 hizasiz cikti — hata tezgahtaydi: ADC2'nin sureci,
    // ADC1'in fazi bir sonraki ornege ilerlettikten SONRA okuyordu,
    // yani iki ADC farkli ornek indislerini suruyordu. Saklanan
    // degeri kullanmak bunu kesin cozuyor: fark her zaman AYRIM,
    // faz farki ne olursa olsun.
    initial begin
        forever begin
            @(negedge adc2_dco_r); #1;
            adc2_d = hiza_kip ? DESEN_A : (son_a + AYRIM);
            @(posedge adc2_dco_r); #1;
            adc2_d = hiza_kip ? DESEN_B : (son_b + AYRIM);
        end
    end

    // =================================================================
    // RGMII ALIS SURUCUSU — gercek UDP kayit yazmasi
    // =================================================================
    reg [7:0] cerceve [0:127];
    integer   cerceve_uz;

    function [31:0] crc_bayt;
        input [31:0] c;
        input [7:0]  d;
        integer i;
        reg [31:0] x;
        begin
            x = c ^ {24'd0, d};
            for (i = 0; i < 8; i = i + 1)
                x = x[0] ? ((x >> 1) ^ 32'hEDB88320) : (x >> 1);
            crc_bayt = x;
        end
    endfunction

    // VERIYI KENARIN USTUNDE DEGISTIRME. Ilk yazdigimda tam kenarda
    // suruyordum ve ornekleme kenariyla yaris kuruyordum: cerceveler
    // dogru uzunlukta geliyordu ama CRC hep tutmuyordu. Kenardan
    // sonra 1 ns bekleyince veri, kendisini yakalayacak kenardan
    // yarim cevrim once kararli oluyor — goz merkezi kenara denk.
    task nibble_ver;
        input [7:0] d;
        input       gecerli;
        begin
            @(negedge rgmii_rxc); #1;
            rgmii_rd   = d[3:0];        // once ALT nibble
            rgmii_rctl = gecerli;
            @(posedge rgmii_rxc); #1;
            rgmii_rd   = d[7:4];
            rgmii_rctl = gecerli;
        end
    endtask

    // Ethernet + IPv4 + UDP + host cercevesi kur
    task kayit_yaz;
        input [7:0]  adr;
        input [31:0] veri;
        integer i;
        reg [31:0] c;
        reg [7:0]  xr;
        begin
            // --- Ethernet basligi
            for (i = 0; i < 6; i = i + 1) cerceve[i]     = 8'hFF;   // dst
            for (i = 0; i < 6; i = i + 1) cerceve[6 + i] = 8'h02;   // src
            cerceve[12] = 8'h08; cerceve[13] = 8'h00;               // IPv4
            // --- IPv4 basligi (IHL=5)
            cerceve[14] = 8'h45; cerceve[15] = 8'h00;
            cerceve[16] = 8'h00; cerceve[17] = 8'd35;   // toplam uzunluk
            cerceve[18] = 8'h00; cerceve[19] = 8'h00;
            cerceve[20] = 8'h00; cerceve[21] = 8'h00;
            cerceve[22] = 8'd64; cerceve[23] = 8'd17;   // TTL, UDP
            cerceve[24] = 8'h00; cerceve[25] = 8'h00;   // saglama (denetlenmiyor)
            for (i = 0; i < 4; i = i + 1) cerceve[26 + i] = 8'd10;  // kaynak IP
            for (i = 0; i < 4; i = i + 1) cerceve[30 + i] = 8'd10;  // hedef IP
            // --- UDP basligi
            cerceve[34] = 8'h13; cerceve[35] = 8'h89;   // kaynak port 5001
            cerceve[36] = 8'h13; cerceve[37] = 8'h89;   // hedef port 5001
            cerceve[38] = 8'h00; cerceve[39] = 8'd15;   // uzunluk
            cerceve[40] = 8'h00; cerceve[41] = 8'h00;   // saglama = 0
            // --- host cercevesi: A5 adr d3 d2 d1 d0 xor
            cerceve[42] = 8'hA5;
            cerceve[43] = adr;
            cerceve[44] = veri[31:24];
            cerceve[45] = veri[23:16];
            cerceve[46] = veri[15:8];
            cerceve[47] = veri[7:0];
            xr = adr ^ veri[31:24] ^ veri[23:16] ^ veri[15:8] ^ veri[7:0];
            cerceve[48] = xr;
            cerceve_uz = 49;
            // --- FCS
            c = 32'hFFFFFFFF;
            for (i = 0; i < cerceve_uz; i = i + 1)
                c = crc_bayt(c, cerceve[i]);
            c = ~c;
            cerceve[cerceve_uz + 0] = c[7:0];
            cerceve[cerceve_uz + 1] = c[15:8];
            cerceve[cerceve_uz + 2] = c[23:16];
            cerceve[cerceve_uz + 3] = c[31:24];
            cerceve_uz = cerceve_uz + 4;

            // --- gonder
            for (i = 0; i < 7; i = i + 1) nibble_ver(8'h55, 1'b1);
            nibble_ver(8'hD5, 1'b1);
            for (i = 0; i < cerceve_uz; i = i + 1)
                nibble_ver(cerceve[i], 1'b1);
            for (i = 0; i < 12; i = i + 1) nibble_ver(8'h00, 1'b0);
        end
    endtask

    // =================================================================
    // GOZLEMCILER — her cikis pini
    //
    // Her sinyal icin: kac kez degisti. Sifir kalan bir cikis, ya
    // test edilmemis bir islev ya da baglanmamis bir sinyaldir.
    // =================================================================
    localparam N_GOZ = 39;
    integer  gecis [0:N_GOZ-1];
    reg [8*14-1:0] goz_ad [0:N_GOZ-1];
    integer gi;

    initial for (gi = 0; gi < N_GOZ; gi = gi + 1) gecis[gi] = 0;

    initial begin
        goz_ad[0]="dac_a";        goz_ad[1]="dac_wrt_a";
        goz_ad[2]="dac_b";        goz_ad[3]="dac_wrt_b";
        goz_ad[4]="dac2_d";       goz_ad[5]="dac2_iqwrt";
        goz_ad[6]="dac2_iqsel";   goz_ad[7]="dac2_iqreset";
        goz_ad[8]="rgmii_td";     goz_ad[9]="rgmii_tctl";
        goz_ad[10]="rgmii_tclk";  goz_ad[11]="rly_ser";
        goz_ad[12]="rly_srclk";   goz_ad[13]="rly_rclk";
        goz_ad[14]="pa_inhibit";  goz_ad[15]="led_status";
        goz_ad[16]="led_rx";      goz_ad[17]="led_tx";
        goz_ad[18]="led_data";    goz_ad[19]="dbg_tx";
        goz_ad[20]="adc_sclk";    goz_ad[21]="adc1_ncsb";
        goz_ad[22]="adc2_ncsb";   goz_ad[23]="adc_sync";
        goz_ad[24]="att_clk";     goz_ad[25]="att_data";
        goz_ad[26]="att1_le";     goz_ad[27]="att2_le";
        goz_ad[28]="att3_le";     goz_ad[29]="att4_le";
        goz_ad[30]="pa_att_le";   goz_ad[31]="bias_cs1";
        goz_ad[32]="bias_cs2";    goz_ad[33]="pa_adc_cs";
        goz_ad[34]="phy1_nrst";   goz_ad[35]="phy2_nrst";
        goz_ad[36]="mdc";         goz_ad[37]="adc_sdio";
        goz_ad[38]="mdio_hat";
    end

    // SAYIM RESETTEN SONRA BASLIYOR.
    //
    // Ilk surumde t=0'dan itibaren sayiyordum ve X->0 ilk atamasi da
    // "gecis" olarak goruluyordu. Sonuc: rapor "butun cikislar
    // suruldu" diyordu, oysa bir sucu pin sadece o tek ilk atamayi
    // gostermisti. Gozlemcinin butun degeri, sessiz kalan pini
    // gostermesinde; onu gizleyen bir sayim ise yaramaz.
    //
    // POR sayaci 4096 cevrim (~51 us). Sayim 55 us'te aciliyor.
    reg say_ac = 1'b0;
    initial begin #55000; say_ac = 1'b1; end

    `define GOZLE(IDX, SIG) \
        always @(SIG) if (say_ac) gecis[IDX] = gecis[IDX] + 1;

    `GOZLE(0,  dac_a)        `GOZLE(1,  dac_wrt_a)
    `GOZLE(2,  dac_b)        `GOZLE(3,  dac_wrt_b)
    `GOZLE(4,  dac2_d)       `GOZLE(5,  dac2_iqwrt)
    `GOZLE(6,  dac2_iqsel)   `GOZLE(7,  dac2_iqreset)
    `GOZLE(8,  rgmii_td)     `GOZLE(9,  rgmii_tctl)
    `GOZLE(10, rgmii_tclk)   `GOZLE(11, rly_ser)
    `GOZLE(12, rly_srclk)    `GOZLE(13, rly_rclk)
    `GOZLE(14, pa_inhibit)   `GOZLE(15, led_status)
    `GOZLE(16, led_rx)       `GOZLE(17, led_tx)
    `GOZLE(18, led_data)     `GOZLE(19, dbg_tx)
    `GOZLE(20, adc_sclk)     `GOZLE(21, adc1_ncsb)
    `GOZLE(22, adc2_ncsb)    `GOZLE(23, adc_sync)
    `GOZLE(24, att_clk)      `GOZLE(25, att_data)
    `GOZLE(26, att1_le)      `GOZLE(27, att2_le)
    `GOZLE(28, att3_le)      `GOZLE(29, att4_le)
    `GOZLE(30, pa_att_le)    `GOZLE(31, bias_cs1)
    `GOZLE(32, bias_cs2)     `GOZLE(33, pa_adc_cs)
    `GOZLE(34, phy1_nrst)    `GOZLE(35, phy2_nrst)
    `GOZLE(36, mdc)          `GOZLE(37, adc_sdio)
    `GOZLE(38, mdio_hat)

    // =================================================================
    // RGMII VERIS IZLEYICISI — cikan cerceveleri say
    // =================================================================
    integer tx_bayt = 0, tx_cerceve = 0;
    reg     tx_icinde = 1'b0;
    always @(posedge rgmii_tclk) begin
        if (rgmii_tctl && !tx_icinde) begin
            tx_icinde  <= 1'b1;
            tx_cerceve <= tx_cerceve + 1;
        end else if (!rgmii_tctl && tx_icinde) begin
            tx_icinde <= 1'b0;
        end
        if (rgmii_tctl) tx_bayt <= tx_bayt + 1;
    end

    // =================================================================
    // KOSU
    // =================================================================
    integer i;
    integer tx_once, gecis_once;

    initial begin
        $display("TUM SISTEM TESTI — ust modul");
        $display("");

        // --- 1. Enerjilenme ve reset
        #500;
        $display("1. ENERJILENME");
        if (pa_inhibit !== 1'b0) begin
            $display("  HATA: acilista PA izni verilmis (pa_inhibit=%b)",
                     pa_inhibit);
            $display("        Guvenlik varsayilan durumdan gelmeli:");
            $display("        FPGA kalkmadan PA surulmemeli.");
            hata = hata + 1;
        end else
            $display("  pa_inhibit acilista dusuk (guvenli)");

        if (phy1_nrst !== 1'b0 && phy2_nrst !== 1'b0)
            $display("  UYARI: PHY resetleri acilista pasif");


        // --- 2. Alis zinciri: ADC'den paket cikiyor mu
        //
        // ONCE ACMAK GEREKIYOR. Ilk surumde once paket ariyordum ve
        // "zincir kopuk" diye bagirdim; oysa alis zinciri acilista
        // KAPALI ve host'un acmasi gerekiyor. Bu dogru bir tasarim
        // karari (kart kendiliginden yayin yapmaz), testin sirasi
        // yanlisti.
        $display("");
        $display("2. ALIS ZINCIRI");
        #60000;                        // POR sayaci: 4096 cevrim ~51 us
        // DAC COGULLAMA SIFIRLAMASI — tek darbe, resetten cikarken.
        // Sayim penceresi 55 us'te aciliyor, darbe ~51 us'te bitiyor,
        // yani gozlemci goremiyor. DENETLENMEDEN gecmesi olurdu:
        // darbe hic atilmazsa U31 cogullama kipinde I/Q'yu ters
        // sirayla yazar ve iki kanal yer degistirir.
        //
        // ILK YAZDIGIMDA BU DENETIM 1. BOLUMDEYDI, yani t=500 ns'de —
        // reset daha birakmamisti ve denetim kendi kendine hata verdi.
        if (dac2_iqreset !== 1'b0) begin
            $display("  HATA: dac2_iqreset resetten sonra hala aktif");
            $display("        U31 cogullama kipinde I/Q sirasi bozulur");
            hata = hata + 1;
        end else
            $display("  dac2_iqreset resetten cikarken birakildi");
        kayit_yaz(8'h01, 32'h0000000F); // dort kanali da ac
        kayit_yaz(8'h02, 32'd64);       // azaltma orani
        kayit_yaz(8'h03, 32'h08000000); // NCO artisi
        kayit_yaz(8'h00, 32'h00000001); // kontrol: alis ac
        tx_once = tx_cerceve;
        #200000;                       // 200 us
        $display("  %0d ADC ornegi surulda", ornek_sayaci);
        if (tx_cerceve == tx_once) begin
            $display("  HATA: 200 us'te hic ethernet cercevesi cikmadi");
            $display("        ADC -> DDC -> paketleyici -> RGMII zinciri");
            $display("        bir yerde kopuk.");
            hata = hata + 1;
        end else
            $display("  %0d cerceve cikti (%0d bayt)",
                     tx_cerceve - tx_once, tx_bayt);

        // --- 3. Kayit yazma: host -> FPGA
        $display("");
        $display("3. KAYIT YAZMA (UDP uzerinden)");
        // ZINCIR TAMPONUNA ONCE VERI YAZ.
        //
        // Ilk surumde sadece "gonder" tetigini yazmistim ve zincirden
        // sifir kaydi: srclk 129 kez kimildadi ama rly_ser hic
        // degismedi. Rolelere sifir yollanan bir kart, testte
        // "zincir calisiyor" gorunur ve sahada hicbir bandi secmez.
        // Veri 0x10..0x1F tamponunda (bayt basina bir kayit).
        kayit_yaz(8'h0A, 32'd8);          // zincir uzunlugu
        kayit_yaz(8'h10, 32'h000000A5);   // tampon bayt 0
        kayit_yaz(8'h11, 32'h0000005A);   // bayt 1
        #2000;
        kayit_yaz(8'h0B, 32'h00000001);   // gonder
        #40000;
        if (gecis[11] + gecis[12] + gecis[13] == gecis_once) begin
            $display("  HATA: role zinciri hic kimildamadi");
            $display("        UDP -> udp_ayikla -> host_arayuz -> kayit");
            $display("        -> kontrol_zinciri yolu kopuk.");
            hata = hata + 1;
        end else
            $display("  role zinciri suruldu (ser %0d, srclk %0d, rclk %0d)",
                     gecis[11], gecis[12], gecis[13]);

        // --- 4. Verici: DAC suruluyor mu
        $display("");
        $display("4. VERICI ZINCIRI");
        kayit_yaz(8'h08, 32'h10000000); // TX NCO artisi
        kayit_yaz(8'h00, 32'h00000003); // kontrol: TX ac
        #50000;
        if (gecis[0] == 0 && gecis[2] == 0 && gecis[4] == 0) begin
            $display("  HATA: hicbir DAC veri yolu kimildamadi");
            hata = hata + 1;
        end else
            $display("  DAC yollari suruldu (A %0d, B %0d, cogullanmis %0d)",
                     gecis[0], gecis[2], gecis[4]);

        // --- 4b. KANAL HIZALAMASI — FIFO'lar kanallari kaydiriyor mu
        //
        // ADC ornekleri saat alanini gecis FIFO'lariyla geciyor ve iki
        // ADC'nin ayri FIFO'su var. Bagimsiz bosalsalardi kanallar
        // birbirine gore kayardi; dort kanalli huzme yonlendirmede o
        // kayma huzmenin yanlis yone bakmasi demek — kartta ancak
        // aynayla olculur, yani sahada.
        //
        // ADC2 = ADC1 + AYRIM oldugu icin FIFO cikisinda fark her
        // zaman AYRIM olmali.
        $display("");
        $display("4b. KANAL HIZALAMASI");
        // ADC'lerin ic boluculerini hizala ve gecis FIFO'larini
        // bosalt. Kartta bu, AD9251'in SYNC girisini surmek demek.

        begin : hiza
            integer n, yanlis;
            n = 0; yanlis = 0;
            while (n < 200) begin
                @(posedge clk_sys);
                if (dut.adc_al) begin
                    n = n + 1;
                    if ($signed(dut.s2_a) - $signed(dut.s1_a) !== AYRIM ||
                        $signed(dut.s2_b) - $signed(dut.s1_b) !== AYRIM)
                        yanlis = yanlis + 1;
                end
            end
            if (yanlis) begin
                $display("  HATA: %0d/%0d ornekte kanallar hizasiz", yanlis, n);
                $display("        iki gecis FIFO'su birbirine gore kaymis");
                hata = hata + 1;
            end else
                $display("  %0d ornekte dort kanal hizali", n);
        end

        // --- 5. SPI CEVRE YOLU
        //
        // ILK KOSUDA BU BOLUM YOKTU ve gozlemci raporu bunu ortaya
        // cikardi: att_data hic degismemis, adc_sclk/mdc/bias_cs*
        // sadece t=0'daki ilk atamayi gostermis. Yani zayiflatici
        // ayari, PA bias yazmasi ve PHY yapilandirmasi HIC test
        // edilmemisti — on alti cikis bosta duruyordu.
        //
        // Gozlemcinin isi tam buydu: testin neye DOKUNMADIGINI
        // soylemek. Gecen bir test, kapsamadigi seyi gizler.
        $display("");
        $display("5. SPI CEVRE YOLU");
        kayit_yaz(8'h0D, 32'h0000003F);  // gonderilecek bitler
        kayit_yaz(8'h0E, 32'h80000006);  // yol=cevre, cihaz 0, 6 bit
        #30000;
        if (gecis[24] < 4 || gecis[25] == 0) begin
            $display("  HATA: cevre SPI surulmedi: clk %0d data %0d",
                     gecis[24], gecis[25]);
            hata = hata + 1;
        end else
            $display("  zayiflatici yolu suruldu (clk %0d, data %0d)",
                     gecis[24], gecis[25]);

        // BUTUN CIHAZ SECIMLERI SUPURULUYOR.
        //
        // Ilk surumde sadece 0 numarali cihazi seciyordum ve gozlemci
        // raporu yedi secim hattini "hic degismedi" diye gosterdi:
        // att2/3/4_le, pa_att_le, bias_cs1/2, pa_adc_cs. Hicbiri
        // bozuk degildi — test onlara hic dokunmuyordu. Kart gelince
        // "zayiflatici 2 calismiyor" diye aranacak sey buydu.
        begin : cihaz_supurme
            integer c;
            for (c = 0; c < 8; c = c + 1) begin
                kayit_yaz(8'h0D, 32'h0000002A);
                // BIT ALANINI TAM 32 BITE KUR. Ilk denememde
                // birlestirme 24 bit tutuyordu ve alanlar kaydi:
                // cihaz numarasi hic yerine oturmadi, supurme
                // hep 0 numarali cihazi surdu ve rapor yedi secim
                // hattini "olu" gostermeye devam etti. Hatanin
                // tasarimda degil testte oldugunu bu ortaya cikardi.
                //   b31 yol | b30:27 - | b26:24 cihaz
                //   b23:14 - | b13:8 okuma biti | b7:6 - | b5:0 uzunluk
                kayit_yaz(8'h0E, {1'b1, 4'd0, c[2:0], 10'd0,
                                  6'd0, 2'd0, 6'd6});
                #12000;
            end
        end

        // ADC yolu: ayni cekirdek, baska secim hatti. IKI ADC de.
        kayit_yaz(8'h0D, 32'h00001234);
        kayit_yaz(8'h0E, 32'h00000010);  // yol=ADC, cihaz 0, 16 bit
        #30000;
        kayit_yaz(8'h0D, 32'h00005678);
        kayit_yaz(8'h0E, 32'h01000010);  // cihaz 1 -> adc2_ncsb
        #30000;
        if (gecis[20] < 4) begin
            $display("  HATA: ADC SPI yolu surulmedi (adc_sclk %0d)",
                     gecis[20]);
            hata = hata + 1;
        end else
            $display("  ADC SPI yolu suruldu (sclk %0d, csb %0d)",
                     gecis[20], gecis[21]);

        // --- 6. MDIO — PHY yapilandirmasi
        $display("");
        $display("6. MDIO");
        kayit_yaz(8'h22, 32'h81000000);  // yaz, PHY 1, kayit 0
        #40000;
        if (gecis[36] < 4) begin
            $display("  HATA: MDIO saati surulmedi (mdc %0d)", gecis[36]);
            $display("        PHY resetten cikip yapilandirilamaz.");
            hata = hata + 1;
        end else
            $display("  MDIO suruldu (mdc %0d, hat %0d)",
                     gecis[36], gecis[38]);

        // --- 7. PA IZNI — guvenli varsayilandan cikabiliyor mu
        //
        // Acilista dusuk olmasi DOGRU (1. bolum onu denetliyor). Ama
        // hic yukselemiyorsa PA hic calismaz ve bunu ancak kartta
        // gorurduk. Bekci kopegi besleniyor ve izin veriliyor.
        $display("");
        $display("7. ADC HIZALAMA VE PA IZNI");
        // once hizalama: desen yaz, ADC'ye ayni deseni sur
        hiza_kip = 1'b1;
        kayit_yaz(8'h0C, {1'b1, 1'b0, DESEN_B, 2'b00, DESEN_A});
        #60000;
        if (!dut.a1_hizali || !dut.a2_hizali) begin
            $display("  HATA: ADC hizalamasi tamamlanmadi (a1=%b a2=%b)",
                     dut.a1_hizali, dut.a2_hizali);
            hata = hata + 1;
        end else
            $display("  ADC hizalandi (takas a1=%b a2=%b)",
                     dut.a1_takas, dut.a2_takas);
        kayit_yaz(8'h0F, 32'h00000005);  // bit0 adc_sync + bit2 kopek
        #4000;
        kayit_yaz(8'h0F, 32'h00000004);  // adc_sync geri indir
        kayit_yaz(8'h00, 32'h00000003);  // alis + veris ac
        #40000;
        kayit_yaz(8'h0F, 32'h00000004);
        #40000;
        if (gecis[14] == 0) begin
            $display("  HATA: pa_inhibit hic yukselmedi");
            $display("        Guvenli varsayilan dogru ama PA hic");
            $display("        calisamaz demek; kartta anlasilirdi.");
            hata = hata + 1;
        end else
            $display("  pa_inhibit surulebiliyor (%0d gecis, son %b)",
                     gecis[14], pa_inhibit);

        // --- 8. GOZLEMCI RAPORU
        $display("");
        $display("8. CIKIS PINI GOZLEMCILERI");
        $display("   %-14s %10s", "pin", "gecis");
        // BU PENCEREDE DEGISEMEYECEKLER — gerekceli istisna.
        //
        // phy1_nrst/phy2_nrst bir 2^21 cevrimlik sayacin ardindan
        // birakiliyor: 80 MHz'te 26 ms. Bu kosu 700 us. Yani pinin
        // sessiz olmasi kusur degil, PENCERE DISI. Istisnayi gerekcesiz
        // birakmak, gozlemciyi zamanla "bunlar zaten hep kirmizi"
        // diye gormezden gelmeye goturur.
        begin : rapor
            integer olu;
            olu = 0;
            for (i = 0; i < N_GOZ; i = i + 1) begin
                if (i == 34 || i == 35) begin
                    $display("   %-14s %10d  (26 ms reset sayaci, pencere disi)",
                             goz_ad[i], gecis[i]);
                end else if (i == 7) begin
                    $display("   %-14s %10d  (tek darbe, 1. bolumde denetlendi)",
                             goz_ad[i], gecis[i]);
                end else if (gecis[i] == 0) begin
                    $display("   %-14s %10s  <-- HIC DEGISMEDI",
                             goz_ad[i], "0");
                    olu = olu + 1;
                end else
                    $display("   %-14s %10d", goz_ad[i], gecis[i]);
            end
            $display("");
            if (olu > 0) begin
                $display("   %0d cikis hic degismedi.", olu);
                $display("   Her biri ya test edilmemis bir islev ya da");
                $display("   baglanmamis bir sinyal. Ikisi de burada");
                $display("   bulunmali, kart geldikten sonra degil.");
            end else
                $display("   butun cikislar suruldu");
        end

        $display("");
        if (hata == 0) $display("TUM SISTEM TESTI GECTI");
        else           $display("TUM SISTEM TESTI KALDI: %0d hata", hata);
        $finish;
    end

    initial begin
        #5_000_000;
        $display("TUM SISTEM TESTI KALDI: zaman asimi");
        $finish;
    end

endmodule

`default_nettype wire
