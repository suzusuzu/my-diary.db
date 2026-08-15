#!/usr/bin/env python3
# diary.db を人が読みやすい CSV に書き出す（可視化用のみ）
# データの本体は diary.db（SQLite）。この CSV はあくまで人間が
# 読むための可視化用・参照用であり、編集・登録の対象にはしない。
# 修正・削除・追加は必ず DB に対して行い、pre-commit で再生成する。
import sqlite3, os, csv

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "..", "diary.db")
OUT = os.path.join(BASE, "..", "diary_human_readable_DO_NOT_EDIT.csv")

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute(
    "SELECT id, datetime, memo "
    "FROM entries ORDER BY datetime DESC, id DESC"
)
cols = [d[0] for d in cur.description]
rows = cur.fetchall()
conn.close()

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(cols)
    for r in rows:
        w.writerow(r)

print("saved:", OUT, f"({len(rows)} 件)")
