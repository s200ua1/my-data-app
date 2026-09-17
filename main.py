```python
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 1. 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")


# --------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# --------------------------------------------------
# Streamlit Cloud 서버의 시간은 한국 시간이 아닐 수 있으므로
# 반드시 한국 시간(KST)을 기준으로 날짜를 계산합니다.

kst = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(kst).date()
yesterday = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 YYYYMMDD 형식으로 변환
target_dt = yesterday.strftime("%Y%m%d")

st.caption(
    f"조회 날짜: {yesterday.strftime('%Y년 %m월 %d일')} "
    f"(한국 시간 기준)"
)


# --------------------------------------------------
# 3. KOBIS API 주소와 인증키
# --------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# Streamlit Cloud의 Secrets에 저장한 인증키를 가져옵니다.
# 코드 안에는 실제 인증키를 절대로 적지 않습니다.
try:
    KOBIS_KEY = st.secrets["KOBIS_KEY"]
except Exception:
    st.error(
        "KOBIS_KEY를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 Settings → Secrets에 "
        "KOBIS_KEY를 등록했는지 확인해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 4. API 요청 함수
# --------------------------------------------------
# 같은 날짜를 다시 요청하면 한 시간 동안 저장된 결과를 사용합니다.
# 따라서 API를 불필요하게 여러 번 호출하지 않습니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_date, api_key):
    params = {
        "key": api_key,
        "targetDt": target_date
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10
        )

        # HTTP 오류가 있으면 예외 발생
        response.raise_for_status()

        # JSON으로 변환
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "error": (
                "KOBIS API에 접속하지 못했습니다.\n\n"
                f"확인할 내용: 인터넷 연결, KOBIS API 주소, "
                f"API 서버 상태를 확인해 주세요.\n\n"
                f"오류 내용: {e}"
            )
        }

    except ValueError:
        return {
            "error": (
                "KOBIS API 응답을 JSON으로 읽지 못했습니다.\n\n"
                "KOBIS API 서버의 응답 상태를 확인해 주세요."
            )
        }

    # --------------------------------------------------
    # 인증키 오류 등으로 faultInfo가 오는 경우
    # HTTP 상태코드는 200일 수 있으므로 별도로 확인합니다.
    # --------------------------------------------------
    if "faultInfo" in data:
        fault = data["faultInfo"]

        error_message = fault.get(
            "message",
            "KOBIS API에서 오류가 발생했습니다."
        )

        error_code = fault.get(
            "errorCode",
            "알 수 없음"
        )

        return {
            "error": (
                "KOBIS API에서 오류가 반환되었습니다.\n\n"
                f"오류 코드: {error_code}\n"
                f"오류 내용: {error_message}\n\n"
                "확인할 내용: Streamlit Secrets의 "
                "KOBIS_KEY가 정확한지 확인해 주세요."
            )
        }

    # 정상적인 박스오피스 결과 확인
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "error": (
                "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
                "확인할 내용: 조회 날짜와 KOBIS API 서버의 "
                "응답 상태를 확인해 주세요."
            )
        }

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "error": (
                f"{yesterday.strftime('%Y년 %m월 %d일')}의 "
                "박스오피스 영화 목록이 없습니다.\n\n"
                "확인할 내용:\n"
                "• 해당 날짜의 박스오피스 데이터가 집계되었는지 확인\n"
                "• 조회 날짜가 올바른지 확인\n"
                "• KOBIS API 서버 상태를 확인해 주세요."
            )
        }

    return {
        "data": movie_list
    }


# --------------------------------------------------
# 5. 데이터 가져오기
# --------------------------------------------------

result = get_boxoffice(target_dt, KOBIS_KEY)

if "error" in result:
    st.error(result["error"])
    st.stop()

movies = result["data"]


# --------------------------------------------------
# 6. 필요한 데이터만 골라서 표 만들기
# --------------------------------------------------

df = pd.DataFrame(movies)

# KOBIS에서 숫자도 문자열로 보내므로 숫자형으로 변환합니다.
numeric_columns = [
    "rank",
    "audiCnt",
    "audiAcc",
    "scrnCnt"
]

for column in numeric_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0).astype(int)

# 순위순으로 정렬
df = df.sort_values("rank")


# --------------------------------------------------
# 7. 1위 영화 정보
# --------------------------------------------------

first_movie = df.iloc[0]

movie_name = first_movie["movieNm"]
audience_count = first_movie["audiCnt"]
total_audience = first_movie["audiAcc"]
screen_count = first_movie["scrnCnt"]

st.subheader(f"🥇 1위: {movie_name}")

# 지표 카드 세 장
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "어제 관객수",
        f"{audience_count:,}명"
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{total_audience:,}명"
    )

with col3:
    st.metric(
        "스크린수",
        f"{screen_count:,}개"
    )


# --------------------------------------------------
# 8. 관객수 상위 5편 막대그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
      .head(5)
      .copy()
)

# 영화명을 인덱스로 사용
chart_data = top5.set_index("movieNm")[["audiCnt"]]

st.bar_chart(
    chart_data,
    y="audiCnt",
    x_label="영화",
    y_label="관객수"
)


# --------------------------------------------------
# 9. 전체 박스오피스 표
# --------------------------------------------------

st.subheader("🎥 전체 박스오피스")

# 화면에 보여줄 열만 선택
display_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 날짜를 보기 좋은 형태로 변환
display_df["openDt"] = pd.to_datetime(
    display_df["openDt"],
    format="%Y%m%d",
    errors="coerce"
).dt.strftime("%Y-%m-%d")

# 열 이름을 한국어로 변경
display_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 숫자를 보기 편하게 표시
st.dataframe(
    display_df.style.format({
        "순위": "{:,.0f}",
        "관객수": "{:,.0f}",
        "누적관객": "{:,.0f}",
        "스크린수": "{:,.0f}"
    }),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "※ 데이터 출처: 영화관입장권통합전산망(KOBIS) 일일 박스오피스 API"
)
```

KOBIS의 공식 일일 박스오피스 서비스가 제공하는 영화별 순위·관객수·스크린수 등의 데이터를 기준으로 작성했습니다.

### `requirements.txt`

```text
streamlit
requests
pandas
```

### Streamlit Cloud Secrets 설정

코드에는 인증키를 넣지 않고, Streamlit Cloud에서 다음처럼 **Secrets**에만 넣으면 됩니다.

```toml
KOBIS_KEY = "발급받은_실제_인증키"
```

이 앱의 날짜 계산은 `Asia/Seoul` 시간대를 사용하므로 서버가 해외 시간대를 사용하더라도 **한국 시간으로 날짜를 판단해서 전날(`targetDt`)을 요청**합니다. 또한 `st.cache_data(ttl=3600)`으로 같은 날짜의 결과를 약 1시간 동안 캐시합니다.

필요한 파일은 **`main.py`와 `requirements.txt` 두 개**입니다.
