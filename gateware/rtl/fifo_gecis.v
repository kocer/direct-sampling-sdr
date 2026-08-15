// Saat alani gecis FIFO'su — Gray sayacli.
//
// clk_sys (80 MHz, VCXO'dan) ile clk_eth (125 MHz, PHY'den) ayri
// kaynaklar. Aralarinda tek bir flip-flop cifti koymak yetmez:
// iki saat yavas suruklenir ve zamanla ornek duser ya da tekrarlar.
// Dusen ornek paket sayacini bozmaz ama VERIYI bozar, ve o hata
// ancak spektrumda gorunur.
//
// GRAY SAYAC NEDEN: ikili sayac saat alani gecerken birden fazla
// biti ayni anda degistiriyor. Karsi taraf o gecis aninda okursa
// hicbir zaman var olmamis bir deger gorur — 0111 ile 1000 arasinda
// 1111 okuyabilir. Gray'de her adimda TEK bit degisiyor, yani en
// kotu durumda bir eski bir yeni deger okunur, ikisi de gecerli.
//
// DERINLIK IKININ KUVVETI OLMALI: sarma sayacin dogal sarmasiyla
// yapiliyor, modulo alinmiyor.

`default_nettype none

module fifo_gecis #(
    parameter GENISLIK = 8,
    parameter DERINLIK = 1024,
    parameter ADR = $clog2(DERINLIK)
) (
    input  wire                 yaz_clk,
    input  wire                 yaz_rst,
    input  wire [GENISLIK-1:0]  yaz_veri,
    input  wire                 yaz,
    output wire                 yaz_hazir,

    input  wire                 oku_clk,
    input  wire                 oku_rst,
    output wire [GENISLIK-1:0]  oku_veri,
    input  wire                 oku,
    output wire                 oku_gecerli,
    // okuma alanindaki doluluk — kac kelime hazir
    output wire [ADR:0]         oku_doluluk
);

    reg [GENISLIK-1:0] bellek [0:DERINLIK-1];

    // ---------------------------------------------------------------
    // DOLULUK — CERCEVEYE BASLAMADAN ONCE BAKILIYOR.
    //
    // RGMII bir kez cerceveye basladiginda DURAMAZ; PHY kesintisiz
    // akis bekliyor. Onceki halde verici FIFO bosalsa bile bayt
    // cekiyordu: bayat veri gidiyor, CRC onun uzerinden hesaplaniyor,
    // ve karsi taraf GECERLI ama YANLIS bir paket aliyordu. Sessiz
    // bozulma — ne kartta ne host'ta hata gorunur.
    //
    // Cozum store-and-forward: cerceveye ancak tam bir paket
    // tamponlandiginda basla. Onun icin okuma alaninda doluluk
    // gerekiyor.
    //
    // GRAY'DEN IKILIYE CEVIRIYORUZ. Senkronlanmis yazma isaretcisi
    // gray; cikarma yapmak icin ikiliye lazim. Cevrim bir XOR
    // zinciri: b[n] = g[n], b[i] = b[i+1] ^ g[i].
    // Sonuc EKSIK TARAFTA HATALI OLABILIR ama fazla tarafta degil:
    // senkronlayici gecikmesi yuzunden gercekte yazilmis olandan az
    // gorunur, cok degil. Yani "yeter mi" sorusuna verdigi cevap
    // her zaman guvenli tarafta.
    // ---------------------------------------------------------------

    // OKUMA TARAFI YAZMACLARI ONDE BILDIRILIYOR: yazma tarafindaki
    // dolu bayragi oku_gray'i, senkron okuma ise oku_sonraki'yi
    // kullanimdan once gormek zorunda.
    reg  [ADR:0] oku_ikili, oku_gray;
    reg  [ADR:0] yaz_gray_o1, yaz_gray_o2;
    // ISARETCI ARTISI ONCEDEN HESAPLANIYOR, MUX SONDA.
    //
    // Once "oku_ikili + (oku && oku_gecerli)" yaziyordu: 'oku'
    // toplayicinin ELDE GIRISINI suruyordu, yani 12 bitlik elde
    // zincirinin tamami onun arkasindaydi, ustune de gray XOR
    // biniyordu. 'oku' rgmii'nin durum makinesinden geliyor; sonuc
    // moduller arasi uzun bir yol ve clk_eth kapanmasi TOHUMA BAGLI
    // hale geldi (bir tohumda 129 MHz, otekinde 124).
    //
    // Iki olasilik da 'oku'dan BAGIMSIZ hesaplanabiliyor. Simdi 'oku'
    // sadece bir 2:1 cogullayici suruyor — tek LUT kademesi.
    wire [ADR:0] oku_arti1   = oku_ikili + 1'b1;
    wire [ADR:0] gray_simdi  = (oku_ikili >> 1) ^ oku_ikili;
    wire [ADR:0] gray_arti1  = (oku_arti1 >> 1) ^ oku_arti1;
    wire         oku_tuket   = oku && oku_gecerli;
    wire [ADR:0] oku_sonraki      = oku_tuket ? oku_arti1  : oku_ikili;
    wire [ADR:0] oku_gray_sonraki = oku_tuket ? gray_arti1 : gray_simdi;

    // ---------------------------------------------------------------
    // Yazma tarafi
    // ---------------------------------------------------------------
    reg [ADR:0] yaz_ikili, yaz_gray;
    reg [ADR:0] oku_gray_y1, oku_gray_y2;

    // DOLU BAYRAGI YAZMACTA, BIRLESIMSEL DEGIL.
    // "yaz_sonraki = yaz_ikili + (yaz && yaz_hazir)" ve
    // "yaz_hazir = ~dolu(yaz_sonraki)" birbirine bagli — birlesimsel
    // dongu. nextpnr zamanlama analizini reddetti; sentez sessizce
    // gecmisti. Cummings'in klasik tasarimi bayragi yazmacta tutuyor.
    reg dolu_r;
    // Yazma tarafinda da ayni: 'yaz' elde girisini degil cogullayiciyi
    // suruyor.
    wire [ADR:0] yaz_arti1      = yaz_ikili + 1'b1;
    wire [ADR:0] yaz_gray_simdi = (yaz_ikili >> 1) ^ yaz_ikili;
    wire [ADR:0] yaz_gray_arti1 = (yaz_arti1 >> 1) ^ yaz_arti1;
    wire         yaz_al         = yaz && ~dolu_r;
    wire [ADR:0] yaz_sonraki      = yaz_al ? yaz_arti1      : yaz_ikili;
    wire [ADR:0] yaz_gray_sonraki = yaz_al ? yaz_gray_arti1 : yaz_gray_simdi;

    always @(posedge yaz_clk) begin
        if (yaz_rst) begin
            yaz_ikili <= 0;
            yaz_gray  <= 0;
        end else begin
            if (yaz && yaz_hazir)
                bellek[yaz_ikili[ADR-1:0]] <= yaz_veri;
            yaz_ikili <= yaz_sonraki;
            yaz_gray  <= yaz_gray_sonraki;
        end
    end

    // okuma isaretcisini yazma alanina getir — IKI KADEME.
    // Tek kademe yeterli degil: ilk flip-flop yarikararli olabilir,
    // ikincisi ona yerlesme suresi tanir.
    always @(posedge yaz_clk) begin
        if (yaz_rst) begin
            oku_gray_y1 <= 0;
            oku_gray_y2 <= 0;
        end else begin
            oku_gray_y1 <= oku_gray;
            oku_gray_y2 <= oku_gray_y1;
        end
    end

    // dolu: gray'de ust iki bit ters, gerisi ayni
    always @(posedge yaz_clk) begin
        if (yaz_rst)
            dolu_r <= 1'b0;
        else
            dolu_r <= (yaz_gray_sonraki ==
                       {~oku_gray_y2[ADR:ADR-1], oku_gray_y2[ADR-2:0]});
    end
    assign yaz_hazir = ~dolu_r;

    // ---------------------------------------------------------------
    // Okuma tarafi
    // ---------------------------------------------------------------

    always @(posedge oku_clk) begin
        if (oku_rst) begin
            oku_ikili <= 0;
            oku_gray  <= 0;
        end else begin
            oku_ikili <= oku_sonraki;
            oku_gray  <= oku_gray_sonraki;
        end
    end

    always @(posedge oku_clk) begin
        if (oku_rst) begin
            yaz_gray_o1 <= 0;
            yaz_gray_o2 <= 0;
        end else begin
            yaz_gray_o1 <= yaz_gray;
            yaz_gray_o2 <= yaz_gray_o1;
        end
    end

    // ---------------------------------------------------------------
    // OKUMA SENKRON — YOKSA BLOK RAM'E DUSMUYOR.
    //
    // Once "assign oku_veri = bellek[oku_ikili]" yaziyordu, yani
    // ASENKRON okuma. ECP5'in blok RAM'i (DP16KD) asenkron okuma
    // yapamaz, o yuzden yosys butun 1024x8 bellegi DAGITIK RAM'e
    // acti: bin kadar LUT, ve okuma yolu bes kademelik bir mux
    // agaci. O agac dogrudan RGMII'nin bayt cogullayicisina
    // giriyordu ve ethernet alani 103 MHz'de kaliyordu — 1000BASE-T
    // 125 istiyor. Kartta 56 blok RAM'in SIFIRI kullaniliyordu.
    //
    // BIR SONRAKI ADRESTEN OKUYORUZ. Cikisi yazmaclamak normalde bir
    // cevrim gecikme demek; ama okuma isaretcisi zaten bu kenarda
    // oku_sonraki'ye guncelleniyor, yani ayni kenarda oku_sonraki
    // adresini okursak yazmacta HER ZAMAN gecerli isaretcinin verisi
    // durur. Disaridan bakinca gecikme yok.
    //
    // Okuma yokken oku_sonraki == oku_ikili, yani ayni adres her
    // cevrim yeniden okunuyor: FIFO bosken yazilan ilk kelime bir
    // cevrim sonra cikista beliriyor. bos bayragi zaten iki kademeli
    // senkronlayicinin ardindan geldigi icin veri cok onceden yerinde.
    reg [GENISLIK-1:0] oku_veri_r;
    always @(posedge oku_clk)
        oku_veri_r <= bellek[oku_sonraki[ADR-1:0]];

    // gray -> ikili
    integer gi;
    reg [ADR:0] yaz_ikili_o;
    always @(*) begin
        yaz_ikili_o[ADR] = yaz_gray_o2[ADR];
        for (gi = ADR - 1; gi >= 0; gi = gi - 1)
            yaz_ikili_o[gi] = yaz_ikili_o[gi+1] ^ yaz_gray_o2[gi];
    end

    // GRAY->IKILI CEVRIM AYRI BIR KADEMEDE.
    //
    // Cevrim seri bagimli bir XOR zinciri: b[n]=g[n], b[i]=b[i+1]^g[i].
    // 2048 derinlikte 11 kademe, ve ustune cikarma biniyordu. Hepsi
    // tek cevrimde olunca ethernet alani 121 MHz'te kaldi (125 gerek)
    // ve kapanma TOHUMA BAGLI hale geldi — bir tohumda geciyor,
    // otekinde gecmiyor. Sansa bagli bir kapanma kirilgandir: bir
    // sonraki degisiklik onu bozar ve sebebi anlasilmaz.
    //
    // Zinciri ve cikarmayi ayirinca ikisi de rahat siginiyor.
    // Bedeli bir cevrim daha gecikme; doluluk zaten cerceve
    // baslatma karari icin kullaniliyor, orada bir cevrim onemsiz.
    reg [ADR:0] yaz_ikili_r;
    always @(posedge oku_clk)
        if (oku_rst) yaz_ikili_r <= 0;
        else         yaz_ikili_r <= yaz_ikili_o;

    // DOLULUK YAZMACTA.
    // Gray'den ikiliye cevrim on bir kademeli bir XOR zinciri, ustune
    // cikarma, ustune de kullanan tarafta bir karsilastirma biniyordu:
    // hepsi tek cevrimde, ve ethernet alani 100 MHz'de kaliyordu
    // (125 gerek). Doluluk yavas degisen bir buyukluk — bir cevrim
    // gecikme, bir cerceve baslatma karari icin onemsiz.
    reg [ADR:0] doluluk_r;
    always @(posedge oku_clk)
        if (oku_rst) doluluk_r <= 0;
        else         doluluk_r <= yaz_ikili_r - oku_ikili;

    wire bos = (oku_gray == yaz_gray_o2);
    assign oku_gecerli = ~bos;
    assign oku_veri    = oku_veri_r;
    assign oku_doluluk = doluluk_r;

endmodule

`default_nettype wire
