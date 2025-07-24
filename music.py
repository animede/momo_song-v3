import json
import asyncio
import re
from textwrap import dedent
from openai_chat import chat_req,AsyncOpenAI
from create_image_world import create_image
import requests
import time

# グローバル変数：ACE-Step-directAPIの初期化状態をキャッシュ
_ace_initialized = False
_last_check_time = 0
_check_interval = 300  # 5分間は初期化状態をキャッシュ

#---------------- OpenAI API -----------------
a_client =AsyncOpenAI(
    #base_url="http://127.0.0.1:8080/v1",
    base_url="http://39.110.248.77:64652/v1", # 27B
    #base_url="http://39.110.248.77:64650/v1", # 27B
    api_key="YOUR_OPENAI_API_KEY",  # このままでOK
    )

#sdxl_url = 'http://0.0.0.0:64656'
sdxl_url = 'http://39.110.248.77:64656'

# ACE-Step-directAPI エンドポイント定数
ACE_API_BASE_URL = "http://0.0.0.0:8019"
ACE_API_ENDPOINT = f"{ACE_API_BASE_URL}/generate_music_direct"
ACE_API_INIT_ENDPOINT = f"{ACE_API_BASE_URL}/initialize"
ACE_API_STATUS_ENDPOINT = f"{ACE_API_BASE_URL}/status"


async def llm(user_msg):
    print("LLM")
    response_json = await chat_req(a_client, user_msg, "あなたは賢いAIです。userの要求や質問に正しく答えること")
    return {"message": response_json}

async def music_generation(user_input,genre_tags,previouse_title):
    print("=====>>>>>user_input=",user_input)
    request_song = dedent(f"""
        ユーザーの入力の意図を正確に判断して選択肢から選び、指定されたワードを返しなさい。選択肢->
        1) autoや、おまかせの場合の指定ワードは'generatSong',
        2) 歌詞を指定している場合の指定ワードは'lyrics',
        3) 曲のジャンルやテーマを入力している場合の指定ワードは'genre',
        4) 歌詞の雰囲気を入力していると判断できる場合の指定ワードは'theme',
        5) 曲のタイトルを入力していると判断できる場合の指定ワードは'title',
        検出された指定ワードは、json内に記載すること。
        user_inputにタイトル、ジャンル、ムード、楽器について記載がある場合は、各々をjesonのtitle、genre、atmosphereにinstruments記載すること。
        json形式は以下の通りとする。必ずすべてのキーを記載すること。必ずjson形式で出力すること。
        楽器が記載されている場合は、genreに追加すること。
        ただし、json形式の出力は以下のようにコードブロックで囲むこと。
        ```json
        {{"word": "指定ワード","title":"タイトル", "lyrics": "歌詞", "genre": "ジャンル", "theme": "テーマ", "atmosphere": "歌詞の雰囲気","instruments","楽器"}}
        該当がない場合の指定ワードはnullです。「これで良いか聞いてください」のような確認文は使ってはいけません。
        ユーザーの入力={user_input}
    """).strip()
    print("request_song=", request_song)
    response =  await  llm(request_song)
    print("response=", response)
    # 正規表現でJSON部分を抽出
    regex = r'```json\s*([\s\S]*?)\s*```'
    match = re.search(regex, response['message'])

    if match:
        json_string = match.group(1)  # マッチしたJSON部分を取得
        try:
            json_data = json.loads(json_string)  # JSON文字列を辞書に変換
            print("抽出されたJSONデータ:", json_data)
        except json.JSONDecodeError as e:
            print("JSONのパースに失敗しました:", e)
            return False, None, None, None
    else:
        print("JSON部分が見つかりませんでした。")
        return False, None, None, None
    sel_word = json_data.get('word', None)
    print("sel_word=", sel_word)

    # sel_wordから処理を分岐
    if sel_word == "generatSong":
        song_generate = "音楽の生成をする場合のタイトルを一つだけ提案してください。\
            タイトルは様々な場面や時間、景色、思い、人、モノ、世界など、音楽のタイトルに相応しいことを想定して多彩で変化に富む内容を考えること。\
            例えは、故郷、夕暮れ、星、思い出、愛、旅、夢、静か、夜、都会、山、海、アニメ、ロボット、AI、未来、過去、世界、日本、大阪、東京、その他の都市、など、\
            これ以外も考慮しつつ多彩なテーマからタイトルを選ぶ。音楽のジャンルや雰囲気をから考えるのも効果的です。\
            LLMの持つ特性に偏りがちなので自らの特性にこだわらないタイトルを考えること。タイトルは必ず記入すること。内容だけで説明は不要です。\
            タイトルは日本で作成して下さい。難しい漢字は使わないこと。前回とは異なる雰囲気やテーマのタイトルを考えてください。前回作成したタイトルは以下の通りです。前回作のタイトル="
        song_generate =song_generate+ previouse_title
        response = await llm(song_generate)
        print("おまかせesponse=", response)
        return await music_generation(response,genre_tags,previouse_title)  # 再帰的に呼び出し
    elif sel_word in ["lyrics", "genre", "theme", "atmosphere",'title']:
        return await gen_lyrics(json_data['title'],json_data['lyrics'], json_data['genre'], json_data['theme'], json_data['atmosphere'],json_data['instruments'],genre_tags)
    else:
        print("genSong_qaで正しい選択肢が得られなかった")
        return False, None, None, None


