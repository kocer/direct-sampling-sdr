#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: CERN-OHL-S-2.0
# Kart uretim zinciri — ADIM ATLAMAK MUMKUN OLMASIN.
#
#   ./yap.sh D          yerlesim + elle cekim + DSN
#   ./yap.sh D route    ustune yonlendiriciyi de kosturur
#   ./yap.sh D import   yonlendirici bitince sonucu alir
#
# NEDEN VAR: bu zinciri elle kosturdugum her seferde bir adim
# atladim ve emek bosa gitti. pcb_kur karti netlistten yeniden
# kuruyor ve butun izleri siliyor; yani yerlesim degisince
# yonlendirme de gecersiz. DSN'i elle_cek'ten ONCE alirsam
# yonlendirici simetrik aglari sokuyor. Karti DSN'den SONRA
# yeniden kurarsam SES ile kart uyusmuyor.
#
# Sira degismez:
#   pcb_kur -> yerlesim -> ayir -> ipek -> elle_cek -> dsn_yaz
set -e
# YERLESIM TEKRARLANABILIR OLMALI — METIN KARMASINI SABITLE.
# Python 3.3'ten beri metin karmasi her SURECTE farkli tohumlaniyor,
# yani bir set'i dolasma sirasi kosudan kosuya degisiyor. Zincirdeki
# kodun birkac yerinde referans adlarindan olusan set'ler dolasiliyor
# ve esitlikler "ilk gorulen" lehine bozuluyor: ayni girdiyle iki
# kosu farkli yerlesim uretiyordu (D'de C110 bir kosuda x=21.6'ya,
# otekinde x=71.0'a; A'da R450 12 mm oteye).
#
# NEDEN ONEMLI: SES dosyasi TEK bir yerlesime ait. Kart yeniden
# kurulunca parcalar oynarsa yonlendiricinin izleri artik baska
# pedlere denk geliyor — 45 kisa devrenin bilinen sebebi bu.
#
# Bulunan iki yeri sorted() ile duzelttim (gercek_yerlesim.kalanlar).
# Tohumu burada da sabitliyorum cunku garanti tek bir fonksiyonda
# degil, ALTI ayri betikte ve ileride yazilacak kodda da gerekiyor.
# Olculdu: bu satirla ust uste iki kosu bit-bit ayni DSN veriyor.
export PYTHONHASHSEED=0
K=$1
case $K in
  A) P=A_main/dogrudan_sdr_A ;;
  C) P=C_rf/dogrudan_sdr_C ;;
  D) P=D_pa/dogrudan_sdr_D ;;
  *) echo "kullanim: ./yap.sh {A|C|D} [route|import]"; exit 1 ;;
esac
S=${SCRATCH:-/tmp}
Q="$(dirname "$0")"
cd "$Q"

