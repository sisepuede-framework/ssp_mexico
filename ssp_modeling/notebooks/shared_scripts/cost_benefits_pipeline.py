"""
cost_benefits_pipeline.py
--------------------------
Full cost-benefit pipeline for MEXICO SSP runs.

Consolidates, in a single function, what Mexico currently does in two steps:
  - ssp_modeling/cost-benefits/cba_mex.py   (raw CostBenefits -> cba_results.csv)
  - ssp_modeling/cost-benefits/scr/reshaping_cbData.r  (-> tableau/data/cb_data.csv)

Wraps costs_benefits_ssp.cb_calculate.CostBenefits and the Tableau-reshaping
logic, so the manager notebook can call a single function.

Mexico-specific defaults vs. the Morocco version
------------------------------------------------
  * apply_shift defaults to False (cba_mex.py disables cb_shift_costs).
  * strategy_id is derived from ATTRIBUTE_STRATEGY (generic) instead of the
    hard-coded PFLO:3->6004 / PFLO:5->6005 mapping in reshaping_cbData.r.
  * strategy_label_map lets the notebook apply human-readable labels
    (e.g. {"PFLO:3": "Pathway 2", "PFLO:5": "Pathway 3"}).
"""

import pandas as pd
from pathlib import Path
from typing import Optional

from costs_benefits_ssp.cb_calculate import CostBenefits


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


def _build_strategy_maps(
    att_primary: pd.DataFrame,
    att_strategy: pd.DataFrame,
) -> tuple:
    """
    Build (strategy_id_map, primary_id_map) dicts keyed by strategy_code.

    strategy_id_map  : strategy_code -> strategy_id  (from att_strategy)
    primary_id_map   : strategy_code -> primary_id   (from att_primary join)
    """
    sid_map = dict(zip(att_strategy["strategy_code"], att_strategy["strategy_id"]))

    # Invert: strategy_id -> primary_id
    sid_to_pid = dict(zip(att_primary["strategy_id"], att_primary["primary_id"]))

    pid_map = {code: sid_to_pid.get(sid) for code, sid in sid_map.items()}
    return sid_map, pid_map


def _reshape_for_tableau(
    results: pd.DataFrame,
    ssp_data: pd.DataFrame,
    strategy_id_map: dict,
    strategy_id_override: Optional[dict] = None,
    strategy_label_map: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Reshape cost-benefit results to Tableau-ready format
    (port of reshaping_cbData.r).

    Steps
    -----
    1.  Split variable string into (name, sector, cb_type, item_1, item_2).
    2.  Scale USD -> billions USD.
    3.  Drop shifted rows.
    4.  Add Year, strategy label, strategy_id, ids, gdp_mmm_usd.

    strategy_id is taken from `strategy_id_override` (codes not present keep
    their strategy_code, matching reshaping_cbData.r); if no override is given,
    the generic ATTRIBUTE_STRATEGY map is used.  GDP is merged on time_period
    only and no primary_id column is emitted, to match the legacy cb_data.csv.
    """
    cb = results.copy()

    # 1. Decompose variable
    parts = cb["variable"].astype(str).str.split(":", n=4, expand=True)
    parts.columns = ["name", "sector", "cb_type", "item_1", "item_2"]
    cb = pd.concat([cb, parts], axis=1)

    # 2. USD -> billions
    cb["value"] = cb["value"] / 1e9

    # 3. Remove shifted entries
    cb = cb[~cb["item_2"].astype(str).str.contains("shifted", na=False)]
    cb = cb[~cb["variable"].astype(str).str.contains("shifted2", na=False)]

    # 4. Year
    cb["Year"] = cb["time_period"] + 2015

    # 5. strategy_id — override wins; codes not present keep their strategy_code
    #    (use .get so mapped ids stay int, matching the legacy "6004" not "6004.0")
    if strategy_id_override:
        cb["strategy_id"] = cb["strategy_code"].map(lambda c: strategy_id_override.get(c, c))
    else:
        cb["strategy_id"] = cb["strategy_code"].map(strategy_id_map)

    # Human-readable label
    cb["strategy"] = cb["strategy_code"]
    if strategy_label_map:
        cb["strategy"] = cb["strategy"].replace(strategy_label_map)

    # 6. Unique identifier
    cb["ids"] = cb["variable"].astype(str) + ":" + cb["strategy_id"].astype(str)

    # 7. Merge GDP (on time_period only, matching reshaping_cbData.r)
    gdp = ssp_data[["time_period", "gdp_mmm_usd"]].drop_duplicates("time_period")
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
    strategy_code_base: str = "BASE",
    apply_shift: bool = False,
    strategy_id_override: Optional[dict] = None,
    strategy_label_map: Optional[dict] = None,
    output_path: Optional[Path] = None,
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
    strategy_code_base : strategy_code that acts as the BAU/BASE reference
    apply_shift        : if True, redistribute pre-2025 costs (cb_shift_costs).
                         Default False to match Mexico's cba_mex.py behaviour.
    strategy_id_override : optional {strategy_code: strategy_id}; codes not in it
                         keep their strategy_code (matches reshaping_cbData.r).
                         If None, the generic ATTRIBUTE_STRATEGY map is used.
    strategy_label_map : optional {strategy_code: label} for the "strategy" column
    output_path        : if given, writes the result CSV to this path

    Returns
    -------
    pd.DataFrame  Tableau-ready cost-benefit results
    """
    cb_config_path = Path(cb_config_path)

    # Resolve base strategy (fall back to BASE if specified code is absent)
    base_code = _resolve_base_code(strategy_code_base, att_strategy)

    # Build dynamic strategy → id map (generic fallback when no override given)
    strategy_id_map, _ = _build_strategy_maps(att_primary, att_strategy)

    # Instantiate and configure
    cb_obj = CostBenefits(df_decomposed, att_primary, att_strategy, base_code)
    cb_obj.load_cb_parameters(str(cb_config_path))

    # Compute
    results_system = cb_obj.compute_system_cost_for_all_strategies()
    results_tx     = cb_obj.compute_technical_cost_for_all_strategies()
    results_all    = pd.concat([results_system, results_tx], ignore_index=True)

    # Post-process interactions (and optionally shift pre-2025 costs)
    results_pp = cb_obj.cb_process_interactions(results_all)
    results    = cb_obj.cb_shift_costs(results_pp) if apply_shift else results_pp

    # Reshape for Tableau
    cb_data = _reshape_for_tableau(
        results,
        df_decomposed,
        strategy_id_map,
        strategy_id_override=strategy_id_override,
        strategy_label_map=strategy_label_map,
    )

    # Save if requested
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cb_data.to_csv(output_path, index=False)
        print(f"[cb_pipeline] Saved {len(cb_data):,} rows → {output_path}")

    return cb_data
