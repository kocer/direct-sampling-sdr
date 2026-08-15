// Kontrol zinciri — roleler, zayiflaticilar, bias DAC'lari.
//
// Uc ayri yol var ve ucu de bu modulden cikiyor:
//
// 1 KAYDIRMALI YAZMAC ZINCIRI (RLY_SER, RLY_SRCLK, RLY_RCLK)
//   C kartinda 7 x 74HC595, D kartinda 1 tane, her ek PA'da 1 tane.
//   Roleler ve karta ozel secme sinyalleri buradan. Zincir
//   A -> C -> D1 -> D2 ... diye uzuyor; ek kart FPGA'da pin
//   harcamiyor.
//
// 2 SPI (ATT_DATA, ATT_CLK, ATT*_LE)
//   PE4312 zayiflaticilar. Veri ortak, LE karta ozel.
//
// 3 DOGRUDAN HAT (PA_INHIBIT)
//   Zincire GIRMIYOR. Guvenlik hatti bir yazmacin arkasinda duramaz:
//   yazmac bozulursa ya da saat durursa kesme calismaz.
//
// DARBE — KILITLENEN ROLELER SUREKLI ENERJI KALDIRMAZ.
//
// C kartinda 28 tane Omron G6KU-2F-Y var: TEK BOBINLI KILITLENEN role.
// Bobini DRV8833 H-koprusu iki yonde suruyor, yani konum bobinin
// polaritesiyle secilіyor ve rolenin kendisi mekanik olarak kaliyor.
// Bobin DARBE icin tasarlanmis (tipik 20-100 ms); surekli enerjili
// kalirsa YANAR. 28 role x ~40 mA ayni anda cekilirse +5V rayi da
// zaten yetmez.
//
// ZAMANLAMAYI HOST'A BIRAKMAK YANLIS. "Host once enerjile, 30 ms
// bekle, sonra birak" desek, baglanti darbenin ortasinda koparsa
// bobin sonsuza kadar enerjili kalir ve yanar. Bir donanim
// korumasinin yazilimin hayatta kalmasina bagli olmasi kabul
// edilemez. O yuzden darbeyi GATEWARE uretiyor: bir kez "sur"
// dendiginde diziyi kendisi tamamliyor.
//
// TUTULAN BITLER AYRI. T/R roleleri (4 x G6K-2F-Y) kilitlenmiyor,
// SUREKLI akim istiyor — guc kesilince alisa dusmeleri zaten
// istenen davranis. Hangi bitlerin surekli tutulacagini tut_maske
// soyluyor; modul rolenin ne oldugunu bilmiyor, sadece "bu bitler
// kalici, otekiler anlik" biliyor. Kart ayrintisi gateware'e
// sizmiyor.
//
// ZINCIR UZUNLUGU CALISMA ANINDA AYARLANIYOR. Kac PA karti takili
// oldugunu gateware bilmiyor; kayit dosyasindan geliyor. Fazla bit
// surmek zararsiz (zincirin sonundan dusuyor), eksik surmek son
// karti guncellemiyor.

