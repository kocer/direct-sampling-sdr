// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// RGMII veris testi — cerceve yapisi ve CRC.
//
// Nibble akisini bayta geri cevirip cerceveyi cozuyoruz. Uc sey
// olculuyor:
//
// 1 YAPI. Onsoz, SFD, MAC'ler, EtherType, IP surumu, protokol.
//   Bir bayt kayarsa alici cerceveyi atar ve kartta hicbir belirti
//   olmaz.
//
// 2 IP SAGLAMASI. Basligin 16 bitlik toplami 0xFFFF vermeli.
//   Yanlissa yonlendirici cerceveyi duser.
//
// 3 CRC-32. Cercevenin kendi hesabiyla bagimsiz olarak yeniden
//   hesaplayip karsilastiriyoruz. Yanlis CRC = sessiz kayip.
`timescale 1ns/1ps
`default_nettype none
module tb_rgmii;
    reg clk=0, rst=1; always #4 clk=~clk;      // 125 MHz
    reg gv=0, vson=0;
    wire hazir;

    // ---------------------------------------------------------------
    // YUK SAYAN BIR DIZI, SABIT DEGIL.
    //
    // Once yuk hep 0xA0 idi (dongu bir kez donuyor ama cerceveye hep
    // ayni deger dusuyordu). Sabit yukte BIR BAYT KAYMASI GORUNMEZ:
    // modul yanlis bayti alsa bile cikti ayni. Tam da bu tezgahin
    // yakalamasi gereken hata gorunmez olur.
    //
    // Kaynak gercek bir FIFO gibi davraniyor: k. bayti sunuyor,
    // DUT veri_hazir'i kaldirdiginda ilerliyor.
    reg [7:0] yuk_no = 8'd0;
    wire [7:0] veri = 8'hA0 + yuk_no;
    always @(posedge clk)
        if (rst)        yuk_no <= 8'd0;
        else if (hazir) yuk_no <= yuk_no + 8'd1;
    wire [3:0] td_yuk, td_dus; wire tctl_yuk, tctl_dus;

    rgmii_veris dut(.clk(clk),.rst(rst),.veri(veri),.veri_gecerli(gv),
        .veri_son(vson),.veri_hazir(hazir),.yuk_uzunluk(16'd8),
        .rgmii_td_yuk(td_yuk), .rgmii_td_dus(td_dus),
        .rgmii_tctl_yuk(tctl_yuk), .rgmii_tctl_dus(tctl_dus));

    // CEVRIM BASINA BIR BAYT.
    // Once iki cevrimden bir bayt toplaniyordu, cunku modul nibble
    // nibble suruyordu — o SDR idi ve PHY'nin gordugu sey degildi.
    // Simdi alt nibble yukselen, ust nibble dusen kenara gidiyor
    // (ODDR ust modulde), yani bir cevrim = bir bayt.
    reg [7:0] cerceve [0:255];
    integer   n=0;
    reg       basladi=0, bitti=0;
    integer   hata=0, k;
    // ILK CERCEVEDE DUR.
    // gv surekli acik kalinca modul art arda cerceve gonderiyor ve
    // tampon doluyordu; FCS'yi n-4'te ararken sonraki cercevenin
    // onsozunu buluyordum (d5555555). Cercevenin sonu, tctl'nin
    // ilk kez dusmesi.
    always @(posedge clk) begin
        if (!bitti) begin
            if (tctl_yuk) begin
                basladi <= 1;
                if (n < 256) begin cerceve[n] = {td_dus, td_yuk}; n = n + 1; end
                // TXCTL'in dusen kenari TXEN xor TXERR; hata yokken
                // yukselenle ayni olmali.
                if (tctl_dus !== tctl_yuk) begin
                    $display("  HATA: tctl_dus=%b, tctl_yuk=%b — TXERR bildirildi",
                             tctl_dus, tctl_yuk);
                    hata = hata + 1;
                end
            end else if (basladi) bitti <= 1;
        end
    end

    reg [31:0] c;
    reg [31:0] hesap;
    reg [31:0] gelen;
    integer    i;

    function [31:0] crc_bayt(input [31:0] c0, input [7:0] d);
        integer j; reg [31:0] t;
        begin
            t = c0 ^ {24'd0, d};
            for (j=0;j<8;j=j+1) t = t[0] ? ((t>>1)^32'hEDB88320) : (t>>1);
            crc_bayt = t;
        end
    endfunction

    initial begin
        $display("RGMII veris testi");
        #100; @(posedge clk); #1; rst=0;
        gv = 1;
        for (k=0;k<600;k=k+1) @(posedge clk);
        gv = 0;
        for (k=0;k<200;k=k+1) @(posedge clk);

        $display("  toplanan bayt: %0d", n);
        // 8 onsoz + 14 eth + 20 ip + 8 udp + 8 veri + 4 fcs = 62
        if (n < 62) begin
            $display("  HATA: cerceve kisa, %0d bayt", n); hata=hata+1;
        end

        // yuk: 8 + 14 + 20 + 8 = 50. bayti A0'dan baslayarak sayilmali
        for (i=0;i<8;i=i+1) begin
            if (cerceve[50+i] !== 8'hA0 + i[7:0]) begin
                $display("  HATA: yuk[%0d] = %02h, beklenen %02h",
                         i, cerceve[50+i], 8'hA0 + i[7:0]);
                hata = hata + 1;
            end
        end
        if (hata == 0) $display("  yuk baytlari sirasiyla dogru");

        if (cerceve[0]!==8'h55 || cerceve[6]!==8'h55 || cerceve[7]!==8'hD5) begin
            $display("  HATA: onsoz/SFD  %02x..%02x %02x",
                     cerceve[0], cerceve[6], cerceve[7]); hata=hata+1;
        end else $display("  onsoz ve SFD dogru");

        if (cerceve[20]!==8'h08 || cerceve[21]!==8'h00) begin
            $display("  HATA: EtherType %02x%02x", cerceve[20], cerceve[21]);
            hata=hata+1;
        end else $display("  EtherType IPv4");

        if (cerceve[22]!==8'h45) begin
            $display("  HATA: IP surum/uzunluk %02x", cerceve[22]); hata=hata+1;
        end
        if (cerceve[31]!==8'h11) begin
            $display("  HATA: protokol %02x, UDP (0x11) olmali", cerceve[31]);
            hata=hata+1;
        end else $display("  IPv4 basligi ve UDP protokolu dogru");

        // IP saglamasi: 20 baytin 16 bitlik toplami 0xFFFF olmali
        c = 0;
        for (i=22;i<42;i=i+2) c = c + {cerceve[i], cerceve[i+1]};
        c = (c & 32'hFFFF) + (c >> 16);
        c = (c & 32'hFFFF) + (c >> 16);
        if (c[15:0] !== 16'hFFFF) begin
            $display("  HATA: IP saglamasi %04x, FFFF olmali", c[15:0]);
            hata=hata+1;
        end else $display("  IP saglama toplami dogru");

        // CRC: SFD'den sonraki her sey, FCS haric
        hesap = 32'hFFFFFFFF;
        for (i=8;i<n-4;i=i+1) hesap = crc_bayt(hesap, cerceve[i]);
        hesap = ~hesap;
        gelen = {cerceve[n-1], cerceve[n-2], cerceve[n-3], cerceve[n-4]};
        if (hesap !== gelen) begin
            $display("  HATA: CRC hesap %08x, cercevede %08x", hesap, gelen);
            hata=hata+1;
        end else $display("  CRC-32 dogru (%08x)", gelen);

        if (hata) begin
            $write("  cerceve:");
            for (i=0;i<n;i=i+1) begin
                if (i%16==0) $write("\n   %3d:", i);
                $write(" %02x", cerceve[i]);
            end
            $display("");
        end
        if (hata==0) $display("RGMII veris testi GECTI");
        else begin $display("RGMII veris testi KALDI: %0d hata", hata); $fatal; end
        $finish;
    end
endmodule
`default_nettype wire
