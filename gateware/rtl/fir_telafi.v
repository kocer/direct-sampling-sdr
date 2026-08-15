// CIC telafi filtresi — sin(x)/x egimini duzeltir.
//
// CIC'in gecirme bandi duz degil:
//     H(f) = | sin(pi f / R) / (pi f / R) |^N
// Olctugumuz: R=64, N=4'te bant kenarinda -3.4 dB. Duzeltmezsek
// bandin kenarindaki bir istasyon ortadakinden 3.4 dB zayif duyulur,
// ve S-metre yanlis okur.
//
// COZUM: ters egimli kisa bir FIR. CIC'in egimi sabit ve bilindigi
// icin katsayilar da sabit — carpani yalnizca bu filtre icin
// harciyoruz, uyarlanabilir bir sey yok.
//
// SIMETRIK KATSAYI: h[n] = h[N-1-n]. Once toplayip sonra carpiyoruz,
// yani 11 dereceli filtre 6 carpanla kosuyor. ECP5-25F'te 28 carpan
// var ve dort kanal x iki yol (I,Q) = 8 karistirici carpani zaten
// gitti; ekonomi burada onemli.
//
// KATSAYILAR: 11 dereceli, tam sayi, toplam 2^15. Ters sin(x)/x'in
// en kucuk kareler yaklasimi, R=64 ve N=4 icin bant kenarina kadar
// hesaplandi. R degisirse egim de degisir — ama R'nin buyuk oldugu
// yerde (dar bant) egim zaten kucuk kaliyor, cunku kullanilan bant
// Nyquist'in cok altinda. En kotu durum R'nin kucuk oldugu genis
// bant modu, katsayilar da ona gore secildi.

