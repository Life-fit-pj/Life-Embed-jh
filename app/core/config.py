""" 설정값을 모아두는 곳 """

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

# parent 를 두 번 올라가야 프로젝트 뿌리다
DATA_DIR = ROOT / "data"
DB_PATH = ROOT / "life.db"

# .env 를 읽어 환경변수로 올린다
load_dotenv()

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not API_KEY:
    raise RuntimeError("API 키가 없다. .env 파일을 확인해라.")


MODEL = "claude-haiku-4-5-20251001"

# py -m pip install anthropic

# ── 임베딩 ────────────────────────────────────
# 저장할 때와 검색할 때 반드시 같은 모델을 써야 한다.
# 모델이 다르면 벡터 차원부터 달라서(e5-small 384, bge-m3 1024)
# 저장해 둔 벡터를 아예 못 쓴다
EMBED_MODEL = "intfloat/multilingual-e5-small"

# ── 추천 지표 ─────────────────────────────────
# user_preferences 의 칸 이름이자 08번 점수 계산의 기준.
# 순서가 바뀌면 위치로 값을 꺼내는 코드가 조용히 깨지므로 여기서만 관리한다
INDICATORS = ["녹지", "안전", "교통", "상권", "의료", "교육", "문화"]

# ── 페르소나 청킹 ─────────────────────────────
# 라이프스타일이 드러나는 서술형 칸들.
# 지식베이스(chunk_kb)와 회원(embed_member)이 같은 방식으로 쪼개야
# 나중에 두 벡터를 같은 기준으로 비교할 수 있다
# 청킹 대상 - 라이프스타일이 드러나는 서술형 칸들
CHUNK_COLUMNS = [
    "persona",
    "professional_persona",
    "sports_persona",
    "arts_persona",
    "travel_persona",
    "culinary_persona",
    "family_persona",
    "cultural_background",
    "career_goals_and_ambitions",
]

# 너무 짧은 청크는 검색에 도움이 안 되므로 버린다
MIN_LENGTH = 20