## 패키지 설치
가상환경이 활성화된 상태에서 실행:

pip install --upgrade pip  
pip install fastapi uvicorn python-dotenv google-generativeai pydantic

## 가상환경(venv) 생성 & 활성화
가상환경 생성 (최상위 폴더에서 실행) python3 -m venv venv

가상환경 활성화 source venv/bin/activate

## FastAPI 실행
uvicorn main:app --reload  
http://127.0.0.1:8000/docs

## 📝 Commit Message 규칙

| 타입(Type) | 설명(Description) |
|------------|-------------------|
| **Feat** | 새로운 기능을 추가한 경우 |
| **Fix** | 에러·버그를 수정한 경우 |
| **Design** | CSS 등 UI 디자인을 변경한 경우 |
| **HOTFIX** | 급하게 치명적인 에러를 즉시 수정한 경우 |
| **Style** | 코드 포맷 변경, 세미콜론 누락 등 **로직 변경 없는** 스타일 수정 |
| **Refactor** | 기능 변화 없이 코드를 리팩토링한 경우 |
| **Comment** | 주석 추가 또는 변경 |
| **Docs** | 문서를 수정한 경우 (README 등) |
| **Test** | 테스트 코드 추가·변경·리팩토링 |
| **Chore** | 기타 변경사항 (빌드, 패키지, 설정 파일 수정 등) |
| **Rename** | 파일·폴더명을 수정하거나 옮기는 경우 |
| **Remove** | 파일을 삭제하는 작업만 수행한 경우 |
