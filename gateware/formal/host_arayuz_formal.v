// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
//
// HOST ARAYUZU — FORMAL OZELLIK.
//
// Test tezgahi DENEDIGI durumlari kanitlar. Formal dogrulama BUTUN
// girdiler icin kanitlar: cozucu ozelligi bozan bir dizi ariyor ve
// bulamazsa "boyle bir dizi YOK" diyor.
//
// Bu modul icin bunu yapmaya deger, cunku kayit yazma yolu zararsiz
// bir yol degil: PA gecit bias'ini, verici frekansini ve role
// zincirini ayni arayuz suruyor. Tek bir bit hatasinin 100 W'lik bir
// kati yanlis noktaya surmesi donanim oldurur.
//
// KANITLANAN OZELLIK
//
//   Cerceve bicimi: A5 adr d3 d2 d1 d0 xor
//   xor = adr ^ d3 ^ d2 ^ d1 ^ d0
//
//   ISPAT: kayit_yaz yukseldigi HER cevrimde, o cerceveyi olusturan
//   yedi baytin saglama toplami DOGRUYDU.
//
//   Tersi soylenirse: saglamasi tutmayan hicbir bayt dizisi, uzunlugu
//   ne olursa olsun, hicbir sirayla, kayit yazmasi uretemez.
//
// NEDEN BU OZELLIK. Bir test tezgahi "bozuk cerceve gonderdim,
// yazmadi" der ve bir ornegi kanitlar. Formal, 2^56 olasi cerceveden
// hicbirinin gecmedigini kanitliyor — ve arada zaman asimi, yeniden
// hizalanma, yarim cerceve gibi durumlar da var. Elle o kombinasyonu
// aramak mumkun degil.
//
// KOSU: sby -f formal/host_arayuz.sby

`default_nettype none

module host_arayuz_formal (
    input  wire        clk,
    input  wire        rst,
    input  wire [7:0]  al_bayt,
    input  wire        al_gecerli,
    input  wire        ver_mesgul,
    input  wire [31:0] kayit_oku
);

    wire [7:0]  ver_bayt;
    wire        ver_gonder;
    wire [7:0]  kayit_adr;
    wire [31:0] kayit_veri;
    wire        kayit_yaz;

    // ZAMAN ASIMI KUCULTULDU. Gercekte 80000 cevrim (1 ms); formal
    // cozucu icin o derinlik anlamsiz. Kucuk bir deger ayni mantigi
    // kosuyor ve zaman asiminin KENDISI de ispata giriyor: sayac
    // dolarken gelen bir cerceve de denenmis oluyor.
    host_arayuz #(.ZAMAN_ASIMI(8)) dut (
        .clk(clk), .rst(rst),
        .al_bayt(al_bayt), .al_gecerli(al_gecerli),
        .ver_bayt(ver_bayt), .ver_gonder(ver_gonder),
        .ver_mesgul(ver_mesgul),
        .kayit_adr(kayit_adr), .kayit_veri(kayit_veri),
        .kayit_yaz(kayit_yaz), .kayit_oku(kayit_oku)
    );

    // -----------------------------------------------------------------
    // BAYT TARIHCESI — DURUM MAKINESI TAKLIDI DEGIL.
    //
    // Ilk denememde dut'un durum makinesini golge olarak yeniden
    // yazmistim. Iki sebepten yanlisti:
    //
    //   Karmasikligi tekrarliyordu (okuma komutu 0xA6, zaman asimi,
    //   yanit durumu) ve benim golgem 0xA6'yi bilmiyordu; bir okuma
    //   cercevesinden sonra ikisi ayrisip ispat sahte bir karsi ornek
    //   uretti. Yani basarisizlik tasarimda degil ispattaydi.
    //
    //   Daha kotusu: durum makinesini taklit eden bir golge, dut'un
    //   hatasini da taklit edebilir ve o zaman ispat hicbir sey
    //   soylemez.
    //
    // Dogrusu cok daha basit — SADECE SON YEDI GECERLI BAYTI tut.
    // Durum yok, zaman asimi yok, komut ayrimi yok. Ozellik de
    // dogrudan: yazma oldugunda o yedi bayt gecerli bir cerceve
    // olusturuyor olmali.
    // -----------------------------------------------------------------
    reg [7:0] ge [0:6];          // ge[0] en yeni
    integer   k;
    initial for (k = 0; k < 7; k = k + 1) ge[k] = 8'h00;

    always @(posedge clk)
        if (al_gecerli) begin
            for (k = 6; k > 0; k = k - 1) ge[k] <= ge[k-1];
            ge[0] <= al_bayt;
        end

    // A5 adr d3 d2 d1 d0 xor   ->   ge[6] ge[5] ge[4] ge[3] ge[2] ge[1] ge[0]
    wire cerceve_gecerli =
        (ge[6] == 8'hA5) &&
        (ge[0] == (ge[5] ^ ge[4] ^ ge[3] ^ ge[2] ^ ge[1]));

`ifdef FORMAL
    reg gecmis = 1'b0;
    always @(posedge clk) gecmis <= 1'b1;

    // ---- VARSAYIM: baslangicta reset
    always @(*) if (!gecmis) assume (rst);

    // ---- ISPAT 1: yazma varsa saglama dogruydu
    //
    // Bu ozellik bozulursa cozucu bize cerceveyi verir ve elimizde
    // "sunu gonderirsen yanlis kayit yazilir" diyen somut bir ornek
    // olur.
    always @(posedge clk)
        if (gecmis && !rst && kayit_yaz)
            assert (cerceve_gecerli);

    // ---- ISPAT 2: yazilan adres ve veri, cercevedeki degerler
    //
    // Saglamanin dogru olmasi yetmiyor: dogru cerceveden YANLIS
    // degeri yazmak da ayni kadar kotu. Ornegin adres ve verinin yer
    // degistirmesi, PA bias kaydina frekans yazardi.
    always @(posedge clk)
        if (gecmis && !rst && kayit_yaz) begin
            assert (kayit_adr  == ge[5]);
            assert (kayit_veri == {ge[4], ge[3], ge[2], ge[1]});
        end
`endif

endmodule

`default_nettype wire
