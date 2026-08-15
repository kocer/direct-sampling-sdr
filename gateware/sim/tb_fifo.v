// fifo_gecis testi — saat alani gecisi.
//
// BU MODULUN TESTI YOKTU ve tam da sessiz bozulan cinsten: dusen ya
// da tekrarlanan bir ornek paket sayacini bozmaz, sadece VERIYI
// bozar, ve o hata ancak spektrumda gorunur. Kart geldikten sonra
// "alici calisiyor ama gurultu tabani tuhaf" diye aranacak hata bu.
//
// Iki saat KASITLI OLARAK ILISKISIZ: 80 ve 125 MHz, ve baslangicta
// faz kaydirmali. Ayni saatle ya da tam katiyla test etmek gecisin
// asil zorlugunu atlar.
//
// Sinanan:
//   1 yazilan sira aynen okunuyor mu (kayip/tekrar yok)
//   2 FIFO dolunca yaz_hazir dusuyor mu ve veri kaybolmuyor mu
//   3 bosalinca oku_gecerli dusuyor mu

`timescale 1ns/1ps
`default_nettype none

module tb_fifo;

    localparam GEN = 8;
    localparam DER = 16;              // kucuk: dolma durumu test edilebilsin

    reg yaz_clk = 1'b0, oku_clk = 1'b0;
    always #6.25 yaz_clk = ~yaz_clk;          // 80 MHz
    always #4.00 oku_clk = ~oku_clk;          // 125 MHz

    reg rst = 1'b1;

    wire [GEN-1:0] yaz_veri;
    wire           yaz;
    wire           yaz_hazir;
    wire [GEN-1:0] oku_veri;
    wire           oku;
    wire           oku_gecerli;

    fifo_gecis #(.GENISLIK(GEN), .DERINLIK(DER)) dut (
        .yaz_clk(yaz_clk), .yaz_rst(rst),
        .yaz_veri(yaz_veri), .yaz(yaz), .yaz_hazir(yaz_hazir),
        .oku_clk(oku_clk), .oku_rst(rst),
        .oku_veri(oku_veri), .oku(oku), .oku_gecerli(oku_gecerli), .oku_doluluk());

    integer hata = 0;
    integer yazilan = 0, okunan = 0;
    localparam TOPLAM = 400;

    // ---------------------------------------------------------------
    // EL SIKISMA BIRLESIMSEL, YAZMACLI DEGIL.
    //
    // Once "if (oku_gecerli) ... oku <= 1" diye suruyordum: kontrol
    // N. cevrimde yapiliyor, oku ise N+1'de etkili oluyordu. Yani
    // tezgah kendi protokolunu bir cevrim kaydirmisti ve FIFO'yu
    // "bir gec veriyor" diye sucluyordu. Bir tur bosa gitti.
    //
    // Dogrusu: tuketim kararini ve verinin kontrolunu AYNI kenarda
    // yap. oku_veri o kenarda gecerliyse, o kenarda tuketilir.
    // ---------------------------------------------------------------
    reg yaz_dur = 1'b0, oku_dur = 1'b0;

    assign yaz      = !rst && yaz_hazir && !yaz_dur && (yazilan < TOPLAM);
    assign yaz_veri = yazilan[7:0];
    assign oku      = !rst && oku_gecerli && !oku_dur;

    always @(posedge yaz_clk)
        if (!rst && yaz) yazilan <= yazilan + 1;

    // Duraklar onemli — surekli yazmak FIFO'yu hep dolu tutar ve
    // BOSALMA yolunu hic sinamaz; surekli okumak tersini yapar.
    //
    // DURAK SAYACI SERBEST KOSUYOR, AKTARILAN SAYIYA BAGLI DEGIL.
    // Once "yazilan % 37" diye kurmustum: durak acilinca yazilan
    // ilerlemiyor, ilerlemeyince kosul dusmuyor — test 35 kelimede
    // kilitlendi. Duraklatan sey duraklattigi seyi sayamaz.
    integer yaz_sayac = 0, oku_sayac = 0;
    always @(posedge yaz_clk) begin
        yaz_sayac <= yaz_sayac + 1;
        yaz_dur   <= ((yaz_sayac % 37) > 30);
    end
    always @(posedge oku_clk) begin
        oku_sayac <= oku_sayac + 1;
        // OKUYUCU KASITLI OLARAK YAVAS. 125 MHz okuma, 80 MHz
        // yazmadan zaten hizli; esit duraklarla FIFO hic dolmuyor
        // ve DOLU yolu hic sinanmiyordu. 53 cevrimin 11'inde
        // okuyunca ortalama okuma ~26 MHz'e iniyor ve FIFO doluyor.
        oku_dur   <= ((oku_sayac % 53) > 10);
    end

    reg [GEN-1:0] beklenen = 8'd0;
    always @(posedge oku_clk) begin
        if (!rst && oku) begin
            if (oku_veri !== beklenen) begin
                if (hata < 8)
                    $display("  HATA: %0d. kelime %02h, beklenen %02h",
                             okunan, oku_veri, beklenen);
                hata <= hata + 1;
            end
            beklenen <= beklenen + 8'd1;
            okunan   <= okunan + 1;
        end
    end

    // ---------------------------------------------------------------
    // Dolma gozlemi: en az bir kez dolmus ve en az bir kez bosalmis
    // olmali, yoksa test iki yolu da gezmemis demektir.
    // ---------------------------------------------------------------
    reg doldu = 1'b0, bosaldi = 1'b0;
    always @(posedge yaz_clk) if (!rst && !yaz_hazir)   doldu   <= 1'b1;
    always @(posedge oku_clk) if (!rst && !oku_gecerli) bosaldi <= 1'b1;

    initial begin
        $display("fifo_gecis testi");
        repeat (10) @(posedge yaz_clk);
        rst = 1'b0;

        wait (okunan >= TOPLAM);
        repeat (20) @(posedge oku_clk);

        if (hata == 0) $display("  %0d kelime sirasiyla gecti", okunan);
        if (!doldu) begin
            $display("  HATA: FIFO hic dolmadi, dolu yolu sinanmadi");
            hata = hata + 1;
        end else $display("  dolu durumu gorundu");
        if (!bosaldi) begin
            $display("  HATA: FIFO hic bosalmadi, bos yolu sinanmadi");
            hata = hata + 1;
        end else $display("  bos durumu gorundu");

        if (hata == 0) $display("fifo_gecis testi GECTI");
        else           $display("fifo_gecis testi KALDI: %0d hata", hata);
        $finish;
    end

    initial begin
        #2_000_000;
        $display("fifo_gecis testi KALDI: zaman asimi (yazilan %0d, okunan %0d)",
                 yazilan, okunan);
        $finish;
    end

endmodule

`default_nettype wire
