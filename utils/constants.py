"""アプリ全体で使う定数"""

ACTIVITY_TYPES   = ["プロデューサー", "コンテンツホルダー", "両方", "未定"]
CONSULT_TYPES    = ["個別", "10分"]
EVENT_CATEGORIES = ["WS", "チーム"]

# event_logs.status の表示ラベル（全パターン）
STATUS_LABELS = {0: "未回答", 1: "出席", 2: "欠席", 3: "参加予定", 4: "欠席予定"}

# 出席アンケート用
SURVEY_OPTIONS = {"参加予定": 3, "欠席予定": 4, "（未回答）": 0}
SURVEY_LABELS  = {3: "参加予定", 4: "欠席予定", 0: "（未回答）"}
