#!/usr/bin/env python3
"""
Финальная загрузка данных с правильной обработкой ошибок
"""
import pandas as pd
import psycopg2
import os
import re

print("🚀 Финальная загрузка реальных данных...")

conn = psycopg2.connect(os.getenv('DATABASE_URL'))

# Читаем данные из XLSX
df = pd.read_excel('attached_assets/gazprombank_auto_credit_1759018718881.xlsx', nrows=500)
print(f"📊 Прочитано {len(df)} записей из XLSX")

success_count = 0
error_count = 0

for _, row in df.iterrows():
    cur = conn.cursor()  # Новый курсор для каждой записи
    try:
        # Очистка текста
        text = str(row['text'])
        text = re.sub(r'<[^>]*>', '', text)
        text = text.strip()
        
        if len(text) < 15:  # Пропускаем короткие отзывы
            continue
        
        # Вставка с ON CONFLICT
        cur.execute("""
            INSERT INTO reviews (review_id, text, grade, service_category, date_create, bank_name)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (review_id) DO NOTHING
        """, (
            f"auto_{row['id']}",  # Уникальный префикс
            text[:2000],
            max(1, min(5, int(row['grade']))),
            'Автокредиты', 
            row['dateCreate'],
            'Газпромбанк'
        ))
        
        conn.commit()  # Коммитим каждую запись отдельно
        success_count += 1
        
        if success_count % 50 == 0:
            print(f"✅ Загружено {success_count} записей...")
            
    except Exception as e:
        conn.rollback()  # Откатываем только текущую запись
        error_count += 1
        
    finally:
        cur.close()

print(f"\n🎉 Загрузка завершена!")
print(f"✅ Успешно: {success_count} записей")
print(f"❌ Ошибок: {error_count} записей")

# Финальная проверка
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM reviews")
total = cur.fetchone()[0]
print(f"📊 Всего в базе: {total} отзывов")

cur.close()
conn.close()