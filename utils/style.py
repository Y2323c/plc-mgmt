import streamlit as st


def apply_style() -> None:
    """全ページ共通スタイル（モダン・シンプル）"""
    st.markdown(
        """
        <style>
        /* ── Google Fonts: Inter ── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

        html, body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont,
                         'Helvetica Neue', sans-serif !important;
        }

        /* テキスト要素のみにInterを適用（アイコンspanを除外） */
        p, h1, h2, h3, h4, h5, h6,
        label, li, td, th, input, textarea, select,
        [data-testid="stMarkdownContainer"],
        [data-testid="stText"],
        .stTextInput input,
        .stSelectbox,
        .stRadio label,
        .stCheckbox label {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont,
                         'Helvetica Neue', sans-serif !important;
        }

        /* ── ページタイトル (h1) ── */
        h1 {
            font-size: 1.35rem !important;
            font-weight: 600 !important;
            letter-spacing: -0.01em !important;
            color: #111827 !important;
            padding-bottom: 0.25rem !important;
        }

        /* ── セクションタイトル (h2) ── */
        h2 {
            font-size: 1.0rem !important;
            font-weight: 500 !important;
            color: #374151 !important;
        }

        /* ── サブ見出し (h3) ── */
        h3 {
            font-size: 0.88rem !important;
            font-weight: 500 !important;
            color: #4b5563 !important;
        }

        /* ── 本文・ラベル ── */
        p, label, div, span, li {
            font-size: 0.855rem !important;
        }

        /* ── メインコンテナ余白 ── */
        .main .block-container {
            padding-top: 1.4rem !important;
            padding-bottom: 2rem !important;
            max-width: 1080px !important;
        }

        /* ── サイドバー ── */
        [data-testid="stSidebar"] {
            background-color: #f9fafb !important;
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            font-size: 0.88rem !important;
            font-weight: 600 !important;
            color: #374151 !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        /* ── ボタン ── */
        button[kind="primary"] {
            background-color: #111827 !important;
            border: none !important;
            border-radius: 6px !important;
            font-size: 0.82rem !important;
            font-weight: 500 !important;
            padding: 0.4rem 1.1rem !important;
        }
        button[kind="secondary"], .stButton > button {
            border-radius: 6px !important;
            font-size: 0.82rem !important;
            font-weight: 400 !important;
            border: 1px solid #d1d5db !important;
            background-color: #fff !important;
            color: #374151 !important;
        }
        button:hover {
            opacity: 0.85 !important;
        }

        /* ── インプット・セレクトボックス ── */
        input, textarea, select,
        [data-baseweb="input"] input,
        [data-baseweb="select"] {
            font-size: 0.855rem !important;
            border-radius: 6px !important;
        }

        /* ── メトリクス ── */
        [data-testid="metric-container"] {
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.6rem 1rem !important;
        }
        [data-testid="metric-container"] label {
            font-size: 0.72rem !important;
            color: #6b7280 !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        [data-testid="metric-container"] [data-testid="stMetricValue"] {
            font-size: 1.05rem !important;
            font-weight: 600 !important;
            color: #111827 !important;
        }

        /* ── 区切り線 ── */
        hr {
            margin: 0.6rem 0 !important;
            border-color: #e5e7eb !important;
            border-width: 1px 0 0 !important;
        }

        /* ── データフレーム ── */
        [data-testid="stDataFrame"] {
            border-radius: 8px !important;
            overflow: hidden !important;
            font-size: 0.83rem !important;
        }

        /* ── タブ ── */
        .stTabs [role="tab"] {
            font-size: 0.83rem !important;
            font-weight: 500 !important;
            padding: 0.35rem 0.9rem !important;
        }
        .stTabs [role="tab"][aria-selected="true"] {
            color: #111827 !important;
            border-bottom-color: #111827 !important;
        }

        /* ── キャプション ── */
        [data-testid="stCaptionContainer"] p {
            font-size: 0.77rem !important;
            color: #9ca3af !important;
        }

        /* ── info / warning / success バナー ── */
        [data-testid="stAlert"] {
            border-radius: 6px !important;
            font-size: 0.83rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
