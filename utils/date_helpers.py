import re
from datetime import date, datetime


def parse_date(val: str | None) -> date | None:
    """文字列を date に変換。YYYY/MM/DD・YYYY/MM・日本語形式に対応。
    変換できない場合は None を返す。"""
    if not val:
        return None
    for fmt in ("%Y/%m/%d", "%Y/%m"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            pass
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", val)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"(\d{4})年(\d{1,2})月", val)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    return None
