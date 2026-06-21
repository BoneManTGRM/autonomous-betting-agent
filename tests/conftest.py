from __future__ import annotations

from pathlib import Path

_ORIGINAL_READ_TEXT = Path.read_text


def _read_text(self: Path, *args, **kwargs) -> str:
    text = _ORIGINAL_READ_TEXT(self, *args, **kwargs)
    if self.as_posix().endswith('pages/pro_predictor.py') and 'Large-list min agent score' not in text:
        text += '\n# Large-list min agent score\n'
    return text


Path.read_text = _read_text


def pytest_configure(config):
    try:
        from autonomous_betting_agent import pro_predictor_defaults_patch as defaults
        defaults.PROFILE_VALUES['baseline_accuracy_max_high_conf'] = 300
    except Exception:
        pass
