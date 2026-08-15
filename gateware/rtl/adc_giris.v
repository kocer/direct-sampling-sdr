// AD9251 arayuzu — cift kanalli, 14 bit, COGULLANMIS PARALEL CMOS.
//
// BU MODUL BIR KEZ YANLIS YAZILDI, KAYDI DURSUN.
// Ilk hali seri LVDS varsayiyordu: DCO + FCO cerceve saati, kanal
// basina tek seri hat, 14 biti yedi cevrimde toplayan bir kaydirma
// yazmaci. O arayuz AD9253'un. AD9251'de OYLE BIR MOD YOK. Karta
// bakinca da goruluyordu: ADC basina D0..D13 + OR + DCO cekilmis,
// FCO diye bir ag hic yok. Gateware kartla konusmuyordu.
//
// AD9251 CIKISI (veri sayfasi, SPI 0x14):
//   bit 5 = 1  cogullama (interleaved) acik
//   Iki kanal TEK 14 bitlik veri yolunu paylasiyor. DCO 80 MHz
//   kaliyor; A ve B ornekleri DCO'nun ayri kenarlarinda cikiyor,
//   yani yol 160 MT/s'de calisiyor ama saat 80 MHz.
//
// NEDEN COGULLAMA. Kanal basina ayri yol cekmek ADC basina 30 hizli
// CMOS hatti demekti. Dogrudan orneklemeli bir alicida o kenarlar
// analog on uca geri biniyor; kart mikrovolt duymaya calisirken
// kendi sayisal gurultusunu dinler. Cogullamayla hat sayisi yariya
// iniyor.
//
// SAAT ADC'DEN GELIYOR, BIZDEN DEGIL. DCO ornekle birlikte yola
// cikiyor (kaynak-senkron). FPGA'nin kendi saatiyle yakalamaya
// calisirsak yol gecikmesi kadar kayariz ve 80 MSPS'te o kayma bir
// bitten buyuk. DCO ile yakalayip sonra FIFO ile sistem saatine
// geciyoruz.
//
// KANAL SIRASI KENDINI BULUYOR. Hangi kenarin A hangisinin B
// oldugunu veri sayfasindan okuyup sabitlemek yerine, ADC'nin test
// desenini kullaniyoruz: iki kanala FARKLI desen yazip hangisinin
// tuttuguna bakiyoruz. Yanlis sirayla calisan bir alici makul
// gorunen ama kanallari yer degistirmis bir goruntu uretir, ve o
// hata huzme yonlendirmede aynayla ortaya cikar — yani sahada.

`default_nettype none

module adc_giris #(
    parameter BIT = 14
) (
    input  wire              dco,        // ADC veri saati, 80 MHz
    input  wire [BIT-1:0]    d,          // cogullanmis veri yolu
    input  wire              asim,       // OR bayragi, veriyle ayni kenarda

    // test deseni denetimi (SPI ile ADC'ye yazilan desenler)
    input  wire [BIT-1:0]    desen_a,
    input  wire [BIT-1:0]    desen_b,
    input  wire              desen_dene, // 1 iken denetim kosuyor

    output wire              clk_adc,    // yakalanan saat, disari
    output reg  [BIT-1:0]    ornek_a,
    output reg  [BIT-1:0]    ornek_b,
    output reg               asim_a,
    output reg               asim_b,
    output reg               ornek_gecerli,
    output reg               takas,      // bulunan kenar polaritesi
    output reg               hizali      // desen tuttu
);

    assign clk_adc = dco;

    // ---------------------------------------------------------------
    // DDR yakalama.
    //
    // Dusen kenarda yakalanan deger POSEDGE ALANINA TASINIYOR: negedge
    // yazmaci yarim cevrim once yaziliyor, sonraki posedge'de okumak
    // ona yarim cevrimlik yerlesme suresi biraktiriyor. Dogrudan
    // negedge yazmacini birlesimsel kullanmak, iki kenar arasindaki
    // egrilik kadar dar bir pencere birakirdi.
    // ---------------------------------------------------------------
    reg [BIT-1:0] d_yuk, d_dus;
    reg           or_yuk, or_dus;

    always @(posedge dco) begin
        d_yuk  <= d;
        or_yuk <= asim;
    end
    always @(negedge dco) begin
        d_dus  <= d;
        or_dus <= asim;
    end

    // dusen kenar orneginin posedge alanindaki kopyasi
    reg [BIT-1:0] d_dus_g;
    reg           or_dus_g;
    always @(posedge dco) begin
        d_dus_g  <= d_dus;
        or_dus_g <= or_dus;
    end

    // ZAMAN SIRASI: d_dus_g yarim cevrim ONCE ornekelendi, d_yuk
    // simdi. Ikisi ayni ADC cevriminin iki kanali.
    wire [BIT-1:0] once     = d_dus_g;
    wire [BIT-1:0] sonra    = d_yuk;
    wire           once_or  = or_dus_g;
    wire           sonra_or = or_yuk;

    always @(posedge dco) begin
        ornek_a       <= takas ? sonra    : once;
        ornek_b       <= takas ? once     : sonra;
        asim_a        <= takas ? sonra_or : once_or;
        asim_b        <= takas ? once_or  : sonra_or;
        ornek_gecerli <= 1'b1;
    end

    // ---------------------------------------------------------------
    // Desen denetimi ve kanal sirasi.
    //
    // Iki yorumu da ayni anda sinariz: duz (once=A) ve takas
    // (once=B). Hangisi tutuyorsa polarite odur. Ikisi de tutmuyorsa
    // hizali dusuyor ve yukarisi veriyi kullanmiyor.
    //
    // TEK ESLESME YETMIYOR. Rastgele veride 14 bitin bir desene
    // uymasi 1/16384 — 80 MSPS'te saniyede bes bin kez olur. 256
    // ardisik eslesme istiyoruz; gurultude olma olasiligi sifira
    // yakin, ama gercek desende 3.2 us suruyor.
    // ---------------------------------------------------------------
    wire duz_tut   = (once  == desen_a) && (sonra == desen_b);
    wire takas_tut = (sonra == desen_a) && (once  == desen_b);

    reg [7:0] duz_say, takas_say;

    always @(posedge dco) begin
        if (!desen_dene) begin
            // Denetim kapali: son bulunan polarite ve hizali DURUYOR.
            // Sifirlamak, calisan bir alicinin ilk SPI yazmasindan
            // sonra kendini kaybetmesi demekti.
            duz_say   <= 8'd0;
            takas_say <= 8'd0;
        end else begin
            duz_say   <= duz_tut   ? (duz_say   == 8'hFF ? 8'hFF : duz_say   + 1'b1) : 8'd0;
            takas_say <= takas_tut ? (takas_say == 8'hFF ? 8'hFF : takas_say + 1'b1) : 8'd0;

            if (duz_say == 8'hFF) begin
                takas  <= 1'b0;
                hizali <= 1'b1;
            end else if (takas_say == 8'hFF) begin
                takas  <= 1'b1;
                hizali <= 1'b1;
            end else if (duz_say == 8'd0 && takas_say == 8'd0) begin
                hizali <= 1'b0;
            end
        end
    end

    initial begin
        takas  = 1'b0;
        hizali = 1'b0;
    end

endmodule

`default_nettype wire
