from __future__ import annotations

from itertools import product
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Threshold Optimizer', layout='wide')
LANG = render_app_sidebar('threshold_optimizer', language_key='threshold_optimizer_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Threshold Optimizer + Score Accuracy Lab',
        'caption': 'Learns which thresholds are actually working. Score mode can grade winner accuracy without odds. Profit mode overlays odds when prices are available.',
        'upload': 'Upload graded CSV / proof ledger', 'run': 'Run optimizer', 'no_file': 'Upload a CSV with finished results first.', 'not_enough': 'Need at least 25 resolved rows for useful optimization.',
        'summary': 'Resolved data summary', 'score_optimizer': 'Score / winner optimizer', 'profit_optimizer': 'Profit optimizer', 'false_positive': 'False positive report', 'sport_market': 'Sport/market performance', 'tier_perf': 'Tier performance', 'download': 'Download optimizer report',
        'proof_warning': 'Use only picks locked before the game when making performance claims. Backfilled results can help tuning, but they are not proof.',
        'mode': 'Optimizer focus', 'score_mode': 'Score-derived winner accuracy first', 'profit_mode': 'Profit / odds overlay',
    },
    'es': {
        'title': 'Optimizador de Umbrales + Laboratorio de Acierto por Marcador',
        'caption': 'Aprende qué umbrales realmente funcionan. El modo marcador puede calificar acierto de ganador sin cuotas. El modo ganancia usa cuotas cuando existen.',
        'upload': 'Subir CSV calificado / ledger de prueba', 'run': 'Ejecutar optimizador', 'no_file': 'Primero sube un CSV con resultados terminados.', 'not_enough': 'Se necesitan al menos 25 filas resueltas para una optimización útil.',
        'summary': 'Resumen de datos resueltos', 'score_optimizer': 'Optimizador marcador / ganador', 'profit_optimizer': 'Optimizador de ganancia', 'false_positive': 'Reporte de falsos positivos', 'sport_market': 'Rendimiento por deporte/mercado', 'tier_perf': 'Rendimiento por nivel', 'download': 'Descargar reporte del optimizador',
        'proof_warning': 'Usa solo picks bloqueados antes del juego para declarar rendimiento. Los resultados agregados después sirven para ajustar, pero no son prueba.',
        'mode': 'Enfoque del optimizador', 'score_mode': 'Acierto de ganador derivado de marcador primero', 'profit_mode': 'Ganancia / cuotas',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def clean_name(value: Any) -> str:
    return str(value or '').strip().lower().replace(' ', '_').replace('-', '_')


def first_col(frame: pd.DataFrame, aliases: list[str]) -> str | None:
    lookup = {clean_name(col): col for col in frame.columns}
    for alias in aliases:
        if clean_name(alias) in lookup:
            return lookup[clean_name(alias)]
    return None


def text_col(frame: pd.DataFrame, aliases: list[str], default: str = '') -> pd.Series:
    col = first_col(frame, aliases)
    if col is None:
        return pd.Series(default, index=frame.index, dtype=str)
    return frame[col].fillna(default).astype(str).str.strip()


def num_col(frame: pd.DataFrame, aliases: list[str], *, probability: bool = False, percent_like: bool = False) -> pd.Series:
    col = first_col(frame, aliases)
    if col is None:
        return pd.Series(float('nan'), index=frame.index, dtype=float)
    raw = frame[col].astype(str).str.strip()
    out = pd.to_numeric(raw.str.replace('%', '', regex=False).str.replace(',', '', regex=False), errors='coerce')
    percent_mask = raw.str.contains('%', regex=False, na=False)
    out.loc[percent_mask] = out.loc[percent_mask] / 100.0
    col_key = clean_name(col)
    if probability:
        out = out.where(out <= 1.0, out / 100.0)
    elif percent_like and ('percent' in col_key or 'pct' in col_key):
        out = out.where(out.abs() <= 1.0, out / 100.0)
    return out


def american_to_decimal(values: pd.Series) -> pd.Series:
    out = pd.Series(float('nan'), index=values.index, dtype=float)
    positive = values > 0
    negative = values < 0
    out.loc[positive] = 1.0 + (values.loc[positive] / 100.0)
    out.loc[negative] = 1.0 + (100.0 / values.loc[negative].abs())
    return out


def compact_text(series: pd.Series) -> pd.Series:
    return series.fillna('').astype(str).str.lower().str.replace(r'[^a-z0-9áéíóúüñ]+', '', regex=True)


def outcome_from_text(result: pd.Series, pick: pd.Series, winner: pd.Series) -> pd.Series:
    outcome = pd.Series(pd.NA, index=result.index, dtype='Int64')
    compact = compact_text(result)
    win_exact = {'win', 'won', 'w', 'correct', 'hit', 'true', 'yes', '1', '10', 'ganada', 'gano', 'victoria', 'acierto'}
    loss_exact = {'loss', 'lost', 'l', 'incorrect', 'miss', 'false', 'no', '0', '00', 'perdida', 'perdio', 'derrota', 'fallo'}
    outcome[compact.isin(win_exact)] = 1
    outcome[compact.isin(loss_exact)] = 0
    outcome[outcome.isna() & compact.str.contains(r'win|won|correct|hit|ganad|victor|aciert', regex=True, na=False)] = 1
    outcome[outcome.isna() & compact.str.contains(r'loss|lost|incorrect|miss|perdid|derrot|fall', regex=True, na=False)] = 0
    pick_clean = compact_text(pick)
    winner_clean = compact_text(winner)
    outcome[outcome.isna() & winner_clean.ne('') & pick_clean.ne('') & winner_clean.eq(pick_clean)] = 1
    outcome[outcome.isna() & winner_clean.ne('') & pick_clean.ne('') & ~winner_clean.eq(pick_clean)] = 0
    return outcome


def winner_from_scores(home_team: pd.Series, away_team: pd.Series, home_score: pd.Series, away_score: pd.Series) -> pd.Series:
    out = pd.Series('', index=home_score.index, dtype=str)
    home_win = home_score.gt(away_score)
    away_win = away_score.gt(home_score)
    out.loc[home_win] = home_team.loc[home_win].fillna('').astype(str)
    out.loc[away_win] = away_team.loc[away_win].fillna('').astype(str)
    return out


def normalize(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out['event'] = text_col(frame, ['event', 'event_name', 'game', 'match', 'partido'])
    out['sport'] = text_col(frame, ['sport', 'sport_key', 'league', 'competition', 'deporte'])
    out['market_type'] = text_col(frame, ['market_type', 'market', 'bet_type', 'prop_type', 'tipo_mercado'], 'score').str.lower()
    out['prediction'] = text_col(frame, ['prediction', 'pick', 'selection', 'prediccion', 'pronostico'])
    out['home_team'] = text_col(frame, ['home_team', 'home', 'local'])
    out['away_team'] = text_col(frame, ['away_team', 'away', 'visitor', 'visitante'])
    out['volume_tier'] = text_col(frame, ['confidence_bucket', 'volume_tier', 'tier', 'ultra80_tier'], 'unknown')
    out['model_probability'] = num_col(frame, ['model_probability_clean', 'model_probability', 'final_probability_value', 'probability', 'probabilidad', 'prob_final'], probability=True)
    decimal = num_col(frame, ['decimal_price', 'best_price', 'average_price', 'odds', 'price', 'cuota', 'mejor_cuota'])
    american = num_col(frame, ['american_odds', 'american_price', 'moneyline'])
    out['decimal_price'] = decimal.fillna(american_to_decimal(american))
    out['edge'] = num_col(frame, ['model_market_edge', 'edge_probability', 'model_edge', 'edge', 'edge_percent', 'edge_pct'], percent_like=True)
    out['ev'] = num_col(frame, ['expected_value_per_unit', 'computed_ev_decimal', 'estimated_ev_decimal', 'estimated_ev', 'ev', 'expected_value_percent', 'ev_percent', 'ev_pct'], percent_like=True)
    out['books'] = num_col(frame, ['bookmaker_count', 'books', 'source_count', 'bookmakers']).fillna(0.0)
    out['api_coverage'] = num_col(frame, ['api_coverage_score', 'api_coverage'], probability=True).fillna(0.0)
    out['agent_score'] = num_col(frame, ['agent_score']).fillna(0.0)
    out['scanner_strength'] = num_col(frame, ['scanner_strength_score', 'signal_strength_score']).fillna(0.0)
    out['memory_signal'] = num_col(frame, ['pattern_ara_memory_signal', 'ara_memory_signal', 'memory_signal'], percent_like=True).fillna(0.0)
    out['pred_home_score'] = num_col(frame, ['predicted_home_score', 'home_score_predicted', 'home_predicted_score', 'projected_home_score', 'home_projection'])
    out['pred_away_score'] = num_col(frame, ['predicted_away_score', 'away_score_predicted', 'away_predicted_score', 'projected_away_score', 'away_projection'])
    out['actual_home_score'] = num_col(frame, ['actual_home_score', 'home_final_score', 'final_home_score', 'home_score'])
    out['actual_away_score'] = num_col(frame, ['actual_away_score', 'away_final_score', 'final_away_score', 'away_score'])
    out['predicted_margin'] = out['pred_home_score'] - out['pred_away_score']
    out['actual_margin'] = out['actual_home_score'] - out['actual_away_score']
    out['predicted_total'] = out['pred_home_score'] + out['pred_away_score']
    out['actual_total'] = out['actual_home_score'] + out['actual_away_score']
    out['margin_error'] = (out['predicted_margin'] - out['actual_margin']).abs()
    out['total_error'] = (out['predicted_total'] - out['actual_total']).abs()
    result = text_col(frame, ['result_status', 'result', 'outcome', 'win_loss', 'graded_result', 'status', 'resultado'])
    winner = text_col(frame, ['winner', 'actual_winner', 'ganador'])
    out['outcome'] = outcome_from_text(result, out['prediction'], winner)
    predicted_winner = winner_from_scores(out['home_team'], out['away_team'], out['pred_home_score'], out['pred_away_score'])
    actual_winner = winner_from_scores(out['home_team'], out['away_team'], out['actual_home_score'], out['actual_away_score'])
    score_mask = predicted_winner.ne('') & actual_winner.ne('')
    out.loc[score_mask, 'outcome'] = (compact_text(predicted_winner[score_mask]).eq(compact_text(actual_winner[score_mask]))).astype(int)
    implied = 1.0 / out['decimal_price']
    out['ev'] = out['ev'].fillna(out['model_probability'] * out['decimal_price'] - 1.0)
    out['edge'] = out['edge'].fillna(out['model_probability'] - implied)
    return out


def profit_units(prob_frame: pd.DataFrame, stake: float = 1.0) -> pd.Series:
    outcome = prob_frame['outcome'].astype(float)
    price = prob_frame['decimal_price'].astype(float)
    profits = pd.Series(float('nan'), index=prob_frame.index, dtype=float)
    valid = price.gt(1.0) & outcome.notna()
    profits.loc[valid] = -1.0 * stake
    wins = valid & outcome.eq(1.0)
    profits.loc[wins] = (price.loc[wins] - 1.0) * stake
    return profits


def metrics(frame: pd.DataFrame) -> dict[str, Any]:
    resolved = frame[frame['outcome'].notna()].copy()
    if resolved.empty:
        return {'rows': 0, 'wins': 0, 'losses': 0, 'hit_rate': None, 'profit_units': None, 'roi': None, 'avg_odds': None, 'avg_prob': None, 'avg_margin_error': None, 'avg_total_error': None}
    wins = int(resolved['outcome'].sum())
    rows = int(len(resolved))
    profits = profit_units(resolved).dropna()
    return {
        'rows': rows,
        'wins': wins,
        'losses': rows - wins,
        'hit_rate': round(wins / rows, 6),
        'profit_units': None if profits.empty else round(float(profits.sum()), 4),
        'roi': None if profits.empty else round(float(profits.sum()) / len(profits), 6),
        'avg_odds': None if resolved['decimal_price'].dropna().empty else round(float(resolved['decimal_price'].mean()), 4),
        'avg_prob': None if resolved['model_probability'].dropna().empty else round(float(resolved['model_probability'].mean()), 6),
        'avg_margin_error': None if resolved['margin_error'].dropna().empty else round(float(resolved['margin_error'].mean()), 4),
        'avg_total_error': None if resolved['total_error'].dropna().empty else round(float(resolved['total_error'].mean()), 4),
    }


def score_mask(frame: pd.DataFrame, p: float, score_gap: float, signal: float, agent: float, books: int, api: float) -> pd.Series:
    gap = frame['predicted_margin'].abs().fillna(0.0)
    return (
        frame['model_probability'].fillna(0.0).ge(p)
        & gap.ge(score_gap)
        & frame['scanner_strength'].fillna(0.0).ge(signal)
        & frame['agent_score'].fillna(0.0).ge(agent)
        & frame['books'].fillna(0.0).ge(books)
        & frame['api_coverage'].fillna(0.0).ge(api)
    )


def optimize_score(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for p, gap, signal, agent, books, api in product([0.56, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68], [0, 1, 2, 3, 5, 7], [30, 35, 38, 40, 45, 50], [0, 35, 40, 45, 50, 60], [0, 1, 2, 4], [0.0, 0.33, 0.50]):
        selected = frame[score_mask(frame, p, gap, signal, agent, books, api)]
        m = metrics(selected)
        if m['rows'] < 10:
            continue
        hit = m['hit_rate'] or 0
        score = hit * 100 + min(m['rows'], 250) / 10
        if hit < 0.65:
            score -= 20
        rows.append({**m, 'score': round(score, 4), 'min_probability': p, 'min_score_gap': gap, 'min_signal_strength': signal, 'min_agent_score': agent, 'min_books': books, 'min_api_coverage': api})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(['score', 'hit_rate', 'rows'], ascending=False).head(50).reset_index(drop=True)


def profit_mask(frame: pd.DataFrame, p: float, edge: float, books: int, signal: float, agent: float) -> pd.Series:
    return frame['model_probability'].fillna(0.0).ge(p) & frame['decimal_price'].gt(1.0).fillna(False) & frame['edge'].fillna(-1.0).ge(edge) & frame['books'].fillna(0.0).ge(books) & frame['scanner_strength'].fillna(0.0).ge(signal) & frame['agent_score'].fillna(0.0).ge(agent)


def optimize_profit(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for p, edge, books, signal, agent in product([0.58, 0.60, 0.62, 0.64, 0.66, 0.70], [-0.03, -0.02, -0.01, 0.0, 0.02], [1, 2, 4], [35, 40, 45, 50], [35, 40, 50, 60]):
        selected = frame[profit_mask(frame, p, edge, books, signal, agent)]
        m = metrics(selected)
        if m['rows'] < 10 or m['roi'] is None:
            continue
        score = (m['hit_rate'] or 0) * 80 + (m['roi'] or -1) * 40 + min(m['rows'], 250) / 20
        rows.append({**m, 'score': round(score, 4), 'min_probability': p, 'min_edge': edge, 'min_books': books, 'min_signal_strength': signal, 'min_agent_score': agent})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(['score', 'roi', 'hit_rate', 'rows'], ascending=False).head(50).reset_index(drop=True)


def group_report(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    usable = frame[frame['outcome'].notna()].copy()
    rows = []
    for keys, group in usable.groupby(cols, dropna=False):
        item = metrics(group)
        if item['rows'] < 3:
            continue
        if not isinstance(keys, tuple):
            keys = (keys,)
        rows.append({**{col: value for col, value in zip(cols, keys)}, **item})
    return pd.DataFrame(rows).sort_values(['hit_rate', 'rows'], ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


def false_positive_report(frame: pd.DataFrame) -> pd.DataFrame:
    losses = frame[(frame['outcome'] == 0)].copy()
    if losses.empty:
        return pd.DataFrame()
    tests = {
        'probability_under_60': losses['model_probability'].lt(0.60),
        'score_gap_under_2': losses['predicted_margin'].abs().lt(2),
        'books_below_4': losses['books'].lt(4),
        'api_below_50pct': losses['api_coverage'].lt(0.50),
        'agent_below_60': losses['agent_score'].lt(60),
        'signal_below_45': losses['scanner_strength'].lt(45),
        'negative_edge': losses['edge'].lt(0.0),
    }
    rows = []
    for reason, mask in tests.items():
        subset = losses[mask.fillna(False)]
        if subset.empty:
            continue
        rows.append({'loss_pattern': reason, 'loss_rows': int(len(subset)), 'share_of_losses': round(len(subset) / len(losses), 6), 'avg_probability': round(float(subset['model_probability'].mean()), 6), 'avg_score_gap': None if subset['predicted_margin'].dropna().empty else round(float(subset['predicted_margin'].abs().mean()), 4), 'avg_signal': round(float(subset['scanner_strength'].mean()), 4)})
    return pd.DataFrame(rows).sort_values('loss_rows', ascending=False).reset_index(drop=True)


st.title(t('title'))
st.caption(t('caption'))
st.warning(t('proof_warning'))
upload = st.file_uploader(t('upload'), type=['csv'])
mode = st.radio(t('mode'), [t('score_mode'), t('profit_mode')], horizontal=True)
if st.button(t('run'), type='primary', use_container_width=True):
    if upload is None:
        st.info(t('no_file'))
        st.stop()
    raw = pd.read_csv(upload)
    data = normalize(raw)
    resolved = data[data['outcome'].notna()].copy()
    if len(resolved) < 25:
        st.warning(f"{t('not_enough')} Resolved rows: {len(resolved)}")
    summary = pd.DataFrame([metrics(resolved)])
    score_opt = optimize_score(resolved)
    profit_opt = optimize_profit(resolved)
    false_pos = false_positive_report(resolved)
    sport_market = group_report(resolved, ['sport', 'market_type'])
    tier_perf = group_report(resolved, ['volume_tier'])
    tabs = st.tabs([t('summary'), t('score_optimizer'), t('profit_optimizer'), t('false_positive'), t('sport_market'), t('tier_perf')])
    with tabs[0]:
        st.dataframe(summary, use_container_width=True, hide_index=True)
    with tabs[1]:
        st.dataframe(score_opt, use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(profit_opt, use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe(false_pos, use_container_width=True, hide_index=True)
    with tabs[4]:
        st.dataframe(sport_market, use_container_width=True, hide_index=True)
    with tabs[5]:
        st.dataframe(tier_perf, use_container_width=True, hide_index=True)
    report = {'summary': summary, 'score_optimizer': score_opt, 'profit_optimizer': profit_opt, 'false_positive': false_pos, 'sport_market': sport_market, 'tier_perf': tier_perf}
    merged = []
    for name, frame in report.items():
        if frame.empty:
            continue
        temp = frame.copy()
        temp.insert(0, 'report_section', name)
        merged.append(temp)
    download = pd.concat(merged, ignore_index=True, sort=False) if merged else pd.DataFrame()
    st.download_button(t('download'), download.to_csv(index=False), file_name='threshold_optimizer_report.csv', mime='text/csv')
