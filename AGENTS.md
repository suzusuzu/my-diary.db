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
└── .gitattributes # diary.db を binary 扱いにする設定
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
4. `datetime` は指示がない限り、操作時点のローカル時刻をISO8601形式で入れる。
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

## 5. スキーマを変更する場合

`entries` にカラムを追加するなど破壊的でない変更は `ALTER TABLE` で行い、
`schema.sql` も同時に更新して差分をコミットする。
破壊的な変更（列の削除・型変更など）を行う場合は、
事前に `diary.db` 全体をバックアップ（例: `cp diary.db diary.db.bak`）してから作業する。
