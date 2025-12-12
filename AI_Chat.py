from fastapi import FastAPI
from fastapi import Body
from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional
from enum import Enum
import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path
import os
import json
from datetime import datetime, timedelta
import uuid
import re
import httpx  # HTTP 클라이언트 라이브러리

BASE_DIR = Path(__file__).parent
load_dotenv(dotenv_path=BASE_DIR / ".env")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Spring Boot 서버 URL (환경변수로 설정)
SPRING_BOOT_URL = os.getenv("SPRING_BOOT_URL", "http://spring-server:8080")

app = FastAPI()

class TravelStyle(str, Enum):
    ACTIVITY = "체험/액티비티"
    HOTPLACE = "SNS 핫플레이스"
    NATURE = "자연과 함께"
    MUST_VISIT = "유명 관광지는 필수"
    HEALING = "여유롭게 힐링"
    CULTURE = "문화/예술/역사"
    LOCAL_VIBE = "여행지 느낌 물씬"
    SHOPPING = "쇼핑은 열정적으로"
    FOOD_FOCUS = "관광보다 먹방"

class TravelInput(BaseModel):
    companions: str
    departure: str
    destination: str
    start_date: str
    end_date: str
    style: List[TravelStyle]
    budget: str

class FeedbackInput(BaseModel):
    message: str

class ScheduleItem(BaseModel):
    orderIndex: int = Field(..., alias='order_index')
    time: str
    title: str = Field(..., max_length=50)  # Spring: length 50
    description: str = Field(..., max_length=100)  # Spring: length 100
    
    class Config:
        populate_by_name = True  # orderIndex, order_index 모두 허용
    
    @model_validator(mode='before')
    @classmethod
    def convert_legacy_fields(cls, data):
        """sequence나 index를 orderIndex로 변환"""
        if isinstance(data, dict):
            # sequence를 orderIndex로 변환
            if 'sequence' in data and 'orderIndex' not in data and 'order_index' not in data:
                data['orderIndex'] = data.pop('sequence')
            # index를 orderIndex로 변환
            elif 'index' in data and 'orderIndex' not in data and 'order_index' not in data:
                data['orderIndex'] = data.pop('index')
        return data

class TripHighlight(BaseModel):
    """하이라이트 정보 - Spring Boot 엔티티 구조"""
    content: str = Field(..., max_length=100)  # Spring: length 100

class DailySchedule(BaseModel):
    day: int
    date: str
    schedules: List[ScheduleItem]

class TripTransportation(BaseModel):
    """교통편 정보 - Spring Boot 엔티티 구조"""
    origin: str = Field(..., max_length=50)  # 출발지 (Spring: length 50)
    destination: str = Field(..., max_length=50)  # 도착지 (Spring: length 50)
    name: str = Field(..., max_length=50)  # 교통수단 이름 (Spring: length 50)
    price: int  # 가격 (숫자)

class TripAccommodation(BaseModel):
    """숙소 정보 - Spring Boot 엔티티 구조"""
    name: str = Field(..., max_length=100)  # 숙소명 (Spring: length 100)
    address: str = Field(..., max_length=100)  # 주소 (Spring: length 100)
    pricePerNight: int  # 1박 가격 (숫자)

class TripPlan(BaseModel):
    title: str = Field(..., max_length=100)  # Spring: length 100
    destination: str = Field(..., max_length=50)  # Spring: length 50
    departure: str = Field(..., max_length=50)  # Spring: length 50
    startDate: str = Field(..., alias='start_date')  # ISO 8601 형식
    endDate: str = Field(..., alias='end_date')  # ISO 8601 형식
    companions: str = Field(..., max_length=50)  # Spring: length 50
    budget: str = Field(..., max_length=30)  # Spring: length 30
    travelStyles: List[TravelStyle] = Field(..., alias='travel_styles')  # camelCase
    highlights: List[TripHighlight] = []  # 각 항목 100자 이하
    fullPlan: str = Field(..., alias='full_plan')  # 전체 계획 텍스트
    dailySchedules: List[DailySchedule] = Field(default=[], alias='daily_schedules')
    outboundTransportation: Optional[TripTransportation] = Field(default=None, alias='outbound_transportation')
    returnTransportation: Optional[TripTransportation] = Field(default=None, alias='return_transportation')
    accommodations: List[TripAccommodation] = []  # 숙소 정보
    
    @model_validator(mode='before')
    @classmethod
    def convert_highlights(cls, data):
        """문자열 리스트를 TripHighlight 객체 리스트로 변환 (하위 호환성)"""
        if isinstance(data, dict) and 'highlights' in data:
            highlights = data['highlights']
            if highlights and isinstance(highlights, list):
                # 문자열 리스트인 경우 객체 리스트로 변환
                if isinstance(highlights[0], str):
                    data['highlights'] = [{'content': h} for h in highlights]
        return data
    
    class Config:
        populate_by_name = True  # snake_case와 camelCase 모두 허용
