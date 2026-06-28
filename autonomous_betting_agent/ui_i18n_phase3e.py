from __future__ import annotations

from autonomous_betting_agent.ui_i18n import COLUMN_LABELS_ES, VALUE_COLUMNS, VALUE_LABELS_ES

COLUMN_LABELS_ES.update({
    "dynamic_shadow_run_id": "ID de corrida Dynamic Shadow",
    "dynamic_probability": "Probabilidad dinamica",
    "dynamic_edge": "Ventaja dinamica",
    "dynamic_no_vig_edge": "Ventaja dinamica sin vig",
    "dynamic_EV": "EV dinamico",
    "dynamic_signal_status": "Estado de senal dinamica",
    "lr_training_rows": "Filas entrenamiento LR",
    "lr_evaluation_rows": "Filas evaluacion LR",
    "evaluation_mode": "Modo de evaluacion",
    "leakage_guard_enabled": "Guardia anti-filtracion activa",
    "train_test_overlap_count": "Traslape train/test",
    "blocked_leakage_fields": "Campos de filtracion bloqueados",
    "walk_forward_windows_evaluated": "Ventanas walk-forward evaluadas",
    "dynamic_green_count": "Conteo dynamic green",
    "dynamic_yellow_count": "Conteo dynamic yellow",
    "dynamic_red_count": "Conteo dynamic red",
    "dynamic_odds_applied_live_count": "Conteo Dynamic Odds aplicado en vivo",
})

VALUE_LABELS_ES.update({
    "dynamic_green": "dynamic green",
    "dynamic_yellow": "dynamic yellow",
    "dynamic_red": "dynamic red",
    "no_odds": "sin cuotas",
    "no_lr_data": "sin datos LR",
    "shadow_only": "solo shadow",
    "future_manual_review": "revision manual futura",
    "keep_testing": "seguir probando",
    "data_blocked": "bloqueado por datos",
    "rejected": "rechazado",
    "chronological_holdout": "holdout cronologico",
    "stable_hash_holdout": "holdout hash estable",
    "phase3e_dynamic_odds_shadow_run": "ejecucion shadow Dynamic Odds Fase 3E",
})

VALUE_COLUMNS.update({"dynamic_signal_status", "evaluation_mode", "decision", "decision_reason", "event_type"})
