#!/usr/bin/env bash
# 계층이 지켜지나 세 가지를 센다. 저장소 뿌리에서  bash check.sh

echo
echo "① app/ 에 날 SQL 이 없다"
# text() 가 날 SQL 을 실행하는 유일한 길이다. 4단계에서 전부 ORM 으로 옮겼다.
#   \b        build_context( · mask_text( 처럼 이름 끝이 text 인 함수를 거른다
#   ['\"]     text(변수) 가 아니라 text("SELECT …") 처럼 글자를 넘기는 것만 본다
#   app/models/  server_default=text("CURRENT_TIMESTAMP") 는 DDL 기본값이라 예외
if grep -rnE "\btext\(['\"]" --include=*.py app | grep -v "^app/models/"; then
    echo "  X 전부 ORM 으로 간다 (app/repositories/*_repository.py)"
else
    echo "  OK 0곳"
fi

echo
echo "② 함수 안 import 가 있으면 안 된다"
if grep -rn "^ \+from app\." --include=*.py app/; then
    echo "  X 맨 위로 올린다. 올려서 죽으면 진짜 순환이다"
else
    echo "  OK 0곳"
fi

echo
echo "③ 계층 방향"
python -m pytest tests/test_layers.py -q


echo
echo "④ 0바이트 __init__.py 가 있으면 안 된다"
if find app -name '__init__.py' | grep .; then
    echo "  X 지운다. 뿌리에서 -m 으로 실행하므로 필요 없다"
else
    echo "  OK 0개"
fi

echo
echo "⑤ LangChain 이 코드에 남아 있으면 안 된다"
if grep -rnE "^ *(from|import) langchain" --include=*.py app pipeline tests tools; then
    echo "  X 4단계에서 걷어냈다. 되살아났다"
else
    echo "  OK 0곳"
fi

echo
echo "⑥ app 밖(tests·tools·pipeline)이 다리에 기대면 안 된다"
if grep -rnE "^ *(from|import) app\.features" --include=*.py tests tools pipeline; then
    echo "  X app.services 를 곧장 부른다. 다리는 팀원이 곧 지운다"
else
    echo "  OK 0곳"
fi


echo
echo "⑦ SQLite 가 되살아났나"
if grep -rniE "sqlite|DB_PATH|PRAGMA|check_same_thread" --include=*.py app pipeline tests tools; then
    echo "  X 5단계에서 없앴다. 되살아났다"
else
    echo "  OK 0곳"
fi