#　歌詞、ジャンル、テーマ,雰囲気　から作詞と作曲をする
async def gen_lyrics(title,lyrics, genre, theme, atmosphere,instruments,genre_tags):
    json_data = {
        "title":title,
        "lyrics": lyrics,
        "genre": genre,
        "theme": theme,
        "atmosphere": atmosphere,
        "instruments":instruments,
    }
    request_msg = dedent(f"""
        jsonDataで示されたユーザーの作曲の意図を正確に判断して作詞のための指定されたlyrics形式と作曲のためのgenreを作成しなさい。
        title、歌詞、ジャンル、ムード（雰囲気）、楽器はユーザー入力に記載があればそのまま採用すること。
        ただし、ジャンル、ムード（雰囲気）、楽器は日本語で入力された場合はそのまま採用せず、必ず英語に翻訳すること。
         "genre"については、ユーザーの入力を採用しても、追加で曲の雰囲気にある、他のタグを追加しても構いません。        
        lyrics形式を作成するきには、ユーザーのリクエストの"lyrics"に歌詞ががあればそのまま変形せずに歌詞として使ってlyrics形式を作成すること。
        ユーザーのリクエストの"lyrics"がすでにlyrics形式の場合はそのまま採用すること。
        ユーザーのリクエストの"lyrics"に歌詞がない場合のlyrics形式は、歌詞の内容を表すものとして、曲のジャンルやテーマ、歌詞の雰囲気を考慮して作成すること。
        英語の歌詞は書いてはいけません。英単語も使ってはいけません。更に日本語以外、他のどのような言語も使わないこと。
        ユーザーのクエストに長さ指定のような記載があれば従ってください、無ければ15行前後の歌詞を作成すること。30行よりも長い歌詞は作成しないこと。
        lyricsの形式の見本は以下のとおりです。ただし、詞や曲の内容に応じて、"verse"、"chorus", "bridge", "outro"を作曲の理論を参照しつつ、組み合わせること。
        "verse"、"chorus", "bridge"は複数回使っても構いません。形式は必ず"verse"、"chorus", "bridge", "outro"を1回以上使う恋と。
        "verse1","verse2"のように複数回使うことも可能です。曲の雰囲気に合わせて、慎重に考えてください。歌詞の形式は必ず以下の見本のように[[ }}形式にすること。
        歌詞の形式の基本的な見本={{"verse": "歌詞の内容", "chorus": "歌詞の内容", "bridge": "歌詞の内容", "outro": "歌詞の内容"}}
        genreの作成は以下のタグが定義されたjsonを参考にしてください。
        'genre'、'instrument'、'mood'、'gender'、'timbre'の各キーから必要に応じて一つ以上のタグを採用してください。
        genre作成用json={json.dumps(genre_tags, ensure_ascii=False)}
        作成したlyrics形式は、以下のjson形式のlyricsの要素に記載すること。各要素は必ず記入すること。出力のjson形式は以下の通りです。
        {{"title": "タイトル", "lyrics": "歌詞", "genre": "ジャンル", "theme": "テーマ", "atmosphere": "雰囲気"}}
        解説は不要です。参考にするユーザーのリクエストは以下のjson形式で示します。
        jsonData={json.dumps(json_data, ensure_ascii=False)}
    """).strip()

    #print("request_msg=", request_msg)
    print("Setup prompt for generate lyrics & genere")
    response = await llm(request_msg)

    # 正規表現でJSON部分を抽出
    regex = r'```json\s*([\s\S]*?)\s*```'
    match = re.search(regex, response["message"])
    json_data_m2 = {}
    if match and match[1]:
        json_string = match[1]
        try:
            json_data_m2 = json.loads(json_string)
            print("Extracted JSON object jsonData_m2:", json_data_m2)
            result = True
        except json.JSONDecodeError as error:
            print("JSON のパースに失敗しました:", error)
            result = False
    else:
        print("JSON 部分が見つかりませんでした。")
        result = False

    if result:
        end_detail = dedent(f"""
            作曲ができたので、歌詞部分だけを抜き出して表示してください。
            ただし、verse、chorus、bridge、outroの各単語は文章には入れないでください。
            歌詞の表示は、改行で区切って出力すること。その後に曲の説明と意図を簡単に説明してください。
            曲の説明には曲が完成したことには触れないこと。
            曲のタイトルは'title'キーに、歌詞は'lyrics'キーに、曲のジャンルは'genre'キーにあります。
            その他の情報は'theme'、'atmosphere'のキーに記載されています。
            各々記載の内容は説明してもいいけど、キーやjsonの形式のデータは出力には入れないこと。
            コメントは、簡潔に説明すること。作曲の結果は次のjson形式で示します。
            作曲結果は以下の通りです。
            {json.dumps(json_data_m2, ensure_ascii=False)}
        """).strip()

        music_world = await llm(end_detail)
        lyrics_m = "test"
        return result, json_data_m2, music_world, lyrics_m
    else:
        return result, None, None, None

