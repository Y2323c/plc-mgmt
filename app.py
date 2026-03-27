import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from utils.style import apply_style

st.set_page_config(page_title="PLC 管理ツール", page_icon="📋", layout="wide")
apply_style()

pg = st.navigation([
    st.Page("pages/01_会員管理.py",         title="会員管理 — 追加・修正・削除",                  icon="⚫"),
    st.Page("pages/07_受講生ログ.py",        title="受講生ログ — 全履歴確認",                      icon="⚫"),
    st.Page("pages/05_イベント管理.py",       title="イベント管理 — WS・チーム登録",                icon="⚫"),
    st.Page("pages/09_アンケート配信.py",     title="出欠アンケート配信 — URL生成・送付",           icon="⚫"),
    st.Page("pages/08_アンケート.py",         title="出欠アンケート個別登録 — 事務局入力用",        icon="⚫"),
    st.Page("pages/06_出席管理.py",           title="出席管理 — 状況確認、出欠状況の更新（当日）", icon="⚫"),
    st.Page("pages/02_コンサル記録.py",       title="コンサル記録 — 個別・10分 実施記録",          icon="⚫"),
    st.Page("pages/03_コーチングチケット.py", title="コーチングチケット — 設定",                   icon="⚫"),
    st.Page("pages/04_コーチング記録.py",     title="コーチング記録 — 実施記録",                   icon="⚫"),
    st.Page("pages/12_コーチング進捗.py",     title="コーチング進捗 — セッション状況確認",         icon="⚫"),
])
pg.run()
