import sqlite3
from app.core.config import DB_PATH
from pipeline.resync import resync_member

con = sqlite3.connect(DB_PATH)

# 1. 지금 C001 의 청크가 몇 개인지 확인
before = con.execute(
    "SELECT COUNT(*) FROM member_chunk WHERE customer_id = 'C001'").fetchone()
print("전:", before)

# 2. nemotron.csv 에서 C001 행 하나를 읽어와서 persona 칸만 살짝 바꿔본다
from app.core.io import read_csv
_, rows = read_csv("data/nemotron.csv", limit=1)
row = rows[0]
row["customer_id"] = "C001"
row["persona"] = row["persona"] + " (테스트로 문장을 하나 더 붙여봄)"

# 3. 다시 만들기
resync_member(con, "C001", row)

# 4. 청크 개수와 내용이 바뀌었는지 확인
after = con.execute(
    "SELECT COUNT(*) FROM member_chunk WHERE customer_id = 'C001'").fetchone()
print("후:", after)

texts = con.execute(
    "SELECT text FROM member_chunk WHERE customer_id = 'C001' AND category = 'persona'"
).fetchall()
print(texts)   # "테스트로 문장을 하나 더 붙여봄" 이 보이면 성공