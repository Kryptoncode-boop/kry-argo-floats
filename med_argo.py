"""
med_argo.py - every Argo float that has reported inside the Mediterranean,
with its last known position (anywhere), status and sensor type.

Usage:
    pip install argopy
    python med_argo.py            # all floats
    python med_argo.py --active   # only floats still in the Med and reporting

Notes:
  * The first run downloads the global Argo profile index (a few hundred MB
    uncompressed). argopy caches it, so later runs are much faster.
  * Set the environment variable ARGO_HOST to use a different GDAC / local mirror.
"""
import os
import sys

import numpy as np
import pandas as pd
from argopy import ArgoIndex
from argopy.errors import DataNotFound

HOST = os.environ.get("ARGO_HOST")  # None = argopy's default GDAC
ACTIVE_DAYS = 30    # reported within this many days -> "reporting"
SILENT_DAYS = 180   # silent longer than this -> "inactive"
CORE = {"PRES", "TEMP", "PSAL"}


def in_med(lon, lat):
    """Rough Mediterranean mask: western edge at Gibraltar (-5.35 E), minus
    the Bay of Biscay, Black Sea/Azov and Sea of Marmara that the bounding box catches.
    It is a hand-drawn approximation, not an official sea boundary."""
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    box = (lon >= -5.35) & (lon <= 36.5) & (lat >= 30.0) & (lat <= 46.0)
    biscay = (lon < -1.0) & (lat > 38.0)
    black_sea = (lon > 27.5) & (lat > 41.1)
    marmara = (lon > 26.9) & (lon < 30.0) & (lat > 40.3) & (lat <= 41.1)
    return box & ~biscay & ~black_sea & ~marmara


def query(index_file, wmos=None, box=None):
    """Search one Argo index. Returns an empty DataFrame if nothing matches."""
    idx = ArgoIndex(index_file=index_file, host=HOST)
    try:
        if box is not None:
            idx.query.box(box)
        else:
            idx.query.wmo(wmos)
        # completed=False skips slow reference-table lookups; wmo and cyc are still added
        return idx.to_dataframe(completed=False)
    except DataNotFound:
        return pd.DataFrame()


def main():
    now = pd.Timestamp.now("UTC").tz_localize(None)  # index dates are naive UTC
    box = [-5.35, 36.5, 30, 46, "2000-01-01", now.strftime("%Y-%m-%d")]

    # 1. Profiles inside the bounding box, then trim to the Mediterranean proper
    med = query("core", box=box)
    med = med[in_med(med["longitude"], med["latitude"])]
    if med.empty:
        sys.exit("No Mediterranean profiles found.")
    wmos = sorted(int(w) for w in med["wmo"].unique())
    in_med_counts = med.groupby("wmo").size().rename("profiles_in_med")

    # 2. Each float's last profile ANYWHERE, so floats that left the Med aren't misreported.
    #    Last report (any profile) and last GPS fix (a profile with a position) can differ.
    allp = query("core", wmos=wmos).dropna(subset=["date"]).sort_values(["wmo", "date", "cyc"])
    reported = allp.groupby("wmo")["date"].max().rename("last_report")
    fixes = allp.dropna(subset=["latitude", "longitude"])
    last = (fixes.groupby("wmo").tail(1).set_index("wmo")
                 [["date", "cyc", "latitude", "longitude", "file"]]
                 .rename(columns={"date": "last_fix"}))
    last["dac"] = last["file"].str.split("/").str[0]
    last = last.drop(columns="file").join(reported).join(in_med_counts)
    last["still_in_med"] = in_med(last["longitude"], last["latitude"])
    last["days_since"] = (now - last["last_report"]).dt.days
    last["status"] = np.where(last["days_since"] <= ACTIVE_DAYS, "reporting",
                      np.where(last["days_since"] <= SILENT_DAYS, "silent", "inactive"))

    # 3. Sensors: only floats with BGC sensors appear in the synthetic-profile index
    bgc = query("bgc-s", wmos=wmos)
    extras = {}
    if not bgc.empty:
        for wmo, g in bgc.groupby("wmo"):
            params = {p for s in g["parameters"].dropna() for p in s.split()}
            extras[wmo] = " ".join(sorted(params - CORE))
    last["data_type"] = [("Core + BGC: " + extras[w]) if w in extras else "Core (PRES, TEMP, PSAL)"
                         for w in last.index]

    if "--active" in sys.argv:
        last = last[last["still_in_med"] & (last["status"] == "reporting")]

    last = last.reset_index().sort_values("last_report", ascending=False)
    cols = ["wmo", "last_report", "last_fix", "latitude", "longitude", "still_in_med",
            "status", "profiles_in_med", "data_type"]

    pd.set_option("display.width", 250, "display.max_colwidth", 70)
    print(f"{len(wmos)} floats have reported in the Mediterranean "
          f"({int(last['still_in_med'].sum())} of those listed have a last fix still inside it)\n")
    print(last[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    out = "med_floats_last_known.csv"
    last[cols + ["cyc", "dac"]].to_csv(out, index=False)
    print(f"\nSaved {out}")
    print("last_fix = last profile with a GPS position; lat/lon are from that fix.")
    print("Status is a heuristic from last_report "
          f"(reporting <= {ACTIVE_DAYS} d, inactive > {SILENT_DAYS} d), not an official OceanOPS status.")


if __name__ == "__main__":
    main()
