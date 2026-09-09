# Life-Embed-jh 추천 엔진 API 이미지 (DOCKER.md 3번)
#
# 베이스 선택 근거는 DOCKER.md 2번 — requirements.txt 전체가 cp312 휠로
# 설치되는 것을 --only-binary dry-run 으로 확인했다. 컴파일이 한 번도
# 일어나지 않으므로 빌더 스테이지 없이 단일 스테이지로 충분하다.
FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE — 이미지 안에 .pyc 를 남기지 않는다
# PYTHONUNBUFFERED     — 로그가 버퍼에 갇히지 않고 stdout 으로 바로 나간다 (14번)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 저장소 루트를 WORKDIR 로 둔다 — app/ 이 __init__.py 없는 네임스페이스
# 패키지라서 루트가 sys.path 에 있어야 app.* 가 resolve 된다 (AGENTS.md).
# 디렉터리 이름을 /app 이 아닌 /code 로 두는 이유는 패키지 이름 app 과
# 겹쳐 읽기 어려워지는 것을 피하기 위해서다
WORKDIR /code

# 요구사항만 먼저 넣고 설치한다 — 소스가 바뀌어도 이 레이어는 캐시에 남는다
COPY requirements.txt ./
# --only-binary=:all: 로 소스 배포를 금지한다. 2번의 "단일 스테이지" 결정을
# 빌드가 스스로 지키게 만드는 장치다 — 휠이 없는 패키지가 새로 들어오면
# 몇 분씩 조용히 컴파일하는 대신 여기서 즉시 실패한다
RUN pip install --only-binary=:all: -r requirements.txt

# 런타임에 필요한 것은 app/ 뿐이다.
#   pipeline/  CSV -> life.db 적재용. 배포에 따라가지 않는다 (AGENTS.md)
#   tests/     런타임 이미지에 테스트 러너를 넣지 않는다 (13번)
#   data/      life.db 는 볼륨으로 마운트한다 (8번). 원본 CSV 는 적재용이라 제외
#   .env       이미지에 굽지 않는다. env_file / 플랫폼 환경변수로 주입한다 (9번)
# COPY 단위가 app/ 통째라서 KAN-87~89 의 내부 모듈 재배치가 끝나도 이 줄은 안 바뀐다
COPY app ./app

# life.db 볼륨이 붙을 자리. 마운트가 없으면 config.py 가 경고만 찍고
# 빈 DB 로 돌아간다 — 조용히 넘어가는 실패라 10번 헬스체크에서 표까지 확인한다
VOLUME ["/code/data"]

EXPOSE 8000

# 컨테이너 안에서는 127.0.0.1 이 아니라 0.0.0.0 으로 열어야 바깥에서 붙는다
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
