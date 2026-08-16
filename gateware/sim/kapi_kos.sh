#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
#
# KAPI DUZEYI KOSU — sentez ciktisini RTL'in test tezgahiyla kostur.
#
#   ./sim/kapi_kos.sh
#
# NEDEN VAR. Buraya kadarki butun testler RTL'i kosturuyor. Ama karta
# giden sey RTL degil, SENTEZ CIKTISI. Aradaki fark bir hata sinifidir
# ve sessizdir:
#
#   baslangic degeri olmayan yazmac — simulasyonda X, sentezde 0
#   istemeden turetilmis mandal    — simulasyonda seffaf, kartta yaris
#   X yayilimi                     — simulasyonda hata gizler
#   yanlis genislik / isaret       — sentez sessizce kirpar
#
# Bu kosu ayni test tezgahini AYNI modulun sentezlenmis haline
# uyguluyor. Gecerse RTL ile netlist ayni davraniyor demektir.
#
# TAM CIP DEGIL, MODUL MODUL. Ust modulun kapi duzeyi kosusu icin
# DP16KD (blok RAM) ve MULT18X18D modelleri gerekiyor; yosys'in ecp5
# kutuphanesinde ikisi de KARA KUTU. MULT18X18D icin model yazildi
# (sim/mult18x18d_sim.v) ama DP16KD'nin cok kipli ikili port RAM'ini
# modellemek ayri bir is. O yuzden kapsam, blok RAM kullanmayan
# moduller — ki sentez surprizlerinin asil yasadigi yer de orasi:
# durum makineleri, sayaclar, kaydirma yazmaclari.
set -u
cd "$(dirname "$0")/.."
export PATH=~/opt/oss-cad-suite/bin:$PATH
CS=~/opt/oss-cad-suite/share/yosys/ecp5

# SENTEZ, TEZGAHIN KULLANDIGI PARAMETRELERLE YAPILMALI.
#
# Sentezlenmis bir netlistte parametre KALMAZ; degerler pismistir.
# Tezgah "#(.BOLEN(4))" diye ornekliyorsa netliste o parametre yok ve
# derleme "parameter BOLEN not found" diyerek duruyor. Ilk kosuda
# yedi modul boyle dustu.
#
# Cozum: yosys'e -chparam ile ayni degerleri vermek. Boylece
# sentezlenen sey, tezgahin kosturdugu seyle AYNI yapilandirma olur.
#
# "tezgah  modul  chparam...  --  kaynaklar"
testler=(
  "tb_nco       nco             -chparam FAZ_BIT 32 -- rtl/nco.v"
  "tb_cic       cic_azalt       -chparam GIRIS_BIT 14 -chparam CIKIS_BIT 24 -- rtl/cic_azalt.v"
  "tb_telafi    fir_telafi      -- rtl/fir_telafi.v"
  "tb_kontrol   kontrol_zinciri -chparam MS_CEVRIM 80 -- rtl/kontrol_zinciri.v"
  "tb_host      host_arayuz     -chparam ZAMAN_ASIMI 8000 -- rtl/host_arayuz.v rtl/uart.v rtl/kayit.v"
  "tb_spi       spi_ana         -chparam BOLEN 4 -chparam CIHAZ 4 -- rtl/spi_ana.v"
  "tb_mdio      mdio            -chparam BOLEN 4 -- rtl/mdio.v"
  "tb_kayit     kayit           -- rtl/kayit.v"
  "tb_rgmii_alis rgmii_alis     -- rtl/rgmii_alis.v"
  "tb_dac_cog   dac_cogullu     -chparam BIT 14 -- rtl/dac_cogullu.v"
)

gecen=0; kalan=0; atlanan=0
echo "KAPI DUZEYI KOSU — sentez ciktisi, RTL'in kendi tezgahiyla"
for t in "${testler[@]}"; do
  set -- $t
  tb=$1; mod=$2; shift 2
  cp=""
  while [ "$1" != "--" ]; do cp="$cp $1"; shift; done
  shift
  kaynak="$*"
  printf "  %-14s " "$mod"

  # sentezle — tezgahin parametreleriyle
  if ! yosys -q -p "verilog_defaults -add -Irtl; read_verilog -sv $kaynak; hierarchy -top $mod$cp; synth_ecp5 -top $mod -json /tmp/k_$mod.json" \
        >/tmp/k_$mod.log 2>&1; then
    echo "ATLANDI (sentez)"; atlanan=$((atlanan+1)); continue
  fi
  # BLOK RAM KULLANIYORSA ATLA — DP16KD modeli yok.
  #
  # Once JSON dosyasinda "DP16KD" kelimesini ariyordum ve ON BIR
  # MODULUN HEPSI atlandi — yosys kullanilmayan kara kutu modul
  # TANIMLARINI da dosyaya yaziyor. Dogru soru "tanimli mi" degil,
  # "hucre olarak KULLANILMIS mi".
  if python3 -c "
