// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
//
// FIFO — IKI SAATLI (GERCEK CDC) FORMAL OZELLIK.
//
// fifo_gecis_formal.v FIFO MANTIGINI kanitliyor ama tek saatle.
// Bu dosya asil riski hedefliyor: yazma ADC'nin DCO'suyla, okuma
// sistem saatiyle ve ikisinin arasinda FAZ ILISKISI YOK.
//
// Tek saatli ispat sunu kacirir: iki alan arasindaki Gray kodlu
// isaretci senkronizasyonu, bir alanin isaretcisini digerinin
// GECIKMELI gormesine dayanir. O gecikme yanlis modellenmisse FIFO
// bazen "bos degil" derken bos, ya da "yer var" derken doludur.
// Belirtisi "arada bir ornek kayboluyor" olur — sahada bulunmasi en
// zor hata turu, cunku tekrarlanabilir degil.
//
// COZUCU SAATLERI KENDISI SURUYOR. yaz_clk ve oku_clk birer serbest
// giris; sby multiclock kipinde cozucu butun sirali kombinasyonlari
// deniyor. Yani "ya iki saat su anda ust uste gelirse" sorusunu biz
// dusunmuyoruz, cozucu ariyor.
//
// KANITLANAN — hepsi saatten BAGIMSIZ ifade edilmis:
//
//   1 OKUMA YAZMAYI GECEMEZ. Okunan kelime sayisi hicbir zaman
//     yazilan kelime sayisini asamaz. Asarsa FIFO var olmayan veri
//     uretmis demektir.
//
//   2 ICERDE DERINLIKTEN FAZLASI OLAMAZ. Asarsa yazma ustune
//     yazilmis ve bir ornek SESSIZCE kaybolmus demektir.
//
//   3 VERI BUTUNLUGU. Cozucunun sectigi sabit bir sira numarasina
//     yazilan deger, o sira okunurken AYNEN cikmali.
//
// KOSU: sby -f formal/fifo_cdc.sby

