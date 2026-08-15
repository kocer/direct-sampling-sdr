// Veris zinciri — taban banttan RF'e.
//
// Alisin tersi: ana bilgisayardan gelen karmasik taban bant ornegi
// once artiriliyor, sonra tasiyiciya bindiriliyor.
//
//   host -> tampon -> cic_artir -> nco + karistirici -> DAC
//
// AZALTMANIN TERSI DEGIL, AYNASI. Alista once karistirip sonra
// azaltiyoruz; veriste once artirip sonra karistiriyoruz. Sirayi
// ters cevirmek, artirmanin urettigi ayna goruntulerini tasiyicinin
// etrafina yayardi.
//
// CIC ARTIRICI: fark alici once, toplayici sonra — azaltmanin tam
// tersi sirasi. Girisler arasina sifir konuyor (sifir doldurma) ve
// CIC o sifirlari dolduruyor.
//
// KAZANC: azaltmada oldugu gibi (R*M)^N. Ama burada TASMA RISKI
// daha buyuk: giris tam olcege yakinsa toplayici zinciri hizla
// buyuyor. Azaltmada girisi ADC sinirliyordu; burada girisi ana
// bilgisayar veriyor ve o sinirli degil. Girise doyurma koyuyoruz.
//
// TEK KANAL: veriste dort kanal ayni anda tam guc vermiyor (tek PA
// var). Dort kanalli faz uyumlu veris icin bu modul dort kez
// ornekleniyor, ama simdilik bir tane yeterli ve kaynak butcesinde
// yer birakiyor.

