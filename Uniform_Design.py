# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import os, gc, uuid
from dotenv import load_dotenv

import torch
from diffusers import StableDiffusionPipeline, EulerAncestralDiscreteScheduler
from PIL import Image, ImageDraw, ImageFont

# =========================
# Init
# =========================
load_dotenv()
app = Flask(__name__)

# Spring(Thymeleaf) 포트에 맞춰 CORS 허용
CORS(
    app,
    resources={
        r"/generate-uniform": {
            "origins": ["http://localhost:8081"],
            "methods": ["POST", "OPTIONS"],
            "allow_headers": ["Content-Type"],
        },
        r"/health": {
            "origins": ["http://localhost:8081"],
            "methods": ["GET", "OPTIONS"],
        },
    },
)

MODEL_ID = "runwayml/stable-diffusion-v1-5"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32

print(f"[INIT] Loading model: {MODEL_ID} on {DEVICE} ({DTYPE})...")
pipe = StableDiffusionPipeline.from_pretrained(MODEL_ID, torch_dtype=DTYPE)
pipe = pipe.to(DEVICE)
# 제품샷 톤에 좋은 Euler a 스케줄러
pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config)
try:
    pipe.enable_xformers_memory_efficient_attention()
except Exception:
    pass


def free_memory():
    """필요시 수동 해제"""
    global pipe
    del pipe
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# =========================
# Prompt helpers
# =========================
STYLE_MAP = {
    "short_sleeve_tshirt": "pullover baseball jersey",  # 저지(풀오버)
    "button_up_shirt": "buttoned baseball jersey",  # 저지(버튼)
    "long_sleeve_tshirt": "compression undershirt under baseball jersey",  # 언더셔츠
    "sleeveless_shirt": "sleeveless baseball jersey",
}

# 다중/콜라주/사람/마네킹/셔츠/체크무늬/저품질/워터마크 차단
NEGATIVE_PROMPT = (
    "two jerseys, multiple jerseys, duplicate, collage, montage, set, "
    "person, people, mannequin, model, body, arm, hand, pants, "
    "dress shirt, formal shirt, polo shirt, hoodie, sweatshirt, cardigan, suit, tie, "
    "plaid, checkered, gingham, tartan, stripes, polka dots, logos, brand logo, text watermark, "
    "cuff buttons, sleeve buttons, pocket square, "
    "lowres, blurry, deformed, worst quality, jpeg artifacts, watermark, signature, text, text garble"
)


def extract_theme(keyword: str):
    """키워드에서 대략적인 색/마스코트 힌트 추출(간단 매핑)"""
    k = (keyword or "").lower()
    primary, accent, mascot = None, None, None

    color_map = {
        "빨간": ("red", "white"),
        "레드": ("red", "white"),
        "파란": ("blue", "white"),
        "파랑": ("blue", "white"),
        "블루": ("blue", "white"),
        "초록": ("green", "white"),
        "그린": ("green", "white"),
        "검정": ("black", "white"),
        "블랙": ("black", "white"),
        "하양": ("white", "black"),
        "화이트": ("white", "black"),
        "노랑": ("yellow", "black"),
        "옐로": ("yellow", "black"),
        "주황": ("orange", "white"),
        "오렌지": ("orange", "white"),
        "보라": ("purple", "white"),
    }
    for key, (p, a) in color_map.items():
        if key in k:
            primary, accent = p, a
            break

    if "호랑" in k:
        mascot = "tiger emblem"
    elif "독수" in k:
        mascot = "eagle emblem"
    elif "용" in k:
        mascot = "dragon emblem"
    elif "사자" in k:
        mascot = "lion emblem"
    elif "곰" in k:
        mascot = "bear emblem"

    return primary, accent, mascot


def decide_view(name_position: str, number_position: str) -> str:
    """오버레이 위치를 보고 front/back 뷰 결정"""
    backish = {"back"}
    frontish = {"front_left", "front_center", "shoulder"}
    if (name_position in backish) or (number_position in backish):
        return "back"
    if (name_position in frontish) or (number_position in frontish):
        return "front"
    return "front"


def build_prompt(keyword: str, sport: str, style: str, view: str) -> str:
    """야구 저지 + 단일 피사체 + 뷰 고정"""
    style_phrase = STYLE_MAP.get(style, "baseball jersey")
    primary, accent, mascot = extract_theme(keyword)
    view_phrase = "back view" if view == "back" else "front view"

    parts = [
        style_phrase,
        "baseball uniform",
        f"{view_phrase}, single jersey centered, isolated subject",
        "studio product photo, plain neutral background, even soft lighting",
        "pro sports apparel, realistic fabric texture, stitched seams, raglan lines, piping",
        "clean composition, symmetrical layout, no mannequin, no person, one garment only",
    ]
    if primary:
        parts.append(f"primary color {primary}")
    if accent:
        parts.append(f"accent color {accent}")
    if mascot and view != "back":  # 등면이면 로고 문구는 불필요
        parts.append(f"small {mascot} on left chest")
    if keyword:
        parts.append(f"theme: {keyword}")

    parts += [
        "(baseball jersey:1.25)",
        "(single subject:1.2)",
        "(studio:1.1)",
        "(clean:1.1)",
    ]
    return ", ".join(parts)


# =========================
# Text overlay (name/number)
# =========================
FONT_NAME_PATH = os.getenv("FONT_NAME_PATH", "fonts/MLBBlock.ttf")
FONT_NUM_PATH = os.getenv("FONT_NUM_PATH", "fonts/MLBNumbers.ttf")


def _load_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size=size)
    except Exception:
        # 시스템 폰트 폴백
        for fp in [
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]:
            try:
                return ImageFont.truetype(fp, size=size)
            except Exception:
                continue
        return ImageFont.load_default()


