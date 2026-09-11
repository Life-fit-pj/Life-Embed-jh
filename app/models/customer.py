"""회원 표 (정형 데이터)"""

from sqlalchemy import Column, Date, Integer, String

from app.db import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id = Column(String, primary_key=True)
    name = Column(String)
    gender = Column(String)
    age = Column(Integer)
    phone = Column(String)
    email = Column(String)

    # 사는 곳과 일하는 곳을 따로 둔다. 추천에서 둘 다 쓴다.
    city = Column(String)
    city_dong = Column(String)
    work_city = Column(String)
    work_dong = Column(String)

    joined_at = Column(Date)      # Postgres 가 date 로 만든다. 글자로 적으면 substr 에서 깨진다
