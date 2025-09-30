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

# --- 2. 행정동 목록 로딩 함수 ---
@st.cache_data(ttl=3600) # 1시간마다 새로고침
def load_dong_list():
    if not supabase_client:
        return {}
    
    table_name = "population"
    
    try:
        # population 테이블에서 고유한 행정동코드와 행정동명 목록을 조회
        response = (
            supabase_client.table(table_name)
            .select("행정동코드, 행정동명")
            .limit(100000) # 충분한 양의 데이터를 가져와서 중복 제거
            .execute()
        )
        
        data = response.data
        if not data:
            return {}
        
        df = pd.DataFrame(data)
        
        # 행정동코드별 행정동명만 남기고 중복 제거
        # 최종적으로 { '행정동명 (코드)': 코드 } 형태의 딕셔너리를 만듭니다.
        df_unique = df[['행정동코드', '행정동명']].drop_duplicates().sort_values(by='행정동코드')
        
        # 사용자에게 보여줄 레이블과 실제 값(코드)을 매핑합니다.
        dong_map = {
            f"{row['행정동명']} ({row['행정동코드']})": str(row['행정동코드']) 
            for index, row in df_unique.iterrows()
        }
        
        return dong_map
        
    except Exception as e:
        st.error(f"⚠️ 행정동 목록 로딩 중 오류 발생. 컬럼 이름(행정동코드, 행정동명)을 확인해주세요. (세부 오류: {e})")
        return {}

# --- 3. 데이터 조회 함수 ---
def load_population_data(dong_code_str, date_str):
    if not supabase_client:
        return pd.DataFrame()

    table_name = "population" 

    try:
        # 컬럼 이름이 소문자로 변환되었다고 가정하고 쿼리합니다.
        response = (
            supabase_client.table(table_name)
            .select("시간대, 총생활인구수, 행정동코드, 날짜")
            .eq("행정동코드", dong_code_str) # 문자열로 비교
            .eq("날짜", date_str)
            .order("시간대")
            .execute()
        )
        
        data = response.data
        if not data:
            return pd.DataFrame()
        
        # 조회된 JSON 데이터를 Pandas DataFrame으로 변환
        df = pd.DataFrame(data)
        
        # 컬럼 이름이 한글로 되어 있을 경우 소문자로 변환되었을 가능성을 대비
        # 데이터프레임의 컬럼 이름을 통일합니다. (이 부분은 데이터에 따라 수정 필요)
        df.columns = df.columns.str.lower()
        
        # 시각화에 필요한 컬럼만 추출하여 반환 (모두 소문자로 가정)
        return df[['시간대', '총생활인구수']]
    
    except Exception as e:
        # 오류 발생 시 더 구체적인 메시지를 출력
        st.error(f"⚠️ 데이터베이스 쿼리 오류 발생: Supabase 응답에 문제가 있습니다. (세부 오류: {e})")
        st.warning(f"💡 현재 쿼리 조건: 테이블='{table_name}', 필터링 컬럼='행정동코드, 날짜'")
        return pd.DataFrame()

# --- 4. Streamlit 앱 인터페이스 ---
st.set_page_config(layout="wide")
st.title("📊 서울시 시간대별 생활인구 추이 분석")
st.markdown("특정 **행정동**과 **날짜**를 선택하여 하루 동안의 **총생활인구수** 변화를 꺾은선 그래프로 확인하세요.")

# 행정동 목록 미리 로드
dong_list = load_dong_list()
dong_options = list(dong_list.keys())

# 사이드바를 이용한 입력 UI
with st.sidebar:
    st.header("🔍 조회 조건 설정")
    
    # 4-1. 행정동코드 드롭다운 메뉴로 변경
    if dong_options:
        selected_dong_label = st.selectbox(
            "행정동 선택",
            options=dong_options,
            index=dong_options.index('여의동 (1156064000)') if '여의동 (1156064000)' in dong_options else 0,
            key='dong_select'
        )
        # 선택된 레이블에서 실제 행정동 코드(value)를 추출
        selected_dong_code_str = dong_list.get(selected_dong_label)
        
    else:
        # 목록 로드 실패 시 임시로 텍스트 입력 박스 유지 (디버깅용)
        st.error("행정동 목록 로드 실패. Supabase 컬럼 이름(행정동코드, 행정동명)을 확인하세요.")
        selected_dong_code_str = st.text_input("행정동코드 (예: 1156064000)", placeholder="1156064000")
    
    
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

if search_button:
    # 요구사항 1: 입력값 유효성 검사
    if not selected_dong_code_str or not date_str:
        st.warning("⚠️ **올바른 값을 선택해주세요.** 행정동과 날짜를 모두 선택해야 합니다.")
        st.stop()
    
    # 데이터 조회 시작
    try:
        with st.spinner(f"행정동코드 **{selected_dong_code_str}**의 **{date_str}** 데이터 조회 중..."):
            # selected_dong_code_str은 이미 문자열입니다.
            df_result = load_population_data(selected_dong_code_str, date_str)

        # 조회 결과 확인
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
                title=f"행정동: {selected_dong_label} ({date_str})"
            ).interactive()
            
            st.altair_chart(chart, use_container_width=True) 
            
            st.markdown("---")
            st.caption("Raw Data (First 5 Rows)")
            st.dataframe(df_result.head())

    except Exception as e:
        st.error(f"예상치 못한 앱 내부 오류가 발생했습니다: {e}")
