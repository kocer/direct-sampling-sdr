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
    reg [7:0] veri=0; reg gv=0, vson=0;
    wire hazir;
    wire [3:0] td; wire tctl, tclk;

    rgmii_veris dut(.clk(clk),.rst(rst),.veri(veri),.veri_gecerli(gv),
        .veri_son(vson),.veri_hazir(hazir),.yuk_uzunluk(16'd8),
        .rgmii_td(td),.rgmii_tctl(tctl),.rgmii_tclk(tclk));

    // nibble -> bayt
    reg [7:0] cerceve [0:255];
    integer   n=0;
    reg [3:0] alt;
    reg       faz=0;
    reg       basladi=0, bitti=0;
    // ILK CERCEVEDE DUR.
    // gv surekli acik kalinca modul art arda cerceve gonderiyor ve
    // tampon doluyordu; FCS'yi n-4'te ararken sonraki cercevenin
    // onsozunu buluyordum (d5555555). Cercevenin sonu, tctl'nin
    // ilk kez dusmesi.
    always @(posedge clk) begin
        if (!bitti) begin
            if (tctl) begin
                basladi <= 1;
                if (!faz) alt <= td;
                else if (n < 256) begin cerceve[n] = {td, alt}; n = n + 1; end
                faz <= ~faz;
            end else begin
                faz <= 0;
                if (basladi) bitti <= 1;
            end
        end
    end

    integer hata=0, k;
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
        veri = 8'hA0; gv = 1;
        for (k=0;k<8;k=k+1) begin
            @(posedge clk); #1;
            if (hazir) veri = 8'hA0 + k + 1;
        end
        for (k=0;k<600;k=k+1) @(posedge clk);
        gv = 0;
        for (k=0;k<200;k=k+1) @(posedge clk);

        $display("  toplanan bayt: %0d", n);
        // 8 onsoz + 14 eth + 20 ip + 8 udp + 8 veri + 4 fcs = 62
        if (n < 62) begin
            $display("  HATA: cerceve kisa, %0d bayt", n); hata=hata+1;
        end

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

        if (hata==0) $display("RGMII veris testi GECTI");
        else begin $display("RGMII veris testi KALDI: %0d hata", hata); $fatal; end
        $finish;
    end
endmodule
`default_nettype wire
