#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
"""BIAS SERVOSU — kararlilik ve ARIZA davranisi.

    python3 bias_sim.py

D kartinda her final MOSFET'in kendi kapali cevrim bias servosu var:

    0.01R olcu direnci -> INA240A1 (x20) -> LM358 integrator
    (10k / 1uF) -> 100R -> gecit (Ciss ~2700 pF) -> gm ~8 S -> drenaj

Paralel MOSFET'lerde ayri servo DOGRU tercih: esik gerilimleri
farkliysa biri akimin cogunu ceker ve olur. Ama servo bir GERI
BESLEME cevrimi ve iki soru soruluyor:

  1 KARARLI MI. Salinan bir bias servosu 100 W'lik bir katta
    yikicidir; dinlenme akimi kare dalga gibi gider gelir.

  2 ARIZADA NE OLUYOR. Bu asil soru. Integrator "olculen akim
    hedefe esit olana kadar gecidi yukselt" diyor. Olcum kolu
    KOPARSA — direnc acilirsa, INA240 beslemesiz kalirsa, +5V
    +12V'den sonra gelirse — olculen akim SIFIR gorunur, hata
    kapanmaz ve integrator gecidi rayina kadar surer.

    Bu bir tek-ariza yikim yolu: koruma devresi korudugu seyi
    oldurur. Ustelik yavas degil — hizini bu arac olcuyor.

ARAC NE YAPIYOR. Cevrim SPICE'ta kuruluyor; MOSFET'in ici degil,
sinir kosullari modelleniyor (gecit kapasitesi, gecis iletkenligi,
esik gerilimi). Uc kosu:

    ac      cevrim kazanci ve faz payi
    kalkis  enerjilenmede gecit ve akim
    ariza   t=20 ms'te olcum kolu koparilinca ne oluyor
"""
import math
import re
import subprocess
import sys

RS = 0.01           # olcu direnci (ohm)
G_INA = 20.0        # INA240A1 kazanci
R_INT = 10e3        # integrator giris direnci
C_INT = 1e-6        # integrator geri besleme kondansatoru
R_GATE = 100.0      # gecit seri direnci
R_PULL = 10e3       # gecit asagi cekme
CISS = 2700e-12     # IRFP250N giris kapasitesi (veri sayfasi)
GM = 8.0            # gecis iletkenligi, kol basina (gen_02_final)
VTH = 3.2           # esik gerilimi, tipik
IDQ = 1.67          # cihaz basina hedef dinlenme akimi (A)
V_RAY = 10.5        # LM358'in +12V'ta ulasabildigi en yuksek cikis

VSET = IDQ * RS * G_INA     # hedef gerilim: 0.334 V


def ortak(dc_yolu=False):
    """Cevrimin ortak parcalari.

    dc_yolu: integrator kondansatorune paralel buyuk direnc. AC
    kosusunda SART — geri besleme sadece kondansatordense DC'de
    cevrim aciktir, calisma noktasi tanimsiz kalir ve ngspice
    lineerlestirecek bir nokta bulamaz (ilk denemede "argument out
    of range for db" ve butun genlikler sifir cikti). 10 Mohm,
    0.016 Hz'in ustunde tepkiyi degistirmiyor.
    """
    ek = ["Rdc vn vg 10meg"] if dc_yolu else []
    return ek + [
        "* bias servosu",
        # --- integrator: LM358, tek besleme, GBW 1 MHz
        "Eop vg_ham 0 vp vn 100k",
        "Rgbw vg_ham vg_i 1k",
        "Cgbw vg_i 0 159n",          # 1k*159n -> 1 MHz GBW kutbu
        # cikis rayi siniri
        "Bclamp vg 0 V = min(max(V(vg_i), 0), %.3f)" % V_RAY,
        "Rint %s vn %.1f" % ("imeas", R_INT),
        "Cint vn vg %.4e" % C_INT,
        # --- gecit agi
        "Rg vg gate %.1f" % R_GATE,
        "Rp gate 0 %.1f" % R_PULL,
        "Cg gate 0 %.4e" % CISS,
    ]


