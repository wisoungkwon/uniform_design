# Uniform_Design.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import replicate
from dotenv import load_dotenv

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

# Replicate 토큰
replicate.api_token = os.environ.get("REPLICATE_API_TOKEN")
if not replicate.api_token:
    raise RuntimeError(
        "REPLICATE_API_TOKEN이 설정되지 않았습니다. .env 파일을 확인하세요."
    )

# 우선순위 모델 후보 (상단일수록 먼저 시도)
# 환경변수 REPLICATE_MODEL 이 있으면 그걸 0번 인덱스로 끼워넣음
CANDIDATE_MODELS = [
    "stability-ai/stable-diffusion",  # 클래식 SD 1.5 라인
    "stability-ai/sdxl",  # SDXL
    "runwayml/stable-diffusion-v1-5",  # 구 라인 호환
]
env_model = os.environ.get("REPLICATE_MODEL")
if env_model:
    # 가장 앞에 넣어서 최우선 시도
    CANDIDATE_MODELS.insert(0, env_model)


def resolve_versioned_ref(model_slug: str) -> str:
    """
    모델 슬러그에서 최신 버전 id를 찾아 'owner/name:version_id'로 반환.
    일부 모델은 버전 목록을 노출하지 않아(404) 실패할 수 있음.
    """
    model = replicate.models.get(model_slug)
    # 일부 모델은 versions.list()를 노출하지 않음 → 여기서 404 가능
    versions = list(model.versions.list())
    if not versions:
        raise RuntimeError(f"모델 버전을 찾을 수 없음: {model_slug}")
    latest = versions[0]  # 일반적으로 최신이 앞
    return f"{model.owner}/{model.name}:{latest.id}"


def get_first_working_model_ref(candidates: list[str]) -> str:
    """
    후보 모델들을 순서대로 시도하여, 버전 해석이 가능한 첫 모델을 반환.
    """
    errors = []
    for slug in candidates:
        try:
            ref = resolve_versioned_ref(slug)
            print(f"[Model] Using: {ref}")
            return ref
        except Exception as e:
            msg = f"[Model] {slug} 해석 실패: {e}"
            print(msg)
            errors.append(msg)
            continue
    raise RuntimeError(
        "모델 버전 자동 해석에 모두 실패했습니다. "
        "REPLICATE_MODEL 환경변수에 버전 노출 모델을 지정하세요.\n" + "\n".join(errors)
    )


@app.route("/health", methods=["GET"])
def health():
    # 어떤 모델을 시도할지 미리 보여줌
    return (
        jsonify(
            {
                "status": "ok",
                "replicateTokenLoaded": bool(replicate.api_token),
                "candidateModels": CANDIDATE_MODELS,
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
        # 1) 후보 모델 중 버전 해석 가능한 모델을 하나 선택
        model_ref = get_first_working_model_ref(CANDIDATE_MODELS)

        # 2) 실행 (가장 일반적인 'prompt' 파라미터 우선)
        output = replicate.run(model_ref, input={"prompt": prompt})

        # 3) 결과 파싱 (list/str/dict 등 대응)
        image_url = None
        if isinstance(output, list) and output:
            first = output[0]
            image_url = (
                first
                if isinstance(first, str)
                else (first.get("url") if isinstance(first, dict) else None)
            )
        elif isinstance(output, str):
            image_url = output
        elif isinstance(output, dict):
            image_url = output.get("image") or output.get("url")

        if not image_url:
            print("Replicate raw output:", output)
            return (
                jsonify(
                    {
                        "error": "이미지 URL을 파싱하지 못했습니다. 콘솔 로그를 확인하세요."
                    }
                ),
                500,
            )

        return (
            jsonify(
                {"message": "이미지 생성이 완료되었습니다.", "imageUrl": image_url}
            ),
            200,
        )

    except Exception as e:
        print(f"Replicate 호출 중 오류: {e}")
        return jsonify({"error": f"Replicate 호출 중 오류: {e}"}), 500


if __name__ == "__main__":
    app.run(port=8000, debug=True)
