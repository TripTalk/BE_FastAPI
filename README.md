# 🎯 TripTalk 여행 정보 저장 시스템

FastAPI 기반의 여행 계획 생성 및 요약 정보 저장 시스템입니다.

## 📋 주요 기능

✅ **여행 요약 정보 자동 추출 및 저장**  
✅ **중복 방지 - 동일 조건 시 업데이트, 새 조건 시 신규 생성**  
✅ **파일 기반 데이터 지속성**  
✅ **RESTful API 제공**  

## 🗂️ 프로젝트 구조

```
TripTalk/
├── AI_Chat.py              # 메인 FastAPI 애플리케이션
├── README.md               # 프로젝트 설명서
├── .env                    # 환경변수 (Google API Key)
├── data/                   # 데이터 저장 폴더
│   └── travel_summaries.json  # 여행 요약 정보
└── outputs/                # 출력 파일 폴더
    └── latest_plan.md      # 최신 여행 계획
```

## 🚀 실행 방법

### 1. 환경 설정
```bash
# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 패키지 설치
pip install fastapi uvicorn python-dotenv google-generativeai pydantic
```

### 2. 환경변수 설정
`.env` 파일에 Google API Key 설정:
```
GOOGLE_API_KEY=your_api_key_here
```

### 3. 서버 실행
```bash
uvicorn AI_Chat:app --reload
```

## 📱 API 사용법

### 여행 계획 생성
**POST** `/Travel-Plan`

```json
{
    "companions": "연인",
    "departure": "서울", 
    "destination": "제주도",
    "start_date": "2024.03.15",
    "end_date": "2024.03.18",
    "style": ["힐링", "자연과 함께"],
    "budget": "50만~100만원"
}
```

### 여행 목록 조회
**GET** `/travel-summaries`

### 특정 여행 조회
**GET** `/travel-summary/{travel_id}`

## 💾 데이터 관리 방식

### 📌 중복 방지 로직
- **동일한 조건** (목적지, 출발지, 기간, 동행자, 예산, 스타일이 모두 같음)으로 여행 계획을 다시 생성하면 **기존 데이터를 업데이트**
- **다른 조건**이면 **새로운 여행 정보 생성**

### 📊 저장되는 정보
- `id`: 여행 고유 식별자
- `title`: 여행 제목
- `destination`: 목적지
- `departure`: 출발지  
- `start_date`, `end_date`: 여행 기간
- `companions`: 동행자 (연인, 가족, 친구 등)
- `budget`: 예산
- `travel_styles`: 여행 스타일 배열
- `highlights`: 여행 하이라이트 (3-5개)
- `full_plan`: 전체 여행 계획 (API 응답에서 제외)

### 📱 API 응답 형태
```json
{
  "id": "uuid-string",
  "title": "🌸 교토 가족 3박 4일 문화 힐링 여행 🌸",
  "destination": "교토",
  "departure": "부산",
  "start_date": "2025.03.01", 
  "end_date": "2025.03.04",
  "companions": "가족",
  "budget": "60만~90만원",
  "travel_styles": ["문화탐방", "힐링"],
  "highlights": ["교토 탐방", "맛집 투어", "문화 체험"]
}
```

## 🔮 향후 연동 계획

프론트엔드 연동 시 이 API를 활용하여:
1. **사용자 입력 폼** → API 요청 데이터 변환
2. **여행 카드 UI** → 저장된 요약 정보로 렌더링  
3. **AI 이미지 생성** → `image_description` 활용

---

**✨ 깔끔하고 효율적인 여행 정보 관리 시스템이 완성되었습니다!**

## 📝 커밋 메시지 규칙

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

### 예시
```
Feat: 여행 계획 생성 API 추가
