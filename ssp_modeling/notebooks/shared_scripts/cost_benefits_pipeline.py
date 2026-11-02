"""
cost_benefits_pipeline.py
--------------------------
Full cost-benefit pipeline for Mexico SSP runs.

Wraps costs_benefits_ssp.cb_calculate.CostBenefits and the Tableau-reshaping
logic that lives in:
  - ssp_modeling/cost-benefits/cba_mex.py            (compute)
  - ssp_modeling/cost-benefits/scr/reshaping_cbData.r (reshape → cb_data.csv)

so the manager notebook can call a single function instead of repeating the
steps inline.

Mexico differences vs the Morocco version:
  * baseline strategy_code is "PFLO:1" (not "PFLO:BAU").
  * costs are NOT shifted (cb_shift_costs is skipped).
  * the Tableau reshape maps the pathway strategies explicitly
    (PFLO:3 → Pathway 2 / id 6004, PFLO:5 → Pathway 3 / id 6005) and merges
    GDP by time_period only.
"""

import pandas as pd
from pathlib import Path
from typing import Optional

from costs_benefits_ssp.cb_calculate import CostBenefits


# Mexico pathway labelling used by reshaping_cbData.r
MEX_STRATEGY_NAME_MAP = {"PFLO:3": "Pathway 2", "PFLO:5": "Pathway 3"}
MEX_STRATEGY_ID_MAP   = {"PFLO:3": 6004, "PFLO:5": 6005}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_base_code(strategy_code_base: str, att_strategy: pd.DataFrame) -> str:
    """Return *strategy_code_base* if it exists in att_strategy, else 'BASE'."""
    if strategy_code_base in att_strategy["strategy_code"].values:
        return strategy_code_base
    fallback = "BASE"
    print(
        f"[cb_pipeline] '{strategy_code_base}' not found in ATTRIBUTE_STRATEGY — "
        f"falling back to '{fallback}'."
    )
    return fallback


def _reshape_for_tableau(
    results: pd.DataFrame,
    ssp_data: pd.DataFrame,
    strategy_name_map: dict,
    strategy_id_map: dict,
) -> pd.DataFrame:
    """
    Reshape cost-benefit results to Tableau-ready format (port of
    reshaping_cbData.r).

    Steps
    -----
    1.  Split variable string into (name, sector, cb_type, item_1, item_2).
    2.  Scale USD → billions USD.
    3.  Drop shifted / shifted2 rows.
    4.  Add Year, pathway strategy label + strategy_id, ids, and GDP.
    """
    cb = results.copy()

    # 1. Decompose variable
    parts = cb["variable"].astype(str).str.split(":", n=4, expand=True)
    parts.columns = ["name", "sector", "cb_type", "item_1", "item_2"]
    cb = pd.concat([cb, parts], axis=1)

    # 2. USD → billions
    cb["value"] = cb["value"] / 1e9

    # 3. Remove shifted entries
    cb = cb[~cb["item_2"].astype(str).str.contains("shifted", na=False)]
    cb = cb[~cb["variable"].astype(str).str.contains("shifted2", na=False)]

    # 4. Year
    cb["Year"] = cb["time_period"] + 2015

    # 5. Pathway label + strategy_id (explicit Mexico mapping)
    cb["strategy"] = cb["strategy_code"].replace(strategy_name_map)
    cb["strategy_id"] = cb["strategy_code"].map(strategy_id_map).fillna(cb["strategy_code"])

    # 6. Unique identifier
    cb["ids"] = cb["variable"].astype(str) + ":" + cb["strategy_id"].astype(str)

    # 7. Merge GDP (one value per time_period, as in reshaping_cbData.r)
    gdp = (
        ssp_data[["time_period", "gdp_mmm_usd"]]
        .drop_duplicates(subset=["time_period"])
    )
    cb = cb.merge(gdp, on="time_period", how="left")

    return cb


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_cost_benefits(
    df_decomposed: pd.DataFrame,
    att_primary: pd.DataFrame,
    att_strategy: pd.DataFrame,
    cb_config_path: Path,
    run_output_dir: Path,
    project_dir: Path,
    strategy_code_base: str = "PFLO:1",
    output_path: Optional[Path] = None,
    strategy_name_map: Optional[dict] = None,
    strategy_id_map: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Run the full cost-benefit pipeline and return a Tableau-ready DataFrame.

    Parameters
    ----------
    df_decomposed      : wide-format decomposed SSP output (from run_decomposition)
    att_primary        : ATTRIBUTE_PRIMARY table as DataFrame
    att_strategy       : ATTRIBUTE_STRATEGY table as DataFrame
    cb_config_path     : path to cb_config_params.xlsx
    run_output_dir     : directory of the current SSP run (for context; not written to here)
    project_dir        : repo root (unused currently; kept for API symmetry)
    strategy_code_base : strategy_code that acts as the BAU/BASE reference (Mexico: PFLO:1)
    output_path        : if given, writes the result CSV to this path
    strategy_name_map  : strategy_code → pathway label (default MEX_STRATEGY_NAME_MAP)
    strategy_id_map    : strategy_code → strategy_id (default MEX_STRATEGY_ID_MAP)

    Returns
    -------
    pd.DataFrame  Tableau-ready cost-benefit results
    """
    cb_config_path = Path(cb_config_path)
    strategy_name_map = MEX_STRATEGY_NAME_MAP if strategy_name_map is None else strategy_name_map
    strategy_id_map   = MEX_STRATEGY_ID_MAP if strategy_id_map is None else strategy_id_map

    # Resolve base strategy (fall back to BASE if specified code is absent)
    base_code = _resolve_base_code(strategy_code_base, att_strategy)

    # Instantiate and configure
    cb_obj = CostBenefits(df_decomposed, att_primary, att_strategy, base_code)
    cb_obj.load_cb_parameters(str(cb_config_path))

    # Compute
    results_system = cb_obj.compute_system_cost_for_all_strategies()
    results_tx     = cb_obj.compute_technical_cost_for_all_strategies()
    results_all    = pd.concat([results_system, results_tx], ignore_index=True)

    # Post-process interactions (Mexico does NOT shift costs)
    results_pp = cb_obj.cb_process_interactions(results_all)

    # Reshape for Tableau
    cb_data = _reshape_for_tableau(
        results_pp,
        df_decomposed,
        strategy_name_map,
        strategy_id_map,
    )

    # Save if requested
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cb_data.to_csv(output_path, index=False)
        print(f"[cb_pipeline] Saved {len(cb_data):,} rows → {output_path}")

    return cb_data
