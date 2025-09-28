#!/usr/bin/env python3
"""
Упрощенная миграция реальных данных из CSV в PostgreSQL
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import os
import re
from datetime import datetime

# Настройки подключения к базе данных
DATABASE_URL = os.getenv('DATABASE_URL')

def clean_html_simple(text):
    """Простая очистка HTML тегов"""
    if not text or pd.isna(text):
        return ""
    
    # Убираем HTML теги простым regex
    text = str(text)
    text = re.sub(r'<[^>]+>', '', text)  # Убираем все HTML теги
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)  # Убираем HTML entities
    text = re.sub(r'\s+', ' ', text).strip()  # Убираем лишние пробелы
    
    return text

def parse_date_simple(date_str):
    """Простой парсинг даты"""
    if not date_str or pd.isna(date_str):
        return datetime.now()
    
    try:
        return pd.to_datetime(date_str).to_pydatetime()
    except:
        return datetime.now()

def migrate_data():
    """Миграция данных"""
    print("🚀 Загружаем реальные данные из CSV...")
    
    # Подключение к БД
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        csv_file = './data/csv/gazprombank_reviews.csv'
        
        print(f"📂 Читаем файл: {csv_file}")
        
        # Читаем первые 50000 записей для начала
        df = pd.read_csv(csv_file, nrows=50000)
        print(f"📊 Загружено {len(df)} записей из CSV")
        
        records = []
        processed = 0
        
        for _, row in df.iterrows():
            try:
                # Очищаем текст
                text = clean_html_simple(row.get('text', ''))
                
                # Пропускаем пустые отзывы
                if not text.strip() or len(text) < 10:
                    continue
                
                record = (
                    str(row.get('id', '')),  # review_id
                    text[:4000],  # text (ограничиваем длину)
                    min(max(int(row.get('grade', 3)), 1), 5) if pd.notna(row.get('grade')) else 3,  # grade 1-5
                    str(row.get('service_category', 'Неопределено'))[:100],  # service_category
                    parse_date_simple(row.get('dateCreate')),  # date_create
                    str(row.get('company_name', 'Газпромбанк'))[:100],  # bank_name
                )
                
                records.append(record)
                processed += 1
                
                # Вставляем данные партиями по 1000
                if len(records) >= 1000:
                    insert_query = """
                        INSERT INTO reviews (review_id, text, grade, service_category, date_create, bank_name)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    
                    execute_batch(cursor, insert_query, records, page_size=500)
                    conn.commit()
                    
                    print(f"✅ Вставлено {len(records)} записей. Всего обработано: {processed}")
                    records = []
                
            except Exception as e:
                print(f"⚠️ Ошибка записи {row.get('id', 'N/A')}: {e}")
                continue
        
        # Вставляем оставшиеся записи
        if records:
            insert_query = """
                INSERT INTO reviews (review_id, text, grade, service_category, date_create, bank_name)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            execute_batch(cursor, insert_query, records, page_size=500)
            conn.commit()
            
            print(f"✅ Вставлено финальных {len(records)} записей")
        
        # Проверяем результат
        cursor.execute("SELECT COUNT(*) FROM reviews")
        total = cursor.fetchone()[0]
        
        print(f"🎉 Миграция завершена! Всего в БД: {total} отзывов")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
        raise
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    migrate_data()