// SPI ana birimi — ADC, VCXO DAC, PA bias, PA ADC icin ortak.
//
// NEDEN VAR: AD9251 acilista COGULLANMAMIS modda geliyor. Kartta
// kanal B'nin cikis bacaklari (D0B..D13B, ORB, DCOB) hic bagli
// degil — cogullama acilmadan kanal B verisi HICBIR YERE gitmiyor
// ve dort kanalin ikisi olu. Yani alis zinciri, ADC'ye SPI ile
// yazacak bir sey olmadan calismiyor. Gateware'de boyle bir sey
// yoktu.
//
// GENEL AMACLI, "ADC KURUCUSU" DEGIL.
// Ilk dusundugum sey acilista sabit bir dizi register yazan bir
// durum makinesiydi. Vazgectim: o zaman veri sayfasindan okudugum
// her deger gateware'e gomulur ve biri yanlissa bitstream'i yeniden
// uretmeden duzeltilemez. Burada sadece "su cerceveyi su cihaza
// yolla" var; hangi registera ne yazilacagi host'un bilgisi.
// Ayni birim VCXO DAC'ini, PA bias DAC'larini ve PA'nin ADC'sini de
// suruyor — hepsi ayni SCLK/SDIO'yu paylasip CS ile ayriliyor.
//
// SDIO CIFT YONLU. AD9251'de tek bir SDIO hatti var: komut evresinde
// ana birim suruyor, okuma evresinde cihaz suruyor. Yon degisimini
// yanlis anda yapmak iki surucuyu karsi karsiya getirir; o yuzden
// birakma, cihazin surmeye baslamasindan YARIM SCLK once yapiliyor.
//
// SAAT KENARI: veri SCLK'nin DUSEN kenarinda degisiyor, cihaz
// YUKSELEN kenarda orneklir (SPI mod 0). Ters yazarsan hat
// osiloskopta kusursuz gorunur ve cihaz cop okur.

`default_nettype none

module spi_ana #(
    // clk / (2 * SCLK). 80 MHz / (2*8) = 5 MHz — AD9251 en fazla
    // 25 MHz kabul ediyor, PA kartina giden uzun hat icin bol pay.
    parameter BOLEN = 8,
    parameter CIHAZ = 4          // kac ayri CS hatti
) (
    input  wire        clk,
    input  wire        rst,

    // komut
    input  wire [31:0] veri,      // yollanacak bitler, MSB once
    input  wire [5:0]  uzunluk,   // toplam bit sayisi (komut + veri)
    input  wire [5:0]  oku_bit,   // son kac bit OKUMA (0 = saf yazma)
    input  wire [2:0]  cihaz,     // hangi CS
    input  wire        basla,     // tek cevrimlik darbe
    output reg  [31:0] okunan,
    output wire        mesgul,

    // pinler
    output reg              sclk,
    output wire             sdio_o,
    output reg              sdio_yon,   // 1 = ana birim suruyor
    input  wire             sdio_i,
    output reg [CIHAZ-1:0]  csb,        // aktif dusuk, aktarim boyunca
    // IKI FARKLI SECIM GELENEGI VAR, IKISI DE GEREKIYOR.
    // AD9251 ve bias DAC'lari CSB kullaniyor: aktarim boyunca DUSUK.
    // PE4312 zayiflaticilar LE kullaniyor: aktarim boyunca dusuk ama
    // sonunda YUKSEK BIR DARBE ile mandalliyorlar. Ikisini tek pine
    // indirmeye calismak birini bozar; iki cikis birakip hangi pinin
    // hangisini kullandigina ust modul karar veriyor.
    output reg [CIHAZ-1:0]  le          // aktarim sonunda darbe
);

    localparam D_BOS = 2'd0, D_ONCE = 2'd1, D_BIT = 2'd2, D_SONRA = 2'd3;

    reg [1:0]  durum;
    reg [31:0] kaydir;
    reg [5:0]  kalan;
    reg [5:0]  oku_kalan;
    reg [15:0] say;
    reg        yarim;         // 0 = SCLK dusuk yarisi, 1 = yuksek

    assign mesgul = (durum != D_BOS);
    assign sdio_o = kaydir[31];

    wire tik = (say == BOLEN - 1);

    always @(posedge clk) begin
        if (rst) begin
            durum    <= D_BOS;
            csb      <= {CIHAZ{1'b1}};
            le       <= {CIHAZ{1'b0}};
            sclk     <= 1'b0;
            sdio_yon <= 1'b0;
            say      <= 16'd0;
            yarim    <= 1'b0;
        end else begin
            case (durum)
            D_BOS: begin
                sclk <= 1'b0;
                csb  <= {CIHAZ{1'b1}};
                le   <= {CIHAZ{1'b0}};
                sdio_yon <= 1'b0;
                if (basla && uzunluk != 6'd0) begin
                    kaydir    <= veri << (32 - uzunluk);
                    kalan     <= uzunluk;
                    oku_kalan <= oku_bit;
                    okunan    <= 32'd0;
                    csb       <= ~({{(CIHAZ-1){1'b0}}, 1'b1} << cihaz);
                    sdio_yon  <= 1'b1;
                    say       <= 16'd0;
                    yarim     <= 1'b0;
                    durum     <= D_ONCE;
                end
            end

            // CS'DEN ILK SAAT KENARINA KADAR BEKLE.
            // AD9251 CSB dustukten sonra bir kurulma suresi istiyor;
            // hemen saat vermek ilk biti kaybettirir ve o kayip
            // butun cerceveyi bir bit kaydirir — cihaz komple baska
            // bir registera yazar.
            D_ONCE: if (tik) begin
                say   <= 16'd0;
                durum <= D_BIT;
            end else say <= say + 1'b1;

            D_BIT: if (tik) begin
                say <= 16'd0;
                if (!yarim) begin
                    // dusuk -> yuksek: cihaz simdi orneklyor
                    sclk  <= 1'b1;
                    yarim <= 1'b1;
                    if (oku_kalan != 6'd0 && kalan <= oku_kalan)
                        okunan <= {okunan[30:0], sdio_i};
                end else begin
                    // yuksek -> dusuk: veriyi degistir
                    sclk   <= 1'b0;
                    yarim  <= 1'b0;
                    kaydir <= {kaydir[30:0], 1'b0};
                    kalan  <= kalan - 1'b1;
                    // OKUMAYA GECMEDEN ONCE HATTI BIRAK.
                    // Cihaz okuma bitlerini surmeye baslayacak;
                    // birakmayi gec yaparsak iki surucu carpisir.
                    if (oku_kalan != 6'd0 && kalan == oku_kalan + 1)
                        sdio_yon <= 1'b0;
                    if (kalan == 6'd1) durum <= D_SONRA;
                end
            end else say <= say + 1'b1;

            // SON EVREDE MANDALLAMA DARBESI.
            // LE tipi cihazlarda veri kaydirma yazmacinda duruyor ve
            // ancak bu darbeyle cikisa geciyor. Darbeyi CSB'nin
            // birakilmasindan ONCE veriyoruz; sonra verirsek bazi
            // parcalarda kaydirma yazmaci coktan bosalmis olur.
            D_SONRA: if (tik) begin
                say   <= 16'd0;
                if (le == {CIHAZ{1'b0}}) begin
                    le <= ({{(CIHAZ-1){1'b0}}, 1'b1} << cihaz);
                end else begin
                    le    <= {CIHAZ{1'b0}};
                    csb   <= {CIHAZ{1'b1}};
                    durum <= D_BOS;
                end
            end else say <= say + 1'b1;
            endcase
        end
    end

endmodule

`default_nettype wire
