#!/usr/bin/env python3
"""Kalan cakismalari ayir — KRITIK PARCALARA DOKUNMADAN.

    python3 ayir.py A_main/dogrudan_sdr_A.kicad_pcb

NEDEN AYRI ARAC: gercek_yerlesim.py'nin icinde calistiramiyoruz.
pcbnew ayni surecte ikinci LoadBoard'da sarmalanmamis SwigPyObject
donduruyor; GetFootprints() bile yok. Temiz surec = temiz kart.

Genel yasallastirma her parcayi esit gorup elle konumlandirdigim RF
zincirini de dagitiyordu. Burada sabit tutulanlar: entegre, konnektor,
trafo, bobin (UJTYL). Sadece pasifler kayiyor, ve yalnizca cakismayi
bitirecek kadar.
"""
import itertools, math, sys
import pcbnew

MM = 1e6
# Q ve K DE SABIT. Once sadece "UJTYL" yazmistim; ayirici D kartinin
# dort final transistorunu oynatti ve surucu-kapi mesafeleri
# 16.3/18.6 mm'ye kaydi. Bu kartta simetri bir suslemeye degil,
# cift harmonik bastirmasina karsilik geliyor. Roleler de sabit:
# LPF bankasinin sirasi bant sirasidir.
# H DE SABIT: MONTAJ DELIKLERI MEKANIK DATUM.
# D kartinda H2 (255,5) olmasi gerekirken (255.94, 2.96)'ya kaymisti
# — ayirici onu 50 V klemensinden (J30) itmis ve delik kartin
# dikdortgeninden cikmisti. Sonuc: civata basi + pul (M3 icin ~6.5 mm
# cap) klemense 2.17 mm kaliyordu. Sase montajinda metal standoff
# kullanilir; montaj sirasindaki bir kayma 50 V'u saseye baglar.
# Montaj deligi kacmaz, ETRAFINDAKI parca kacar.
SABIT = tuple("UJTYLQKH")


def elle_konulanlar(yol):
    """gercek_yerlesim.py'nin elle yerlestirdigi parcalar.

    Tip bazli sabit listesi yetmiyordu: dirençler oynatilabilir
    sayiliyordu ve simetrik yerlestirilen kapi/kol dirençleri
    sonradan kayiyordu. Karar tipten daha guclu — elle konulduysa
    sabit.
    """
    import os
    d = os.path.join(os.path.dirname(os.path.abspath(yol)), "sabit.txt")
    try:
        return {s.strip() for s in open(d) if s.strip()}
    except OSError:
        return set()


def kutu(f):
    lay = pcbnew.B_CrtYd if f.GetLayer() == pcbnew.B_Cu else pcbnew.F_CrtYd
    return f.GetCourtyard(lay).BBox()


def cakismalar(fps):
    # SIRALI, YOKSA SONUC TEKRARLANMIYOR.
    # b.Footprints() karttaki ic siraya gore geliyor ve o sira
    # UUID'lere bagli — her kurulumda farkli. Ayirici hangi cifti
    # once ittigi degisince farkli sonuca variyordu: iki kurulum
    # arasinda 38 parcanin konumu farkliydi, ve o yuzden bir
    # kurulumdan alinan SES otekine uymuyor, kart kisa devre
    # doluyordu.
    out = []
    for a, c in itertools.combinations(sorted(fps), 2):
        if fps[a].GetLayer() != fps[c].GetLayer():
            continue
        ka, kc = kutu(fps[a]), kutu(fps[c])
        if ka.GetWidth() > 0 and kc.GetWidth() > 0 and ka.Intersects(kc):
            out.append((a, c))
    return out


