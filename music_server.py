# music_server.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import io, base64, json
from openai_chat import  AsyncOpenAI
from create_image_world import create_image
from music import music_generation, generate_song
import asyncio
from PIL import Image, ImageDraw, ImageFont

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')

a_client =AsyncOpenAI(
    #base_url="http://127.0.0.1:8080/v1",
    #base_url="http://39.110.248.77:64652/v1", # 27B　PC2
    base_url="http://39.110.248.77:64650/v1", # 27B　PC1
    api_key="YOUR_OPENAI_API_KEY",  # このままでOK
    )
sdxl_url = 'http://39.110.248.77:64656'

# genre_tags.json を読み込む
with open("genre_tags.json", "r", encoding="utf-8") as f:
     genre_tags = json.load(f)

@app.get('/')
async def read_index():
    return FileResponse('templates/index.html')

@app.post('/generate_lyrics')
async def generate(request: Request, user_input: str = Form(...),previouse_title:str=Form(...), no_vocal: bool = Form(False)):
    if user_input is None or user_input.strip() == "":
        user_input = "おまかせで音楽を生成してください"
    
    # ボーカルなしの場合は、プロンプトにinstrumentalを追加
    if no_vocal:
        user_input = f"instrumental music, no vocal, {user_input}"
        print(f"ボーカルなしモード: プロンプトを'{user_input}'に変更しました")
    
    success, lyrics_dict, music_world, _ = await music_generation(user_input,genre_tags,previouse_title)
    if not success:
        return JSONResponse({ 'err': '音楽生成に失敗しました' }, status_code=500)
    print("music_world=",music_world)
    print("lyrics_dict=",lyrics_dict)
    result=True
    return JSONResponse({"result":result,"lyrics_dict": lyrics_dict, "music_world":music_world})

@app.post('/generate_music')
async def generate_music(request: Request,
                         lyrics_dict: str = Form(...), 
                         infer_step: int = Form(27), 
                         guidance_scale: float = Form(15), 
                         gomega_scale: float = Form(10), 
                         music_world: str = Form(...),
                         height: int = Form(976),
                         width: int = Form(1296),
                         no_vocal: bool = Form(False),
                         audio_duration: int = Form(-1)):
    music_world = json.loads(music_world.replace(" ", ""))
    print("music_world=",music_world)
    lyrics_dict = json.loads(lyrics_dict.replace(" ", ""))
    print("lyrics_dict=",lyrics_dict)
    print(f"no_vocal parameter received: {no_vocal}")
    print(f"audio_duration parameter received: {audio_duration}")
    # ① 音楽生成の結果を取得
    #generate_song から bytes が返ってくる想定
    # 並列処理で音楽と画像を生成
    try:
        audio_task = asyncio.to_thread(generate_song, lyrics_dict, infer_step, guidance_scale, gomega_scale, no_vocal, audio_duration)
        image_task = create_image(sdxl_url, a_client, music_world, "text2image", "t2i",height,width)
        audio_bytes, pil_image = await asyncio.gather(audio_task, image_task)
        
        # 画像生成に失敗した場合のフォールバック処理
        if pil_image is None:
            # デフォルト画像を作成またはプレースホルダー画像を使用
            from PIL import Image, ImageDraw, ImageFont
            pil_image = Image.new('RGB', (width, height), color=(100, 150, 200))
            draw = ImageDraw.Draw(pil_image)
            
            # フォントサイズを動的に調整
            font_size = min(width, height) // 20
            try:
                # デフォルトフォントを使用
                font = ImageFont.load_default()
            except:
                font = None
            
            text = "♪ Generated Music ♪"
            # テキストを中央に配置
            if font:
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
            else:
                text_width = len(text) * 10  # 大まかな推定
                text_height = 20
            
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            draw.text((x, y), text, fill=(255, 255, 255), font=font)
            print("デフォルト画像を生成しました")
        
        buf = io.BytesIO()
        pil_image.save(buf, format='PNG')
        image_base64 = 'data:image/png;base64,' + __import__('base64').b64encode(buf.getvalue()).decode()
        
    except Exception as e:
        print(f"音楽・画像生成中にエラーが発生しました: {e}")
        return JSONResponse({'err': f'音楽・画像生成に失敗しました: {str(e)}'}, status_code=500)
    # ④ 音声も Base64 にエンコード（Data URI スキーム）
    audio_base64 = 'data:audio/mp3;base64,' + base64.b64encode(audio_bytes).decode()
    # ⑤ JSON でまとめて返却
    print("generate_music_result:lyrics_dict =", lyrics_dict)
    return JSONResponse({
        'lyrics_json': json.dumps(lyrics_dict, ensure_ascii=False, indent=2),
        'image_base64': image_base64,
        'audio_base64': audio_base64,
    })

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('music_server:app', host='0.0.0.0', port=64653, reload=True)