`default_nettype none

module duc #(
    parameter GIRIS_BIT = 16,
    parameter DAC_BIT   = 14,
    parameter KADEME    = 4,
    parameter MAKS_R    = 2048
) (
    input  wire                        clk,
    input  wire                        rst,

    // taban bant giris (host'tan)
    input  wire signed [GIRIS_BIT-1:0] i_giris,
    input  wire signed [GIRIS_BIT-1:0] q_giris,
    input  wire                        giris_gecerli,
    output wire                        giris_hazir,

    input  wire [11:0]                 artir_orani,
    input  wire [31:0]                 faz_artis,
    // FAZ YUKLEME DISARIDAN. Once NCO'ya sabit sifir baglanmisti
    // ("faz_ofset(32'd0), yukle_ofset(1'b0)"). Tek kanalli veriste
    // zararsizdi ama dort kanalliya gecince ortaya cikti: kanal 0'in
    // fazi YUKLENEMEDIGI icin, diger uc kanal yuklendiginde kanal 0
    // kaldigi yerden devam ediyor ve aralarinda RASTGELE bir sabit
    // faz kaliyor. Olctum: uc kanalda da 90 derecelik ayni kayma.
    // Huzme acisi kanallar ARASI faza bagli, yani bu dogrudan
    // huzmenin yanlis yone bakmasi demek — ve her yuklemede farkli
    // bir yone.
    input  wire [31:0]                 faz_ofset,
    input  wire                        faz_yukle,

    // SAAT IZNI — ORNEK HIZI SAAT HIZI DEGIL.
    // Kart U31'i cogullanmis modda kullaniyor ve orada kanal basina
    // 40 MSPS cikiyor (dac_cogullu.v). Dort kanal AYNI hizda olmak
    // zorunda, yoksa aralarindaki faz iliskisi ornek bazinda kayar.
    // O yuzden butun veris zinciri 80 MHz saatte 40 MSPS kosuyor:
    // her ikinci cevrimde bir ilerliyor. Cikisi 80 MHz'te uretip her
    // ikincisini almak da olurdu ama o 2'ye bolme demek ve 20 MHz
    // ustu her sey banda katlanirdi.
    input  wire                        izin,

    output reg  signed [DAC_BIT-1:0]   dac,
    output reg                         dac_gecerli,

    // ARTIRILMIS TABAN BANT DISARI VERILIYOR.
    // Dort kanalli veriste dort kanal AYNI taban bandi tasiyor,
    // sadece tasiyicinin FAZI farkli — huzme yonlendirme bu.
    // Yani CIC'i dort kez kurmak bosuna: bir kez artir, dort kez
    // karistir. Kanal basina iki carpan, dordu icin sekiz; dort
    // ayri DUC kursaydik yirmi carpan giderdi ve ECP5-25F'te
    // yirmi sekiz tane var.
    output wire signed [15:0]          ic_i,
    output wire signed [15:0]          ic_q,
    output wire                        ic_gecerli
);

    localparam LOG2R  = $clog2(MAKS_R);
    localparam IC_BIT = GIRIS_BIT + (KADEME * LOG2R);

    // ---------------------------------------------------------------
    // Ornekleme sayaci: her R cevrimde bir yeni giris ornegi al,
    // arasina sifir koy.
    // ---------------------------------------------------------------
    reg [11:0] sayac;
    wire       yeni_ornek = (sayac == 12'd0);

    assign giris_hazir = yeni_ornek & izin;

    always @(posedge clk) begin
        if (rst)
            sayac <= 12'd0;
        else if (!izin)
            sayac <= sayac;
        else if (sayac >= artir_orani - 1)
            sayac <= 12'd0;
        else
            sayac <= sayac + 1'b1;
    end

    // ---------------------------------------------------------------
    // GIRISTE DOYURMA.
    // Alista girisi ADC sinirliyordu; burada ana bilgisayar veriyor
    // ve o sinirli degil. Tam olcegin ustunde bir deger CIC'in
    // toplayici zincirini sarar ve cikis anlamsizlasir — hem de
    // sessizce, cunku sarma bir hata bayragi uretmiyor.
    // Tam olcegin %90'inda kesiyoruz; kalan pay CIC'in gecici
    // asimlari icin.
    // ---------------------------------------------------------------
    localparam signed [GIRIS_BIT-1:0] TAVAN =
        (1 <<< (GIRIS_BIT - 1)) * 9 / 10 - 1;
    localparam signed [GIRIS_BIT-1:0] TABAN = -TAVAN;

    wire signed [GIRIS_BIT-1:0] i_kes =
        (i_giris > TAVAN) ? TAVAN : (i_giris < TABAN) ? TABAN : i_giris;
    wire signed [GIRIS_BIT-1:0] q_kes =
        (q_giris > TAVAN) ? TAVAN : (q_giris < TABAN) ? TABAN : q_giris;

    // ---------------------------------------------------------------
    // Sifir doldurma + fark alici zinciri (azaltmanin aynasi)
    // ---------------------------------------------------------------
    reg signed [IC_BIT-1:0] fark_g_i [0:KADEME-1];
    reg signed [IC_BIT-1:0] fark_c_i [0:KADEME-1];
    reg signed [IC_BIT-1:0] fark_g_q [0:KADEME-1];
    reg signed [IC_BIT-1:0] fark_c_q [0:KADEME-1];

    // HER ALWAYS BLOGUNUN KENDI DONGU DEGISKENI VAR.
    // Tek bir "integer k"yi iki blokta kullanmak sentezde iki
    // surucu demek: yosys "multiple conflicting drivers" veriyordu.
    // Donguler acildigi icin sonuc simdilik dogru cikiyor, ama
    // degisken sentezciye birakilmis bir kaza — ayni hatanin bir
    // baska turu test tezgahinda gercekten yanlis sonuc uretmisti.
    integer k;   // integratorler / birinci blok
    integer m;   // fark kademeleri / ikinci blok
    always @(posedge clk) begin
        if (rst) begin
            for (k = 0; k < KADEME; k = k + 1) begin
                fark_g_i[k] <= {IC_BIT{1'b0}};
                fark_c_i[k] <= {IC_BIT{1'b0}};
                fark_g_q[k] <= {IC_BIT{1'b0}};
                fark_c_q[k] <= {IC_BIT{1'b0}};
            end
        end else if (izin && yeni_ornek && giris_gecerli) begin
            fark_g_i[0] <= {{(IC_BIT-GIRIS_BIT){i_kes[GIRIS_BIT-1]}}, i_kes};
            fark_c_i[0] <= {{(IC_BIT-GIRIS_BIT){i_kes[GIRIS_BIT-1]}}, i_kes}
                           - fark_g_i[0];
            fark_g_q[0] <= {{(IC_BIT-GIRIS_BIT){q_kes[GIRIS_BIT-1]}}, q_kes};
            fark_c_q[0] <= {{(IC_BIT-GIRIS_BIT){q_kes[GIRIS_BIT-1]}}, q_kes}
                           - fark_g_q[0];
            for (k = 1; k < KADEME; k = k + 1) begin
                fark_g_i[k] <= fark_c_i[k-1];
                fark_c_i[k] <= fark_c_i[k-1] - fark_g_i[k];
                fark_g_q[k] <= fark_c_q[k-1];
                fark_c_q[k] <= fark_c_q[k-1] - fark_g_q[k];
            end
        end
    end

    // ---------------------------------------------------------------
    // Toplayici zinciri — TAM HIZDA (sifirlar burada doluyor)
    // ---------------------------------------------------------------
    reg signed [IC_BIT-1:0] topla_i [0:KADEME-1];
    reg signed [IC_BIT-1:0] topla_q [0:KADEME-1];

    always @(posedge clk) begin
        if (rst) begin
            for (m = 0; m < KADEME; m = m + 1) begin
                topla_i[m] <= {IC_BIT{1'b0}};
                topla_q[m] <= {IC_BIT{1'b0}};
            end
        end else if (izin) begin
            topla_i[0] <= topla_i[0] +
                          (yeni_ornek ? fark_c_i[KADEME-1] : {IC_BIT{1'b0}});
            topla_q[0] <= topla_q[0] +
                          (yeni_ornek ? fark_c_q[KADEME-1] : {IC_BIT{1'b0}});
            for (m = 1; m < KADEME; m = m + 1) begin
                topla_i[m] <= topla_i[m] + topla_i[m-1];
                topla_q[m] <= topla_q[m] + topla_q[m-1];
            end
        end
    end

    // OLCEKLEME AZALTMANINKIYLE AYNI DEGIL.
    //
    // CIC azalticinin kazanci (R*M)^N. Ama ARTIRICININ kazanci
    //     (R*M)^N / R = R^(N-1) * M^N
    // cunku sifir doldurma girisin enerjisini R'ye boluyor.
    //
    // Azaltmanin tablosunu oldugu gibi kullanmistim ve log2(R) bit
    // fazla kaydiriyordu. Olculdu: 8000 birimlik girise DAC'ta
    // sadece +-125 cikti, yani tam olcegin %1.5'i. 36 dB dinamik
    // aralik cope gidiyordu — ve bu, cikis "calisiyor" gorundugu
    // icin fark edilmesi zor bir hata.
    //
    // Dogrusu (N-1) * log2(R).
    function [5:0] kaydirma;
        input [11:0] r;
        begin
            if      (r <= 12'd1)    kaydirma = 6'd0;
            else if (r <= 12'd2)    kaydirma = (KADEME-1) * 1;
            else if (r <= 12'd4)    kaydirma = (KADEME-1) * 2;
            else if (r <= 12'd8)    kaydirma = (KADEME-1) * 3;
            else if (r <= 12'd16)   kaydirma = (KADEME-1) * 4;
            else if (r <= 12'd32)   kaydirma = (KADEME-1) * 5;
            else if (r <= 12'd64)   kaydirma = (KADEME-1) * 6;
            else if (r <= 12'd128)  kaydirma = (KADEME-1) * 7;
            else if (r <= 12'd256)  kaydirma = (KADEME-1) * 8;
            else if (r <= 12'd512)  kaydirma = (KADEME-1) * 9;
            else if (r <= 12'd1024) kaydirma = (KADEME-1) * 10;
            else                    kaydirma = (KADEME-1) * 11;
        end
    endfunction

    // KAYDIRMA MIKTARI YAZMACTA — cic_azalt.v ile ayni gerekce.
    // Oncelik zinciri + barrel shifter tek cevrime sigmiyordu ve
    // artir_orani host yazmadikca degismiyor.
    reg [5:0] kaydir;
    always @(posedge clk)
        if (rst)      kaydir <= 6'd0;
        else if (izin) kaydir <= kaydirma(artir_orani);

    wire signed [IC_BIT-1:0] ci = topla_i[KADEME-1] >>> kaydir;
    wire signed [IC_BIT-1:0] cq = topla_q[KADEME-1] >>> kaydir;

    // ---------------------------------------------------------------
    // DOYURARAK KES — ALT BITLERI ALMA.
    //
    // Karistiriciya "$signed(ci[15:0])" giriyordu, yani genis sonucun
    // ALT 16 BITI. Assaydi alt bitler sarar ve ISARET DONERDI:
    // +tam olcek bir ornek -tam olcek olur, cikan sey gurultu gibi
    // degil MAKUL BIR SINYAL gibi gorunur.
    //
    // OLCTUM: SU ANDA ASMIYOR. Tam olcek ustu girisle (32000) ve
    // oran 2/4/16/64'te |ci| en fazla 29490 cikiyor, 16 bit siniri
    // 32767. Kaydirma telafisi dogru calisiyor, yani bu bir CANLI
    // HATA DEGIL — denetimde teorik olarak isaretlenmisti, olcunce
    // tetiklenmedigi goruldu.
    //
    // YINE DE DOYURUYORUZ, cunku pay %10. GIRIS_BIT, KADEME ya da
    // olcekleme birazcik degisirse sinir asilir ve o gun kimse
    // burayi hatirlamaz. Bedeli birkac LUT; karsiliginda en kotu
    // ihtimal "tepede duz kirpilmis cikis" oluyor — bozulma var ama
    // isaret dogru, urun bandin icinde.
    function signed [15:0] doyur16;
        input signed [IC_BIT-1:0] x;
        begin
            if      (x >  $signed({{(IC_BIT-16){1'b0}}, 16'sh7FFF}))
                doyur16 =  16'sh7FFF;
            else if (x <  $signed({{(IC_BIT-16){1'b1}}, 16'sh8000}))
                doyur16 =  16'sh8000;
            else
                doyur16 = x[15:0];
        end
    endfunction

    wire signed [15:0] ci_d = doyur16(ci);
    wire signed [15:0] cq_d = doyur16(cq);

    assign ic_i       = ci_d;
    assign ic_q       = cq_d;
    assign ic_gecerli = izin;   // artirilmis akis izinli cevrimlerde

    // ---------------------------------------------------------------
    // NCO + karistirici: taban bandi tasiyiciya bindir
    //     dac = I*cos(wt) - Q*sin(wt)
    // ---------------------------------------------------------------
    wire signed [15:0] nco_s, nco_c;

    nco u_nco (
        .clk(clk), .rst(rst),
        .faz_artis(faz_artis), .faz_ofset(faz_ofset), .yukle_ofset(faz_yukle),
        .izin(izin),
        .sin_cik(nco_s), .cos_cik(nco_c)
    );

    localparam MIX_BIT = 16 + 16;

    reg signed [MIX_BIT-1:0] mix;
    always @(posedge clk) begin
        if (rst)
            mix <= {MIX_BIT{1'b0}};
        else if (izin)
            mix <= ci_d * nco_c - cq_d * nco_s;
    end

    // MIX_BIT'ten DAC_BIT'e, yuvarlayarak
    localparam MKAYDIR = MIX_BIT - DAC_BIT - 1;

    wire signed [MIX_BIT-1:0] yuvarlak =
        mix + {{(MIX_BIT-MKAYDIR){1'b0}}, 1'b1, {(MKAYDIR-1){1'b0}}};

    always @(posedge clk) begin
        if (rst) begin
            dac         <= {DAC_BIT{1'b0}};
            dac_gecerli <= 1'b0;
        end else if (izin) begin
            dac         <= yuvarlak[MKAYDIR +: DAC_BIT];
            dac_gecerli <= 1'b1;
        end
    end

endmodule

`default_nettype wire
