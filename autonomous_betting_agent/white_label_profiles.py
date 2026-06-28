from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .report_product_layer import safe_text

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPO_ROOT / 'data' / 'white_label_profiles.json'
DEFAULT_DISCLAIMER_EN = 'Informational content only. Results are not guaranteed.'


def _normalized_disclaimer(value: Any) -> str:
    text = safe_text(value)
    return '' if text == DEFAULT_DISCLAIMER_EN else text


@dataclass
class WhiteLabelProfile:
    profile_id: str = 'default'
    workspace_id: str = 'test_01'
    brand_name: str = 'ABA Signal Pro'
    logo_url: str = ''
    tagline: str = 'Powered by Reparodynamics'
    language: str = 'en'
    report_title: str = 'Daily Sports Analysis'
    disclaimer: str = DEFAULT_DISCLAIMER_EN
    preferred_report_mode: str = 'Consumer Magazine'
    preferred_sports: list[str] | None = None
    risk_preference: str = 'Balanced'
    show_technical_fields: bool = False
    default_audience: str = 'consumer'
    export_preferences: dict[str, bool] | None = None
    delivery_settings: dict[str, Any] | None = None

    def normalized(self) -> 'WhiteLabelProfile':
        profile_id = normalize_id(self.profile_id or self.workspace_id or self.brand_name)
        return WhiteLabelProfile(
            profile_id=profile_id,
            workspace_id=normalize_id(self.workspace_id or profile_id),
            brand_name=safe_text(self.brand_name) or 'ABA Signal Pro',
            logo_url=safe_text(self.logo_url),
            tagline=safe_text(self.tagline) or 'Powered by Reparodynamics',
            language='es' if safe_text(self.language).lower().startswith('es') or 'español' in safe_text(self.language).lower() else 'en',
            report_title=safe_text(self.report_title) or 'Daily Sports Analysis',
            disclaimer=_normalized_disclaimer(self.disclaimer),
            preferred_report_mode=safe_text(self.preferred_report_mode) or 'Consumer Magazine',
            preferred_sports=list(self.preferred_sports or []),
            risk_preference=safe_text(self.risk_preference) or 'Balanced',
            show_technical_fields=bool(self.show_technical_fields),
            default_audience=safe_text(self.default_audience) or 'consumer',
            export_preferences=dict(self.export_preferences or {'html': True, 'pdf': True, 'markdown': True, 'json': True, 'csv': True}),
            delivery_settings=dict(self.delivery_settings or {'save_latest_feed': True, 'visibility': 'private'}),
        )


def normalize_id(value: Any) -> str:
    text = safe_text(value).lower() or 'default'
    return ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in text)[:80]


def _read_store(path: Path = PROFILE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {'profiles': {}}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {'profiles': {}}
    if not isinstance(payload, dict):
        return {'profiles': {}}
    if not isinstance(payload.get('profiles'), dict):
        payload['profiles'] = {}
    return payload


def _write_store(payload: dict[str, Any], path: Path = PROFILE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')


def list_profiles(path: Path = PROFILE_PATH) -> list[dict[str, Any]]:
    store = _read_store(path)
    return [dict(value) for value in store.get('profiles', {}).values() if isinstance(value, dict)]


def load_profile(profile_id: str = 'default', path: Path = PROFILE_PATH) -> WhiteLabelProfile:
    store = _read_store(path)
    data = store.get('profiles', {}).get(normalize_id(profile_id), {})
    if not isinstance(data, dict):
        data = {}
    return WhiteLabelProfile(**{k: v for k, v in data.items() if k in WhiteLabelProfile.__dataclass_fields__}).normalized()


def save_profile(profile: WhiteLabelProfile | dict[str, Any], path: Path = PROFILE_PATH) -> WhiteLabelProfile:
    if isinstance(profile, dict):
        profile = WhiteLabelProfile(**{k: v for k, v in profile.items() if k in WhiteLabelProfile.__dataclass_fields__})
    normalized = profile.normalized()
    store = _read_store(path)
    store.setdefault('profiles', {})[normalized.profile_id] = asdict(normalized)
    _write_store(store, path)
    return normalized


def delete_profile(profile_id: str, path: Path = PROFILE_PATH) -> bool:
    store = _read_store(path)
    profiles = store.setdefault('profiles', {})
    key = normalize_id(profile_id)
    existed = key in profiles
    profiles.pop(key, None)
    _write_store(store, path)
    return existed
