"""
環境変数の取得ヘルパー。
- ローカル: .env から load_dotenv() で読み込み
- Streamlit Cloud: st.secrets から読み込み
"""
import os
from dotenv import load_dotenv

load_dotenv()


def get_secret(key: str) -> str:
    # Streamlit Cloud の secrets を優先
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    # ローカルの環境変数にフォールバック
    return os.environ.get(key, "")
