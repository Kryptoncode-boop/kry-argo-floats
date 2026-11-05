"""
argo_lookup.py - latest profile of one Argo float: what it measures, all the
data from that profile, and the data type of every variable.

Usage:
    pip install argopy
    python argo_lookup.py <number>            # all data the float sent, QC flags included
    python argo_lookup.py <number> --clean    # only points that passed quality control
    python argo_lookup.py <number> --full     # print every variable in the dtype table

Saves argo_<wmo>_cycle<n>.csv. Set ARGO_HOST to use a different GDAC / local mirror.
Needs internet: the index comes from the GDAC and the data from ERDDAP.

Why not --clean by default: argopy's standard mode drops a point unless EVERY sensor
on it has a good QC flag. A fresh real-time BGC profile almost never does, so you
would get 0 rows. The default (expert mode) keeps everything and you check the *_QC columns.
"""
import os
import sys
import numpy as np
import pandas as pd
from argopy import ArgoIndex, DataFetcher
from argopy.errors import DataNotFound

HOST = os.environ.get("ARGO_HOST")  # None = argopy's default GDAC
CORE = ["PRES", "TEMP", "PSAL"]
# Longest first, so "_ADJUSTED_QC" isn't mistaken for "_QC"
SUFFIXES = ["_ADJUSTED_ERROR", "_ADJUSTED_QC", "_ADJUSTED", "_DATA_MODE", "_ERROR", "_QC"]


def read_index(index_file, wmo):
    """All index rows for one float. Empty DataFrame if the float isn't in that index."""
    idx = ArgoIndex(index_file=index_file, host=HOST)
    try:
        idx.query.wmo(wmo)
        return idx.to_dataframe(completed=False)  # includes wmo and cyc columns
    except DataNotFound:
        return pd.DataFrame()


def split_suffix(name):
    for s in SUFFIXES:
        if name.endswith(s):
            return name[: -len(s)], s
    return name, None


def measured_parameters(ds):
    """Parameters present in the data: float variables without a QC/error/adjusted suffix."""
    return sorted(
        v for v in ds.data_vars
        if split_suffix(v)[1] is None and np.issubdtype(ds[v].dtype, np.floating)
    )


def describe(ds):
    """One row per variable: role, dtype, units, description."""
    rows = []
    for v in ds.variables:
        a = ds[v].attrs
        rows.append({
            "variable": v,
            "role": "coord" if v in ds.coords else "data",
            "dtype": str(ds[v].dtype),
            "units": a.get("units", "-"),
            "description": a.get("long_name", "-"),
        })
    return pd.DataFrame(rows)


def suffix_summary(table):
    """Collapse the *_QC / *_ERROR / *_DATA_MODE ... variables into one line per suffix type."""
    rows = []
    for s in SUFFIXES:
        sub = table[table["variable"].map(lambda v: split_suffix(v)[1] == s)]
        if len(sub):
            rows.append({"suffix": s, "dtype": ", ".join(sorted(sub["dtype"].unique())),
                         "variables": len(sub)})
    return pd.DataFrame(rows)


def fmt(x, nd=4):
    return "n/a" if pd.isna(x) else f"{x:.{nd}f}"


def fetch_profile(wmo, cyc, has_bgc, mode):
    """Fetch every parameter of one cycle; fall back to core if BGC data isn't available."""
    if has_bgc:
        try:
            ds = DataFetcher(ds="bgc", params="all", mode=mode).profile(wmo, cyc).to_xarray()
            return ds, "Core + BGC"
        except Exception as err:
            print(f"(BGC fetch failed: {type(err).__name__}: {err}\n falling back to core data)\n")
    return DataFetcher(mode=mode).profile(wmo, cyc).to_xarray(), "Core"


def lookup(wmo, clean=False, full=False):
    core = read_index("core", wmo)
    if core.empty:
        sys.exit(f"Float {wmo} not found in the Argo core index.")
    core = core.dropna(subset=["date"]).sort_values(["date", "cyc"])
    last = core.iloc[-1]
    cyc = int(last["cyc"])

    # Sensors: only BGC floats appear in the synthetic-profile index, and it lists their parameters
    bgc = read_index("bgc-s", wmo)
    has_bgc = not bgc.empty
    if has_bgc:
        listed = sorted({p for s in bgc["parameters"].dropna() for p in s.split()})
    else:
        listed = CORE

    print(f"Float {wmo}  (DAC: {last['file'].split('/')[0]})")
    print(f"Last profile: cycle {cyc}, {last['date']} UTC")
    print(f"Position: {fmt(last['latitude'])}, {fmt(last['longitude'])}  (lat, lon)")
    print(f"Index says it collects: {', '.join(listed)}"
          + ("" if has_bgc else "  [core float; the core index doesn't list parameters, so this is assumed]"))
    print(f"Total profiles on record: {len(core)}\n")

    mode = "standard" if clean else "expert"
    ds, kind = fetch_profile(wmo, cyc, has_bgc, mode)
    df = ds.to_dataframe().reset_index()
    print(f"Fetched as: {kind}, {mode} mode, {len(df)} rows")
    if df.empty:
        print("No rows came back. In standard (--clean) mode that means nothing in this profile passed QC yet; "
              "run without --clean to see the raw data.")
        return
    print(f"Parameters measured in this profile: {', '.join(measured_parameters(ds))}\n")

    table = describe(ds)
    if full:
        print("Variables and data types:")
        print(table.to_string(index=False), "\n")
    else:
        main = table[table["variable"].map(lambda v: split_suffix(v)[1] is None)]
        print("Variables and data types (use --full to list the QC/error/mode variables too):")
        print(main.to_string(index=False), "\n")
        print("Companion variables, one set per parameter:")
        print(suffix_summary(table).to_string(index=False), "\n")

    out = f"argo_{wmo}_cycle{cyc}.csv"
    df.to_csv(out, index=False)
    show = [c for c in df.columns if split_suffix(c)[1] is None or c in CORE]
    print(f"Data from the last profile ({len(df)} rows; main columns shown, all {len(df.columns)} saved to CSV):")
    print(df[show].to_string(index=False))
    print(f"\nSaved {out}")
    print("The newest profile is usually real-time data (automatic QC only). QC flags: 1 = good, "
          "2 = probably good, 3/4 = bad, 8 = estimated, 9 = missing.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("Usage: python argo_lookup.py <WMO number> [--clean] [--full]")
    lookup(int(args[0]), clean="--clean" in sys.argv, full="--full" in sys.argv)
