from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import duckdb
import os
import urllib.parse
from typing import Optional

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
        sheet_list = [
            {"file": f, "name": f.replace("data_", "").replace(".parquet", "")}
            for f in sorted(parquet_files)
        ]
        return {"sheets": sheet_list}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/filters/{file_name}")
def get_filter_options(file_name: str):
    decoded_file_name = urllib.parse.unquote(file_name)
    file_path = os.path.join(BASE_DIR, decoded_file_name)
    
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": f"File not found: {decoded_file_name}"})
    
    conn = duckdb.connect()
    
    # 동적 컬럼 확인
    cols = [c[0] for c in conn.execute(f"DESCRIBE SELECT * FROM '{file_path}'").fetchall()]
    mfr_col = "제조사" if "제조사" in cols else "MANUFACTURER"
    
    markets = [r[0] for r in conn.execute(f"SELECT DISTINCT \"Markets\" FROM '{file_path}' WHERE \"Markets\" IS NOT NULL ORDER BY \"Markets\"").fetchall()]
    periods = [r[0] for r in conn.execute(f"SELECT DISTINCT \"Periods\" FROM '{file_path}' WHERE \"Periods\" IS NOT NULL").fetchall()]
    
    month_map = {
        "JAN": "01월", "FEB": "02월", "MAR": "03월", "APR": "04월", "MAY": "05월", "JUN": "06월",
        "JUL": "07월", "AUG": "08월", "SEP": "09월", "OCT": "10월", "NOV": "11월", "DEC": "12월"
    }
    years, months = set(), set()
    for p in periods:
        p_clean = str(p).strip()
        if len(p_clean) >= 6:
            m_str, y_str = p_clean[:3].upper(), p_clean[4:6]
            if m_str in month_map: months.add(m_str)
            if y_str.isdigit(): years.add(f"20{y_str}년")
                
    mfrs_raw = [r[0] for r in conn.execute(f"SELECT DISTINCT \"{mfr_col}\" FROM '{file_path}' WHERE \"{mfr_col}\" IS NOT NULL ORDER BY \"{mfr_col}\"").fetchall()]
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
    decoded_file_name = urllib.parse.unquote(file_name)
    file_path = os.path.join(BASE_DIR, decoded_file_name)
    
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": f"File not found: {decoded_file_name}"})

    conn = duckdb.connect()
    
    # 동적 컬럼 확인
    cols = [c[0] for c in conn.execute(f"DESCRIBE SELECT * FROM '{file_path}'").fetchall()]
    mfr_col = "제조사" if "제조사" in cols else "MANUFACTURER"
    brand_col = "브랜드" if "브랜드" in cols else "BRAND"
    has_dist = "Numeric 취급률" in cols

    where_clauses = ["1=1"]
    if market and market != "ALL": where_clauses.append(f"\"Markets\" = '{market}'")
    if year and year != "ALL": where_clauses.append(f"SUBSTRING(\"Periods\", 5, 2) = '{year.replace('20', '').replace('년', '')}'")
    if month and month != "ALL": where_clauses.append(f"UPPER(SUBSTRING(\"Periods\", 1, 3)) = '{month}'")
    if manufacturer and manufacturer != "ALL": where_clauses.append(f"\"{mfr_col}\" = '{manufacturer}'")
    if search: where_clauses.append(f"(\"ITEM\" ILIKE '%{search}%' OR \"{brand_col}\" ILIKE '%{search}%')")
    
    where_sql = " AND ".join(where_clauses)
    dist_sql = "ROUND(AVG(TRY_CAST(\"Numeric 취급률\" AS DOUBLE)), 1)" if has_dist else "0.0"

    kpi_query = f"""
        SELECT 
            COALESCE(SUM("판매액 (백만원)") / 100.0, 0) as total_sales_eok,
            COALESCE(SUM(CASE WHEN \"{mfr_col}\" = '롯데웰푸드' THEN \"판매액 (백만원)\" ELSE 0 END) / 100.0, 0) as lotte_sales_eok,
            COALESCE(SUM("판매수량 (000)"), 0) as total_qty,
            COALESCE(SUM(CASE WHEN \"{mfr_col}\" = '롯데웰푸드' THEN \"판매수량 (000)\" ELSE 0 END), 0) as lotte_qty,
            {dist_sql} as avg_dist,
            COUNT(DISTINCT \"{mfr_col}\") as manufacturer_count,
            COUNT(DISTINCT \"ITEM\") as item_count
        FROM '{file_path}'
        WHERE {where_sql}
    """
    kpi = conn.execute(kpi_query).df().to_dict(orient="records")[0]
    
    total_sales, lotte_sales = kpi["total_sales_eok"], kpi["lotte_sales_eok"]
    kpi["lotte_ms"] = round((lotte_sales / total_sales * 100), 2) if total_sales > 0 else 0.0

    mfr_query = f"""
        SELECT \"{mfr_col}\" as manufacturer, SUM(\"판매액 (백만원)\") / 100.0 as sales_eok
        FROM '{file_path}'
        WHERE {where_sql}
        GROUP BY \"{mfr_col}\"
        ORDER BY sales_eok DESC
    """
    mfr_all = conn.execute(mfr_query).df().to_dict(orient="records")
    
    lotte_rank = "-"
    for idx, row in enumerate(mfr_all):
        if row["manufacturer"] == "롯데웰푸드":
            lotte_rank = f"{idx + 1}위"
            break
    kpi["lotte_rank"] = lotte_rank

    brand_query = f"""
        SELECT COALESCE(\"{brand_col}\", '미분류') as brand, \"{mfr_col}\" as manufacturer, SUM(\"판매액 (백만원)\") / 100.0 as sales_eok
        FROM '{file_path}'
        WHERE {where_sql}
        GROUP BY \"{brand_col}\", \"{mfr_col}\"
        ORDER BY sales_eok DESC
        LIMIT 10
    """
    brand_df = conn.execute(brand_query).df().to_dict(orient="records")

    period_meta_query = f"""
        SELECT DISTINCT {PERIOD_FORMAT_EXPR} as formatted_period, {PERIOD_SORT_EXPR} as sort_key
        FROM '{file_path}' WHERE {where_sql} ORDER BY sort_key ASC
    """
    formatted_periods = [p["formatted_period"] for p in conn.execute(period_meta_query).df().to_dict(orient="records")]

    all_mfr_trend_query = f"""
        SELECT \"{mfr_col}\" as manufacturer, {PERIOD_FORMAT_EXPR} as formatted_period, {PERIOD_SORT_EXPR} as sort_key, SUM(\"판매액 (백만원)\") / 100.0 as sales_eok
        FROM '{file_path}' WHERE {where_sql}
        GROUP BY \"{mfr_col}\", {PERIOD_FORMAT_EXPR}, {PERIOD_SORT_EXPR}
        ORDER BY sort_key ASC
    """
    trend_rows = conn.execute(all_mfr_trend_query).fetchall()
    trend_matrix = {}
    for mfr, p_fmt, _, sales in trend_rows:
        if mfr not in trend_matrix: trend_matrix[mfr] = {}
        trend_matrix[mfr][p_fmt] = sales

    dist_select = 'COALESCE(\"Numeric 취급률\", \'-\') as \"Numeric 취급률\",' if has_dist else '\'-\' as \"Numeric 취급률\",'
    table_query = f"""
        SELECT 
            \"Markets\", {PERIOD_FORMAT_EXPR} as \"Periods\", \"{mfr_col}\" as MANUFACTURER, \"{brand_col}\" as BRAND, \"ITEM\", 
            (\"판매액 (백만원)\" / 100.0) as \"판매액 (억원)\", \"판매수량 (000)\", {dist_select}
        FROM '{file_path}'
        WHERE {where_sql}
        ORDER BY \"판매액 (억원)\" DESC
        LIMIT 200
    """
    table_df = conn.execute(table_query).df().to_dict(orient="records")

    return {
        "kpi": kpi,
        "has_dist": has_dist,
        "manufacturers": mfr_all[:8],
        "all_mfr_names": [m["manufacturer"] for m in mfr_all],
        "brands": brand_df,
        "periods_all": formatted_periods,
        "trend_matrix": trend_matrix,
        "table": table_df
    }