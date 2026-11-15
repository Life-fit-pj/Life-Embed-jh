"""user_memory 표 하나만 만든다(장기 메모리). 이미 있으면 아무것도 안 한다 — 여러 번 돌려도 안전하다.

실행: py -m pipeline.migrate_user_memory

pipeline.schema 는 표 17개를 지우고 다시 만들어 쌓인 기록이 날아간다. 표 하나를 더할 때는 이 파일처럼
그 표만 만든다. RLS 도 schema.py 7단계와 같은 이유로 켠다 — 안 켜면 anon 키로 REST 를 직접 쳐서 읽힌다.
"""

from sqlalchemy import DDL

from app.db import engine
from app.models.memory import UserMemory


def main():
    UserMemory.__table__.create(engine, checkfirst=True)
    with engine.begin() as con:
        con.execute(DDL(f'ALTER TABLE public."{UserMemory.__tablename__}" ENABLE ROW LEVEL SECURITY'))
    print(f"✅ {UserMemory.__tablename__} 표 준비 · RLS 켬")


if __name__ == "__main__":
    main()