`default_nettype none

module fifo_cdc_formal #(
    parameter GENISLIK = 4,
    parameter DERINLIK = 4
) (
    input  wire                 yaz_clk,
    input  wire                 oku_clk,
    input  wire                 rst,
    input  wire [GENISLIK-1:0]  yaz_veri,
    input  wire                 yaz,
    input  wire                 oku
);
    localparam ADR = $clog2(DERINLIK);

    wire                yaz_hazir, oku_gecerli;
    wire [GENISLIK-1:0] oku_veri;
    wire [ADR:0]        oku_doluluk;

    wire yaz_et = yaz && yaz_hazir;
    wire oku_et = oku && oku_gecerli;

    fifo_gecis #(.GENISLIK(GENISLIK), .DERINLIK(DERINLIK)) dut (
        .yaz_clk(yaz_clk), .yaz_rst(rst),
        .yaz_veri(yaz_veri), .yaz(yaz_et), .yaz_hazir(yaz_hazir),
        .oku_clk(oku_clk), .oku_rst(rst),
        .oku_veri(oku_veri), .oku(oku_et),
        .oku_gecerli(oku_gecerli), .oku_doluluk(oku_doluluk)
    );

`ifdef FORMAL
    localparam SAY = 6;

    // -----------------------------------------------------------------
    // RESET IKI ALANIN DA GORMESI GEREKIYOR.
    //
    // Ilk denememde reseti sadece yazma saatinin bir kenarina kadar
    // tutuyordum ve ispat 2. adimda dustu. Sebep tasarim degildi:
    // cozucu okuma saatini hic kimildatmadan reseti birakabiliyordu,
    // yani okuma alani resetten hic gecmemis bir durumda ispata
    // giriyordu. Iki bagimsiz saat varken "reset bitti" tek bir an
    // degil; her alan kendi saatiyle cikiyor.
    //
    // Bu, ispatin hatasi — ama ayni zamanda gercek kartta da gecerli
    // bir kural: reset, en yavas saatin en az bir kenarindan gecmeli.
    // -----------------------------------------------------------------
    reg yaz_gordu = 1'b0, oku_gordu = 1'b0;
    always @(posedge yaz_clk) if (rst) yaz_gordu <= 1'b1;
    always @(posedge oku_clk) if (rst) oku_gordu <= 1'b1;

    wire ikisi_de = yaz_gordu & oku_gordu;
    always @(*) if (!ikisi_de) assume (rst);

    // -----------------------------------------------------------------
    // RESET BIR KEZ INER, BIR DAHA KALKMAZ.
    //
    // Bu varsayim olmadan ispat dustu ve karsi ornek ogreticiydi:
    // cozucu reseti ORTADA tekrar bastiriyordu, ve o darbeyi bir alan
    // goruyor digeri gormuyordu (o sirada saati kimildamiyor). Sonuc
    // FIFO'nun iki yakasinin ayri dusmesi — yazma tarafi sifirlanmis,
    // okuma tarafi eski isaretcisiyle "veri var" diyor.
    //
    // Varsayim GERCEGE UYGUN: ust.v'de rst = ~por[12] ve por sayaci
    // doyuyor, yani reset bir kez birakiliyor ve bir daha kalkmiyor.
    //
    // AMA KARSI ORNEK GERCEK BIR KURALI GOSTERDI ve ust.v'ye not
    // dusuldu: bu FIFO'nun yazma tarafi ADC'nin DCO'suyla calisiyor
    // ve DCO, ADC SPI ile yapilandirilana kadar gelmeyebilir. O
    // durumda reset darbesini SADECE okuma tarafi gorur. Gercek
    // cipte ECP5'in GSR'i yazmaclari baslangic degerine cektigi icin
    // sorun cikmiyor; ama bu bir GSR bagimliligi ve bilinerek
    // birakilmali, kesfedilerek degil.
    reg rst_dustu = 1'b0;
    always @(posedge yaz_clk) if (ikisi_de && !rst) rst_dustu <= 1'b1;
    always @(*) if (rst_dustu) assume (!rst);

    // reset birakildiktan sonra ispat basliyor
    reg gecmis = 1'b0;
    always @(posedge yaz_clk) if (ikisi_de && !rst) gecmis <= 1'b1;

    // -----------------------------------------------------------------
    // SAYACLAR KENDI ALANLARINDA.
    //
    // yaz_no yazma saatiyle, oku_no okuma saatiyle sayiyor. Ikisini
    // ayni saate baglamak, tam da kanitlamak istedigimiz seyi
    // varsaymak olurdu.
    // -----------------------------------------------------------------
    reg [SAY-1:0] yaz_no, oku_no;

    always @(posedge yaz_clk)
        if (rst) yaz_no <= 0;
        else if (yaz_et) yaz_no <= yaz_no + 1'b1;

    always @(posedge oku_clk)
        if (rst) oku_no <= 0;
        else if (oku_et) oku_no <= oku_no + 1'b1;

    // ---- 1. OKUMA YAZMAYI GECEMEZ
    //
    // Iki alanda sayilan iki degeri karsilastirmak formal icin
    // gecerli: ikisi de durum, ve cozucu her ara zamanda bakiyor.
    always @(posedge oku_clk)
        if (gecmis && !rst)
            assert (oku_no <= yaz_no);

    // ---- 2. ICERDE DERINLIKTEN FAZLASI OLAMAZ
    always @(posedge yaz_clk)
        if (gecmis && !rst)
            assert (yaz_no - oku_no <= DERINLIK);

    // ---- 3. VERI BUTUNLUGU
    (* anyconst *) reg [SAY-1:0] izlenen;
    always @(*) assume (izlenen < 6'd16);

    reg [GENISLIK-1:0] izlenen_veri;
    reg                izlenen_yazildi;

    always @(posedge yaz_clk)
        if (rst) izlenen_yazildi <= 1'b0;
        else if (yaz_et && yaz_no == izlenen) begin
            izlenen_veri    <= yaz_veri;
            izlenen_yazildi <= 1'b1;
        end

    always @(posedge oku_clk)
        if (gecmis && !rst && oku_et && oku_no == izlenen) begin
            // Bu noktada yazma MUTLAKA olmus olmali (ozellik 1'in
            // sonucu), yoksa okunan veri hicbir yerden gelmiyor.
            assert (izlenen_yazildi);
            assert (oku_veri == izlenen_veri);
        end
`endif

endmodule

`default_nettype wire
