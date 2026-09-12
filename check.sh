#!/usr/bin/env bash
# 계층이 지켜지나 세 가지를 센다. 저장소 뿌리에서  bash check.sh

echo
echo "① 창구·엔진에 SQL이 있으면 안 된다"
if grep -rnE "SELECT |INSERT |UPDATE |DELETE FROM|CREATE TABLE" --include=*.py app/features app/engine app/services; then
    echo "  X 위에 나온 곳들을 app/tables/ 로 내려야 한다"
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