def ayir(b, tur=400, elle=(), pay=2.0):
    """Cakisan parcalari it-kak ile ayir.

    TUR SAYISI 60'TAN 400'E CIKARILDI. 1500 de denendi: A ve C'de
    ayni sonucu verdi (5 ve 8), D'de on dakikayi asti. Yani algoritma
    yakinsamiyor, kalan cakismalar tur sayisiyla cozulmuyor — 400
    ayni sonucu cok daha ucuza veriyor. D kartina tuzak
    kondansatorleri ve yedinci filtre bolumu eklenince 162 cakisma
    olustu ve 60 turda 54'u cozulemedi. Kart doluluk orani %49, yani
    yer VAR — yalnizca yineleme butcesi yetmiyordu. Yer olmasaydi
    tur artirmak da cozmezdi; once onu olctum.

    Cakisan parcalari birbirinden it — KART SINIRI ICINDE KALARAK.

    SINIR KISITI SONRADAN EKLENDI. Ayirici parcalari iterken kartin
    kenarini hic gormuyordu; iceri_al() ondan ONCE calistigi icin de
    kimse geri cekmiyordu. Olculdu: D kartinda R400'un (kuplorun 51R
    sonlandirmasi) 2. pedi x=278.4'e, yani 275.1 mm'lik kartin 3.3 mm
    DISINA cikti. Disari tasan bakir uretimde yok — parca
    lehimlenemez ve DRC bunu "kart disi ped" diye ayri bir kural
    olarak da aramaz.

    Kisit PEDLERE gore: govde disari sarkabilir (kenar montaj
    konnektorlerinde zaten oyle), pedler sarkamaz.
    """
    elle = set(elle)
    kutu_b = b.GetBoardEdgesBoundingBox()
    sx0, sy0 = kutu_b.GetLeft() / MM + pay, kutu_b.GetTop() / MM + pay
    sx1, sy1 = kutu_b.GetRight() / MM - pay, kutu_b.GetBottom() / MM - pay
    kenar_mont = kenar_montajlar(b)

    def sinirla(fp):
        """Pedleri kart icine geri cek."""
        if fp.GetReference() in kenar_mont:
            return
        pedler = [q.GetBoundingBox() for q in fp.Pads()]
        if not pedler:
            return
        sol = min(k.GetLeft() for k in pedler) / MM
        sag = max(k.GetRight() for k in pedler) / MM
        ust = min(k.GetTop() for k in pedler) / MM
        alt = max(k.GetBottom() for k in pedler) / MM
        dx = dy = 0.0
        if sol < sx0:
            dx = sx0 - sol
        elif sag > sx1:
            dx = sx1 - sag
        if ust < sy0:
            dy = sy0 - ust
        elif alt > sy1:
            dy = sy1 - alt
        if dx or dy:
            q = fp.GetPosition()
            fp.SetPosition(pcbnew.VECTOR2I(int(q.x + dx * MM),
                                           int(q.y + dy * MM)))

    for _ in range(tur):
        fps = {f.GetReference(): f for f in b.Footprints()}
        cift = cakismalar(fps)
        if not cift:
            return 0
        for a, c in cift:
            pa, pc = fps[a].GetPosition(), fps[c].GetPosition()
            dx, dy = (pc.x - pa.x) / MM, (pc.y - pa.y) / MM
            d = math.hypot(dx, dy)
            if d < 1e-6:
                # TAM UST USTE. Yon vektoru sifir olunca itme de sifir
                # oluyordu ve cift sonsuza kadar cakisik kaliyordu
                # (D kartinda R101/R103). Kesisen bir yon uydur.
                dx, dy, d = 1.0, 0.0, 1.0
            ka, kc = kutu(fps[a]), kutu(fps[c])
            it = (min(ka.GetRight(), kc.GetRight())
                  - max(ka.GetLeft(), kc.GetLeft())) / MM
            iy = (min(ka.GetBottom(), kc.GetBottom())
                  - max(ka.GetTop(), kc.GetTop())) / MM
            adim = min(it, iy) / 2 + 0.15
            for ref, s in ((a, -1), (c, 1)):
                if ref[0] in SABIT or ref in elle:
                    continue
                q = fps[ref].GetPosition()
                fps[ref].SetPosition(pcbnew.VECTOR2I(
                    int(q.x + s * dx / d * adim * MM),
                    int(q.y + s * dy / d * adim * MM)))
                sinirla(fps[ref])

    # SON CARE: SIKISAN PARCAYI BOS YERE TASI.
    #
    # It-kak yerel calisiyor: dort toroidin ortasina sikismis bir
    # kondansator hangi yone itilse baska bir toroide giriyor ve
    # dongu bosa donuyor. D kartinda C11 ve C512 tam bunu yapiyordu
    # (dokuz cakismanin kaynagi iki parcaydi).
    #
    # Burada oynayabilen taraf spiral tarama ile en yakin GERCEKTEN
    # bos noktaya tasiniyor. Uzaklasmak istenmez ama ic ice gecmis
    # bir parcadan iyidir: kart basilir, parca takilamaz.
    fps = {f.GetReference(): f for f in b.Footprints()}
    kalan = cakismalar(fps)
    tasindi = 0
    for a, c in list(kalan):
        for ref in (a, c):
            if ref[0] in SABIT or ref in elle:
                continue
            fp = fps[ref]
            k0 = kutu(fp)
            w, h = k0.GetWidth() / MM, k0.GetHeight() / MM
            p0 = fp.GetPosition()
            bulundu = None
            for r in [x * 0.5 for x in range(4, 60)]:
                for aci in range(0, 360, 15):
                    nx = p0.x / MM + r * math.cos(math.radians(aci))
                    ny = p0.y / MM + r * math.sin(math.radians(aci))
                    fp.SetPosition(pcbnew.VECTOR2I(int(nx * MM), int(ny * MM)))
                    sinirla(fp)
                    kk = kutu(fp)
                    if any(kk.Intersects(kutu(fps[o]))
                           for o in fps if o != ref
                           and fps[o].GetLayer() == fp.GetLayer()
                           and kutu(fps[o]).GetWidth() > 0):
                        continue
                    bulundu = fp.GetPosition()
                    break
                if bulundu:
                    break
            if bulundu:
                fp.SetPosition(bulundu)
                tasindi += 1
                break
            fp.SetPosition(p0)
    fps = {f.GetReference(): f for f in b.Footprints()}
    return len(cakismalar(fps))


