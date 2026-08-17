from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import duckdb
import os
import urllib.parse
from typing import Optional

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 모든 컬럼을 동적으로 찾아주는 헬퍼 함수
def resolve_columns(conn, file_path):
    # 파일 내 실제 컬럼 목록 추출
    cols = [c[0] for c in conn.execute(f"DESCRIBE SELECT * FROM '{file_path}'").fetchall()]
    
    def match_column(candidates, fallback):
        # 1순위: 대소문자 및 공백 제거 후 완벽 일치 검색
        for cand in candidates:
            for c in cols:
                if cand.lower().replace(" ", "") == c.lower().replace(" ", ""):
                    return c
        # 2순위: 부분 일치 검색 (예: '판매액' 키워드 포함)
        for cand in candidates:
            for c in cols:
                if cand.lower().replace(" ", "") in c.lower().replace(" ", ""):
                    return c
        return fallback

    # 핵심 데이터 컬럼 자동 감지
    mfr_col = match_column(["제조사", "MANUFACTURER"], "MANUFACTURER")
    brand_col = match_column(["브랜드", "BRAND"], "BRAND")
    market_col = match_column(["Markets", "MARKET", "채널", "유통"], "Markets")
    period_col = match_column(["Periods", "PERIOD", "기간", "년월"], "Periods")
    item_col = match_column(["ITEM", "제품", "품목"], "ITEM")
    sales_col = match_column(["판매액(백만원)", "판매액", "Sales", "Value"], "판매액 (백만원)")
    qty_col = match_column(["판매수량(000)", "판매수량", "Volume", "Qty"], "판매수량 (000)")
    dist_col = match_column(["Numeric취급률", "NumericDistribution", "취급률"], "Numeric 취급률")
    
    has_dist = dist_col in cols
    return mfr_col, brand_col, market_col, period_col, item_col, sales_col, qty_col, dist_col, has_dist

# 동적 기간(Periods) 포맷팅 표현식 생성 함수
def get_period_exprs(period_col):
    format_expr = f"""
    CASE 
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'JAN' THEN SUBSTRING("{period_col}", 5, 2) || '년 01월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'FEB' THEN SUBSTRING("{period_col}", 5, 2) || '년 02월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'MAR' THEN SUBSTRING("{period_col}", 5, 2) || '년 03월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'APR' THEN SUBSTRING("{period_col}", 5, 2) || '년 04월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'MAY' THEN SUBSTRING("{period_col}", 5, 2) || '년 05월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'JUN' THEN SUBSTRING("{period_col}", 5, 2) || '년 06월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'JUL' THEN SUBSTRING("{period_col}", 5, 2) || '년 07월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'AUG' THEN SUBSTRING("{period_col}", 5, 2) || '년 08월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'SEP' THEN SUBSTRING("{period_col}", 5, 2) || '년 09월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'OCT' THEN SUBSTRING("{period_col}", 5, 2) || '년 10월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'NOV' THEN SUBSTRING("{period_col}", 5, 2) || '년 11월'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'DEC' THEN SUBSTRING("{period_col}", 5, 2) || '년 12월'
        ELSE "{period_col}"
    END
    """
    sort_expr = f"""
    CASE 
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'JAN' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '01'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'FEB' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '02'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'MAR' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '03'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'APR' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '04'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'MAY' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '05'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'JUN' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '06'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'JUL' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '07'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'AUG' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '08'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'SEP' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '09'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'OCT' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '10'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'NOV' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '11'
        WHEN UPPER(SUBSTRING("{period_col}", 1, 3)) = 'DEC' THEN '20' || SUBSTRING("{period_col}", 5, 2) || '12'
        ELSE "{period_col}"
    END
    """
    return format_expr, sort_expr

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def serve_dashboard():
    html_path = os.path.join(BASE_DIR, "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/sheets")
def get_sheets():
    try:
        all_files = os.listdir(BASE_DIR)
        parquet_files = [f for f in all_files if f.startswith("data_") and f.endswith(".parquet")]
        sheet_list = [{"file": f, "name": f.replace("data_", "").replace(".parquet", "")} for f in sorted(parquet_files)]
        return {"sheets": sheet_list}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/filters/{file_name}")
