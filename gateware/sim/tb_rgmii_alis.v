// rgmii_alis testi — gercek bir cerceve, gercek bir FCS.
//
// Modulun tek isi PHY'den gelen nibble akisini bayta cevirip
// cercevenin saglam olup olmadigini soylemek. O yuzden test tam
// bunu olcuyor:
//
//   1 BAYTLAR DOGRU CIKIYOR MU. Nibble sirasi ters olsaydi (RGMII'de
//     once ALT nibble geliyor) her bayt yer degistirirdi ve belirtisi
//     "her cerceve bozuk" olurdu — yani CRC hatasi gibi gorunurdu ve
//     insan CRC'de hata arardi.
//
//   2 SAGLAM CERCEVEYE "DOGRU" DIYOR MU.
//   3 BOZUK CERCEVEYE "YANLIS" DIYOR MU. Ucuncusu olmadan ikincisi
//     bir sey ispatlamaz: crc_dogru'yu sabit 1'e baglasak da test
//     gecerdi.
//
// FCS test tezgahinda hesaplaniyor, elle yazilmiyor: elle yazilan bir
// sabit, CRC fonksiyonu degistiginde sessizce yanlis olur.

`timescale 1ns/1ps
`default_nettype none

module tb_rgmii_alis;

    reg clk = 1'b0;
    always #4 clk = ~clk;            // 125 MHz
    reg rst = 1'b1;

    reg [3:0] rd_yuk = 4'd0, rd_dus = 4'd0;
    reg       rctl_yuk = 1'b0, rctl_dus = 1'b0;

    wire [7:0] bayt;
    wire       bayt_gecerli, cerceve_sonu, crc_dogru, hata;

    rgmii_alis dut (
        .clk(clk), .rst(rst),
        .rd_yuk(rd_yuk), .rd_dus(rd_dus),
        .rctl_yuk(rctl_yuk), .rctl_dus(rctl_dus),
        .bayt(bayt), .bayt_gecerli(bayt_gecerli),
        .cerceve_sonu(cerceve_sonu), .crc_dogru(crc_dogru), .hata(hata));

    // ---------------------------------------------------------------
    // CRC — RTL ile ayni fonksiyon (test tezgahinin kendi kopyasi)
    // ---------------------------------------------------------------
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

    localparam N = 46;               // yuk uzunlugu
    reg [7:0] gonderilen [0:N+3];    // yuk + 4 bayt FCS
    reg [7:0] alinan [0:255];
    integer   alinan_n;

    integer i, hata_say = 0;
    reg [31:0] c;

    // bir bayti nibble'lara bolup ver
    task bayt_ver(input [7:0] d, input gecerli, input err);
        begin
            @(negedge clk);
            rd_yuk   = d[3:0];       // ONCE ALT nibble
            rd_dus   = d[7:4];
            rctl_yuk = gecerli;
            rctl_dus = err ^ gecerli;
        end
    endtask

    task bosluk(input integer n);
        integer k;
        begin
            for (k = 0; k < n; k = k + 1) bayt_ver(8'h00, 1'b0, 1'b0);
        end
    endtask

    // onsoz + SFD + govde
    task cerceve_ver(input integer bozuk_index);
        integer k;
        begin
            for (k = 0; k < 7; k = k + 1) bayt_ver(8'h55, 1'b1, 1'b0);
            bayt_ver(8'hD5, 1'b1, 1'b0);
            for (k = 0; k < N + 4; k = k + 1)
                bayt_ver(gonderilen[k] ^ ((k == bozuk_index) ? 8'h01 : 8'h00),
                         1'b1, 1'b0);
            bosluk(4);
        end
    endtask

    // alinan baytlari topla
    always @(posedge clk)
        if (!rst && bayt_gecerli) begin
            alinan[alinan_n] = bayt;
            alinan_n = alinan_n + 1;
        end

    initial begin
        $display("rgmii_alis testi");
        // yuk: taninabilir bir desen
        for (i = 0; i < N; i = i + 1) gonderilen[i] = i[7:0] + 8'h10;
        // FCS: yuk uzerinden hesapla, sonra tersle, LSB once
        c = 32'hFFFFFFFF;
        for (i = 0; i < N; i = i + 1) c = crc_bayt(c, gonderilen[i]);
        c = ~c;
        gonderilen[N+0] = c[7:0];
        gonderilen[N+1] = c[15:8];
        gonderilen[N+2] = c[23:16];
        gonderilen[N+3] = c[31:24];
        $display("  hesaplanan FCS: %02h %02h %02h %02h",
                 gonderilen[N], gonderilen[N+1], gonderilen[N+2], gonderilen[N+3]);

        repeat (4) @(posedge clk); #1; rst = 0;
        bosluk(4);

        // ---- 1. saglam cerceve ----
        alinan_n = 0;
        cerceve_ver(-1);
        if (alinan_n != N + 4) begin
            $display("  HATA: %0d bayt alindi, %0d bekleniyordu", alinan_n, N + 4);
            hata_say = hata_say + 1;
        end else $display("  bayt sayisi dogru (%0d, FCS dahil)", alinan_n);

        begin : icerik
            integer yanlis;
            yanlis = 0;
            for (i = 0; i < N + 4; i = i + 1)
                if (alinan[i] !== gonderilen[i]) yanlis = yanlis + 1;
            if (yanlis) begin
                $display("  HATA: %0d bayt yanlis — nibble sirasi ters olabilir",
                         yanlis);
                $display("        ilk: alinan %02h, beklenen %02h",
                         alinan[0], gonderilen[0]);
                hata_say = hata_say + 1;
            end else $display("  butun baytlar dogru (nibble sirasi dogru)");
        end

        if (!crc_dogru) begin
            $display("  HATA: saglam cerceveye crc_dogru=0 dendi");
            hata_say = hata_say + 1;
        end else $display("  saglam cerceve: crc_dogru=1");

        // ---- 2. BOZUK cerceve — bu olmadan yukaridaki bir sey ispatlamaz
        alinan_n = 0;
        cerceve_ver(5);              // 5. bayti boz
        if (crc_dogru) begin
            $display("  HATA: bozuk cerceveye de crc_dogru=1 dendi");
            $display("        (denetim hic calismiyor demektir)");
            hata_say = hata_say + 1;
        end else $display("  bozuk cerceve yakalandi: crc_dogru=0");
        if (!hata) begin
            $display("  HATA: bozuk cerceve icin hata bayragi kalkmadi");
            hata_say = hata_say + 1;
        end

        // ---- 3. PHY hata bildirirse ----
        alinan_n = 0;
        begin : phy_hata
            integer k;
            for (k = 0; k < 7; k = k + 1) bayt_ver(8'h55, 1'b1, 1'b0);
            bayt_ver(8'hD5, 1'b1, 1'b0);
            for (k = 0; k < N + 4; k = k + 1)
                bayt_ver(gonderilen[k], 1'b1, (k == 3));   // 3. baytta RXERR
            bosluk(4);
        end
        if (crc_dogru) begin
            $display("  HATA: PHY RXERR verdi ama cerceve saglam sayildi");
            hata_say = hata_say + 1;
        end else $display("  PHY hata bildirimi dinleniyor");

        if (hata_say == 0) $display("rgmii_alis testi GECTI");
        else               $display("rgmii_alis testi KALDI: %0d hata", hata_say);
        $finish;
    end

    initial begin
        #200_000;
        $display("rgmii_alis testi KALDI: zaman asimi");
        $finish;
    end

endmodule

`default_nettype wire
