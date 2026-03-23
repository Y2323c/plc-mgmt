import os
import pandas as pd
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

files = [
    ("01supabase_users_master.csv",     "users_master"),
    ("02supabase_name_mappings.csv",    "name_mappings"),
    ("03supabase_event_logs.csv",       "event_logs"),
    ("04supabase_coaching_tickets.csv", "coaching_tickets"),
    ("05supabase_coaching_logs.csv",    "coaching_logs"),
]

for filename, table in files:
    path = os.path.join(DATA_DIR, filename)
    # encoding='utf-8-sig' で BOM を除去（02〜05 に BOM あり）
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
    df = df.where(pd.notnull(df), None)  # NaN → None

    # event_logs は CSV に id 列がないのでそのまま、他は id を含む
    # id カラムがある場合、重複を除去（先頭を優先）
    if "id" in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset="id", keep="first")
        dropped = before - len(df)
        if dropped:
            print(f"  ⚠ {filename}: 重複ID {dropped} 件を除去")

    # "3.0" のような float 表記の整数を "3" に変換
    def fix_value(v):
        if isinstance(v, str) and v.endswith(".0") and v[:-2].lstrip("-").isdigit():
            return str(int(float(v)))
        return v

    rows = [{k: fix_value(v) for k, v in row.items()} for row in df.to_dict(orient="records")]

    chunk = 500
    inserted = 0
    for i in range(0, len(rows), chunk):
        supabase.table(table).insert(rows[i:i+chunk]).execute()
        inserted += len(rows[i:i+chunk])

    print(f"✓ {table}: {inserted} 行 挿入完了")

print("\n全テーブルの挿入が完了しました。")
