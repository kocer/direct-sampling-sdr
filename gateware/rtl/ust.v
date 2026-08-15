// SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
// SPDX-License-Identifier: GPL-3.0-only
// Ust modul — butun zinciri birlestirir.
//
//   ADC -> DDC (4 kanal) -> paketleyici -> RGMII -> host
//   host -> kayit -> NCO/CIC ayarlari, kontrol zinciri
//   kayit -> DUC -> DAC
//
// SDRAM VE DPD HENUZ YOK. Ikisi de calisan bir alici icin sart
// degil: SDRAM tamponu ethernet tikandiginda veri saklamak icin,
// DPD ise verisin dogrusalligini artirmak icin. Once uctan uca
// calisan en kucuk sistemi kuruyoruz, sonra ustune ekliyoruz.
//
// SAAT ALANLARI:
//   clk_adc   ADC'nin DCO'su, 80 MHz — DDC on ucu
//   clk_sys   VCXO -> PLL, 80 MHz — DDC arkasi, kontrol
//   clk_eth   RGMII, 125 MHz — ethernet
//
// clk_adc ile clk_sys ayni frekansta ama AYRI KAYNAKLARDAN. Aralarini
// FIFO ile geciyoruz; elle senkronlayici koymak, iki saat arasinda
// yavas suruklenme oldugunda ornek kaybettirir ve o kayip faz
// surekliligini bozar.

