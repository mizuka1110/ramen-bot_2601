# LINE ラーメン検索 Bot（現状仕様）

この README は、**現在の実装コードに合わせた仕様書**です。
（要件メモではなく、2026-04-13 時点の挙動ベース）

## 1. 概要

本アプリは、LINE Messaging API を入口にして、ユーザーが送った位置情報をもとに近隣のラーメン店を検索・ランキングし、Flex Message で返す FastAPI サーバです。

- 店舗検索: Google Places API（Nearby Search / Place Details / Photo）
- 要約・カテゴリ抽出: OpenAI Responses API（`gpt-4o-mini`）
- 嗜好保存: PostgreSQL（`user_preferences` テーブル）
- UI補助: LIFF ページ（好み登録・日時指定）

## 2. 主要機能

### 2.1 LINE Webhook

- エンドポイント: `POST /line/webhook`
- 受信イベント:
  - テキストメッセージ
  - 位置情報メッセージ
  - ポストバック（「おかわり」「好み登録」系）
- GET 疎通確認: `GET /line/webhook` -> `{ "status": "ok" }`

### 2.2 テキスト入力時の挙動

主なキーワードと動作:

- 「今すぐ検索」「ラーメン」を含む:
  - 即時検索モードに入り、位置情報 Quick Reply を返す
- 「日時・場所を指定」または「場所・日時を指定」を含む:
  - 日時指定 LIFF への導線 Flex を返す
- `日時指定:YYYY-MM-DDTHH:MM` 形式:
  - サーバ内セッションに日時を保存し、位置情報送信を促す
- 「好み」を含む:
  - 好み登録 LIFF（固定URL）への導線 Flex を返す

### 2.3 位置情報入力時の検索フロー

位置情報受信時は `search_ramen_items` を実行します。

1. 検索半径を `1000m -> 2000m -> 3000m` と段階的に拡張
2. Places 結果を重複排除して候補を収集
3. 各候補の Place Details から口コミ/営業時間を取得（並列）
4. OpenAI で以下を付与
   - 高評価口コミの短文要約
   - ラーメンカテゴリ mention 数抽出
5. ユーザー嗜好（weights）を使ってスコアリングし並び替え
6. 先頭 10 件を Flex カルーセルで返信

補足:

- 結果が 10 件を超える場合は「おかわり」ボタン（postback）を返す
- 日時指定モード時は営業情報注記を付与し、同時刻で別地点検索の Quick Reply を返す
- 半径 2000m 以上に広げた場合は「検索半径を広げた」旨のメッセージを追加

### 2.4 おかわり（ページング）

- postback data: `ramen:more:{offset}`
- サーバメモリ上の検索セッションを参照して次ページ（10件）を返却
- 2ページ目は、初回でプリフェッチ済みデータがあればそれを優先利用

### 2.5 好み登録

#### A. LINE内 Flex UI（postback）

- `pref:menu` でカテゴリ一覧
- `pref:category:{category}` で選択肢表示
- `pref:set:{category}:{choice}` で保存

choice と重み:

- `like`: `0.075`
- `love`: `0.15`
- `addict`: `1.0`
- `dislike`: `-0.075`

カテゴリ（12種）:

- つけ麺 / まぜそば / 魚介 / 煮干し / 鶏白湯 / 豚骨 / 醤油 / 味噌 / 塩 / 辛い / 家系 / 二郎系

#### B. LIFF ページ + API

- LIFF 画面: `GET /preferences`（`app/static/preferences.html`）
- 保存 API: `POST /api/preferences`
- 取得 API: `GET /api/preferences?user_id=...`

### 2.6 日時指定検索（LIFF）

- ページ: `app/static/datetime.html`
- LIFF から `日時指定:...` テキストを LINE トークへ送信
- サーバは `opening_hours.periods` を解析して「指定時刻に営業中/時間外」を判定
- カルーセルで営業時間（当日分テキスト）を表示可能

## 3. ランキング仕様（実装ベース・詳細）

このセクションは `app/services/ranking.py` の実装ロジックを、そのまま仕様として読めるように整理したものです。

### 3.1 まず何で並べるか（営業状態の優先）

検索モードで優先キーが変わります。

- 通常検索（現在時刻ベース / `prioritize_open_now_status=True`）
  1. `open_now` の優先度
     - `True`（営業中） -> 最優先
     - `None`（不明） -> 次点
     - `False`（営業時間外） -> 最後
  2. 上記が同じなら `total_score` 降順

- 日時指定検索（`prioritize_open_now_status=False`）
  1. 「実効的に営業中か」を優先
     - `open_at_search_time` が bool のときはそれを採用
     - それ以外（未判定など）は `open_now is True` を代替採用
  2. 営業中グループ内 / 非営業グループ内で `total_score` 降順

### 3.2 総合スコア `total_score` の式

スコアは次式です。

```text
total_score = rating + preference_score + addict_bonus + review_penalty
```

- `rating`
  - Places の店舗評価（未取得時は `0`）
- `preference_score`
  - ユーザー嗜好（weights）とカテゴリ言及数から算出
- `addict_bonus`
  - 「中毒（weight >= 1.0）」カテゴリに対する追加ボーナス
  - 口コミカテゴリと店名が一致した場合の小さな店名一致ボーナスを含む
- `review_penalty`
  - 口コミ件数（`rating_count`）が少ない店舗への控えめな減点

### 3.3 口コミ件数ペナルティ `review_penalty`

