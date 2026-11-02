"""
postprocessing.py
-----------------
Intertemporal decomposition / rescaling of SSP simulation output for Mexico.

Wraps ssp_modeling.output_postprocessing.intertemporal_decomposition,
which is the Python translation of:
  - ssp_modeling/output_postprocessing/scr/run_script_baseline_run_new.r
  - ssp_modeling/output_postprocessing/scr/intertemporal_decomposition.r
"""

import sys
import pandas as pd
from pathlib import Path
from typing import Optional


# Mexico-specific fixed patches applied before rescaling, matching the
# `data_all$<var> <- 0.001` lines in run_script_baseline_run_new.r.
MEX_FIXED_PATCHES = {
    "emission_co2e_nf3_ippu_production_chemicals": 0.001,
    "emission_co2e_nf3_ippu_production_electronics": 0.001,
    "nemomod_entc_discounted_operating_costs_pp_waste_incineration": 0.001,
}


def run_decomposition(
    df_export: pd.DataFrame,
    project_dir: Path,
    targets_path: Path,
    iso_code3: str,
    year_ref: int,
    region: str,
    output_path: Optional[Path] = None,
    initial_conditions_id: str = "_0",
    fixed_patches: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Rescale *df_export* against Mexico inventory targets and return the
    decomposed DataFrame.  Also writes the result to *output_path* if given.

    Parameters
    ----------
    df_export             : wide-format SSP simulation output (filtered primary_ids)
    project_dir           : repo root — added to sys.path so the module resolves
    targets_path          : path to emission_targets_MEX_<year>_ni.csv
    iso_code3             : 3-letter ISO country code (e.g. "MEX")
    year_ref              : reference / calibration year (e.g. 2023)
    region                : region label used inside the model (e.g. "mexico")
    output_path           : where to write the decomposed CSV (None = skip)
    initial_conditions_id : primary_id suffix of the baseline scenario (default "_0")
    fixed_patches         : whole-column patches applied before rescaling
                            (defaults to MEX_FIXED_PATCHES)
    """
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from ssp_modeling.output_postprocessing.intertemporal_decomposition import (
        run_postprocessing,
    )

    df_decomposed = run_postprocessing(
        df_ssp_output         = df_export,
        targets_path          = targets_path,
        iso_code3             = iso_code3,
        year_ref              = year_ref,
        region                = region,
        initial_conditions_id = initial_conditions_id,
        fixed_patches         = MEX_FIXED_PATCHES if fixed_patches is None else fixed_patches,
        output_path           = output_path,
    )

    return df_decomposed
