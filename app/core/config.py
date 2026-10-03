""" 설정값을 모아두는 곳 """

import os
from pathlib import Path

from dotenv import load_dotenv

# 이 파일이 app/core/ 안에 있으므로 뿌리까지 세 단계다
#   .parent         app/core
#   .parent.parent  app
#   세 번째          프로젝트 뿌리
BASE_DIR = Path(__file__).resolve().parents[2]  # Life-Embed-jh 루트
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"      # CSV 원본. pipeline/ 만 읽는다

# DB 는 이것 하나로 정한다. 기본값이 없다 — 없으면 죽는다.
# API 키와 같은 규칙이다: 없는 채로 돌면 9,900번째가 아니라 첫 줄에서 알게 된다
DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 이 없다. .env 파일을 확인해라.")

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY 가 없다. .env 파일을 확인해라.")

# ── Supabase Auth ─────────────────────────────
# service_role 키는 RLS 를 무시하는 전권 키다. 토큰 검증(app/ai/supabase_auth.py)에만
# 쓰고, 절대 Life-Web/프론트로 넘기지 않는다.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 가 없다. .env 파일을 확인해라.")

MODEL = "claude-haiku-4-5-20251001"

# ── 임베딩 ────────────────────────────────────
# 저장할 때와 검색할 때 반드시 같은 모델을 써야 한다.
# 모델이 다르면 벡터 차원부터 달라서(e5-small 384, text-embedding-3-small 1536)
# 저장해 둔 벡터를 아예 못 쓴다
#
# 키 확인을 여기서 하는 이유 — 없는 채로 재임베딩을 돌리면
# 9,900번째가 아니라 첫 줄에서 알게 된다
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 가 없다. .env 파일을 확인해라.")

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIMENSION = 1536


# ── 추천 지표 ─────────────────────────────────
# user_preferences 의 칸 이름이자 08번 점수 계산의 기준.
# 순서가 바뀌면 위치로 값을 꺼내는 코드가 조용히 깨지므로 여기서만 관리한다
INDICATORS = ["녹지", "안전", "교통", "상권", "의료", "교육", "문화"]

# ── 페르소나 청킹 ─────────────────────────────
# 라이프스타일이 드러나는 서술형 칸들.
# 지식베이스와 회원을 같은 방식으로 쪼개야 두 벡터를 같은 기준으로 비교할 수 있다.
# 쪼개는 것도 담는 것도 이제 한 곳이다 — pipeline/chunk.py 가 chunks 표에 넣는다
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

# 회원에게만 있는 열 번째 칸 — 가입 설문이 아니라 활동(검색·좋아요)에서 정리한 성향이다.
# CHUNK_COLUMNS 에 넣지 않는다 — 그 목록은 "CSV 에 있는 가입 칸 아홉"이고,
# pipeline/fix_member_persona.py 가 아홉 칸이 전부 있다고 가정한다
ACTIVITY_COLUMN = "activity_persona"

# 페르소나 한 칸의 최대 글자 수. 넘으면 저장을 거절한다 — 350자를 넘는 글은 조각 여러 개로 나뉘므로(chunker.MAX_LENGTH) 두 조각까지만 받는다
MAX_PERSONA_LENGTH = 700

# ── 벡터 검색 임계값 ─────────────────────────
# 코사인 유사도(1 = 같음). 이보다 낮으면 "비슷한 사람이 없다"로 보고 버린다.
# 검색은 거리와 무관하게 top_k 개를 늘 돌려주므로, 결과가 있다고 관련 있는 게 아니다.
# 0.0 = 끄기. 값의 근거는 pipeline.golden_search 의 "유사 회원 5명 중 최저 점수" 분포 —
# 정할 때 날짜와 숫자를 여기 적는다.
# 2026-09-29 3문항 실측: 맞은 문항 0.399·0.404, 틀린 문항 0.426 — 틀린 쪽이 더 높아 경계가 없다.
#   임계값으로 못 가르는 실패다(순위 계산 쪽 문제). 20문항에서 다시 본다. 그때까지 끈다.
SIMILARITY_FLOOR = 0.0
