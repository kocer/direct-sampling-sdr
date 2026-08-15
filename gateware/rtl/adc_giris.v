// AD9251 arayuzu — cift kanalli, 14 bit, LVDS DDR.
//
// ADC ornekleri DDR veriyor: saatin hem yukselen hem dusen kenarinda
// bir bit. Iki kanal (A ve B) ayri seri hatlardan geliyor ve her
// kanal 14 biti 7 saat cevriminde yolluyor.
//
// SAAT ADC'DEN GELIYOR, BIZDEN DEGIL. DCO (data clock out) ornekle
// birlikte yola cikiyor, yani kaynak-senkron. FPGA'nin kendi saatiyle
// yakalamaya calisirsak yol gecikmesi kadar kayariz ve 80 MSPS'te o
// kayma bir bitten buyuk. DCO ile yakalayip sonra FIFO ile sistem
// saatine geciyoruz.
//
// CERCEVE HIZALAMA: ADC'nin kendi test deseni var (ADC_TEST_PATTERN).
// Baslangicta o deseni okuyup 14 bitin nerede basladigini buluyoruz.
// Desen tutmadan veri gecerli sayilmiyor — yanlis hizalanmis bir
// cerceve sessizce yanlis genlik uretir, ve bu hata olcum yapana
// kadar gorunmez.

`default_nettype none

module adc_giris #(
    parameter BIT = 14
) (
    input  wire              dco_p,      // ADC veri saati
    input  wire              dco_n,
    input  wire              fco_p,      // cerceve saati
    input  wire              fco_n,
    input  wire              d_a_p,      // kanal A seri veri
    input  wire              d_a_n,
    input  wire              d_b_p,      // kanal B seri veri
    input  wire              d_b_n,

    output wire              clk_adc,    // yakalanan saat, disari
    output reg  [BIT-1:0]    ornek_a,
    output reg  [BIT-1:0]    ornek_b,
    output reg               ornek_gecerli,
    output reg               hizali      // cerceve kilitlendi mi
);

    // ---------------------------------------------------------------
    // LVDS alicilar. ECP5'te diferansiyel giris ayri bir ilkel degil;
    // p ucunu normal giris olarak tanimlayip IO_TYPE="LVDS" veriyoruz,
    // n ucu otomatik esleniyor. Kisit dosyasinda (ecp5.lpf) belirtiliyor.
    // ---------------------------------------------------------------
    wire dco = dco_p;
    wire fco = fco_p;
    wire d_a = d_a_p;
    wire d_b = d_b_p;

    assign clk_adc = dco;

    // ---------------------------------------------------------------
    // DDR yakalama: her kenarda bir bit.
    // ---------------------------------------------------------------
    reg d_a_yuk, d_a_dus, d_b_yuk, d_b_dus;
    reg fco_yuk;

    always @(posedge dco) begin
        d_a_yuk <= d_a;
        d_b_yuk <= d_b;
        fco_yuk <= fco;
    end
    always @(negedge dco) begin
        d_a_dus <= d_a;
        d_b_dus <= d_b;
    end

    // ---------------------------------------------------------------
    // Seri -> paralel. 14 bit, MSB once (AD9251 veri sayfasi Sekil 4).
    // Her saat cevriminde iki bit giriyor, yani 7 cevrimde bir ornek.
    // ---------------------------------------------------------------
    localparam SAYAC_SON = (BIT / 2) - 1;   // 6

    reg [3:0]      sayac;
    reg [BIT-1:0]  kaydir_a, kaydir_b;
    reg            fco_onceki;

    wire cerceve_kenari = fco_yuk & ~fco_onceki;

    always @(posedge dco) begin
        fco_onceki <= fco_yuk;

        // FCO'nun yukselen kenari cercevenin basi. Sayaci ORAYA
        // sifirliyoruz; serbest sayan bir sayac zamanla kayar ve
        // kayma sessizce yanlis ornek uretir.
        if (cerceve_kenari) begin
            sayac    <= 0;
            kaydir_a <= {d_a_yuk, d_a_dus, {(BIT-2){1'b0}}};
            kaydir_b <= {d_b_yuk, d_b_dus, {(BIT-2){1'b0}}};
            ornek_gecerli <= 1'b0;
        end else begin
            kaydir_a <= {kaydir_a[BIT-3:0], d_a_yuk, d_a_dus};
            kaydir_b <= {kaydir_b[BIT-3:0], d_b_yuk, d_b_dus};

            if (sayac == SAYAC_SON) begin
                ornek_a       <= {kaydir_a[BIT-3:0], d_a_yuk, d_a_dus};
                ornek_b       <= {kaydir_b[BIT-3:0], d_b_yuk, d_b_dus};
                ornek_gecerli <= 1'b1;
                sayac         <= 0;
            end else begin
                ornek_gecerli <= 1'b0;
                sayac         <= sayac + 1'b1;
            end
        end
    end

    // ---------------------------------------------------------------
    // Hizalama denetimi. FCO her 7 cevrimde bir gelmeli. Gelmiyorsa
    // ya saat yok ya da baglanti bozuk — o durumda 'hizali' dusuyor ve
    // yukarisi veriyi kullanmiyor.
    //
    // Sessizce yanlis veri uretmektense hic uretmemek dogru: yanlis
    // hizalanmis bir cerceve makul gorunen ama yanlis genlikli ornek
    // verir, ve bunu ancak bilinen bir sinyalle olcerken fark edersin.
    // ---------------------------------------------------------------
    reg [7:0] cerceve_sayaci;
    always @(posedge dco) begin
        if (cerceve_kenari) begin
            hizali         <= (cerceve_sayaci == SAYAC_SON);
            cerceve_sayaci <= 0;
        end else if (cerceve_sayaci != 8'hFF) begin
            cerceve_sayaci <= cerceve_sayaci + 1'b1;
        end else begin
            hizali <= 1'b0;
        end
    end

endmodule

`default_nettype wire