def convert_lyrics_dict_to_text(lyrics_dict, no_vocal=False):
    """歌詞辞書をテキストに変換する関数
    
    Args:
        lyrics_dict: 歌詞辞書
        no_vocal: True の場合、ACE-Step公式推奨のインストゥルメンタル形式（構造のみ）に変換
    
    Returns:
        str: 変換された歌詞テキスト
    """
    if not isinstance(lyrics_dict, dict):
        print(f"lyrics_dictは辞書型である必要があります。現在の型: {type(lyrics_dict)}")
        return lyrics_dict
    
    result = ""
    for key, value in lyrics_dict.items():
        if not isinstance(value, str):
            print(f"警告: 値が文字列ではありません。スキップします。キー: {key}, 値: {value}")
            continue
        
        processed_key = re.sub(r"[（(].*?[）)]", "", key).strip()
        
        if no_vocal:
            # ACE-Step公式推奨：歌詞の構造セクションのみを残す（テキストは削除）　　→　ボーカル削除では効果がなかった
            result += f"[{processed_key}]\n\n"
        else:
            # 通常モード：歌詞テキストも含める
            processed_value = re.sub(r"^[（(].*?[）)]\s*\n?", "", value)
            result += f"[{processed_key}]\n{processed_value}\n"
    
    return result.strip()

# 各キーの値をカンマ区切りで結合し、テキスト形式に変換
def convert_genre_to_text(genre_data):
    result = []
    for key, values in genre_data.items():
        # キーと値を結合してテキスト形式に変換
        result.append(f"{key}: {', '.join(values)}")
    return "\n".join(result)

