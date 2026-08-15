#!/usr/bin/env python3
"""05_driver: 32 kilitlenen role surucusu. Kaynak: ../NETLIST_C.md §5."""
import json, os
from schlib import Sheet

HERE = os.path.dirname(os.path.abspath(__file__))
UU = json.load(open(os.path.join(HERE, "sheet_uuids.json")))

SR = "74xx:74HC595"
FSR = "Package_SO:SOIC-16_3.9x9.9mm_P1.27mm"
HB = "Driver_Motor:DRV8833PWP"
FHB = "Package_SO:HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm_ThermalVias"
R, C = "Device:R", "Device:C"
FR = "Resistor_SMD:R_0603_1608Metric"
FC = "Capacitor_SMD:C_0603_1608Metric"

s = Sheet("05_driver", "Role surucu", UU["05_driver"],
          "8 x 74HC595 + 16 x DRV8833, 32 kilitlenen role", paper="A1")

nr = [0]


def cnt(p):
    nr[0] += 1
    return f"{p}{599 + nr[0]}"


s.text("ROLE SURUCUSU — 28 kilitlenen filtre rolesi", 16, 14, 2.2)
s.text("G6KU TEK SARIMLI kilitlenen: bobine verilen gerilimin YONU konumu\\n"
       "belirliyor. Acik drenaj surucu (TPIC6B595) YETMEZ — akimi sadece\\n"
       "bir yonde cekebilir. H koprusu sart.\\n\\n"
       "Zincir: A kartindan 3 hat -> 8 x 74HC595 (64 lojik cikis)\\n"
       "        56 lojik -> 16 x DRV8833 (kanal basina dort)\\n"
       "        28 H koprusu kanali -> 28 filtre rolesi\\n\\n"
       "74HC595 yetiyor cunku bobin akimini DRV8833 veriyor; yazmacin\\n"
       "surdugu sey sadece lojik giris. TPIC6B595 ($0.68) yerine\\n"
       "74HC595 ($0.07, TEMEL kutuphane) — yedi adette $4.3 fark.",
       16, 22, 1.4)

