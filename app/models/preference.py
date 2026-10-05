"""회원 가중치 표. 칸 이름이 한글인데 그대로 쓴다 — 교안 1-3절 참고."""

from sqlalchemy import Column, Float, Integer, String

from app.db import Base


class Preference(Base):
    __tablename__ = "user_preferences"

    customer_id = Column(String, primary_key=True)

    # 주거 조건
    건물유형 = Column(String)
    거래형태 = Column(String)
    매매가 = Column(Integer)
    보증금 = Column(Integer)
    월세 = Column(Integer)
    건축면적 = Column(Integer)
    층수 = Column(Integer)
    준공년도 = Column(Integer)

    # 추천 지표 7개. app/core/config.py 의 INDICATORS 와 이름이 같아야 한다.
    # 실수다 — 관리자 슬라이더와 성향 제안이 4.5 같은 값을 저장한다.
    # Integer 로 적으면 SQLAlchemy 가 저장할 때 값에 ::INTEGER 를 붙여 보내서 오류 없이 4 로 깎인다
    녹지 = Column(Float)
    안전 = Column(Float)
    교통 = Column(Float)
    상권 = Column(Float)
    의료 = Column(Float)
    교육 = Column(Float)
    문화 = Column(Float)

    # 관리자가 고치기 전의 원래 값. 되돌리기와 "얼마나 고쳤나" 계산에 쓴다. 위 일곱과 타입이 같아야 한다
    녹지_초기 = Column(Float)
    안전_초기 = Column(Float)
    교통_초기 = Column(Float)
    상권_초기 = Column(Float)
    의료_초기 = Column(Float)
    교육_초기 = Column(Float)
    문화_초기 = Column(Float)