# KURULUM HER ZAMAN KOSAR, "import"ta da.
# Ice alma karti sifirlamiyor (ses_oku artik iz silmiyor), yani
# import'u iki kez kosturunca dikis via'lari birikiyordu: ikinci
# turda 20 maske koprusu ve 8 kisa devre. Kurulum karti netlistten
# yeniden yapiyor, yani her import temiz zeminden basliyor.
if true; then
  echo "== $K kuruluyor =="
  # SEGFAULT'A IZIN VER. gercek_yerlesim karti KAYDEDIYOR, sonra
  # pcbnew cikarken cokuyor (A kartinda duzenli oluyor). set -e
  # bunu hata sayip zinciri durduruyordu; kaydedilmis karti
  # kullanamiyorduk. Kaydin gerceklestigini asagida dogruluyoruz.
  python3 pcb_kur.py $K          >/dev/null 2>&1 || true
  # YERLESIMIN GERCEKTEN KOSTUGUNU DOGRULA.
  # "|| true" ciddi bir cokmeyi gizliyordu: gercek_yerlesim kenar
  # cizgilerini silerken cokuyor, hicbir sey kaydetmiyor, ve kart
  # pcb_kur'un kuvvet-guduml u yerlesimiyle kaliyordu. Zincir
  # calisiyor gorunuyor, uretilen kart yanlis.
  # Ozet satiri ancak kayit basariliysa yaziliyor; onu ariyoruz.
  # TEMEL DENETIM — YERLESIMDEN ONCE, EN ALT KATMAN.
  #
  # Sembolun pin numarasi ayak izinin ped numarasiyla tutmuyorsa
  # netlist o baglantiyi sessizce dusuruyor; ERC semaya bakip teli
  # goruyor, DRC bagsiz pedi ihlal saymiyor. Bu oturumda kart
  # olduren hatalarin hepsi bu katmandaydi (ADC'nin acik pedi,
  # PHY'nin yanlis paketi, kristalin govdeye giden XO ucu).
  #
  # BURADA DURUYOR cunku asagisi bosa gider: hatali bir semadan
  # uretilen yerlesim ve saatlerce koşan yonlendirme cope gider.
  python3 temel_denetim.py $K 2>/dev/null | grep -aE "=> KART|UYARI" || true
  python3 temel_denetim.py $K >/dev/null 2>&1 || { echo "HATA: sembol/ayak izi uyusmuyor"; exit 1; }
  ozet=$(python3 gercek_yerlesim.py $K 2>/dev/null | grep -a "kritik parca elle")
  if [ -z "$ozet" ]; then
      echo "HATA: yerlesim uygulanmadi"; exit 1
  fi
  echo "  $ozet"
  # AYIR COKERSE ZINCIR DURSUN.
  # "|| true" bir sozdizimi hatasini sessizce yuttu ve uc kart
  # cakismalari HIC ayrilmadan kuruldu; belirtisi sadece ozet
  # satirinin kaybolmasiydi. Ayni sinif hata nextpnr'da da vardi.
  python3 ayir.py $P.kicad_pcb 2>&1 | grep -a cakisma
  [ ${PIPESTATUS[0]} -eq 0 ] || { echo "HATA: ayir cokti"; exit 1; }
  # FIDUCIAL + TEST NOKTALARI — AYIR'DAN SONRA.
  # Once ayir'dan ONCE kosuyordu ve bedeli olculdu: test noktalari
  # cakisma uretiyor, ayir onlari cozerken AYIRMA KONDANSATORLERINI
  # itiyor ve kondansatorler bacaklarindan uzaklasiyor. D kartinda
  # uc INA240 ve A'da flash bellek boyle kondansatorsuz kaliyordu.
  # Bu arac zaten kendi bos yer aramasini yapiyor, ayir'a ihtiyaci
  # yok. pcb_kur karti yeniden kurdugu icin her kosuda cagriliyor.
  python3 montaj_isaret.py $K 2>/dev/null | grep -aE "eklendi|bulunamadi" || true
  # AYIRMA KONDANSATORLERI — AYIR'DAN SONRA.
  # Yerlesimin icinde, ayir'dan once kosuyordu ve ayir onlari
  # bacaklarindan uzaga itiyordu (olculdu: 4.7 mm -> 17.9 mm).
  # "|| true" BIR COKMEYI GIZLEDI. Gecise ikinci bir adim eklenince
  # NameError aldi ve hicbir sey yapmadi; zincir rc=0 ile bitti,
  # ozet satiri kayboldu, kart ayirma kondansatorleri cekilmemis
  # halde uretildi. Ayni sinif hata daha once ayir'da da olmustu.
  # Gecis EN AZ BIR ozet satiri yazmali; yazmiyorsa dur.
  ayirma_ozet=$(python3 gercek_yerlesim.py --ayirma $K 2>/dev/null | grep -a cekildi)
  [ -n "$ayirma_ozet" ] || { echo "HATA: ayirma gecisi cikti vermedi"; exit 1; }
  echo "$ayirma_ozet"
  # AYIRMA GECISINDEN SONRA KISA BIR AYIRMA TURU DAHA.
  # Kondansatorleri bacaklarina cekerken bos yer aramasi bazilarini
  # buyuk parcalarin (LPF toroidleri) courtyard'ina sokuyor. Ikinci
  # tur onlari birkac milimetre itiyor — ilk turdaki gibi yirmi
  # milimetre otelemiyor, cunku artik cozulecek cakisma az.
  python3 ayir.py $P.kicad_pcb 2>&1 | grep -a cakisma
  [ ${PIPESTATUS[0]} -eq 0 ] || { echo "HATA: ikinci ayir cokti"; exit 1; }
  python3 ipek.py $K             >/dev/null 2>&1
  python3 elle_cek.py $P.kicad_pcb 2>/dev/null | grep -aE "^   " || true
  # AGSIZ PED DENETIMI — DSN'DEN ONCE, VE ZINCIRI DURDURUR.
  # Sembol pin numarasi ayak izi ped numarasiyla tutmazsa ag hicbir
  # yere gitmiyor ve ne ERC ne DRC bunu goruyor. Ilk kosuda 31 boyle
  # ped vardi; ikisi kart olduruyordu (PHY ayak izi yanlis parcaya
  # aitti, kristalin XO ucu govde pedine gidiyordu).
  python3 ped_denetim.py $K 2>/dev/null || { echo "HATA: agsiz ped var, yukariya bak"; exit 1; }
  python3 dsn_yaz.py $P.kicad_pcb "$S/$K.dsn" 2>/dev/null | grep -a katman || true
fi

