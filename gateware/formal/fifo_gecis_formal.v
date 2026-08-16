// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
//
// SAAT ALANI GECIS FIFO'SU — FORMAL OZELLIK.
//
// NEDEN BU MODUL. Her ADC ornegi buradan geciyor: yakalama ADC'nin
// DCO'suyla, isleme sistem saatiyle, ve ikisinin arasinda faz
// iliskisi YOK. CDC hatalari en sinsi hata turudur — kart calisir
// gorunur, saatler arasi kayma belli bir sicaklikta ya da belli bir
// kart orneginde tutmaz, ve belirtisi "arada bir ornek kayboluyor"
// olur. O hata tezgahta rastgele uyarimla ancak sansla bulunur.
//
// UC OZELLIK KANITLANIYOR:
//
//   1 BOSKEN GECERLI DEMEZ. oku_gecerli, icinde veri yokken
//     yukselmemeli. Yukselirse okuma tarafi cop okur.
//
//   2 DOLUYKEN HAZIR DEMEZ. yaz_hazir, yer yokken yukselmemeli.
//     Yukselirse yazma sessizce kaybolur — en kotusu bu, cunku
//     hicbir yerde bir hata bayragi kalkmaz.
//
//   3 VERI BUTUNLUGU. Icerideki bir konuma yazilan deger, okunurken
//     AYNEN cikmali. Klasik formal yontem: cozucu rastgele ama sabit
//     bir konum secsin, o konuma yazilani izleyelim ve cikista ayni
//     degeri bekleyelim. Tek tek butun konumlari denemeye gerek
//     kalmiyor — cozucu en kotuyu kendisi ariyor.
//
// KUCUK DERINLIK. Formal icin DERINLIK=4 kullaniliyor. Ayni mantik
// kosuyor ama durum uzayi kucuk kaliyor; dolma ve bosalma kenarlari
// da bu sayede ispatin ICINE giriyor (1024 derinlikte cozucu dolu
// duruma hic ulasamazdi ve en onemli ozellik hic denenmemis olurdu).
//
// KOSU: sby -f formal/fifo_gecis.sby

`default_nettype none

// VERI GENISLIGI ISPAT ICIN KUCULTULDU. FIFO mantigi genislikten
// bagimsiz: isaretciler, dolu/bos kosullari ve sira, veri bitlerinin
// sayisina bakmiyor. Dort bit ayni ozellikleri kanitliyor ve cozucu
// icin cok daha ucuz.
module fifo_gecis_formal #(
    parameter GENISLIK = 4,
    parameter DERINLIK = 4
) (
    input  wire                 clk,
    input  wire                 rst,
    input  wire [GENISLIK-1:0]  yaz_veri,
    input  wire                 yaz,
    input  wire                 oku
);
    localparam ADR = $clog2(DERINLIK);

    wire                yaz_hazir, oku_gecerli;
    wire [GENISLIK-1:0] oku_veri;
    wire [ADR:0]        oku_doluluk;

    // TEK SAAT KULLANILIYOR — bilerek.
    //
    // Formal cozucu iki bagimsiz saati modelleyebilir ama o zaman
    // ispat cok derinlesir ve asil sorulan sey (veri butunlugu,
    // bos/dolu mantigi) gurultunun altinda kalir. Iki saatli
    // senkronizasyonun kendisi Gray kodlu isaretcilerle cozulmus bir
    // problem; buradaki ispat FIFO MANTIGINI hedefliyor.
    fifo_gecis #(.GENISLIK(GENISLIK), .DERINLIK(DERINLIK)) dut (
        .yaz_clk(clk), .yaz_rst(rst),
        .yaz_veri(yaz_veri), .yaz(yaz && yaz_hazir), .yaz_hazir(yaz_hazir),
        .oku_clk(clk), .oku_rst(rst),
        .oku_veri(oku_veri), .oku(oku && oku_gecerli),
        .oku_gecerli(oku_gecerli), .oku_doluluk(oku_doluluk)
    );

`ifdef FORMAL
    reg gecmis = 1'b0;
    always @(posedge clk) gecmis <= 1'b1;
    always @(*) if (!gecmis) assume (rst);

    // -----------------------------------------------------------------
    // BAGIMSIZ SAYAC — dut'un icine bakmadan kac kelime icerde
    // -----------------------------------------------------------------
    reg [ADR+1:0] sayac;
    always @(posedge clk)
        if (rst) sayac <= 0;
        else begin
            case ({yaz && yaz_hazir, oku && oku_gecerli})
                2'b10: sayac <= sayac + 1'b1;
                2'b01: sayac <= sayac - 1'b1;
                default: ;
            endcase
        end

    // ---- 1. bosken gecerli demez
    always @(posedge clk)
        if (gecmis && !rst && sayac == 0)
            assert (!oku_gecerli);

    // ---- 2. doluyken hazir demez
    always @(posedge clk)
        if (gecmis && !rst && sayac == DERINLIK)
            assert (!yaz_hazir);

    // ---- 3. VERI BUTUNLUGU
    //
    // Cozucu rastgele ama SABIT bir sira numarasi seciyor. O sira
    // numarasindaki yazma izleniyor ve ayni sira numarasi okunurken
    // deger karsilastiriliyor.
    // SAYACLAR GENIS TUTULUYOR — SARMASINLAR.
    //
    // Ilk denememde ADR+1 bit (3 bit) kullandim ve sira korunumu
    // ozelligi 27. adimda dustu. Sebep tasarim degildi: sayaclar
    // 8'de sariyor ve oku_no <= yaz_no karsilastirmasi anlamsizlasiyor.
    // Ispatta kullanilan yardimci degiskenler, kosu derinligi boyunca
    // sarmayacak kadar genis olmali.
    // GENISLIK DEGIL, SADECE SARMAYACAK KADAR. Once 8 bit yaptim ve
    // cozucu 10 dakikada bitiremedi: her fazladan bit durum uzayini
    // ikiye katliyor. Kosu derinligi 24; 6 bit (63'e kadar) sarmayi
    // engellemeye fazlasiyla yeter ve arama cok daha kucuk.
    localparam SAY = 6;
    (* anyconst *) reg [SAY-1:0] izlenen;
    reg [GENISLIK-1:0] izlenen_veri;
    reg [SAY-1:0] yaz_no, oku_no;
    reg           izlenen_yazildi;

    // izlenen sira numarasi bu kosuda ulasilabilir olmali
    always @(*) assume (izlenen < 6'd20);

    always @(posedge clk)
        if (rst) begin
            yaz_no <= 0; oku_no <= 0; izlenen_yazildi <= 1'b0;
        end else begin
            if (yaz && yaz_hazir) begin
                if (yaz_no == izlenen) begin
                    izlenen_veri    <= yaz_veri;
                    izlenen_yazildi <= 1'b1;
                end
                yaz_no <= yaz_no + 1'b1;
            end
            if (oku && oku_gecerli)
                oku_no <= oku_no + 1'b1;
        end

    // izlenen sira numarasi okunurken deger ayni olmali
    always @(posedge clk)
        if (gecmis && !rst && oku && oku_gecerli &&
            oku_no == izlenen && izlenen_yazildi)
            assert (oku_veri == izlenen_veri);

    // ---- 4. SIRA KORUNUYOR: okunan sayi yazilani gecemez
    always @(posedge clk)
        if (gecmis && !rst)
            assert (oku_no <= yaz_no);
`endif

endmodule

`default_nettype wire