def kenar_montajlar(b):
    """Gercek kenar montaj konnektorleri — AYAK IZI ADINDAN.

    Once "pedi kenara yakin olan J" diye geometriden turetmistim.
    Dongusel cikti: alt sira dikey basliklar zaten hatali sekilde
    kenara dayanmis durumdaydi, o yuzden kenar montaj sayilip
    duzeltmeden muaf tutuldular. Parcanin NE OLDUGU nereye
    dustugunden okunmaz.

    Kenar montaj = govdesi kartin disina sarkan, pedi kenara dayanmak
    ZORUNDA olan tip. Dikey pin baslik boyle degil: govdesi de pedi de
    kartin uzerinde durur, kenardan uzak durmali.
    """
    imza = ("EdgeMount", "Edge_Mount", "Castellated")
    return {fp.GetReference() for fp in b.Footprints()
            if any(s in str(fp.GetFPID().GetLibItemName()) for s in imza)}


def iceri_al(b, pay=2.0):
    """Pedleri kart disinda kalan parcalari iceri cek.

    Kenar montaj konnektorlerini gercek_yerlesim.koy() zaten pedlerine
    gore hizaliyor. Ama kenar bayragi verilmeden yerlestirilenler
    (magjack'ler, guc girisi, alt sira basliklar) kat planindaki
    koordinatta duruyor ve govdeleriyle birlikte pedleri de disari
    tasabiliyor — A kartinda 33 ped boyleydi. Lehimlenecek bakir
    orada yok; parca takilamaz.

    Sadece OTELIYOR, dondurmuyor: kenar montajin yonu zaten dogru
    ayarlanmis, aciyi bozmak SMA'nin agzini ice cevirir.

    PAY 2 mm. Once 0.3, sonra 1 mm'ydi ve alt sira basliklar (J60/J62/J63/
    J65/J66) tam oraya dayaniyordu. Delikli ped icin dar: kart
    kenarini kesen frezenin yol toleransi +-0.1..0.15 mm, delik
    toleransi +-0.05 mm. Ust uste binince halka kenardan kirilir ve
    ped bakiri kartin yan yuzunde aciga cikar. 1 mm'de pedler
    kurtuluyordu ama yonlendirici pedlerle kenar arasindaki seride
    iz cekiyordu; 2 mm o seridi kapatiyor ve kenar boyunca temiz bir
    kusak birakiyor. Kenar montaj konnektorleri bu payin disinda — onlarda pedin kenara dayanmasi
    zaten istenen sey (gercek_yerlesim.PED_ICERI).
    """
    k = b.GetBoardEdgesBoundingBox()
    x0, y0 = k.GetLeft() / MM, k.GetTop() / MM
    x1, y1 = k.GetRight() / MM, k.GetBottom() / MM
    n = 0
    # KENARA DAYALI THT PARCALARI ATLA. Magjack'in on yuzu kart
    # kenariyla hizali olmak zorunda (yoksa kablo fisi kenara
    # carpar); pay uygulayip iceri cekersek o hizayi bozuyoruz.
    hizali = {"J40", "J41"}
    # KENAR MONTAJ MUAF. gercek_yerlesim.koy() onlari zaten pedlerine
    # gore hizaladi; 1 mm pay uygularsak SMA'yi iceri ceker ve RF
    # yolunda sap birakiriz.
    kenar_mont = kenar_montajlar(b)
    for fp in b.Footprints():
        r = fp.GetReference()
        if r in hizali or r in kenar_mont:
            continue
        pedler = list(fp.Pads())
        if not pedler:
            continue
        # DONMUS PED KUTUSU. GetSizeX/GetSizeY pedin kendi
        # cercevesindeki olcu, donme uygulanmamis; ustelik butun
        # pedlerin en buyugu hem x hem y icin kullaniliyordu.
        # gercek_yerlesim.koy()'da ayni hata kenar montaj
        # konnektorlerinin pedini 1.14 mm kartin disina cikarmisti.
        # Burada su an hicbir parcayi etkilemiyor (genel dolgu zaten
        # kenardan 8 mm iceride durduruyor) ama olcut yanlis olarak
        # kalirsa kenara yakin yerlestirilen ilk parcada patlar.
        kutular = [q.GetBoundingBox() for q in pedler]
        sol = min(q.GetLeft() for q in kutular) / MM
        sag = max(q.GetRight() for q in kutular) / MM
        ust = min(q.GetTop() for q in kutular) / MM
        alt = max(q.GetBottom() for q in kutular) / MM
        dx = dy = 0.0
        if sol < x0 + pay:
            dx = (x0 + pay) - sol
        elif sag > x1 - pay:
            dx = (x1 - pay) - sag
        if ust < y0 + pay:
            dy = (y0 + pay) - ust
        elif alt > y1 - pay:
            dy = (y1 - pay) - alt
        if dx or dy:
            p = fp.GetPosition()
            fp.SetPosition(pcbnew.VECTOR2I(int(p.x + dx * MM),
                                           int(p.y + dy * MM)))
            n += 1
    return n


