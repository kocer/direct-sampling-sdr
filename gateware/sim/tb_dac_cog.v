// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// dac_cogullu testi — karsisina AD9767 cogullanmis mod modeli.
//
// Modul kendi kendini dogrulayamaz: "IQWRT darbeledim" demek, cipin
// dogru kanala dogru degeri yazdigi anlamina gelmiyor. IQSEL yanlis
// polaritedeyse ya da veri IQWRT ile AYNI kenarda degisiyorsa dalga
// bicimi kusursuz gorunur ve iki kanal yer degistirir — huzme yanlis
// yone bakar, kartta duzeltilemez.
//
// Model AD9767 gibi davraniyor: IQWRT'nin YUKSELEN kenarinda veri
// yolunu, IQSEL'in o andaki seviyesine gore kanal 3 ya da kanal 4
// mandalina yaziyor. Ayrica kurulum suresini denetliyor.
//
// IQWRT ODDR'DAN GELIYOR: modul iki bit veriyor (yuk/dus) ve ust.v
// bunlari ODDRX1F'e baglıyor. Test burada ODDR'i modelliyor:
// saat yuksekken D0, alcakken D1.

`timescale 1ns/1ps
`default_nettype none

module tb_dac_cog;

    localparam BIT = 14;
    localparam real T_SAAT = 12.5;      // 80 MHz

    reg clk = 1'b0;
    always #6.25 clk = ~clk;
    reg rst = 1'b1;

    reg signed [BIT-1:0] ornek_i = 0, ornek_q = 0;
    reg                  gecerli = 1'b0;
    reg                  iqsel_ters = 1'b0;

    wire [BIT-1:0] dac_d;
    wire           iqwrt_yuk, iqwrt_dus, iqsel, iqreset, hazir;

    dac_cogullu #(.BIT(BIT)) dut (
        .clk(clk), .rst(rst),
        .ornek_i(ornek_i), .ornek_q(ornek_q),
        .ornek_gecerli(gecerli), .iqsel_ters(iqsel_ters),
        .dac_d(dac_d), .iqwrt_yuk(iqwrt_yuk), .iqwrt_dus(iqwrt_dus),
        .iqsel(iqsel), .iqreset(iqreset), .hazir(hazir));

    // ODDR modeli
    wire iqwrt = clk ? iqwrt_yuk : iqwrt_dus;

    // ---------------------------------------------------------------
    // AD9767 cogullanmis mod modeli
    // ---------------------------------------------------------------
    reg [BIT-1:0] mandal_i = 0, mandal_q = 0;
    integer yazma = 0;
    // KURULUM OLCUMU ZAMANLA, CEVRIM SAYARAK DEGIL.
    //
    // Once "kac cevrimdir kararli" diye bir sayac tutuyordum ve onu
    // IQWRT kenarinda okuyordum. Ikisi de ayni saat kenarinda
    // guncellendigi icin hangi degerin okunacagi belirsizdi — test
    // DUT'u degil kendi yarisini olcuyordu ve dort "ihlal" uretiyordu.
    //
    // Simdi veri son ne zaman degisti onu ZAMAN olarak tutuyoruz ve
    // IQWRT kenarinda gecen sureye bakiyoruz. Yarış yok, ustelik
    // sonuc veri sayfasiyla dogrudan karsilastirilabilir bir sayi:
    // AD9767 kurulum suresi 2.0 ns, tutma suresi 1.5 ns.
    real son_degisim = 0.0;
    real en_kisa_kurulum = 1e9;
    real en_kisa_tutma = 1e9;
    real son_yazma = -1.0;
    integer       kurulum_ihlali = 0;
    integer       tutma_ihlali = 0;
    reg           reset_gordu = 0;

    always @(dac_d) if (!rst) begin
        // TUTMA DENETIMI: veri, onceki IQWRT kenarindan en az 1.5 ns
        // sonra degismeli. Kurulumu olcup tutmayi atlamak, veriyi
        // kenardan hemen sonra degistiren bir tasarima "gecti" der.
        if (son_yazma >= 0.0) begin
            if ($realtime - son_yazma < en_kisa_tutma)
                en_kisa_tutma = $realtime - son_yazma;
            if ($realtime - son_yazma < 1.5) tutma_ihlali = tutma_ihlali + 1;
        end
        son_degisim = $realtime;
    end

    always @(posedge clk) if (iqreset) reset_gordu <= 1;

    // SIFIRLAMA SIRASINDA OLCME. rst=1 iken cikislar tanimsiz ve
    // IQRESET zaten basili — cip dinlemiyor. t=0'daki X->deger olayi
    // aksi halde sahte bir kurulum ihlali uretiyor.
    always @(posedge iqwrt) if (!rst) begin
        if ($realtime - son_degisim < en_kisa_kurulum)
            en_kisa_kurulum = $realtime - son_degisim;
        if ($realtime - son_degisim < 2.0) kurulum_ihlali = kurulum_ihlali + 1;
        if (iqsel) mandal_i <= dac_d;
        else       mandal_q <= dac_d;
        son_yazma = $realtime;
        yazma = yazma + 1;
    end

    integer hata = 0;

    task ornek_ver(input signed [BIT-1:0] i, input signed [BIT-1:0] q);
        begin
            @(posedge clk);
            while (!hazir) @(posedge clk);
            #1; ornek_i = i; ornek_q = q; gecerli = 1;
            @(posedge clk); #1; gecerli = 0;
            repeat (5) @(posedge clk);
        end
    endtask

    function [BIT-1:0] ofs(input signed [BIT-1:0] x);
        ofs = {~x[BIT-1], x[BIT-2:0]};
    endfunction

    // ---------------------------------------------------------------
    // Kabul edilen ornek cifti sayaci — VERIM olcumu icin.
    // ---------------------------------------------------------------
    integer kabul = 0;
    always @(posedge clk)
        if (!rst && hazir && gecerli) kabul = kabul + 1;

    real t0, t1;
    real kanal_msps;

    initial begin
        $display("dac_cogullu testi");
        repeat (5) @(posedge clk);
        rst = 0;
        repeat (10) @(posedge clk);

        if (!reset_gordu) begin
            $display("  HATA: IQRESET hic verilmedi — cipin ic isaretcisi");
            $display("        bizimkiyle ters baslayabilir, kanallar kalici yer degistirir");
            hata = hata + 1;
        end else $display("  IQRESET acilista verildi");

        // ---- normal ornek ----
        ornek_ver(14'sd1000, -14'sd2000);
        if (mandal_i !== ofs(14'sd1000)) begin
            $display("  HATA: kanal 3 mandali %04h, %04h olmali", mandal_i, ofs(14'sd1000));
            hata = hata + 1;
        end else $display("  kanal 3 dogru: %04h", mandal_i);
        if (mandal_q !== ofs(-14'sd2000)) begin
            $display("  HATA: kanal 4 mandali %04h, %04h olmali", mandal_q, ofs(-14'sd2000));
            hata = hata + 1;
        end else $display("  kanal 4 dogru: %04h", mandal_q);

        // ---- tam olcek uclari, ofset ikili donusumu ----
        ornek_ver(-14'sd8192, 14'sd8191);
        if (mandal_i !== 14'h0000 || mandal_q !== 14'h3FFF) begin
            $display("  HATA: uc degerler k3=%04h k4=%04h, 0000/3FFF olmali",
                     mandal_i, mandal_q);
            hata = hata + 1;
        end else $display("  ofset ikili uclari dogru (0000 / 3FFF)");

        // ---- zamanlama ----
        if (kurulum_ihlali != 0) begin
            $display("  HATA: %0d kez kurulum suresi 2.0 ns altina dustu",
                     kurulum_ihlali);
            hata = hata + 1;
        end else $display("  kurulum suresi %0.2f ns (gereken 2.0), %0d yazma",
                          en_kisa_kurulum, yazma);
        if (tutma_ihlali != 0) begin
            $display("  HATA: %0d kez tutma suresi 1.5 ns altina dustu",
                     tutma_ihlali);
            hata = hata + 1;
        end else $display("  tutma suresi %0.2f ns (gereken 1.5)", en_kisa_tutma);

        // ---- polarite bitini cevir, kanallar yer degistirmeli ----
        iqsel_ters = 1'b1;
        ornek_ver(14'sd500, 14'sd1500);
        if (mandal_q !== ofs(14'sd500) || mandal_i !== ofs(14'sd1500)) begin
            $display("  HATA: iqsel_ters=1'de kanallar degismedi (k3=%04h k4=%04h)",
                     mandal_i, mandal_q);
            hata = hata + 1;
        end else $display("  iqsel_ters kanallari degistiriyor");
        iqsel_ters = 1'b0;

        // ---------------------------------------------------------------
        // VERIM — BU TESTIN VAROLUS SEBEBI.
        //
        // Ilk surum dort evreliydi ve kanal basina 20 MSPS veriyordu,
        // ama basliginda "40 MSPS" yaziyordu. Yukaridaki testlerin
        // HICBIRI bunu yakalamiyordu: her ornek tek tek verildigi
        // icin verim hic olculmuyordu, sadece dogruluk olculuyordu.
        // Yanlis olan sayi da koddaki bir sabit degil, bir YORUMDU.
        //
        // Burasi surekli akis verip gercek ornek hizini olcuyor.
        // 40 MSPS bekleniyor (80 MHz saatte iki evre).
        // ---------------------------------------------------------------
        @(posedge clk); #1; gecerli = 1;
        ornek_i = 14'sd100; ornek_q = -14'sd100;
        repeat (20) @(posedge clk);       // boru dolsun
        kabul = 0; t0 = $realtime;
        repeat (2000) @(posedge clk);
        t1 = $realtime; #1; gecerli = 0;

        kanal_msps = kabul * 1000.0 / (t1 - t0);   // ornek/us = MSPS
        $display("  surekli akis: %0d ornek cifti / %0.0f ns -> kanal basina %0.1f MSPS",
                 kabul, t1 - t0, kanal_msps);
        if (kanal_msps < 39.0) begin
            $display("  HATA: kanal basina %0.1f MSPS, en az 39 olmali", kanal_msps);
            $display("        (20 civariysa modul dort evreye dusmus demektir)");
            hata = hata + 1;
        end else
            $display("  verim yeterli: Nyquist %0.1f MHz, 17 m bandini kapsiyor",
                     kanal_msps / 2.0);

        if (hata == 0) $display("dac_cogullu testi GECTI");
        else           $display("dac_cogullu testi KALDI: %0d hata", hata);
        $finish;
    end

    initial begin
        #500_000;
        $display("dac_cogullu testi KALDI: zaman asimi");
        $finish;
    end

endmodule

`default_nettype wire
