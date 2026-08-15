#!/usr/bin/env python3
"""
Telif ve lisans metninin TEK kaynagi.

NEDEN TEK DOSYA: sema dosyalari uretecten cikiyor ve her ./yap.sh
kosusunda sifirdan yaziliyor. Telif satirini uretilmis .kicad_sch
dosyasina elle koyarsan ilk kosuda ucar. Bu yuzden satir ureticinin
CIKTISINA basiliyor, ve ureticiler de bu dosyadan okuyor.

Adi degistirmek gerekirse burasi ve kok dizindeki COPYRIGHT dosyasi
degisir, baska hicbir yer degismez.

TELIF SAHIBININ ADI: cagri isareti kullaniliyor. Yasal ad BTK'daki
amator telsizcilik belgesinde ve okuldaki kayitta bu cagri isaretine
baglidir. Yasal adi acikca yazmak istersen asagidaki SAHIP satirini
degistir; baska dosyaya dokunmana gerek yok.
"""

YIL = "2026"
SAHIP = "TA4DTA"

TELIF = f"Copyright (c) {YIL} {SAHIP}"

# Donanim: sema, yerlesim ve onlari ureten betikler.
LISANS_HW = "CERN-OHL-S-2.0"
# HDL ve arac yazilimi.
LISANS_SW = "GPL-3.0-only"
# Belgeler.
LISANS_DOC = "CC-BY-SA-4.0"

# Sema title_block'una basilan iki satir.
SEMA_TELIF = f"{TELIF} - lisans {LISANS_HW}"
SEMA_LISANS = ("Donanim CERN-OHL-S-2.0 | HDL ve yazilim GPL-3.0-only | "
               "belgeler CC-BY-SA-4.0")


def spdx(lisans, yorum="//"):
    """Kaynak dosyanin basina konacak iki satirlik basligi dondurur."""
    return (f"{yorum} SPDX-FileCopyrightText: {TELIF}\n"
            f"{yorum} SPDX-License-Identifier: {lisans}\n")
