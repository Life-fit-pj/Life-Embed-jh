"""엔진 단독 FastAPI. 9단계에서 만들었다.

실행: py -m uvicorn app.main:app --reload --port 8000
문서: http://127.0.0.1:8000/docs

요청이 흘러가는 길 —
  브라우저 -> api -> schemas -> services -> engine·rag -> tables -> repositories -> DB

★ Life-Web(:5000)과 별개로 뜬다. 둘은 같은 DB 를 본다 —
  .env 의 DATABASE_URL 한 줄이 그것을 정한다(지금은 Supabase Postgres).
  화면은 아직 Life-Web 에 있고 여기에는 /docs 뿐이다.
  팀원이 Life-Web/routers/ 를 app/api/ 로 옮기고 나면 이 서버 하나만 남는다.
"""

import sys
# Windows 콘솔의 기본 코드페이지(cp949)는 이모지를 못 담는다.
# search_service.get_ready() 등이 찍는 ⏳/✅/❌ print 가 그대로 두면 UnicodeEncodeError 로
# 죽는다 — 처음 요청에서 죽으면 캐시(_ready)가 안 채워져 재시도해도 계속 죽는다.
# 여기서 먼저 UTF-8 로 바꿔 둔다 (Life-Web/main.py 와 같은 처방)
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI

from app.api import admin, analysis, auth, chat, customers, history, recommend, regions, survey

app = FastAPI(title="LIFE,FIT 엔진", description="추천 엔진 API")

app.include_router(recommend.router)
app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(admin.router)
app.include_router(analysis.router)
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(regions.router)
app.include_router(survey.router)


@app.get("/")
def home():
    return {"message": "LIFE,FIT 엔진 API", "문서": "/docs"}