class TripPlanResponse(BaseModel):
    title: str = Field(..., max_length=100)
    destination: str = Field(..., max_length=50)
    departure: str = Field(..., max_length=50)
    startDate: str
    endDate: str
    companions: str = Field(..., max_length=50)
    budget: str = Field(..., max_length=30)
    travelStyles: List[TravelStyle]
    highlights: List[TripHighlight] = []  # 각 항목 100자 이하
    dailySchedules: List[DailySchedule] = []
    outboundTransportation: Optional[TripTransportation] = None
    returnTransportation: Optional[TripTransportation] = None
    accommodations: List[TripAccommodation] = []
    
    class Config:
        by_alias = True  # JSON 출력 시 camelCase 사용

OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
TRAVEL_SUMMARIES_FILE = DATA_DIR / "travel_data.json"
travel_summaries_store: Dict[str, TripPlan] = {}


def load_travel_summaries() -> None:
    """파일에서 여행 요약 정보를 로드"""
    global travel_summaries_store
    if TRAVEL_SUMMARIES_FILE.exists():
        try:
            with open(TRAVEL_SUMMARIES_FILE, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
                data_list = file_data.get('data', [])
                travel_summaries_store = {}
                for item in data_list:
                    travel_id = item.pop('id', str(uuid.uuid4()))  # id를 분리하여 키로 사용
                    travel_summaries_store[travel_id] = TripPlan(**item)
        except Exception as e:
            print(f"여행 요약 데이터 로드 실패: {e}")
            travel_summaries_store = {}


def save_travel_summaries() -> None:
    """여행 요약 정보를 파일에 저장"""
    try:
        data_list = []
        for travel_id, travel_plan in travel_summaries_store.items():
            plan_dict = travel_plan.dict()
            plan_dict['id'] = travel_id  # 내부 관리용 id 추가
            data_list.append(plan_dict)
        file_data = {"data": data_list}
        with open(TRAVEL_SUMMARIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(file_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"여행 요약 데이터 저장 실패: {e}")


def save_plan_to_file(content: str, filename: str = "latest_plan.md") -> None:
    """가장 최신 일정을 파일로 저장해서 에디터(VSCode 등)에서 확인 가능하게 함."""
    (OUTPUT_DIR / filename).write_text(content, encoding="utf-8")


def remove_json_blocks(text: str) -> str:
    """텍스트에서 JSON 코드 블록을 제거"""
    # 일자별 타임라인 JSON 제거
    text = re.sub(r'```json\s*\n.*?\n```', '', text, flags=re.DOTALL)
    # 교통편 JSON 제거
    text = re.sub(r'```transportation\s*\n.*?\n```', '', text, flags=re.DOTALL)
    # 숙소 JSON 제거
    text = re.sub(r'```accommodations\s*\n.*?\n```', '', text, flags=re.DOTALL)
    return text.strip()

def remove_ids(obj):
    """dict/list 내부의 모든 id 필드를 제거 (재귀)"""
    if isinstance(obj, dict):
        obj.pop("id", None)
        return {k: remove_ids(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [remove_ids(item) for item in obj]
    return obj

def extract_timeline_from_plan(plan: str, original_input: TravelInput) -> List[DailySchedule]:
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
                    for idx, item in enumerate(timeline_data.get('schedules', []), start=1):
                        schedules.append(ScheduleItem(
                            orderIndex=idx,
                            time=item['time'],
                            title=item['title'][:50],  # 50자 제한
                            description=item['description'][:30]  # 30자 제한
                        ))
                    
                    daily_schedules.append(DailySchedule(
                        day=day_num,
                        date=day_date.replace(".", "-"),  # YYYY-MM-DD 형식
                        schedules=schedules
                    ))
                
                elif isinstance(timeline_data, list):
                    for day_data in timeline_data:
                        if 'day' in day_data:
                            day_num = day_data['day']
                            day_date = (start_date + timedelta(days=day_num-1)).strftime("%Y.%m.%d")
                            
                            schedules = []
                            for idx, item in enumerate(day_data.get('schedules', []), start=1):
                                schedules.append(ScheduleItem(
                                    orderIndex=idx,
                                    time=item['time'],
                                    title=item['title'][:50],  # 50자 제한
                                    description=item['description'][:30]  # 30자 제한
                                ))
                            
                            daily_schedules.append(DailySchedule(
                                day=day_num,
                                date=day_date.replace(".", "-"),  # YYYY-MM-DD 형식
                                schedules=schedules
                            ))
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
    
    return daily_schedules


def extract_transportations_from_plan(plan: str) -> tuple[Optional[TripTransportation], Optional[TripTransportation]]:
    """AI 생성 계획에서 왕복 교통편 정보 추출 (가는 편, 돌아오는 편)"""
    outbound = None
    return_transport = None
    
    json_pattern = r'```transportation\s*\n(.*?)\n```'
    json_matches = re.findall(json_pattern, plan, re.DOTALL)
    
    if json_matches:
        try:
            transport_data = json.loads(json_matches[0])
            
            # 리스트 형식 (왕복 정보)
            if isinstance(transport_data, list):
                if len(transport_data) >= 1 and isinstance(transport_data[0], dict):
                    outbound = TripTransportation(**transport_data[0])
                if len(transport_data) >= 2 and isinstance(transport_data[1], dict):
                    return_transport = TripTransportation(**transport_data[1])
            # 딕셔너리 형식 (편도만)
            elif isinstance(transport_data, dict):
                outbound = TripTransportation(**transport_data)
                
        except json.JSONDecodeError as e:
            print(f"교통편 JSON 파싱 오류: {e}")
        except Exception as e:
            print(f"교통편 데이터 처리 오류: {e}")
    
    return outbound, return_transport


def extract_accommodations_from_plan(plan: str) -> List[TripAccommodation]:
    """AI 생성 계획에서 숙소 정보 추출"""
    accommodations = []
    json_pattern = r'```accommodations\s*\n(.*?)\n```'
    json_matches = re.findall(json_pattern, plan, re.DOTALL)
    
    if json_matches:
        try:
            accommodations_data = json.loads(json_matches[0])
            if isinstance(accommodations_data, list):
                for acc_data in accommodations_data:
                    accommodations.append(TripAccommodation(**acc_data))
            elif isinstance(accommodations_data, dict):
                accommodations.append(TripAccommodation(**accommodations_data))
        except json.JSONDecodeError as e:
            print(f"숙소 JSON 파싱 오류: {e}")
    
    return accommodations


def extract_summary_from_plan(plan: str, original_input: TravelInput) -> TripPlan:
    """생성된 여행 계획에서 요약 정보 추출"""
    
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
            if line.strip().startswith("•") or line.strip().startswith("-") or line.strip().startswith("*"):
                highlight = line.strip().replace("•", "").replace("-", "").replace("*", "").strip()
                if highlight:
                    highlights.append(highlight)
            elif line.strip().startswith("**") or line.strip() == "":
                continue
            elif line.strip().startswith("---"):
                # 구분선이 나오면 하이라이트 섹션 종료
                in_highlight_section = False
            else:
                in_highlight_section = False
    
    # 타임라인 정보 추출
    daily_schedules = extract_timeline_from_plan(plan, original_input)
    
    # 왕복 교통편 정보 추출
    outbound_transportation, return_transportation = extract_transportations_from_plan(plan)
    
    # 숙소 정보 추출
    accommodations = extract_accommodations_from_plan(plan)
    
    return TripPlan(
        title=title[:100],  # 100자 제한
        destination=original_input.destination[:50],  # 50자 제한
        departure=original_input.departure[:50],  # 50자 제한
        start_date=original_input.start_date,
        end_date=original_input.end_date,
        companions=original_input.companions[:50],  # 50자 제한
        budget=original_input.budget[:30],  # 30자 제한
        travel_styles=original_input.style,
        highlights=[TripHighlight(content=h[:100]) for h in highlights[:5]] if highlights else [TripHighlight(content=f"{original_input.destination} 탐방"[:100]), TripHighlight(content="맛집 투어"), TripHighlight(content="문화 체험")],  # 각 100자 제한
        full_plan=plan,
        daily_schedules=daily_schedules,
        outbound_transportation=outbound_transportation,
        return_transportation=return_transportation,
        accommodations=accommodations
    )


def find_existing_travel(data: TravelInput) -> Optional[str]:
    """동일한 조건의 기존 여행이 있는지 확인"""
    for travel_id, travel in travel_summaries_store.items():
        if (travel.destination == data.destination and 
            travel.departure == data.departure and
            travel.startDate == data.start_date and 
            travel.endDate == data.end_date and
            travel.companions == data.companions and
            travel.budget == data.budget and
            set(travel.travelStyles) == set([style.value for style in data.style])):
            return travel_id
    return None


example_prompt = """
[출력 예시]

- 제목: 제주도 3박 4일 힐링 여행
- 여행지: 제주도  
- 기간: 2024.03.15 ~ 2024.03.18  
- 동행자: 연인  
- 예산: 50만~100만원  
- 하이라이트:  
  • 성산일출봉 일출 감상  
  • 한라산 트레킹  
  • 오션뷰 카페 투어  
  • 제주 전통 맛집 탐방

---

📅 1일차
- 이동수단: 비행기 "김포공항 → 제주공항" (편도 약 60,000원, 소요시간 1시간)
- 오전: 제주공항 도착 → 렌터카 픽업 (1일 약 50,000원) → 숙소 체크인  
- 카페: "앤트러사이트 제주" (대표 메뉴: 콜드브루, 영업시간 09:00~19:00, 월요일 휴무)
- 오후: 성산일출봉 등반 및 오션뷰 감상  
- 점심: "연돈볼카츠" (대표 메뉴: 돈카츠, 영업시간 11:00~20:00)
- 저녁: 해안도로 드라이브 & 숙소 휴식  
- 숙소: "신라스테이 제주" (1박 약 120,000원)

📅 2일차
- 오전: 숙소 체크아웃 (10:00) → 관광 시작
- 오후: 한라산 트레킹
- 점심: "산방산 맛집" (대표 메뉴: 해물칼국수)
...

💬 예산 피드백 (필요한 경우만): 
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
아래 사용자의 여행 정보를 바탕으로 실제 존재하는 장소, 숙소, 맛집을 포함한 여행 일정을 작성하고,  
상단에는 카드 형태로 표현할 수 있는 요약 정보(하이라이트)를 함께 생성하세요.

---

[여행 정보]
- 출발지: {data.departure}
- 여행지: {data.destination}
- 동행자: {data.companions}
- 여행 기간: {data.start_date} ~ {data.end_date}
- 여행 스타일: {', '.join([style.value for style in data.style])}
- 예산: {data.budget}

---

[요청 조건]
1. 출력은 두 부분으로 구성하세요.
   - (1) 여행 요약 카드 섹션
   - (2) 상세 일정 섹션
2. 여행 요약 카드에는 다음 정보를 포함하세요.
   - 여행 제목 (예: "제주도 3박 4일 힐링 여행")
   - 출발지
   - 여행지 이름
   - 기간 (YYYY.MM.DD 형식)
   - 동행자 유형
   - 예산 범위
   - 여행 하이라이트 (4~5개 핵심 키워드 문장형, 각 100자 이내, 이모지나 날짜 정보 포함 금지, 예: "성산일출봉 일출 감상", "한라산 트레킹", "오션뷰 카페 투어")
3. 상세 일정은 일자별로 오전/오후/저녁 단위로 나누고 짧은 설명을 포함하세요.
4. 이동수단은 각 일자의 상단에 명시하고, 반드시 실제 운행 시간표와 정확한 요금을 확인하여 제공하세요.
   - 실제 이용 가능한 이동수단 (비행기, 기차, 고속버스, 택시, 렌터카, 대중교통 등)
   - 출발지 → 목적지 경로
   - 실제 출발 시간과 도착 시간을 명시 (예: 09:00 출발 → 10:00 도착)
   - 실제 운행 시간표를 기반으로 한 시간 설정 (항공편, 열차, 버스의 실제 시간표 반영)
   - **시간표가 아직 공개되지 않은 미래 날짜의 경우**: 기존 운행 패턴을 기반으로 예상 시간을 제시하고 "(현재 시간표 기준, 변동 가능)" 표기
   - 실제 요금 (편도 또는 왕복, 원 또는 현지 통화)
   - 실제 소요 시간
   - 운행 회사명 또는 노선명 (가능한 경우)
   - 예: "비행기 '김포공항 → 제주공항' (대한항공 KE1234편, 09:00 출발 → 10:05 도착, 편도 65,000원)"
   - 예: "KTX '서울역 → 부산역' (KTX 101편, 06:00 출발 → 08:38 도착, 편도 59,800원)"
   - 예: "고속버스 '서울고속터미널 → 강릉' (08:30 출발 → 11:10 도착, 편도 17,800원, 현재 시간표 기준)"
   - 예: "렌터카 (롯데렌터카, 1일 60,000원, 공항 인근 영업소에서 09:00 픽업 가능)"
   - 예: "지하철 '강남역 → 인천공항' (AREX 직통 08:00 출발 → 08:51 도착, 9,500원)"
   - 귀가 시에도 동일하게 실제 출발/도착 시간을 명시하세요.
   - 첫날 일정은 교통편 도착 시간을 고려하여 시작하고, 마지막 날 일정은 귀가 교통편 출발 시간을 고려하여 마무리하세요.
5. 추천 장소(관광지, 맛집, 카페 등)는 실제 존재하는 곳으로 구성하고 아래 정보를 포함하세요.
   - 이름 (실존)
   - 대표 메뉴 또는 활동
   - 영업시간 및 휴무일 (휴무일일 경우 대체 장소 제시)
   - 위치(지역명 또는 주소)
6. 숙소는 반드시 실존하는 브랜드/업체명과 1박 평균 요금을 명시하세요.
   - **주요 브랜드 호텔**: 롯데호텔, 신라호텔, 메리어트, 하얏트, 힐튼, 그랜드조선, 파크하얏트, 포시즌스, 반얀트리, 인터컨티넨탈, 노보텔, 이비스, 메종글래드 등
   - **리조트/펜션**: 해당 지역에서 실제 운영 중인 리조트명 (예: 제주-"제주신화월드", "메이필드호텔", "해비치호텔", 부산-"파라다이스호텔", "아난티코브", 강릉-"세인트존스호텔")
   - **글램핑/캠핑**: 실제 운영 중인 글램핑장 이름 (예: "별빛정원글램핑", "캠프통 포레스트", "힐링파크 글램핑", "글램핑프레도")
   - **게스트하우스/호스텔**: 해당 지역의 유명 게스트하우스 (예: 서울-"북촌게스트하우스", 제주-"제주하우스")
   - **주의**: 에어비앤비는 제외, 반드시 "OO 인근 펜션", "OO 지역 호텔" 같은 일반 명칭 대신 구체적인 업체명 사용
   - 예: "제주 신라호텔 (1박 약 250,000원)", "부산 파라다이스호텔 (1박 약 180,000원)", "강릉 세인트존스호텔 (1박 약 150,000원)"
   - **숙소 이동 최소화**: 2박 이상일 경우 가능한 같은 숙소에 연박하여 짐 이동 부담을 줄이세요. 5박 6일 이상일 때만 중간에 숙소 1회 변경 권장.
7. 전체 일정은 주어진 예산 내에서 현실적으로 구성하세요. 교통비, 숙박비, 식비, 액티비티 비용을 모두 고려하세요.
8. 예산이 명확히 부족하거나 과도할 때만 간단히 피드백을 추가하세요.
9. [필수] 각 일자 섹션 마지막에 타임라인 JSON을 반드시 생성하세요:
   - 형식: ```json 코드 블록 사용
   - 구조: {{"day": 숫자, "schedules": [{{"time": "HH:MM", "title": "활동명 (50자 이내)", "description": "간결한 설명 (30자 이내)"}}]}}
   - description 작성 가이드:
     * 30자 이내의 간결한 핵심 설명만 작성
     * title과 중복되지 않도록 핵심만 표현
     * 음식점: "점심" 또는 "저녁"으로만 표기
     * 카페: "카페 방문" 또는 "휴식"
     * 관광/활동: 핵심 활동만 (예: "등산", "해변 산책", "드라이브")
     * 이동: 이동 수단만 (예: "비행기 탑승", "렌터카 픽업")
     * 숙소 체크인: 숙소명만 명시 (예: "신라호텔 체크인")
     * 숙소 체크아웃: 숙소명만 명시 (예: "신라호텔 체크아웃")
     * 휴식: "휴식" 또는 "자유시간"
   - 모든 활동을 시간순으로 포함 (공항, 렌터카, 카페, 식사, 관광, 체크인 등)
   - 숙소 체크인/체크아웃 시간 규칙:
     * 체크인: 일반적으로 15:00~18:00 사이 (호텔/펜션 표준)
     * 체크아웃: 일반적으로 10:00~12:00 사이 (호텔/펜션 표준)
     * 실제 숙소 정책에 따라 조정 가능 (예: 게스트하우스는 더 유연할 수 있음)
     * 체크인 전에 도착하면 짐 보관만 하고, 체크인 시간 이후에 정식 체크인
     * 마지막 날은 체크아웃 후 관광 또는 귀가

10. [필수] 왕복 교통편 정보를 JSON 배열로 생성하세요 (여행 계획 끝에 한 번만):
   - 형식: ```transportation 코드 블록 사용
   - 구조: [
       {{
         "origin": "출발지 (50자 이하)",
         "destination": "목적지 (50자 이하)",
         "name": "교통수단명 (50자 이하, 예: 대한항공 KE1234편, KTX 산천 101호)",
         "price": 가격_숫자만_정수형
       }},
       {{
         "origin": "목적지 (돌아오는 편 출발지)",
         "destination": "출발지 (돌아오는 편 목적지)",
         "name": "교통수단명 (50자 이하)",
         "price": 가격_숫자만_정수형
       }}
     ]
   - 주의: 
     * 반드시 배열 형식 [가는 편, 돌아오는 편]으로 작성
     * price는 숫자만 입력 (단위 제거, 정수형)
     * origin/destination/name은 각각 50자 이하
   - 예시:
     ```transportation
     [
       {{
         "origin": "김포공항",
         "destination": "제주공항",
         "name": "대한항공KE1234",
         "price": 65000
       }},
       {{
         "origin": "제주공항",
         "destination": "김포공항",
         "name": "아시아나OZ8954",
         "price": 68000
       }}
     ]
     ```

11. [필수] 숙소 정보를 JSON으로 생성하세요 (여행 계획 끝에 한 번만):
   - 형식: ```accommodations 코드 블록 사용
   - 구조: [
       {{
         "name": "실제 브랜드/업체명 (100자 이하, 필수)",
         "address": "숙소 주소 (100자 이하)",
         "pricePerNight": 1박_가격_숫자만_정수형
       }}
     ]
   - 주의: 
     * "OO 인근 펜션", "OO 지역 호텔" 같은 일반 명칭 금지
     * 반드시 구체적인 브랜드명 사용
     * 여행 기간 동안 숙소 변경 최소화 (가능하면 같은 숙소)
     * pricePerNight는 숫자만 입력 (단위 제거, 정수형)
     * name과 address는 각각 100자 이하
     * 체크인/체크아웃 일정 설명에 숙소명 표시 (예: "제주신라호텔 체크인")
   - 예시:
     ```accommodations
     [
       {{
         "name": "제주신라호텔",
         "address": "제주시 중앙로 75",
         "pricePerNight": 250000
       }}
     ]
     ```

---

[출력 예시]

{example_prompt}

---
이제 위 형식을 기반으로, 실제 장소와 최신 정보를 반영한 여행 일정을 작성하세요.
반드시 각 일자마다 ```json 코드 블록을 생성하세요.
"""



    model = genai.GenerativeModel("models/gemini-2.0-flash")
    response = model.generate_content(prompt)
    
    latest_plan = response.text
    save_plan_to_file(latest_plan)
    
    existing_travel_id = find_existing_travel(data)
    
    if existing_travel_id:
        existing_travel = travel_summaries_store[existing_travel_id]
        
        updated_summary = extract_summary_from_plan(latest_plan, data)
        
        travel_summaries_store[existing_travel_id] = updated_summary
        save_travel_summaries()
        
        # 사용자에게는 JSON 블록 없이 깨끗한 텍스트만 전달
        clean_plan = remove_json_blocks(latest_plan)
        
        return {
            "plan": clean_plan,
            "travel_id": existing_travel_id,
            "message": "기존 여행 계획이 업데이트되었습니다.",
            "summary": TripPlanResponse(
                title=updated_summary.title,
                destination=updated_summary.destination,
                departure=updated_summary.departure,
                startDate=updated_summary.startDate,
                endDate=updated_summary.endDate,
                companions=updated_summary.companions,
                budget=updated_summary.budget,
                travelStyles=updated_summary.travelStyles,
                highlights=updated_summary.highlights,
                dailySchedules=updated_summary.dailySchedules,
                outboundTransportation=updated_summary.outboundTransportation,
                returnTransportation=updated_summary.returnTransportation,
                accommodations=updated_summary.accommodations
            )
        }
    else:
        travel_summary = extract_summary_from_plan(latest_plan, data)
        travel_id = str(uuid.uuid4())
        travel_summaries_store[travel_id] = travel_summary
        save_travel_summaries()
        
        # 사용자에게는 JSON 블록 없이 깨끗한 텍스트만 전달
        clean_plan = remove_json_blocks(latest_plan)
        
        return {
            "plan": clean_plan,
            "travel_id": travel_id,
            "message": "새로운 여행 계획이 생성되었습니다.",
            "summary": TripPlanResponse(
                title=travel_summary.title,
                destination=travel_summary.destination,
                departure=travel_summary.departure,
                startDate=travel_summary.startDate,
                endDate=travel_summary.endDate,
                companions=travel_summary.companions,
                budget=travel_summary.budget,
                travelStyles=travel_summary.travelStyles,
                highlights=travel_summary.highlights,
                dailySchedules=travel_summary.dailySchedules,
                outboundTransportation=travel_summary.outboundTransportation,
                returnTransportation=travel_summary.returnTransportation,
                accommodations=travel_summary.accommodations
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

🎯 목표
1. 기존 여행지와 전체 일정 구조는 그대로 유지합니다.  
2. 피드백을 다음 두 가지 유형으로 구분해 반영하세요:
   - 제약 조건(Constraint): 음식, 예산, 날짜, 활동 불가 등의 제한이 명확히 제시된 경우
     → 반드시 100% 반영 (예: "해산물 못 먹어요", "비건이에요", "비 오는 날은 실내 일정으로 변경해주세요.")
   - 선호/요청(Preference): 특정 활동/음식/장소/분위기에 대한 제안, 변경 희망  
     → 기존 일정의 맥락과 균형을 유지하면서 가능한 범위 내에서 자연스럽게 반영  
       (예: "좀 더 여유로운 일정으로 바꿔주세요.", "카페 시간을 늘려주세요.", "야경 명소를 넣어주세요.")
3. 기존 일정은 다시 보여주지 말고, 수정된 여행 일정만 텍스트로 출력하세요.
4. “알겠습니다” 같은 설명 문장은 포함하지 마세요.
5. 모든 계획은 실제 존재하는 장소, 숙소, 음식점을 기반으로 작성되어야 합니다.

---

🧩 출력 규칙
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
    
    # 사용자에게는 JSON 블록 없이 깨끗한 텍스트만 전달
    clean_plan = remove_json_blocks(latest_plan)
    
    return {"reply": clean_plan}

@app.get("/travel-summary/{travel_id}")
async def get_travel_summary(travel_id: str):
    """특정 여행의 요약 정보를 조회합니다."""
    if travel_id not in travel_summaries_store:
        return {"error": f"여행 ID '{travel_id}'를 찾을 수 없습니다."}
    
    summary = travel_summaries_store[travel_id]
    return TripPlanResponse(
        title=summary.title,
        destination=summary.destination,
        departure=summary.departure,
        startDate=summary.startDate,
        endDate=summary.endDate,
        companions=summary.companions,
        budget=summary.budget,
        travelStyles=summary.travelStyles,
        highlights=summary.highlights,
        dailySchedules=summary.dailySchedules,
        outboundTransportation=summary.outboundTransportation,
        returnTransportation=summary.returnTransportation,
        accommodations=summary.accommodations
    )

@app.get("/travel-summaries")
async def get_all_travel_summaries():
    """저장된 모든 여행 요약 정보를 조회합니다."""
    summaries = []
    for summary in travel_summaries_store.values():
        summaries.append(TripPlanResponse(
            title=summary.title,
            destination=summary.destination,
            departure=summary.departure,
            startDate=summary.startDate,
            endDate=summary.endDate,
            companions=summary.companions,
            budget=summary.budget,
            travelStyles=summary.travelStyles,
            highlights=summary.highlights,
            dailySchedules=summary.dailySchedules,
            outboundTransportation=summary.outboundTransportation,
            returnTransportation=summary.returnTransportation,
            accommodations=summary.accommodations
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

@app.post("/save-plan/{travel_id}")
async def save_plan(travel_id: str):
    """여행 계획을 Spring Boot 서버로 전송하여 DB에 저장합니다."""
    if travel_id not in travel_summaries_store:
        return {"error": "여행 ID 없음", "success": False}
    
    travel_plan = travel_summaries_store[travel_id]
    
    # TripPlanResponse로 변환 (camelCase로 자동 변환됨)
    plan_response = TripPlanResponse(
        title=travel_plan.title,
        destination=travel_plan.destination,
        departure=travel_plan.departure,
        startDate=travel_plan.startDate,
        endDate=travel_plan.endDate,
        companions=travel_plan.companions,
        budget=travel_plan.budget,
        travelStyles=travel_plan.travelStyles,
        highlights=travel_plan.highlights,
        dailySchedules=travel_plan.dailySchedules,
        outboundTransportation=travel_plan.outboundTransportation,
        returnTransportation=travel_plan.returnTransportation,
        accommodations=travel_plan.accommodations
    )
    
    # JSON으로 변환 (camelCase 형식)
    plan_data = plan_response.model_dump(by_alias=True)
    
    # 전체 데이터 구조에서 모든 id 제거
    plan_data = remove_ids(plan_data)
    
    # highlights를 Spring Boot 형식으로 변환 (객체 리스트 → 문자열 리스트)
    if "highlights" in plan_data and plan_data["highlights"]:
        plan_data["highlights"] = [h["content"] for h in plan_data["highlights"]]
    
    # DEBUG: Spring Boot로 전송하는 데이터 출력
    print("=" * 80)
    print("[DEBUG] Spring Boot로 전송하는 JSON 데이터:")
    print(json.dumps(plan_data, indent=2, ensure_ascii=False))
    print("=" * 80)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Spring Boot API 엔드포인트로 POST 요청
            response = await client.post(
                f"{SPRING_BOOT_URL}/api/trip-plan/from-fastapi",
                json=plan_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200 or response.status_code == 201:
                spring_response = response.json()
                return {
                    "success": True,
                    "message": "여행 계획이 Spring Boot 서버에 성공적으로 저장되었습니다.",
                    "spring_data": spring_response,
                    "fastapi_travel_id": travel_id
                }
            else:
                return {
                    "success": False,
                    "error": f"Spring Boot 서버 응답 오류: {response.status_code}",
                    "detail": response.text
                }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Spring Boot 서버 연결 시간 초과"
        }
    except httpx.RequestError as e:
        return {
            "success": False,
            "error": f"Spring Boot 서버 연결 실패: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"예상치 못한 오류 발생: {str(e)}"
        }

