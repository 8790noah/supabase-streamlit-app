# Force update to clear cache
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from streamlit_chartjs import chartjs # Chart.js 렌더링을 위한 라이브러리 임포트

# --- 1. Supabase 연결 설정 ---
# @st.cache_resource를 사용하여 앱이 실행되는 동안 단 한 번만 연결을 초기화합니다.
@st.cache_resource
def init_connection():
    # Streamlit Secrets (secrets.toml 또는 Cloud Secrets)에서 정보를 안전하게 가져옴
    try:
        url: str = st.secrets["supabase"]["url"]
        key: str = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except KeyError:
        st.error("Error: Could not find Supabase connection secrets. Please check your secrets.toml or Streamlit Cloud Secrets settings.")
        return None

# 전역 Supabase 클라이언트 생성
supabase_client = init_connection()

# --- 2. 데이터 조회 함수 ---
# 사용자가 입력한 행정동코드와 날짜에 해당하는 데이터를 Supabase에서 조회합니다.
def load_population_data(dong_code, date_str):
    if not supabase_client:
        return pd.DataFrame()

    # 데이터 테이블 이름: Supabase에 업로드된 테이블 이름과 동일해야 합니다.
    table_name = "서울시_생활인구_2023"

    try:
        # Supabase 쿼리: 
        # 1. '행정동코드'와 '날짜'가 일치하는 데이터 필터링
        # 2. '시간대'와 '총생활인구수' 컬럼만 선택
        # 3. '시간대'를 기준으로 오름차순 정렬 (0시부터 23시까지 순서대로)
        response = (
            supabase_client.table(table_name)
            .select("시간대, 총생활인구수")
            .eq("행정동코드", dong_code)
            .eq("날짜", date_str)
            .order("시간대")
            .execute()
        )
        
        data = response.data
        if not data:
            return pd.DataFrame()
        
        # 조회된 JSON 데이터를 Pandas DataFrame으로 변환
        df = pd.DataFrame(data)
        return df
    
    except Exception as e:
        st.error("데이터베이스 조회 중 오류가 발생했습니다. 테이블 이름('서울시_생활인구_2023') 또는 컬럼 이름이 Supabase와 일치하는지 확인해 주세요.")
        # 디버깅을 위해 콘솔에 전체 에러 메시지를 출력합니다.
        # print(f"Supabase query error: {e}") 
        return pd.DataFrame()

# --- 3. Streamlit 앱 인터페이스 ---
st.set_page_config(layout="wide")
st.title("📊 서울시 시간대별 생활인구 추이 분석")
st.markdown("특정 **행정동**과 **날짜**를 선택하여 하루 동안의 **총생활인구수** 변화를 꺾은선 그래프로 확인하세요.")

# 사이드바를 이용한 입력 UI
with st.sidebar:
    st.header("🔍 조회 조건 설정")
    
    # 3-1. 행정동코드 입력 필드 (Supabase 테이블의 데이터 타입에 따라 문자열로 처리)
    dong_code_str = st.text_input(
        "행정동코드 (예: 1156064000)", # 여의동 코드
        placeholder="1156064000",
        max_chars=10 # 행정동코드는 보통 10자리입니다.
    ) 
    
    # 3-2. 날짜 선택 필드
    # 날짜 입력은 Streamlit의 date_input 위젯 사용
    selected_date = st.date_input(
        "조회 날짜 선택", 
        value=pd.to_datetime("2023-01-01"), # 기본값 설정 (데이터셋 기간 내 날짜 선택)
        min_value=pd.to_datetime("2023-01-01"), 
        max_value=pd.to_datetime("2023-12-31")
    ) 
    
    # 날짜 객체를 Supabase 쿼리에 맞는 문자열(YYYY-MM-DD)로 변환
    date_str = selected_date.strftime("%Y-%m-%d")

    # 3-3. 조회 버튼
    search_button = st.button("📈 데이터 조회 및 시각화", type="primary")

# --- 4. 조회 실행 로직 및 유효성 검사 ---

if search_button:
    # 요구사항 1: 입력값 유효성 검사 (빈 값 체크)
    if not dong_code_str or not date_str:
        st.warning("⚠️ **올바른 값을 입력해주세요.** 행정동코드와 날짜를 모두 입력해야 합니다.")
        st.stop()
    
    # 행정동 코드가 숫자로만 구성되었는지 확인
    if not dong_code_str.isdigit() or len(dong_code_str) != 10:
        st.warning("⚠️ 행정동코드는 10자리 숫자 형태여야 합니다.")
        st.stop()

    # 데이터 조회 시작
    try:
        dong_code = int(dong_code_str)
        
        with st.spinner(f"행정동코드 **{dong_code}**의 **{date_str}** 데이터 조회 중..."):
            df_result = load_population_data(dong_code, date_str)

        # 조회 결과 확인
        if df_result.empty:
            st.error(f"🔍 해당 행정동(코드: {dong_code})의 {date_str} 데이터가 Supabase에 없습니다. 조건을 다시 확인해주세요.")
        else:
            st.success(f"✅ 데이터 조회 완료: {date_str} 기준, 24개 시간대 데이터 ({df_result['총생활인구수'].sum():,.0f} 명)")
            
            # --- 5. Chart.js 시각화 (요구사항) ---
            st.subheader(f"시간대별 총생활인구수 추이 ({date_str})")
            
            # Chart.js에 전달할 JSON 데이터 구조 정의
            chart_config = {
                "type": "line", # 꺾은선 그래프 (Line Chart)
                "data": {
                    # X축 (시간대: 0시부터 23시)
                    "labels": df_result['시간대'].tolist(), 
                    "datasets": [
                        {
                            "label": "총생활인구수 (명)",
                            "data": df_result['총생활인구수'].tolist(), 
                            "backgroundColor": "rgba(75, 192, 192, 0.4)",
                            "borderColor": "rgba(75, 192, 192, 1)",
                            "borderWidth": 3,
                            "pointRadius": 5,
                            "fill": False, # 선 아래를 채우지 않음
                            "tension": 0.4 # 곡선 처리
                        }
                    ]
                },
                "options": {
                    "responsive": True,
                    "maintainAspectRatio": False,
                    "plugins": {
                        "legend": {"position": "top"},
                        "title": {"display": True, "text": f"행정동 코드: {dong_code_str}"}
                    },
                    "scales": {
                        "x": {"title": {"display": True, "text": "시간대 (Hour)", "font": {"size": 14}}},
                        "y": {"title": {"display": True, "text": "총생활인구수 (명)", "font": {"size": 14}}}
                    }
                }
            }
            
            # chartjs 함수를 사용하여 차트 렌더링
            # height를 지정하여 차트 크기 조정
            chartjs(chart_config, height=500) 
            
            st.markdown("---")
            st.caption("Raw Data (First 5 Rows)")
            st.dataframe(df_result.head())

    except Exception as e:
        st.error(f"예상치 못한 오류가 발생했습니다: {e}")
