import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from shiny import App, reactive
from shiny.express import ui, input, render
from shinywidgets import output_widget, render_plotly
import plotly.graph_objects as go
import geopandas as gpd
import json
import plotly.colors as pc
from faicons import icon_svg
from shinyswatch import theme
from shiny.express import render, ui


import pydeck as pdk
from pathlib import Path
import os

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'  # 맑은 고딕
plt.rcParams['axes.unicode_minus'] = False     # 마이너스 기호 깨짐 방지

if 'SHINY_SERVER' in os.environ:
    app_dir = Path('/home/shiny')  # shinyapps.io 환경
else:
    app_dir = Path(__file__).parent  # 로컬 환경

# -----------------------------------------------------
#  개요 탭
# -----------------------------------------------------

# 엑셀 데이터 불러오기
df_nation = pd.read_excel(app_dir / "data/전국_시도별_고령인구_현황_최종.xlsx")
df_nation["시도"] = df_nation["시도"].str.strip()
df_nation = df_nation[df_nation["시도"] != "전국"]

# 쉼표 포맷 텍스트 라벨 및 커스텀 데이터 추가
df_nation["고령인구비율_label"] = df_nation["고령인구비율(%)"].apply(lambda x: f"{x:.1f}%")
df_nation["label"] = df_nation["시도"] + "<br>" + df_nation["고령인구비율_label"]
df_nation["고령인구수_포맷"] = df_nation["고령인구수"].apply(lambda x: f"{x:,}")
df_nation["총인구수_포맷"] = df_nation["총인구수"].apply(lambda x: f"{x:,}")

# 데이터 불러오기
df_gyeongbuk = pd.read_excel(app_dir / "data/202504_경북_시군별_65세이상_인구수_및_비율.xlsx")
df_gyeongbuk = df_gyeongbuk[df_gyeongbuk["시군명"] != "경상북도"]
df_gyeongbuk["시군명"] = df_gyeongbuk["시군명"].str.strip()
df_gyeongbuk = df_gyeongbuk.sort_values(by="총인구수", ascending=False)
df_gyeongbuk2 = df_gyeongbuk.sort_values(by="고령인구비율(%)", ascending=False)

df_gyeongbuk["label"] = df_gyeongbuk["시군명"] + "<br>" + df_gyeongbuk["65세이상"].astype(str) + "명"


# highlight = ["영천시", "영주시", "상주시", "칠곡군"]
# df_gyeongbuk["색상"] = df_gyeongbuk["시군명"].apply(
#     lambda x: "blue" if x in highlight else "lightgrey"
# )
import numpy as np

highlight = ["영주시", "상주시", "칠곡군"]  # 비교 대상
df_gyeongbuk["색상"] = np.select(
    [
        df_gyeongbuk["시군명"] == "영천시",
        df_gyeongbuk["시군명"].isin(highlight)
    ],
    [
        "gold",    # 영천시: 기준 지점
        "blue"     # 비교군
    ],
    default="lightgrey"  # 그 외: 기본색
)



# 📌 KPI 계산
total_population = df_gyeongbuk[df_gyeongbuk["시군명"] == "영천시"]["총인구수"].values[0]
average_elderly_ratio = 20.4
yeongcheon_ratio = df_gyeongbuk[df_gyeongbuk["시군명"] == "영천시"]["고령인구비율(%)"].values[0]



# -----------------------------------------------------
#  의료 탭
# -----------------------------------------------------

# 의료시설 데이터
hospital_df = pd.read_excel(app_dir / "data/hospital_gyeongbuk.xlsx")
pharmacy_df = pd.read_excel(app_dir / "data/pharmacy_gyeongbuk.xlsx")
geo_path = app_dir / "data/sig.shp"

score_df = pd.DataFrame({
    "시군구코드명": ["상주시", "영주시", "영천시"],
    "병원수": [146, 144, 151],
    "약국수": [44, 41, 47],
    "의료점수": [168.0, 164.5, 174.5],
    "총 인구수": [91227, 98228, 97132],
    "인구1만명당_의료점수": [18.42, 16.75, 17.97]
})
coords = {"상주시": [128.159, 36.415], "영주시": [128.623, 36.805], "영천시": [128.938, 35.973]}
score_df["lat"] = score_df["시군구코드명"].map(lambda x: coords[x][1])
score_df["lon"] = score_df["시군구코드명"].map(lambda x: coords[x][0])

target_cities = ["영천시", "상주시", "영주시"]
hospital_df = hospital_df[hospital_df["시군구코드명"].isin(target_cities)]
pharmacy_df = pharmacy_df[pharmacy_df["시군구코드명"].isin(target_cities)]
hospital_df["시설유형"] = "의료기관"
pharmacy_df["시설유형"] = "약국"
hospital_df = hospital_df.rename(columns={"좌표(Y)": "위도", "좌표(X)": "경도"})
pharmacy_df = pharmacy_df.rename(columns={"좌표(Y)": "위도", "좌표(X)": "경도"})
hospital_df = hospital_df[["시군구코드명", "읍면동", "종별코드명", "위도", "경도", "요양기관명", "시설유형"]]
pharmacy_df = pharmacy_df[["시군구코드명", "읍면동", "종별코드명", "위도", "경도", "요양기관명", "시설유형"]]
combined_df = pd.concat([hospital_df, pharmacy_df], ignore_index=True)
unique_types = combined_df["종별코드명"].unique()
type_colors = {t: color for t, color in zip(unique_types, pc.qualitative.Plotly * 3)}
combined_df["색상"] = combined_df["종별코드명"].map(type_colors)

