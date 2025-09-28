#!/usr/bin/env python3
"""
Простая вставка первых 100 записей из XLSX
"""
import pandas as pd
import psycopg2
import os
import re

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Читаем только первые 100 записей
print("📊 Читаем XLSX...")
df = pd.read_excel('attached_assets/gazprombank_auto_credit_1759018718881.xlsx', nrows=100)
print(f"Прочитано {len(df)} записей")

# Вставляем по одной записи
count = 0
for _, row in df.iterrows():
    try:
        # Простая очистка текста
        text = str(row['text'])
        text = re.sub(r'<[^>]*>', '', text)  # Убираем HTML теги
        text = text.strip()
        
        if len(text) < 10:  # Пропускаем короткие
            continue
            
        # Простая вставка
        cur.execute("""
            INSERT INTO reviews (review_id, text, grade, service_category, date_create, bank_name)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            str(row['id']),
            text[:1000],  # Ограничиваем длину
            int(row['grade']),
            'Автокредиты',
            str(row['dateCreate']),
            'Газпромбанк'
        ))
        count += 1
        print(f"✅ Добавлено {count} записей", end='\r')
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        continue

conn.commit()
print(f"\n🎉 Всего загружено: {count} записей")
cur.close()
conn.close()