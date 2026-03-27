import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from utils.style import apply_style

st.set_page_config(
    page_title="PLC",
    page_icon="●",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_style(public_mode=True)

pg = st.navigation([
    st.Page("pages/08_アンケート.py",     title="出欠アンケート — 回答フォーム"),                                    # /
    st.Page("pages/06_出席管理.py",       title="出席管理 — チェックイン",           url_path="checkin"),          # /checkin
    st.Page("pages/11_コーチング入力.py", title="コーチング記録 — 入力フォーム",     url_path="coaching"),         # /coaching
    st.Page("pages/12_コーチング進捗.py", title="コーチング進捗 — セッション状況確認", url_path="coaching_status"), # /coaching_status
])
pg.run()