gdf = gpd.read_file(geo_path, encoding="cp949")
gdf = gdf[gdf["SIG_KOR_NM"].isin(target_cities)].copy()
if gdf.crs is None:
    gdf = gdf.set_crs(epsg=5179)
gdf = gdf.to_crs(epsg=4326)
gdf["centroid"] = gdf.geometry.centroid
gdf["lon"] = gdf.centroid.x
gdf["lat"] = gdf.centroid.y
geojson_data = json.loads(gdf.drop(columns=["centroid", "lon", "lat"]).to_json())

##############################################################################
# 교빈 첫페이지 추가!

# 데이터 불러오기 및 병합 처리
gdf1 = gpd.read_file(app_dir / "data/ychsi.shp", encoding="utf-8")
xls = pd.ExcelFile(app_dir / "data/2025.04_age_population_of_Yeongcheon.xlsx")
df = xls.parse('기관별연령별인구통계')

# 열 이름 정리
header1 = df.iloc[4]
header2 = df.iloc[5]
columns = [str(h1).strip() if not pd.isna(h1) else str(h2).strip() for h1, h2 in zip(header1, header2)]
data = df.iloc[6:].copy()
data.columns = columns
total_row = data[data["연령"] == "합   계"]

emd_names = [col for col in columns if col not in ['연령', '영천시', '구성비', '성비', 'nan'] and not col.startswith('Unnamed')]
emd_pop = pd.DataFrame({
    "읍면동명": [name.strip() for name in emd_names],
    "총인구수": [int(str(total_row[name].values[0]).replace(",", "")) for name in emd_names]
})

gdf1.columns = gdf1.columns.str.strip()
gdf1["ADM_NM"] = gdf1["ADM_NM"].str.strip()
emd_pop["읍면동명"] = emd_pop["읍면동명"].str.strip()

if gdf1.crs is None:
    gdf1 = gdf1.set_crs(epsg=5179)
gdf1 = gdf1.to_crs(epsg=4326)

merged = gdf1.merge(emd_pop, left_on="ADM_NM", right_on="읍면동명", how="left")
merged["총인구수"] = merged["총인구수"].fillna(0)
geojson_data = json.loads(merged.to_json())



# -----------------------------------------------------
#  복지 탭
# -----------------------------------------------------

# 📥 1. 개별 데이터 불러오기
df_pop = pd.read_excel(app_dir / "data/읍면동별_전체및고령인구_영천영주상주_행정동처리.xlsx")
df_facility = pd.read_excel(app_dir / "data/노인여가복지시설_읍면동포함_행정동처리.xlsx")

# 📊 2. 시설 개수 집계
df_facility_grouped = (
    df_facility.groupby(["시군", "읍면동"])
    .size()
    .reset_index(name="시설수")
)

# 복지시설 도넛차트용 데이터 전처리
facility_counts = df_facility.groupby(["시군", "시설종류"]).size().reset_index(name="시설수")
total_counts = facility_counts.groupby("시군")["시설수"].sum().reset_index(name="총시설수")
merged_df1 = pd.merge(facility_counts, total_counts, on="시군")
merged_df1["비율"] = merged_df1["시설수"] / merged_df1["총시설수"]



# 2️ 복지시설 개수 집계 (시군 + 읍면동 기준)
facility_counts = (
    df_facility.groupby(["시군", "읍면동"])
    .agg(시설수=("시설명", "count"),
         총이용회원수=("이용회원수", "sum"))
    .reset_index()
)

# 3 인구 데이터와 병합
merged_df2 = pd.merge(
    df_pop,
    facility_counts,
    on=["시군", "읍면동"],
    how="left"
)

# 4️ 시설 없는 지역은 0으로 처리
merged_df2["시설수"] = merged_df2["시설수"].fillna(0)

# 5️ 고령인구 1,000명당 시설 수 계산
merged_df2["고령인구1000명당시설수"] = (
    merged_df2["시설수"] / merged_df2["65세 이상 인구수"] * 1000
)
merged_df2["시군_읍면동"] = merged_df2["시군"] + " " + merged_df2["읍면동"]
merged_sorted = merged_df2.sort_values("고령인구1000명당시설수", ascending=False)

# ▶︎ 평균값 계산
avg_dict = merged_sorted.groupby("시군")["고령인구1000명당시설수"].mean().to_dict()
color_map = {"상주시": "blue", "영천시": "red", "영주시": "green"}

merged_df2["고령인구비율(%)"] = (merged_df2["65세 이상 인구수"] / merged_df2["전체 인구수"]) * 100

# ▶︎ 분위수 기준선 추가 (고령인구 Q3, 시설밀도 Q1)
q75_aging = merged_df2["고령인구비율(%)"].quantile(0.75)
q25_facility = merged_df2["고령인구1000명당시설수"].quantile(0.25)

# 필터링: 복지 사각지대 핵심 후보
core_gap_df = merged_df2[
    (merged_df2["65세 이상 인구수"] >= q75_aging) &
    (merged_df2["고령인구1000명당시설수"] <= q25_facility)].copy()

# 시군+읍면동 이름 결합 (중복 방지용)
core_gap_df["시군_읍면동"] = core_gap_df["시군"] + " " + core_gap_df["읍면동"]

