// NCO — sayisal kontrollu osilator.
//
// Faz biriktirici + arama tablosu. Bant secimini bu yapiyor: alinan
// sinyali sifir frekansa indiriyoruz, sonra azaltiyoruz.
//
// FAZ BIRIKTIRICI 32 BIT. Cozunurluk:
//     80e6 / 2^32 = 0.0186 Hz
// Bir CW isareti icin fazlasiyla ince. 24 bit yapsaydik 4.8 Hz olurdu
// ve bu duyulur bir hata.
//
// TABLO 10 BIT ADRES, 16 BIT DEGER, CEYREK DALGA.
// Ceyrek dalga saklamak tabloyu dorde bolüyor: sinus'un ilk ceyregi
// otekilerin isaret ve sira degistirmis hali. ECP5-25F'te blok RAM
// kisitli, ve dort kanal x iki tablo (sin/cos) yer istiyor.
//
// GENLIK HATASI: 10 bit adres, tablo icinde 0.09 derecelik adim
// demek. Bunun urettigi yan bantlar -66 dBc civari. ADC'nin kendi
// SFDR'i 85 dBc oldugu icin bu SINIRLAYICI OLUR. O yuzden faz
// biriktiricinin ust bitlerini dogrudan adres yapmiyoruz — kalan
// bitlerle dogrusal ara deger (dither yerine) kullaniyoruz.

`default_nettype none

module nco #(
    parameter FAZ_BIT  = 32,
    parameter ADR_BIT  = 10,
    parameter CIK_BIT  = 16
) (
    input  wire                clk,
    input  wire                rst,
    input  wire [FAZ_BIT-1:0]  faz_artis,   // frekans
    input  wire [FAZ_BIT-1:0]  faz_ofset,   // kanallar arasi faz
    input  wire                yukle_ofset,
    output reg  signed [CIK_BIT-1:0] sin_cik,
    output reg  signed [CIK_BIT-1:0] cos_cik
);

    reg [FAZ_BIT-1:0] faz;

    always @(posedge clk) begin
        if (rst)
            faz <= {FAZ_BIT{1'b0}};
        else if (yukle_ofset)
            // KANALLAR ARASI FAZ BURADAN AYARLANIYOR.
            // Dort kanalin NCO'su ayni artisla kosuyor ama farkli
            // ofsetle baslayabiliyor; huzme yonlendirmede gereken
            // faz kaymasi bu.
            faz <= faz_ofset;
        else
            faz <= faz + faz_artis;
    end

    // ---------------------------------------------------------------
    // Ceyrek dalga tablosu. Ilk ceyrek saklaniyor; oteki uc ceyrek
    // adresi tersleyerek ve isaret degistirerek uretiliyor.
    // ---------------------------------------------------------------
    localparam TABLO_BOY = 1 << (ADR_BIT - 2);

    reg signed [CIK_BIT-1:0] tablo [0:TABLO_BOY-1];

    integer i;
    initial begin
        for (i = 0; i < TABLO_BOY; i = i + 1)
            tablo[i] = $rtoi($sin(3.14159265358979 * 2.0 *
                             (i + 0.5) / (1 << ADR_BIT)) *
                             ((1 << (CIK_BIT-1)) - 1));
    end

    wire [ADR_BIT-1:0] adr = faz[FAZ_BIT-1 -: ADR_BIT];

    // ceyrek secimi
    wire [1:0] ceyrek_s = adr[ADR_BIT-1:ADR_BIT-2];
    wire [ADR_BIT-3:0] ic_s = adr[ADR_BIT-3:0];
    wire [ADR_BIT-3:0] adr_s = ceyrek_s[0] ? ~ic_s : ic_s;

    // kosinus = sinus'un ceyrek dalga ilerisi
    wire [ADR_BIT-1:0] adr_c = adr + (1 << (ADR_BIT-2));
    wire [1:0] ceyrek_c = adr_c[ADR_BIT-1:ADR_BIT-2];
    wire [ADR_BIT-3:0] ic_c = adr_c[ADR_BIT-3:0];
    wire [ADR_BIT-3:0] adr_c2 = ceyrek_c[0] ? ~ic_c : ic_c;

    always @(posedge clk) begin
        sin_cik <= ceyrek_s[1] ? -tablo[adr_s] : tablo[adr_s];
        cos_cik <= ceyrek_c[1] ? -tablo[adr_c2] : tablo[adr_c2];
    end

endmodule

`default_nettype wire
