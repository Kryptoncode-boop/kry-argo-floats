"""
interpret_argo.py - turn the CSV saved by argo_lookup.py into a plain-language
reading of one Argo profile: water structure, nutrients, plankton, oxygen, quality.

Usage:
    python interpret_argo.py argo_1902763_cycle34.csv
    python interpret_argo.py 1902763           # newest argo_1902763_cycle*.csv in this folder
    python interpret_argo.py FILE --plot       # also save a PNG (needs: pip install matplotlib)
    python interpret_argo.py FILE --strict     # never use uncalibrated (QC 3) sensor data

Needs numpy and pandas only. Depth means pressure in dbar (1 dbar is about 1 m).

How values are chosen: for each parameter the *_ADJUSTED value is used where its
QC flag is 1 or 2, otherwise the raw value where its QC flag is 1 or 2. Interpolated
points (QC 8) are ignored. If a biogeochemical sensor has no good points at all
(typical for oxygen/pH in a fresh real-time profile), its uncalibrated QC 3 values
are used and clearly labelled PROVISIONAL, unless you pass --strict.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

GOOD = (1, 2)
MIN_POINTS = 5
BGC = {"DOXY", "CHLA", "CHLA_FLUORESCENCE", "BBP700", "CDOM", "NITRATE", "PH_IN_SITU_TOTAL",
       "DOWNWELLING_PAR", "DOWN_IRRADIANCE380", "DOWN_IRRADIANCE412", "DOWN_IRRADIANCE443",
       "DOWN_IRRADIANCE490", "DOWN_IRRADIANCE555"}
ORDER = ["TEMP", "PSAL", "DOXY", "CHLA", "BBP700", "CDOM", "NITRATE", "PH_IN_SITU_TOTAL",
         "DOWNWELLING_PAR", "DOWN_IRRADIANCE380", "DOWN_IRRADIANCE412", "DOWN_IRRADIANCE443",
         "DOWN_IRRADIANCE490", "DOWN_IRRADIANCE555"]
LINES = []


def say(text=""):
    print(text)
    LINES.append(text)


def find_csv(arg):
    if os.path.isfile(arg):
        return arg
    if arg.isdigit():
        files = sorted(glob.glob(f"argo_{arg}_cycle*.csv"), key=os.path.getmtime)
        if files:
            return files[-1]
    sys.exit(f"Can't find '{arg}'. Give a CSV made by argo_lookup.py, or a WMO number "
             "with its CSV in this folder.")


def column(df, name):
    return df[name] if name in df else pd.Series(np.nan, index=df.index)


def select(df, depth, p, strict):
    """Usable points for parameter p -> (DataFrame[z, v], label, n_raw) or None."""
    if p not in df or df[p].notna().sum() == 0:
        return None
    raw, adj = df[p], column(df, f"{p}_ADJUSTED")
    qc, adjqc = column(df, f"{p}_QC"), column(df, f"{p}_ADJUSTED_QC")
    m_adj = adj.notna() & adjqc.isin(GOOD)
    m_raw = raw.notna() & qc.isin(GOOD) & ~m_adj
    val = pd.Series(np.nan, index=df.index)
    val[m_adj] = adj[m_adj]
    val[m_raw] = raw[m_raw]
    label = " + ".join(n for n, m in (("adjusted", m_adj), ("raw", m_raw)) if m.any())
    label = f"{label} (QC 1/2)" if label else ""
    if val.notna().sum() < MIN_POINTS and p in BGC and not strict:
        m_prov = raw.notna() & (qc == 3)
        if m_prov.sum() >= MIN_POINTS:
            val = raw.where(m_prov)
            label = "PROVISIONAL: raw, uncalibrated (QC 3)"
    sel = pd.DataFrame({"z": depth, "v": val}).dropna()
    if len(sel) < MIN_POINTS:
        return None
    return sel, label, int(raw.notna().sum())


def grid(sel, smooth=1):
    """Median per depth, linearly interpolated onto a 1 dbar grid."""
    s = sel.groupby("z")["v"].median().sort_index()
    if len(s) < 3:
        return None
    z = np.arange(np.ceil(s.index.min()), np.floor(s.index.max()) + 1.0)
    v = np.interp(z, s.index.values, s.values)
    if smooth > 1:
        v = pd.Series(v).rolling(smooth, center=True, min_periods=1).median().values
    return z, v


def surface(sel, top=10.0):
    s = sel.loc[sel["z"] <= top, "v"]
    return float(s.median()) if len(s) else None


def at_depth(z, v, d):
    return float(np.interp(d, z, v))


def f(x, nd=2):
    return "n/a" if x is None or pd.isna(x) else f"{x:.{nd}f}"


def in_med(lon, lat):
    return -5.35 <= lon <= 36.5 and 30 <= lat <= 46 and not (lon < -1 and lat > 38) \
        and not (lon > 27.5 and lat > 41.1)


def interpret(df, strict, src):
    if df.empty:
        sys.exit("The CSV has no rows (a --clean download of a fresh profile can be empty). "
                 "Re-run argo_lookup.py without --clean.")
    depth = column(df, "PRES_ADJUSTED").fillna(column(df, "PRES"))
    lat, lon = float(df["LATITUDE"].median()), float(df["LONGITUDE"].median())
    wmo = int(df["PLATFORM_NUMBER"].iloc[0]) if "PLATFORM_NUMBER" in df else "?"
    cyc = int(df["CYCLE_NUMBER"].iloc[0]) if "CYCLE_NUMBER" in df else "?"
    when = pd.to_datetime(df["TIME"]).iloc[0] if "TIME" in df else None
    direction = {"A": "ascending", "D": "descending"}.get(str(df.get("DIRECTION", pd.Series(["?"])).iloc[0]), "")

    sels = {p: select(df, depth, p, strict) for p in ORDER}
    say(f"=== Argo float {wmo}, cycle {cyc} ===")
    say(f"{when:%Y-%m-%d %H:%M} UTC, {direction} profile, {lat:.3f}N {lon:.3f}E, "
        f"{len(df)} levels, {f(depth.min(), 1)} to {f(depth.max(), 1)} dbar")
    say(f"Source: {os.path.basename(src)}\n")

    say("DATA USED (and how good it is)")
    for p in ORDER:
        if p in df and df[p].notna().any():
            s = sels[p]
            say(f"  {p:<20} {int(df[p].notna().sum()):>5} values | "
                + (f"{len(s[0]):>5} used | {s[1]}" if s else "none usable (no QC 1/2 points)"))
    say("")

    findings, caveats = [], []
    mld = None
    say("PHYSICAL STRUCTURE")
    t = sels["TEMP"]
    s_ = sels["PSAL"]
    if t:
        z, v = grid(t[0], smooth=5)
        top = surface(t[0])
        ref = at_depth(z, v, 10) if z[0] <= 10 else v[0]
        hit = np.where((z > 10) & (v <= ref - 0.2))[0]
        mld = float(z[hit[0]]) if len(hit) else None
        say(f"  Surface (top 10 dbar): {f(top)} C" + (f", salinity {f(surface(s_[0]))}" if s_ else ""))
        if mld is not None:
            say(f"  Mixed layer depth: about {mld:.0f} dbar (temperature falls 0.2 C below its 10 dbar value)")
            kind = ("shallow: the surface is strongly stratified and cut off from the water below" if mld < 30 else
                    "moderate: surface cooling and wind mixing are working on the upper water" if mld < 100 else
                    "deep: the upper ocean is well mixed, convective or storm mixing is under way")
            say(f"  -> Reading: this mixed layer is {kind}.")
        else:
            say(f"  Mixed layer: deeper than {z.max():.0f} dbar, the whole profile is nearly uniform in temperature.")
        sel_z = (z >= 10) & (z <= 300)
        if sel_z.sum() > 10:
            gr = np.gradient(v, z)
            i = np.argmax(np.abs(gr) * sel_z)
            say(f"  Steepest thermocline: {abs(gr[i]) * 10:.2f} C per 10 dbar at about {z[i]:.0f} dbar")
        say(f"  Deepest good reading ({z.max():.0f} dbar): {f(v[-1])} C"
            + (f", salinity {f(grid(s_[0])[1][-1])}" if s_ else ""))
        say(f"  Temperature range in the profile: {f(t[0]['v'].min())} to {f(t[0]['v'].max())} C")
    if s_:
        z, v = grid(s_[0], smooth=5)
        m = z >= 50
        if m.sum() > 20:
            i = np.argmax(np.where(m, v, -np.inf))
            above, below = v[m][0], v[-1]
            if z[i] < z.max() - 20 and v[i] - above >= 0.02 and v[i] - below >= 0.02:
                say(f"  Subsurface salinity maximum: {v[i]:.2f} at about {z[i]:.0f} dbar")
                if in_med(lon, lat):
                    say("  -> Reading: in the Mediterranean a salty, warm intermediate layer like this is usually "
                        "Levantine Intermediate Water, formed in the eastern basin and spread westward.")
            else:
                say(f"  Salinity: {f(v.min())} to {f(v.max())}, no clear subsurface maximum")
    if not t and not s_:
        say("  No usable temperature or salinity points.")
    say("")

    say("BIOGEOCHEMISTRY")
    chl = sels["CHLA"]
    if chl:
        z, v = grid(chl[0], smooth=5)
        top = surface(chl[0])
        i = int(np.argmax(v))
        ratio = v[i] / top if top and top > 0 else np.inf
        if z[i] > 10 and v[i] >= 1.5 * (top or 0) and v[i] > 0.1:
            say(f"  Chlorophyll: peak {v[i]:.2f} mg/m3 at about {z[i]:.0f} dbar, "
                f"{'' if np.isinf(ratio) else f'{ratio:.1f}x '}the surface value ({f(top)}).")
            say("  -> Reading: a deep chlorophyll maximum, plankton living below the surface "
                "where light and nutrients meet.")
            findings.append(("dcm", float(z[i])))
        else:
            say(f"  Chlorophyll: surface {f(top)}, maximum {v[i]:.2f} mg/m3 at {z[i]:.0f} dbar, "
                "no pronounced subsurface maximum.")
        bb = sels["BBP700"]
        if bb:
            zb, vb = grid(bb[0], smooth=5)
            j = int(np.argmax(vb))
            say(f"  Particle backscatter (BBP700): surface {f(surface(bb[0]), 5)}, "
                f"maximum {vb[j]:.5f} 1/m at about {zb[j]:.0f} dbar")
    no3 = sels["NITRATE"]
    if no3:
        z, v = grid(no3[0], smooth=3)
        top = surface(no3[0])
        deep = float(np.median(no3[0].sort_values("z")["v"].tail(5)))
        say(f"  Nitrate: surface {f(top)}, deepest values about {f(deep)} umol/kg ({len(no3[0])} levels)")
        up = np.where(v >= 1.0)[0]
        if len(up) and z[up[0]] > 5:
            say(f"  Nitracline (nitrate reaches 1 umol/kg): about {z[up[0]]:.0f} dbar")
        if top is not None and top < 0.5:
            say("  -> Reading: the surface is nutrient-depleted, so growth depends on nutrients "
                "supplied from below.")
    ox = sels["DOXY"]
    if ox:
        o = ox[0].sort_values("z")
        say(f"  Oxygen: surface {f(surface(o))}, minimum {o['v'].min():.0f} at about "
            f"{o.loc[o['v'].idxmin(), 'z']:.0f} dbar, deepest {o['v'].iloc[-1]:.0f} umol/kg "
            f"({len(o)} points, so coarse)")
    ph = sels["PH_IN_SITU_TOTAL"]
    if ph:
        p_ = ph[0].sort_values("z")
        say(f"  pH (total scale): surface {f(surface(p_), 3)}, minimum {p_['v'].min():.3f} at about "
            f"{p_.loc[p_['v'].idxmin(), 'z']:.0f} dbar")
    if not (chl or no3 or ox or ph):
        say("  No biogeochemical sensors in this profile (core float).")
    say("")

    say("LIGHT")
    par = sels["DOWNWELLING_PAR"]
    if par:
        top = surface(par[0])
        if top is not None and top < 5:
            say(f"  Surface PAR is {f(top, 3)} umol quanta/m2/s: the profile was taken in darkness, "
                "so the light sensors only show noise. Ignore them for this cycle.")
        else:
            z, v = grid(par[0], smooth=3)
            hit = np.where(v <= 0.01 * (top or v[0]))[0]
            say(f"  Surface PAR {f(top, 0)} umol quanta/m2/s"
                + (f"; 1% light depth (base of the sunlit zone) about {z[hit[0]]:.0f} dbar" if len(hit) else ""))
    else:
        say("  No usable light data.")
    say("")

    say("CAVEATS")
    prov = [p for p in ORDER if sels[p] and sels[p][1].startswith("PROVISIONAL")]
    if prov:
        say(f"  - PROVISIONAL (uncalibrated, QC 3): {', '.join(prov)}. Treat as indicative only.")
    say("  - Real-time data have only automatic quality checks; delayed-mode calibration can take months.")
    say("  - Depths are pressure in dbar and good to a few metres (adjusted and raw pressure differ by up to ~5 dbar).")
    say("  - Chlorophyll comes from fluorescence and is uncertain by roughly a factor of two.")
    say("  - One profile is a snapshot. Eddies, fronts and the time of day all change what you see.")
    return sels, mld, findings, depth


def plot(sels, mld, findings, depth, png, title):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        say("\n(--plot needs matplotlib: pip install matplotlib)")
        return
    panels = [[("TEMP", "Temperature (C)", "tab:red"), ("PSAL", "Salinity", "tab:blue")],
              [("DOXY", "Oxygen (umol/kg)", "tab:green"), ("PH_IN_SITU_TOTAL", "pH", "tab:purple")],
              [("CHLA", "Chlorophyll (mg/m3)", "tab:olive"), ("BBP700", "Backscatter 700 nm (1/m)", "tab:gray")],
              [("NITRATE", "Nitrate (umol/kg)", "tab:orange")]]
    fig, axes = plt.subplots(1, 4, figsize=(15, 6), sharey=True)
    for ax, panel in zip(axes, panels):
        for k, (p, lab, colour) in enumerate(panel):
            s = sels.get(p)
            if not s:
                continue
            a = ax if k == 0 else ax.twiny()
            d = s[0].sort_values("z")
            prov = s[1].startswith("PROVISIONAL")
            a.plot(d["v"], d["z"], ls=":" if prov else "-", marker=".", ms=3, color=colour)
            a.set_xlabel(lab + (" PROVISIONAL" if prov else ""), color=colour, fontsize=9)
            if k == 1:
                a.xaxis.set_label_position("top")
                a.xaxis.tick_top()
            else:
                a.xaxis.set_label_position("bottom")
        if mld:
            ax.axhline(mld, color="k", lw=0.8, ls="--")
        for kind, z in findings:
            ax.axhline(z, color="tab:green", lw=0.8, ls="-.")
        ax.grid(alpha=0.3)
    top = float(depth.max())
    axes[0].set_ylim(top, 0)
    axes[0].set_ylabel("Pressure (dbar, about metres)")
    fig.suptitle(title + ("   (dashed: mixed layer depth, dash-dot: chlorophyll maximum)"
                          if mld or findings else ""), fontsize=10)
    fig.tight_layout()
    fig.savefig(png, dpi=130)
    say(f"\nSaved plot {png}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    src = find_csv(args[0])
    frame = pd.read_csv(src)
    sels, mld, findings, depth = interpret(frame, "--strict" in sys.argv, src)
    stem = os.path.splitext(src)[0]
    if "--plot" in sys.argv:
        plot(sels, mld, findings, depth, f"{stem}_interpretation.png", os.path.basename(stem))
    with open(f"{stem}_interpretation.txt", "w") as fh:
        fh.write("\n".join(LINES) + "\n")
    print(f"\nSaved {stem}_interpretation.txt")