# 파이차트 시각화 함수
def get_region_pie(region_name):
    region_df = merged_df1[merged_df1["시설종류"] == region_name]
    fig = px.pie(
        region_df,
        values="시설수",
        names="시군",
        title=f"{region_name}",
        hole=0.5,
        color="시군",
        color_discrete_sequence=px.colors.qualitative.Set3,
        color_discrete_map={
    "영천시": "#87CEEB",   # Sky Blue
    "상주시": "#2ca02c",   # Soft Green
    "영주시": "#FFD700"    # Gold Yellow
}
    )
    fig.update_traces(
        textinfo="percent+label",
        textposition="inside",  # ← 겹침 방지 핵심
        insidetextorientation='radial')
    return fig



# ① 이용률 계산
merged_df2["이용률(%)"] = (merged_df2["총이용회원수"] / merged_df2["65세 이상 인구수"]) * 100

# ② 고령인구비율 Q3 기준 계산
q75_ratio = merged_df2["고령인구비율(%)"].quantile(0.75)

# ③ 조건: 고령화 심한데 이용률 낮은 지역 추출
df_low_use_high_aging = merged_df2[
    (merged_df2["고령인구비율(%)"] >= q75_ratio)
].sort_values("이용률(%)").head(10)  # 이용률 낮은 순 Top10


# ###########################################################
# 교통카드 데이터 불러오기
df_traffic = pd.read_excel(app_dir / "data/전체_승하차_좌표포함.xlsx").dropna()

# 영천시 범위 기준 필터링
lat_min, lat_max = 35.80, 37.10
lon_min, lon_max = 128.85, 131.15

df_traffic = df_traffic[
    (df_traffic["승차위도"].between(lat_min, lat_max)) &
    (df_traffic["하차위도"].between(lat_min, lat_max)) &
    (df_traffic["승차경도"].between(lon_min, lon_max)) &
    (df_traffic["하차경도"].between(lon_min, lon_max))
]

# 요일, 시간대 파생
weekday_map = {"Monday": "월", "Tuesday": "화", "Wednesday": "수",
               "Thursday": "목", "Friday": "금", "Saturday": "토", "Sunday": "일"}
df_traffic["요일"] = df_traffic["하차시각"].dt.day_name().map(weekday_map)

def get_time_band(hour):
    if 6 <= hour < 9: return "출근시간"
    elif 9 <= hour < 12: return "오전"
    elif 12 <= hour < 14: return "점심시간"
    elif 14 <= hour < 17: return "오후"
    elif 17 <= hour < 20: return "퇴근시간"
    elif 20 <= hour < 24: return "야간"
    else: return "심야"

df_traffic["시간대"] = df_traffic["하차시각"].dt.hour.apply(get_time_band)

# 교통 GeoJSON 경계선 처리
gdf_traffic = gpd.read_file(app_dir / "data/ychsi.shp", encoding="utf-8")
if gdf_traffic.crs is None:
    gdf_traffic = gdf_traffic.set_crs(epsg=5179)
gdf_traffic = gdf_traffic.to_crs(epsg=4326)
geojson_traffic = json.loads(gdf_traffic.to_json())


# GeoJSON
gdf3 = gpd.read_file(app_dir /"data/gdf_processed.geojson")
merged_df3 = pd.read_pickle(app_dir /"data/merged_df.pkl")

center3 = gdf3.geometry.unary_union.centroid




# -----------------------------------------------------
#  체크박스 관련 함수들
# -----------------------------------------------------

@reactive.Calc
def selected_regions():
    regions = []
    if input.chk_sangju():
        regions.append("상주시")
    if input.chk_yeongju():
        regions.append("영주시")
    if input.chk_yeongcheon():
        regions.append("영천시")
    return regions





# -----------------------------------------------------
#  체크박스
# -----------------------------------------------------


@reactive.Calc
def selected_regions():
    return input.selected_city()

@reactive.Calc
def filtered_combined_df():
    return combined_df[combined_df["시군구코드명"].isin(selected_regions())]

@reactive.Calc
def filtered_hospital_df():
    return hospital_df[hospital_df["시군구코드명"].isin(selected_regions())]

@reactive.Calc
def filtered_pharmacy_df():
    return pharmacy_df[pharmacy_df["시군구코드명"].isin(selected_regions())]

@reactive.Calc
def filtered_score_df():
    return score_df[score_df["시군구코드명"].isin(selected_regions())]



@reactive.Calc
def selected_regions():
    regions = []
    if input.chk_sangju():
        regions.append("상주시")
    if input.chk_yeongju():
        regions.append("영주시")
    if input.chk_yeongcheon():
        regions.append("영천시")
    return regions


# -----------------------------------------------------
#  
# -----------------------------------------------------

import numpy as np

기준값 = 34.3
허용오차 = 10  # 원하는 경우 slider 또는 selectize로 연동 가능
하한 = 기준값 * (1 - 허용오차 / 100)
상한 = 기준값 * (1 + 허용오차 / 100)

df_sorted = df_gyeongbuk2.sort_values(by="고령인구비율(%)", ascending=False).copy()

df_sorted["색상"] = np.select(
    [
        df_sorted["시군명"] == "영천시",  # 조건 1: 영천시
        df_sorted["고령인구비율(%)"].between(하한, 상한)  # 조건 2: 기준 이내
    ],
    [
        "gold",  # 영천시 색상
        "blue"        # 기준 이내 색상
    ],
    default="lightgray"  # 기준 외 색상
)



