from __future__ import annotations


def is_spanish(language: str | None) -> bool:
    return str(language or "").strip().lower().startswith("es")


def tr(language: str | None, english: str, spanish: str) -> str:
    return spanish if is_spanish(language) else english


def upload_helper(language: str | None) -> str:
    return tr(language, "Upload control text may be controlled by Streamlit.", "El botón interno de carga puede aparecer en inglés por Streamlit.")
