import polars as pl
import fastexcel
import os
import time

input_excel = "raw_data.xlsx"

print(f"[{input_excel}] 다중 시트 변환을 시작합니다...")
start_time = time.time()

try:
    # 1. 엑셀 파일 내의 모든 시트 이름 가져오기
    excel_file = fastexcel.read_excel(input_excel)
    sheet_names = excel_file.sheet_names
    print(f"발견된 시트 목록 ({len(sheet_names)}개): {sheet_names}\n")

    total_rows = 0
    total_parquet_size = 0

    # 2. 각 시트별로 순회하며 개별 Parquet 파일로 저장
    for sheet in sheet_names:
        sheet_start = time.time()
        
        # 시트 데이터 읽기
        df = pl.read_excel(input_excel, sheet_name=sheet)
        
        # 파일명 생성 (특수문자/공백 처리)
        safe_sheet_name = "".join(c for c in sheet if c.isalnum() or c in (' ', '_', '-')).strip()
        output_parquet = f"data_{safe_sheet_name}.parquet"
        
        # Parquet으로 저장
        df.write_parquet(output_parquet, compression="zstd")
        
        p_size = round(os.path.getsize(output_parquet) / (1024 * 1024), 2)
        total_parquet_size += p_size
        total_rows += df.height
        
        print(f" - [{sheet}] -> {output_parquet} 저장 완료 ({df.height:,}행 / {df.width}열 / {p_size} MB / {round(time.time() - sheet_start, 2)}초)")

    elapsed_time = round(time.time() - start_time, 2)
    orig_size = round(os.path.getsize(input_excel) / (1024 * 1024), 2)

    print("\n--- 전체 변환 완료 ---")
    print(f"총 소요 시간: {elapsed_time}초")
    print(f"총 데이터 행 수: {total_rows:,}개")
    print(f"원본 엑셀 크기: {orig_size} MB")
    print(f"변환된 Parquet 총합 크기: {round(total_parquet_size, 2)} MB")

except Exception as e:
    print(f"\n[오류 발생]: {e}")