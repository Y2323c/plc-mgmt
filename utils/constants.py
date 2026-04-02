"""アプリ全体で使う定数"""

# ── イベントステータスコード（event_logs.status） ──
ST_NO_ANSWER = 0   # 未回答
ST_ATTENDED  = 1   # 出席（確定）
ST_ABSENT    = 2   # 欠席（確定）
ST_PLAN_IN   = 3   # 参加予定（アンケート回答）
ST_PLAN_OUT  = 4   # 欠席予定（アンケート回答）

# ── 管理ステータスコード（users_master.management_status） ──
MS_PP_OTHER  = 0   # PPほか
MS_ACTIVE    = 1   # 在籍
MS_PAUSED    = 2   # 休会
MS_LEFT      = 9   # 退会
MS_TO_DELETE = 99  # 削除予定

# ── カテゴリ名（event_logs.category） ──
CAT_WS      = "WS"
CAT_TEAM    = "チーム"
CAT_CONSULT = "コンサル"

# ── m_status カテゴリキー ──
M_STATUS_CAT_COACH         = "coach"
M_STATUS_CAT_COACHING_TYPE = "coaching_type"

# ── コーチングログ種別 ──
LOG_TYPE_SESSION = "session"
LOG_TYPE_MEMO    = "memo"

# ── コーチング種別ごとのデフォルト値 ──
COACHING_TYPE_DEFAULTS = {
    "新規コーチング": {"max_sessions": 7, "duration_months": 11},
    "継続コーチング": {"max_sessions": 2, "duration_months": 12},
    "追加コーチング": {"max_sessions": 4, "duration_months": 0},
    "救済コーチング": {"max_sessions": 2, "duration_months": 0},
}

# ── 選択肢リスト ──
ACTIVITY_TYPES   = ["プロデューサー", "コンテンツホルダー", "両方", "未定"]
CONSULT_TYPES    = ["個別", "10分"]
EVENT_CATEGORIES = [CAT_WS, CAT_TEAM]

# ── event_logs.status → 表示ラベル ──
STATUS_LABELS = {
    ST_NO_ANSWER: "未回答",
    ST_ATTENDED:  "出席",
    ST_ABSENT:    "欠席",
    ST_PLAN_IN:   "参加予定",
    ST_PLAN_OUT:  "欠席予定",
}

# ── アンケート画面用（ラベル → コード / コード → ラベル） ──
SURVEY_OPTIONS = {"参加予定": ST_PLAN_IN, "欠席予定": ST_PLAN_OUT, "（未回答）": ST_NO_ANSWER}
SURVEY_LABELS  = {ST_PLAN_IN: "参加予定", ST_PLAN_OUT: "欠席予定", ST_NO_ANSWER: "（未回答）"}

# ── 日付フォーマット ──
DATE_FMT_YM  = "%Y/%m"
DATE_FMT_YMD = "%Y/%m/%d"

# ── メッセージテンプレート ──
DEFAULT_WELCOME_TEMPLATE = "こんにちは。"

# ── Chatwork API ──
CHATWORK_API_BASE = "https://api.chatwork.com/v2"
CHATWORK_TIMEOUT  = 10  # 秒

# ── 公開アプリ ──
PUBLIC_APP_BASE_URL = "https://plc-mgmt-zndsegnd3csnyf48tnmzfb.streamlit.app"

# ── コーチング完了通知先（Chatwork グループ room_id）──
COACHING_COMPLETION_ROOM_ID = "402536772"
