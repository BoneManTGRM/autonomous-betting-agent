"""Reparodynamics operating doctrine for ABA Signal Pro.

This module is intentionally wording-focused and behavior-safe. It defines the
Phase 3E doctrine used by reports and dashboards. Phase 3E adds a Dynamic Odds
Predictor shadow layer while still forbidding live repairs, live confidence
changes, live bet-tier changes, bankroll changes, sportsbook changes, live
filters, proof-ledger mutation, stored-data mutation, and production model
mutation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

DOCTRINE_SCHEMA_VERSION = "reparodynamics_phase_3e_dynamic_odds_shadow_v1"

REPARODYNAMICS_MOTIVE = (
    "Reparodynamics is the operating doctrine of measured self-repair. "
    "ABA observes first, diagnoses carefully, preserves data integrity, "
    "conserves repair energy, tests repairs in Shadow Backtest, stores "
    "repair memory for manual review, and now evaluates Dynamic Odds Predictor "
    "probabilities in shadow mode only."
)

REPAIR_PRINCIPLES = [
    "Observe first and repair later.",
    "Diagnose drift before proposing any repair.",
    "Separate data blockers from repair candidates.",
    "Prefer targeted repair over blind retraining.",
    "Conserve repair energy by changing only what evidence supports.",
    "Evaluate pattern candidates in Shadow Backtest before promotion.",
    "Evaluate Dynamic Odds Predictor output against held-out rows before any future consideration.",
    "Store repeated repair evidence in Repair Memory before future consideration.",
    "Treat manual review as a label and future gate only, not activation.",
    "Treat RYE readiness as readiness only, not live activation.",
]

SAFETY_PRINCIPLES = [
    "Phase 3E enables Dynamic Odds Predictor shadow evaluation, Repair Memory, and Manual Review only.",
    "Learning means observation, diagnostics, shadow evaluation, memory summaries, readiness checks, and saved reports only.",
    "No live repair activates during Phase 3E.",
    "No dynamic odds probability activates during Phase 3E.",
    "No repair survives without repeated proof.",
    "Manual approval does not activate live repairs.",
    "The system does not chase losses.",
    "The system does not panic after variance.",
    "The system does not blindly retrain.",
    "The system does not inflate confidence.",
]

FORBIDDEN_PHASE_3E_ACTIONS = [
    "live repairs",
    "Dynamic Odds Predictor live activation",
    "TGRM repair activation",
    "full RYE repair activation",
    "Hidden Value Score activation",
    "confidence calibration activation",
    "live pick filtering",
    "live model mutation",
    "Learning Page live model updates",
    "automatic confidence adjustment",
    "automatic bet-tier changes",
    "production repair candidates",
    "automatic bankroll changes",
    "automatic sportsbook recommendation changes",
    "stored proof data mutation",
    "automatic proof ledger mutation",
    "automatic live promotion",
]

PHASE_3E_DOCTRINE: dict[str, Any] = {
    "doctrine_version": DOCTRINE_SCHEMA_VERSION,
    "motive": REPARODYNAMICS_MOTIVE,
    "current_phase": "Phase 3E Dynamic Odds Predictor Shadow",
    "operating_mode": "Dynamic Odds Predictor Shadow + Repair Memory + Manual Review Gate",
    "repair_philosophy": "Evidence-gated targeted repair memory with leakage-safe Dynamic Odds shadow testing",
    "repair_principles": REPAIR_PRINCIPLES,
    "safety_principles": SAFETY_PRINCIPLES,
    "forbidden_actions": FORBIDDEN_PHASE_3E_ACTIONS,
    "live_mutation": "FORBIDDEN",
    "repair_activation": "OFF",
    "shadow_mode_activation": "ON",
    "dynamic_odds_predictor": "SHADOW ONLY",
    "dynamic_odds_live_activation": "OFF",
    "dynamic_odds_applied_live": 0,
    "dynamic_odds_applied_live_count": 0,
    "tgrm_activation": "SHADOW ONLY",
    "rye_activation": "SHADOW ONLY",
    "model_training": "FORBIDDEN",
    "stored_data_mutation": "FORBIDDEN",
    "live_repairs_applied": 0,
    "repairs_applied_live": 0,
    "live_repairs_applied_count": 0,
    "repair_memory": "ENABLED",
    "manual_review": "ENABLED",
    "phase4_lockbox": "PREPARATION ONLY",
    "automatic_live_promotion": "FORBIDDEN",
    "final_rule": "ABA may run Dynamic Odds Predictor in shadow mode and store repair memory, but live repair and live dynamic odds activation remain forbidden.",
}

# Backward-compatible aliases for code that imports older constant names.
PHASE_3D_DOCTRINE = PHASE_3E_DOCTRINE
PHASE_3C_DOCTRINE = PHASE_3E_DOCTRINE
PHASE_3B_DOCTRINE = PHASE_3E_DOCTRINE
PHASE_3A_DOCTRINE = PHASE_3E_DOCTRINE


def get_reparodynamics_doctrine() -> dict[str, Any]:
    """Return a defensive copy of the current Reparodynamics doctrine."""
    return deepcopy(PHASE_3E_DOCTRINE)
