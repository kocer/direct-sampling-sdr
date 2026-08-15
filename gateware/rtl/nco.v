// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
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
    // SAAT IZNI — VERIS ZINCIRI TAM HIZDA KOSMUYOR.
    //
    // Alista NCO her cevrim ilerliyor (izin surekli 1). Veriste ise
    // ornek hizi 40 MSPS, saat 80 MHz: NCO tam hizda kossaydi
    // tasiyici 80 MHz'e gore uretilir, DAC ise her ikinci ornegi
    // alirdi — yani cikis 2'ye BOLUNEREK ornekleniyor ve 20 MHz
    // ustundeki her sey (CIC artirma aynalari dahil) banda katlanirdi.
    // Izinle NCO ornek basina bir ilerliyor, katlama hic olusmuyor.
    input  wire                izin,
    output reg  signed [CIK_BIT-1:0] sin_cik,
    output reg  signed [CIK_BIT-1:0] cos_cik
);

    reg [FAZ_BIT-1:0] faz;

    always @(posedge clk) begin
        if (rst)
            faz <= {FAZ_BIT{1'b0}};
        // YUKLEME IZINDEN BAGIMSIZ. Faz ofseti host'un yazma anina
        // bagli, ornek hizina degil; izne baglasaydik yukleme darbesi
        // izin dusukken gelirse SESSIZCE kaybolurdu.
        else if (yukle_ofset)
            // KANALLAR ARASI FAZ BURADAN AYARLANIYOR.
            // Dort kanalin NCO'su ayni artisla kosuyor ama farkli
            // ofsetle baslayabiliyor; huzme yonlendirmede gereken
            // faz kaymasi bu.
            faz <= faz_ofset;
        else if (izin)
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

    // ---------------------------------------------------------------
    // TABLO OKUMASI YAZMACLI — YOKSA BLOK RAM'E DUSMUYOR.
    //
    // Once "sin_cik <= ceyrek ? -tablo[adr] : tablo[adr]" tek satirdi:
    // tablo BIRLESIMSEL okunuyordu ve ECP5'in blok RAM'i asenkron
    // okuma yapamaz. yosys butun tabloyu LUT agacina acti ve o agac
    // clk_sys'in kritik yolu oldu — 74 MHz, 80 gerekiyor. Tasarimda
    // on NCO ornegi var (dort kanal x sin/cos + DUC), yani ayni agac
    // on kez.
    //
    // Okumayi yazmaclayinca DP16KD cikiyor: hem yol kisaliyor hem
    // binlerce LUT geri geliyor. Karsiligi BIR CEVRIM gecikme.
    //
    // GECIKME ZARARSIZ, cunku SABIT VE ORTAK. NCO cikisi bir cevrim
    // gec gelince tasiyicinin faz referansi bir ornek kayiyor —
    // dort kanalda AYNI miktarda. Huzme yonlendirme kanallar ARASI
    // faz farkina bakiyor, o fark degismiyor.
    // ---------------------------------------------------------------
    reg signed [CIK_BIT-1:0] rom_s, rom_c;
    reg                      isaret_s, isaret_c;

    always @(posedge clk) if (izin) begin
        rom_s    <= tablo[adr_s];
        rom_c    <= tablo[adr_c2];
        isaret_s <= ceyrek_s[1];
        isaret_c <= ceyrek_c[1];
    end

    always @(posedge clk) if (izin) begin
        sin_cik <= isaret_s ? -rom_s : rom_s;
        cos_cik <= isaret_c ? -rom_c : rom_c;
    end

endmodule

`default_nettype wire
