# Technical rationale — four decisions

This document gives the four main decisions of the design and the
reason for each. The Turkish original is `docs/gerekce.md`; the longer form is
`TASARIM.md` in the repository root.

---

## 1. Why direct sampling

The predecessor of this project was a direct-conversion receiver with
a Tayloe detector. It was a good receiver, and it met three ceilings:

| Problem | With the Tayloe detector | With direct sampling |
|---|---|---|
| Instantaneous window | 96 kHz, the limit of the audio codec | **40 MHz**, all of HF at once |
| Phase noise | The noise of the local oscillator goes into the signal | **No local oscillator** |
| Transmit cleanliness | Software I/Q calibration, −25 dBc to −50 dBc | **No analogue modulator** |

When you remove the mixer you do not remove only a part. The phase
noise of the local oscillator, the intermodulation of the mixer, the
I/Q imbalance and the image frequency all go with it. Two sources of
error remain: the jitter of the sample clock, and the linearity of the
ADC. Both are measurable and both are in a datasheet. They are not
quantities that you chase with calibration.

**The cost, stated plainly:** all of HF enters the chip at the same
time. A megawatt broadcast station at 6 MHz takes the top of the ADC
while you listen at 14 MHz. This, not the number of bits, is the real
weakness of a direct-sampling receiver.

**The answer, without a compromise:** the usual answer is a
preselector, but a preselector removes the ability to see the whole
band. The AD9251 is a **dual** ADC, so the design does both:

```
main antenna -> protection -+- ADC-1A - no preselector ----> panorama and raw IQ
                            +- ADC-1B - switched bandpass -> serious receiver
```

One chip, one clock. The datasheet gives −110 dBc of crosstalk between
the channels, so the wide path does not pollute the narrow one. Board
C exists for this switched filter bank: 4 channels × 7 bands.

The band filters also do a second job that only appeared under
simulation. Above Nyquist, every signal folds onto the band, and after
the fold the receiver cannot tell it from the wanted signal. The
filters are the only protection. Two positions needed a transmission
zero for this reason; `VERIFICATION.md` records the measurement.

---

## 2. Why four channels — beam steering and noise cancelling

The second AD9251 makes four channels. All four take the same VCXO, so
they are phase-coherent. Three things start here that two separate
receivers cannot do:

**Noise cancelling.** The station is on a school campus, with
switching power supplies, LED lighting and chargers. If you sample the
noise with a separate antenna and subtract it adaptively from the main
channel, you can gain 10 dB to 20 dB in the real world.

**Direction finding.** Two antennas, a phase difference, an angle of
arrival. Radiosonde chasing, interference hunting, the direction of a
meteor trail.

**Beam forming.** Two vertical antennas give a steerable null. You can
suppress a station in a direction that you do not want.

All three depend on phase coherence, and phase coherence comes from
the common clock. This has a cost: one VCXO cannot drive two ADCs
directly, so a buffer with low additive jitter is necessary.

```
sqrt(100^2 + 50^2) = 112 fs        VCXO 100 fs + buffer 50 fs
```

From 100 fs to 112 fs, which does not matter. But the buffer must be a
part that specifies its additive jitter. If it does not, the whole
clock budget is lost.

Phase coherence is kept on the transmit side also: the four transmit
channels take the same clock, so the transmit beam can be steered.
This is why board C has four attenuators. The specification said two.
Phase coherence requires the chains to be **identical**, so you cannot
attenuate two channels and leave two.

---

## 3. Why the ECP5 (LFE5U-25F)

**A fully open toolchain.** Yosys, nextpnr-ecp5 and Project Trellis go
from source to bitstream with no vendor software. For a school club
this is not a question of licence but of continuity: when the student
graduates, the toolchain must still be possible to install, and it
must not be behind an account. The gateware in this repository is
really built with that chain.

**The variant follows from supply.** The LFE5U-45F cannot be obtained
in practice. The LFE5U-25F is available, and the `I` in `-7BG256I`
means the industrial temperature range, −40 °C to +100 °C. For a unit
that will sit on a cliff, in the sun, in a sealed box, that matters
more than the commercial grade.

**The size of the ECP5-25 set the architecture.** The naive approach,
a full-rate mixer for each of eight channels, needs 32 multipliers and
the device has 28. A two-stage DDC solves it:

```
ADC -> COMMON first decimator (CIC, no multipliers)  80 MHz -> 10 MHz
         +- channels 1..8: NCO, mixer, FIR -> 50 kHz
         |  (one multiplier set, shared in time)
         +- wide path: raw IQ output
```

The FIR load is 8 × 50 kHz × 100 taps, which is 40 M MAC/s, or about
half a multiplier at 80 MHz. The bottleneck is not the DSP count; it
is the timing closure of the full-rate CIC.

The measured use is LUT4 49 %, DSP 78 %, block RAM 21 %. There is room
in the logic and none in the multipliers, which shows that the design
was built to the multiplier budget.

**Why a BGA-256 was accepted.** The smaller packages do not give
enough I/O. Two ADCs need 28 data lines, two DACs need 31, the SDRAM
needs 39, and two gigabit PHYs need 24. With the control bus and the
board-to-board connections, the banks fill: bank 1 is at 32 of 32. A
0.8 mm pitch BGA is the limit that a 6-layer board can carry in the
standard process of the manufacturer.

---

## 4. Why a class-A power amplifier

Direct sampling uses no analogue modulator on transmit; the output of
the DAC is already clean. The only place that can spoil it is the
power amplifier. A class-AB stage makes crossover distortion and gives
back the spectral cleanliness that direct sampling won.

Class A does not make it. The cost is efficiency, about 233 W of heat
for 100 W of output, and a school station can pay it: a fixed
installation, mains power, a suitable heatsink. In exchange there is a
measurable intermodulation figure and a spectrum that needs no digital
predistortion.

What this forces onto the board: a bias servo for each device, flange
temperature measurement with a cut-off, and forward and reflected
power measurement with SWR protection. Most of the parts on board D
are this protection and feedback chain. The output stage itself is
four IRFP250N devices.

**Two consequences were measured, not assumed.**

The bias servo has a single-fault destruction path. If the measurement
arm opens, the measured current reads zero and the integrator drives
the gate to the supply rail. Simulation gives 57.6 A and 2878 W in
each device, against a continuous limit of 214 W. A gate clamp does
not solve it, because the transconductance is 8 S and 1 V above the
threshold already gives 8 A. The board detects the condition already,
but `PA_INHIBIT` removes only the driver supply, and in a class-A
stage the quiescent current does the damage. A signal that
short-circuits the integrator capacitor closes the path.

The mounting method matters more than the heatsink. The tab of the
TO-247 package is the drain, and this is a push-pull stage, so the
devices cannot go directly on a common heatsink. With an insulated
pad the device drops 55 °C inside itself at 58.3 W, and no heatsink
can correct that drop. The requirement is an AlN ceramic pad and
forced air, with a heatsink of 0.24 °C/W or better.
