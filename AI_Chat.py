from fastapi import FastAPI
from fastapi import Body
from pydantic import BaseModel
from typing import List, Dict, Optional
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path
import os
import json
from datetime import datetime, timedelta
import uuid
import re

BASE_DIR = Path(__file__).parent
load_dotenv(dotenv_path=BASE_DIR / ".env")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()
class TravelInput(BaseModel):
    companions: str
    departure: str
    destination: str
    start_date: str
    end_date: str
    style: list[str]
    budget: str

class FeedbackInput(BaseModel):
    message: str

class TimelineItem(BaseModel):
    time: str
    title: str
    description: str

class DaySchedule(BaseModel):
    day: int
    date: str
    schedules: List[TimelineItem]

class TravelSummary(BaseModel):
    id: str
    title: str
    destination: str
    departure: str
    start_date: str
    end_date: str
    companions: str
    budget: str
    travel_styles: List[str]
    highlights: List[str]
    full_plan: str
    daily_schedules: List[DaySchedule] = []
class TravelSummaryResponse(BaseModel):
    id: str
    title: str
    destination: str
    departure: str
    start_date: str
    end_date: str
    companions: str
    budget: str
    travel_styles: List[str]
    highlights: List[str]

OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
TRAVEL_SUMMARIES_FILE = DATA_DIR / "travel_data.json"
travel_summaries_store: Dict[str, TravelSummary] = {}


