from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import duckdb
import glob
import os
from typing import Optional

app = FastAPI()

# 1. Markets 컬럼 정제 표현식 ("개인" 포함 시 '개인 슈퍼'로 치환)
MARKET_EXPR = "CASE WHEN \"Markets\" LIKE '%개인%' THEN '개인 슈퍼' ELSE \"Markets\" END"

# 2. 제조사(MANUFACTURER) 정제 표현식 (분유 시트의 '파스퇴르' 및 롯데 계열사를 '롯데웰푸드'로 통합)
MFR_EXPR = """
CASE 
    WHEN "MANUFACTURER" IN ('파스퇴르', '롯데제과', '롯데푸드', '롯데웰푸드') THEN '롯데웰푸드'
    ELSE COALESCE("MANUFACTURER", '기타')
END
"""

# 3. Periods -> "YY년 MM월" 및 정렬용 YYYYMM 생성 표현식
PERIOD_FORMAT_EXPR = """
CASE 
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'JAN' THEN SUBSTRING("Periods", 5, 2) || '년 01월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'FEB' THEN SUBSTRING("Periods", 5, 2) || '년 02월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'MAR' THEN SUBSTRING("Periods", 5, 2) || '년 03월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'APR' THEN SUBSTRING("Periods", 5, 2) || '년 04월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'MAY' THEN SUBSTRING("Periods", 5, 2) || '년 05월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'JUN' THEN SUBSTRING("Periods", 5, 2) || '년 06월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'JUL' THEN SUBSTRING("Periods", 5, 2) || '년 07월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'AUG' THEN SUBSTRING("Periods", 5, 2) || '년 08월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'SEP' THEN SUBSTRING("Periods", 5, 2) || '년 09월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'OCT' THEN SUBSTRING("Periods", 5, 2) || '년 10월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'NOV' THEN SUBSTRING("Periods", 5, 2) || '년 11월'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'DEC' THEN SUBSTRING("Periods", 5, 2) || '년 12월'
    ELSE "Periods"
END
"""

PERIOD_SORT_EXPR = """
CASE 
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'JAN' THEN '20' || SUBSTRING("Periods", 5, 2) || '01'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'FEB' THEN '20' || SUBSTRING("Periods", 5, 2) || '02'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'MAR' THEN '20' || SUBSTRING("Periods", 5, 2) || '03'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'APR' THEN '20' || SUBSTRING("Periods", 5, 2) || '04'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'MAY' THEN '20' || SUBSTRING("Periods", 5, 2) || '05'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'JUN' THEN '20' || SUBSTRING("Periods", 5, 2) || '06'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'JUL' THEN '20' || SUBSTRING("Periods", 5, 2) || '07'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'AUG' THEN '20' || SUBSTRING("Periods", 5, 2) || '08'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'SEP' THEN '20' || SUBSTRING("Periods", 5, 2) || '09'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'OCT' THEN '20' || SUBSTRING("Periods", 5, 2) || '10'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'NOV' THEN '20' || SUBSTRING("Periods", 5, 2) || '11'
    WHEN UPPER(SUBSTRING("Periods", 1, 3)) = 'DEC' THEN '20' || SUBSTRING("Periods", 5, 2) || '12'
    ELSE "Periods"
END
"""

@app.get("/api/sheets")
def get_sheets():
    files = glob.glob("data_*.parquet")
    sheet_list = [
        {"file": os.path.basename(f), "name": os.path.basename(f).replace("data_", "").replace(".parquet", "")}
        for f in files
    ]
    return {"sheets": sheet_list}

