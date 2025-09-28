#!/usr/bin/env python3
"""
Минимальная загрузка данных
"""
import pandas as pd
import psycopg2
import os

DATABASE_URL = os.getenv('DATABASE_URL')

# Загрузить только первые 1000 записей быстро
df = pd.read_excel('attached_assets/gazprombank_auto_credit_1759018718881.xlsx', nrows=1000)
print(f"Загружаем {len(df)} записей...")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

for i, row in df.iterrows():
    text = str(row['text']).replace('<p>', '').replace('</p>', '')[:500]
    if len(text) < 10:
        continue
    try:
        cur.execute("""
            INSERT INTO reviews (review_id, text, grade, service_category, date_create, bank_name)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (review_id) DO NOTHING
        """, (str(row['id']), text, int(row['grade']), 'Автокредиты', 
              pd.to_datetime(row['dateCreate']), 'Газпромбанк'))
        if i % 100 == 0:
            conn.commit()
            print(f"Загружено {i} записей")
    except:
        continue

conn.commit()
print(f"✅ Загружено записей!")
cur.close()
conn.close()