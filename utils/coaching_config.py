# ── リマインドスケジュール ────────────────────────────────────────────────
# day    : 基準日からの経過日数（この日に送信）
# months : メッセージ内の「〇ヶ月」
# session: まだ実施されていないと判定するセッション番号

REMINDERS = {
    "新規コーチング": [
        {"day": 140, "months": 5,  "session": 5},
        {"day": 230, "months": 8,  "session": 6},
        {"day": 320, "months": 11, "session": 7},
    ],
    "継続コーチング": [
        {"day":  80, "months": 3, "session": 1},
        {"day": 230, "months": 8, "session": 2},
    ],
    "救済コーチング": [
        {"day":  80, "months": 3, "session": 1},
        {"day": 230, "months": 8, "session": 2},
    ],
    "追加コーチング": [
        {"day":  80, "months": 3, "session": 1},
        {"day": 230, "months": 8, "session": 2},
    ],
}


def _cw_mention(name: str, account_id: str | None, suffix: str = "") -> str:
    """Chatwork メンション文字列を生成する。IDがあれば [To:ID] 形式、なければテキストのみ。"""
    if account_id:
        return f"[To:{account_id}]{name}{suffix}"
    return f"{name}{suffix}"


def build_reminder_message(coaching_type: str, months: int, session_num: int,
                           member_name: str, coach_name: str,
                           member_account_id: str | None = None,
                           coach_account_id: str | None = None) -> str:
    """リマインドメッセージ本文を生成する。"""
    base = (
        _cw_mention(coach_name, coach_account_id, suffix="さん") + "\n"
        + _cw_mention(member_name, member_account_id, suffix="さん") + "\n"
    )
    if coaching_type == "新規コーチング":
        return (
            base
            + f"あと10日で入会{months}ヶ月を迎えます。\n"
            + f"{session_num}回目のコーチングの日時の調整をお願いいたします。"
        )
    elif coaching_type == "救済コーチング":
        return (
            base
            + f"{session_num}回目のコーチングの日時の調整をお願いいたします。"
        )
    elif coaching_type == "追加コーチング":
        return (
            base
            + f"あと10日で追加{months}ヶ月を迎えます。\n"
            + f"{session_num}回目のコーチングの日時の調整をお願いいたします。\n"
            + "ローンチの状況に合わせて、2ヶ月以内を目安にコーチングを行なってください。"
        )
    else:  # 継続コーチング
        return (
            base
            + f"あと10日で継続{months}ヶ月を迎えます。\n"
            + f"{session_num}回目のコーチングの日時の調整をお願いいたします。\n"
            + "ローンチの状況に合わせて、2ヶ月以内を目安にコーチングを行なってください。"
        )