if [ "$2" = "route" ]; then
  echo "== $K yonlendiriliyor =="
  # JAVA VE JAR YOLU DEGISKENLE. Once ikisi de sabit yazilmisti
  # ($S/jdk-21.0.12+8/bin/java) ve o dizin gecici bir calisma
  # klasoruydu — silinince zincirin yonlendirme adimi sessizce
  # hicbir sey yapmaz oldu. freerouting 1.9.0 JDK 17 ile
  # derlenmis (MANIFEST'ten okundu), sistem java'si kosturuyor.
  JAVA=${JAVA:-java}
  FR_JAR=${FR_JAR:-$S/fr1.9.0.jar}
  if [ ! -f "$FR_JAR" ] && [ ! -x "${FR_BIN:-$S/fr2/freerouting-2.3.0-linux-x64/bin/freerouting}" ]; then
      echo "HATA: ne freerouting 2.3.0 ne de 1.9.0 jar bulundu"
      exit 1
  fi
  mkdir -p "$S/logs"
  # FREEROUTING 2.3.0 — 1.9.0'DAN NEDEN CIKTIK.
  #
  # 1.9.0'da (Ekim 2023) yonlendirme ile optimizasyon ayri asamalar
  # ve OPTIMIZASYON TEK CEKIRDEKLI. Olctum: D kartinin autoroute'u
  # 31 saniye, ardindan gelen optimizasyon 3.5 saatte bitmedi ve
  # .ses ancak en sonda yaziliyor — yani saatlerce bekleyip elde
  # hicbir sey olmuyordu. Durdurmayi denedim: -mp 0/1/2/5 ve
  # -oit 0/1/10/50/99, sekiz kosu, hicbiri optimizasyonu sinirlamiyor.
  #
  # 2.3.0'da -mt optimizasyonu is parcaciklarina bolmus (varsayilan
  # cekirdek sayisi - 1) ve her tur ayri raporlaniyor: kac ag kaldi,
  # kac ihlal var, ne kadar surdu. 1.9.0 kara kutuydu.
  #
  # Kendi Java 25 runtime'iyla geliyor (jpackage); kutuda 17 var,
  # jar tek basina calismiyor ("class file version 69.0").
  FR_BIN=${FR_BIN:-$S/fr2/freerouting-2.3.0-linux-x64/bin/freerouting}
  if [ -x "$FR_BIN" ]; then
      nohup "$FR_BIN" \
        -de "$S/$K.dsn" -do "$S/$K.ses" -mp 100 > "$S/logs/${K}_route.log" 2>&1 &
  else
      echo "  NOT: $FR_BIN yok, 1.9.0'a dusuluyor (cok daha yavas)"
      nohup "$JAVA" -jar "$FR_JAR" \
        -de "$S/$K.dsn" -do "$S/$K.ses" -mp 40 > "$S/logs/${K}_route.log" 2>&1 &
  fi
  disown
  echo "arka planda basladi"
fi

if [ "$2" = "import" ]; then
  echo "== $K iceri aliniyor =="
  # YERLESIM PARMAK IZI — SES BU KARTA MI AIT?
  # Yukaridaki kurulum blogu karti netlistten YENIDEN kuruyor. O
  # yeniden kurulum, SES'in uretildigi DSN'deki yerlesimle birebir
  # ayni olmazsa yonlendiricinin izleri baska pedlere denk gelir ve
  # kart sessizce kisa devre dolar (45 kisa devrenin sebebi buydu ve
  # hicbir adim sikayet etmemisti). Zincir artik tekrarlanabilir;
  # bu sinama o tekrarlanabilirligin BOZULDUGUNU haber veriyor.
  python3 - "$P.kicad_pcb" "$S/$K.dsn.parmak" <<'PY' || exit 1
import sys
sys.path.insert(0, ".")
import dsn_yaz, pcbnew
try:
    beklenen = open(sys.argv[2]).read().strip()
except OSError:
    print("HATA: parmak izi yok — dsn_yaz'i yeniden kostur"); sys.exit(1)
simdiki = dsn_yaz.parmak(pcbnew.LoadBoard(sys.argv[1]))
if simdiki != beklenen:
    print("HATA: yerlesim SES ile uyusmuyor — ice alma iptal.")
    print(f"  DSN  {beklenen[:16]}")
    print(f"  kart {simdiki[:16]}")
    print("  Zincir tekrarlanabilirligini kaybetmis; once onu duzelt.")
    sys.exit(1)
print("  yerlesim parmak izi tutuyor")
PY
  python3 - "$P.kicad_pcb" "$S/$K.ses" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, ".")
import ses_oku, pcbnew
s, i, v, a = ses_oku.oku(sys.argv[1], sys.argv[2])
b = pcbnew.LoadBoard(sys.argv[1])
b.BuildConnectivity()
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[1])
open("/tmp/yap_sonuc.txt", "w").write(f"{i} iz + {v} via, {a} ag atlandi")
PY
  cat /tmp/yap_sonuc.txt; echo
  # TOPRAK DIKISI ICE ALMADAN SONRA, DRC'DEN ONCE.
  # Dokum adalarini birbirine baglayan via'lar ve dokumun
  # ulasamadigi QFN toprak bacaklarina giden kisa saplar.
  python3 dikis.py $P.kicad_pcb 2>/dev/null | tail -2
  kicad-cli pcb drc $P.kicad_pcb -o "$S/$K.rpt" --severity-error >/dev/null 2>&1
  python3 - "$S/$K.rpt" <<'PY'
import re, sys, collections
print("DRC:", dict(collections.Counter(
    re.findall(r'^\s*\[(\w+)\]', open(sys.argv[1], encoding="utf-8").read(), re.M))))
PY
fi
