from fastapi import FastAPI
from fastapi import Body
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path
import os

# 🔹 환경 변수 로드
load_dotenv(dotenv_path=Path(__file__).parent / ".env")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# 🔹 FastAPI 앱 생성
app = FastAPI()

# 🔹 공통 출력 예시 (한 곳만 수정해도 두 API에 자동 반영)
example_prompt = """
[출력 예시]

🏖️ **여행 요약**
- **제목:** 제주도 3박 4일 힐링 여행  
- **여행지:** 제주도  
- **기간:** 2024.03.15 ~ 2024.03.18  
- **동행자:** 연인  
- **예산:** 50만~100만원  
- **하이라이트:**  
  • 성산일출봉 일출 감상  
  • 한라산 트레킹  
  • 오션뷰 카페 투어  
  • 제주 전통 맛집 탐방  
- **대표 이미지 설명:** 한라산과 푸른 바다를 배경으로 한 제주 가을 풍경

---

📅 **1일차**
- **오전:** 제주공항 도착 → 숙소 체크인  
  ☕ 카페: "앤트러사이트 제주" (대표 메뉴: 콜드브루, 영업시간 09:00~19:00, 월요일 휴무)
- **오후:** 성산일출봉 등반 및 오션뷰 감상  
  🍽️ 점심: "연돈볼카츠" (대표 메뉴: 돈카츠, 영업시간 11:00~20:00)
- **저녁:** 해안도로 드라이브 & 숙소 휴식  
🏨 숙소: "신라스테이 제주" (1박 약 120,000원)

📅 **2일차**
...

💬 **예산 피드백 (필요한 경우만):**  
현재 예산으로 중상급 숙소 선택 시 식비를 약간 조정하는 것을 추천합니다.
"""

# 🔹 사용자 입력 데이터 구조 정의
class TravelInput(BaseModel):
    companions: str
    departure: str
    destination: str
    start_date: str
    end_date: str
    style: list[str]
    budget: str

class FeedbackInput(BaseModel):
    message: str  # ✅ 사용자의 피드백 내용

# 🔹 전역 변수로 최신 여행 일정 저장
latest_plan = None

# 🔹 1️⃣ 여행 계획 자동 생성 API
@app.post("/Travel-Plan")
async def create_travel_plan(data: TravelInput = Body(...)):
    global latest_plan  # ✅ 전역 변수 선언 추가

    prompt = f"""
당신은 전문 여행 플래너이자 컨시어지입니다.  
아래 사용자의 여행 정보를 바탕으로 **실제 존재하는 장소, 숙소, 맛집**을 포함한 여행 일정을 작성하고,  
상단에는 카드 형태로 표현할 수 있는 **요약 정보(하이라이트)**를 함께 생성하세요.

---

[여행 정보]
- 출발지: {data.departure}
- 여행지: {data.destination}
- 동행자: {data.companions}
- 여행 기간: {data.start_date} ~ {data.end_date}
- 여행 스타일: {', '.join(data.style)}
- 예산: {data.budget}

---

[요청 조건]
1. **출력은 두 부분으로 구성하세요.**
   - (1) 여행 요약 카드 섹션
   - (2) 상세 일정 섹션
2. 여행 요약 카드에는 다음 정보를 포함하세요.
   - 여행 제목 (예: “제주도 3박 4일 힐링 여행”)
   - 여행지 이름
   - 기간 (YYYY.MM.DD 형식)
   - 동행자 유형
   - 예산 범위
   - 여행 하이라이트 (3~5개 핵심 키워드 문장형, 예: “성산일출봉 일출 감상”, “한라산 트레킹”, “오션뷰 카페 투어”)
   - 대표 이미지 설명 (AI가 이미지를 생성할 수 있도록 간단한 문장으로 작성. 예: “한라산과 바다를 배경으로 한 가을 제주의 풍경”)
3. 상세 일정은 일자별로 오전/오후/저녁 단위로 나누고 짧은 설명을 포함하세요.
4. 추천 장소(관광지, 맛집, 카페 등)는 **실제 존재하는 곳**으로 구성하고 아래 정보를 포함하세요.
   - 이름 (실존)
   - 대표 메뉴 또는 활동
   - 영업시간 및 휴무일 (휴무일일 경우 대체 장소 제시)
   - 위치(지역명 또는 주소)
5. 숙소는 실제 숙소명과 1박 평균 요금(원 또는 현지 통화)을 명시하세요.
6. 전체 일정은 주어진 예산 내에서 현실적으로 구성하세요.
7. 예산이 명확히 부족하거나 과도할 때만 간단히 피드백을 추가하세요.

---

[출력 예시]

{example_prompt}

---
이제 위 형식을 기반으로, 실제 장소와 최신 정보를 반영한 여행 일정을 작성하세요.
"""



    model = genai.GenerativeModel("models/gemini-2.0-flash")
    response = model.generate_content(prompt)
    
    # ✅ 생성된 일정 저장
    latest_plan = response.text
    return {"plan": latest_plan}

# 🔹 2️⃣ 피드백(대화형 수정) 기능 추가
chat_history = []  # 대화 저장용 리스트 (간단 테스트용)

@app.post("/feedback")
async def feedback(data: FeedbackInput):
    global latest_plan

    if latest_plan is None:
        return {"error": "아직 생성된 여행 일정이 없습니다. 먼저 /Travel-Plan을 호출하세요."}
    

    # ✅ 프롬프트 추가
    prompt = f"""
당신은 전문 여행 플래너이자 컨시어지입니다.
아래의 **기존 여행 일정**을 기반으로 사용자의 피드백을 반영하여 새로운 일정을 작성하세요.

---

[기존 여행 일정]
{latest_plan}

---

[사용자 피드백]
{data.message}

---

🎯 **목표**
1. 기존 여행지와 전체 일정 구조는 그대로 유지합니다.  
2. 피드백을 다음 두 가지 유형으로 구분해 반영하세요:
   - **제약 조건(Constraint)**: 음식, 예산, 날짜, 활동 불가 등의 제한이 명확히 제시된 경우  
     → 반드시 100% 반영 (예: “해산물 못 먹어요”, “비건이에요”, “비 오는 날은 실내 일정으로 변경해주세요.”)
   - **선호/요청(Preference)**: 특정 활동/음식/장소/분위기에 대한 제안, 변경 희망  
     → 기존 일정의 맥락과 균형을 유지하면서 가능한 범위 내에서 자연스럽게 반영  
       (예: “좀 더 여유로운 일정으로 바꿔주세요.”, “카페 시간을 늘려주세요.”, “야경 명소를 넣어주세요.”)
3. 기존 일정은 다시 보여주지 말고, **수정된 여행 일정만** 텍스트로 출력하세요.
4. “알겠습니다” 같은 설명 문장은 포함하지 마세요.
5. 모든 계획은 실제 존재하는 장소, 숙소, 음식점을 기반으로 작성되어야 합니다.

---

🧩 **출력 규칙**
- 전체 포맷은 기존 여행 일정과 동일한 형식으로 출력합니다.  
  (제목, 날짜, 일정 순서, 표, 리스트, 이모지 등 포함)

---

[출력 예시]

{example_prompt}

---
이제 위 형식을 기반으로, 사용자의 피드백을 반영한 여행 일정을 작성하세요.
"""

    model = genai.GenerativeModel("models/gemini-2.0-flash")
    response = model.generate_content(prompt)
    
    # ✅ 최신 일정 갱신
    latest_plan = response.text
    return {"reply": latest_plan}