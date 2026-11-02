"""
Python translation of the R post-processing pipeline, adapted for SSP Mexico.

Mirrors:
  - ssp_modeling/output_postprocessing/scr/run_script_baseline_run_new.r
  - ssp_modeling/output_postprocessing/scr/intertemporal_decomposition.r

The rescale() algorithm is country-agnostic — country selection is driven by
`iso_code3`, `region`, and `year_ref`.  The only Mexico-specific behaviour lives
in preprocess_ssp_output(): Mexico applies a handful of fixed value patches
(`fixed_patches`) before rescaling and does NOT use the generic zero->0.01
patch that the Morocco port added.

Usage
-----
from ssp_modeling.output_postprocessing.intertemporal_decomposition import run_postprocessing

df_decomposed = run_postprocessing(
    df_ssp_output         = df_out_wide,
    targets_path          = "ssp_modeling/output_postprocessing/data/inventory_2026/emission_targets_MEX_2023_ni.csv",
    iso_code3             = "MEX",
    year_ref              = 2023,
    region                = "mexico",
    initial_conditions_id = "_0",
    fixed_patches         = {
        "emission_co2e_nf3_ippu_production_chemicals": 0.001,
        "emission_co2e_nf3_ippu_production_electronics": 0.001,
        "nemomod_entc_discounted_operating_costs_pp_waste_incineration": 0.001,
    },
    output_path           = None,
)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _fill_na_with_mean(series: pd.Series) -> pd.Series:
    """Replace single NaN values with the column mean; all-NaN -> 0."""
    mean_val = series.mean()
    if pd.isna(mean_val):
        return series.fillna(0.0)
    return series.fillna(mean_val)


def _pct_diff_and_diff(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Replicate R logic for pct_diff and diff columns.

    R code:
        diff  <- c(diff(values), 0)                      # forward diff, last = 0
        pct_diff[0]  <- 0
        pct_diff[t]  <- diff[t-1] / values[t-1]          # = (v[t]-v[t-1]) / v[t-1]

    Returns (pct_diff, abs_diff) as Series aligned with the input index.
    """
    arr = values.to_numpy(dtype=float)
    n = len(arr)

    abs_diff = np.zeros(n)
    abs_diff[1:] = np.diff(arr)

    pct_diff = np.zeros(n)
    if not np.all(arr == 0) and not np.isnan(arr).all():
        with np.errstate(divide="ignore", invalid="ignore"):
            pct_diff[1:] = np.where(arr[:-1] == 0, 0.0, np.diff(arr) / arr[:-1])
        pct_diff = np.where(~np.isfinite(pct_diff), 0.0, pct_diff)

    return (
        pd.Series(pct_diff, index=values.index),
        pd.Series(abs_diff, index=values.index),
    )


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def prepare_targets(
    targets_path: str | Path,
    iso_code3: str,
) -> pd.DataFrame:
    """
    Read emission_targets CSV and return a clean DataFrame.

    Keeps columns: subsector_ssp, gas, vars, ID, tvalue
    (tvalue is the country-specific target column, e.g. 'MEX').

    The Mexico targets file (emission_targets_MEX_2023_ni.csv) carries extra
    columns (mex_sector, mex_subsector, aggregation_category, ids) that are
    dropped here — only the columns the rescaler needs are kept.
    """
    te_all = pd.read_csv(targets_path)

    cols_keep = ["subsector_ssp", "gas", "vars", "ID", iso_code3]
    te_all = te_all[cols_keep].copy()
    te_all = te_all.rename(columns={iso_code3: "tvalue"})
    return te_all.reset_index(drop=True)