# ++++++++++++++++++++++++　歌の生成　+++++++++++++++++++++++
def generate_song(jeson_song: dict,infer_step: int = 27,guidance_scale: float = 15,omega_scale: float = 10, no_vocal: bool = False, audio_duration: int = -1):
    # JSON 文字列化
    print("======>>>>>jeson_song=",jeson_song)
    print(f"======>>>>>no_vocal parameter={no_vocal}")
    lyrics_dic = jeson_song['lyrics']
    print("###### lyrics_dic >>>>",lyrics_dic)
    lyrics = convert_lyrics_dict_to_text(lyrics_dic, no_vocal)
    print("###### lyrics_text >>>>",lyrics)
    genre = jeson_song['genre']
    print("###### genre >>>>",genre)
    
    # ボーカルなしの場合：最も効果的な [inst] タグを使用
    if no_vocal:
        lyrics = "[inst]"  # 実際のテストで最も効果的だった方法
        print("=== 最も効果的なボーカル除去方法: [inst] タグ使用 ===")
        print(f"lyrics設定: '{lyrics}'")
        
        # ジャンルからボーカル関連キーワードを除去し、インストゥルメンタル指定を追加
        instrumental_prefix = "pure instrumental, no vocal, no voice, no singing, no human sound, no lyrics, no words, no speech, instrumental music only, background music, ambient music, instrumental track"
        
        vocal_keywords = [
            "vocal", "vocals", "singer", "voice", "singing", "song", "lyrics", 
            "chorus", "verse", "rap", "chant", "human", "words", "speech", 
            "vocal melody", "singer", "artist", "performer", "choir", "harmony",
            "lead vocal", "backing vocal", "vocal line", "sung", "choral"
        ]
        
        cleaned_genre = genre
        for keyword in vocal_keywords:
            # 大文字小文字両方をチェック
            cleaned_genre = cleaned_genre.replace(keyword, "").replace(keyword.capitalize(), "").replace(keyword.upper(), "")
        
        # 複数のスペースとカンマを整理
        cleaned_genre = " ".join(cleaned_genre.split()).replace(" ,", ",").replace(",,", ",").strip(",").strip()
        
        # 最終的なジャンル文字列（インストゥルメンタル指定を最優先）
        genre = f"{instrumental_prefix}, {cleaned_genre}" if cleaned_genre else instrumental_prefix
        
        print(f"=== 最も効果的なボーカル除去: [inst] タグアプローチ ===")
        print(f"歌詞設定: '{lyrics}'")
        print(f"強化されたインストゥルメンタル指定: '{genre}'")
        print("=" * 60)
    
    # APIに送信するデータの準備（ACE-Step-directAPI標準形式）
    data = {
        "audio_duration": audio_duration,  # フロントエンドから設定可能に変更
        "genre": genre,
        "infer_step": infer_step,
        "lyrics": lyrics,
        "guidance_scale": guidance_scale,
        "scheduler_type": "euler",
        "cfg_type": "apg",
        "omega_scale": omega_scale,
        "guidance_interval": 0.5,
        "guidance_interval_decay": 0.0,
        "min_guidance_scale": 3,
        "use_erg_tag": True,
        "use_erg_lyric": False if no_vocal else True,  # ボーカルなしの場合は歌詞処理を完全無効化
        "use_erg_diffusion": True,
        "guidance_scale_text": 0.0,
        "guidance_scale_lyric": -1.0 if no_vocal else 0.0  # ボーカルなしの場合はより強力に抑制
    }
    
    # ボーカルなしの場合の追加強力設定
    if no_vocal:
        # ACE-Stepオリジナル準拠のボーカル抑制設定
        data.update({
            "guidance_scale_lyric": -3.0,     # 負の値でボーカルを強力に抑制（オリジナル準拠）
            "guidance_scale_text": 1.5,      # テキストガイダンスを少し強化
            "use_erg_lyric": False,           # 歌詞ERG処理を完全無効化
            "use_erg_diffusion": True,        # 拡散ERG処理は有効のまま
        })
        
        print("=== 最も効果的なインストゥルメンタル設定: [inst] タグ使用 ===")
        print(f"use_erg_lyric: {data['use_erg_lyric']}")
        print(f"use_erg_diffusion: {data['use_erg_diffusion']}")
        print(f"guidance_scale_lyric: {data['guidance_scale_lyric']}")
        print(f"guidance_scale_text: {data['guidance_scale_text']}")
        print(f"lyrics: '{lyrics}'")
        print(f"enhanced instrumental genre: '{genre}'")
        print("=" * 50)
    else:
        print("=== 通常のボーカル有り設定 ===")
        print(f"use_erg_lyric: {data['use_erg_lyric']}")
        print(f"guidance_scale_lyric: {data['guidance_scale_lyric']}")
        print("=" * 30)
    
    print(f"APIに送信するデータ: {data}")  # デバッグ用
    
    # ACE APIを呼び出し
    response = call_ace_api(data, no_vocal)
    
    if response is None:
        print("音楽生成エラー: すべてのエンドポイントで失敗")
        return None
    
    # サーバからのContent-Dispositionヘッダーからファイル名を抽出
    cd = response.headers.get("Content-Disposition", "")
    match = re.search(r'filename="?([^"]+)"?', cd)
    filename = match.group(1) if match else "output.wav"
    
    # 音楽データをバイナリとして直接返す（music_server.pyとの互換性のため）
    print(f"音楽データを受信しました: {len(response.content)} bytes")
    return response.content

