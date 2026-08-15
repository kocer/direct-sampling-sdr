// Dort kanalli veris — huzme yonlendirmeli.
//
// Dort kanal AYNI taban bandi tasiyor, sadece tasiyicinin FAZI
// farkli. Huzme yonlendirme tam olarak bu: dort antene ayni sinyali
// farkli fazlarla verince isima yonu degisiyor. Alis tarafinin
// aynasi (ddc_dort.v), orada da dort kanal ayni ADC saatinden
// besleniyor ve NCO faz ofsetleriyle ayriliyor.
//
// CIC BIR KEZ, KARISTIRICI DORT KEZ. Dort ayri DUC kurmak yirmi
// carpan yerdi; ECP5-25F'te yirmi sekiz tane var ve on altisi
// aliciya gidiyor. Taban bant ayni oldugu icin artirmayi paylasmak
// bedava: bir DUC (kanal 0) hem artiriyor hem karistiriyor, kalan
// uc kanal onun artirilmis cikisini kendi NCO'suyla karistiriyor.
// Toplam sekiz carpan.
//
// FAZ OFSETLERI AYNI ANDA YUKLENIYOR. Dort kanalin fazi tek tek
// degisirse gecis sirasinda huzme saga sola atliyor; kayit dosyasi
// dorduncu ofset yazildiginda hepsini birden uyguluyor (nco_yukle).
//
// KANAL 0'IN NCO'SU DUC'UN ICINDE. Disaridan bakildiginda dort
// kanal esit gorunuyor ama kanal 0'in faz ofseti duc.v'ye degil
// buraya bagli degil — o yuzden kanal 0 REFERANS kabul ediliyor ve
// ofseti her zaman sifir. Huzme acisi zaten kanallar ARASI farkla
// belirleniyor, mutlak fazla degil.

`default_nettype none

module duc_dort #(
    parameter GIRIS_BIT = 16,
    parameter DAC_BIT   = 14
) (
    input  wire                        clk,
    input  wire                        rst,

    input  wire signed [GIRIS_BIT-1:0] i_giris,
    input  wire signed [GIRIS_BIT-1:0] q_giris,
    input  wire                        giris_gecerli,
    output wire                        giris_hazir,

    input  wire [11:0]                 artir_orani,
    input  wire [31:0]                 faz_artis,
    input  wire [31:0]                 faz_ofset1,
    input  wire [31:0]                 faz_ofset2,
    input  wire [31:0]                 faz_ofset3,
    input  wire                        faz_yukle,
    // Saat izni — bkz. duc.v. Dort kanal AYNI izinle ilerliyor;
    // ayri ayri olsaydi aralarinda bir cevrimlik sabit kayma
    // kalabilirdi ve 40 MSPS'te bu 25 ns, 14 MHz'te 126 derece.
    input  wire                        izin,

    output wire signed [DAC_BIT-1:0]   dac0,
    output wire signed [DAC_BIT-1:0]   dac1,
    output wire signed [DAC_BIT-1:0]   dac2,
    output wire signed [DAC_BIT-1:0]   dac3,
    output wire                        dac_gecerli
);

    // ---------------------------------------------------------------
    // Kanal 0: artirma + karistirma (referans faz)
    // ---------------------------------------------------------------
    wire signed [15:0] ic_i, ic_q;
    wire               ic_gecerli;

    duc #(.GIRIS_BIT(GIRIS_BIT), .DAC_BIT(DAC_BIT)) u_duc0 (
        .clk(clk), .rst(rst),
        .i_giris(i_giris), .q_giris(q_giris),
        .giris_gecerli(giris_gecerli), .giris_hazir(giris_hazir),
        .artir_orani(artir_orani), .faz_artis(faz_artis),
        // Kanal 0 REFERANS: ofseti sifir, ama YUKLENIYOR — dortu de
        // ayni anda sifirlanmazsa aralarinda rastgele sabit faz kalir.
        .faz_ofset(32'd0), .faz_yukle(faz_yukle), .izin(izin),
        .dac(dac0), .dac_gecerli(dac_gecerli),
        .ic_i(ic_i), .ic_q(ic_q), .ic_gecerli(ic_gecerli)
    );

    // ---------------------------------------------------------------
    // Kanal 1..3: ayni taban bant, kendi NCO'su
    // ---------------------------------------------------------------
    wire [31:0] ofset [1:3];
    assign ofset[1] = faz_ofset1;
    assign ofset[2] = faz_ofset2;
    assign ofset[3] = faz_ofset3;

    wire signed [DAC_BIT-1:0] dac_k [1:3];
    assign dac1 = dac_k[1];
    assign dac2 = dac_k[2];
    assign dac3 = dac_k[3];

    genvar g;
    generate
    for (g = 1; g <= 3; g = g + 1) begin : kanal
        wire signed [15:0] s, c;

        nco u_nco (
            .clk(clk), .rst(rst),
            .faz_artis(faz_artis),
            .faz_ofset(ofset[g]), .yukle_ofset(faz_yukle), .izin(izin),
            .sin_cik(s), .cos_cik(c)
        );

        // dac = I*cos - Q*sin
        reg signed [31:0] mix;
        always @(posedge clk) begin
            if (rst)       mix <= 32'sd0;
            else if (izin) mix <= ic_i * c - ic_q * s;
        end

        // OLCEKLEME KANAL 0 ILE BIREBIR AYNI — YUVARLAMA DAHIL.
        //
        // Once duz kesiyordum (mix[30-:14]); kanal 0 ise duc.v icinde
        // YUVARLIYOR. Aradaki fark en fazla bir LSB, ama tam da
        // onemsememem gereken yer burasi degil: dort kanalin genligi
        // bire bir tutmali, yoksa fazlar dogru olsa bile huzme sekli
        // bozulur. Bir LSB'lik sistematik fark dort antenin birinde
        // kalici genlik hatasi demek.
        localparam MKAYDIR = 32 - DAC_BIT - 1;   // duc.v ile ayni
        wire signed [31:0] yuvarlak =
            mix + {{(32-MKAYDIR){1'b0}}, 1'b1, {(MKAYDIR-1){1'b0}}};

        reg signed [DAC_BIT-1:0] cik;
        always @(posedge clk) begin
            if (rst)       cik <= {DAC_BIT{1'b0}};
            else if (izin) cik <= yuvarlak[MKAYDIR +: DAC_BIT];
        end
        assign dac_k[g] = cik;
    end
    endgenerate

endmodule

`default_nettype wire
