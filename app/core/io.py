"""
파일 읽고 쓰는 기능을 모아둔다.

CSV 를 읽는 코드가 01·03·04·06번에 똑같이 복사되어 있었다.
인코딩 처리 하나를 고치려면 네 곳을 다 찾아 고쳐야 했다.
"""

import csv

# CSV 한 칸에 아주 긴 글이 들어있을 수 있다 (페르소나 서술문).
# 파이썬 기본 상한은 131,072 글자라 그걸 넘으면 에러가 난다
csv.field_size_limit(10 * 1024 * 1024)


def read_csv(path, limit=None):
    """CSV 를 읽어 (칸 이름 목록, 줄 목록) 을 돌려준다.

    encoding 이 "utf-8-sig" 인 이유 —
    윈도우에서 만든 CSV 는 맨 앞에 BOM 이라는 눈에 안 보이는 표식이 붙는다.
    "utf-8" 로 읽으면 첫 칸 이름이 'customer_id' 가 아니라
    '\ufeffcustomer_id' 가 되어 표끼리 잇는 작업이 통째로 깨진다.

    limit 을 주면 그 줄 수까지만 읽는다.
    nemotron.csv 는 438MB 라 구조만 볼 때 전부 올릴 이유가 없다
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        if limit is None :
            return fieldnames, list(reader)
        
        rows = []
        
        for i, row in enumerate(reader):
            if i >= limit:
                break
            rows.append(row)
            
        return fieldnames, rows


def read_csv(path, limit=None):
    """CSV 를 읽어 (칸 이름 목록, 줄 목록) 을 돌려준다.

    인코딩을 차례로 시도하는 이유 —
    공공데이터는 utf-8 과 cp949 가 섞여 있다.
    엑셀에서 저장한 파일은 대개 cp949 다.

    utf-8-sig 를 먼저 쓰는 이유 —
    윈도우에서 만든 CSV 는 맨 앞에 BOM 이라는 눈에 안 보이는 표식이 붙는다.
    "utf-8" 로 읽으면 첫 칸 이름이 'customer_id' 가 아니라
    '\ufeffcustomer_id' 가 되어 표끼리 잇는 작업이 통째로 깨진다
    """
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames

                if limit is None:
                    return fieldnames, list(reader)

                rows = []
                for i, row in enumerate(reader):
                    if i >= limit:
                        break
                    rows.append(row)

                return fieldnames, rows

        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(f"{path.name} 인코딩 판별 실패 (utf-8, cp949 모두 실패)")

def count_rows(path):
    """줄 수만 센다. 줄을 저장하지 않으므로 파일이 커도 메모리를 안 먹는다."""
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return sum(1 for _ in csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    return 0
    
    
    