`default_nettype none

module ust (
    // saatler
    input  wire        clk_sys,       // 80 MHz, VCXO'dan (VCXO_CLK)

    // ADC 1 (iki kanal, tek veri yolunda cogullanmis)
    input  wire        adc1_dco,
    input  wire [13:0] adc1_d,
    input  wire        adc1_or,
    // ADC 2
    input  wire        adc2_dco,
    input  wire [13:0] adc2_d,
    input  wire        adc2_or,

    // DAC
    // DORT VERIS KANALI, IKI CIP.
    //   U30 (cift port) : kanal 0 -> P1/WRT1,  kanal 1 -> P2/WRT2
    //   U31 (cogullanmis): kanal 2 ve 3 tek yolda, IQSEL ayiriyor
    output wire [13:0] dac_a,
    output wire        dac_wrt_a,
    output wire [13:0] dac_b,
    output wire        dac_wrt_b,
    output wire [13:0] dac2_d,
    output wire        dac2_iqwrt,
    output wire        dac2_iqsel,
    output wire        dac2_iqreset,

    // RGMII veris
    output wire [3:0]  rgmii_td,
    output wire        rgmii_tctl,
    output wire        rgmii_tclk,

    // RGMII ALIS — host'tan kayit yazmalari.
    // Saat PHY'den geliyor (rgmii_rxc) ve bizim clk_eth'imizle
    // arasinda faz iliskisi YOK; alis mantigi kendi alaninda
    // calisiyor, cikisi FIFO ile clk_sys'e geciyor.
    input  wire [3:0]  rgmii_rd,
    input  wire        rgmii_rctl,
    input  wire        rgmii_rxc,

    // kontrol zinciri
    output wire        rly_ser,
    output wire        rly_srclk,
    output wire        rly_rclk,
    output wire        pa_inhibit,

    // durum LED'leri (aktif dusuk)
    output wire        led_status,
    output wire        led_rx,
    output wire        led_tx,
    output wire        led_data,

    // hata ayiklama UART'i (DBG_RX / DBG_TX)
    input  wire        dbg_rx,
    output wire        dbg_tx,

    // ---------------------------------------------------------------
    // SPI — IKI AYRI YOL.
    //
    // Kart ici ADC yolu: ADC_SCLK + ADC_SDIO (cift yonlu), secim
    // ADC1/2_nCSB. Cevre yolu: ATT_CLK (saat) + ATT_DATA (cikis),
    // ve DONUS YOLU YINE ADC_SDIO — iki yol o hatti PAYLASIYOR.
    // O yuzden ikisi ayni anda kullanilamaz; cevre yolundan okurken
    // AD9251'lerin CSB'si yukselde kalmali, yoksa iki cihaz ayni
    // hatti surer.
    //
    // BUNLARIN HICBIRI SURULMUYORDU. Kartta cekili duruyorlardi ama
    // gateware'de karsiligi yoktu: ADC cogullanmis moda alinamiyor,
    // zayiflaticilar ayarlanamiyor, PA bias'i yazilamiyor, PHY
    // resetten cikmiyordu.
    // ---------------------------------------------------------------
    output wire        adc_sclk,
    inout  wire        adc_sdio,
    output wire        adc1_ncsb,
    output wire        adc2_ncsb,
    output wire        adc_sync,

    output wire        att_clk,
    output wire        att_data,
    output wire        att1_le,
    output wire        att2_le,
    output wire        att3_le,
    output wire        att4_le,
    output wire        pa_att_le,
    output wire        bias_cs1,
    output wire        bias_cs2,
    output wire        pa_adc_cs,

    output wire        phy1_nrst,
    output wire        phy2_nrst,

    // PHY yonetim arayuzu (iki PHY ortak hatti paylasiyor,
    // adresle ayriliyorlar: strap ile 0 ve 1)
    output wire        mdc,
    inout  wire        mdio_hat
);

    // ---------------------------------------------------------------
    // SIFIRLAMA ICERDE URETILIYOR.
    //
    // rst_n ust duzey giris portuydu ama kartta ona karsilik gelen
    // bir ag YOK — buton da yok. Sentezci onu sabit kabul eder ve
    // sifirlama mantiginin bir kismini atardi; gercek kartta ise
    // yazmaclar konfigurasyondan sonra bilinmeyen durumda kalirdi.
    //
    // Yapilandirma bittiginde ECP5 zaten GSR uyguluyor. Ustune 4096
    // cevrim (~51 us) bekletiyoruz: PLL kilitlenene kadar tureyen
    // saatler kararsiz, o sirada calisan mantik cop uretir.
    reg [12:0] por = 13'd0;
    always @(posedge clk_sys)
        if (!por[12]) por <= por + 1'b1;

    wire rst = ~por[12];

    // ---------------------------------------------------------------
    // ETHERNET SAATI PLL'DEN — KARTTA 125 MHz OSILATOR YOK.
    //
    // clk_eth ust modulde giris portuydu ve hicbir seye baglanmiyordu:
    // kartta o frekansta bir kaynak yok, RGMII'de GTX_CLK'yi MAC
    // uretiyor (PHY1_TXC bizim CIKISIMIZ). Yani ethernet hic
    // calismazdi ve bunun kartta gorunur bir belirtisi olmazdi —
    // baglanti kurulmaz, sebep aranir.
    //
    // 80 -> 125 MHz = 25/16. EHXPLLL:
    //   fPFD = 80 / CLKI_DIV(16)              =   5 MHz
    //   fVCO = fPFD * CLKFB_DIV(25) * DIV(5)  = 625 MHz   (400-800 ✓)
    //   CLKOP = fVCO / 5                      = 125 MHz
    //
    // fPFD 5 MHz dusuk, yani dongu bant genisligi dar ve VCO
    // gurultusunun daha cogu geciyor. RGMII icin sorun degil: veri
    // penceresi nanosaniye mertebesinde. ADC saatine BU PLL'I
    // KARISTIRMIYORUZ — orada jitter dogrudan SNR tavani, ve VCXO
    // 60 fs'i PLL'den gecirmek onu yuz kat bozardi.
    //
    // TXC'YE FAZ KAYDIRMASI YOK — GECIKMEYI PHY URETIYOR.
    //
    // Once CLKOS'tan +90 derece (2 ns) kaydirilmis bir saat
    // uretiyordum. Kartta olctum: R602/R603 (ve PHY2'de R618/R619)
    // 1k ile +1V8'e cekiyor, RTL8211F'te RXD1 = TXDLY, RXD0 = RXDLY
    // ve YUKSEK demek "2 ns ic gecikme ACIK" demek. Yani gecikme iki
    // kez sayiliyordu: 2 + 2 = 4 ns, 8 ns'lik periyodun yarisi.
    // Baglanti kalkar, paketler sessizce duser ya da bozulur.
    //
    // Kartin strap'i tek gercek kaynak; gateware ona uyuyor.
    // ---------------------------------------------------------------
    wire clk_eth;        // 125 MHz
    wire pll_kilit;

    (* FREQUENCY_PIN_CLKI  = "80"  *)
    (* FREQUENCY_PIN_CLKOP = "125" *)
    (* ICP_CURRENT = "12" *) (* LPF_RESISTOR = "8" *)
    EHXPLLL #(
        .CLKI_DIV(16), .CLKFB_DIV(25),
        .FEEDBK_PATH("CLKOP"),
        .CLKOP_ENABLE("ENABLED"), .CLKOP_DIV(5),
        .CLKOP_CPHASE(4), .CLKOP_FPHASE(0),
        .CLKOS_ENABLE("DISABLED"),
        .INTFB_WAKE("DISABLED"), .STDBY_ENABLE("DISABLED"),
        .PLLRST_ENA("DISABLED"), .DPHASE_SOURCE("DISABLED")
    ) u_pll (
        .CLKI(clk_sys), .CLKFB(clk_eth),
        .CLKOP(clk_eth),
        .RST(1'b0), .STDBY(1'b0),
        .PHASESEL0(1'b0), .PHASESEL1(1'b0),
        .PHASEDIR(1'b0), .PHASESTEP(1'b0), .PHASELOADREG(1'b0),
        .PLLWAKESYNC(1'b0), .ENCLKOP(1'b0),
        .LOCK(pll_kilit)
    );

    // ---------------------------------------------------------------
    // ADC arayuzleri
    // ---------------------------------------------------------------
    wire [13:0] a1_a, a1_b, a2_a, a2_b;
    wire        a1_gecerli, a2_gecerli, a1_hizali, a2_hizali;
    wire        a1_takas, a2_takas;
    wire        a1_asim_a, a1_asim_b, a2_asim_a, a2_asim_b;
    wire        clk_adc1, clk_adc2;

    // ASIM (over-range) DORT KANALDAN DA TOPLANIYOR.
    // Onceki halde paketleyiciye sabit sifir gidiyordu, yani ADC
    // dolduysa host bunu hic ogrenmiyordu. Kirpilmis bir ornek
    // spektrumda gercek gibi duran sahte urunler uretir.
    wire        adc_asim = a1_asim_a | a1_asim_b | a2_asim_a | a2_asim_b;

    adc_giris u_adc1 (
        .dco(adc1_dco), .d(adc1_d), .asim(adc1_or),
        .desen_a(adc_desen_a), .desen_b(adc_desen_b),
        .desen_dene(adc_desen_dene),
        .clk_adc(clk_adc1),
        .ornek_a(a1_a), .ornek_b(a1_b),
        .asim_a(a1_asim_a), .asim_b(a1_asim_b),
        .ornek_gecerli(a1_gecerli),
        .takas(a1_takas), .hizali(a1_hizali)
    );

    adc_giris u_adc2 (
        .dco(adc2_dco), .d(adc2_d), .asim(adc2_or),
        .desen_a(adc_desen_a), .desen_b(adc_desen_b),
        .desen_dene(adc_desen_dene),
        .clk_adc(clk_adc2),
        .ornek_a(a2_a), .ornek_b(a2_b),
        .asim_a(a2_asim_a), .asim_b(a2_asim_b),
        .ornek_gecerli(a2_gecerli),
        .takas(a2_takas), .hizali(a2_hizali)
    );

    // ---------------------------------------------------------------
    // Hata ayiklama UART'i -> kayit dosyasi
    //
    // TEK KONTROL YOLU BU. Ethernet ALIS yolu henuz yok; onsuz
    // kayitlara yazacak hicbir sey olmadigi icin NCO frekansi,
    // azaltma orani, kanal maskesi ayarlanamazdi. Ethernet alisi
    // yazildiktan sonra da bu yol duruyor: ethernet bozuldugunda
    // bakacak bagimsiz bir kapi gerekiyor.
    //
    // 1 Mbaud. 80 MHz / 80 = tam bolme, yani baud hatasi SIFIR.
    // 115200 secseydik bolen 694.4 cikardi ve %0.06 hata olurdu —
    // kabul edilebilir ama bedava degilken neden odeyelim.
    // ---------------------------------------------------------------
    wire [7:0]  uart_al_bayt, uart_ver_bayt;
    // Host bayt kaynagi (UART ya da ethernet) — SECIM ASAGIDA,
    // bildirim burada: kullanildigi yer (host_arayuz) yukarida.
    wire [7:0]  host_bayt;
    wire        host_gecerli;
    wire        uart_al_gecerli, uart_ver_gonder, uart_ver_mesgul;
    wire [7:0]  kayit_adr;
    wire [31:0] kayit_veri;
    wire        kayit_yaz;

    uart_al #(.BOLEN(80)) u_uart_al (
        .clk(clk_sys), .rst(rst), .rx(dbg_rx),
        .bayt(uart_al_bayt), .gecerli(uart_al_gecerli)
    );

    uart_ver #(.BOLEN(80)) u_uart_ver (
        .clk(clk_sys), .rst(rst),
        .bayt(uart_ver_bayt), .gonder(uart_ver_gonder),
        .tx(dbg_tx), .mesgul(uart_ver_mesgul)
    );

    host_arayuz u_host (
        .clk(clk_sys), .rst(rst),
        .al_bayt(host_bayt), .al_gecerli(host_gecerli),
        .ver_bayt(uart_ver_bayt), .ver_gonder(uart_ver_gonder),
        .ver_mesgul(uart_ver_mesgul),
        .kayit_adr(kayit_adr), .kayit_veri(kayit_veri),
        .kayit_yaz(kayit_yaz), .kayit_oku(kayit_oku)
    );

    // ---------------------------------------------------------------
    // Kayit dosyasi
    // ---------------------------------------------------------------
    wire        alis_ac, veris_ac, yazilim_rst, nco_yukle;
    wire [3:0]  kanal_maske;
    wire [11:0] azalt_orani, tx_oran;
    wire        tx_yukle, tx_iqsel_ters;
    wire [31:0] tx_ofs1, tx_ofs2, tx_ofs3;
    wire [31:0] nco_artis, ofs0, ofs1, ofs2, ofs3, tx_artis;
    wire [4:0]  zincir_uzun, zincir_adr;
    wire        zincir_gonder, zincir_yaz;
    wire [7:0]  zincir_veri;
    wire        zincir_darbe_kip, zincir_maske_bank;
    wire [7:0]  zincir_darbe_ms;
    wire [31:0] kayit_oku;
    wire [13:0] adc_desen_a, adc_desen_b;
    wire        adc_desen_dene;
    wire [31:0] spi_veri, spi_okunan;
    wire [5:0]  spi_uzunluk, spi_oku_bit;
    wire [2:0]  spi_cihaz;
    wire        spi_yol, spi_basla, spi_mesgul;
    wire        phy_rst_zorla;
    wire        pa_besle;
    wire [4:0]  mdio_phy, mdio_kayit;
    wire [15:0] mdio_veri, mdio_okunan;
    wire        mdio_yaz, mdio_basla, mdio_mesgul;
    wire        mdio_o, mdio_yon;

    kayit u_kayit (
        .clk(clk_sys), .rst(rst),
        .adr(kayit_adr), .veri(kayit_veri), .yaz(kayit_yaz),
        .oku_veri(kayit_oku), .oku_adr(kayit_adr),
        .pll_kilit(pll_kilit),
        .adc_hizali(a1_hizali & a2_hizali),
        .tasma(adc_asim),
        .alis_ac(alis_ac), .veris_ac(veris_ac),
        .yazilim_rst(yazilim_rst),
        .kanal_maske(kanal_maske), .azalt_orani(azalt_orani),
        .nco_artis(nco_artis),
        .nco_ofset0(ofs0), .nco_ofset1(ofs1),
        .nco_ofset2(ofs2), .nco_ofset3(ofs3),
        .nco_yukle(nco_yukle),
        .tx_artis(tx_artis), .tx_oran(tx_oran),
        .tx_ofset1(tx_ofs1), .tx_ofset2(tx_ofs2), .tx_ofset3(tx_ofs3),
        .tx_yukle(tx_yukle), .tx_iqsel_ters(tx_iqsel_ters),
        .zincir_uzun(zincir_uzun), .zincir_gonder(zincir_gonder),
        .zincir_veri(zincir_veri), .zincir_adr(zincir_adr),
        .zincir_yaz(zincir_yaz),
        .zincir_darbe_kip(zincir_darbe_kip),
        .zincir_darbe_ms(zincir_darbe_ms),
        .zincir_maske_bank(zincir_maske_bank),
        .adc_desen_a(adc_desen_a), .adc_desen_b(adc_desen_b),
        .adc_desen_dene(adc_desen_dene),
        .adc_takas({a2_takas, a1_takas}),
        .spi_veri(spi_veri), .spi_uzunluk(spi_uzunluk),
        .spi_oku_bit(spi_oku_bit), .spi_cihaz(spi_cihaz),
        .spi_yol(spi_yol), .spi_basla(spi_basla),
        .spi_okunan(spi_okunan), .spi_mesgul(spi_mesgul),
        .adc_sync(adc_sync), .phy_rst_zorla(phy_rst_zorla),
        .pa_besle(pa_besle),
        .mdio_phy(mdio_phy), .mdio_kayit(mdio_kayit),
        .mdio_veri(mdio_veri), .mdio_yaz(mdio_yaz),
        .mdio_basla(mdio_basla),
        .mdio_okunan(mdio_okunan), .mdio_mesgul(mdio_mesgul)
    );

    // ---------------------------------------------------------------
    // MDIO — PHY yonetimi
    //
    // 80 MHz / (2*32) = 1.25 MHz. Standart ust sinir 2.5 MHz; yarisinda
    // kalmak kart uzerindeki uzun hat ve pull-up ile yavaslayan kenara
    // pay birakiyor. Yilda birkac kez okunan bir arayuzde hiz kazanmanin
    // degeri yok.
    // ---------------------------------------------------------------
    mdio #(.BOLEN(32)) u_mdio (
        .clk(clk_sys), .rst(rst),
        .phy_adr(mdio_phy), .kayit_adr(mdio_kayit),
        .yaz_veri(mdio_veri), .yaz(mdio_yaz), .basla(mdio_basla),
        .oku_veri(mdio_okunan), .mesgul(mdio_mesgul),
        .mdc(mdc), .mdio_o(mdio_o), .mdio_yon(mdio_yon),
        .mdio_i(mdio_hat)
    );

    assign mdio_hat = mdio_yon ? mdio_o : 1'bz;

    // ---------------------------------------------------------------
    // SPI ana birimleri
    // ---------------------------------------------------------------
    wire        adc_sdio_o, adc_sdio_yon;
    wire [1:0]  adc_csb;
    wire        adc_mesgul, cev_mesgul;
    wire [31:0] adc_oku, cev_oku;
    wire [7:0]  cev_csb, cev_le;
    wire        cev_sdo;

    assign spi_mesgul = adc_mesgul | cev_mesgul;
    assign spi_okunan = spi_yol ? cev_oku : adc_oku;

    spi_ana #(.BOLEN(8), .CIHAZ(2)) u_spi_adc (
        .clk(clk_sys), .rst(rst),
        .veri(spi_veri), .uzunluk(spi_uzunluk), .oku_bit(spi_oku_bit),
        .cihaz(spi_cihaz), .basla(spi_basla && !spi_yol),
        .okunan(adc_oku), .mesgul(adc_mesgul),
        .sclk(adc_sclk), .sdio_o(adc_sdio_o), .sdio_yon(adc_sdio_yon),
        .sdio_i(adc_sdio), .csb(adc_csb), .le()
    );

    spi_ana #(.BOLEN(8), .CIHAZ(8)) u_spi_cev (
        .clk(clk_sys), .rst(rst),
        .veri(spi_veri), .uzunluk(spi_uzunluk), .oku_bit(spi_oku_bit),
        .cihaz(spi_cihaz), .basla(spi_basla && spi_yol),
        .okunan(cev_oku), .mesgul(cev_mesgul),
        .sclk(att_clk), .sdio_o(cev_sdo), .sdio_yon(),
        .sdio_i(adc_sdio), .csb(cev_csb), .le(cev_le)
    );

    assign att_data  = cev_sdo;
    assign adc1_ncsb = adc_csb[0];
    assign adc2_ncsb = adc_csb[1];

    // LE TIPI ve CSB TIPI cihazlar ayni yolda.
    // Zayiflaticilar (PE4312) aktarim sonunda YUKSEK darbe istiyor;
    // bias DAC'lari ve PA'nin ADC'si aktarim boyunca DUSUK seviye.
    assign att1_le   = cev_le[0];
    assign att2_le   = cev_le[1];
    assign att3_le   = cev_le[2];
    assign att4_le   = cev_le[3];
    assign pa_att_le = cev_le[4];
    assign bias_cs1  = cev_csb[5];
    assign bias_cs2  = cev_csb[6];
    assign pa_adc_cs = cev_csb[7];

    // ADC_SDIO CIFT YONLU: sadece ADC yolu suruyor.
    assign adc_sdio = adc_sdio_yon ? adc_sdio_o : 1'bz;

    // ---------------------------------------------------------------
    // PHY sifirlamasi.
    //
    // PHY1_nRST / PHY2_nRST kartta SADECE FPGA'ya bagli — cekme
    // direnci yok. Gateware surmezse PHY sifirlamada ya da tanimsiz
    // kalir ve baglanti hic kurulmaz.
    //
    // RTL8211F besleme oturduktan sonra sifirlamanin en az 10 ms
    // tutulmasini istiyor. POR sayaci ~51 us; ustune ayri bir sayac
    // koyup ~26 ms tutuyoruz (80 MHz'de 2^21 cevrim).
    // ---------------------------------------------------------------
    reg [21:0] phy_say;
    always @(posedge clk_sys)
        if (rst)             phy_say <= 22'd0;
        else if (!phy_say[21]) phy_say <= phy_say + 1'b1;

    assign phy1_nrst = phy_say[21] & ~phy_rst_zorla;
    assign phy2_nrst = phy1_nrst;

    // ---------------------------------------------------------------
    // Dort kanalli DDC
    // ---------------------------------------------------------------
    wire signed [23:0] i0, i1, i2, i3, q0, q1, q2, q3;
    wire [3:0] kanal_gecerli;

    ddc_dort u_ddc (
        .clk(clk_sys), .rst(rst | yazilim_rst),
        .adc0(a1_a), .adc1(a1_b), .adc2(a2_a), .adc3(a2_b),
        .adc_gecerli(a1_gecerli & alis_ac),
        .faz_artis(nco_artis),
        .faz_ofset0(ofs0), .faz_ofset1(ofs1),
        .faz_ofset2(ofs2), .faz_ofset3(ofs3),
        .faz_yukle(nco_yukle),
        .azalt_orani(azalt_orani),
        .i_cik0(i0), .i_cik1(i1), .i_cik2(i2), .i_cik3(i3),
        .q_cik0(q0), .q_cik1(q1), .q_cik2(q2), .q_cik3(q3),
        .kanal_gecerli(kanal_gecerli)
    );

    // ---------------------------------------------------------------
    // Paketleyici
    //
    // PAKET BOYU TEK YERDEN. Paketleyicinin urettigi bayt sayisi ile
    // RGMII'ye soylenen yuk uzunlugu AYNI olmali; ayri sabitler
    // yazildiginda cerceve paketin ortasindan kesiliyordu.
    // ---------------------------------------------------------------
    localparam PAKET_ORNEK = 60;
    localparam PAKET_BAYT  = 16 + PAKET_ORNEK * 24;   // 1456

    // azalt_orani -> log2, baslikta host'a bildirilen olcek
    reg [3:0] azalt_log2;
    always @(*) begin
        casez (azalt_orani)
        12'b????_????_???1: azalt_log2 = 4'd0;
        12'b????_????_??10: azalt_log2 = 4'd1;
        12'b????_????_?100: azalt_log2 = 4'd2;
        12'b????_????_1000: azalt_log2 = 4'd3;
        12'b????_???1_0000: azalt_log2 = 4'd4;
        12'b????_??10_0000: azalt_log2 = 4'd5;
        12'b????_?100_0000: azalt_log2 = 4'd6;
        12'b????_1000_0000: azalt_log2 = 4'd7;
        12'b???1_0000_0000: azalt_log2 = 4'd8;
        12'b??10_0000_0000: azalt_log2 = 4'd9;
        12'b?100_0000_0000: azalt_log2 = 4'd10;
        default:            azalt_log2 = 4'd11;
        endcase
    end

    wire [7:0] paket_bayt;
    wire       paket_gecerli, paket_basi, paket_sonu;

    paketleyici #(.PAKET_ORNEK(PAKET_ORNEK)) u_paket (
        .clk(clk_sys), .rst(rst),
        .i0(i0), .q0(q0), .i1(i1), .q1(q1),
        .i2(i2), .q2(q2), .i3(i3), .q3(q3),
        .kanal_gecerli(kanal_gecerli),
        .kanal_maskesi(kanal_maske),
        // AZALTMA BASLIKTA CALISMA ANI DEGERINDEN.
        // 4'd6 sabit yaziliyordu ama azalt_orani host tarafindan
        // degistirilebiliyor; host basligda hep 6 gorup spektrum
        // olcegini sessizce yanlis hesaplardi.
        .azalt_log2(azalt_log2),
        .tasma(adc_asim), .saat_kayip(~(a1_hizali & a2_hizali)),
        .bayt(paket_bayt), .bayt_gecerli(paket_gecerli),
        .paket_basi(paket_basi), .paket_sonu(paket_sonu),
        .hazir(rgmii_hazir_sys)
    );

    // ---------------------------------------------------------------
    // clk_sys -> clk_eth gecisi
    //
    // FIFO, ELLE SENKRONLAYICI DEGIL. Iki saat farkli kaynaklardan
    // ve aralarinda yavas suruklenme var; tek bir flip-flop cifti
    // zamanla ornek dusurur ya da tekrarlar. Dusen bir ornek paket
    // sayacini bozmaz ama veriyi bozar, ve o hata ancak spektrumda
    // gorunur.
    // ---------------------------------------------------------------
    wire        rgmii_hazir_sys;
    wire [7:0]  eth_bayt;
    wire        eth_gecerli, eth_hazir;

    // DERINLIK BIR PAKETTEN BUYUK OLMALI.
    // 1024 yaziyordu, paket ise 1456 bayt — tam paket hicbir zaman
    // tamponlanamazdi, yani store-and-forward kurulamazdi.
    // 2048 x 8 = 16 kbit = tam bir DP16KD blogu.
    wire [11:0] fifo_doluluk;

    fifo_gecis #(.GENISLIK(8), .DERINLIK(2048)) u_fifo (
        .yaz_clk(clk_sys), .yaz_rst(rst),
        .yaz_veri(paket_bayt), .yaz(paket_gecerli),
        .yaz_hazir(rgmii_hazir_sys),
        .oku_clk(clk_eth), .oku_rst(rst),
        .oku_veri(eth_bayt), .oku(eth_hazir),
        .oku_gecerli(eth_gecerli),
        .oku_doluluk(fifo_doluluk)
    );

    // CERCEVEYE ANCAK TAM PAKET HAZIRSA BASLA.
    // rgmii_veris veri_gecerli'yi yalnizca cerceve baslangicinda
    // bakiyor; bir kez basladiktan sonra durmadan bayt cekiyor,
    // cunku RGMII'de duraklamak yok. Tam paket sarti olmadan
    // bosalan FIFO bayat veriyi gecerli CRC ile yollardi.
    wire paket_hazir = (fifo_doluluk >= PAKET_BAYT);

    wire [3:0] td_yuk, td_dus;
    wire       tctl_yuk, tctl_dus;

    rgmii_veris u_rgmii (
        .clk(clk_eth), .rst(rst),
        .veri(eth_bayt), .veri_gecerli(paket_hazir), .veri_son(1'b0),
        .veri_hazir(eth_hazir),
        .yuk_uzunluk(PAKET_BAYT[15:0]),
        .rgmii_td_yuk(td_yuk), .rgmii_td_dus(td_dus),
        .rgmii_tctl_yuk(tctl_yuk), .rgmii_tctl_dus(tctl_dus)
    );

    // ---------------------------------------------------------------
    // RGMII cikis kati — ODDR.
    //
    // Nibble'lari mantikta bolmek yetmez, IKI KENARDA DA CIKMALI.
    // Onceki halde bir nibble bir cevrim suruyordu; PHY iki kenari da
    // ornekledigi icin her nibble'i iki kez okurdu ve cerceve
    // bozulurdu.
    //
    // SAAT DE ODDR'DAN GECIYOR, "assign rgmii_tclk = clk" DEGIL.
    // Duz atama saati normal mantik yolundan cikariyor: veri
    // hatlariyla arasindaki gecikme eslesmiyor ve pencere kayiyor.
    // D0=1/D1=0 ile ODDR ayni IO yolundan bir saat kopyasi uretiyor,
    // veriyle ayni gecikmeyi goruyor — yani TXC veriyle KENAR
    // HIZALI cikiyor, ki PHY'nin ic gecikmesi acikken istenen budur.
    // ---------------------------------------------------------------
    genvar gi;
    generate for (gi = 0; gi < 4; gi = gi + 1) begin : g_td
        ODDRX1F u_td (.SCLK(clk_eth), .RST(rst),
                      .D0(td_yuk[gi]), .D1(td_dus[gi]),
                      .Q(rgmii_td[gi]));
    end endgenerate

    ODDRX1F u_tctl (.SCLK(clk_eth), .RST(rst),
                    .D0(tctl_yuk), .D1(tctl_dus), .Q(rgmii_tctl));

    ODDRX1F u_tclk (.SCLK(clk_eth), .RST(rst),
                    .D0(1'b1), .D1(1'b0), .Q(rgmii_tclk));

    // ---------------------------------------------------------------
    // ETHERNET ALIS — host -> FPGA kayit yolu
    //
    // Bu yola kadar host'un tek yolu UART'ti (115200 baud). Kayit
    // yazmak icin yeterliydi ama ethernet zaten kartta ve tek yonlu
    // kullanmak (yalniz veris) kablonun yarisini bosa harciyordu.
    //
    // UDP YUKU UART ILE AYNI CERCEVE BICIMINI TASIYOR
    // (A5 adr d3 d2 d1 d0 xor), yani host_arayuz oldugu gibi
    // yeniden kullaniliyor. Iki ayri cozumleyici yazmak iki kat
    // bakim ve iki kat hata demekti.
    // ---------------------------------------------------------------
    wire [3:0] rd_yuk, rd_dus;
    wire       rctl_yuk, rctl_dus;

    genvar gr;
    generate for (gr = 0; gr < 4; gr = gr + 1) begin : rgmii_rx
        IDDRX1F u_rd (.SCLK(rgmii_rxc), .RST(rst), .D(rgmii_rd[gr]),
                      .Q0(rd_yuk[gr]), .Q1(rd_dus[gr]));
    end endgenerate

    IDDRX1F u_rctl (.SCLK(rgmii_rxc), .RST(rst), .D(rgmii_rctl),
                    .Q0(rctl_yuk), .Q1(rctl_dus));

    wire [7:0] al_bayt_rx;
    wire       al_gecerli_rx, al_son_rx, al_crc_rx;

    rgmii_alis u_rgmii_al (
        .clk(rgmii_rxc), .rst(rst),
        .rd_yuk(rd_yuk), .rd_dus(rd_dus),
        .rctl_yuk(rctl_yuk), .rctl_dus(rctl_dus),
        .bayt(al_bayt_rx), .bayt_gecerli(al_gecerli_rx),
        .cerceve_sonu(al_son_rx), .crc_dogru(al_crc_rx), .hata()
    );

    wire [7:0] yuk_bayt_rx;
    wire       yuk_gecerli_rx;

    udp_ayikla #(.PORT(16'd5001)) u_udp (
        .clk(rgmii_rxc), .rst(rst),
        .bayt(al_bayt_rx), .bayt_gecerli(al_gecerli_rx),
        .cerceve_sonu(al_son_rx), .crc_dogru(al_crc_rx),
        .yuk_bayt(yuk_bayt_rx), .yuk_gecerli(yuk_gecerli_rx)
    );

    // RXC -> clk_sys gecisi. Iki saat ayri kaynaklardan; tek
    // senkronizatorle 125 MHz'lik bir bayt akisini 80 MHz'e sokmak
    // tasma demekti.
    // AD CAKISMASI: "eth_bayt" ZATEN KULLANILIYOR.
    // Ilk yazdigimda alis FIFO'sunun cikisina da eth_bayt dedim;
    // ornek yolundaki FIFO (u_fifo, satir ~514) o adi kullaniyor.
    // Iki surucu tek tele bagli kaldi ve nextpnr "multiply driven"
    // ile durdu. Onemli olan: SENTEZ (yosys) sadece uyari verdi ve
    // devam etti — uyariya bakmasam bitstream uretilmis gorunurdu.
    // Alis yolunun adlari artik "eth_al_" onekli.
    wire [7:0] eth_al_bayt;
    wire       eth_al_var;

    // OKU VE OKU_GECERLI AYRI TELLER OLMAK ZORUNDA.
    // Ikisini ayni tele baglamistim: biri FIFO'nun GIRISI, oteki
    // CIKISI. yosys "multiple conflicting drivers" verdi ve iki ayri
    // FIFO'nun blok RAM cikislari birbirine baglandi — yani kontrol
    // yolu ile ornek yolu ayni tellere yaziyordu. Sentez yine de
    // bitstream uretti; uyari okunmasa kartta "ethernet bazen
    // sacmaliyor" diye gorunurdu.
    //
    // Dogrusu: gecerli olan her bayti ayni cevrimde tuket.
    // host_arayuz cevrimde bir bayt aliyor, yani biriktirme yok.
    fifo_gecis #(.GENISLIK(8), .DERINLIK(256)) u_eth_fifo (
        .yaz_clk(rgmii_rxc), .yaz_rst(rst),
        .yaz_veri(yuk_bayt_rx), .yaz(yuk_gecerli_rx), .yaz_hazir(),
        .oku_clk(clk_sys), .oku_rst(rst),
        .oku_veri(eth_al_bayt), .oku(eth_al_var), .oku_gecerli(eth_al_var_w),
        .oku_doluluk()
    );
    wire eth_al_var_w;
    assign eth_al_var = eth_al_var_w;

    // KAYNAK SECIMI: ethernet varsa o, yoksa UART.
    //
    // Ikisi AYNI ANDA kullanilmiyor — host birini seciyor. Ayni anda
    // yazilirsa baytlar birbirine karisir; host_arayuz'un XOR
    // saglamasi cogunu yakalar ve zaman asimi ile hizalanir, yani
    // sonuc "komut kayboldu" olur, "yanlis komut uygulandi" degil.
    // Bir arbitre yazmak, olmayan bir kullanim icin karmasiklik
    // olurdu.
    // FIFO CIKISI YAZMACLANIYOR — YOKSA clk_sys 80 MHz'I TUTMUYOR.
    //
    // Olctum: blok RAM cikisi (eth_al_bayt) DOGRUDAN host_arayuz'un
    // cozumleyicisine giriyordu ve kritik yol 12.84 ns cikti, butce
    // 12.50. Yani ethernet alisini eklemek clk_sys'i 88.96'dan
    // 77.86 MHz'e dusurdu — BRAM'in clk-to-q'su 5.83 ns ve ustune
    // durum makinesinin butun LUT zinciri biniyordu.
    //
    // Araya bir yazmac koymak yolu ikiye boluyor. Bedeli bir cevrim
    // gecikme; bu yol kayit yazmalari icin, ornek icin degil.
    reg [7:0] eth_al_bayt_r;
    reg       eth_al_var_r;
    always @(posedge clk_sys) begin
        if (rst) begin
            eth_al_bayt_r <= 8'd0;
            eth_al_var_r  <= 1'b0;
        end else begin
            eth_al_bayt_r <= eth_al_bayt;
            eth_al_var_r  <= eth_al_var;
        end
    end

    assign host_bayt    = eth_al_var_r ? eth_al_bayt_r : uart_al_bayt;
    assign host_gecerli = eth_al_var_r | uart_al_gecerli;

    // ---------------------------------------------------------------
    // Veris zinciri
    // ---------------------------------------------------------------
    // TX ORNEK HIZI DORT KANALDA DA AYNI OLMAK ZORUNDA.
    //
    // Huzme yonlendirme dort antende AYNI dalga bicimini farkli
    // fazlarla ister. Iki kanal 80 MSPS, ikisi 40 MSPS kosarsa
    // aralarindaki faz iliskisi ornek bazinda kayar ve huzme
    // dagilir — dalga bicimleri tek tek dogru gorunse bile.
    //
    // Ortak hizi U31 belirliyor: cogullanmis modda tek veri yolu iki
    // kanali tasiyor, yani kanal basina 40 MSPS (bkz. dac_cogullu.v).
    // U30 daha hizli kosabilirdi ama kosmuyor; sinir kartta.
    //
    // Hiz kapisi TEK YERDEN: dac_cogullu'nun "hazir"i hem kendisini
    // hem U30'u besliyor. Ayri iki bolucu olsaydi aralarinda bir
    // cevrimlik sabit kayma kalabilirdi ve bu, 40 MSPS'te 25 ns —
    // 14 MHz'te 126 derece faz hatasi.
    wire signed [13:0] duc_d0, duc_d1, duc_d2, duc_d3;
    wire               duc_gecerli;
    wire               tx_hazir;
    wire               tx_ver = duc_gecerli & tx_hazir & veris_ac;

    duc_dort u_duc (
        .clk(clk_sys), .rst(rst),
        .i_giris(16'd0), .q_giris(16'd0),      // host tamponu gelince baglanacak
        .giris_gecerli(veris_ac), .giris_hazir(),
        .artir_orani(tx_oran), .faz_artis(tx_artis),
        .faz_ofset1(tx_ofs1), .faz_ofset2(tx_ofs2), .faz_ofset3(tx_ofs3),
        .faz_yukle(tx_yukle), .izin(tx_hazir),
        .dac0(duc_d0), .dac1(duc_d1), .dac2(duc_d2), .dac3(duc_d3),
        .dac_gecerli(duc_gecerli)
    );

    // U30 — cift port, kanal 0 ve 1
    dac_cikis u_dac (
        .clk(clk_sys), .rst(rst),
        .ornek_a(duc_d0), .ornek_b(duc_d1),
        .ornek_gecerli(tx_ver),
        .dac_a(dac_a), .dac_b(dac_b),
        .wrt_a(dac_wrt_a), .wrt_b(dac_wrt_b), .dac_clk()
    );

    // U31 — cogullanmis, kanal 2 ve 3
    wire dac2_iqwrt_yuk, dac2_iqwrt_dus;

    dac_cogullu u_dac2 (
        .clk(clk_sys), .rst(rst),
        .ornek_i(duc_d2), .ornek_q(duc_d3),
        .ornek_gecerli(tx_ver), .iqsel_ters(tx_iqsel_ters),
        .dac_d(dac2_d),
        .iqwrt_yuk(dac2_iqwrt_yuk), .iqwrt_dus(dac2_iqwrt_dus),
        .iqsel(dac2_iqsel), .iqreset(dac2_iqreset),
        .hazir(tx_hazir)
    );

    // IQWRT ODDR'DAN. Veri posedge'de degisiyor, IQWRT negedge'de
    // yukseliyor: kurulum 6.25 ns (gereken 2.0), tutma 6.25 ns
    // (gereken 1.5). Ayni kenardan surulseydi kurulum sifir olurdu
    // ve iki kanal rastgele yer degistirirdi.
    ODDRX1F u_iqwrt (.SCLK(clk_sys), .RST(rst),
                     .D0(dac2_iqwrt_yuk), .D1(dac2_iqwrt_dus),
                     .Q(dac2_iqwrt));

    // ---------------------------------------------------------------
    // Kontrol zinciri
    // ---------------------------------------------------------------
    kontrol_zinciri u_kontrol (
        .clk(clk_sys), .rst(rst),
        .yaz_veri(zincir_veri), .yaz_adr(zincir_adr),
        .yaz_darbe(zincir_yaz),
        .zincir_bayt(zincir_uzun), .gonder(zincir_gonder),
        .darbe_kip(zincir_darbe_kip), .darbe_ms(zincir_darbe_ms),
        .maske_bank(zincir_maske_bank),
        .rly_ser(rly_ser), .rly_srclk(rly_srclk), .rly_rclk(rly_rclk),
        .mesgul()
    );

    // ---------------------------------------------------------------
    // PA IZNI — VE BEKCI KOPEGI.
    //
    // ADI YANILTICI: pin PA_INHIBIT diye geciyor ama mantik ters
    // degil, YUKSEK = PA'ya izin. D kartinda 100k asagi cekme var,
    // yani kablo koparsa ya da FPGA yapilandirilmamissa PA KAPALI.
    // Dogru davranis bu; adi bir sonraki kart revizyonunda
    // PA_ENABLE olmali.
    //
    // BEKCI KOPEGI NEDEN: host verirken baglantiyi kaybederse
    // (UART sokuldu, ethernet koptu, ana bilgisayar cakildi) 100 W
    // acik kalir ve kimse kapatamaz. Host'un periyodik olarak
    // "beslemesi" gerekiyor; beslemezse PA kendiliginden kesiliyor.
    //
    // 250 ms. Insan tepkisinden kisa, normal bir kontrol dongusunden
    // uzun. 80 MHz'te 20 milyon cevrim.
    localparam KOPEK_SINIR = 25'd20_000_000;
    reg [24:0] kopek;
    always @(posedge clk_sys)
        if (rst)                 kopek <= KOPEK_SINIR;
        else if (pa_besle)       kopek <= KOPEK_SINIR;
        else if (kopek != 25'd0) kopek <= kopek - 1'b1;

    wire kopek_canli = (kopek != 25'd0);

    assign pa_inhibit = veris_ac & a1_hizali & a2_hizali & kopek_canli;

    // ---------------------------------------------------------------
    // Durum LED'leri — aktif dusuk (anot +3V3'te)
    // ---------------------------------------------------------------
    // LED'LER TAMAMEN clk_sys ALANINDA VE YAZMACLI.
    //
    // led_data once "eth_gecerli | yanip[20]" idi: eth_gecerli
    // clk_eth alaninda, yanip clk_sys alaninda. Iki saat alanini
    // BIRLESIMSEL karistiran bir ifade. Islevsel olarak zararsiz
    // gorunuyor (sadece bir LED) ama bedeli var: ethernet alaninin
    // en kritik sinyallerinden biri olan eth_gecerli'ye fazladan
    // yayilim ve saat alanlari arasi bir yol ekliyor, ve yerlestirici
    // o yolu kritik yolun ortasina koyuyordu.
    //
    // Veri akisini clk_sys tarafindan gosteriyoruz: paket_gecerli
    // zaten "paketleyici bayt uretiyor" demek, ki LED'in anlatmasi
    // gereken sey tam olarak bu.
    reg [24:0] yanip;
    always @(posedge clk_sys) yanip <= yanip + 1'b1;

    reg veri_akiyor;
    always @(posedge clk_sys)
        if (rst)                 veri_akiyor <= 1'b0;
        else if (paket_gecerli)  veri_akiyor <= 1'b1;
        else if (yanip[20:0] == 21'd0) veri_akiyor <= 1'b0;

    reg led_status_r, led_rx_r, led_tx_r, led_data_r;
    always @(posedge clk_sys) begin
        led_status_r <= ~(a1_hizali & a2_hizali);
        led_rx_r     <= ~(alis_ac  & yanip[22]);
        led_tx_r     <= ~(veris_ac & yanip[22]);
        led_data_r   <= ~veri_akiyor;
    end
    assign led_status = led_status_r;
    assign led_rx     = led_rx_r;
    assign led_tx     = led_tx_r;
    assign led_data   = led_data_r;

endmodule

`default_nettype wire
