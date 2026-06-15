from __future__ import annotations

import streamlit as st

_REAL_FILE_UPLOADER = st.file_uploader


def mobile_safe_file_uploader(label, *args, **kwargs):
    label_text = str(label).lower()
    if "memory" in label_text or "ara" in label_text:
        kwargs["type"] = None
        kwargs["accept_multiple_files"] = False
        if kwargs.get("key") == "ara_memory_csv_upload":
            kwargs["key"] = "ara_memory_mobile_safe_upload_v7"
        kwargs["help"] = "Mobile-safe uploader. Accepts any file type; choose your CSV file."
    return _REAL_FILE_UPLOADER(label, *args, **kwargs)


st.file_uploader = mobile_safe_file_uploader
st.caption("Upload fix build: mobile-safe-uploader-v7")

import pages.pro_predictor  # noqa: F401,E402
