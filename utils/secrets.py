"""
環境変数の取得ヘルパー。
- ローカル: .env から load_dotenv() で読み込み
- Streamlit Cloud: st.secrets から読み込み
"""
import os
from dotenv import load_dotenv

load_dotenv()


def get_secret(key: str) -> str:
    """
    Streamlit Cloud の st.secrets を優先し、なければ環境変数から取得する。
    どちらにもない場合は空文字を返す。
    """
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return str(val)
    except Exception:
        # secrets.toml が存在しない場合（ローカル）や
        # StreamlitSecretNotFoundError なども含めてスキップし .env にフォールバック
        pass
    return os.environ.get(key, "")
