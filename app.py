import streamlit as st
import pandas as pd
from supabase import create_client, Client
import altair as alt

# --- 1. Supabase 연결 설정 ---
@st.cache_resource
def init_connection():
    # Streamlit Secrets에서 SUPABASE_URL과 SUPABASE_KEY를 읽습니다.
    try:
        url: str = st.secrets["SUPABASE_URL"]
        key: str = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError:
        st.error("Error: Could not find Supabase connection secrets. Please ensure SUPABASE_URL and SUPABASE_KEY are set directly in your Streamlit Cloud Secrets.")
        return None

# 전역 Supabase 클라이언트 생성
supabase_client = init_connection()

# --- 2. 행정동 목록 로딩 함수 (컬럼 이름: dong_code) ---
@st.cache_data(ttl=3600) # 1시간마다 새로고침
def load_dong_list():
    if not supabase_client:
        return []
    
    table_name = "population"
    
    try:
        # 데이터베이스에서 고유한 'dong_code' 목록만 조회합니다. (영문 소문자 가정)
        response = (
            supabase_client.table(table_name)
            .select("dong_code") # << 컬럼 이름 수정
            .limit(100000)
            .execute()
        )
        
        data = response.data
        if not data:
            return []
        
        df = pd.DataFrame(data)
        
        # 중복된 코드를 제거하고 문자열로 변환하여 리스트를 만듭니다.
        # 컬럼 이름이 'dong_code'라고 가정합니다.
        dong_codes = df['dong_code'].drop_duplicates().astype(str).sort_values().tolist()
        
        return dong_codes
        
    except Exception as e:
        # 목록 로딩 실패 시 발생하는 오류를 출력
        st.error(f"⚠️ 행정동 코드 목록 로딩 중 오류 발생. 테이블 이름(population) 또는 컬럼 이름(dong_code)을 확인해주세요. (세부 오류: {e})")
        return []

# --- 3. 데이터 조회 함수 (컬럼 이름: hour, total_population, dong_code, date) ---
def load_population_data(dong_code_str, date_str):
    if not supabase_client:
        return pd.DataFrame()

    table_name = "population" 

    try:
        # 영문 컬럼 이름으로 쿼리합니다.
        response = (
            supabase_client.table(table_name)
            .select("hour, total_population") # << 컬럼 이름 수정
            .eq("dong_code", dong_code_str) # << 컬럼 이름 수정
            .eq("date", date_str) # << 컬럼 이름 수정 (날짜 컬럼이 'date'라고 가정)
            .order("hour") # << 컬럼 이름 수정
            .execute()
        )
        
        data = response.data
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # 시각화 함수에 맞춰서 컬럼 이름 변경 (차트 UI에 한글로 표시하기 위함)
        df.columns = ['시간대', '총생활인구수'] 
        return df
    
    except Exception as e:
        st.error(f"⚠️ 데이터베이스 쿼리 오류 발생: Supabase 응답에 문제가 있습니다. (세부 오류: {e})")
        st.warning(f"💡 현재 쿼리 조건: 테이블='{table_name}', 필터링 컬럼='dong_code, date'")
        return pd.DataFrame()

# --- 4. Streamlit 앱 인터페이스 ---
st.set_page_config(layout="wide")
st.title("📊 서울시 시간대별 생활인구 추이 분석")
st.markdown("특정 **행정동 코드**와 **날짜**를 선택하여 하루 동안의 **총생활인구수** 변화를 꺾은선 그래프로 확인하세요.")

# 행정동 목록 미리 로드
dong_codes = load_dong_list()

# 사이드바를 이용한 입력 UI
with st.sidebar:
    st.header("🔍 조회 조건 설정")
    
    # 4-1. 행정동코드 드롭다운 메뉴
    if dong_codes:
        selected_dong_code_str = st.selectbox(
            "행정동 코드 선택",
            options=dong_codes,
            index=dong_codes.index('1156064000') if '1156064000' in dong_codes else 0,
            key='dong_select'
        )
    else:
        st.error("행정동 코드 목록 로드에 실패했습니다. 위의 오류 메시지를 확인하세요.")
        selected_dong_code_str = '1156064000' # 기본값 설정 (선택할 목록이 없을 때)

    # 4-2. 날짜 선택 필드
    selected_date = st.date_input(
        "조회 날짜 선택", 
        value=pd.to_datetime("2023-01-01"),
        min_value=pd.to_datetime("2023-01-01"), 
        max_value=pd.to_datetime("2023-12-31")
    ) 
    
    date_str = selected_date.strftime("%Y-%m-%d")

    # 4-3. 조회 버튼
    search_button = st.button("📈 데이터 조회 및 시각화", type="primary")

# --- 5. 조회 실행 로직 및 시각화 ---

if search_button and selected_dong_code_str:
    try:
        with st.spinner(f"행정동코드 **{selected_dong_code_str}**의 **{date_str}** 데이터 조회 중..."):
            df_result = load_population_data(selected_dong_code_str, date_str)

        if df_result.empty:
            st.error(f"🔍 해당 행정동(코드: {selected_dong_code_str})의 {date_str} 데이터가 Supabase에 없습니다. 조건을 다시 확인해주세요.")
        else:
            st.success(f"✅ 데이터 조회 완료: {date_str} 기준, 24개 시간대 데이터 ({df_result['총생활인구수'].sum():,.0f} 명)")
            
            # --- Altair 시각화 ---
            st.subheader(f"시간대별 총생활인구수 추이 ({date_str})")
            
            chart = alt.Chart(df_result).mark_line(point=True).encode(
                x=alt.X('시간대', title='시간대 (Hour)', scale=alt.Scale(domain=[0, 23])),
                y=alt.Y('총생활인구수', title='총생활인구수 (명)'),
                tooltip=['시간대', alt.Tooltip('총생활인구수', format=',.0f')]
            ).properties(
                title=f"행정동 코드: {selected_dong_code_str} ({date_str})"
            ).interactive()
            
            st.altair_chart(chart, use_container_width=True) 
            
            st.markdown("---")
            st.caption("Raw Data (First 5 Rows)")
            st.dataframe(df_result.head())

    except Exception as e:
        st.error(f"예상치 못한 앱 내부 오류가 발생했습니다: {e}")
