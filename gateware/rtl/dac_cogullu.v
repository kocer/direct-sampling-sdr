// AD9767 COGULLANMIS mod arayuzu — U31 icin.
//
// Kartta iki AD9767 var ve IKISI FARKLI MODDA:
//   U30  MODE pini +3V3'e  -> CIFT PORT: iki ayri 14 bitlik yol,
//                             WRT1 ve WRT2. dac_cikis.v bunu suruyor.
//   U31  MODE pini GND'ye  -> COGULLANMIS: TEK 14 bitlik yol, iki
//                             kanal sirayla, IQSEL hangisine
//                             yazildigini soyluyor.
//
// Bu modul U31 icin. Ayni modulu ikisine birden kullanamayiz cunku
// protokol farkli — ayni parcanin iki farkli modu, ve kart bunlari
// KASITLI olarak boyle secmis: U30'un iki portu bagimsiz iki TX
// kanali veriyor, U31'in cogullanmis modu ise tek veri yoluyla iki
// kanal daha veriyor ve FPGA'da 14 pin tasarruf ediyor.
//
// ---------------------------------------------------------------------
// HIZ: IKI EVRE, DORT DEGIL. ONCEKI SURUM YARIM HIZDAYDI.
//
// Ilk yazdigimda dort evre kullaniyordum (I ver / I yaz / Q ver /
// Q yaz) ve modul basligina "her kanal 40 MSPS" yazmistim. YANLIS:
// dort evre 80 MHz'te bir (I,Q) cifti icin 50 ns demek, yani kanal
// basina 20 MSPS. Nyquist 10 MHz — 40 m bandi bile gecmez. Yorum
// dogru sanildigi icin hata sentezde de testte de gorunmuyordu;
// evre sayisini ELLE carpip kontrol edince cikti.
//
// Iki evrenin calismasinin sebebi IQWRT'nin ODDR'dan uretilmesi:
//   veri  posedge'de degisiyor
//   IQWRT negedge'de YUKSELIYOR   (ODDR: D0=0, D1=1)
// Boylece her saat cevriminde bir yazma oluyor, IQWRT 80 MHz, kanal
// basina 40 MSPS. Kurulum suresi yarim cevrim = 6.25 ns; AD9767
// 2.0 ns istiyor. Tutma suresi de yarim cevrim = 6.25 ns; 1.5 ns
// isteniyor. Ikisi de genis paylar.
//
// DAHA HIZLI OLMUYOR. Kanal basina 80 MSPS icin IQWRT 160 MHz
// gerekirdi. Kart bunu kaldirir — DAC2 veri yolunun 14 hattinda
// ped-ped uzunluk yayilimi 1.9 mm, yaklasik 13 ps, 6.25 ns'lik goz
// yaninda hicbir sey (bu sayiyi ölçtüm, varsaymadim). Sinir CIPTE:
// AD9767 125 MSPS'lik bir parca ve 160 MHz yazma hizi veri sayfasi
// sinirinin ustunde. O yuzden TX ornek hizi dort kanalda da 40 MSPS.
//
// SONUC — BU KARTIN TX YETENEGI: dort kanalli huzme yonlendirme
// Nyquist 20 MHz'e kadar, yani 160 m'den 17 m'ye. 15/12/10 m'de
// dort kanalli calisilamaz. Iki kanalli (sadece U30, cift port,
// 80 MSPS) tum HF'yi kapsiyor. Bu bir KART kisiti, gateware degil;
// bir sonraki revizyonda U31 yerine ikinci bir cift-port AD9767
// konmasi cozer (14 FPGA pini daha ister).
// ---------------------------------------------------------------------
//
// IQSEL POLARITESI KAYITTAN. Veri sayfasindan okuyup sabitlemek
// yerine bir kayit biti; yanlissa iki kanal yer degistirir ve bu,
// huzmenin yanlis yone bakmasi olarak cikar — kartta duzeltmesi
// imkansiz, bir bitle duzeltmesi bedava.
//
// ORNEK_I / ORNEK_Q ADLARI: bunlar bir karmasik sinyalin I ve Q'su
// DEGIL, iki BAGIMSIZ RF kanali (dizinin 3. ve 4. anteni). Adlar
// cipin bacak adlarindan geliyor.