def ac_netlist():
    """Cevrim kazanci: cevrim imeas'te kirilip oradan enjekte ediliyor.

    MOSFET burada LINEER gecis iletkenligi olarak modelleniyor.
    Kucuk isaret analizinde dogrusu bu: max(Vgs-Vth,0) ifadesi
    calisma noktasi etrafinda zaten gm'e lineerlesir, ama ngspice'in
    o noktayi bulabilmesi icin cevrimin DC'de kapali olmasi gerekiyor.
    """
    s = ["* cevrim kazanci"]
    s += ["Vset vp 0 %.4f" % VSET]
    s += ["Vin imeas 0 DC %.4f AC 1" % VSET]
    s += ortak(dc_yolu=True)
    # gecit -> drenaj akimi -> olcu direnci -> INA240 (lineer)
    s += ["Eid ida 0 gate 0 %.6f" % (GM * RS * G_INA)]
    s += [".ac dec 100 0.01 10meg", ".print ac vdb(ida) vp(ida)", ".end"]
    return "\n".join(s)


def gecici_netlist(ariza=False, kesme=False):
    """Zaman cozumu: enerjilenme, olcum kolu kopmasi, kesme devresi.

    kesme: onerilen duzeltme. Ariza gorulunce bir MOSFET integrator
    kondansatorunu KISA DEVRE yapiyor. Iki isi birden goruyor:

      1 Integratoru sifirliyor. Sadece gecidi asagi cekseydik
        integrator rayda dolu kalirdi ve ariza gecince gecit bir
        anda 10.5 V'a sicrardi — duzeltme kendisi bir tuzak olurdu.

      2 Kondansator kisa devreyken opamp VSET'i takip ediyor, yani
        VG = 0.33 V. Esik 3.2 V; cihaz kapali.

    Kesme, FPGA'nin zaten urettigi sarttan geliyor: "Idq kurulan
    degerden %20 sapti -> bias servosu bozuk". O sart bu arizada
    saglaniyor (olculen akim sifir gorunuyor), ama PA_INHIBIT bugun
    sadece SURUCUYU kesiyor. A sinifi bir katta olduren sey surus
    degil, dinlenme akimi.
    """
    s = ["* gecici"]
    s += ["Vset vp 0 PWL(0 0 1m %.4f)" % VSET]
    s += ortak()
    if kesme:
        # FPGA arizayi 1 ms icinde gorup kesiyor (ADC okuma hizi)
        s += ["Skill vg vn kill 0 anahtar", ".model anahtar SW "
              "vt=2.5 ron=8 roff=1g"]
        s += ["Bkill kill 0 V = (time > 21m) ? 5 : 0"]
    # gercek geri besleme: akim -> olcu direnci -> INA240 -> imeas
    if ariza:
        # t=20 ms'te olcum kolu kopuyor: imeas sifira dusuyor
        s += ["Bmeas imeas 0 V = (time < 20m) ? "
              "(%.3f * max(V(gate) - %.2f, 0) * %.4f * %.1f) : 0"
              % (GM, VTH, RS, G_INA)]
    else:
        s += ["Bmeas imeas 0 V = %.3f * max(V(gate) - %.2f, 0) * %.4f * %.1f"
              % (GM, VTH, RS, G_INA)]
    s += ["Bid id 0 V = %.3f * max(V(gate) - %.2f, 0)" % (GM, VTH)]
    # KOSU SURESI. Once 60 ms kosuyordum ve servo hic acilmiyordu:
    # integrator 33.4 V/s rampaliyor (VSET / (Rint*Cint)), esik
    # gerilimine varmasi tek basina ~96 ms. Yani "hedefe oturmuyor"
    # sonucu tasarimin degil, kosunun kisaligindandi.
    s += [".tran 200u 500m", ".print tran v(gate) v(id)", ".end"]
    return "\n".join(s)


def kos(nl, ad):
    yol = "/tmp/bias_%s.cir" % ad
    open(yol, "w").write(nl)
    r = subprocess.run(["ngspice", "-b", yol], capture_output=True, text=True)
    v = []
    for satir in r.stdout.splitlines():
        m = re.match(r"\s*\d+\s+([-\d.eE+]+)\s+([-\d.eE+]+)(?:\s+([-\d.eE+]+))?",
                     satir)
        if m:
            try:
                v.append(tuple(float(g) for g in m.groups() if g is not None))
            except ValueError:
                pass
    return v, r.stderr


