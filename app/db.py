"""DB 연결을 담당한다. 1단계에서는 Base 하나만 만든다.

Base   모든 표 모델이 물려받는 기준.
       이걸 상속하는 순간 SQLAlchemy 가 "이 클래스는 표다" 라고 등록한다.
       등록되어야 db.query(Customer) 로 조회할 수 있다.

engine · SessionLocal · get_db 는 2단계에서 이 파일에 덧붙인다.
지금 안 만드는 이유 — 1단계의 모델은 "표가 어떻게 생겼나"만 적은 것이고,
연결은 아직 필요 없다. 필요해진 단계에서 만든다.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