def load_travel_summaries() -> None:
    """파일에서 여행 요약 정보를 로드"""
    global travel_summaries_store
    if TRAVEL_SUMMARIES_FILE.exists():
        try:
            with open(TRAVEL_SUMMARIES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                travel_summaries_store = {
                    k: TravelSummary(**v) for k, v in data.items()
                }
        except Exception as e:
            print(f"여행 요약 데이터 로드 실패: {e}")
            travel_summaries_store = {}


def save_travel_summaries() -> None:
    """여행 요약 정보를 파일에 저장"""
    try:
        data = {k: v.dict() for k, v in travel_summaries_store.items()}
        with open(TRAVEL_SUMMARIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"여행 요약 데이터 저장 실패: {e}")


def save_plan_to_file(content: str, filename: str = "latest_plan.md") -> None:
    """가장 최신 일정을 파일로 저장해서 에디터(VSCode 등)에서 확인 가능하게 함."""
    (OUTPUT_DIR / filename).write_text(content, encoding="utf-8")


def extract_timeline_from_plan(plan: str, original_input: TravelInput) -> List[DaySchedule]:
    """AI가 생성한 JSON 타임라인 추출"""
    daily_schedules = []
    
    try:
        start_date = datetime.strptime(original_input.start_date.replace("/", "."), "%Y.%m.%d")
    except ValueError:
        try:
            start_date = datetime.strptime(original_input.start_date, "%Y-%m-%d")
        except ValueError:
            start_date = datetime.now()
    
    # JSON 블록 추출
    json_pattern = r'```json\s*\n(.*?)\n```'
    json_matches = re.findall(json_pattern, plan, re.DOTALL)
    
    if json_matches:
        try:
            for json_str in json_matches:
                timeline_data = json.loads(json_str)
                
                if isinstance(timeline_data, dict) and 'day' in timeline_data:
                    day_num = timeline_data['day']
                    day_date = (start_date + timedelta(days=day_num-1)).strftime("%Y.%m.%d")
                    
                    schedules = []
                    for item in timeline_data.get('schedules', []):
                        schedules.append(TimelineItem(
                            time=item['time'],
                            title=item['title'],
                            description=item['description']
                        ))
                    
                    daily_schedules.append(DaySchedule(
                        day=day_num,
                        date=day_date,
                        schedules=schedules
                    ))
                
                elif isinstance(timeline_data, list):
                    for day_data in timeline_data:
                        if 'day' in day_data:
                            day_num = day_data['day']
                            day_date = (start_date + timedelta(days=day_num-1)).strftime("%Y.%m.%d")
                            
                            schedules = []
                            for item in day_data.get('schedules', []):
                                schedules.append(TimelineItem(
                                    time=item['time'],
                                    title=item['title'],
                                    description=item['description']
                                ))
                            
                            daily_schedules.append(DaySchedule(
                                day=day_num,
                                date=day_date,
                                schedules=schedules
                            ))
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
    
    return daily_schedules


def extract_summary_from_plan(plan: str, original_input: TravelInput) -> TravelSummary:
    """생성된 여행 계획에서 요약 정보 추출"""
    travel_id = str(uuid.uuid4())
    
    lines = plan.split('\n')
    title = f"{original_input.destination} 여행"
    highlights = []
    for line in lines:
        if "**제목:**" in line:
            title = line.split("**제목:**")[-1].strip()
            # 괄호 제거 (예: "제주도 여행 (3박4일)" -> "제주도 여행")
            if '(' in title:
                title = title.split('(')[0].strip()
            break
        elif "제목:" in line and not "**" in line:
            title = line.split("제목:")[-1].strip()
            # 괄호 제거
            if '(' in title:
                title = title.split('(')[0].strip()
            break
        elif line.strip().startswith("#") and ("여행" in line or "관광" in line or "투어" in line):
            title = line.strip()
            title = title.replace("#", "").strip()
            # 괄호 제거
            if '(' in title:
                title = title.split('(')[0].strip()
            break
    in_highlight_section = False
    for line in lines:
        if "하이라이트" in line or "**하이라이트:**" in line:
            in_highlight_section = True
            continue
        elif in_highlight_section:
            if line.strip().startswith("•") or line.strip().startswith("-"):
                highlight = line.strip().replace("•", "").replace("-", "").strip()
                if highlight:
                    highlights.append(highlight)
            elif line.strip().startswith("**") or line.strip() == "":
                continue
            else:
                in_highlight_section = False
    
    # 타임라인 정보 추출
    daily_schedules = extract_timeline_from_plan(plan, original_input)
    
    return TravelSummary(
        id=travel_id,
        title=title,
        destination=original_input.destination,
        departure=original_input.departure,
        start_date=original_input.start_date,
        end_date=original_input.end_date,
        companions=original_input.companions,
        budget=original_input.budget,
        travel_styles=original_input.style,
        highlights=highlights if highlights else [f"{original_input.destination} 탐방", "맛집 투어", "문화 체험"],
        full_plan=plan,
        daily_schedules=daily_schedules
    )


def find_existing_travel(data: TravelInput) -> Optional[str]:
    """동일한 조건의 기존 여행이 있는지 확인"""
    for travel_id, travel in travel_summaries_store.items():
        if (travel.destination == data.destination and 
            travel.departure == data.departure and
            travel.start_date == data.start_date and 
            travel.end_date == data.end_date and
            travel.companions == data.companions and
            travel.budget == data.budget and
            set(travel.travel_styles) == set(data.style)):
            return travel_id
    return None


example_prompt = """
[출력 예시]

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
- **이동수단:** ✈️ 비행기 "김포공항 → 제주공항" (편도 약 60,000원, 소요시간 1시간)
- **오전:** 제주공항 도착 → 렌터카 픽업 (1일 약 50,000원) → 숙소 체크인  
  ☕ 카페: "앤트러사이트 제주" (대표 메뉴: 콜드브루, 영업시간 09:00~19:00, 월요일 휴무)
- **오후:** 성산일출봉 등반 및 오션뷰 감상  
  🍽️ 점심: "연돈볼카츠" (대표 메뉴: 돈카츠, 영업시간 11:00~20:00)
- **저녁:** 해안도로 드라이브 & 숙소 휴식  
🏨 숙소: "신라스테이 제주" (1박 약 120,000원)

```json
{
  "day": 1,
  "schedules": [
    {"time": "09:00", "title": "김포공항 도착", "description": "비행기 탑승"},
    {"time": "10:00", "title": "렌터카 픽업", "description": "차량 대여"},
    {"time": "11:00", "title": "앤트러사이트 제주", "description": "카페"},
    {"time": "12:30", "title": "연돈볼카츠", "description": "점심"},
    {"time": "14:00", "title": "성산일출봉 등반", "description": "등산과 전망"},
    {"time": "15:00", "title": "신라스테이 제주", "description": "호텔 체크인"},
    {"time": "17:00", "title": "해안도로 드라이브", "description": "해변 드라이브"},
    {"time": "19:00", "title": "해녀의 집", "description": "저녁"},
    {"time": "21:00", "title": "숙소 휴식", "description": "자유시간"}
  ]
}
```

📅 **2일차**
- **오전:** 숙소 체크아웃 (10:00) → 관광 시작
...

```json
{
  "day": 2,
  "schedules": [
    {"time": "10:00", "title": "신라스테이 제주", "description": "호텔 체크아웃"},
    {"time": "11:00", "title": "한라산 트레킹", "description": "자연 탐방"},
    {"time": "13:00", "title": "산방산 맛집", "description": "해물칼국수 점심"}
  ]
}
```

💬 **예산 피드백 (필요한 경우만):**  
현재 예산으로 중상급 숙소 선택 시 식비를 약간 조정하는 것을 추천합니다.
"""

latest_plan = None
chat_history: list[str] = []

load_travel_summaries()
@app.post("/Travel-Plan")
async def create_travel_plan(data: TravelInput = Body(...)):
    global latest_plan, chat_history
    chat_history = []

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
   - 출발지
   - 여행지 이름
   - 기간 (YYYY.MM.DD 형식)
   - 동행자 유형
   - 예산 범위
   - 여행 하이라이트 (3~5개 핵심 키워드 문장형, 예: “성산일출봉 일출 감상”, “한라산 트레킹”, “오션뷰 카페 투어”)
   - 대표 이미지 설명 (AI가 이미지를 생성할 수 있도록 간단한 문장으로 작성. 예: “한라산과 바다를 배경으로 한 가을 제주의 풍경”)
3. 상세 일정은 일자별로 오전/오후/저녁 단위로 나누고 짧은 설명을 포함하세요.
4. **이동수단은 각 일자의 상단에 명시하세요.**
   - 실제 이용 가능한 이동수단 (비행기, 기차, 고속버스, 택시, 렌터카, 대중교통 등)
   - 출발지 → 목적지 경로
   - 편도 또는 왕복 요금(원 또는 현지 통화)
   - 소요 시간
   - 예: "✈️ 비행기 '김포공항 → 제주공항' (편도 약 60,000원, 소요시간 1시간)"
   - 예: "🚄 KTX '서울역 → 부산역' (편도 약 59,800원, 소요시간 2시간 30분)"
   - 예: "🚌 고속버스 '서울고속터미널 → 강릉' (편도 약 18,000원, 소요시간 3시간)"
   - 예: "🚗 렌터카 (1일 약 50,000원)"
5. 추천 장소(관광지, 맛집, 카페 등)는 **실제 존재하는 곳**으로 구성하고 아래 정보를 포함하세요.
   - 이름 (실존)
   - 대표 메뉴 또는 활동
   - 영업시간 및 휴무일 (휴무일일 경우 대체 장소 제시)
   - 위치(지역명 또는 주소)
6. 숙소는 실제 숙소명과 1박 평균 요금(원 또는 현지 통화)을 명시하세요.
7. 전체 일정은 주어진 예산 내에서 현실적으로 구성하세요. 교통비, 숙박비, 식비, 액티비티 비용을 모두 고려하세요.
8. 예산이 명확히 부족하거나 과도할 때만 간단히 피드백을 추가하세요.
9. **[필수] 각 일자 섹션 마지막에 타임라인 JSON을 반드시 생성하세요:**
   - 형식: ```json 코드 블록 사용
   - 구조: {{"day": 숫자, "schedules": [{{"time": "HH:MM", "title": "활동명", "description": "간결한 설명"}}]}}
   - **description 작성 가이드:**
     * 2-5단어 정도의 간결한 설명
     * title과 잘 어울리는 자연스러운 표현 사용
     * **음식점**: "점심" 또는 "저녁"으로 표기 (예: "점심", "저녁")
     * **카페**: "카페"로 통일
     * **관광/활동**: 활동 성격 표현 (예: "등산과 전망", "바다 구경", "자연 탐방", "해변 드라이브")
     * **이동**: 이동 수단 표현 (예: "비행기 탑승", "차량 대여", "택시 이동")
     * **숙소**: "호텔 체크인", "호텔 체크아웃" 등
     * **휴식**: "자유시간", "호텔 휴식" 등
   - 모든 활동을 시간순으로 포함 (공항, 렌터카, 카페, 식사, 관광, 체크인 등)
   - **숙소 체크인/체크아웃 시간 규칙:**
     * 체크인: 일반적으로 15:00~18:00 사이 (호텔/펜션 표준)
     * 체크아웃: 일반적으로 10:00~12:00 사이 (호텔/펜션 표준)
     * 실제 숙소 정책에 따라 조정 가능 (예: 게스트하우스는 더 유연할 수 있음)
     * 체크인 전에 도착하면 짐 보관만 하고, 체크인 시간 이후에 정식 체크인
     * 마지막 날은 체크아웃 후 관광 또는 귀가

---

[출력 예시]

{example_prompt}

---
이제 위 형식을 기반으로, 실제 장소와 최신 정보를 반영한 여행 일정을 작성하세요.
**반드시 각 일자마다 ```json 코드 블록을 생성하세요.**
"""



    model = genai.GenerativeModel("models/gemini-2.0-flash")
    response = model.generate_content(prompt)
    
    latest_plan = response.text
    save_plan_to_file(latest_plan)
    
    existing_travel_id = find_existing_travel(data)
    
    if existing_travel_id:
        existing_travel = travel_summaries_store[existing_travel_id]
        
        updated_summary = extract_summary_from_plan(latest_plan, data)
        updated_summary.id = existing_travel_id
        
        travel_summaries_store[existing_travel_id] = updated_summary
        save_travel_summaries()
        
        return {
            "plan": latest_plan,
            "travel_id": existing_travel_id,
            "message": "기존 여행 계획이 업데이트되었습니다.",
            "summary": TravelSummaryResponse(
                id=updated_summary.id,
                title=updated_summary.title,
                destination=updated_summary.destination,
                departure=updated_summary.departure,
                start_date=updated_summary.start_date,
                end_date=updated_summary.end_date,
                companions=updated_summary.companions,
                budget=updated_summary.budget,
                travel_styles=updated_summary.travel_styles,
                highlights=updated_summary.highlights
            )
        }
    else:
        travel_summary = extract_summary_from_plan(latest_plan, data)
        travel_summaries_store[travel_summary.id] = travel_summary
        save_travel_summaries()
        
        return {
            "plan": latest_plan,
            "travel_id": travel_summary.id,
            "message": "새로운 여행 계획이 생성되었습니다.",
            "summary": TravelSummaryResponse(
                id=travel_summary.id,
                title=travel_summary.title,
                destination=travel_summary.destination,
                departure=travel_summary.departure,
                start_date=travel_summary.start_date,
                end_date=travel_summary.end_date,
                companions=travel_summary.companions,
                budget=travel_summary.budget,
                travel_styles=travel_summary.travel_styles,
                highlights=travel_summary.highlights
            )
        }

@app.post("/feedback")
async def feedback(data: FeedbackInput):
    global latest_plan, chat_history

    if latest_plan is None:
        return {"error": "아직 생성된 여행 일정이 없습니다. 먼저 /Travel-Plan을 호출하세요."}

    history_prompt = "\n".join(f"- {message}" for message in chat_history) or "이전 피드백 없음"

    prompt = f"""
당신은 전문 여행 플래너이자 컨시어지입니다.
아래의 **기존 여행 일정**을 기반으로 사용자의 피드백을 반영하여 새로운 일정을 작성하세요.

---

[기존 여행 일정]
{latest_plan}

---

[이전 대화 기록]
{history_prompt}

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
    
    latest_plan = response.text
    save_plan_to_file(latest_plan)
    chat_history.append(data.message)
    
    return {"reply": latest_plan}

@app.get("/travel-summary/{travel_id}")
async def get_travel_summary(travel_id: str):
    """특정 여행의 요약 정보를 조회합니다."""
    if travel_id not in travel_summaries_store:
        return {"error": f"여행 ID '{travel_id}'를 찾을 수 없습니다."}
    
    summary = travel_summaries_store[travel_id]
    return TravelSummaryResponse(
        id=summary.id,
        title=summary.title,
        destination=summary.destination,
        departure=summary.departure,
        start_date=summary.start_date,
        end_date=summary.end_date,
        companions=summary.companions,
        budget=summary.budget,
        travel_styles=summary.travel_styles,
        highlights=summary.highlights
    )

@app.get("/travel-summaries")
async def get_all_travel_summaries():
    """저장된 모든 여행 요약 정보를 조회합니다."""
    summaries = []
    for summary in travel_summaries_store.values():
        summaries.append(TravelSummaryResponse(
            id=summary.id,
            title=summary.title,
            destination=summary.destination,
            departure=summary.departure,
            start_date=summary.start_date,
            end_date=summary.end_date,
            companions=summary.companions,
            budget=summary.budget,
            travel_styles=summary.travel_styles,
            highlights=summary.highlights
        ))
    
    return {"summaries": summaries, "total": len(summaries)}

@app.get("/travel-plan/{travel_id}")
async def get_travel_plan(travel_id: str):
    """특정 여행의 전체 계획을 조회합니다."""
    if travel_id not in travel_summaries_store:
        return {"error": f"여행 ID '{travel_id}'를 찾을 수 없습니다."}
    
    summary = travel_summaries_store[travel_id]
    return {"id": travel_id, "plan": summary.full_plan}

@app.delete("/travel/{travel_id}")
async def delete_travel(travel_id: str):
    """특정 여행을 삭제합니다."""
    if travel_id not in travel_summaries_store:
        return {"error": f"여행 ID '{travel_id}'를 찾을 수 없습니다."}
    
    del travel_summaries_store[travel_id]
    save_travel_summaries()
    
    return {"message": f"여행 ID '{travel_id}'가 성공적으로 삭제되었습니다."}
