from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import gc
from dotenv import load_dotenv

# Hugging Face diffusers 라이브러리 추가
from diffusers import StableDiffusionPipeline
import torch


# .env 로드
load_dotenv()

app = Flask(__name__)

# STS(Spring) 앱 포트에 맞게 오리진 조정
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

# Stable Diffusion 모델 로드 (서버 시작 시 1회만 실행)
# 이 경로는 Stable Diffusion v1.5 모델이 있는 Hugging Face Hub를 가리킵니다.
# 첫 실행 시에는 모델 파일을 다운로드하므로 시간이 오래 걸립니다.
model_id = "runwayml/stable-diffusion-v1-5"
print(f"Loading model: {model_id}...")
# torch_dtype=torch.float16을 사용해 메모리 사용량 최적화
pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16)
# GPU로 모델 이동
pipe.to("cuda")


# 모델을 메모리에서 해제하는 함수
def free_memory():
    del pipe
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


@app.route("/health", methods=["GET"])
def health():
    return (
        jsonify(
            {
                "status": "ok",
                "model_loaded": True,
            }
        ),
        200,
    )


@app.route("/generate-uniform", methods=["POST"])
def generate_uniform():
    data = request.get_json(silent=True) or {}
    keyword = data.get("keyword")
    style = data.get("style")

    if not keyword or not style:
        return jsonify({"error": "키워드와 스타일을 제공해야 합니다."}), 400

    prompt = (
        f"A professional {style} sports uniform with a theme of {keyword}. "
        f"High-quality, detailed, realistic, clean layout, integrated team name, front and back."
    )

    try:
        # Stable Diffusion 모델 추론
        print("Generating image...")
        output = pipe(prompt, num_inference_steps=50, guidance_scale=7.5)

        # PIL Image 객체 반환
        image = output.images[0]

        # 이미지 저장 경로 설정 및 디렉토리 생성
        image_dir = "static/generated_images"
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)

        # 파일명 생성
        filename = f"{keyword}_{style}_{len(os.listdir(image_dir)) + 1}.png"
        file_path = os.path.join(image_dir, filename)

        # 이미지 저장
        image.save(file_path)

        # 저장된 파일 경로를 반환 (프론트엔드에서 접근 가능한 경로)
        image_url = f"http://127.0.0.1:8000/{file_path}"

        print("Image generated:", image_url)
        return (
            jsonify(
                {"message": "이미지 생성이 완료되었습니다.", "imageUrl": image_url}
            ),
            200,
        )

    except Exception as e:
        print(f"이미지 생성 중 오류: {e}")
        return jsonify({"error": f"이미지 생성 중 오류: {e}"}), 500


if __name__ == "__main__":
    app.run(port=8000, debug=True)
