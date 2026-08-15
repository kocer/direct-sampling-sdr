#!/usr/bin/env python3
"""LPF'i KARTTAN uret, elle yazma.

    python3 sentez/lpf_yaz.py            # sentez/ust.lpf yazar

NEDEN URETILIYOR. Pin kisit dosyasini elle tutmak, kart degistiginde
sessizce yanlis kalan ikinci bir gercek kaynagi demek. Bir ball yanlis
yazilirsa sentez de yerlestirme de sorunsuz gecer; hata ancak kart
elde, olcu aletiyle bulunur. Kartin kendisi tek kaynak olsun.

BU ARAC AYRICA DENETCI. Ust modulun her portu icin kartta bir ag
aramak zorunda oldugu icin, karsiligi olmayan portu ve suruclenmeyen
onemli agi hemen bildiriyor. Boyle uc bosluk zaten bulundu: rst_n'in
kartta pini yoktu, dac_clk kartta FPGA'dan degil saat agacindan
geliyordu, ve kayit arayuzunun hicbir yere baglanmadigi icin
gateware'i yapilandirmanin YOLU YOKTU.
"""
import json
import os
import re
import sys

import pcbnew

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KART = os.path.join(os.path.dirname(KOK), "kicad",
                    "A_main", "dogrudan_sdr_A.kicad_pcb")
IODB = ("/home/cinar/opt/oss-cad-suite/share/trellis/database/"
        "ECP5/LFE5U-25F/iodb.json")
PAKET = "CABGA256"

# ust.v portu -> karttaki ag adi.
# Demetler icin {i} indeksle genisletiliyor.
ESLEME = [
    # clk_sys VCXO_CLK'e baglanmiyor. VCXO_CLK bir FPGA CIKISI —
    # J62'ye giden, VCXO varaktorunu suren SPI DAC'inin SCK'si.
    # Sistem saati ADCLK846 -> SN65LVDS2 (U18) -> FPGA_CLK80 yolundan
    # geliyor ve K16 (PCLKT2_0) gercek saat pini.
    ("clk_sys",      "FPGA_CLK80",    None),
    ("adc1_dco",     "ADC1_DCO",      None),
    ("adc1_d",       "ADC1_D{i}",     14),
    ("adc1_or",      "ADC1_OR",       None),
    ("adc2_dco",     "ADC2_DCO",      None),
    ("adc2_d",       "ADC2_D{i}",     14),
    ("adc2_or",      "ADC2_OR",       None),
    ("dac_a",        "DAC1_P1_D{i}",  14),
    ("dac_wrt_a",    "DAC1_WRT1",     None),
    # DORT VERIS KANALI: U30 cift port (P1+P2), U31 cogullanmis.
    ("dac_b",        "DAC1_P2_D{i}",  14),
    ("dac_wrt_b",    "DAC1_WRT2",     None),
    ("dac2_d",       "DAC2_D{i}",     14),
    ("dac2_iqwrt",   "DAC2_IQWRT",    None),
    ("dac2_iqsel",   "DAC2_IQSEL",    None),
    ("dac2_iqreset", "DAC2_IQRESET",  None),
    ("rgmii_td",     "PHY1_TXD{i}",   4),
    # ALIS: saat PHY'den geliyor, RXC bir GIRIS saati.
    ("rgmii_rd",     "PHY1_RXD{i}",  4),
    ("rgmii_rctl",   "PHY1_RXCTL",   None),
    ("rgmii_rxc",    "PHY1_RXC",     None),
    ("rgmii_tctl",   "PHY1_TXCTL",    None),
    ("rgmii_tclk",   "PHY1_TXC",      None),
    ("rly_ser",      "RLY_SER",       None),
    ("rly_srclk",    "RLY_SRCLK",     None),
    ("rly_rclk",     "RLY_RCLK",      None),
    ("pa_inhibit",   "PA_INHIBIT",    None),
    ("led_status",   "LED_STATUS",    None),
    ("led_rx",       "LED_RX",        None),
    ("led_tx",       "LED_TX",        None),
    ("led_data",     "LED_DATA",      None),
    ("dbg_rx",       "DBG_RX",        None),
    ("dbg_tx",       "DBG_TX",        None),

    # SPI — kart ici ADC yolu
    ("adc_sclk",     "ADC_SCLK",      None),
    ("adc_sdio",     "ADC_SDIO",      None),
    ("adc1_ncsb",    "ADC1_nCSB",     None),
    ("adc2_ncsb",    "ADC2_nCSB",     None),
    ("adc_sync",     "ADC_SYNC",      None),

    # SPI — cevre yolu (zayiflaticilar, PA bias, PA ADC)
    ("att_clk",      "ATT_CLK",       None),
    ("att_data",     "ATT_DATA",      None),
    ("att1_le",      "ATT1_LE",       None),
    ("att2_le",      "ATT2_LE",       None),
    ("att3_le",      "ATT3_LE",       None),
    ("att4_le",      "ATT4_LE",       None),
    ("pa_att_le",    "PA_ATT_LE",     None),
    ("bias_cs1",     "BIAS_CS1",      None),
    ("bias_cs2",     "BIAS_CS2",      None),
    ("pa_adc_cs",    "PA_ADC_CS",     None),

    ("mdc",          "MDC",           None),
    ("mdio_hat",     "MDIO",          None),
    ("phy1_nrst",    "PHY1_nRST",     None),
    ("phy2_nrst",    "PHY2_nRST",     None),
]

