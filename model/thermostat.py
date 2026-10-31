"""Python model of the LabVIEW VI "Le Thermostat d'Alerte".

Reproduces the VI logic (100 ms loop, comparisons, 3-zone status, alert
counter) and compares the original version with the corrected one:

  original  : overheat = T > threshold          counter += 1 on every cycle in alert
  corrected : hysteresis 75 / 70 °C              counter += 1 on the rising edge only
              + validation of out-of-range measurements

Usage:  python thermostat.py      (writes ../docs/chattering.png and prints a summary)
"""
from dataclasses import dataclass
from pathlib import Path
import math
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LOOP_MS = 100          # Wait (ms) in the While loop -> 10 Hz
T_COLD = 10.0          # "Alerte Froid" (the challenge): T < 10 °C
SENSOR_MIN, SENSOR_MAX = 0.0, 100.0


def zone(t, threshold):
    """Case structure with ranges: '..9' cold, '10..threshold' nominal, else overheat."""
    if t < T_COLD:
        return "FROID"
    if t > threshold:
        return "SURCHAUFFE"
    return "NOMINAL"


@dataclass
class OriginalVI:
    threshold: float = 75.0
    alerts: int = 0                      # Shift Register

    def step(self, t):
        hot = t > self.threshold         # Greater?
        cold = t < T_COLD                # Less?
        if hot or cold:
            self.alerts += 1             # counts loop iterations, not events
        return hot, cold


@dataclass
class CorrectedVI:
    threshold: float = 75.0
    hysteresis: float = 5.0              # 75 / 70 °C
    alerts: int = 0
    hot: bool = False
    cold: bool = False
    invalid: int = 0

    def step(self, t):
        if math.isnan(t) or not SENSOR_MIN <= t <= SENSOR_MAX:
            self.invalid += 1            # rejected, outputs unchanged
            return self.hot, self.cold
        was_hot, was_cold = self.hot, self.cold
        if self.hot:
            self.hot = t > self.threshold - self.hysteresis
        else:
            self.hot = t > self.threshold
        if self.cold:
            self.cold = t < T_COLD + self.hysteresis
        else:
            self.cold = t < T_COLD
        if (self.hot and not was_hot) or (self.cold and not was_cold):
            self.alerts += 1             # rising edge = one event
        return self.hot, self.cold


def temperature_profile(seconds=60, seed=3):
    """Slow heating up to the threshold, noisy plateau around 75 °C, then cooling."""
    random.seed(seed)
    out = []
    for i in range(int(seconds * 1000 / LOOP_MS)):
        s = i * LOOP_MS / 1000
        if s < 15:
            base = 40 + 35 * s / 15
        elif s < 40:
            base = 75 + 1.2 * math.sin(s * 1.3)
        else:
            base = 75 - 1.8 * (s - 40)
        t = base + random.gauss(0, 0.8)
        if abs(s - 30) < 0.05:
            t = 250.0                    # sensor glitch (out of range)
        out.append((s, t))
    return out


def main():
    prof = temperature_profile()
    a, b = OriginalVI(), CorrectedVI()
    rows = []
    for s, t in prof:
        ha, _ = a.step(t)
        hb, _ = b.step(t)
        rows.append((s, t, ha, hb, a.alerts, b.alerts))

    def toggles(col):
        return sum(1 for i in range(1, len(rows)) if rows[i][col] != rows[i - 1][col])

    print(f"Original : LED toggled {toggles(2):3d} times, counter = {a.alerts}")
    print(f"Corrected: LED toggled {toggles(3):3d} times, counter = {b.alerts}, invalid samples rejected = {b.invalid}")

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 7.5), sharex=True,
                                        gridspec_kw={"height_ratios": [2.2, 1, 1]})
    s = [r[0] for r in rows]
    ax1.plot(s, [min(r[1], 100) for r in rows], color="#444", lw=1, label="temperature (°C)")
    ax1.axhline(75, color="#d64545", ls="--", lw=1, label="threshold 75 °C")
    ax1.axhline(70, color="#e0a800", ls=":", lw=1, label="hysteresis low 70 °C")
    ax1.annotate("glitch 250 °C\n(rejected by the corrected VI)", xy=(30, 100), xytext=(32, 55), fontsize=8,
                 arrowprops=dict(arrowstyle="->", color="#777"))
    ax1.set_ylim(35, 102)
    ax1.set_ylabel("°C")
    ax1.legend(fontsize=8, loc="lower center")
    ax1.set_title("Le Thermostat d'Alerte — original vs corrected logic", fontsize=11)

    ax2.step(s, [r[2] for r in rows], where="post", color="#d64545", lw=1)
    ax2.set_yticks([0, 1], ["off", "on"])
    ax2.set_title(f"Original — LED « Alerte Surchauffe »: {toggles(2)} toggles (chattering), counter = {a.alerts}",
                  fontsize=9, loc="left")
    ax3.step(s, [r[3] for r in rows], where="post", color="#2e9e44", lw=1.5)
    ax3.set_yticks([0, 1], ["off", "on"])
    ax3.set_title(f"Corrected — hysteresis 75/70 °C + rising edge: {toggles(3)} toggles, counter = {b.alerts}",
                  fontsize=9, loc="left")
    ax3.set_xlabel("time (s) — loop at 10 Hz")
    fig.tight_layout()
    out = Path(__file__).resolve().parent.parent / "docs/chattering.png"
    fig.savefig(out, dpi=130)
    print("saved", out)


if __name__ == "__main__":
    main()