@app.get("/api/filters/{file_name}")
def get_filter_options(file_name: str):
    if not file_name.startswith("data_") or not file_name.endswith(".parquet"):
        return {"error": "Invalid file"}
    
    conn = duckdb.connect()
    
    markets = [r[0] for r in conn.execute(f"SELECT DISTINCT {MARKET_EXPR} as mkt FROM '{file_name}' WHERE \"Markets\" IS NOT NULL ORDER BY mkt").fetchall()]
    periods = [r[0] for r in conn.execute(f"SELECT DISTINCT \"Periods\" FROM '{file_name}' WHERE \"Periods\" IS NOT NULL").fetchall()]
    
    month_map = {
        "JAN": "01월", "FEB": "02월", "MAR": "03월", "APR": "04월", "MAY": "05월", "JUN": "06월",
        "JUL": "07월", "AUG": "08월", "SEP": "09월", "OCT": "10월", "NOV": "11월", "DEC": "12월"
    }
    
    years = set()
    months = set()
    
    for p in periods:
        p_clean = p.strip()
        if len(p_clean) >= 6:
            m_str = p_clean[:3].upper()
            y_str = p_clean[4:6]
            if m_str in month_map:
                months.add(m_str)
            if y_str.isdigit():
                years.add(f"20{y_str}년")
                
    # 제조사 목록 (롯데웰푸드 우선 정렬)
    mfrs_raw = [r[0] for r in conn.execute(f"SELECT DISTINCT {MFR_EXPR} as mfr FROM '{file_name}' ORDER BY mfr").fetchall()]
    manufacturers = sorted(mfrs_raw, key=lambda x: (0 if x == '롯데웰푸드' else 1, x))
    
    return {
        "markets": markets,
        "years": sorted(list(years), reverse=True),
        "months": sorted(list(months), key=lambda x: list(month_map.keys()).index(x)),
        "manufacturers": manufacturers
    }