color_map = {
    "영천시": "#87CEEB",   # Sky Blue
    "상주시": "#2ca02c",   # Soft Green
    "영주시": "#FFD700"    # Gold Yellow
}


# -----------------------------------------------------
#  UI 코드
# -----------------------------------------------------

# 탭 3개로 구성
# 개요/의료/복지/교통or문화
# 🧱 UI 구성
ui.page_opts(title="", theme=theme.superhero)
ui.tags.div(
    "영천시 중심 고령인구 및 인프라 분석 대시보드",
    style="""
        font-size: 40px;
        font-weight: 900;
        color: #FFFFFF;
        text-align: center;
        margin: 40px 0 60px 0;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
        letter-spacing: 1px;
    """
)


# 탭 3개로 구성
# 개요/의료/복지/교통or문화
# 🧱 UI 구성
# ui.page_opts(title="영천시 고령인구 분석 대시보드", fillable=False)

with ui.navset_tab():
    with ui.nav_panel("인구 분포"):
        ui.br()
        # 상단 KPI 카드
        # ----------------------------
        with ui.layout_columns():
            with ui.value_box(showcase=icon_svg("users")):
                ui.h3("영천시 총인구수")
                f"{total_population:,.0f}명"
            with ui.value_box(showcase=icon_svg("earth-americas")):
                ui.h3("전국 고령인구비율")
                f"{average_elderly_ratio:.1f}%"
            with ui.value_box(showcase=icon_svg("person-cane")):
                ui.h3("영천시 고령인구비율")
                f"{yeongcheon_ratio:.1f}%"

        # ----------------------------
        # 🔵 Choropleth 지도 시각화 카드
        # ----------------------------
        with ui.layout_columns():
            with ui.card(full_screen=True):
                ui.h4("영천시 읍면동별 총인구수 분포")
                
            

                @render_plotly
                def choropleth_population():
                    # Choropleth 레이어
                    choropleth = go.Choroplethmapbox(
                        geojson=geojson_data,
                        locations=merged["ADM_CD"],
                        z=merged["총인구수"],
                        featureidkey="properties.ADM_CD",
                        colorscale="Blues",
                        colorbar_title="총인구수",
                        marker_opacity=0.7,
                        marker_line_width=0.5,
                        text=merged["ADM_NM"],
                        hovertemplate="<b>%{text}</b><br>총인구수: %{z:,}명<extra></extra>",
                        name="총인구수"
                    )

                    # 중심좌표 계산용 투영 중심점 처리
                    merged_proj = merged.to_crs(epsg=5179)
                    merged["centroid"] = merged_proj.geometry.centroid.to_crs(epsg=4326)
                    merged["lon"] = merged["centroid"].x
                    merged["lat"] = merged["centroid"].y

                    # 텍스트 레이어
                    text_layer = go.Scattermapbox(
                        lat=merged["lat"],
                        lon=merged["lon"],
                        mode="text",
                        text=merged["ADM_NM"],
                        textfont=dict(size=11, color="black"),
                        hoverinfo="none",
                        name="읍면동 이름"
                    )

                    # 최종 지도 출력
                    fig = go.Figure(data=[choropleth, text_layer])
                    fig.update_layout(
                        mapbox_style="carto-positron",
                        mapbox_zoom=9.6,
                        mapbox_center={"lat": merged["lat"].mean(), "lon": merged["lon"].mean()},
                        margin={"r": 0, "t": 30, "l": 0, "b": 0}
                    )
                    return fig
        
            with ui.card(full_screen=True):
                ui.h4("연도별 영천시 총인구수 및 고령인구 비율")
                ui.p( "영천시의 총인구수는 해마다 감소하고 있는 반면, 고령인구 비율은 지속적으로 증가하는 추세입니다. 이에 따라 노년층을 위한 인프라가 충분히 마련되어 있는지 점검할 필요성이 커지고 있습니다.",
                     style="font-size: 18px;" )
                @render_plotly
                def population_and_ratio():
                    import plotly.graph_objects as go

                    # 데이터
                    years = [2022, 2023, 2024, 2025]
                    population = [101479, 100951, 100135, 97123]
                    elderly_ratio = [29.81, 30.89, 32.15, 34.33]

                    # ▶ 총인구수 (막대)
                    bar = go.Bar(
                        x=years,
                        y=population,
                        name="총인구수 (명)",
                        yaxis="y1",
                        marker_color="skyblue"
                    )

                    # ▶ 고령인구비율 (선)
                    line = go.Scatter(
                        x=years,
                        y=elderly_ratio,
                        name="고령인구 비율 (%)",
                        yaxis="y2",
                        mode="lines+markers",
                        line=dict(color="tomato"),
                        marker=dict(size=8)
                    )

                    # ▶ 레이아웃
                    layout = go.Layout(
                        xaxis=dict(
                            title="연도",
                            tickmode="array",
                            tickvals=[2022, 2023, 2024, 2025],
                            ticktext=["2022", "2023", "2024", "2025"]
                        ),
                        yaxis=dict(
                            title="총인구수 (명)",
                            title_font=dict(color="skyblue"),
                            tickfont=dict(color="skyblue"),
                            range=[80000, 120000] 
                        ),
                        yaxis2=dict(
                            title="고령인구 비율 (%)",
                            title_font=dict(color="tomato"),
                            tickfont=dict(color="tomato"),
                            overlaying="y",
                            side="right"
                        ),
                        legend=dict(x=0.01, y=0.99),
                        margin=dict(t=30, b=40, l=40, r=40),
                        # template="plotly_dark"
                    )

                    fig = go.Figure(data=[bar, line], layout=layout)
                    return fig



