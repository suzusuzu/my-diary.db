#!/usr/bin/env python3
# 現在時刻を JST（日本標準時, UTC+9）の ISO8601 形式で出力する。
# サーバは UTC なので `date` や datetime('now') は JST とズレる。使わないこと。
# 「今」の日時が必要なときは必ずこのスクリプトで取得する。
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
print(datetime.now(JST).strftime("%Y-%m-%dT%H:%M:%S+09:00"))
