# LINEラーメン推薦Bot

## 1. 目的

スマホ利用を前提に、LINE上で  
**「現在地周辺のラーメン店」** を検索し、  
**ユーザーの過去対話から学習した嗜好を反映して、理由つきで候補を提案する。**

---

## 2. 対象ユーザー

- 外出中に、近くのラーメン店を**素早く決めたい**スマホユーザー  
- 好み（例：こってりが好き / 辛いのが苦手 など）を  
  **毎回説明したくない**ユーザー

---

## 3. ユースケース

- 「今いる場所の近くでラーメンを探したい」
- 「辛いのが苦手」「こってりが好き」など  
  **嗜好を踏まえた提案**がほしい
- 過去に伝えた嗜好を  
  **次回以降も自動的に反映**してほしい

---

## 4. 機能要件（MVP）

### 必須機能

#### 1) LINEでの対話

- **ユーザー入力**
  - テキスト（例：「ラーメン」）
  - 位置情報（現在地 or 地名）
- **Bot出力**
  - 候補3件を**カルーセル形式**で提示  
    - 店名  
    - 評価  
    - 営業時間  
    - おすすめ理由  
    - 地図リンク  

---

#### 2) 店舗検索（外部知識参照 / RAG要素）

- **Google Places API** を利用し、  
  「現在地周辺のラーメン店」を検索
- 取得する情報（例）
  - 店名
  - 住所
  - 評価
  - 営業時間
  - Place ID
  - 地図URL  
  - （必要に応じて写真）

---

#### 3) OpenAI APIの利用（APIサーバ経由）

- LINEクライアントから直接呼ばず、  
  **APIサーバ経由で OpenAI API を利用**
- 利用目的
  - 候補3件それぞれの  
    **「おすすめ理由」を生成**
  - ユーザー嗜好を踏まえた自然文生成

  ##### OpenAI 設定
- 使用モデル: gpt-4o-mini
- 環境変数: OPENAI_API_KEY を各自設定
- responses API を使用（openai>=2.x）

---

#### 4) 過去対話を踏まえた回答

- ユーザーの嗜好を **DBに永続化**
- 次回以降の提案に反映
- 例  
  - 「辛いのが苦手」  
    → 辛そうな候補を避ける、または注意書きを付与

---

#### 5) 嗜好の自動更新（+α）

- 会話内容から **嗜好タグを自動抽出**
- OpenAI API を使って **JSON形式で抽出**
- DBに保存・更新する
---

## 5. 非機能要件（最低限）

- **セキュリティ**
  - OpenAI APIキーはサーバ側で管理
  - クライアント（LINE）には露出しない
- **可用性 / 運用**
  - 小規模MVPとして安定稼働すればOK
  - 大規模スケールは対象外
- **コスト配慮（設計方針）**
  - Google Placesの検索結果は  
    **短期キャッシュ可能な構造**
  - （実装は任意）

---

## 6. ディレクトリ構成

```txt
├─ app/
│  ├─ main.py              # FastAPI起点
│  ├─ line/
│  │  ├─ webhook.py        # Webhook受信・署名検証
│  │  └─ messages.py       # テキスト / カルーセル定義
│  ├─ services/
│  │  ├─ places_cache.py   # places結果キャッシュ
│  │  ├─ ai_summary.py     # OpenAI（口コミ要約）
│  │  ├─ places.py         # Google Places API 呼び出し
│  │  ├─ llm.py            # OpenAI連携（生成・抽出）
│  │  └─ profile.py        # DB操作（user_profiles）
│  ├─ schemas.py           # Pydantic 定義（任意）
│  └─ config.py            # 環境変数管理
│
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
├─ .env.example
└─ README.md

## 6. ディレクトリ構成

### テーブル一覧

| テーブル名 | 目的 |
|---|---|
| `user_profiles` | LINEユーザーごとの嗜好（likes/dislikes/notes）と直近の検索条件を保持 |
```
---

### テーブル定義：`user_profiles`

| カラム名 | 型 | 制約 | 説明 |
|---|---|---|---|
| `line_user_id` | text | PRIMARY KEY | LINEのユーザーID |
| `prefs` | jsonb | NOT NULL | ユーザー嗜好データ（JSON） |
| `created_at` | timestamptz | NOT NULL | 作成日時 |
| `updated_at` | timestamptz | NOT NULL | 更新日時 |

---

### `prefs`（jsonb）キー定義

| キー | 型 | 説明 |
|---|---|---|
| `likes` | array[string] | 好きな傾向（例：豚骨、こってり、つけ麺） |
| `dislikes` | array[string] | 苦手な傾向（例：辛い、魚介強め） |
| `notes` | string | 補足（例：並ぶのが苦手、夜遅め希望） |
| `last_query` | string | 直近の検索ワード（例：ラーメン） |
| `last_location.lat` | number | 直近の緯度 |
| `last_location.lng` | number | 直近の経度 |

---

### `prefs` の例

```json
{
  "likes": ["豚骨", "こってり"],
  "dislikes": ["辛い", "魚介強め"],
  "notes": "並ぶのが苦手",
  "last_query": "ラーメン",
  "last_location": {
    "lat": 35.6812,
    "lng": 139.7671
  }
}