##################################################################################
        # 중단: 트리맵 + 총인구수 막대그래프
        with ui.layout_columns():
            with ui.card(full_screen=True):
                ui.h4("전국 65세 이상 인구비율 분포")
                @render_plotly
                def treemap():
                    fig = px.treemap(
                        df_nation,
                        path=["시도"],
                        values="고령인구비율(%)",
                        color="고령인구비율(%)",
                        color_continuous_scale="PuBuGn",
                        custom_data=["고령인구수_포맷", "총인구수_포맷"],
                    )
                    
                    fig.update_traces(
                        text=df_nation["label"],
                        texttemplate="%{text}",
                        hovertemplate="<b>%{label}</b><br>고령인구비율: %{value}%<br>65세 이상: %{customdata[0]}명<br>총 인구수: %{customdata[1]}명"
                    )
                    return fig

            with ui.card(full_screen=True):
                ui.h4("경상북도 지역별 총 인구수")
                @render_plotly
                def bar_chart():
                    fig = px.bar(
                        df_gyeongbuk,
                        x="총인구수",
                        y="시군명",
                        orientation='h',
                        color="색상",
                        color_discrete_map="identity",
                        text="총인구수",
                        category_orders={"시군명": df_gyeongbuk["시군명"].tolist()}
                    )

                    fig.update_traces(
                        texttemplate="%{text:,}명",
                        textposition="outside",
                        marker_line_width=1,
                        hovertemplate="총 인구수: %{x:,}명<br>시군명: %{y}<extra></extra>"
                    )

                    fig.update_layout(
                        # title="경상북도 시군별 총 인구수",
                        xaxis_title="총 인구수 (명)",
                        yaxis_title="",
                        showlegend=False,
                        margin=dict(t=40, l=80, r=40, b=40)
                    )
                    return fig

        # 하단: 고령인구비율 비교
        with ui.layout_columns():
            with ui.card(full_screen=True, width="2/3"):
                    ui.h4("경상북도 지역별 고령인구비율")
                    @render_plotly
                    def bar_compare():
                        # target = ["영주시", "영천시", "상주시"]
                        # df_target = df_gyeongbuk[df_gyeongbuk["시군명"].isin(target)].dropna(subset=["고령인구비율(%)"]).copy()
                        fig = px.bar(
                            df_sorted,
                            x="시군명",
                            y="고령인구비율(%)",
                            text="고령인구비율(%)",
                            color="색상",
                            color_discrete_map="identity",
                            category_orders={"시군명": df_sorted["시군명"].tolist()}
                            # title="고령인구비율 비교"
                        )

                        fig.update_traces(
                            texttemplate="%{text:.1f}%",
                            textposition="outside"
                        )

                        fig.update_layout(
                            yaxis_title="고령인구비율 (%)",
                            xaxis_title="시군명",
                            yaxis=dict(range=[0, df_sorted["고령인구비율(%)"].max() + 5]),
                            showlegend=False,
                            margin=dict(t=40, l=40, r=40, b=40)
                        )
                        return fig
                    
            with ui.card(full_screen=True):
                ui.h4("총인구수 & 고령인구비율 유사 지역 (영천시 기준 10%이내)")

                with ui.value_box(showcase=icon_svg("map-pin")):
                    ui.h4("비교군 ①")
                    ui.h2("영주시")

                with ui.value_box(showcase=icon_svg("map-pin")):
                    ui.h4("비교군 ②")
                    ui.h2("상주시")
                    
            # with ui.layout_columns():
            #     with ui.value_box(showcase=icon_svg("map-pin"), width="1/2"):  # 또는 적절한 아이콘
            #         ui.h4("비교군 ①")
            #         ui.h2("영주시")

            #     with ui.value_box(showcase=icon_svg("map-pin"), width="1/2"):
            #         ui.h4("비교군 ②")
            #         ui.h2("상주시")
                            

    with ui.nav_panel("의료시설 인프라"):
        # ✅ 시군구 필터 (왼쪽 사이드 느낌) - layout_sidebar 활용
        # with ui.layout_sidebar():
        #     with ui.sidebar(title="필터 설정", open="closed", width="250px"):
        #         ui.input_checkbox_group(
        #             "selected_city",
        #             "시군구 필터",
        #             choices=["상주시", "영주시", "영천시"],
        #             selected=["상주시", "영주시", "영천시"]
        #         )

        ui.br()
        with ui.card():
            ui.h4("지역 필터")
            with ui.layout_columns():  #  가로로 정렬
                ui.input_checkbox("chk_sangju", "상주시", value=True)
                ui.input_checkbox("chk_yeongju", "영주시", value=True)
                ui.input_checkbox("chk_yeongcheon", "영천시", value=True)






        with ui.layout_columns():
            with ui.card(full_screen=True):
                ui.h4("영주시 vs 영천시 vs 상주시 의료시설 분포 (행정동 경계 포함)")

                @render_plotly
                def map_all_med():
                    combined_df = filtered_combined_df()

                    #  행정동 경계 (gdf3 사용)
                    choropleth = go.Choroplethmapbox(
                        geojson=gdf3.__geo_interface__,
                        locations=gdf3["geo_id"],  # gdf3에는 geo_id가 고유 ID
                        z=[1] * len(gdf3),  # 시각화를 위한 dummy 값
                        featureidkey="properties.geo_id",
                        colorscale="Greys",  # 연한 회색으로 행정동만 윤곽 표시
                        marker_opacity=0.15,
                        marker_line_width=1,
                        text=gdf3["행정동"],
                        hovertemplate="<b>%{text}</b><extra></extra>",
                        showscale=False
                    )

                    #  의료시설 점
                    facility_traces = []
                    for 종별, group in combined_df.groupby("종별코드명"):
                        facility_traces.append(go.Scattermapbox(
                            lat=group["위도"], lon=group["경도"],
                            mode="markers",
                            marker=dict(size=8, color=group["색상"].iloc[0]),
                            text=group["요양기관명"],
                            hovertemplate=f"<b>{종별}</b><br>%{{text}}<extra></extra>",
                            name=종별
                        ))

                    #  전체 통합
                    fig = go.Figure(data=[choropleth] + facility_traces)
                    fig.update_layout(
                        mapbox_style="carto-positron",
                        mapbox_zoom=7.3,
                        mapbox_center={
                            "lat": combined_df["위도"].mean(),
                            "lon": combined_df["경도"].mean()
                        },
                        margin=dict(t=40, r=20, b=20, l=20),
                        legend=dict(x=0, y=1)
                    )

                    return fig
                    # output_widget("map_all_med", width="100%", height="800px")
            with ui.card(full_screen=True):
                    ui.h4("지역별 병원 종류 비교")
                    @render_plotly
                    def hospital_chart_med():
                        grouped = filtered_hospital_df().groupby(["시군구코드명", "종별코드명"]).size().reset_index(name="count")
                        fig = px.bar(
                            grouped,
                            x="종별코드명", y="count",
                            color="시군구코드명",
                            barmode="group",
                            # title="병원 종별코드 분포"
                            color_discrete_map={
    "영천시": "#87CEEB",   # Sky Blue
    "상주시": "#2ca02c",   # Soft Green
    "영주시": "#FFD700"    # Gold Yellow
}
                        )
                        # fig.update_layout(width=1000, height=700, autosize=False)
                        return fig
                    # output_widget("hospital_chart_med", height="800px")
        with ui.layout_columns():
            with ui.card(full_screen=True):
                ui.h4("지역별 의료점수")
            # with ui.layout_column_wrap(width=1/3):
                @render_plotly
                def score_bar_med():
                    score_df = filtered_score_df()
                    fig = px.bar(
                        score_df,
                        x="시군구코드명",
                        y="인구1만명당_의료점수",
                        color="시군구코드명",
                        text=score_df["인구1만명당_의료점수"].round(2),
                        color_discrete_map={
    "영천시": "#87CEEB",   # Sky Blue
    "상주시": "#2ca02c",   # Soft Green
    "영주시": "#FFD700"    # Gold Yellow
}
                    )
                    fig.update_traces(textposition="outside")
                    return fig
                # output_widget("score_bar_med", height="400px")
            with ui.card(full_screen=True):
                ui.h4("지역별 약국 수")
                @render_plotly
                def pharmacy_chart_med():
                    grouped = filtered_pharmacy_df().groupby(["시군구코드명", "종별코드명"]).size().reset_index(name="count")
                    fig = px.bar(
                        grouped,
                        x="시군구코드명", y="count",
                        color="시군구코드명",
                        text=grouped["count"].round(2),
                        
                        # title="약국 종별코드 분포"
                        color_discrete_map={
    "영천시": "#87CEEB",   # Sky Blue
    "상주시": "#2ca02c",   # Soft Green
    "영주시": "#FFD700"    # Gold Yellow
}
                    )
                    fig.update_traces(textposition="outside")
                    return fig
                # output_widget("pharmacy_chart_med", height="400px")
            with ui.card(full_screen=True):
                ui.h4("지역별 병원 수")
                @render_plotly
                def hospital_total_med():
                    total = filtered_hospital_df().groupby("시군구코드명").size().reset_index(name="총병원수")
                    fig = px.bar(
                        total,
                        x="시군구코드명", y="총병원수",
                        color="시군구코드명",
                        text="총병원수",
                        # title="시군구별 병원 수"
                        color_discrete_map={
    "영천시": "#87CEEB",   # Sky Blue
    "상주시": "#2ca02c",   # Soft Green
    "영주시": "#FFD700"    # Gold Yellow
}
                    )
                    fig.update_traces(textposition="outside")
                    return fig
                # output_widget("hospital_total_med", height="400px")





    with ui.nav_panel("복지시설 인프라"):
        ui.br()
        with ui.layout_columns():
            with ui.card(full_screen=True):
                ui.h4("지역별 노인여가복지시설 구성 비율")
                with ui.layout_column_wrap(width=1/3):
                    @render_plotly
                    def sangju_pie():
                        fig = get_region_pie("경로당")
                        fig.update_traces(textfont_size=16)  # <- 이 줄을 추가하세요
                        return fig 

                    @render_plotly
                    def yeongju_pie():
                        fig = get_region_pie("노인교실")
                        fig.update_traces(textfont_size=16)  # <- 이 줄을 추가하세요
                        return fig 

                    @render_plotly
                    def yeongcheon_pie():
                        fig = get_region_pie("노인복지관")
                        fig.update_traces(textfont_size=16)  # <- 이 줄을 추가하세요
                        return fig 

        with ui.layout_columns():        
            with ui.card(full_screen=True):
                ui.h4("읍면동별 고령인구 1,000명당 복지시설 수")
                @render_plotly
                def bar_avg_plot():
                # ▶︎ 1. 기본 막대그래프
                    fig = px.bar(
                    merged_sorted,
                    x="시군_읍면동",
                    y="고령인구1000명당시설수",
                    color="시군",
                    labels={"고령인구1000명당시설수": "1000명당 시설 수"},
                    hover_data=["전체 인구수", "65세 이상 인구수", "시설수"],
                    # title="읍면동별 고령인구 1,000명당 복지시설 수"
                    color_discrete_map={
    "영천시": "#87CEEB",   # Sky Blue
    "상주시": "#2ca02c",   # Soft Green
    "영주시": "#FFD700"    # Gold Yellow
}
                    )
                    fig.update_layout(xaxis_tickangle=-45)

                    # ▶ 평균선 추가
                    for 시군명, avg in avg_dict.items():
                        fig.add_trace(go.Scatter(
                            x=merged_sorted["시군_읍면동"],
                            y=[avg] * len(merged_sorted),
                            mode="lines",
                            name=f"{시군명} 평균선",
                            line=dict(color=color_map[시군명], dash="dot"),
                            hoverinfo="skip",
                            showlegend=True,
                        ))


                # ▶︎ 3. 평균선 주석 띄우기 (겹침 방지)
                    fig.add_annotation(
                    x=3, y=avg_dict["상주시"] + 0.5,
                    text=f"상주시 평균: {avg_dict['상주시']:.1f}",
                    showarrow=False,
                    font=dict(color="blue"), bgcolor="white"
                    )
                    fig.add_annotation(
                    x=22, y=avg_dict["영천시"] + 0.5,
                    text=f"영천시 평균: {avg_dict['영천시']:.1f}",
                    showarrow=False,
                    font=dict(color="red"), bgcolor="white"
                    )
                    fig.add_annotation(
                    x=40, y=avg_dict["영주시"] + 0.5,
                    text=f"영주시 평균: {avg_dict['영주시']:.1f}",
                    showarrow=False,
                    font=dict(color="green"), bgcolor="white"
                    )
                    return fig
                
        with ui.layout_columns():
            with ui.card(full_screen=True):
                ui.h4("읍면동별 고령인구 1000명당 복지시설 분포")
                @render_plotly
                def choropleth_plot():
                    fig = px.choropleth_mapbox(
                        merged_df3,
                        geojson=gdf3.__geo_interface__,
                        locations="geo_id",
                        featureidkey="properties.geo_id",
                        color="고령인구1000명당시설수",
                        color_continuous_scale="Blues",
                        mapbox_style="carto-positron",
                        center={"lat": center3.y, "lon": center3.x},
                        zoom=7.3,
                        opacity=0.6,
                        labels={"고령인구1000명당시설수": "1000명당 복지시설 수"}
                    )
                    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
                    return fig

        
        # ▶︎ Shiny UI 구성
        with ui.layout_columns():
            with ui.card(full_screen=True):
                ui.h4("고령인구비율 vs 복지시설 밀도")
                # ui.output_plot("bubble_chart")

                # ▶︎ Shiny 서버: 버블차트 렌더링
                @render_plotly
                def bubble_chart():
                    fig = px.scatter(
                    merged_df2,
                    x="고령인구비율(%)",
                    y="고령인구1000명당시설수",
                    color="시군",
                    hover_name="읍면동",
                    size="총이용회원수",  # 거품 크기 = 총이용회원수
                    color_discrete_sequence=px.colors.qualitative.Set1,
                    # title="고령인구비율 vs 1,000명당 복지시설 수 (시군 비교)"
                    color_discrete_map={
    "영천시": "#87CEEB",   # Sky Blue
    "상주시": "#2ca02c",   # Soft Green
    "영주시": "#FFD700"    # Gold Yellow
}
                    )
                    fig.add_vline(
                        x=q75_aging,
                        line_dash="dot",
                        line_color="gray",
                        annotation_text="고령인구비율 Q3 (상위 25%)",
                        annotation_position="top left"
                    )
                    fig.add_hline(
                        y=q25_facility,
                        line_dash="dot",
                        line_color="gray",
                        annotation_text="시설밀도 Q1 (하위 25%)",
                        annotation_position="bottom right"
                    )

                    fig.update_layout(
                        xaxis_title="고령인구비율(%)",
                        yaxis_title="1,000명당 복지시설 수"
                    )
                    return fig
            
                 
            with ui.card(full_screen=True):
                ui.h4("복지시설 이용률 저조 지역 Top10 (고령화 심화 지역 기준)")

                @render_plotly
                def low_use_top10():
                    fig = px.bar(
                        df_low_use_high_aging,
                        x="읍면동",
                        y="이용률(%)",
                        color="시군",
                        # title="고령화 심한데 이용률 낮은 지역 Top10"
                        color_discrete_map={
    "영천시": "#87CEEB",   # Sky Blue
    "상주시": "#2ca02c",   # Soft Green
    "영주시": "#FFD700"    # Gold Yellow
}
                    )
                    fig.update_layout(
                        xaxis_tickangle=-45,
                        yaxis_title="복지시설 이용률 (%)"
                    )
                    return fig

    with ui.nav_panel("교통 인프라"):
        ui.br()
        
        with ui.layout_columns():
            with ui.card():
                ui.h4("교통카드 기반 이동 경로 분석")
                ui.input_select("weekday", "요일 선택", 
                    choices=["월", "화", "수", "목", "금", "토", "일"], selected="금")
                ui.input_select("timeband", "시간대 선택", 
                    choices=["출근시간", "오전", "점심시간", "오후", "퇴근시간", "야간", "심야"], 
                    selected="퇴근시간")
                
                ui.h5("상위 3개 이동 경로")
                @render.text
                def top3():
                    filtered = df_traffic[(df_traffic["요일"] == input.weekday()) & (df_traffic["시간대"] == input.timeband())]

                    top3_routes = (
                        filtered.groupby(["승차역", "하차역"])["경로이동자수"]
                        .sum()
                        .reset_index()
                    )

                    # 동일 정류장 경로 제거
                    top3_routes = top3_routes[top3_routes["승차역"] != top3_routes["하차역"]]

                    # 정렬 및 상위 3개 추출
                    top3_routes = top3_routes.sort_values("경로이동자수", ascending=False).head(3)

                    if top3_routes.empty:
                        return "❗ 조건에 맞는 이동 경로가 없습니다."

                    return "\n".join([
                        f"{i+1}. {row['승차역']} → {row['하차역']} : {int(row['경로이동자수'])}명"
                        for i, row in top3_routes.iterrows()
                    ])

        with ui.card(full_screen=True):
            ui.h4("이동 경로 지도 시각화")
            
            @render.ui
            def traffic_map():
                filtered = df_traffic[(df_traffic["요일"] == input.weekday()) & (df_traffic["시간대"] == input.timeband())]

                grouped = (
                    filtered.groupby(["승차역", "하차역"])
                    .agg({
                        "승차위도": "mean",
                        "승차경도": "mean",
                        "하차위도": "mean",
                        "하차경도": "mean",
                        "경로이동자수": "sum"
                    })
                    .reset_index()
                )

                # 동일 정류장 경로 제거
                grouped = grouped[grouped["승차역"] != grouped["하차역"]]

                if grouped.empty:
                    return ui.p("해당 조건에 맞는 데이터가 없습니다.")

                max_count = grouped["경로이동자수"].max()
                grouped["color_scale"] = (grouped["경로이동자수"] / max_count * 255).astype(int)
                grouped["color"] = grouped["color_scale"].apply(lambda x: [0, 100 + x // 2, 255])
                grouped["width"] = (grouped["경로이동자수"] / max_count * 10).clip(lower=1)

                geo_layer = pdk.Layer("GeoJsonLayer", geojson_traffic, stroked=True, filled=False,
                                      get_line_color=[0, 0, 0], line_width_min_pixels=1)

                arc_layer = pdk.Layer("ArcLayer", data=grouped,
                                      get_source_position=["승차경도", "승차위도"],
                                      get_target_position=["하차경도", "하차위도"],
                                      get_source_color="color",
                                      get_target_color="color",
                                      get_width="width",
                                      pickable=True)

                boarding_layer = pdk.Layer("ScatterplotLayer", data=grouped,
                                           get_position=["승차경도", "승차위도"],
                                           get_radius=50, get_fill_color=[0, 150, 0, 160])

                alighting_layer = pdk.Layer("ScatterplotLayer", data=grouped,
                                            get_position=["하차경도", "하차위도"],
                                            get_radius=50, get_fill_color=[200, 0, 0, 160])

                view_state = pdk.ViewState(
                    latitude=grouped["승차위도"].mean(),
                    longitude=grouped["승차경도"].mean(),
                    zoom=11,
                    pitch=30,
                )

                deck = pdk.Deck(
                    layers=[geo_layer, arc_layer, boarding_layer, alighting_layer],
                    initial_view_state=view_state,
                    tooltip={"text": "{승차역} → {하차역}\n이동자수: {경로이동자수}"},
                    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
                )

                return ui.tags.iframe(
                    srcDoc=deck.to_html(as_string=True, notebook_display=False),
                    style="width:100%; height:800px; border:none;"
                )

        with ui.layout_columns():
            with ui.card(full_screen=True):
                ui.h4("시간대별 총 이동량")
                
                @render_plotly
                def time_analysis():
                    time_summary = df_traffic.groupby("시간대")["경로이동자수"].sum().reset_index()
                    
                    fig = px.bar(
                        time_summary,
                        x="시간대",
                        y="경로이동자수",
                        color="시간대",
                        text="경로이동자수"
                    )
                    
                    fig.update_traces(texttemplate="%{text:,}명", textposition="outside")
                    fig.update_layout(
                        xaxis_title="시간대",
                        yaxis_title="총 이동자수 (명)",
                        showlegend=False
                    )
                    return fig

            with ui.card(full_screen=True):
                ui.h4("요일별 총 이동량")
                
                @render_plotly
                def weekday_analysis():
                    weekday_summary = df_traffic.groupby("요일")["경로이동자수"].sum().reset_index()
                    
                    # 요일 순서 정렬
                    weekday_order = ["월", "화", "수", "목", "금", "토", "일"]
                    weekday_summary["요일"] = pd.Categorical(weekday_summary["요일"], categories=weekday_order, ordered=True)
                    weekday_summary = weekday_summary.sort_values("요일")
                    
                    fig = px.line(
                        weekday_summary,
                        x="요일",
                        y="경로이동자수",
                        markers=True,
                        text="경로이동자수"
                    )
                    
                    fig.update_traces(texttemplate="%{text:,}명", textposition="top center")
                    fig.update_layout(
                        xaxis_title="요일",
                        yaxis_title="총 이동자수 (명)"
                    )
                    return fig