`default_nettype none

module kontrol_zinciri #(
    parameter MAKS_BAYT = 16,     // zincirde en fazla bu kadar 595
    // Bir milisaniyedeki cevrim sayisi. Testte kucultuluyor: 30 ms'i
    // gercek hizda simule etmek 2.4 milyon cevrim demek ve o test
    // kimsenin kosturmayacagi kadar yavas olur. Kosturulmayan test
    // yoktur.
    parameter MS_CEVRIM = 80000   // 80 MHz
) (
    input  wire        clk,
    input  wire        rst,

    // kayit arayuzu
    input  wire [7:0]  yaz_veri,
    input  wire [4:0]  yaz_adr,
    input  wire        yaz_darbe,
    input  wire [4:0]  zincir_bayt,     // kac 595 var
    input  wire        gonder,          // zinciri sur
    input  wire        darbe_kip,       // 1 = darbe dizisi kos
    input  wire [7:0]  darbe_ms,        // darbe suresi (ms)
    input  wire        maske_bank,      // yazma hedefi: 0 veri, 1 maske

    // kaydirmali yazmac zinciri
    output reg         rly_ser,
    output reg         rly_srclk,
    output reg         rly_rclk,

    output wire        mesgul
);

    // ---------------------------------------------------------------
    // Zincir tamponu. Her bayt bir 595.
    // ---------------------------------------------------------------
    reg [7:0] tampon    [0:MAKS_BAYT-1];
    reg [7:0] tut_maske [0:MAKS_BAYT-1];

    integer i;
    always @(posedge clk) begin
        if (rst) begin
            for (i = 0; i < MAKS_BAYT; i = i + 1) begin
                tampon[i]    <= 8'd0;
                // SIFIRLAMADA MASKE DE SIFIR: hicbir bit tutulmaz.
                // Guvenli varsayilan, cunku yanlis tutulan bir bit
                // bobin yakar; tutulmayan bir bit sadece rolenin
                // atmamasina yol acar.
                tut_maske[i] <= 8'd0;
            end
        end else if (yaz_darbe && yaz_adr < MAKS_BAYT) begin
            if (maske_bank) tut_maske[yaz_adr] <= yaz_veri;
            else            tampon[yaz_adr]    <= yaz_veri;
        end
    end

    // ---------------------------------------------------------------
    // Surucu durum makinesi
    //
    // 595 zincirinde EN SON yazmac ILK surulen bayti alir. Yani
    // tamponu sondan basa gonderiyoruz. Ters gonderirsek roleler
    // dogru sayida ama yanlis kartta calisir — ve bu hata ancak
    // yanlis anten secildiginde fark edilir.
    // ---------------------------------------------------------------
    localparam D_BOS   = 3'd0;
    localparam D_SUR   = 3'd1;
    localparam D_KILIT = 3'd2;
    localparam D_BEKLE = 3'd3;   // darbe suresi

    reg [2:0]  durum;
    reg        evre;             // 0 = enerjile, 1 = birak

    // SURE IKI KADEMELI SAYILIYOR, CARPMA YOK.
    //
    // Once "ms_sayaci >= darbe_ms * MS_CEVRIM" yaziyordum. O ifade
    // her cevrim BIRLESIMSEL bir 8x17 carpma ve 25 bitlik bir
    // karsilastirma demek; clk_sys 91.7 MHz'ten 62 MHz'e dustu ve
    // 80 MHz hedefi kacti. Oysa carpmaya hic gerek yok: kucuk bir
    // sayac bir milisaniyeyi olcuyor, buyuk sayac milisaniyeleri
    // sayiyor.
    reg [16:0] cev_sayaci;       // MS_CEVRIM'e kadar
    reg [7:0]  kalan_ms;
    reg [4:0]  bayt_no;      // sondan basa
    reg [3:0]  bit_no;
    reg [7:0]  kaydir;
    reg [3:0]  kilit_sayaci;

    assign mesgul = (durum != D_BOS);

    // SRCLK bolucusu: 595'in azami saat hizi 20 MHz (5 V'ta daha
    // dusuk). 80 MHz'i dorde boluyoruz -> 10 MHz kaydirma. Bu
    // hizda 16 bayt zincir 13 mikrosaniyede doluyor; role
    // anahtarlamasi milisaniye mertebesinde, yani sorun yok.
    reg [1:0] bolucu;

    // Ikinci evrede sadece TUTULAN bitler surulur; anlik bitler
    // dusuyor ve bobinler serbest kaliyor.
    function [7:0] cikacak;
        input [4:0] no;
        begin
            cikacak = evre ? (tampon[no] & tut_maske[no]) : tampon[no];
        end
    endfunction

    always @(posedge clk) begin
        if (rst) begin
            durum        <= D_BOS;
            rly_ser      <= 1'b0;
            rly_srclk    <= 1'b0;
            rly_rclk     <= 1'b0;
            bolucu       <= 2'd0;
            bayt_no      <= 5'd0;
            bit_no       <= 4'd0;
            kilit_sayaci <= 4'd0;
            evre         <= 1'b0;
            cev_sayaci   <= 17'd0;
            kalan_ms     <= 8'd0;
        end else begin
            bolucu <= bolucu + 1'b1;

            case (durum)
            D_BOS: begin
                rly_srclk <= 1'b0;
                rly_rclk  <= 1'b0;
                if (gonder && zincir_bayt != 5'd0) begin
                    durum   <= D_SUR;
                    bayt_no <= zincir_bayt - 1'b1;   // sondan basla
                    bit_no  <= 4'd7;                 // MSB once
                    // ILK BAYT MASKESIZ, cikacak() ILE DEGIL.
                    // cikacak() 'evre'yi okuyor ama evre bu kenarda
                    // bloklamayan atamayla sifirlaniyor, yani burada
                    // hala ONCEKI kosunun degeri. Bir onceki kosu
                    // darbe kipindeyse ilk bayt maskeleniyordu ve
                    // zincirin SON 595'i sifir kaliyordu. Ilk evre
                    // her zaman tam desen, o yuzden dogrudan tampon.
                    kaydir  <= tampon[zincir_bayt - 1'b1];
                    bolucu  <= 2'd0;
                    evre    <= 1'b0;
                end
            end

            D_SUR: begin
                case (bolucu)
                2'd0: begin
                    rly_ser   <= kaydir[7];
                    rly_srclk <= 1'b0;
                end
                2'd2: begin
                    rly_srclk <= 1'b1;      // yukselen kenarda yakalanir
                end
                2'd3: begin
                    rly_srclk <= 1'b0;
                    kaydir    <= {kaydir[6:0], 1'b0};
                    if (bit_no == 4'd0) begin
                        if (bayt_no == 5'd0) begin
                            durum        <= D_KILIT;
                            kilit_sayaci <= 4'd0;
                        end else begin
                            bayt_no <= bayt_no - 1'b1;
                            bit_no  <= 4'd7;
                            kaydir  <= cikacak(bayt_no - 1'b1);
                        end
                    end else begin
                        bit_no <= bit_no - 1'b1;
                    end
                end
                default: ;
                endcase
            end

            // RCLK: butun bitler kaydiktan SONRA tek darbe.
            // Kaydirirken kilitlemek roleleri ara durumlarda
            // anahtarlar — bir bant filtresinin yanlis anda devreye
            // girmesi verirken PA'yi acik yuke sokabilir.
            D_KILIT: begin
                kilit_sayaci <= kilit_sayaci + 1'b1;
                if (kilit_sayaci == 4'd2)
                    rly_rclk <= 1'b1;
                else if (kilit_sayaci >= 4'd6) begin
                    rly_rclk <= 1'b0;
                    // Darbe kipinde ve daha birakma evresi kosmadiysa
                    // sureyi bekleyip ikinci turu kosuyoruz.
                    if (darbe_kip && !evre) begin
                        durum      <= D_BEKLE;
                        cev_sayaci <= 17'd0;
                        kalan_ms   <= darbe_ms;
                    end else begin
                        durum <= D_BOS;
                    end
                end
            end

            // DARBE SURESI. Kucuk sayac bir ms, buyuk sayac kac ms.
            D_BEKLE: begin
                if (cev_sayaci >= MS_CEVRIM - 1) begin
                    cev_sayaci <= 17'd0;
                    if (kalan_ms != 8'd0) kalan_ms <= kalan_ms - 1'b1;
                end else begin
                    cev_sayaci <= cev_sayaci + 1'b1;
                end
                if (kalan_ms == 8'd0) begin
                    evre    <= 1'b1;
                    durum   <= D_SUR;
                    bayt_no <= zincir_bayt - 1'b1;
                    bit_no  <= 4'd7;
                    kaydir  <= tampon[zincir_bayt - 1'b1] &
                               tut_maske[zincir_bayt - 1'b1];
                    bolucu  <= 2'd0;
                end
            end

            default: durum <= D_BOS;
            endcase
        end
    end

endmodule

`default_nettype wire