# Bos tutulacak koridorlar: (kart, x0, y0, x1, y1).
# Simetrik aglarin izleri buradan gecmek zorunda. Genel dolgu buraya
# parca birakirsa elle cekilen duz hat pedin ustunden geciyor ve
# kisa devre oluyor — D'de 12 kisa devre, C'de 22 ag cizilemedi.
# Koridor bos olmali ki iz aynasi ile ayni uzunlukta kalabilsin;
# dolasmak zorunda kalan iz zaten simetriyi bozar.
KORIDOR = {
    "dogrudan_sdr_D": [(105, 12, 195, 50)],       # final -> surucu
    "dogrudan_sdr_C": [(0, 18, 350, 32), (0, 73, 350, 87),
                       (0, 128, 350, 142), (0, 183, 350, 197)],
    "dogrudan_sdr_A": [(0, 112, 60, 212)],        # RX zincirleri
}


def koridor_bosalt(b, yol, elle):
    """Koridorlardaki serbest parcalari disari cikar."""
    import os
    ad = os.path.basename(yol).replace(".kicad_pcb", "")
    kutular = KORIDOR.get(ad, [])
    if not kutular:
        return 0
    n = 0
    for fp in sorted(b.Footprints(), key=lambda f: f.GetReference()):
        r = fp.GetReference()
        if r[0] in SABIT or r in elle:
            continue
        q = fp.GetPosition()
        x, y = q.x / MM, q.y / MM
        for x0, y0, x1, y1 in kutular:
            if x0 <= x <= x1 and y0 <= y <= y1:
                # en yakin kenardan disari it
                d = {"ust": y - y0, "alt": y1 - y, "sol": x - x0,
                     "sag": x1 - x}
                yon = min(d, key=d.get)
                ny, nx = y, x
                # KORIDORUN HEMEN DIBINE DEGIL, UZAGINA.
                # 3 mm disari itince parcalar finallerin (y=8) ve
                # suruculerin (y=52) tam ustune dustu ve kapi izleri
                # yine cizilemedi. Koridorun disi da kalabalik;
                # cikarilan parca kenara dogru surulmeli.
                if yon == "ust":
                    ny = max(2.0, y0 - 14)
                elif yon == "alt":
                    ny = y1 + 14
                elif yon == "sol":
                    nx = max(2.0, x0 - 14)
                else:
                    nx = x1 + 14
                fp.SetPosition(pcbnew.VECTOR2I(int(nx * MM), int(ny * MM)))
                n += 1
                break
    return n