`rating_count` による段階減点です。

- 100件以上: `0`
- 75〜99件: `-0.1`
- 50〜74件: `-0.2`
- 25〜49件: `-0.3`
- 24件以下: `-0.5`

### 3.4 嗜好スコア `preference_score` / 中毒ボーナス `addict_bonus`

#### A. 通常系（`category_mentions` が dict である場合）

OpenAI が抽出したカテゴリ mention 数（正の整数のみ採用）を使います。

- `weight < 1.0` のカテゴリ:
  - `preference_score += weight * mention_count`
- `weight >= 1.0`（中毒）のカテゴリ:
  - `preference_score` には加算しない
  - 代わりに `addict_bonus` に下記を加算
    - mention_count <= 1 : `+1.05`
    - mention_count <= 3 : `+1.15`
    - mention_count >= 4 : `+1.3`

> 補足: 中毒カテゴリは「線形加点（weight * count）」ではなく、専用ボーナスで強めに効かせる設計です。

#### C. 店名一致ボーナス（小）

カテゴリシグナルがある場合のみ、店名との一致で `addict_bonus` に小加点します。

- 正の重み（`weight > 0`）カテゴリのみ対象
- `weight >= 1.0`（中毒）: `+0.2`
- それ以外の正の重み: `+0.08`
- 合計上限: `+0.3`
- 表記ゆれ対応例:
  - `塩` / `しおそば` / `しおラーメン`（※ `しお` 単独は誤検知回避のため対象外）
  - `醤油` / `しょうゆ`
  - `味噌` / `みそ`
  - `つけ麺` / `つけめん` / `つけそば`
  - `煮干し` / `にぼし`
  - `二郎系` は店名中の `二郎` も一致扱い

#### B. フォールバック系（`category_mentions` が dict でない場合）

旧データ等で mention 辞書が無い場合、`categories` 配列を使って簡易計算します。

- `preference_score = Σ weights[category]`
- `addict_bonus = 1.05`（`weights[category] >= 1.0` が1つでもあれば）

### 3.5 同点時の扱い

Python の `sorted()` は安定ソートのため、

- 優先キー（営業状態）と `total_score` が完全同値の要素同士は、
- ソート前の順序（= 収集順）を保持します。

### 3.6 実運用上の見え方（要点）

- まず「営業中（または指定時刻営業中）」が上に来る。
- その中で、`rating` を基礎点に「嗜好一致」と「中毒ボーナス」が上乗せされる。
- ただし口コミ件数が極端に少ない店は、最大 `-0.5` の減点で少し抑制される。

### 3.7 非ラーメン店の除外（口コミ必須）

`app/services/ramen_search.py::_should_exclude_non_ramen_shop` で、候補店の除外判定を行います。

- 口コミ本文（`reviews[].text`）の中に、ラーメン関連キーワードが1件でもあれば通過
- **口コミ本文にラーメン関連キーワードが1件も無い場合は除外**
- そのうえで、店名 / type / 概要などに明確な非ラーメンシグナルがあれば除外

## 4. API 一覧

### 4.1 業務API

- `POST /line/webhook` : LINE イベント受信
- `GET /line/webhook` : webhook ヘルス
- `GET /shops/search?lat=...&lng=...&q=...&radius=...` : 周辺検索（内部利用・デバッグ向け）
- `GET /shops/photo?ref=...&maxwidth=...` : Google Photo のプロキシ
- `GET /preferences` : 好み登録 LIFF ページ配信
- `POST /api/preferences` : 好み保存
- `GET /api/preferences?user_id=...` : 好み取得

### 4.2 運用・デバッグAPI

- `POST /debug/push?lat=...&lng=...` : 指定ユーザーへテスト Push
- `GET /health` : アプリヘルス
- `GET /health/db` : DBヘルス

## 5. データ仕様

### 5.1 DB テーブル

`user_preferences` テーブルを利用します。

想定カラム:

- `line_user_id` (text, PK)
- `weights` (jsonb)
- `updated_at` (timestamp)

※ アプリ起動時に自動マイグレーションは実装されていないため、事前にテーブル作成が必要です。

## 6. 環境変数

必須（主に本番運用で必要）:

- `LINE_CHANNEL_ACCESS_TOKEN`
- `PLACES_API_KEY`
- `OPENAI_API_KEY`
- `PUBLIC_BASE_URL`（画像URL/Flex内リンク生成）

DB 接続系（優先順）:

1. `SUPABASE_DB_URL`
2. `DATABASE_URL`
3. `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD`

任意:

- `DATETIME_LIFF_ID`（未設定時デフォルトあり）
- `DATETIME_LIFF_URL`
- `ENV`（`.env.{ENV}` を読み込み。未指定は `development`）
- `LINE_USER_ID`（`/debug/push` 用）

## 7. ローカル実行

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

または Docker:

```bash
docker compose up --build
```

`docker-compose.yml` は `api:8000` を公開し、`.env.development` を読み込みます。

## 8. 現状の制約 / 注意点

- ユーザー状態・検索セッションは**プロセスメモリ保持**（再起動で消える）
- Webhook 署名検証は未実装（リクエストJSONを直接処理）
- LIFF URL の一部はコード内固定値
- OpenAI/Places の失敗時は、可能な範囲でフォールバックして返信

---

必要であれば次のステップで、
- 「運用手順書（デプロイ手順）」
- 「DB 初期化 SQL」
- 「LINE Developers 側の設定手順」
まで README に追記できます。
