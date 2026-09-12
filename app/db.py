"""DB 연결을 담당한다. 이 파일이 가진 것은 셋이다.

Base          모든 표 모델이 물려받는 기준 (1단계에서 만들었다)
engine        실제 DB 와 이어 주는 통로. 프로그램에 하나만 있으면 된다
SessionLocal  작업 한 건에 쓸 세션을 만들어 주는 공장

get_db(요청마다 열고 닫아 주는 FastAPI 의존성)는 안 만들었다.
수업은 api 가 세션을 받아 service 에 넘기지만, 우리는 app/tables/ 의 다리가
_run() 으로 세션을 열고 닫는다(3-A). 그래서 api 가 세션을 알 필요가 없다.

  수업   api(db) -> service(db) -> repository(db)
  우리   api     -> service     -> tables(다리가 세션을 연다) -> repository(db)

한 요청 안에서 여러 조회를 한 트랜잭션으로 묶어야 할 일이 생기면 그때 만든다.
"""


from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL)

# sessionmaker 는 "세션을 찍어내는 틀" 이다. 이것 자체는 세션이 아니다.
# 쓸 때 SessionLocal() 처럼 괄호를 붙여 한 개를 만들어 낸다.
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()