def check_ace_initialization():
    """ACE-Step-directAPIサーバーが既に初期化されているかチェック（キャッシュ付き）"""
    global _ace_initialized, _last_check_time
    
    current_time = time.time()
    
    # 最近チェックして初期化済みならスキップ
    if _ace_initialized and (current_time - _last_check_time) < _check_interval:
        print(f"✓ ACE-Step（キャッシュ済み）: 前回チェックから{int(current_time - _last_check_time)}秒")
        return True
    
    print("ACE-Step初期化状態を確認中...")
    
    # statusエンドポイントをチェック
    try:
        response = requests.get(ACE_API_STATUS_ENDPOINT, timeout=5)
        if response.status_code == 200:
            try:
                json_resp = response.json()
                if json_resp.get('initialized', False):
                    print(f"✓ ACE-Step-directAPIは既に初期化済み: {ACE_API_STATUS_ENDPOINT}")
                    _ace_initialized = True
                    _last_check_time = current_time
                    return True
            except:
                pass
    except:
        pass
    
    # statusエンドポイントが無い場合、軽量なテストリクエストで確認
    # 軽量なテストデータ（最小パラメータ）
    test_data = {
        "format": "wav",
        "audio_duration": 3.0,  # 非常に短い
        "prompt": "test",
        "lyrics": "",
        "infer_step": 1,  # 最小ステップ
        "guidance_scale": 1.0,
        "scheduler_type": "euler",
        "cfg_type": "apg"
    }
    
    try:
        print(f"軽量テスト中: {ACE_API_ENDPOINT}")
        # 短いタイムアウトで確認
        response = requests.post(ACE_API_ENDPOINT, json=test_data, timeout=8)
        
        if response.status_code == 200:
            print(f"✓ ACE-Step-directAPIは初期化済み")
            _ace_initialized = True
            _last_check_time = current_time
            return True
        elif response.status_code == 500:
            # 500エラーは未初期化の可能性
            print(f"未初期化の可能性（500エラー）")
            _ace_initialized = False
            return False
            
    except requests.exceptions.Timeout:
        print(f"処理中の可能性（タイムアウト）")
        # タイムアウトは初期化済みと判断（処理中）
        _ace_initialized = True
        _last_check_time = current_time
        return True
    except Exception as e:
        print(f"チェックエラー: {str(e)}")
    
    _ace_initialized = False
    return False

def ensure_ace_initialization():
    """ACE-Step-directAPIサーバーの初期化を確実に実行（必要な場合のみ）"""
    global _ace_initialized, _last_check_time
    
    # まず初期化状態をチェック
    if check_ace_initialization():
        print("ACE-Step-directAPIは既に初期化済みです。スキップします。")
        return True
    
    print("ACE-Step-directAPIが未初期化のため、初期化を実行します...")
    
    try:
        print(f"ACE-Step-directAPI初期化を試行中: {ACE_API_INIT_ENDPOINT}")
        response = requests.post(ACE_API_INIT_ENDPOINT, json={}, timeout=90)  # タイムアウト延長
        
        if response.status_code == 200:
            try:
                json_resp = response.json()
                if json_resp.get('success', False):
                    print(f"✓ 初期化成功: {ACE_API_INIT_ENDPOINT}")
                    _ace_initialized = True
                    _last_check_time = time.time()
                    return True
                else:
                    print(f"初期化レスポンスでsuccess=False: {json_resp}")
            except:
                print(f"✓ 初期化完了（非JSONレスポンス）: {ACE_API_INIT_ENDPOINT}")
                _ace_initialized = True
                _last_check_time = time.time()
                return True
        else:
            print(f"✗ 初期化失敗 ({response.status_code}): {ACE_API_INIT_ENDPOINT}")
            print(f"Response: {response.text[:200]}")
            
    except requests.exceptions.RequestException as e:
        print(f"✗ 初期化接続エラー: {ACE_API_INIT_ENDPOINT} - {str(e)}")
    
    print("すべての初期化エンドポイントで失敗")
    _ace_initialized = False
    return False

