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
apply_style()

# 公開アプリ専用: サイドバー・ツールバー・フッターを非表示
st.markdown(
    """
    <style>
    /* サイドバー本体と開閉ボタンを非表示 */
    [data-testid="stSidebar"]        { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    /* 右下の Manage app ボタン（ツールバー）を非表示 */
    [data-testid="stToolbar"]        { display: none !important; }
    #MainMenu                        { visibility: hidden !important; }
    footer                           { visibility: hidden !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

pg = st.navigation([
    st.Page("pages/08_アンケート.py", title="出欠アンケート — 回答フォーム"),          # / でアクセス
    st.Page("pages/06_出席管理.py",   title="出席管理 — チェックイン", url_path="checkin"),  # /checkin でアクセス
])
pg.run()