# ------------------------------------------------------------ kaydirmali yazmaclar
s.text("KAYDIRMALI YAZMAC ZINCIRI", 16, 90, 1.8)
for i in range(7):
    x = 55 + (i % 4) * 110
    y = 130 + (i // 4) * 90
    ref = f"U{60 + i}"
    s.sym(SR, ref, "74HC595D", x, y, fp=FSR)
    s.pin_label(SR, "14", x, y, 0, "RLY_SER" if i == 0 else f"SRQ{i - 1}",
                "input", d=7.62)
    if i < 6:
        s.pin_label(SR, "9", x, y, 0, f"SRQ{i}", "output", d=7.62)
    else:
        # Zincirin sonu D kartina devam ediyor: PA'nin LPF yazmaci
        # ayni zincirin sekizinci halkasi (06_iface J82).
        s.pin_label(SR, "9", x, y, 0, "RLY_SER_OUT", "output", d=7.62)
    s.pin_label(SR, "11", x, y, 0, "RLY_SRCLK", "input", d=12.7)
    s.pin_label(SR, "12", x, y, 0, "RLY_RCLK", "input", d=17.78)
    s.pin_label(SR, "10", x, y, 0, "+3V3", "input", d=22.86)     # ~SRCLR
    s.pin_power(SR, "13", x, y, 0, "GND", d=27.94)               # ~OE
    s.pin_label(SR, "16", x, y, 0, "+3V3", "input", d=5.08)
    s.pin_power(SR, "8", x, y, 0, "GND", d=5.08)
    for j, pn in enumerate(("15", "1", "2", "3", "4", "5", "6", "7")):
        s.pin_label(SR, pn, x, y, 0, f"Q{i * 8 + j}", "output", d=7.62)
    s.sym(C, cnt("C"), "100nF", x + 40, y, rot=90, fp=FC)
    s.pin_label(C, "1", x + 40, y, 90, "+3V3", "input")
    s.pin_power(C, "2", x + 40, y, 90, "GND")

s.text("~SRCLR yukari (+3V3): silme kullanilmiyor, RCLK ile guncelleniyor.\\n"
       "~OE topragda: cikislar hep acik.\\n"
       "QH' bir sonraki yazmacin SER'ine — sekizi tek zincir, 64 bit.",
       16, 300, 1.35)

# ------------------------------------------------------------ H koprusu
s.text("H KOPRULERI — 16 x DRV8833, her biri iki role", 460, 90, 1.8)

# role listesi: 28 filtre (4 kanal x 7 pozisyon) + 4 T/R
# T/R roleleri BU ZINCIRDE DEGIL: onlar kilitlenmeyen ve dogrudan
# TR1..TR4 hattindan MOSFET ile suruluyor (02_protect). Guvenlik
# varsayilan durumdan gelmeli — kilitlenen role gucsuz kalinca
# konumu korur, T/R'da bu anteni PA'da birakmak demek.
ROLELER = [f"K{ch}{p}" for ch in range(1, 5) for p in range(1, 8)]
assert len(ROLELER) == 28, len(ROLELER)

# ** 14 DEGIL 16 SURUCU — KANAL BASINA DORT. **
#
# 14 x 2 = 28 cikis 28 roleye TAM oturuyor ama kanal basina role
# sayisi YEDI, yani TEK. Esleme kacinilmaz olarak kanal sinirini
# asiyordu: U73 -> K17 (kanal 1) + K21 (kanal 2), U80 -> K37 + K41.
# O iki surucu kartin iki ucundaki rolelere birden yakin olamaz.
# Olculdu: 28 surucu-role ciftinin 27'si 60 mm'nin uzerinde,
# ortalama 144 mm, en uzugu 274 mm (U73 -> K17). Kilitlenen role
# bobinine verilen darbe o mesafede zayifliyor; bazen atmayan bir
# bant filtresi rolesi = yanlis filtreyle verme.
#
# Kanal basina DORT surucu (8 cikis, 7 role, biri yedek):
#   - her surucu kendi kanalinin seridinde kaliyor
#   - dort kanal BIREBIR AYNI oluyor (bu kartin varlik sebebi)
#   - bosta kalan cikis ileride bir bant eklenirse hazir
# Bedeli iki DRV8833 (~$1). Sayfanin kendi basligi zaten
# "8 x 74HC595 + 16 x DRV8833" diyordu; uygulama 7/14 kalmisti.
#
# KAYDIRMALI YAZMAC SAYISI DEGISMIYOR. Kullanilan H koprusu
# sayisi yine 28, yani 56 lojik hat = 7 x 74HC595. Bos kalan
# dordu de girisleri TOPRAGA bagli (kopru kapali).
# ROLE -> Q ESLEMESI DE DEGISMIYOR: role r (kanal sirasinda
# 0..27) yine Q(2r) ve Q(2r+1) ile suruluyor. Gateware'in bit
# haritasina dokunulmuyor.
for ch in range(1, 5):
    for j in range(4):
        i = (ch - 1) * 4 + j
        x = 480 + (i % 4) * 90
        y = 130 + (i // 4) * 75
        ref = f"U{70 + i}"
        s.sym(HB, ref, "DRV8833PWPR", x, y, fp=FHB)
        # A yarisi tek numarali roleyi, B yarisi bir sonrakini surer
        ra = f"K{ch}{2 * j + 1}"
        rb = f"K{ch}{2 * j + 2}" if 2 * j + 2 <= 7 else None
        ia = (ch - 1) * 7 + 2 * j          # kanal sirasinda role indisi
        ib = ia + 1
        s.pin_label(HB, "16", x, y, 0, f"Q{2 * ia + 0}", "input", d=7.62)
        s.pin_label(HB, "15", x, y, 0, f"Q{2 * ia + 1}", "input", d=12.7)
        if rb:
            s.pin_label(HB, "9", x, y, 0, f"Q{2 * ib + 0}", "input", d=17.78)
            s.pin_label(HB, "10", x, y, 0, f"Q{2 * ib + 1}", "input", d=22.86)
            s.pin_label(HB, "7", x, y, 0, f"{rb}_S", "output", d=17.78)
            s.pin_label(HB, "5", x, y, 0, f"{rb}_R", "output", d=22.86)
        else:
            # YEDEK YARIM KOPRU: girisleri topraga, cikislari bosta.
            # Girisi havada birakmak CMOS'ta tanimsiz durum demek —
            # kopru rastgele iletir ve bosuna akim ceker.
            s.pin_power(HB, "9", x, y, 0, "GND", d=17.78)
            s.pin_power(HB, "10", x, y, 0, "GND", d=22.86)
            s.nc(*s.P(HB, "7", x, y))
            s.nc(*s.P(HB, "5", x, y))
        s.pin_label(HB, "2", x, y, 0, f"{ra}_S", "output", d=7.62)
        s.pin_label(HB, "4", x, y, 0, f"{ra}_R", "output", d=12.7)
        s.pin_label(HB, "12", x, y, 0, "+5V", "input", d=5.08)         # VM
        s.pin_label(HB, "1", x, y, 0, "+3V3", "input", d=27.94)        # ~SLEEP
        s.pin_label(HB, "8", x, y, 0, "RLY_FAULT", "output", d=33.02)  # ~FAULT
    # AISEN/BISEN dogrudan topraga DEGIL, 0R uzerinden. Iki sebep:
    # (1) ERC "cift yonlu pin guc cikisiyla baglanmis" diyor, cunku
    #     toprak agina PWR_FLAG konmus durumda;
    # (2) akim sinirlama istenirse buraya olcu direnci takilir,
    #     kart degismez. Simdilik 0R.
        for k, pn in enumerate(("3", "6")):
            sx, sy = x - 30, y + 30 + k * 12
            s.sym(R, cnt("R"), "0R", sx, sy, rot=90, fp=FR)
            s.pin_label(HB, pn, x, y, 0, f"{ref}_ISEN{k}", "passive",
                        d=5.08 + k * 5.08)
            s.pin_label(R, "1", sx, sy, 90, f"{ref}_ISEN{k}", "passive")
            s.pin_power(R, "2", sx, sy, 90, "GND")
        s.pin_power(HB, "13", x, y, 0, "GND", d=5.08)
        s.pin_power(HB, "17", x, y, 0, "GND", d=10.16)
        s.nc(*s.P(HB, "11", x, y))                                     # VCP
        s.nc(*s.P(HB, "14", x, y))                                     # VINT
        s.sym(C, cnt("C"), "100nF", x + 42, y, rot=90, fp=FC)
        s.pin_label(C, "1", x + 42, y, 90, "+5V", "input")
        s.pin_power(C, "2", x + 42, y, 90, "GND")

s.sym(R, "R690", "10k", 460, 440, rot=90, fp=FR)
s.pin_label(R, "1", 460, 440, 90, "+3V3", "input")
s.pin_label(R, "2", 460, 440, 90, "RLY_FAULT", "passive")

s.text("DRV8833: cift H koprusu, 1.5 A tepe, kanal basina.\\n"
       "Bobin 5 V / 21 mA / 237 ohm — koprunun kapasitesinin cok altinda.\\n\\n"
       "AIN1/AIN2 = 10 -> ileri (SET), = 01 -> geri (RESET), = 00 -> bosta.\\n"
       "Firmware darbeyi ~20 ms tutup sifirliyor; kilitlenen role konumunu\\n"
       "koruyor ve akim kesiliyor. Surekli tuketim SIFIR.\\n\\n"
       "~FAULT hepsinde ortak, acik drenaj, 10k ile yukari. Asiri akim ya\\n"
       "da asiri sicaklikta FPGA haberdar oluyor.\\n\\n"
       "AISEN/BISEN topragda: akim sinirlama kullanilmiyor, bobin zaten\\n"
       "237 ohm ile kendi akimini belirliyor.", 460, 450, 1.35)

s.text("ACILIS: roleler bilinmeyen konumda\\n"
       "Kilitlenen role gucsuz kaldigi konumu koruyor; kart ilk kez\\n"
       "aciliyorsa ya da uzun sure bekledi ise konum belirsiz.\\n"
       "Firmware ilk is olarak 32 rolenin HEPSINI RESET'liyor, sonra\\n"
       "istenen bandi SET'liyor. Yoksa iki bant ayni anda devrede\\n"
       "kalabilir ve filtre bankasi kisa devre olur.", 16, 340, 1.35)

s.write(os.path.join(HERE, "05_driver.kicad_sch"))
print("05_driver.kicad_sch yazildi")
