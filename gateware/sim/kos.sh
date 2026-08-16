#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2026 TA4DTA
# SPDX-License-Identifier: GPL-3.0-only
# Butun test tezgahlarini kostur.
#
#   ./sim/kos.sh
#
# NEDEN TEK KOMUT: her modulu ayri kosturmak zamanla unutuluyor ve
# bir degisiklik baska bir modulu bozdugunda haftalar sonra
# gorunuyor. Kart gelmeden once guvendigimiz tek sey bu testler.
set -u
cd "$(dirname "$0")/.."
export PATH=~/opt/oss-cad-suite/bin:$PATH

testler=(
  # ECP5 ilkel modelleri — bunlar YANLIS olursa tb_ust gecer ama
  # hicbir sey kanitlamaz, o yuzden ONCE kosuyor.
  "tb_ecp5     sim/tb_ecp5_sim.v sim/ecp5_sim.v"
  "tb_nco      sim/tb_nco.v      rtl/nco.v"
  "tb_cic      sim/tb_cic.v      rtl/cic_azalt.v"
  "tb_telafi   sim/tb_telafi.v   rtl/fir_telafi.v"
  "tb_paket    sim/tb_paket.v    rtl/paketleyici.v"
  "tb_kontrol  sim/tb_kontrol.v  rtl/kontrol_zinciri.v"
  "tb_dac      sim/tb_dac.v      rtl/dac_cikis.v"
  "tb_adc      sim/tb_adc.v      rtl/adc_giris.v"
  "tb_host     sim/tb_host.v     rtl/uart.v rtl/host_arayuz.v rtl/kayit.v"
  "tb_mdio     sim/tb_mdio.v     rtl/mdio.v"
  "tb_spi      sim/tb_spi.v      rtl/spi_ana.v"
  "tb_fifo     sim/tb_fifo.v     rtl/fifo_gecis.v"
  "tb_kayit    sim/tb_kayit.v    rtl/kayit.v"
  "tb_rgmii    sim/tb_rgmii.v    rtl/rgmii_veris.v"
  "tb_duc      sim/tb_duc.v      rtl/duc.v rtl/nco.v"
  "tb_ddc      sim/tb_ddc.v      rtl/nco.v rtl/karistirici.v rtl/cic_azalt.v"
  # BU IKISI YAZILMISTI AMA LISTEYE HIC EKLENMEMISTI — yani iki modul
  # testi olmasina ragmen suite'te hic kosmuyordu. dac_cogullu'nun
  # yarim hiz hatasi tam da bu yuzden aylarca gorunmedi.
  "tb_duc_dort sim/tb_duc_dort.v rtl/duc_dort.v rtl/duc.v rtl/nco.v"
  "tb_dac_cog  sim/tb_dac_cog.v  rtl/dac_cogullu.v"
  "tb_rgmii_al sim/tb_rgmii_alis.v rtl/rgmii_alis.v"
  "tb_udp      sim/tb_udp.v      rtl/rgmii_alis.v rtl/udp_ayikla.v"
)

# ---------------------------------------------------------------
# UST MODUL SENTEZDEN GECIRILIYOR.
#
# Bu adim YOKTU ve bedeli agir oldu. On iki tezgah gecerken ust
# modul hic elaborate edilmiyordu: port sayisi, modul arasi genislik
# uyumu, kartta karsiligi olmayan port — hicbiri sinanmiyordu.
# adc_giris.v aylarca YANLIS ARAYUZLE durdu (seri LVDS varsayiyordu,
# parca cogullanmis paralel CMOS), cunku kendi tezgahi kendi yanlis
# varsayimini dogruluyordu ve ustte kimse bakmiyordu.
#
# Sentez dogruluk kaniti degil ama BAGLANTI kaniti: baglanmayan
# port, yanlis genislik, eksik modul buradan gecemez.
# ---------------------------------------------------------------
gecen=0; kalan=0
printf "  %-12s " "ust (sentez)"
if yosys -q -p "read_verilog rtl/*.v; synth_ecp5 -top ust -json /tmp/ust_kontrol.json" 2>/tmp/ust_hata.txt; then
  echo "GECTI"; gecen=$((gecen+1))
else
  echo "KALDI"; kalan=$((kalan+1)); head -5 /tmp/ust_hata.txt
fi

# LPF de karta karsi dogrulaniyor: her ust portunun gercek bir
# ball'i var mi. Uyari varsa gateware kartla konusmuyor demektir.
printf "  %-12s " "lpf (kart)"
if python3 sentez/lpf_yaz.py 2>/dev/null | grep -q "uyari yok"; then
  echo "GECTI"; gecen=$((gecen+1))
else
  echo "KALDI"; kalan=$((kalan+1)); python3 sentez/lpf_yaz.py 2>/dev/null | tail -12
fi

for t in "${testler[@]}"; do
  set -- $t
  ad=$1; shift
  # GECTI OLCUTU: "KALDI" YOKSA GECTI.
  # Once sadece "GECTI" ariyordu. Bir tezgah once GECTI yazip sonra
  # duserse ya da ikinci bir asamada kalirsa, o kosu GECTI sayiliyordu.
  # Simdi cikti tutuluyor: KALDI/HATA gecen bir kosu her halukarda duser.
  cikti=$(iverilog -g2012 -o "/tmp/$ad" "$@" 2>&1) || { printf "  %-12s KALDI (derleme)\n" "$ad"; kalan=$((kalan+1)); echo "$cikti" | head -3; continue; }
  cikti=$(timeout 400 vvp "/tmp/$ad" 2>&1)
  if echo "$cikti" | grep -aq "GECTI" && ! echo "$cikti" | grep -aq "KALDI\|HATA\|ERROR"; then
    printf "  %-12s GECTI\n" "$ad"; gecen=$((gecen+1))
  else
    printf "  %-12s KALDI\n" "$ad"; kalan=$((kalan+1))
  fi
done
# ---------------------------------------------------------------------
# TUM SISTEM TESTI — ayri kosuyor cunku BUTUN rtl'i istiyor.
#
# Bu tezgah gelene kadar sim/ dizininde ondokuz test vardi ve hicbiri
# ust modulu kosturmuyordu; ust.v sadece sentezden geciyordu. Yani her
# modul tek basina dogruydu ve birlestirilmis sistem hic
# calistirilmamisti. Entegrasyon hatalari tam o boslukta yasar.
printf "  %-12s " "tb_ust"
cikti=$(iverilog -g2012 -o /tmp/tb_ust sim/tb_ust.v sim/ecp5_sim.v rtl/*.v 2>&1) \
  && cikti=$(timeout 900 vvp /tmp/tb_ust 2>&1)
if echo "$cikti" | grep -aq "TUM SISTEM TESTI GECTI"; then
  echo "GECTI"; gecen=$((gecen+1))
else
  echo "KALDI"; kalan=$((kalan+1)); echo "$cikti" | grep -a "HATA" | head -6
fi

echo "  ----"
echo "  $gecen gecti, $kalan kaldi"
[ "$kalan" -eq 0 ]