import json,sys
j=json.load(open('/tmp/k_$mod.json'))
m=j['modules'].get('$mod',{})
sys.exit(0 if any(h['type']=='DP16KD' for h in m.get('cells',{}).values()) else 1)
"; then
    echo "ATLANDI (blok RAM)"; atlanan=$((atlanan+1)); continue
  fi
  yosys -q -p "read_json /tmp/k_$mod.json; write_verilog -noattr /tmp/k_$mod.v" \
        >>/tmp/k_$mod.log 2>&1

  # PARAMETRE BILDIRIMLERINI GERI KOY — ETKISIZ OLARAK.
  #
  # -chparam ile dogru degerle sentezlemek yetmedi: netlistte deger
  # PISMIS oluyor ama BILDIRIM kalmiyor, ve tezgah hala
  # "#(.BOLEN(4))" diye ornekliyor. iverilog "parameter not found"
  # diyerek duruyor.
  #
  # Bildirimler netliste geri konuyor. Degerleri sentezde kullanilanla
  # AYNI — yani etkisizler; sadece tezgahin ornekleme sozdizimini
  # gecerli kiliyorlar. Farkli bir deger yazsaydik netlist ile tezgah
  # ayri seyler kosturur ve kosu yalan soylerdi.
  if [ -n "$cp" ]; then
    python3 - "$mod" $cp <<'PYEOF'
import re, sys
mod = sys.argv[1]
cift = sys.argv[2:]
bildirim = []
i = 0
while i < len(cift):
    if cift[i] == "-chparam":
        bildirim.append("  parameter %s = %s;" % (cift[i+1], cift[i+2]))
        i += 3
    else:
        i += 1
yol = "/tmp/k_%s.v" % mod
t = open(yol).read()
m = re.search(r"^module %s\b[^;]*;" % re.escape(mod), t, re.M | re.S)
if m and bildirim:
    t = t[:m.end()] + "\n" + "\n".join(bildirim) + t[m.end():]
    open(yol, "w").write(t)
PYEOF
  fi

  # TEZGAHIN KENDI YARDIMCI MODULLERI DE GEREKIYOR.
  #
  # tb_host sadece host_arayuz'u degil, yanina uart_al ve uart_ver'i
  # de ornekliyor. Onlar RTL olarak kalmali (test altindaki sey
  # host_arayuz), ama derlemede bulunmalari sart. Kaynak listesinden
  # DUT'un KENDI dosyasi cikarilip geri kalani tezgaha veriliyor.
  yardimci=""
  for k in $kaynak; do
    case "$k" in */$mod.v) ;; *) yardimci="$yardimci $k";; esac
  done

  # tezgahi netliste kosturarak derle
  if ! iverilog -g2012 -Irtl -I"$CS" -o "/tmp/kg_$mod" -s "$tb" \
        "sim/$tb.v" "/tmp/k_$mod.v" $yardimci sim/ecp5_sim.v \
        sim/mult18x18d_sim.v sim/ecp5_hucre.v 2>>/tmp/k_$mod.log; then
    echo "KALDI (derleme)"; kalan=$((kalan+1))
    tail -3 /tmp/k_$mod.log | sed 's/^/      /'
    continue
  fi
  cikti=$(timeout 400 vvp "/tmp/kg_$mod" 2>&1)
  if echo "$cikti" | grep -aq "GECTI" && ! echo "$cikti" | grep -aq "KALDI\|HATA"; then
    echo "GECTI"; gecen=$((gecen+1))
  else
    echo "KALDI"; kalan=$((kalan+1))
    echo "$cikti" | grep -a "HATA" | head -3 | sed 's/^/      /'
  fi
done
echo "  ----"
echo "  $gecen gecti, $kalan kaldi, $atlanan atlandi"
[ "$kalan" -eq 0 ]