def kenar_grubu(b):
    """Kenara degen konnektorleri "kenar_montaj" grubuna al.

    Bu konnektorlerin pedleri kart kenarina DEGMEK zorunda — SMA'nin
    ve kart-arasi baglantinin isi bu. Varsayilan kenar boslugu kurali
    57 hata uretiyordu. .kicad_dru bu gruba muafiyet yaziyor; bloke
    muafiyet yanlis olurdu, o zaman kartin ORTASINDAKI gercek bir
    ihlal de gorunmez olurdu.

    Burada, gercek_yerlesim.py'de degil: orada pcbnew proxy'leri
    bozuluyor (GetPosition() bile). Temiz surec sart.
    """
    for g in list(b.Groups()):
        if g.GetName() == "kenar_montaj":
            b.Remove(g)
    kutu_b = b.GetBoardEdgesBoundingBox()
    en, boy = kutu_b.GetWidth() / MM, kutu_b.GetHeight() / MM
    g = pcbnew.PCB_GROUP(b)
    g.SetName("kenar_montaj")
    n = 0
    for fp in b.Footprints():
        if not fp.GetReference().startswith("J"):
            continue
        q = fp.GetPosition()
        x, y = q.x / MM, q.y / MM
        if x < 8 or y < 8 or x > en - 8 or y > boy - 8:
            g.AddItem(fp)
            n += 1
    if n:
        b.Add(g)
    return n


KENAR_KURALI = """
# Kenar montaj konnektorleri. Pedleri kart kenarina DEGMEK zorunda:
# SMA'nin ve kart-arasi baglantinin isi bu. Varsayilan kenar boslugu
# kurali bunlari hata sayiyor, oysa tasarim boyle.
# Muafiyet GRUBA bagli, bloke degil: kartin ORTASINDAKI gercek bir
# kenar ihlali gorunur kalsin.
(rule "kenar montaj pedleri"
  (condition "A.memberOfGroup('kenar_montaj')")
  (constraint edge_clearance (min 0mm)))
"""


def kenar_kurali_yaz(yol):
    """Grubu olusturan betik, grubu ANLAMLI KILAN kurali da yazsin.

    NEDEN BURADA: kenar_montaj grubu uc kartta da kuruluyordu ama
    .kicad_dru dosyasi yalnizca A kartinda vardi — elle yazilmis ve
    oteki iki karta hic kopyalanmamis. Sonuc: D kartinda 10,
    C kartinda benzeri sayida copper_edge_clearance ihlali, hepsi
    kenar montaj konnektorlerinin pedlerinden ve hepsi YANLIS ALARM.
    Gercek ihlaller o gurultunun icinde gorunmez oluyordu.

    Grubu kuran yerin kurali da yazmasi, dorduncu bir kart eklendiginde
    kimsenin hatirlamasini gerektirmiyor. Var olan kurallara
    DOKUNMUYORUZ: A'nin kendi RF/LVDS/GUC kurallari duruyor, kural
    zaten varsa dosya oldugu gibi birakiliyor.
    """
    import os
    dru = os.path.splitext(os.path.abspath(yol))[0] + ".kicad_dru"
    try:
        mevcut = open(dru, encoding="utf-8").read()
    except OSError:
        mevcut = ""
    if "kenar_montaj" in mevcut:
        return False
    if not mevcut.strip():
        mevcut = "(version 1)\n"
    open(dru, "w", encoding="utf-8").write(mevcut.rstrip() + "\n"
                                           + KENAR_KURALI)
    return True


if __name__ == "__main__":
    yol = sys.argv[1]
    b = pcbnew.LoadBoard(yol)
    once = len(cakismalar({f.GetReference(): f for f in b.Footprints()}))
    elle = elle_konulanlar(yol)
    kor = koridor_bosalt(b, yol, elle)
    ic = iceri_al(b)
    kalan = ayir(b, elle=elle)
    grup = kenar_grubu(b)
    kural = kenar_kurali_yaz(yol)
    b.Save(yol)
    print(f"{yol.split('/')[-1]}: {once} cakisma -> {kalan}, "
          f"{ic} iceri, {kor} koridordan cikarildi, "
          f"{grup} kenar konnektoru gruplandi"
          + (", kenar kurali yazildi" if kural else ""))
