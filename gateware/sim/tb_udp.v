// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// udp_ayikla testi — rgmii_alis ile BIRLIKTE, gercek bir UDP paketi.
//
// Iki modulu ayri ayri test etmek buradaki asil riski kacirirdi:
// ikisinin ARASINDAKI sozlesme. rgmii_alis FCS'i de bayt akisina
// koyuyor (CRC'yi onunla dogruluyor), udp_ayikla ise onu yuktan
// dusmek zorunda. Bu ikisi ayri test edilse ikisi de "gecer" ve
// host dort cop bayt gorur.
//
// OLCULEN UC SEY:
//   1 Saglam paketin yuku BIREBIR cikiyor mu.
//   2 BOZUK paketten HIC bayt cikmiyor mu. Bu, modulun varlik
//     sebebi: bu kartta kayit yazmak PA iznini ve gate biasini
//     suruyor, yani dogrulanmamis bir paketten yazmak donanim
//     oldurur.
//   3 BASKA PORTA gelen paket yok sayiliyor mu.

`timescale 1ns/1ps
`default_nettype none

module tb_udp;

    reg clk = 1'b0;
    always #4 clk = ~clk;
    reg rst = 1'b1;

    reg [3:0] rd_yuk = 0, rd_dus = 0;
    reg       rctl_yuk = 0, rctl_dus = 0;

    wire [7:0] rb;
    wire       rbv, rson, rcrc, rhata;

    rgmii_alis u_al (
        .clk(clk), .rst(rst),
        .rd_yuk(rd_yuk), .rd_dus(rd_dus),
        .rctl_yuk(rctl_yuk), .rctl_dus(rctl_dus),
        .bayt(rb), .bayt_gecerli(rbv),
        .cerceve_sonu(rson), .crc_dogru(rcrc), .hata(rhata));

    wire [7:0] yb;
    wire       ybv;

    udp_ayikla #(.PORT(16'd5001)) u_udp (
        .clk(clk), .rst(rst),
        .bayt(rb), .bayt_gecerli(rbv),
        .cerceve_sonu(rson), .crc_dogru(rcrc),
        .yuk_bayt(yb), .yuk_gecerli(ybv));

    // ---------------------------------------------------------------
    function [31:0] crc_bayt;
        input [31:0] c; input [7:0] d;
        integer i; reg [31:0] x;
        begin
            x = c ^ {24'd0, d};
            for (i = 0; i < 8; i = i + 1)
                x = x[0] ? ((x >> 1) ^ 32'hEDB88320) : (x >> 1);
            crc_bayt = x;
        end
    endfunction

    // yuk: iki kayit yazma cercevesi (A5 adr d3 d2 d1 d0 xor)
    localparam YUK = 14;
    reg [7:0] yuk [0:YUK-1];

    localparam CER = 14 + 20 + 8 + YUK;      // FCS haric
    reg [7:0] cer [0:CER+3];

    reg [7:0] alinan [0:63];
    integer   alinan_n;

    integer i, hata_say = 0;
    reg [31:0] c;

    task bayt_ver(input [7:0] d, input gecerli);
        begin
            @(negedge clk);
            rd_yuk = d[3:0]; rd_dus = d[7:4];
            rctl_yuk = gecerli; rctl_dus = gecerli;   // RXERR = 0
        end
    endtask

    task bosluk(input integer n);
        integer k;
        begin for (k = 0; k < n; k = k + 1) bayt_ver(8'h00, 1'b0); end
    endtask

    task cerceve_ver(input integer boz);
        integer k;
        begin
            for (k = 0; k < 7; k = k + 1) bayt_ver(8'h55, 1'b1);
            bayt_ver(8'hD5, 1'b1);
            for (k = 0; k < CER + 4; k = k + 1)
                bayt_ver(cer[k] ^ ((k == boz) ? 8'h01 : 8'h00), 1'b1);
            bosluk(30);              // bosaltma bitsin
        end
    endtask

    task cerceve_kur(input [15:0] port);
        integer k;
        begin
            for (k = 0; k < 6; k = k + 1) cer[k]      = 8'h02;  // hedef MAC
            for (k = 0; k < 6; k = k + 1) cer[6+k]    = 8'h06;  // kaynak MAC
            cer[12] = 8'h08; cer[13] = 8'h00;                   // IPv4
            cer[14] = 8'h45;                                    // surum4/IHL5
            cer[15] = 8'h00;
            cer[16] = 8'h00; cer[17] = 8'd28 + YUK;             // toplam uzunluk
            for (k = 18; k < 23; k = k + 1) cer[k] = 8'h00;
            cer[23] = 8'd17;                                    // UDP
            cer[24] = 8'h00; cer[25] = 8'h00;                   // baslik saglamasi
            for (k = 26; k < 34; k = k + 1) cer[k] = 8'h0A;     // IP adresleri
            cer[34] = 8'h13; cer[35] = 8'h88;                   // kaynak port
            cer[36] = port[15:8]; cer[37] = port[7:0];          // hedef port
            cer[38] = 8'h00; cer[39] = 8'd8 + YUK;              // UDP uzunlugu
            cer[40] = 8'h00; cer[41] = 8'h00;                   // UDP saglamasi
            for (k = 0; k < YUK; k = k + 1) cer[42+k] = yuk[k];
            // FCS
            c = 32'hFFFFFFFF;
            for (k = 0; k < CER; k = k + 1) c = crc_bayt(c, cer[k]);
            c = ~c;
            cer[CER+0] = c[7:0];   cer[CER+1] = c[15:8];
            cer[CER+2] = c[23:16]; cer[CER+3] = c[31:24];
        end
    endtask

    always @(posedge clk)
        if (!rst && ybv) begin
            alinan[alinan_n] = yb;
            alinan_n = alinan_n + 1;
        end

    initial begin
        $display("udp_ayikla testi (rgmii_alis ile birlikte)");
        // iki kayit yazma cercevesi
        yuk[0]=8'hA5; yuk[1]=8'h03; yuk[2]=8'h12; yuk[3]=8'h34;
        yuk[4]=8'h56; yuk[5]=8'h78; yuk[6]=8'h03^8'h12^8'h34^8'h56^8'h78;
        yuk[7]=8'hA5; yuk[8]=8'h09; yuk[9]=8'h00; yuk[10]=8'h00;
        yuk[11]=8'h00; yuk[12]=8'h40; yuk[13]=8'h09^8'h40;

        repeat (4) @(posedge clk); #1; rst = 0;
        bosluk(4);

        // ---- 1. saglam paket, dogru port ----
        cerceve_kur(16'd5001);
        alinan_n = 0;
        cerceve_ver(-1);
        if (alinan_n != YUK) begin
            $display("  HATA: %0d bayt yuk cikti, %0d bekleniyordu", alinan_n, YUK);
            $display("        (%0d ise FCS dusulmemis)", YUK + 4);
            hata_say = hata_say + 1;
        end else begin
            begin : icerik
                integer y; y = 0;
                for (i = 0; i < YUK; i = i + 1)
                    if (alinan[i] !== yuk[i]) y = y + 1;
                if (y) begin
                    $display("  HATA: %0d yuk bayti yanlis", y);
                    hata_say = hata_say + 1;
                end else $display("  yuk birebir cikti (%0d bayt, FCS dusuldu)", YUK);
            end
        end

        // ---- 2. BOZUK paket: hic bayt cikmamali ----
        alinan_n = 0;
        cerceve_ver(45);             // yukun icinden bir bayti boz
        if (alinan_n != 0) begin
            $display("  HATA: bozuk paketten %0d bayt gecti", alinan_n);
            $display("        (dogrulanmamis kayit yazmasi = PA/bias riski)");
            hata_say = hata_say + 1;
        end else $display("  bozuk paketten hicbir sey gecmedi");

        // ---- 3. baska port ----
        cerceve_kur(16'd9999);
        alinan_n = 0;
        cerceve_ver(-1);
        if (alinan_n != 0) begin
            $display("  HATA: yanlis porta gelen paketten %0d bayt gecti", alinan_n);
            hata_say = hata_say + 1;
        end else $display("  yanlis port yok sayildi");

        // ---- 4. dogru port yine calisiyor mu (durum takilmadi mi) ----
        cerceve_kur(16'd5001);
        alinan_n = 0;
        cerceve_ver(-1);
        if (alinan_n != YUK) begin
            $display("  HATA: ucuncu pakette %0d bayt (durum takildi)", alinan_n);
            hata_say = hata_say + 1;
        end else $display("  arka arkaya paketler calisiyor");

        if (hata_say == 0) $display("udp_ayikla testi GECTI");
        else               $display("udp_ayikla testi KALDI: %0d hata", hata_say);
        $finish;
    end

    initial begin
        #500_000;
        $display("udp_ayikla testi KALDI: zaman asimi");
        $finish;
    end

endmodule

`default_nettype wire
