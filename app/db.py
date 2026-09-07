"""DB 연결을 담당한다. 이 파일이 가진 것은 셋이다.

Base          모든 표 모델이 물려받는 기준 (1단계에서 만들었다)
engine        실제 DB 와 이어 주는 통로. 프로그램에 하나만 있으면 된다
SessionLocal  작업 한 건에 쓸 세션을 만들어 주는 공장

get_db(요청마다 열고 닫아 주는 FastAPI 의존성)는 여기 없다.
부르는 쪽(app/api/)이 9단계에 생기므로 그때 만든다.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DATABASE_URL

# SQLite 는 "연결을 만든 스레드에서만 써라" 가 기본값이다.
# 그런데 engine 은 연결을 풀에 넣고 돌려쓰므로, A 스레드가 만든 연결이
# B 스레드에게 넘어갈 수 있다. 그때 이 옵션이 없으면 ProgrammingError 로 죽는다.
#
# 지금 app/core/db.py 25행이 같은 옵션을 쓰고 있다 — 같은 이유다.
# PostgreSQL 은 이 문제가 없으므로 sqlite 일 때만 붙인다.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

# sessionmaker 는 "세션을 찍어내는 틀" 이다. 이것 자체는 세션이 아니다.
# 쓸 때 SessionLocal() 처럼 괄호를 붙여 한 개를 만들어 낸다.
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()
