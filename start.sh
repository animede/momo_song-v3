#!/bin/bash

# Momo Song v3 起動スクリプト

echo "Momo Song v3 を起動しています..."

# 仮想環境の確認
if [ ! -d "venv" ]; then
    echo "仮想環境を作成しています..."
    python3 -m venv venv
fi

# 仮想環境の有効化
source venv/bin/activate

# 依存関係のインストール
echo "依存関係をインストールしています..."
pip install -r requirements.txt

# サーバーの起動
echo "サーバーを起動しています..."
echo "ブラウザで http://localhost:64653 にアクセスしてください"
python music_server.py