def get_filter_options(file_name: str):
    file_path = os.path.join(BASE_DIR, urllib.parse.unquote(file_name))
    if not os.path.exists(file_path): return JSONResponse(status_code=404, content={"error": "File not found"})
    
    conn = duckdb.connect()
    mfr_col, _, market_col, period_col, _, _, _, _, _ = resolve_columns(conn, file_path)
    
    markets = [r[0] for r in conn.execute(f"SELECT DISTINCT \"{market_col}\" FROM '{file_path}' WHERE \"{market_col}\" IS NOT NULL ORDER BY \"{market_col}\"").fetchall()]
    periods = [r[0] for r in conn.execute(f"SELECT DISTINCT \"{period_col}\" FROM '{file_path}' WHERE \"{period_col}\" IS NOT NULL").fetchall()]
    
    month_map = {"JAN": "01월", "FEB": "02월", "MAR": "03월", "APR": "04월", "MAY": "05월", "JUN": "06월", "JUL": "07월", "AUG": "08월", "SEP": "09월", "OCT": "10월", "NOV": "11월", "DEC": "12월"}
    years, months = set(), set()
    for p in periods:
        p_clean = str(p).strip()
        if len(p_clean) >= 6:
            m_str, y_str = p_clean[:3].upper(), p_clean[4:6]
            if m_str in month_map: months.add(m_str)
            if y_str.isdigit(): years.add(f"20{y_str}년")
                
    mfrs_raw = [r[0] for r in conn.execute(f"SELECT DISTINCT \"{mfr_col}\" FROM '{file_path}' WHERE \"{mfr_col}\" IS NOT NULL ORDER BY \"{mfr_col}\"").fetchall()]
    manufacturers = sorted(mfrs_raw, key=lambda x: (0 if x == '롯데웰푸드' else 1, x))
    
    return {"markets": markets, "years": sorted(list(years), reverse=True), "months": sorted(list(months), key=lambda x: list(month_map.keys()).index(x)), "manufacturers": manufacturers}

