#!/usr/bin/env python3
"""
Minik KiCad sema uretici.

Sadece ihtiyacimiz olan kadarini yapiyor: sembol yerlestir, tel cek,
global etiket koy, guc sembolu koy. Karmasik sey yok; sema icerigini
KiCad'de elle duzenlemek de serbest, bu sadece ilk dolguyu uretiyor.

Kullanim:
    s = Sheet("01_power", "Guc agaci", sheet_uuid)
    s.sym("Device:R", "R1", "10k", 100, 100, rot=90,
          fp="Resistor_SMD:R_0603_1608Metric")
    s.wire(100, 100, 120, 100)
    s.glabel("+3V3", 120, 100, "output")
    s.power("GND", 100, 120)
    s.write(path)
"""
import os, re, uuid

VER = 20260306          # KiCad 10.0.5 surumu
LIBDIRS = ["/usr/share/kicad/symbols",
           os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")]
# C KARTI. A'dan kopyalandi; proje adini degistirmeyi unutursam sembol
# ornek yollari "dogrudan_sdr_A" projesine isaret eder ve KiCad acilista
# "bir hata bulundu ve duzeltildi" der.
PROJ = "dogrudan_sdr_D"

GRID = 1.27

def g(v):
    """1.27 mm izgarasina oturt. KiCad semada baglanti icin bunu sart kosuyor;
    izgara disi uc 'endpoint_off_grid' hatasi veriyor ve tel PIN'e degmiyor."""
    return round(round(float(v) / GRID) * GRID, 4)

_cache = {}

def _lib_path(libname):
    for d in LIBDIRS:
        p = os.path.join(d, libname + ".kicad_sym")
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"kutuphane yok: {libname}")

def sym_def(lib_id):
    """Kutuphaneden sembol tanimini cek, lib_symbols'e gomulecek hale getir."""
    if lib_id in _cache:
        return _cache[lib_id]
    libname, symname = lib_id.split(":", 1)
    s = open(_lib_path(libname), encoding="utf-8").read()
    # sembol blogunu bul: girinti bir tab, kapanis ayni girintide
    i = s.find(f'(symbol "{symname}"')
    if i < 0:
        raise KeyError(f"sembol yok: {lib_id}")
    depth, j = 0, i
    while j < len(s):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                j += 1
                break
        j += 1
    blk = s[i:j]
    # SADECE dis ad lib_id oluyor. Alt-semboller (SymName_0_1 gibi)
    # kutuphane onekini ALMIYOR — KiCad boyle bekliyor ve almazsa
    # dosyanin tamamini reddediyor. Bir saat bunu aradim.
    blk = blk.replace(f'(symbol "{symname}"', f'(symbol "{lib_id}"', 1)
    # Kutuphane dosyasina OZEL alanlar sema gomulusunde kabul edilmiyor.
    # KiCad gomerken bunlari atiyor; aynen kopyalarsak dosya reddediliyor.
    # SADECE sema gomulusunde gercekten yasak olanlar atiliyor.
    # show_name / do_not_autoplace atilirsa KiCad 'lib_symbol_mismatch'
    # uyarisi veriyor — kutuphanedeki kopyayla ayni kalmali.
    for tok in ("in_pos_files", "duplicate_pin_numbers_are_jumpers",
                "embedded_fonts"):
        blk = re.sub(r"[ \t]*\(" + tok + r"\s+(?:yes|no)\s*\)\s*\n?", "", blk)
    _cache[lib_id] = blk
    return blk


def _extends(lib_id):
    """Sembol baska bir sembolu genisletiyorsa ebeveyn lib_id'sini don."""
    m = re.search(r'\(extends "([^"]+)"\)', sym_def(lib_id))
    if not m:
        return None
    return lib_id.split(":", 1)[0] + ":" + m.group(1)