# Banka gerilimleri kartin besleme agindan (gen_01_power.py):
#   banka 6  +1V8   AD9251 sayisal cikislari
#   banka 3  +1V8   RTL8211F DVDD_RG ile ayni, RGMII 1.8 V
#   digeri   +3V3
BANKA_TIPI = {6: "LVCMOS18", 3: "LVCMOS18"}
VARSAYILAN_TIP = "LVCMOS33"

# Saat frekanslari. clk_eth PLL cikisi, kisiti EHXPLLL uzerindeki
# FREQUENCY_PIN_CLKOP niteliginden geliyor — burada tekrarlanmaz.
FREKANS = {
    "clk_sys":  80.0,
    "adc1_dco": 80.0,
    "adc2_dco": 80.0,
    # RGMII ALIS SAATI 125 MHz — KISIT YAZILMAZSA VARSAYILAN ALINIR.
    # Ilk kosuda pnr "rgmii_rxc: 132.24 MHz (hedef 12.00)" dedi:
    # kisit yoktu, nextpnr 12 MHz varsaydi ve yol "gecti". 12 MHz'e
    # gore kapanan bir yol 125 MHz'te on kat pay eksigi demek, yani
    # zamanlama raporu dogru gorunurken kart calismaz.
    "rgmii_rxc": 125.0,
}

# RGMII cikislarinda hizli kenar: 1.8 V'ta 125 MHz DDR, yavas kenar
# veri gozunu yiyor. Diger cikislarda hizli kenar sadece gurultu.
HIZLI = re.compile(r"^rgmii_")


def ust_portlari(yol):
    """ust.v'nin port listesini oku: [(ad, genislik|None, yon)]"""
    s = open(yol, encoding="utf-8").read()
    m = re.search(r"module\s+ust\s*\((.*?)\n\);", s, re.S)
    if not m:
        sys.exit("HATA: ust modulunun port listesi bulunamadi")
    out = []
    for yon, gen, ad in re.findall(
            r"\b(input|output|inout)\s+wire\s*(\[\s*\d+\s*:\s*\d+\s*\])?\s*(\w+)",
            m.group(1)):
        n = None
        if gen:
            ust, alt = re.findall(r"\d+", gen)
            n = int(ust) - int(alt) + 1
        out.append((ad, n, yon))
    return out