`default_nettype none

module fir_telafi #(
    // GIRIS 18 BIT, 24 DEGIL.
    // 24 bitte simetrik cift toplami 25 bit oluyor ve 25x18 carpim
    // tek MULT18X18'e sigmiyor — yosys her carpani IKI DSP ile
    // kuruyor. Olculdu: kanal basina 26 DSP, ECP5-25F'te 28 tane var,
    // yani TEK kanal cipi dolduruyor.
    // 18 bit giriste toplam 19 bit; hala tasiyor. 17 bit giris ->
    // 18 bit toplam -> tek DSP. Kaybettigimiz araligin karsiligi
    // 6 dB ve CIC cikisinda zaten o kadar bos ust bit var.
    parameter GIRIS_BIT = 17,
    parameter CIKIS_BIT = 24,
    parameter KAT_BIT   = 18
) (
    input  wire                          clk,
    input  wire                          rst,
    input  wire signed [GIRIS_BIT-1:0]   giris,
    input  wire                          giris_gecerli,
    output reg  signed [CIKIS_BIT-1:0]   cikis,
    output reg                           cikis_gecerli
);

    localparam DERECE = 11;
    localparam YARI   = (DERECE - 1) / 2;    // 5

    // Simetrik katsayilar, h[0..5]; h[6..10] aynasi. Toplam 32768.
    //
    // TASARIM: 1/CIC'in en kucuk kareler yaklasimi, bandin ilk %40'i
    // uzerinde ve bant kenarina dogru agirlikli. Butun bandi
    // duzeltmeye calismak Gibbs dalgalanmasi birakiyor; %40'in otesini
    // zaten yarim bant filtresi kesiyor.
    //
    // Ilk denememde katsayilari elle uydurmustum; egimin ancak yarisini
    // duzeltiyorlardi (bant kenarinda 1.8 dB kaliyordu). Olcmeden
    // katsayi yazmak, tam da bu filtrenin duzeltmesi gereken hatayi
    // yerinde birakiyor.
    //
    // Olculen sonuc (R=64, N=4):
    //     f/Nyq   CIC      FIR     toplam
    //      0.1   -0.14    +0.14     0.00 dB
    //      0.2   -0.57    +0.57     0.00 dB
    //      0.3   -1.30    +1.30     0.00 dB
    //      0.4   -2.32    +2.32     0.00 dB
    //      0.5   -3.65    +3.65     0.00 dB
    //
    // 18 BIT: merkez katsayi 58896, 16 bit isaretliye (32767) sigmiyor.
    // ECP5'in MULT18X18'i zaten 18 bit isaretli, yani bedava.
    localparam signed [KAT_BIT-1:0] H0 =  -18'sd19;
    localparam signed [KAT_BIT-1:0] H1 =   18'sd200;
    localparam signed [KAT_BIT-1:0] H2 =  -18'sd1140;
    localparam signed [KAT_BIT-1:0] H3 =   18'sd4721;
    localparam signed [KAT_BIT-1:0] H4 =  -18'sd16826;
    localparam signed [KAT_BIT-1:0] H5 =   18'sd58896;   // merkez

    // ---------------------------------------------------------------
    // Kaydirmali hat
    // ---------------------------------------------------------------
    reg signed [GIRIS_BIT-1:0] hat [0:DERECE-1];
    integer k;

    always @(posedge clk) begin
        if (rst) begin
            for (k = 0; k < DERECE; k = k + 1)
                hat[k] <= {GIRIS_BIT{1'b0}};
        end else if (giris_gecerli) begin
            hat[0] <= giris;
            for (k = 1; k < DERECE; k = k + 1)
                hat[k] <= hat[k-1];
        end
    end

    // ---------------------------------------------------------------
    // Simetrik cift once TOPLANIYOR, sonra bir kez carpiliyor.
    // 11 dereceli filtre 11 degil 6 carpan kullaniyor.
    // Toplam bir bit buyuyor, o yuzden GIRIS_BIT+1.
    // ---------------------------------------------------------------
    wire signed [GIRIS_BIT:0] c0 = hat[0]  + hat[10];
    wire signed [GIRIS_BIT:0] c1 = hat[1]  + hat[9];
    wire signed [GIRIS_BIT:0] c2 = hat[2]  + hat[8];
    wire signed [GIRIS_BIT:0] c3 = hat[3]  + hat[7];
    wire signed [GIRIS_BIT:0] c4 = hat[4]  + hat[6];
    wire signed [GIRIS_BIT:0] c5 = {hat[5][GIRIS_BIT-1], hat[5]};

    localparam CARP_BIT = GIRIS_BIT + 1 + KAT_BIT;
    localparam TOP_BIT  = CARP_BIT + 3;      // 6 terim toplami: +3 bit

    reg signed [TOP_BIT-1:0] toplam;
    reg                      toplam_gecerli;

    always @(posedge clk) begin
        if (rst) begin
            toplam         <= {TOP_BIT{1'b0}};
            toplam_gecerli <= 1'b0;
        end else begin
            toplam <= $signed(c0) * H0 + $signed(c1) * H1 +
                      $signed(c2) * H2 + $signed(c3) * H3 +
                      $signed(c4) * H4 + $signed(c5) * H5;
            toplam_gecerli <= giris_gecerli;
        end
    end

    // ---------------------------------------------------------------
    // Olcekleme: katsayi toplami 2^15, o yuzden 15 bit geri kaydir.
    // Yuvarlayarak — DC sapmasi birakmamak icin.
    //
    // DOYURMA: telafi filtresi bant kenarinda 1'den BUYUK kazanc
    // veriyor (CIC'in kaybini geri veriyor). Tam olcege yakin bir
    // sinyal burada tasabilir. Tasan bir sayi sarip isaret degistirir
    // ve o, kirpmadan cok daha kotu bir bozulma uretir — kirpma
    // harmonik verir, sarma genis bantli gurultu verir.
    // ---------------------------------------------------------------
    localparam KAYDIR = 15;

    wire signed [TOP_BIT-1:0] yuvarlak =
        toplam + {{(TOP_BIT-KAYDIR){1'b0}}, 1'b1, {(KAYDIR-1){1'b0}}};
    wire signed [TOP_BIT-KAYDIR-1:0] olcekli = yuvarlak >>> KAYDIR;

    wire tasma_p, tasma_n;
    // DOYURMA YALNIZCA KORUMA BITI VARSA.
    // GIRIS_BIT 24'ten 17'ye inince TOP_BIT-KAYDIR = CIKIS_BIT oldu,
    // yani olceklenmis degerin cikistan fazla biti kalmadi ve
    // olcekli[22:23] gibi ters sirali bir dilim olustu — iverilog
    // hata verdi, yosys sessizce gecti. Sentezleyicinin sessiz
    // gecmesi hatanin yoklugu anlamina gelmiyor.
    //
    // Koruma biti yoksa tasma da olamaz: 17 bit giris, kazanci en
    // fazla 1.5 olan bir filtreden gecince 18 bit ediyor, cikis 24
    // bit. Yer bol.
    localparam KORUMA = TOP_BIT - KAYDIR - CIKIS_BIT;

    generate
    if (KORUMA > 0) begin : g_doyur
        wire t_p = !olcekli[TOP_BIT-KAYDIR-1] &&
                   |olcekli[TOP_BIT-KAYDIR-2 : CIKIS_BIT-1];
        wire t_n =  olcekli[TOP_BIT-KAYDIR-1] &&
                   ~&olcekli[TOP_BIT-KAYDIR-2 : CIKIS_BIT-1];
        assign tasma_p = t_p;
        assign tasma_n = t_n;
    end else begin : g_doyur_yok
        assign tasma_p = 1'b0;
        assign tasma_n = 1'b0;
    end
    endgenerate

    always @(posedge clk) begin
        if (rst) begin
            cikis         <= {CIKIS_BIT{1'b0}};
            cikis_gecerli <= 1'b0;
        end else begin
            if (tasma_p)
                cikis <= {1'b0, {(CIKIS_BIT-1){1'b1}}};
            else if (tasma_n)
                cikis <= {1'b1, {(CIKIS_BIT-1){1'b0}}};
            else
                cikis <= olcekli[CIKIS_BIT-1:0];
            cikis_gecerli <= toplam_gecerli;
        end
    end

endmodule

`default_nettype wire