def draw_text_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    center_xy,
    font,
    fill,
    stroke_fill,
    stroke_width,
):
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = center_xy[0] - w // 2
    y = center_xy[1] - h // 2
    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def overlay_name_and_number(
    img: Image.Image,
    name: str,
    number: str,
    name_position: str = "back",
    number_position: str = "back",
    view: str = "front",
):
    """
    front/back 뷰별 좌표로 이름/번호를 오버레이.
    정면 제품샷(세로 1024 권장) 기준 비율 좌표.
    """
    img = img.convert("RGBA")
    W, H = img.size
    draw = ImageDraw.Draw(img)

    name_font = _load_font(
        FONT_NAME_PATH, size=int(H * (0.06 if view == "front" else 0.07))
    )
    num_font = _load_font(
        FONT_NUM_PATH, size=int(H * (0.14 if view == "front" else 0.16))
    )

    white, black = (255, 255, 255, 255), (0, 0, 0, 255)

    # --- 이름 ---
    if name:
        if view == "front":
            if name_position == "front_left":
                cx, cy = int(W * 0.33), int(H * 0.34)
            elif name_position == "none":
                cx, cy = None, None
            else:
                cx, cy = int(W * 0.5), int(H * 0.18)  # front에서 back 요청시 타협 배치
        else:
            cx, cy = int(W * 0.5), int(H * 0.16)  # 등 상단

        if cx is not None:
            draw_text_centered(
                draw, name, (cx, cy), name_font, white, black, stroke_width=3
            )

    # --- 번호 ---
    if number:
        if view == "front":
            if number_position == "front_center":
                cx, cy = int(W * 0.5), int(H * 0.46)
            elif number_position == "shoulder":
                cx, cy = int(W * 0.5), int(H * 0.28)
            else:
                cx, cy = int(W * 0.5), int(H * 0.60)  # front에서 back 요청시 타협 배치
        else:
            cx, cy = int(W * 0.5), int(H * 0.52)  # 등 중앙 약간 아래

        draw_text_centered(
            draw, number, (cx, cy), num_font, white, black, stroke_width=4
        )

    return img


# =========================
# Routes
# =========================
@app.get("/health")
def health():
    return jsonify({"status": "ok", "device": DEVICE, "model_loaded": True}), 200


@app.post("/generate-uniform")
def generate_uniform():
    data = request.get_json(silent=True) or {}

    keyword = (data.get("keyword") or "").strip()
    style = data.get("style") or data.get("uniform_style") or "short_sleeve_tshirt"
    sport = data.get("sport", "baseball") or "baseball"

    player_name = (data.get("player_name") or "").strip()
    player_number = str(data.get("player_number") or "").strip()

    name_style = data.get("name_style", "english")  # 현재는 대⋅소문자만 처리
    name_position = data.get("name_position", "back")
    number_position = data.get("number_position", "back")
    uppercase = str(data.get("name_uppercase", "on")).lower() in ("on", "true", "1")

    if not keyword or not style:
        return jsonify({"error": "키워드와 스타일을 제공해야 합니다."}), 400

    if uppercase:
        player_name = player_name.upper()

    # 뷰 결정 → 프롬프트 구성
    view = decide_view(name_position, number_position)
    prompt = build_prompt(keyword=keyword, sport=sport, style=style, view=view)

    # 추론 파라미터(프런트에서 오버라이드 가능)
    steps = int(data.get("steps", 40))  # 36~44 권장
    guidance = float(data.get("guidance", 6.5))  # 6.0~7.0 권장
    # 세로 비율 권장(상의 구도 안정)
    height = int(data.get("height", 1024))
    width = int(data.get("width", 768))
    seed = data.get("seed", None)

    g = None
    if isinstance(seed, int):
        g = torch.Generator(device=DEVICE).manual_seed(seed)

    try:
        print("[GEN] view:", view)
        print("[GEN] prompt >>>", prompt)

        # 일부 환경에서 cpu autocast 미지원 → 안전하게 분기
        try:
            with torch.autocast(
                device_type=("cuda" if DEVICE == "cuda" else "cpu"), dtype=DTYPE
            ):
                out = pipe(
                    prompt,
                    negative_prompt=NEGATIVE_PROMPT,
                    num_inference_steps=steps,
                    guidance_scale=guidance,
                    height=height,
                    width=width,
                    generator=g,
                )
        except Exception:
            out = pipe(
                prompt,
                negative_prompt=NEGATIVE_PROMPT,
                num_inference_steps=steps,
                guidance_scale=guidance,
                height=height,
                width=width,
                generator=g,
            )

        base_img = out.images[0]

        # 서버 합성으로 이름/등번호 확정
        final_img = overlay_name_and_number(
            base_img,
            name=player_name,
            number=player_number,
            name_position=name_position,
            number_position=number_position,
            view=view,
        )

        # 저장 & URL 반환
        image_dir = "static/generated_images"
        os.makedirs(image_dir, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.png"
        file_path = os.path.join(image_dir, filename)
        final_img.save(file_path)

        image_url = f"http://127.0.0.1:8000/{file_path}"
        print("[GEN] done:", image_url)

        return (
            jsonify(
                {
                    "message": "이미지 생성이 완료되었습니다.",
                    "imageUrl": image_url,
                    "caption": "생성된 디자인이 여기 있습니다!",
                    "prompt": prompt,
                    "view": view,
                }
            ),
            200,
        )

    except Exception as e:
        print(f"[ERR] 이미지 생성 중 오류: {e}")
        return jsonify({"error": f"이미지 생성 중 오류: {e}"}), 500


if __name__ == "__main__":
    # 개발용: 외부 노출 필요하면 host="0.0.0.0"
    app.run(port=8000, debug=True)