def _flatten(lib_id):
    """Turetilmis sembolu ebeveyniyle birlestirip TEK blok yap.

    NEDEN: KiCad kutuphanesinde W25Q128JVS gibi semboller
    (extends "W25Q32JVSS") ile tanimli — cizim ve pinler ebeveynde.
    Iki blogu da lib_symbols'e koymak yetmiyor: gomulu kopyada
    extends cozulmuyor, sembol PINSIZ yerlesiyor. Netlist'te bileseni
    goruyorsun ama hicbir agda yok, ERC'de butun teller boslukta.
    Bir saatimi yedi. Cozum: ebeveynin govdesini alip cocugun
    ozellikleriyle giydirmek, extends'i tamamen atmak."""
    par = _extends(lib_id)
    if not par:
        return sym_def(lib_id)
    child, parent = sym_def(lib_id), _flatten(par)
    cname = lib_id.split(":", 1)[1]
    pname = par.split(":", 1)[1]
    blk = parent.replace(f'(symbol "{par}"', f'(symbol "{lib_id}"', 1)
    blk = blk.replace(f'(symbol "{pname}_', f'(symbol "{cname}_')
    # cocugun ozellikleri (Value, Datasheet, aciklama) ebeveyninkini ezer
    for prop in re.findall(r'\(property "([^"]+)"', child):
        cm = _prop(child, prop)
        if cm is None:
            continue
        if _prop(blk, prop) is None:
            blk = blk.replace(f'(symbol "{lib_id}"',
                              f'(symbol "{lib_id}"\n\t\t' + cm, 1)
        else:
            blk = blk[:_prop_span(blk, prop)[0]] + cm + blk[_prop_span(blk, prop)[1]:]
    return blk


def _prop_span(blk, name):
    i = blk.find(f'(property "{name}"')
    if i < 0:
        return None
    depth, j = 0, i
    while j < len(blk):
        if blk[j] == "(":
            depth += 1
        elif blk[j] == ")":
            depth -= 1
            if depth == 0:
                return (i, j + 1)
        j += 1
    return None


def _prop(blk, name):
    sp = _prop_span(blk, name)
    return None if sp is None else blk[sp[0]:sp[1]]


def sym_defs(lib_id):
    """lib_symbols'e gomulecek blok(lar). Turetilmisler duzlestiriliyor."""
    return [_flatten(lib_id)]


def pins(lib_id):
    """{pin_no: (dx, dy, rot, name)} — sembol merkezine gore pin konumlari.
    Turetilmis sembolde pinler ebeveynde, zinciri takip ediyoruz."""
    blk = sym_def(lib_id)
    par = _extends(lib_id)
    if par and "(pin " not in blk:
        return pins(par)
    out = {}
    for m in re.finditer(
        r'\(pin\s+\w+\s+\w+\s*\(at\s+([-\d.]+)\s+([-\d.]+)\s+(\d+)\)'
        r'.*?\(name "([^"]*)".*?\(number "([^"]*)"', blk, re.S):
        dx, dy, rot, name, num = m.groups()
        out[num] = (float(dx), float(dy), int(rot), name)
    return out


def unit_pins(lib_id, unit):
    """Cok birimli sembolun SADECE bir biriminin pinleri: {no: ad}.
    pins() hepsini birden veriyor; ECP5'te 256 pin sekiz bankaya bolunmus,
    bir sayfaya bir banka cizerken hangisinin hangi birimde oldugu lazim."""
    blk = sym_def(lib_id)
    name = lib_id.split(":", 1)[1]
    m = re.search(re.escape(f'(symbol "{name}_{unit}_1"'), blk)
    if not m:
        raise KeyError(f"{lib_id} birim {unit} yok")
    nxt = re.search(re.escape(f'(symbol "{name}_') , blk[m.end():])
    sub = blk[m.start(): m.end() + nxt.start()] if nxt else blk[m.start():]
    return {num: nm for nm, num in re.findall(
        r'\(name "([^"]*)".*?\(number "([^"]*)"', sub, re.S)}


def pin_xy(lib_id, num, x, y, rot=0):
    """Yerlestirilmis sembolun bir pininin MUTLAK konumu.
    KiCad'de sema Y ekseni asagi artiyor, sembol tanimi yukari — isaret ters.

    ORIJIN ONCE IZGARAYA OTURUYOR. Sheet.sym() de ayni seyi yapiyor;
    ikisi ayni yuvarlamayi yapmazsa hesaplanan nokta pinin yaninda
    kaliyor ve tel bosluga baglaniyor ('unconnected_wire_endpoint').
    Bir kere bu tuzaga dustum: sembolu 340 mm'ye koydum, 340/1.27
    tam sayi degil, butun pinler 1.27 kaydi."""
    x, y = g(x), g(y)
    dx, dy, _, _ = pins(lib_id)[str(num)]
    dy = -dy
    if rot == 90:
        dx, dy = dy, -dx
    elif rot == 180:
        dx, dy = -dx, -dy
    elif rot == 270:
        dx, dy = -dy, dx
    return (g(x + dx), g(y + dy))