def kart_haritasi():
    b = pcbnew.LoadBoard(KART)
    fpga = [f for f in b.GetFootprints() if len(f.Pads()) > 200]
    if not fpga:
        sys.exit("HATA: FPGA footprint'i bulunamadi")
    fpga = fpga[0]
    h = {}
    for p in fpga.Pads():
        n = p.GetNetname() or ""
        if n and not n.startswith("unconnected"):
            h[n] = p.GetPadName()
    return h, fpga.GetValue()


def banka_haritasi():
    d = json.load(open(IODB))
    pkg = d["packages"][PAKET]
    md = {(m["row"], m["col"], m["pio"]): m for m in d["pio_metadata"]}
    out = {}
    for ball, loc in pkg.items():
        m = md.get((loc["row"], loc["col"], loc["pio"]))
        out[ball] = (m.get("bank"), m.get("function", "")) if m else (None, "")
    return out


def main():
    net2ball, parca = kart_haritasi()
    banka = banka_haritasi()
    portlar = dict((a, (n, y)) for a, n, y in ust_portlari(
        os.path.join(KOK, "rtl", "ust.v")))

    satir = []
    uyari = []
    eslesen = set()

    satir.append("# BU DOSYA URETILIYOR — ELLE DUZENLEME.")
    satir.append("#   python3 sentez/lpf_yaz.py")
    satir.append("# Kaynak: kicad/A_main/dogrudan_sdr_A.kicad_pcb")
    satir.append("# Parca:  %s" % parca)
    satir.append("")

    for port, kalip, genislik in ESLEME:
        if port not in portlar:
            uyari.append("ESLEMEDE var, ust.v'de YOK: %s" % port)
            continue
        eslesen.add(port)
        p_gen = portlar[port][0]
        if (p_gen or 0) != (genislik or 0):
            uyari.append("genislik uyusmuyor: %s ust.v'de %s, eslemede %s"
                         % (port, p_gen, genislik))

        indeksler = range(genislik) if genislik else [None]
        for i in indeksler:
            ag = kalip.format(i=i) if i is not None else kalip
            ad = "%s[%d]" % (port, i) if i is not None else port
            ball = net2ball.get(ag)
            if ball is None:
                uyari.append("KARTTA AG YOK: %s (port %s)" % (ag, ad))
                continue
            bank, islev = banka.get(ball, (None, ""))
            if bank is None:
                uyari.append("BALL KULLANICI I/O DEGIL: %s = %s (port %s)"
                             % (ball, ag, ad))
                continue
            tip = BANKA_TIPI.get(bank, VARSAYILAN_TIP)
            ek = " SLEWRATE=FAST" if HIZLI.match(port) else ""
            satir.append('LOCATE COMP "%s" SITE "%s";   # %s, banka %d%s'
                         % (ad, ball, ag, bank,
                            " " + islev if islev else ""))
            satir.append('IOBUF PORT "%s" IO_TYPE=%s%s;' % (ad, tip, ek))
        satir.append("")

    satir.append("# Saat kisitlari")
    for port, mhz in sorted(FREKANS.items()):
        if port in eslesen:
            satir.append('FREQUENCY PORT "%s" %.1f MHZ;' % (port, mhz))
    satir.append("")

    # ust.v'de olup eslemede olmayan port
    for p in portlar:
        if p not in eslesen:
            uyari.append("ust.v'de var, ESLEMEDE yok (pini olmayacak): %s" % p)

    cikti = os.path.join(KOK, "sentez", "ust.lpf")
    os.makedirs(os.path.dirname(cikti), exist_ok=True)
    open(cikti, "w", encoding="utf-8").write("\n".join(satir) + "\n")

    kisit = sum(1 for s in satir if s.startswith("LOCATE"))
    print("%s yazildi, %d pin kisiti" % (cikti, kisit))
    if uyari:
        print("\nUYARI (%d):" % len(uyari))
        for u in uyari:
            print("  " + u)
        return 1
    print("uyari yok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
