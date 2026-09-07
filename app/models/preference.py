"""회원 가중치 표. 칸 이름이 한글인데 그대로 쓴다 — 교안 1-3절 참고."""

from sqlalchemy import Column, Integer, String

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
    녹지 = Column(Integer)
    안전 = Column(Integer)
    교통 = Column(Integer)
    상권 = Column(Integer)
    의료 = Column(Integer)
    교육 = Column(Integer)
    문화 = Column(Integer)

    # 관리자가 고치기 전의 원래 값. 되돌리기와 "얼마나 고쳤나" 계산에 쓴다.
    녹지_초기 = Column(Integer)
    안전_초기 = Column(Integer)
    교통_초기 = Column(Integer)
    상권_초기 = Column(Integer)
    의료_초기 = Column(Integer)
    교육_초기 = Column(Integer)
    문화_초기 = Column(Integer)