if __name__ == "__main__":
    kotu = 0
    print("BIAS SERVOSU — hedef %.2f A/cihaz, VSET %.3f V" % (IDQ, VSET))
    print()

    # ---------------------------------------------------------- kararlilik
    v, err = kos(ac_netlist(), "ac")
    if not v:
        print("ac kosusu cikti vermedi")
        print(err[:400])
        kotu += 1
    else:
        # FAZ RADYAN GELIYOR, DERECE DEGIL. ngspice'in vp() cikisini
        # once derece sandim ve faz payini 182 derece diye okudum —
        # bir integrator icin anlamsiz bir sayi. Gercek deger
        # 1.6 rad = 91.7 derece, yani beklenen +90.
        #
        # ISARET DUZENI. Olculen sey DONUS ORANI T = ida/imeas ve
        # opampin evirmesi zaten icinde. Cevrim imeas <- ida diye
        # kapaniyor, yani karakteristik denklem 1 - T = 0 ve
        # kararsizlik T = +1'de. Bu yuzden faz payi, arg(T)'nin
        # sifira olan uzakligi: |arg(T)|.
        gecis = None
        for satir in v:
            if len(satir) < 3:
                continue
            f, db, faz_rad = satir[0], satir[1], satir[2]
            if db <= 0 and gecis is None:
                gecis = (f, math.degrees(faz_rad))
        if gecis is None:
            print("KARARLILIK: cevrim 10 MHz'e kadar birim kazanci gecmiyor")
        else:
            f0, faz = gecis
            pay = abs(faz)
            print("KARARLILIK")
            print("   birim kazanc frekansi : %.1f Hz" % f0)
            print("   faz payi              : %.0f derece" % pay)
            print("   yerlesme zaman sabiti : %.1f ms" % (1000 / (2 * math.pi * f0)))
            if pay < 45:
                print("   ** FAZ PAYI YETERSIZ **")
                kotu += 1
            else:
                print("   kararli")
        print()

    # ---------------------------------------------------------- kalkis
    v, err = kos(gecici_netlist(False), "kalkis")
    if v:
        son = v[-1]
        oturma = next((x[0] for x in v if abs(x[2] - IDQ) <= IDQ * 0.05), None)
        print("KALKIS")
        if oturma:
            print("   hedefin %%5'ine oturma  : %.0f ms" % (oturma * 1000))
        print("   500 ms'te gecit %.2f V, akim %.2f A (hedef %.2f A)"
              % (son[1], son[2], IDQ))
        if abs(son[2] - IDQ) > IDQ * 0.1:
            print("   ** HEDEFE OTURMUYOR **")
            kotu += 1
        print()

    # ---------------------------------------------------------- ARIZA
    v, err = kos(gecici_netlist(True), "ariza")
    if v:
        onceki = [x for x in v if x[0] < 20e-3]
        sonraki = [x for x in v if x[0] >= 20e-3]
        print("ARIZA — t=20 ms'te olcum kolu kopuyor")
        if onceki:
            print("   kopmadan once : gecit %.2f V, akim %.2f A"
                  % (onceki[-1][1], onceki[-1][2]))
        if sonraki:
            son = sonraki[-1]
            # gecit rayina ne kadar surede variyor
            varis = next((x[0] for x in sonraki if x[1] >= V_RAY * 0.99), None)
            print("   kopmadan sonra: gecit %.2f V, akim %.1f A" % (son[1], son[2]))
            print("   drenaj gucu   : %.0f W  (50 V x %.1f A, cihaz basina)"
                  % (50.0 * son[2], son[2]))
            if varis:
                print("   gecit rayina %.1f ms'te variyor"
                      % ((varis - 20e-3) * 1000))
            if son[2] > IDQ * 3:
                print()
                print("   ** TEK ARIZA YIKIM YOLU **")
                print("   Olcum kolu koptugunda integrator hatayi kapatamiyor")
                print("   ve gecidi rayina suruyor. IRFP250N'in surekli guc")
                print("   siniri 214 W (25 C); yukaridaki deger cihaz basina.")
                print("   Gecitte kelepce ya da asiri akim kesmesi YOK.")
                kotu += 1

    # ------------------------------------------------- onerilen duzeltme
    v, err = kos(gecici_netlist(True, kesme=True), "kesme")
    if v:
        sonraki = [x for x in v if x[0] >= 21e-3]
        if sonraki:
            tepe = max(x[2] for x in sonraki)
            son = sonraki[-1]
            print()
            print("DUZELTME — kesme integrator kondansatorunu kisa devre yapiyor")
            print("   ariza sonrasi tepe akim : %.2f A  (%.0f W)"
                  % (tepe, tepe * 50))
            print("   500 ms'te gecit %.2f V, akim %.2f A" % (son[1], son[2]))
            if tepe < 2.0:
                print("   cihaz guvende")
                kotu -= 1
    sys.exit(1 if kotu else 0)
