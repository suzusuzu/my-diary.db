# 日記/メモDB 仕様書 (AGENTS.md)

このリポジトリは、日常の出来事を記録する日記/メモをSQLiteデータベース
(`diary.db`) にそのまま保存し、GitHubで管理するためのものです。
DBへの読み書きは人間が直接行わず、coding agent（Claude Codeなど）経由で行います。

> **記録の単位について:** 記録は「1日単位」ではなく「その時その時」の単位で行う。
> 同じ日に何件でも、それぞれ独立した1レコードとして `datetime`（その瞬間の
> 日時）と `memo` を保存する。1日分をまとめた長いメモを1レコードに入れるのではなく、
> 起きた出来事・思ったことのたびに、その時刻のレコードを追加していく。

---

## 1. リポジトリ構成

```
.
├── AGENTS.md      # agent向け操作仕様（このファイル）
├── diary.db       # 本体のSQLite DB（バイナリのままコミットする）
├── schema.sql     # 初期化・再構築用のスキーマ定義
├── .gitattributes # diary.db を binary 扱いにする設定
├── .gitignore     # .venv/ を除外
├── setup-hooks.sh # 新マシンで hooks を有効化する（core.hooksPath=git-hooks）
├── git-hooks/     # pre-commit フック
├── tools/         # export_csv.py / jst_now.py 等の補助スクリプト
└── diary_human_readable_DO_NOT_EDIT.csv  # 可視化用CSV（pre-commitで自動生成・編集禁止）
```

`diary.db` が存在しない場合は次のコマンドで作成する。

```bash
sqlite3 diary.db < schema.sql
```

`.gitattributes` の内容（バイナリ扱いにしてdiffノイズを防ぐ）:

```
diary.db binary
diary.db.bak binary
```

---

## 2. データベース仕様

### テーブル: `entries`

```sql
CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  datetime DATETIME NOT NULL,
  memo TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entries_datetime ON entries (datetime);
```

| カラム   | 型       | 説明                                                        |
|----------|----------|-------------------------------------------------------------|
| id       | INTEGER  | PRIMARY KEY AUTOINCREMENT                                    |
| datetime | DATETIME | ISO8601形式の文字列で格納。例: `2026-08-15T21:30:00+09:00`   |
| memo     | TEXT     | 本文。改行を含んでよい                                       |

> **補足（DATETIME型について）:** SQLiteには真の`DATETIME`ストレージ型は
> 存在せず、`DATETIME`と宣言するとNUMERIC affinityが付与される。
> ISO8601文字列は数値に変換できないため、実際にはTEXTとして保存される
> （動作自体はTEXT宣言時と同じ）。それでも`DATETIME`と宣言しておくことで、
> スキーマを見たときに「日時を表す列」だと分かりやすくなり、
> `date()`/`datetime()`/`strftime()`といったSQLiteの日時関数で扱うことを
> 想定した列であることが明示される。値は必ずISO8601形式
> （`YYYY-MM-DDTHH:MM:SS±HH:MM`）で入れること。

---

## 3. Agentへの操作指示

### 共通ルール

1. 作業開始前に必ず `git pull` して最新の `diary.db` を取得する。
   複数人・複数エージェントが同時に別ブランチで `diary.db` を編集すると
   バイナリファイルのためマージができず、片方の変更が失われる。
   常に「pull → 操作 → commit → push」を1セットとして直列に行う。
2. DB操作は原則 `sqlite3` CLI を使う。破壊的な操作（UPDATE/DELETE）の前には
   対象レコードを `SELECT` して内容を確認してから実行する。
3. 操作が終わったら `diary.db` の変更を含めて commit する。
   コミットメッセージは日付や内容が分かる形にする。
   例: `diary: 2026-08-15 のメモを追加`
4. `datetime` は指示がない限り、操作時点の JST をISO8601形式で入れる。
   「今」は必ず `python3 tools/jst_now.py` で取得する（詳しくは §5）。
5. `memo` にシングルクォートが含まれる場合はSQLエスケープ（`''`）するか、
   `sqlite3` の `-cmd` やヒアドキュメント経由でパラメータ化して安全に渡す。

### 追加（新しいメモ/日記を記録する）

```bash
sqlite3 diary.db "INSERT INTO entries (datetime, memo) VALUES ('2026-08-15T21:00:00+09:00', 'メモ内容');"
git add diary.db
git commit -m "diary: 2026-08-15 のメモを追加"
git push
```

### 一覧・検索

