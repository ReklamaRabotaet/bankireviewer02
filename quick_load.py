#!/usr/bin/env python3
"""
Быстрая загрузка реальных данных из XLSX
"""

import pandas as pd
import psycopg2
import os
import re
from datetime import datetime

# Подключение к БД
DATABASE_URL = os.getenv('DATABASE_URL')

def clean_text(text):
    """Очистка HTML"""
    if not text:
        return ""
    text = str(text)
    text = re.sub(r'<[^>]+>', '', text)  # HTML теги
    text = re.sub(r'&[#\w]+;', ' ', text)  # HTML entities
    text = re.sub(r'\s+', ' ', text).strip()  # Пробелы
    return text

def main():
    print("🚀 Быстрая загрузка XLSX данных...")
    
    try:
        # Читаем данные
        df = pd.read_excel('attached_assets/gazprombank_auto_credit_1759018718881.xlsx')
        print(f"📊 Загружено {len(df)} записей")
        
        # Подготовка данных
        data = []
        for _, row in df.iterrows():
            text = clean_text(row.get('text', ''))
            if len(text) < 20:  # Пропускаем короткие
                continue
                
            try:
                date_create = pd.to_datetime(row['dateCreate']).to_pydatetime()
            except:
                date_create = datetime.now()
                
            data.append((
                str(row['id']),
                text[:4000],  # Ограничиваем длину
                max(1, min(5, int(row.get('grade', 1)))),
                'Автокредиты',
                date_create,
                'Газпромбанк'
            ))
        
        print(f"✅ Подготовлено {len(data)} записей для загрузки")
        
        # Массовая загрузка
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Вставляем все одним запросом
        args_str = ','.join(cur.mogrify("(%s,%s,%s,%s,%s,%s)", row).decode('utf-8') for row in data)
        
        cur.execute(f"""
            INSERT INTO reviews (review_id, text, grade, service_category, date_create, bank_name)
            VALUES {args_str}
            ON CONFLICT (review_id) DO NOTHING
        """)
        
        conn.commit()
        
        # Проверяем результат
        cur.execute("SELECT COUNT(*) FROM reviews")
        total = cur.fetchone()[0]
        print(f"🎉 Загружено {total} реальных отзывов в БД!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()