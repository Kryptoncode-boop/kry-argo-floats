# kryptoncode-boop - Argo Float Simple Data Collection and Analysis

This folder contains the Mediterranean Argo float analysis workflow. It is focused on identifying active floats, downloading their latest profiles, and interpreting the oceanographic data they report.

## Simple explanation for non-programmers

This project helps track floating ocean instruments called Argo floats. These floats move through the Mediterranean Sea and collect information about the water, including temperature, salinity, oxygen, and other conditions.

The scripts in this folder do three main things:

1. Find which floats are still active in the Mediterranean.
2. Download the newest measurements from a chosen float.
3. Turn the raw data into a clearer summary of the water conditions.

In plain English, the workflow is:
- look for nearby active floats,
- choose one float to study,
- download its latest data,
- read the summary to understand what the ocean is like at that time.

A few helpful terms:
- Argo float: an ocean-monitoring device that drifts in the sea.
- profile: one set of measurements taken by a float during a pass through the water.
- CSV: a simple spreadsheet-style data file.
- WMO: the float's identification number.
- active: the float is still reporting data.

This is mainly a scientific and data-analysis project, but the workflow is designed to help a person search for float activity, download data, and interpret ocean conditions without manually checking every raw file.

---

## Contents

### SETUP.md
Purpose:
- Describes how to create the Python environment for the project.
- Lists the required packages and the recommended virtual environment workflow.

Use:
- Follow this file first before running any of the analysis scripts.
- It ensures `argopy`, `numpy`, `pandas`, and optionally `matplotlib` are installed.

### files/
This directory contains the main scripts and generated data files used in the workflow.

#### med_argo.py
Purpose:
- Finds Argo floats that have reported inside the Mediterranean Sea.
- Shows each float’s most recent report, last GPS fix, status, and sensor type.
- Produces the summary file `med_floats_last_known.csv`.

Use:
```bash
cd files
python med_argo.py
python med_argo.py --active
```

Usefulness:
- Best for discovering which floats are currently active in the Mediterranean and which ones are still reporting.
- Helpful for selecting a float to inspect in more detail.

#### argo_lookup.py
Purpose:
- Downloads the latest profile data for one specific float.
- Shows the variables measured in the profile and the data quality flags.
- Saves the downloaded profile as a CSV named like `argo_<wmo>_cycle<n>.csv`.

Use:
```bash
cd files
python argo_lookup.py 7901000
python argo_lookup.py 7901000 --clean
python argo_lookup.py 7901000 --full
```

Usefulness:
- Best for analyzing one specific float in detail.
- Useful when you want the raw profile data from a selected cycle.

#### interpret_argo.py
Purpose:
- Reads an Argo profile CSV and converts it into a readable oceanographic interpretation.
- Summarizes temperature, salinity, oxygen, nitrate, chlorophyll, and light structure.
- Can optionally produce a plot.

Use:
```bash
cd files
python interpret_argo.py argo_1902763_cycle34.csv
python interpret_argo.py 1902763
python interpret_argo.py FILE --plot
python interpret_argo.py FILE --strict
```

Usefulness:
- Best for understanding the physical and biological state of a float profile without manually inspecting all raw columns.
- Useful for scientific interpretation and quick reporting.

---

## Generated outputs

### med_floats_last_known.csv
A summary table of floats that have reported in the Mediterranean.

Relevant columns include:
- `wmo`: float identifier
- `last_report`: most recent report date
- `last_fix`: last known GPS position
- `latitude`, `longitude`: last position
- `still_in_med`: whether the last fix remains inside the Mediterranean mask
- `status`: `reporting`, `silent`, or `inactive`
- `profiles_in_med`: how many profiles were recorded in the Mediterranean
- `data_type`: core or biogeochemical sensors carried by the float
- `cyc`: most recent cycle number
- `dac`: data acquisition center

### argo_<wmo>_cycle<n>.csv
The raw or near-raw profile downloaded for a specific float and cycle.

### argo_<wmo>_cycle<n>_interpretation.txt
A plain-text interpretation summarizing the profile in natural language.

---

## Intended workflow

The normal usage flow is:

1. Set up the environment using `SETUP.md`.
2. Run `med_argo.py` to see which floats are active in the Mediterranean.
3. Select a float WMO number of interest.
4. Run `argo_lookup.py <WMO>` to download the most recent profile.
5. Run `interpret_argo.py <CSV>` to read the profile in human-friendly terms.

This makes the folder useful both for broad monitoring and for detailed investigation of a single float.

---

## Practical notes

- The scripts rely on internet access because they fetch Argo index and profile data from GDAC sources.
- `argopy` is the main dependency used by the float workflow.
- `matplotlib` is optional and only needed for plotting in `interpret_argo.py`.
- The scripts are designed for oceanographic research and data exploration rather than as a packaged application.
