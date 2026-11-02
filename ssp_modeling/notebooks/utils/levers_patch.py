"""Fix for building the Tableau levers table over strategies whose transformations
store `magnitude` as a per-category dict (e.g. ENFU:ADJ_EXPORTS, ENFU:ADJ_PRICES).

Problem
-------
`sisepuede.visualization.tables.LeversImplementationTable.build_table_for_strategies`
fails on strategies such as 6004 / 6005 with:

    UFuncTypeError: Cannot cast ufunc 'multiply' output from dtype('O')
    to dtype('float64') with casting rule 'same_kind'

Root cause: in `TransformationSummarizer.summarize_transformation_magnitude`, the
base-case lookup `summarize_from_magnitude(..., key_magnitude="magnitude")` runs
*before* the transformer-specific special cases. For ENFU exports/prices the
`magnitude` parameter is a dict (e.g. ``{"fuel_crude": 2.5, "fuel_natural_gas": 200}``),
so the dict is returned as-is and `_update_vir_and_start_period` then does
``vec_implementation_ramp *= magnitude`` with a dict, which numpy cannot cast.

Fix: wrap `summarize_from_magnitude` so a dict magnitude collapses to the mean of
its numeric values -- the same summary the ENFU special-case summarizers already
intend (`np.mean(dict.values())`). Scalars and ``None`` pass through unchanged, so
``None`` still falls through to the special cases and numeric behaviour is identical.
"""

import numpy as np

import sisepuede.visualization.tables as svt


_ATTR_FLAG = "_dict_magnitude_fix_applied"


def _summarize_from_magnitude_scalar(self, dict_params, kwargs, key_magnitude="magnitude"):
    """Patched ``summarize_from_magnitude`` that never returns a non-scalar magnitude."""
    magnitude = dict_params.get(
        key_magnitude,
        kwargs.get(key_magnitude),
    )

    if isinstance(magnitude, dict):
        vals = [
            v for v in magnitude.values()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
        magnitude = float(np.mean(vals)) if len(vals) else None

    return magnitude


def apply_levers_dict_magnitude_fix() -> bool:
    """Monkeypatch sisepuede so the levers table handles dict-valued magnitudes.

    Call this once before using ``LeversImplementationTable``. Idempotent and safe
    to call from any notebook. Returns True if the patch was applied, False if it
    was already in place.
    """
    summarizer = svt.TransformationSummarizer

    if getattr(summarizer, _ATTR_FLAG, False):
        return False

    summarizer.summarize_from_magnitude = _summarize_from_magnitude_scalar
    setattr(summarizer, _ATTR_FLAG, True)

    return True
