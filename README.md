# Momo Song v3

音楽生成Webアプリケーション

## 機能

- AI による歌詞生成
- 音楽生成（[ACE-Step-directAPI](https://github.com/RetricSu/ACE-Step-direct) 使用）
- 画像生成（SDXL使用）
- 自動生成機能
- ボーカル版/インストゥルメンタル版の選択
- 生成パラメータの詳細設定

## セットアップ

1. 必要なパッケージのインストール：
```bash
pip install -r requirements.txt
```

2. 設定の確認：
- `music_server.py`内のAPIエンドポイントURLを環境に合わせて修正
- OpenAI API キーの設定

3. 外部API依存関係の設定：
- **ACE-Step-direct API**: 音楽生成用サーバー
- **SDXL API**: 画像生成用サーバー
- **OpenAI Compatible API**: 歌詞生成用サーバー

4. サーバーの起動：
```bash
python music_server.py
```

5. ブラウザで <http://localhost:64653> にアクセス

## ファイル構成

- `music_server.py`: FastAPIサーバー（メイン）
- `music.py`: 音楽生成ロジック
- `openai_chat.py`: OpenAI API ラッパー
- `create_image_world.py`: 画像生成ロジック
- `genre_tags.json`: ジャンルタグ設定
- `templates/index.html`: WebUI
- `static/`: CSS、画像ファイル

## 使用方法

1. テキストエリアに生成したい音楽のイメージを入力
2. 生成パラメータを調整（任意）
3. 「音楽生成」ボタンをクリック
4. 自動生成を有効にすると、一定時間操作がない場合に自動で新しい音楽を生成

## 主な機能

### 生成パラメータ
- タイトル、ジャンル、ムード、楽器の指定
- infer_step、guidance_scale、omega_scale の調整
- 画像サイズ（16:9/4:3）と向き（横/縦）の選択
- ボーカルあり/なしの選択

### 自動生成
- チェックボックスをONにすると即座に音楽生成を開始
- その後、60秒間操作がないと自動で新しい音楽を生成
- ユーザーが操作すると自動で無効化

## 注意事項

- 外部APIサーバーとの接続が必要
- 生成には時間がかかる場合があります

## 外部API依存関係

### 1. ACE-Step-direct API（音楽生成）

**リポジトリ:** [ACE-Step-direct](https://github.com/RetricSu/ACE-Step-direct)

**必要なエンドポイント:**
- 音楽生成API
- 歌詞から音楽への変換
- ボーカル/インストゥルメンタル対応

### 2. SDXL API（画像生成）

**必要なAPI仕様:**

**エンドポイント:** `POST /text2image`

**リクエスト形式:**
```json
{
  "prompt": "画像生成プロンプト",
  "width": 1296,
  "height": 728,
  "steps": 20,
  "cfg_scale": 7.0
}
```

**レスポンス形式:**
```json
{
  "images": ["base64_encoded_image_data"],
  "info": "generation_info"
}
```

**必要な機能:**
- テキストから画像生成（text2image）
- 複数解像度対応（16:9、4:3）
- カスタムプロンプト対応
- Base64エンコード画像出力

### 3. OpenAI Compatible API（歌詞生成）

**必要なエンドポイント:**
- `/v1/chat/completions`
- GPT-3.5/GPT-4互換API
- 非同期リクエスト対応

## 詳細ドキュメント

- [📚 詳細仕様・処理フロー](DOCUMENTATION.md) - アプリケーションの詳細機能説明と処理フロー
- [🔧 API リファレンス](API_REFERENCE.md) - APIエンドポイントと関数の詳細仕様
- [🚀 デプロイメントガイド](DEPLOYMENT.md) - 本番環境への導入手順とシステム設定

## ライセンス

MIT License