@app.get("/api/dashboard/{file_name}")
def get_dashboard_data(
    file_name: str, market: Optional[str] = None, year: Optional[str] = None, month: Optional[str] = None, manufacturer: Optional[str] = None, search: Optional[str] = None
):
    file_path = os.path.join(BASE_DIR, urllib.parse.unquote(file_name))
    if not os.path.exists(file_path): return JSONResponse(status_code=404, content={"error": "File not found"})

    conn = duckdb.connect()
    mfr_col, brand_col, market_col, period_col, item_col, sales_col, qty_col, dist_col, has_dist = resolve_columns(conn, file_path)
    period_fmt, period_srt = get_period_exprs(period_col)

    where_clauses = ["1=1"]
    if market and market != "ALL": where_clauses.append(f"\"{market_col}\" = '{market}'")
    if year and year != "ALL": where_clauses.append(f"SUBSTRING(\"{period_col}\", 5, 2) = '{year.replace('20', '').replace('년', '')}'")
    if month and month != "ALL": where_clauses.append(f"UPPER(SUBSTRING(\"{period_col}\", 1, 3)) = '{month}'")
    if manufacturer and manufacturer != "ALL": where_clauses.append(f"\"{mfr_col}\" = '{manufacturer}'")
    if search: where_clauses.append(f"(\"{item_col}\" ILIKE '%{search}%' OR \"{brand_col}\" ILIKE '%{search}%')")
    
    where_sql = " AND ".join(where_clauses)
    dist_sql = f"ROUND(AVG(TRY_CAST(\"{dist_col}\" AS DOUBLE)), 1)" if has_dist else "0.0"

    kpi_query = f"""
        SELECT 
            COALESCE(SUM(TRY_CAST(\"{sales_col}\" AS DOUBLE)) / 100.0, 0) as total_sales_eok,
            COALESCE(SUM(CASE WHEN \"{mfr_col}\" = '롯데웰푸드' THEN TRY_CAST(\"{sales_col}\" AS DOUBLE) ELSE 0 END) / 100.0, 0) as lotte_sales_eok,
            COALESCE(SUM(TRY_CAST(\"{qty_col}\" AS DOUBLE)), 0) as total_qty,
            COALESCE(SUM(CASE WHEN \"{mfr_col}\" = '롯데웰푸드' THEN TRY_CAST(\"{qty_col}\" AS DOUBLE) ELSE 0 END), 0) as lotte_qty,
            {dist_sql} as avg_dist,
            COUNT(DISTINCT \"{mfr_col}\") as manufacturer_count,
            COUNT(DISTINCT \"{item_col}\") as item_count
        FROM '{file_path}' WHERE {where_sql}
    """
    kpi = conn.execute(kpi_query).df().to_dict(orient="records")[0]
    
    total_sales, lotte_sales = kpi["total_sales_eok"], kpi["lotte_sales_eok"]
    kpi["lotte_ms"] = round((lotte_sales / total_sales * 100), 2) if total_sales > 0 else 0.0

    mfr_query = f"""
        SELECT \"{mfr_col}\" as manufacturer, SUM(TRY_CAST(\"{sales_col}\" AS DOUBLE)) / 100.0 as sales_eok
        FROM '{file_path}' WHERE {where_sql} GROUP BY \"{mfr_col}\" ORDER BY sales_eok DESC
    """
    mfr_all = conn.execute(mfr_query).df().to_dict(orient="records")
    
    lotte_rank = "-"
    for idx, row in enumerate(mfr_all):
        if row["manufacturer"] == "롯데웰푸드":
            lotte_rank = f"{idx + 1}위"
            break
    kpi["lotte_rank"] = lotte_rank

    brand_query = f"""
        SELECT COALESCE(\"{brand_col}\", '미분류') as brand, \"{mfr_col}\" as manufacturer, SUM(TRY_CAST(\"{sales_col}\" AS DOUBLE)) / 100.0 as sales_eok
        FROM '{file_path}' WHERE {where_sql} GROUP BY \"{brand_col}\", \"{mfr_col}\" ORDER BY sales_eok DESC LIMIT 10
    """
    brand_df = conn.execute(brand_query).df().to_dict(orient="records")

    period_meta_query = f"""
        SELECT DISTINCT {period_fmt} as formatted_period, {period_srt} as sort_key
        FROM '{file_path}' WHERE {where_sql} ORDER BY sort_key ASC
    """
    formatted_periods = [p["formatted_period"] for p in conn.execute(period_meta_query).df().to_dict(orient="records")]

    all_mfr_trend_query = f"""
        SELECT \"{mfr_col}\" as manufacturer, {period_fmt} as formatted_period, {period_srt} as sort_key, SUM(TRY_CAST(\"{sales_col}\" AS DOUBLE)) / 100.0 as sales_eok
        FROM '{file_path}' WHERE {where_sql} GROUP BY \"{mfr_col}\", {period_fmt}, {period_srt} ORDER BY sort_key ASC
    """
    trend_rows = conn.execute(all_mfr_trend_query).fetchall()
    trend_matrix = {}
    for mfr, p_fmt, _, sales in trend_rows:
        if mfr not in trend_matrix: trend_matrix[mfr] = {}
        trend_matrix[mfr][p_fmt] = sales

    dist_select = f'COALESCE(TRY_CAST(\"{dist_col}\" AS VARCHAR), \'-\') as \"Numeric 취급률\",' if has_dist else '\'-\' as \"Numeric 취급률\",'
    table_query = f"""
        SELECT 
            \"{market_col}\" as \"Markets\", {period_fmt} as \"Periods\", \"{mfr_col}\" as MANUFACTURER, \"{brand_col}\" as BRAND, \"{item_col}\" as ITEM, 
            (TRY_CAST(\"{sales_col}\" AS DOUBLE) / 100.0) as \"판매액 (억원)\", TRY_CAST(\"{qty_col}\" AS DOUBLE) as \"판매수량 (000)\", {dist_select}
        FROM '{file_path}' WHERE {where_sql} ORDER BY \"판매액 (억원)\" DESC LIMIT 200
    """
    table_df = conn.execute(table_query).df().to_dict(orient="records")

    return {
        "kpi": kpi, "has_dist": has_dist, "manufacturers": mfr_all[:8], "all_mfr_names": [m["manufacturer"] for m in mfr_all],
        "brands": brand_df, "periods_all": formatted_periods, "trend_matrix": trend_matrix, "table": table_df
    }