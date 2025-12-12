# 🤖 TripTalk AI Server - FastAPI

> Google Gemini 2.0 Flash 기반 맞춤형 여행 일정 생성 AI 서버

## 📋 목차
- [프로젝트 개요](#-프로젝트-개요)
- [주요 기능](#-주요-기능)
- [기술 스택](#-기술-스택)
- [시스템 아키텍처](#-시스템-아키텍처)
- [데이터 모델](#-데이터-모델)
- [API 명세](#-api-명세)
- [설치 및 실행](#-설치-및-실행)
- [Spring Boot 연동](#-spring-boot-연동)

---

## 🎯 프로젝트 개요

**TripTalk AI Server**는 사용자의 여행 스타일, 목적지, 예산, 동행인 정보를 기반으로 
Google Gemini 2.0 Flash API를 활용하여 **맞춤형 여행 일정을 자동 생성**하는 FastAPI 기반 AI 서버입니다.

생성된 여행 계획은 JSON 파일로 임시 저장되며, 사용자 확인 후 Spring Boot 서버로 전송되어 MySQL DB에 영구 저장됩니다.

### 핵심 가치
- 🤖 **AI 맞춤 추천**: Google Gemini 2.0 Flash 기반 개인화된 여행 일정 생성
- 📅 **상세 일정**: 일별/시간대별 구체적인 여행 계획 (식당, 관광지, 교통편 포함)
- 🏨 **교통편/숙소 정보**: 출발편, 귀환편, 숙소 예약 정보 자동 생성
- 🔗 **Spring Boot 연동**: RESTful API 통신으로 완벽한 시스템 통합

---

## ✨ 주요 기능

### 1. 🗺️ AI 여행 일정 생성
- **Google Gemini 2.0 Flash API 연동**
  - 사용자 입력 기반 프롬프트 생성
  - 자연어 기반 구조화된 JSON 응답
  - 9가지 여행 스타일 분석 (체험·액티비티, 자연과 함께, 여유롭게 힐링 등)
  
- **상세 일정 생성**
  - 일별 스케줄 (DailySchedule)
  - 시간대별 상세 계획 (ScheduleItem)
  - 실제 식당·관광지 이름 포함
  - 교통편 정보 (항공사명, 출발/도착 시간, 가격)
  - 숙소 정보 (호텔명, 주소, 1박 가격)
  
- **하이라이트 추출**
  - 여행의 주요 포인트 3-5개 자동 생성
  - 각 하이라이트 100자 이내

### 2. 📋 여행 계획 관리
- **JSON 파일 기반 저장**
  - `data/travel_data.json`에 영구 저장
  - UUID 기반 고유 ID 생성
  - 중복 방지 로직 (동일 조건 시 업데이트)
  
- **여행 목록 조회**
  - 전체 여행 목록 반환
  - 특정 여행 상세 조회

### 3. 🔗 Spring Boot 연동
- **HTTP POST 통신**
  - FastAPI → Spring Boot REST API 호출
  - JSON 데이터 자동 직렬화 (camelCase 변환)
  - 에러 핸들링 및 재시도 로직
  
- **데이터 변환**
  - Pydantic 모델 → JSON (by_alias=True)
  - snake_case → camelCase 자동 변환
  - Spring Boot DTO 형식에 맞춘 데이터 구조

---

## 🛠 기술 스택

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI 0.115.5
- **AI**: Google Gemini 2.0 Flash API
- **Data Validation**: Pydantic 2.10.3
- **HTTP Client**: httpx 0.28.1
- **CORS**: FastAPI CORS Middleware

### Storage
- **File System**: JSON 파일 기반 데이터 저장
- **Data Format**: UTF-8 JSON (ensure_ascii=False)

### External APIs
- **Google Gemini API**: Gemini 2.0 Flash 기반 여행 일정 생성
- **Spring Boot API**: 여행 계획 DB 저장

---

## 🏗 시스템 아키텍처

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Client    │ ───> │   FastAPI    │ ───> │   Google    │
│  (Mobile)   │      │  (AI Server) │      │ Gemini 2.0  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ├──────> Spring Boot API
                            │        (DB 저장)
                            │
                            └──────> data/travel_data.json
                                     (임시 저장)
```

### 데이터 플로우
```
1. 사용자 입력 (목적지, 기간, 예산, 동행인, 여행 스타일)
   ↓
2. FastAPI → Google Gemini 2.0 Flash API 요청
   ↓
3. Gemini → 구조화된 여행 계획 JSON 생성
   ↓
4. FastAPI → Pydantic 모델 검증 및 저장 (travel_data.json)
   ↓
5. 사용자 확인 후 "저장" 버튼 클릭
   ↓
6. FastAPI → Spring Boot API 호출 (POST /api/trip-plan/from-fastapi)
   ↓
7. Spring Boot → MySQL DB 저장
```

---

## 📦 데이터 모델

### Pydantic 모델 구조

#### TravelStyle (여행 스타일)
```python
class TravelStyle(BaseModel):
    category: str  # "체험·액티비티", "자연과 함께", "여유롭게 힐링" 등
```

#### ScheduleItem (상세 일정)
```python
class ScheduleItem(BaseModel):
    order_index: int      # 순서
    time: str             # "09:00"
    title: str            # "김포공항 출발"
    description: str      # "진에어 LJ313편으로 제주 출발"
```

#### DailySchedule (일별 일정)
```python
class DailySchedule(BaseModel):
    day: int                          # 1, 2, 3...
    date: str                         # "2025-12-13"
    schedules: List[ScheduleItem]     # 상세 일정 리스트
```

#### TripTransportation (교통편)
```python
class TripTransportation(BaseModel):
    origin: str          # "김포공항"
    destination: str     # "제주공항"
    name: str            # "진에어LJ313"
    price: int           # 45000
```

#### TripAccommodation (숙소)
```python
class TripAccommodation(BaseModel):
    name: str            # "제주신화월드 호텔"
    address: str         # "제주 서귀포시..."
    pricePerNight: int   # 200000
```

#### TripPlan (전체 여행 계획)
```python
class TripPlan(BaseModel):
    title: str                                      # "제주도 2박 3일 우정 여행"
    destination: str                                # "제주도"
    departure: str                                  # "서울"
    startDate: str (alias='start_date')            # "2025-12-13"
    endDate: str (alias='end_date')                # "2025-12-15"
    companions: str                                 # "친구"
    budget: str                                     # "70만원"
    travelStyles: List[TravelStyle]                # 여행 스타일 리스트
    highlights: List[TripHighlight]                # 하이라이트 리스트
    fullPlan: str (alias='full_plan')              # 전체 텍스트 계획
    dailySchedules: List[DailySchedule]            # 일별 일정
    outboundTransportation: TripTransportation     # 출발 교통편
    returnTransportation: TripTransportation       # 귀환 교통편
    accommodations: List[TripAccommodation]        # 숙소 리스트
```

---

## 📡 API 명세

### Base URL
```
Production: http://52.78.55.147:8000
Local Development: http://localhost:8000
```

### 1. 여행 계획 생성

#### 여행 계획 생성 요청
```http
POST /Travel-Plan
Content-Type: application/json

{
  "companions": "친구",
  "departure": "서울",
  "destination": "제주도",
  "start_date": "2025-12-13",
  "end_date": "2025-12-15",
  "style": ["자연과 함께", "여유롭게 힐링"],
  "budget": "50만원~70만원"
}
```

**응답 예시:**
```json
{
  "travel_id": "37488429-3759-4320-9603-a0db0277bd56",
  "title": "제주도 2박 3일 우정 여행",
  "destination": "제주도",
  "departure": "서울",
  "start_date": "2025-12-13",
  "end_date": "2025-12-15",
  "companions": "친구",
  "budget": "70만원",
  "travel_styles": [
    {"category": "자연과 함께"}
  ],
  "highlights": [
    {"content": "겨울 바다 만끽하며 우정 스냅 촬영"},
    {"content": "따뜻한 온천으로 피로 풀기"},
    {"content": "제주 흑돼지 맛집 탐방"}
  ],
  "daily_schedules": [
    {
      "day": 1,
      "date": "2025-12-13",
      "schedules": [
        {
          "order_index": 1,
          "time": "07:30",
          "title": "비행기 탑승",
          "description": "김포공항에서 진에어 LJ313편으로 제주로 출발"
        }
      ]
    }
  ],
  "outbound_transportation": {
    "origin": "김포공항",
    "destination": "제주공항",
    "name": "진에어LJ313",
    "price": 45000
  },
  "return_transportation": {...},
  "accommodations": [...]
}
```

### 2. 여행 목록 조회

#### 전체 여행 목록
```http
GET /travel-summaries
```

#### 특정 여행 상세 조회
```http
GET /travel-summary/{travel_id}
```

### 3. Spring Boot 연동

#### 여행 계획 저장 (Spring Boot로 전송)
```http
POST /save-plan/{travel_id}

Response:
{
  "success": true,
  "message": "여행 계획이 Spring Boot 서버에 성공적으로 저장되었습니다.",
  "spring_response": {
    "id": 123,
    "title": "제주도 2박 3일 우정 여행",
    ...
  },
  "fastapi_travel_id": "37488429-3759-4320-9603-a0db0277bd56"
}
```

---

## 🚀 설치 및 실행

### 배포 환경

현재 **AWS EC2 (52.78.55.147)에 Docker Compose로 배포 운영 중**입니다.

#### 서버 정보
- **FastAPI Server**: http://52.78.55.147:8000
- **Spring Boot Server**: http://52.78.55.147:8080

#### Docker Compose로 실행
```bash
# 서버에서 실행
cd /path/to/TripTalk
docker-compose up -d

# 로그 확인
docker-compose logs -f fastapi

# 재시작
docker-compose restart fastapi

# 중지
docker-compose down
```

#### 환경변수 설정
`.env` 파일:
```bash
# Google Gemini API Key
GOOGLE_API_KEY=your-google-gemini-api-key-here

# Spring Boot Server URL (배포 환경)
SPRING_BOOT_URL=http://52.78.55.147:8080
```

---

### 로컬 개발 환경 (선택사항)

#### 요구사항
- Python 3.11 이상
- Google Gemini API Key

#### 1. 가상환경 생성 및 활성화
```bash
# 가상환경 생성
python3 -m venv venv

# 활성화 (macOS/Linux)
source venv/bin/activate
```

#### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

**requirements.txt:**
```txt
fastapi==0.115.5
uvicorn==0.34.0
pydantic==2.10.3
google-generativeai==0.8.3
httpx==0.28.1
python-dotenv==1.0.1
```

#### 3. 환경변수 설정 (로컬)
`.env` 파일:
```bash
GOOGLE_API_KEY=your-api-key
SPRING_BOOT_URL=http://localhost:8080
```

#### 4. 로컬 실행
```bash
# 개발 모드
uvicorn AI_Chat:app --reload --host 0.0.0.0 --port 8000
```

#### 5. API 테스트
```bash
# 배포 서버 테스트
curl http://52.78.55.147:8000/travel-summaries

# 로컬 테스트
curl http://localhost:8000/travel-summaries
```

---

## 🐳 배포 환경 (Docker)

### 현재 배포 상태

**Docker Compose**로 운영 중이며, `docker-compose.yml` 설정:

```yaml
version: "3.9"

services:
  fastapi:
    build: .
    container_name: fastapi-server
    ports:
      - "8000:8000"
    restart: always
    environment:
      GOOGLE_API_KEY: ${GOOGLE_API_KEY}
      SPRING_BOOT_URL: http://52.78.55.147:8080
    volumes:
      - ./data:/app/data
      - ./outputs:/app/outputs
```

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "AI_Chat:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 배포 관리 명령어
```bash
# 서버 배포 (처음 또는 코드 변경 시)
docker-compose up -d --build

# 서버 재시작
docker-compose restart

# 로그 확인
docker-compose logs -f fastapi

# 서버 중지
docker-compose down

# 컨테이너 상태 확인
docker-compose ps
```

---

## 🔗 Spring Boot 연동

### 연동 플로우

```
1. FastAPI에서 여행 계획 생성 → travel_data.json 저장
2. 사용자 확인 후 "저장" 버튼 클릭
3. FastAPI → Spring Boot API 호출
   POST http://52.78.55.147:8080/api/trip-plan/from-fastapi
4. Spring Boot → MySQL DB 저장
5. 저장 결과 반환
```

### 데이터 변환 과정

**FastAPI (snake_case) → Spring Boot (camelCase)**

```python
# TripPlan 모델 (FastAPI)
plan_data = plan_response.model_dump(by_alias=True)
# startDate, endDate, dailySchedules... (camelCase)

# Spring Boot로 전송 (배포 환경)
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://52.78.55.147:8080/api/trip-plan/from-fastapi",
        json=plan_data
    )
```

**Spring Boot CreateFromFastAPIDTO:**
```java
public static class CreateFromFastAPIDTO {
    private String startDate;  // FastAPI에서 "startDate" 전송
    private String endDate;
    private String budget;
    private List<DailyScheduleDTO> dailySchedules;
    // ...
}
```

### 배포 환경 구성

```
┌─────────────────┐
│   Client App    │
│   (Mobile/Web)  │
└────────┬────────┘
         │
         ├──────────────────────┬─────────────────────┐
         │                      │                     │
         ▼                      ▼                     ▼
┌─────────────────┐  ┌──────────────────┐  ┌─────────────────┐
│  FastAPI Server │  │ Spring Boot API  │  │   Google        │
│   (Docker)      │─>│  (AWS EC2)       │  │   Gemini API    │
│   Port: 8000    │  │  52.78.55.147    │  └─────────────────┘
└─────────────────┘  └────────┬─────────┘
         │                     │
         ▼                     ▼
┌─────────────────┐  ┌──────────────────┐
│ travel_data.json│  │   MySQL (RDS)    │
│   (로컬 저장)     │  │   (영구 저장)       │
└─────────────────┘  └──────────────────┘
```

---

## 📂 프로젝트 구조

```
TripTalk/
├── AI_Chat.py              # 메인 FastAPI 애플리케이션
├── main.py                 # 애플리케이션 엔트리 포인트
├── requirements.txt        # Python 패키지 의존성
├── .env                    # 환경변수 (OpenAI API Key)
├── Dockerfile              # Docker 이미지 빌드 파일
├── docker-compose.yml      # Docker Compose 설정
├── README.md               # 프로젝트 문서
├── data/
│   └── travel_data.json    # 여행 계획 JSON 저장소
└── outputs/
    └── latest_plan.md      # 최신 여행 계획 마크다운
```

---

## 🔧 주요 기술적 특징

### 1. Pydantic Field Aliases
- JSON 파일: `start_date`, `end_date` (snake_case)
- Python 모델: `startDate`, `endDate` (camelCase)
- Spring Boot 전송: `startDate`, `endDate` (camelCase)

```python
class TripPlan(BaseModel):
    startDate: str = Field(..., alias='start_date')
    endDate: str = Field(..., alias='end_date')
```

### 2. Google Gemini Structured Output
- Gemini 2.0 Flash의 자연어 기반 JSON 생성
- Pydantic 모델과 일치하는 구조화된 응답
- 파싱 에러 최소화

### 3. 중복 방지 로직
- 동일 조건 (목적지, 기간, 동행자, 예산, 스타일) 시 기존 데이터 업데이트
- 다른 조건 시 새 UUID 생성

### 4. 에러 핸들링
- Spring Boot 통신 실패 시 재시도
- Google Gemini API 타임아웃 처리
- JSON 파싱 에러 복구

---

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

### 예시
```bash
git commit -m "Feat: Google Gemini 2.0 Flash 여행 계획 생성 API 추가"
git commit -m "Fix: Spring Boot 연동 시 camelCase 변환 오류 수정"
git commit -m "Docs: README 데이터 모델 섹션 추가"
```

---

## 🔄 버전 히스토리

### v1.0.0 (2025-12-12)
- ✅ Google Gemini 2.0 Flash 기반 여행 계획 생성
- ✅ Pydantic 모델 기반 데이터 검증
- ✅ JSON 파일 기반 영구 저장
- ✅ Spring Boot API 연동 완료
- ✅ camelCase/snake_case 자동 변환

---

**🤖 TripTalk AI Server - 당신만의 완벽한 여행을 AI가 설계합니다!**