```bash
# 新しい順に全件表示
sqlite3 -header -column diary.db "SELECT * FROM entries ORDER BY datetime DESC;"

# キーワード検索
sqlite3 -header -column diary.db "SELECT * FROM entries WHERE memo LIKE '%キーワード%' ORDER BY datetime DESC;"

# 期間指定
sqlite3 -header -column diary.db "SELECT * FROM entries WHERE datetime BETWEEN '2026-08-01' AND '2026-08-31' ORDER BY datetime;"
```

### 更新・削除

事前に対象を確認してから実行すること。

```bash
# 確認
sqlite3 -header -column diary.db "SELECT * FROM entries WHERE id = 5;"

# 更新
sqlite3 diary.db "UPDATE entries SET memo = '修正後の内容' WHERE id = 5;"

# 削除
sqlite3 diary.db "DELETE FROM entries WHERE id = 5;"

git add diary.db
git commit -m "diary: id=5 を更新（または削除）"
git push
```

### 文章の推敲・修正

記録済みの `memo` の文章を読みやすく推敲・修正してほしいという指示が
来た場合は、以下の方針で対応する。

- 内容・事実はそのままに、文章の推敲・補完・修正を行う（例: 語句の補完、
  文の整理、読点の調整、明示的な列挙、自然な言い回しへの変更）。
- 意味を変えない範囲で、読みやすく自然な日本語に整える。
  必要に応じて文を補完して明確化してよいが、事実と異なる情報を
  勝手に書き足さない。
- 修正は必ず DB に対して `UPDATE` で行い、`datetime` は変更しない
  （その瞬間の記録であるため、記録時刻はそのまま保つ）。
- 修正前後を確認するため、`UPDATE` の前に `SELECT` で対象レコードを
  確認し、実行後にも修正後の `memo` を `SELECT` で確認する。
- コミットメッセージは「推敲・修正した」ことが分かる形にする。
  例: `diary: id=2 のメモを読みやすく修正`

```bash
# 確認
sqlite3 -header -column diary.db "SELECT id, memo FROM entries WHERE id = 2;"

# 修正
sqlite3 diary.db "UPDATE entries SET memo = '推敲後の内容' WHERE id = 2;"

# 修正後確認
sqlite3 -header -column diary.db "SELECT id, memo FROM entries WHERE id = 2;"

git add diary.db
git commit -m "diary: id=2 のメモを読みやすく修正"
git push
```

---

## 4. 変更履歴の確認について

`diary.db` はバイナリのため `git diff` / `git log -p` では中身の差分は見えない。
過去の内容を確認したい場合は、該当コミットをチェックアウトするか
`git show <commit>:diary.db` で当時のファイルを取り出し、
別名で保存してから `sqlite3` で中身を見る。

```bash
git show abc1234:diary.db > /tmp/diary_old.db
sqlite3 -header -column /tmp/diary_old.db "SELECT * FROM entries;"
```

---

## 5. 日時は常に JST（日本標準時）

システムは UTC なので `date` や `datetime('now','localtime')` は JST にならない。
常に JST で記録すること。

- 「今」の時刻が必要なときは必ず `python3 tools/jst_now.py` で取得する。
  （ISO8601 + `+09:00` 形式で出力される）
- `datetime` は必ず JST の ISO8601 形式 `YYYY-MM-DDTHH:MM:SS+09:00` で書く。
- 手動で日時を指定する場合も、先に `tools/jst_now.py` で現在 JST を確認してから書く。
- 書き込み後は必ず `SELECT id, datetime FROM entries WHERE id=<id>;` で
  投入した時刻が JST（UTC の +9）になっていることを確認する。

## 6. git hooks（他マシンで有効化）

このリポジトリは `core.hooksPath = git-hooks` でフック
（pre-commit: `tools/export_csv.py` で `diary_human_readable_DO_NOT_EDIT.csv` を
常に再生成）を参照する。

- `core.hooksPath` はローカル git config なのでクローンした他マシンには伝搬しない。
  新マシンでは一度 `./setup-hooks.sh` を実行して hooks を有効化する（venv も自動作成）。
- pre-commit は venv（`.venv/bin/python3`）があればそれを使い、無ければ python3 に
  フォールバックする。ツールが無い・失敗時は警告してスキップする（コミットは止めない）。
- `diary_human_readable_DO_NOT_EDIT.csv` は人間が読むための可視化用・参照用であり、
  編集・登録の対象にはしない。修正・削除・追加は必ず DB に対して行い、
  pre-commit が再生成する。

## 7. スキーマを変更する場合

`entries` にカラムを追加するなど破壊的でない変更は `ALTER TABLE` で行い、
`schema.sql` も同時に更新して差分をコミットする。
破壊的な変更（列の削除・型変更など）を行う場合は、
事前に `diary.db` 全体をバックアップ（例: `cp diary.db diary.db.bak`）してから作業する。
