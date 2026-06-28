from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import filter_locked_proof_rows, save_persistent_ledger
from autonomous_betting_agent.pick_hold_store import (
    HELD_KEYS,
    github_store_enabled,
    load_held_rows,
    normalize_workspace_id,
    save_held_rows,
    store_snapshot,
)
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title='Storage Diagnostics', layout='wide')
LANG = render_app_sidebar('storage_diagnostics', language_key='storage_diagnostics_language')

GITHUB_API = 'https://api.github.com'
PROOF_KEYS = ['odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows', 'ara_latest_predictions']

TEXT = {
    'en': {
        'title': 'Storage Diagnostics',
        'caption': 'Session, local disk, backup, and GitHub durable recovery status for the active workspace.',
        'workspace_id': 'Workspace ID',
        'active_workspace': 'Active workspace',
        'github_store': 'GitHub durable store',
        'enabled': 'enabled',
        'not_configured': 'not configured',
        'repo_target': 'GitHub repo target',
        'loaded_rows': 'Total loaded rows',
        'disk_rows': 'Total disk rows',
        'backup_rows': 'Total backup rows',
        'github_rows': 'Total GitHub rows',
        'write_test_note': 'The red write-test button only proves GitHub writes work. It does not save proof rows by itself.',
        'run_write_test': 'Run GitHub durable write test',
        'sync_rows': 'Sync loaded rows to GitHub',
        'write_failed': 'GitHub write failed',
        'synced_keys': 'Keys',
        'rows': 'rows',
        'recover_title': 'Recover from locked proof CSV',
        'recover_note': 'Use this if a reboot wiped the app but you downloaded a locked proof CSV earlier.',
        'recover_upload': 'Upload locked proof CSV and save to GitHub durable storage',
        'missing_github': 'GitHub durable storage is not configured. Add GITHUB_PROOF_TOKEN to Streamlit secrets to survive reboot/redeploy.',
        'no_github_rows': 'GitHub durable storage is enabled, but no durable proof rows were found yet. Create a new lock in Odds Lock Pro, then return here or press Sync loaded rows to GitHub while rows are still visible.',
        'has_github_rows': 'GitHub durable storage has rows for this workspace.',
        'no_rows': 'No saved rows found for this workspace.',
        'readable': 'Storage is readable for this workspace.',
        'no_token': 'No GitHub token found in Streamlit secrets.',
        'probe_purpose': 'ABA Signal Pro durable storage probe only; not a proof ledger',
        'probe_message': 'Durable storage probe for',
        'probe_success': 'GitHub durable write test succeeded',
        'store_not_configured': 'GitHub durable store is not configured.',
        'sync_success': 'Synced loaded rows to GitHub durable storage.',
        'sync_empty': 'No loaded/local rows were available to sync. Recreate locks first.',
        'csv_read_error': 'Could not read CSV',
        'csv_no_locked': 'Uploaded CSV does not contain locked proof rows with proof_id and locked_at_utc.',
        'csv_no_save': 'Proof rows were detected, but save_persistent_ledger returned no rows.',
        'csv_imported': 'Imported locked proof CSV and saved it to durable storage.',
    },
    'es': {
        'title': 'Diagnóstico de Almacenamiento',
        'caption': 'Estado de sesión, disco local, respaldo y recuperación duradera de GitHub para el espacio de trabajo activo.',
        'workspace_id': 'ID del espacio de trabajo',
        'active_workspace': 'Espacio de trabajo activo',
        'github_store': 'Almacenamiento duradero de GitHub',
        'enabled': 'activado',
        'not_configured': 'no configurado',
        'repo_target': 'Repositorio GitHub destino',
        'loaded_rows': 'Total de filas cargadas',
        'disk_rows': 'Total de filas en disco',
        'backup_rows': 'Total de filas en respaldo',
        'github_rows': 'Total de filas en GitHub',
        'write_test_note': 'El botón rojo de prueba solo confirma que GitHub puede escribir. No guarda filas de prueba por sí solo.',
        'run_write_test': 'Ejecutar prueba de escritura duradera en GitHub',
        'sync_rows': 'Sincronizar filas cargadas con GitHub',
        'write_failed': 'Falló la escritura en GitHub',
        'synced_keys': 'Claves',
        'rows': 'filas',
        'recover_title': 'Recuperar desde CSV de prueba bloqueada',
        'recover_note': 'Usa esto si un reinicio borró la app pero descargaste antes un CSV de prueba bloqueada.',
        'recover_upload': 'Subir CSV de prueba bloqueada y guardarlo en almacenamiento duradero de GitHub',
        'missing_github': 'El almacenamiento duradero de GitHub no está configurado. Agrega GITHUB_PROOF_TOKEN a los secretos de Streamlit para sobrevivir reinicios/redespliegues.',
        'no_github_rows': 'El almacenamiento duradero de GitHub está activado, pero todavía no se encontraron filas de prueba duraderas. Crea un nuevo bloqueo en Odds Lock Pro y vuelve aquí, o presiona Sincronizar filas cargadas con GitHub mientras las filas aún sean visibles.',
        'has_github_rows': 'El almacenamiento duradero de GitHub tiene filas para este espacio de trabajo.',
        'no_rows': 'No se encontraron filas guardadas para este espacio de trabajo.',
        'readable': 'El almacenamiento se puede leer para este espacio de trabajo.',
        'no_token': 'No se encontró token de GitHub en los secretos de Streamlit.',
        'probe_purpose': 'Sonda de almacenamiento duradero de ABA Signal Pro; no es un ledger de prueba',
        'probe_message': 'Sonda de almacenamiento duradero para',
        'probe_success': 'La prueba de escritura duradera en GitHub funcionó',
        'store_not_configured': 'El almacenamiento duradero de GitHub no está configurado.',
        'sync_success': 'Filas cargadas sincronizadas con almacenamiento duradero de GitHub.',
        'sync_empty': 'No había filas cargadas/locales disponibles para sincronizar. Primero recrea los bloqueos.',
        'csv_read_error': 'No se pudo leer el CSV',
        'csv_no_locked': 'El CSV subido no contiene filas de prueba bloqueadas con proof_id y locked_at_utc.',
        'csv_no_save': 'Se detectaron filas de prueba, pero save_persistent_ledger no devolvió filas.',
        'csv_imported': 'CSV de prueba bloqueada importado y guardado en almacenamiento duradero.',
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return localize_dataframe(frame, LANG)


def _secret_value(*names: str) -> str:
    for name in names:
        try:
            value = str(st.secrets.get(name, '')).strip()
            if value:
                return value
        except Exception:
            pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


def _github_settings() -> tuple[str, str, str]:
    token = _secret_value('GITHUB_PROOF_TOKEN', 'PROOF_GITHUB_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN')
    repo = _secret_value('GITHUB_PROOF_REPO', 'PROOF_GITHUB_REPO', 'GITHUB_REPOSITORY') or 'BoneManTGRM/autonomous-betting-agent'
    branch = _secret_value('GITHUB_PROOF_BRANCH', 'PROOF_GITHUB_BRANCH') or 'main'
    return token, repo, branch


def github_write_probe(workspace_id: str) -> dict[str, Any]:
    token, repo, branch = _github_settings()
    if not token:
        return {'ok': False, 'status_code': None, 'message': t('no_token')}
    path = f'.aba_state/diagnostic_probe_{normalize_workspace_id(workspace_id)}.json'
    url = f'{GITHUB_API}/repos/{repo}/contents/{path}'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    sha = ''
    try:
        existing = requests.get(url, headers=headers, params={'ref': branch}, timeout=15)
        if existing.status_code == 200:
            sha = str(existing.json().get('sha', ''))
    except Exception:
        sha = ''
    payload = {
        'workspace_id': normalize_workspace_id(workspace_id),
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'purpose': t('probe_purpose'),
    }
    body: dict[str, Any] = {
        'message': f"{t('probe_message')} {normalize_workspace_id(workspace_id)}",
        'branch': branch,
        'content': base64.b64encode((json.dumps(payload, indent=2) + '\n').encode('utf-8')).decode('ascii'),
    }
    if sha:
        body['sha'] = sha
    try:
        response = requests.put(url, headers=headers, json=body, timeout=20)
        if response.status_code in {200, 201}:
            return {'ok': True, 'status_code': response.status_code, 'message': f"{t('probe_success')}: {path}"}
        return {'ok': False, 'status_code': response.status_code, 'message': response.text[:500]}
    except Exception as exc:
        return {'ok': False, 'status_code': None, 'message': str(exc)}


def sync_loaded_rows_to_github(workspace_id: str) -> dict[str, Any]:
    if not github_store_enabled():
        return {'ok': False, 'synced_keys': 0, 'synced_rows': 0, 'message': t('store_not_configured'), 'details': ''}
    synced_keys = 0
    synced_rows = 0
    details: list[str] = []
    for key in sorted(HELD_KEYS):
        rows = load_held_rows(key, workspace_id)
        if not rows:
            details.append(f'{key}: 0')
            continue
        saved = save_held_rows(key, rows, workspace_id)
        synced_keys += 1
        synced_rows += saved
        details.append(f'{key}: {saved}')
    ok = synced_rows > 0
    return {
        'ok': ok,
        'synced_keys': synced_keys,
        'synced_rows': synced_rows,
        'message': t('sync_success') if ok else t('sync_empty'),
        'details': '; '.join(details),
    }


def import_locked_csv(uploaded_file: Any, workspace_id: str) -> tuple[bool, str, int]:
    try:
        frame = pd.read_csv(uploaded_file)
    except Exception as exc:
        return False, f"{t('csv_read_error')}: {exc}", 0
    locked = filter_locked_proof_rows(frame)
    if locked.empty:
        return False, t('csv_no_locked'), 0
    locked = locked.copy()
    locked['test_window_id'] = workspace_id
    saved = save_persistent_ledger(locked, workspace_id=workspace_id)
    if saved.empty:
        return False, t('csv_no_save'), 0
    records = saved.to_dict('records')
    for key in PROOF_KEYS:
        save_held_rows(key, records, workspace_id)
        st.session_state[key] = records
    return True, t('csv_imported'), len(saved)


st.title(t('title'))
st.caption(t('caption'))

workspace_input = st.text_input(t('workspace_id'), value=st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id

snapshot = store_snapshot(workspace_id)

token, repo, branch = _github_settings()
st.metric(t('active_workspace'), workspace_id)
st.metric(t('github_store'), t('enabled') if github_store_enabled() else t('not_configured'))
st.caption(f"{t('repo_target')}: {repo} / branch: {branch}")
st.metric(t('loaded_rows'), int(snapshot['loaded_rows'].sum()) if not snapshot.empty else 0)
st.metric(t('disk_rows'), int(snapshot['disk_rows'].sum()) if not snapshot.empty else 0)
st.metric(t('backup_rows'), int(snapshot['backup_rows'].sum()) if not snapshot.empty else 0)
st.metric(t('github_rows'), int(snapshot['github_rows'].sum()) if not snapshot.empty and 'github_rows' in snapshot.columns else 0)

st.info(t('write_test_note'))
button_cols = st.columns(2)
if button_cols[0].button(t('run_write_test'), type='primary', use_container_width=True):
    result = github_write_probe(workspace_id)
    if result.get('ok'):
        st.success(result.get('message'))
    else:
        st.error(f"{t('write_failed')}: {result.get('status_code')} / {result.get('message')}")

if button_cols[1].button(t('sync_rows'), use_container_width=True):
    result = sync_loaded_rows_to_github(workspace_id)
    if result.get('ok'):
        st.success(f"{result.get('message')} {t('synced_keys')}: {result.get('synced_keys')} / {t('rows')}: {result.get('synced_rows')}")
        st.caption(str(result.get('details', '')))
    else:
        st.warning(str(result.get('message')))
        st.caption(str(result.get('details', '')))

with st.expander(t('recover_title'), expanded=False):
    st.caption(t('recover_note'))
    recovery_upload = st.file_uploader(t('recover_upload'), type=['csv'], key='storage_recovery_upload')
    if recovery_upload is not None:
        ok, message, count = import_locked_csv(recovery_upload, workspace_id)
        if ok:
            st.success(f'{message} {t("rows")}: {count}')
        else:
            st.error(message)

snapshot = store_snapshot(workspace_id)
st.dataframe(display_frame(snapshot), use_container_width=True, hide_index=True)

if not github_store_enabled():
    st.warning(t('missing_github'))
elif not snapshot.empty and snapshot.get('github_rows', 0).sum() == 0:
    st.warning(t('no_github_rows'))
elif not snapshot.empty and snapshot.get('github_rows', 0).sum() > 0:
    st.success(t('has_github_rows'))

if not snapshot.empty and snapshot['loaded_rows'].sum() == 0 and snapshot['disk_rows'].sum() == 0 and snapshot['backup_rows'].sum() == 0 and snapshot.get('github_rows', 0).sum() == 0:
    st.warning(t('no_rows'))
elif not snapshot.empty:
    st.success(t('readable'))