`default_nettype none

module dac_cogullu #(
    parameter BIT = 14
) (
    input  wire                   clk,
    input  wire                   rst,

    input  wire signed [BIT-1:0]  ornek_i,      // kanal 3
    input  wire signed [BIT-1:0]  ornek_q,      // kanal 4
    input  wire                   ornek_gecerli,
    input  wire                   iqsel_ters,   // kanal sirasi

    output reg  [BIT-1:0]         dac_d,
    // IQWRT ODDR'dan cikiyor: ust.v'de ODDRX1F(.D0(iqwrt_yuk),
    // .D1(iqwrt_dus)). Modul icinde primitif kullanmiyoruz ki test
    // yalin Verilog'la kosabilsin — rgmii_veris.v ile ayni yol.
    output wire                   iqwrt_yuk,
    output wire                   iqwrt_dus,
    output reg                    iqsel,
    output reg                    iqreset,
    output wire                   hazir         // yeni ornek alabilir
);

    // ISARETLIDEN OFSET IKILIYE — dac_cikis.v ile ayni gerekce.
    // DAC 0..16383 isaretsiz bekliyor, orneklerimiz isaretli.
    wire [BIT-1:0] ofs_i = {~ornek_i[BIT-1], ornek_i[BIT-2:0]};

    // IQWRT SUREKLI KOSUYOR. Yeni ornek gelmediginde de yazma darbesi
    // cikiyor ve o an veri yolunda ne varsa AYNI mandala tekrar
    // yaziliyor — icerik degismedigi icin zararsiz. Darbeyi kosullu
    // yapmak IQWRT'yi ODDR'dan cikarmayi bozardi ve kurulum payini
    // yeniden hesaplamak gerekirdi.
    assign iqwrt_yuk = 1'b0;    // saatin YUKSEK yarisinda dusuk
    assign iqwrt_dus = 1'b1;    // ALCAK yarisinda yuksek -> negedge'de yukselen kenar

    // Iki evre: kanal 3 ver / kanal 4 ver. Yazma kenarlari aralarinda.
    localparam E_I = 1'b0;
    localparam E_Q = 1'b1;

    reg evre;
    reg signed [BIT-1:0] tut_q;

    // Yeni cift SADECE I evresinde aliniyor; boylece iki kanal AYNI
    // ornekleme aninin degerlerini tasiyor. Ayri anlarda alinsaydi
    // aralarinda yarim ornek gecikme olur ve huzme acisi kayardi.
    assign hazir = (evre == E_I);

    // ---------------------------------------------------------------
    // IQRESET: ic kanal isaretcisini sifirliyor.
    //
    // Sifirlamadan sonra BIR KEZ veriliyor. Verilmezse cipin ic
    // isaretcisi bizimkiyle ters baslayabiliyor ve iki kanal kalici
    // olarak yer degistiriyor — yine yanlis huzme, yine aranmasi zor.
    // ---------------------------------------------------------------
    reg reset_verildi;

    always @(posedge clk) begin
        if (rst) begin
            evre          <= E_I;
            iqsel         <= 1'b0;
            iqreset       <= 1'b1;      // sifirlamada aktif
            dac_d         <= {BIT{1'b0}};
            tut_q         <= {BIT{1'b0}};
            reset_verildi <= 1'b0;
        end else if (!reset_verildi) begin
            // sifirlamadan cikarken tek darbe
            iqreset       <= 1'b0;
            reset_verildi <= 1'b1;
            evre          <= E_I;
        end else begin
            iqreset <= 1'b0;
            case (evre)
            E_I: begin
                if (ornek_gecerli) begin
                    tut_q <= ornek_q;
                    dac_d <= ofs_i;
                    iqsel <= ~iqsel_ters;   // kanal 3
                    evre  <= E_Q;
                end
            end
            E_Q: begin
                dac_d <= {~tut_q[BIT-1], tut_q[BIT-2:0]};
                iqsel <= iqsel_ters;        // kanal 4
                evre  <= E_I;
            end
            endcase
        end
    end

endmodule

`default_nettype wire