def preprocess_ssp_output(
    data_all: pd.DataFrame,
    te_all: pd.DataFrame,
    time_period_ref: int,
    initial_conditions_id: str = "_0",
    fixed_patches: Optional[dict] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Mirror the pre-processing in run_script_baseline_run_new.r (Mexico):

    1. Filter data to time_period >= time_period_ref.
    2. Apply Mexico's fixed value patches (whole-column assignments) so a few
       vars are non-zero / well-defined at baseline, exactly as the R script's
       `data_all$<var> <- 0.001` lines do.
    3. Compute factor_correction for rows in te_all where baseline = 0
       but target > 0, and adjust tvalue accordingly.

    Note: unlike the Morocco port, Mexico does NOT apply a generic zero->0.01
    patch to the target vars — only the explicit `fixed_patches` below.

    Returns (data_all_filtered, te_all_adjusted).
    """
    data_all = data_all[data_all["time_period"] >= time_period_ref].copy()

    # 2. Mexico fixed patches — set the whole column (creates it if absent),
    #    matching `data_all$<var> <- <value>` in run_script_baseline_run_new.r.
    if fixed_patches:
        for col, val in fixed_patches.items():
            data_all[col] = float(val)

    baseline_pid = initial_conditions_id.lstrip("_")

    te_all = te_all.copy()
    te_all["simulation"] = 0.0

    baseline_mask = (
        (data_all["primary_id"] == baseline_pid)
        & (data_all["time_period"] == time_period_ref)
    )
    baseline_row = data_all[baseline_mask]

    for i, row in te_all.iterrows():
        vars_i = [v.strip() for v in row["vars"].split(":")]
        vars_present = [v for v in vars_i if v in baseline_row.columns]
        if vars_present:
            sim_val = float(baseline_row[vars_present].sum(axis=1).sum())
        else:
            sim_val = 0.0
        te_all.at[i, "simulation"] = sim_val
        print(f"Sector: {row['ID']}")

    te_all["simulation"] = np.where(
        (te_all["simulation"] == 0) & (te_all["tvalue"] > 0), 0.0, 1.0
    )

    correct = (
        te_all.groupby("ID")["simulation"]
        .mean()
        .rename("factor_correction")
        .reset_index()
    )
    te_all = te_all.merge(correct, on="ID")

    te_all["tvalue"] = np.where(
        te_all["factor_correction"] == 0,
        te_all["tvalue"],
        te_all["tvalue"] / te_all["factor_correction"],
    )
    te_all = te_all.drop(columns=["simulation", "factor_correction", "ID"])

    return data_all.reset_index(drop=True), te_all.reset_index(drop=True)


def rescale(
    data_all: pd.DataFrame,
    te_all: pd.DataFrame,
    region: str,
    initial_conditions_id: str,
    time_period_ref: int,
    output_path: Optional[str | Path] = None,
) -> pd.DataFrame:
    """
    Python translation of the R `rescale()` function in intertemporal_decomposition.r.

    Parameters
    ----------
    data_all              : SSP wide output filtered to time_period >= time_period_ref
    te_all                : emission targets DataFrame (from prepare_targets / preprocess_ssp_output)
    region                : region label, e.g. "mexico"
    initial_conditions_id : primary_id suffix of the baseline, e.g. "_0"
    time_period_ref       : first time period to consider (year_ref - 2015)
    output_path           : optional CSV path to write the decomposed output

    Returns
    -------
    DataFrame with rescaled emission columns and subsector totals appended.
    """
    data = data_all[data_all["region"] == region].copy().reset_index(drop=True)

    tv1_all = [
        c for c in data.columns
        if "co2e_" in c and "emission_co2e_subsector_total_" not in c
    ]

    data["Index"] = data["region"].astype(str) + "_" + data["primary_id"].astype(str)
    inds = data["Index"].unique().tolist()
    ref_ind = f"{region}{initial_conditions_id}"

    print(f"Computing percent differences for {len(inds)} scenarios × {len(tv1_all)} vars …")
    pct_diff_frames = []

    for ind in inds:
        sub = data[data["Index"] == ind].sort_values("time_period").copy()
        row_data = {"Index": sub["Index"].values, "time_period": sub["time_period"].values}

        for var in tv1_all:
            series = sub[var].copy()
            series = _fill_na_with_mean(series)

            pct_d, abs_d = _pct_diff_and_diff(series)
            row_data[f"pct_diff_{var}"] = pct_d.values
            row_data[f"diff_{var}"] = abs_d.values

        pct_diff_frames.append(pd.DataFrame(row_data))

    pct_diffs = pd.concat(pct_diff_frames, ignore_index=True)
    pct_diffs = pct_diffs.sort_values(["Index", "time_period"]).reset_index(drop=True)

    te_work = te_all.copy().reset_index()
    te_work["sector_gas"] = (
        te_work["index"].astype(str) + "-"
        + te_work["subsector_ssp"] + "-"
        + te_work["gas"]
    )
    sector_gas_all = te_work["sector_gas"].unique().tolist()

    print(f"Applying deviation factors for {len(sector_gas_all)} sector-gas combinations …")

    for sg in sector_gas_all:
        row_sg = te_work[te_work["sector_gas"] == sg].iloc[0]
        tv1 = [v.strip() for v in row_sg["vars"].split(":")]
        tv1 = [v for v in tv1 if v in data.columns]

        target_total = float(row_sg["tvalue"])

        ref_mask = (data["time_period"] == time_period_ref) & (data["Index"] == ref_ind)
        uncalibrated_total = float(data.loc[ref_mask, tv1].sum(axis=1).sum()) if tv1 else 0.0

        deviation_factor = (
            1.0 if uncalibrated_total == 0
            else target_total / uncalibrated_total
        )

        ref_tp_mask = data["time_period"] == time_period_ref
        for v in tv1:
            data.loc[ref_tp_mask, v] = data.loc[ref_tp_mask, v] * deviation_factor

        for ind in inds:
            ind_mask_pd = pct_diffs["Index"] == ind
            init_ind_mask = (data["Index"] == ref_ind) & (data["time_period"] == time_period_ref)

            for v in tv1:
                init_value = float(data.loc[init_ind_mask, v].values[0]) if init_ind_mask.sum() > 0 else 0.0
                pd_col_diff = f"diff_{v}"
                pd_col_pct = f"pct_diff_{v}"

                ind_data_mask = data["Index"] == ind

                if init_value == 0:
                    diffs = pct_diffs.loc[ind_mask_pd, pd_col_diff].values
                    new_vals = init_value + np.cumsum(diffs) * deviation_factor
                    data.loc[ind_data_mask, v] = new_vals
                else:
                    pcts = pct_diffs.loc[ind_mask_pd, pd_col_pct].values
                    time_change = np.cumprod(1.0 + pcts)
                    data.loc[ind_data_mask, v] = init_value * time_change

    subsectors = te_all["subsector_ssp"].unique().tolist()
    for subsector in subsectors:
        sub_vars_raw = (
            te_all[te_all["subsector_ssp"] == subsector]["vars"]
            .str.split(":")
            .explode()
            .str.strip()
            .dropna()
        )
        sub_vars = [v for v in sub_vars_raw if v != "" and v in data.columns]
        col_name = f"emission_co2e_subsector_total_{subsector}"
        if sub_vars:
            data[col_name] = data[sub_vars].sum(axis=1)
        else:
            data[col_name] = 0.0

    data = data.drop(columns=["Index"])

    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(out, index=False)
        print(f"Decomposed output written to: {out}")

    print(f"Done: {region}")
    return data.reset_index(drop=True)


def run_postprocessing(
    df_ssp_output: pd.DataFrame,
    targets_path: str | Path,
    iso_code3: str,
    year_ref: int,
    region: str,
    initial_conditions_id: str = "_0",
    fixed_patches: Optional[dict] = None,
    output_path: Optional[str | Path] = None,
) -> pd.DataFrame:
    """
    Full pipeline: targets → preprocess → rescale.

    Parameters
    ----------
    df_ssp_output         : wide SSP output DataFrame (all time periods, all scenarios)
    targets_path          : path to emission_targets_<ISO>_<year>_ni.csv
    iso_code3             : ISO 3-letter code for target column, e.g. "MEX"
    year_ref              : calibration year, e.g. 2023
    region                : region name used in the data, e.g. "mexico"
    initial_conditions_id : primary_id suffix of the baseline scenario (default "_0")
    fixed_patches         : {column: value} whole-column patches applied before
                            rescaling (Mexico sets a few vars to 0.001)
    output_path           : optional CSV path to write the result

    Returns
    -------
    DataFrame with rescaled emissions and updated subsector totals.
    """
    time_period_ref = year_ref - 2015

    te_all = prepare_targets(targets_path, iso_code3)

    data_all, te_all = preprocess_ssp_output(
        df_ssp_output,
        te_all,
        time_period_ref,
        initial_conditions_id=initial_conditions_id,
        fixed_patches=fixed_patches,
    )

    result = rescale(
        data_all=data_all,
        te_all=te_all,
        region=region,
        initial_conditions_id=initial_conditions_id,
        time_period_ref=time_period_ref,
        output_path=output_path,
    )

    return result
