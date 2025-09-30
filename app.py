# Force update to clear cache
import streamlit as st
import pandas as pd
from supabase import create_client, Client
import altair as alt # Altair 차트 라이브러리 임포트

# --- 1. Supabase 연결 설정 ---
# @st.cache_resource를 사용하여 앱이 실행되는 동안 단 한 번만 연결을 초기화합니다.
@st.cache_resource
def init_connection():
    # Streamlit Secrets에서 단일 레벨 변수 이름을 읽습니다. (SUPABASE_URL, SUPABASE_KEY)
    try:
        url: str = st.secrets["SUPABASE_URL"]
        key: str = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError:
        st.error("Error: Could not find Supabase connection secrets. Please ensure SUPABASE_URL and SUPABASE_KEY are set directly in your Streamlit Cloud Secrets.")
        return None

# 전역 Supabase 클라이언트 생성
supabase_client = init_connection()

# --- 2. 데이터 조회 함수 ---
# 사용자가 입력한 행정동코드와 날짜에 해당하는 데이터를 Supabase에서 조회합니다.
def load_population_data(dong_code, date_str):
    if not supabase_client:
        return pd.DataFrame()

    # 데이터 테이블 이름: Supabase에서 한글 이름이 소문자로 자동 변환되었을 가능성을 고려하여 .lower()를 적용
    table_name = "서울시_생활인구_2023".lower()

    try:
        # Supabase 쿼리 실행: 테이블 이름, 컬럼 이름, 필터링 조건 모두 Supabase와 일치해야 합니다.
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
        # 오류 발생 시 더 구체적인 메시지를 출력
        st.error(f"⚠️ 데이터베이스 쿼리 오류 발생: Supabase 응답에 문제가 있습니다. (세부 오류: {e})")
        st.warning(f"💡 현재 쿼리 조건: 테이블='{table_name}', 컬럼='시간대, 총생활인구수, 행정동코드, 날짜'")
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
            # 이 메시지는 테이블 이름이 맞지만, 입력한 코드/날짜에 데이터가 없을 때 뜹니다.
            st.error(f"🔍 해당 행정동(코드: {dong_code})의 {date_str} 데이터가 Supabase에 없습니다. 조건을 다시 확인해주세요.")
        else:
            st.success(f"✅ 데이터 조회 완료: {date_str} 기준, 24개 시간대 데이터 ({df_result['총생활인구수'].sum():,.0f} 명)")
            
            # --- 5. Altair 시각화 ---
            st.subheader(f"시간대별 총생활인구수 추이 ({date_str})")
            
            # Altair 차트 생성
            chart = alt.Chart(df_result).mark_line(point=True).encode(
                # X축: 시간대 (순서대로 정렬)
                x=alt.X('시간대', title='시간대 (Hour)', scale=alt.Scale(domain=[0, 23])),
                # Y축: 총생활인구수
                y=alt.Y('총생활인구수', title='총생활인구수 (명)'),
                # 툴팁 설정
                tooltip=['시간대', alt.Tooltip('총생활인구수', format=',.0f')]
            ).properties(
                title=f"행정동 코드: {dong_code_str} ({date_str})"
            ).interactive() # 확대/축소 기능 활성화
            
            # Streamlit에 차트 표시
            st.altair_chart(chart, use_container_width=True) 
            
            st.markdown("---")
            st.caption("Raw Data (First 5 Rows)")
            st.dataframe(df_result.head())

    except Exception as e:
        st.error(f"예상치 못한 앱 내부 오류가 발생했습니다: {e}")
```eof

**GitHub에 이 코드를 커밋한 후,** 앱을 재시작하고 **데이터가 확실히 존재하는 행정동 코드와 날짜**를 입력하여 최종 확인해 보세요! 모든 오류를 극복하고 완성에 도달하셨습니다! 👍