@app.get("/api/dashboard/{file_name}")
def get_dashboard_data(
    file_name: str, 
    market: Optional[str] = None,
    year: Optional[str] = None,
    month: Optional[str] = None,
    manufacturer: Optional[str] = None,
    search: Optional[str] = None
):
    if not file_name.startswith("data_") or not file_name.endswith(".parquet"):
        return {"error": "Invalid file"}

    conn = duckdb.connect()
    
    where_clauses = ["1=1"]
    if market and market != "ALL":
        where_clauses.append(f"{MARKET_EXPR} = '{market}'")
    if year and year != "ALL":
        y_short = year.replace("20", "").replace("년", "")
        where_clauses.append(f"SUBSTRING(\"Periods\", 5, 2) = '{y_short}'")
    if month and month != "ALL":
        where_clauses.append(f"UPPER(SUBSTRING(\"Periods\", 1, 3)) = '{month}'")
    if manufacturer and manufacturer != "ALL":
        where_clauses.append(f"{MFR_EXPR} = '{manufacturer}'")
    if search:
        where_clauses.append(f"(\"ITEM\" ILIKE '%{search}%' OR \"BRAND\" ILIKE '%{search}%')")
    
    where_sql = " AND ".join(where_clauses)

    # 1. 전체 KPI 및 자사(롯데웰푸드) 전용 KPI 계산
    kpi_query = f"""
        SELECT 
            COALESCE(SUM("판매액 (백만원)") / 100.0, 0) as total_sales_eok,
            COALESCE(SUM(CASE WHEN {MFR_EXPR} = '롯데웰푸드' THEN "판매액 (백만원)" ELSE 0 END) / 100.0, 0) as lotte_sales_eok,
            COALESCE(SUM("판매수량 (000)"), 0) as total_qty,
            COALESCE(SUM(CASE WHEN {MFR_EXPR} = '롯데웰푸드' THEN "판매수량 (000)" ELSE 0 END), 0) as lotte_qty,
            COUNT(DISTINCT {MFR_EXPR}) as manufacturer_count,
            COUNT(DISTINCT "ITEM") as item_count
        FROM '{file_name}'
        WHERE {where_sql}
    """
    kpi = conn.execute(kpi_query).df().to_dict(orient="records")[0]
    
    # 롯데웰푸드 점유율(M/S %) 계산
    total_sales = kpi["total_sales_eok"]
    lotte_sales = kpi["lotte_sales_eok"]
    kpi["lotte_ms"] = round((lotte_sales / total_sales * 100), 2) if total_sales > 0 else 0.0

    # 2. 제조사 전체 순위 및 매출 비중 (Top 10)
    mfr_query = f"""
        SELECT 
            {MFR_EXPR} as manufacturer,
            SUM("판매액 (백만원)") / 100.0 as sales_eok
        FROM '{file_name}'
        WHERE {where_sql}
        GROUP BY {MFR_EXPR}
        ORDER BY sales_eok DESC
    """
    mfr_all = conn.execute(mfr_query).df().to_dict(orient="records")
    
    # 자사 랭킹 산출
    lotte_rank = "-"
    for idx, row in enumerate(mfr_all):
        if row["manufacturer"] == "롯데웰푸드":
            lotte_rank = f"{idx + 1}위"
            break
    kpi["lotte_rank"] = lotte_rank
    mfr_df = mfr_all[:8]

    # 3. Top 10 브랜드 매출 (자사 브랜드 여부 태깅)
    brand_query = f"""
        SELECT 
            COALESCE("BRAND", '미분류') as brand,
            {MFR_EXPR} as manufacturer,
            SUM("판매액 (백만원)") / 100.0 as sales_eok
        FROM '{file_name}'
        WHERE {where_sql}
        GROUP BY "BRAND", {MFR_EXPR}
        ORDER BY sales_eok DESC
        LIMIT 10
    """
    brand_df = conn.execute(brand_query).df().to_dict(orient="records")

    # 4. 시계열 데이터 (YY년 MM월 순서 정렬 및 모든 제조사별 월별 매출 딕셔너리 구축)
    period_meta_query = f"""
        SELECT DISTINCT 
            {PERIOD_FORMAT_EXPR} as formatted_period,
            {PERIOD_SORT_EXPR} as sort_key
        FROM '{file_name}'
        WHERE {where_sql}
        ORDER BY sort_key ASC
    """
    period_meta = conn.execute(period_meta_query).df().to_dict(orient="records")
    formatted_periods = [p["formatted_period"] for p in period_meta]

    # 모든 제조사의 시계열 추이 데이터
    all_mfr_trend_query = f"""
        SELECT 
            {MFR_EXPR} as manufacturer,
            {PERIOD_FORMAT_EXPR} as formatted_period,
            {PERIOD_SORT_EXPR} as sort_key,
            SUM("판매액 (백만원)") / 100.0 as sales_eok
        FROM '{file_name}'
        WHERE {where_sql}
        GROUP BY {MFR_EXPR}, {PERIOD_FORMAT_EXPR}, {PERIOD_SORT_EXPR}
        ORDER BY sort_key ASC
    """
    trend_rows = conn.execute(all_mfr_trend_query).fetchall()
    
    trend_matrix = {}
    for mfr, p_fmt, _, sales in trend_rows:
        if mfr not in trend_matrix:
            trend_matrix[mfr] = {}
        trend_matrix[mfr][p_fmt] = sales

    # 5. 테이블 데이터
    table_query = f"""
        SELECT 
            {MARKET_EXPR} as "Markets",
            {PERIOD_FORMAT_EXPR} as "Periods", 
            {MFR_EXPR} as "MANUFACTURER", 
            "BRAND", 
            "ITEM", 
            ("판매액 (백만원)" / 100.0) as "판매액 (억원)", 
            "판매수량 (000)"
        FROM '{file_name}'
        WHERE {where_sql}
        ORDER BY "판매액 (억원)" DESC
        LIMIT 200
    """
    table_df = conn.execute(table_query).df().to_dict(orient="records")

    return {
        "kpi": kpi,
        "manufacturers": mfr_df,
        "all_mfr_names": [m["manufacturer"] for m in mfr_all],
        "brands": brand_df,
        "periods_all": formatted_periods,
        "trend_matrix": trend_matrix,
        "table": table_df
    }

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()