def reset_ace_initialization_cache():
    """ACE-Step初期化キャッシュをリセット（テスト用）"""
    global _ace_initialized, _last_check_time
    _ace_initialized = False
    _last_check_time = 0
    print("ACE-Step初期化キャッシュをリセットしました")

def call_ace_api(data, no_vocal=False):
    """ACE APIエンドポイントでボーカル制御を確実に行う"""
    
    # 初期化を確実に実行
    init_success = ensure_ace_initialization()
    if not init_success:
        print("警告: ACE-Step-directAPIの初期化に失敗しました。続行します...")
    
    try:
        print(f"エンドポイント試行中: {ACE_API_ENDPOINT}")
        
        # ACE-Step-directAPI用のJSONリクエスト形式
        json_data = {
            "format": "wav",
            "audio_duration": data["audio_duration"],  # フロントエンドから設定されたデフォルト-1を使用
            "prompt": data["genre"],  # genreをpromptとして使用
            "lyrics": data["lyrics"],
            "infer_step": data["infer_step"],
            "guidance_scale": data["guidance_scale"],
            "scheduler_type": data["scheduler_type"],
            "cfg_type": data["cfg_type"],
            "omega_scale": data["omega_scale"],
            "guidance_interval": data["guidance_interval"],
            "guidance_interval_decay": data["guidance_interval_decay"],
            "min_guidance_scale": data["min_guidance_scale"],
            "use_erg_tag": data["use_erg_tag"],
            "use_erg_lyric": data["use_erg_lyric"],
            "use_erg_diffusion": data["use_erg_diffusion"],
            "guidance_scale_text": data["guidance_scale_text"],
            "guidance_scale_lyric": data.get("guidance_scale_lyric", 0.0),  # 強化された設定を使用
            "audio2audio_enable": False,  # ボーカルなしの場合はオーディオ変換を無効化
            "ref_audio_strength": 0.0,    # 参照音声の強度を0に
            "lora_name_or_path": "none",
            "lora_weight": 0.0
        }
        
        # ボーカルなしの場合の追加的な強化設定
        if no_vocal:
            # dataに追加されたボーカル抑制設定を反映
            json_data.update({
                "lyric_strength": data.get("lyric_strength", 0.0),
                "vocal_suppression": data.get("vocal_suppression", True),
                "guidance_scale_lyric": data.get("guidance_scale_lyric", -2.0),  # 負の値でさらに強力に
            })
        
        # ボーカルなしの場合の追加デバッグ情報
        if no_vocal:
            print(f"=== ボーカルなし設定でAPIリクエスト ===")
            print(f"prompt (genre): '{json_data['prompt']}'")
            print(f"lyrics: '{json_data['lyrics']}'")
            print(f"use_erg_lyric: {json_data['use_erg_lyric']}")
            print("=" * 40)
        
        print(f"送信するJSONデータ: {json.dumps(json_data, indent=2, ensure_ascii=False)}")
        response = requests.post(ACE_API_ENDPOINT, json=json_data, timeout=120)
        
        if response.status_code == 200:
            print(f"✓ エンドポイント成功: {ACE_API_ENDPOINT}")
            
            # レスポンスの内容を確認
            content_type = response.headers.get('content-type', '')
            print(f"Content-Type: {content_type}")
            print(f"Content-Length: {len(response.content)} bytes")
            
            if content_type.startswith('audio/'):
                # 直接音声データが返された場合
                print("✓ 音声データを直接受信しました")
                return response
            else:
                # JSONレスポンスの場合（エラーの可能性）
                try:
                    json_resp = response.json()
                    print(f"JSONレスポンス: {json_resp}")
                    if not json_resp.get('success', False):
                        print(f"APIエラー: {json_resp.get('error_message', 'Unknown error')}")
                        return None
                except:
                    print("JSONパースに失敗、生データを返します")
                    return response
        else:
            print(f"✗ エンドポイント失敗 ({response.status_code}): {ACE_API_ENDPOINT}")
            print(f"Response: {response.text[:200]}...")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"✗ エンドポイント接続エラー: {ACE_API_ENDPOINT} - {str(e)}")
        return None
    
    print("エンドポイントで失敗しました")
    return None