class Sheet:
    def __init__(self, name, title, sheet_uuid, comment="", root_uuid=None,
                 paper="A3"):
        """sheet_uuid: kok semadaki sheet nesnesinin UUID'si.
        root_uuid: KOK SEMANIN kendi UUID'si — sembol ornegi yolunun oneki.
        Yol '/kok/sayfa' olmali; sadece '/sayfa' yazilirsa KiCad acilista
        dosyayi 'bozuk, duzelttim' sayiyor."""
        self.name, self.title = name, title
        self.suuid = sheet_uuid
        if root_uuid is None:
            import json as _j, os as _o
            root_uuid = _j.load(open(_o.path.join(
                _o.path.dirname(_o.path.abspath(__file__)),
                "sheet_uuids.json")))["__root__"]
        self.path = f"/{root_uuid}/{sheet_uuid}"
        self.comment = comment
        self.items, self.used = [], []
        self.paper = paper
        self._rots = {}
        # Guc sembolu sayaci. SAYFA NUMARASIYLA OFSETLI: her sayfa
        # 1'den baslarsa iki sayfada da #PWR01 olusuyor, KiCad bunu
        # cift referans sayip acilista "annotation errors" diyor.
        # Sayfa adinin basindaki iki hane (01_power -> 1) bloguu veriyor.
        try:
            self._pwr = int(name[:2]) * 100
        except ValueError:
            self._pwr = 0

    def _u(self):
        return str(uuid.uuid4())

    def sym(self, lib_id, ref, val, x, y, rot=0, fp="", unit=1, mirror=None):
        x, y = g(x), g(y)      # pin_xy ile AYNI yuvarlama — bkz. pin_xy
        # Yerlesim acisini KAYDET. pin_label/pin_power'a baska aci
        # verilirse pinler bambaska yerde hesaplaniyor ve teller
        # boslukta kaliyor — sema normal gorunuyor, ERC "unconnected
        # wire endpoint" diyor ve nedeni gorunmuyor. Bir kez oldu.
        self._rots[(g(x), g(y), lib_id)] = rot
        x, y = g(x), g(y)
        if lib_id not in self.used:
            self.used.append(lib_id)
        m = f" (mirror {mirror})" if mirror else ""
        self.items.append(f'''  (symbol (lib_id "{lib_id}") (at {x} {y} {rot}){m} (unit {unit})
    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid "{self._u()}")
    (property "Reference" "{ref}" (at {x} {y-5.08} 0)
      (effects (font (size 1.27 1.27))))
    (property "Value" "{val}" (at {x} {y-2.54} 0)
      (effects (font (size 1.27 1.27))))
    (property "Footprint" "{fp}" (at {x} {y} 0)
      (effects (font (size 1.27 1.27)) (hide yes)))
    (instances (project "{PROJ}"
      (path "{self.path}" (reference "{ref}") (unit {unit}))))
  )''')
        return self

    def power(self, kind, x, y, rot=0):
        """Guc/toprak sembolu. Referans NUMARALANDIRILMIS olmali:
        '#PWR?' birakilirsa KiCad acilista 'annotation errors' deyip
        otomatik numaralandiriyor ve dosyayi 'duzeltilmis' sayiyor."""
        x, y = g(x), g(y)
        self._pwr += 1
        ref = f"#PWR{self._pwr:03d}"
        lib_id = f"power:{kind}"
        if lib_id not in self.used:
            self.used.append(lib_id)
        self.items.append(f'''  (symbol (lib_id "{lib_id}") (at {x} {y} {rot}) (unit 1)
    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid "{self._u()}")
    (property "Reference" "{ref}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Value" "{kind}" (at {x} {y+(3.81 if rot==180 else -3.81)} 0)
      (effects (font (size 1.27 1.27))))
    (instances (project "{PROJ}"
      (path "{self.path}" (reference "{ref}") (unit 1))))
  )''')
        return self

    def wire(self, x1, y1, x2, y2):
        x1, y1, x2, y2 = g(x1), g(y1), g(x2), g(y2)
        self.items.append(f'''  (wire (pts (xy {x1} {y1}) (xy {x2} {y2}))
    (stroke (width 0) (type default)) (uuid "{self._u()}"))''')
        return self

    SHAPES = ("input", "output", "bidirectional", "tri_state", "passive")

    def glabel(self, text, x, y, shape="bidirectional", rot=0):
        # GECERSIZ SEKIL SESSIZCE OLDURUYOR. "power_in" yazmistim —
        # pin tipi olarak gecerli ama etiket sekli olarak degil. KiCad
        # o SAYFANIN TAMAMINI yuklemeyi biraktı: hiyerarsik ERC yine
        # calisti, netlist'te ikinci PHY hic yoktu, hicbir hata mesaji
        # yoktu. Uc saatlik hata avina donusebilirdi; burada patlasin.
        if shape not in self.SHAPES:
            raise ValueError(f"gecersiz etiket sekli {shape!r}; "
                             f"gecerliler: {', '.join(self.SHAPES)}")
        x, y = g(x), g(y)
        self.items.append(f'''  (global_label "{text}" (shape {shape}) (at {x} {y} {rot})
    (fields_autoplaced yes) (effects (font (size 1.27 1.27)) (justify left))
    (uuid "{self._u()}"))''')
        return self

    def label(self, text, x, y, rot=0):
        self.items.append(f'''  (label "{text}" (at {x} {y} {rot})
    (effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{self._u()}"))''')
        return self

    def text(self, s, x, y, size=1.6):
        esc = s.replace('"', "'").replace("\n", "\\n")
        self.items.append(f'''  (text "{esc}" (at {x} {y} 0)
    (effects (font (size {size} {size})) (justify left top)) (uuid "{self._u()}"))''')
        return self

    def nc(self, x, y):
        x, y = g(x), g(y)
        self.items.append(f'  (no_connect (at {x} {y}) (uuid "{self._u()}"))')
        return self

    def junction(self, x, y):
        self.items.append(f'''  (junction (at {x} {y}) (diameter 0) (color 0 0 0 0)
    (uuid "{self._u()}"))''')
        return self

    def _chk_rot(self, lib_id, x, y, rot):
        placed = self._rots.get((g(x), g(y), lib_id))
        if placed is not None and placed != rot:
            raise ValueError(
                f"{lib_id} @({x},{y}) {placed} derece yerlestirildi ama "
                f"pin {rot} derece ile isteniyor — teller pine degmez")

    def pin_label(self, lib_id, num, x, y, rot, text, shape="bidirectional", d=5.08):
        self._chk_rot(lib_id, x, y, rot)
        """Pinden kisa tel cek, ucuna global etiket koy. Yon pinin
        baktigi tarafa gore secilir."""
        px, py = pin_xy(lib_id, num, x, y, rot)
        _, _, prot, _ = pins(lib_id)[str(num)]
        ang = (prot + rot) % 360
        dxy = {0: (-d, 0), 180: (d, 0), 90: (0, d), 270: (0, -d)}[ang]
        ex, ey = g(px + dxy[0]), g(py + dxy[1])
        self.wire(px, py, ex, ey)
        lrot = {0: 180, 180: 0, 90: 270, 270: 90}[ang]
        self.glabel(text, ex, ey, shape, lrot)
        return self

    def pin_power(self, lib_id, num, x, y, rot, kind, d=3.81):
        self._chk_rot(lib_id, x, y, rot)
        px, py = pin_xy(lib_id, num, x, y, rot)
        _, _, prot, _ = pins(lib_id)[str(num)]
        ang = (prot + rot) % 360
        dxy = {0: (-d, 0), 180: (d, 0), 90: (0, d), 270: (0, -d)}[ang]
        ex, ey = g(px + dxy[0]), g(py + dxy[1])
        self.wire(px, py, ex, ey)
        self.power(kind, ex, ey, 180 if ang == 90 else 0)
        return self

    def link(self, a, b, mid=None):
        """Iki noktayi ortogonal telle birlestir. a,b = (x,y).
        mid: None ise once yatay sonra dikey; 'v' ise tersi."""
        (x1, y1), (x2, y2) = a, b
        if abs(y1 - y2) < 0.01:
            self.wire(x1, y1, x2, y2)
        elif abs(x1 - x2) < 0.01:
            self.wire(x1, y1, x2, y2)
        elif mid == "v":
            self.wire(x1, y1, x1, y2); self.wire(x1, y2, x2, y2)
        else:
            self.wire(x1, y1, x2, y1); self.wire(x2, y1, x2, y2)
        return self

    def P(self, lib_id, num, x, y, rot=0):
        """Yerlestirilmis sembolun pin konumu — kisayol."""
        return pin_xy(lib_id, num, x, y, rot)

    def pwr_flag(self, x, y):
        """ERC'nin 'bu ray nereden besleniyor' sorusunu susturur."""
        self.power("PWR_FLAG", x, y)
        return self

    def decaps(self, rail, n, val, x, y, ref0, per_row=8, pitch=17.78,
               vgap=22.86):
        """Bir rayin ayristirma kondansatorlerini dizi halinde koy.

        Bunlar semada nereye konuldugu onemli olmayan, hepsi ray-toprak
        arasinda duran parcalar; onemli olan YERLESIMDE her besleme
        topunun/bacaginin dibine dusmeleri. Semada dizi olarak duruyorlar
        ki BOM ve adet dogru ciksin, cizim de okunakli kalsin.
        """
        # ADIM 17.78 (14 x 1.27). 13 mm denedim: yatay duran
        # kondansatorlerin saplamalari komsuyla ust uste bindi ve butun
        # dizi tek aga birlesti. Gereken en az 15.24 (7.62 ray saplamasi
        # + 6.35 toprak saplamasi + govde), marjla 17.78.
        C = "Device:C"
        FC = "Capacitor_SMD:C_0402_1005Metric"
        for i in range(n):
            cx = x + (i % per_row) * pitch
            cy = y + (i // per_row) * vgap
            ref = f"C{ref0 + i}"
            self.sym(C, ref, val, cx, cy, rot=90, fp=FC)
            self.pin_label(C, "1", cx, cy, 90, rail, "input")
            self.pin_power(C, "2", cx, cy, 90, "GND")
        return n

    def overlaps(self):
        """Ayni dogru uzerinde UST USTE BINEN tel parcalarini bul.

        Bu uretecte en sinsi hata sinifi: iki sembolun saplamalari ayni
        yatay/dikey hatta denk gelince KiCad onlari tek dugum sayiyor ve
        iki ag sessizce birlesiyor. Bobin kisa devre oldu, 50R
        sonlandirma IOUT'u toprakladi — ikisi de sema goruntusunde
        normal duruyordu, ancak netlist'e bakinca anlasildi.
        Uretimde bagirmasi, ERC'yi beklemekten iyi."""
        segs = []
        for it in self.items:
            m = re.match(r'\s*\(wire \(pts \(xy ([-\d.]+) ([-\d.]+)\) '
                         r'\(xy ([-\d.]+) ([-\d.]+)\)\)', it)
            if m:
                segs.append(tuple(float(v) for v in m.groups()))
        bad = []
        for i, (x1, y1, x2, y2) in enumerate(segs):
            for x3, y3, x4, y4 in segs[i + 1:]:
                if abs(y1 - y2) < .01 and abs(y3 - y4) < .01 and abs(y1 - y3) < .01:
                    lo, hi = min(x1, x2), max(x1, x2)
                    lo2, hi2 = min(x3, x4), max(x3, x4)
                    ov = min(hi, hi2) - max(lo, lo2)
                elif abs(x1 - x2) < .01 and abs(x3 - x4) < .01 and abs(x1 - x3) < .01:
                    lo, hi = min(y1, y2), max(y1, y2)
                    lo2, hi2 = min(y3, y4), max(y3, y4)
                    ov = min(hi, hi2) - max(lo, lo2)
                else:
                    continue
                # Ortak uc paylasan parcalar kasitli birlestirme (T dugumu),
                # onlari bildirme. Kalanlar suphelidir: netlist'ten dogrula.
                if ov > 0.01 and not ({(x1, y1), (x2, y2)} & {(x3, y3), (x4, y4)}):
                    bad.append(((x1, y1, x2, y2), (x3, y3, x4, y4)))
        return bad

    def write(self, path):
        for a, b in self.overlaps():
            print(f"  ** UST USTE TEL: {a} ile {b} — {self.name}")
        seen, blocks = set(), []
        for l in self.used:
            for b in sym_defs(l):
                key = b[:80]
                if key not in seen:
                    seen.add(key); blocks.append(b)
        libs = "\n".join(blocks)
        out = f'''(kicad_sch (version {VER}) (generator "schlib") (uuid "{self._u()}")
  (paper "{self.paper}")
  (title_block
    (title "{self.title}")
    (rev "A")
    (company "{PROJ}")
    (comment 1 "{self.comment}")
    (comment 2 "Baglantilar: ../NETLIST.md")
  )
  (lib_symbols
{libs}
  )
{chr(10).join(self.items)}
)
'''
        open(path, "w", encoding="utf-8").write(out)
        return path
