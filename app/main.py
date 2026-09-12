"""엔진 단독 FastAPI. 9단계에서 만들었다.

실행: py -m uvicorn app.main:app --reload --port 8000
문서: http://127.0.0.1:8000/docs

요청이 흘러가는 길 —
  브라우저 -> api -> schemas -> services -> engine·rag -> tables -> repositories -> DB

★ Life-Web(:5000)과 별개로 뜬다. 둘은 같은 data/life.db 를 본다.
  화면은 아직 Life-Web 에 있고 여기에는 /docs 뿐이다.
  팀원이 Life-Web/routers/ 를 app/api/ 로 옮기고 나면 이 서버 하나만 남는다.
"""

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
