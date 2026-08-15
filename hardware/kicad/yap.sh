#!/bin/bash
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
  ozet=$(python3 gercek_yerlesim.py $K 2>/dev/null | grep -a "kritik parca elle")
  if [ -z "$ozet" ]; then
      echo "HATA: yerlesim uygulanmadi"; exit 1
  fi
  echo "  $ozet"
  python3 ayir.py $P.kicad_pcb   2>/dev/null | grep -a cakisma || true
  python3 ipek.py $K             >/dev/null 2>&1
  python3 elle_cek.py $P.kicad_pcb 2>/dev/null | grep -aE "^   " || true
  python3 dsn_yaz.py $P.kicad_pcb "$S/$K.dsn" 2>/dev/null | grep -a katman || true
fi

if [ "$2" = "route" ]; then
  echo "== $K yonlendiriliyor =="
  nohup "$S/jdk-21.0.12+8/bin/java" -jar "$S/fr1.9.0.jar" \
    -de "$S/$K.dsn" -do "$S/$K.ses" -mp 40 > "$S/logs/${K}_route.log" 2>&1 &
  disown
  echo "arka planda basladi"
fi

if [ "$2" = "import" ]; then
  echo "== $K iceri aliniyor =="
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
