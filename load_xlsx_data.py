#!/usr/bin/env python3
"""
Загрузка реальных данных из XLSX в PostgreSQL
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
    
    text = str(text)
    # Убираем HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    # Убираем HTML entities
    text = re.sub(r'&[a-zA-Z#0-9]+;', ' ', text)
    # Убираем лишние пробелы и переносы
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def load_xlsx_data():
    """Загружает данные из XLSX файла в PostgreSQL"""
    print("🚀 Начинаем загрузку реальных данных по автокредитам...")
    
    # Подключение к БД
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        xlsx_file = 'attached_assets/gazprombank_auto_credit_1759018718881.xlsx'
        
        print(f"📂 Читаем XLSX файл: {xlsx_file}")
        df = pd.read_excel(xlsx_file)
        print(f"📊 Загружено {len(df):,} записей из XLSX")
        
        records = []
        processed = 0
        skipped = 0
        
        for _, row in df.iterrows():
            try:
                # Очищаем текст отзыва
                text = clean_html_simple(row.get('text', ''))
                
                # Пропускаем очень короткие отзывы
                if not text.strip() or len(text) < 20:
                    skipped += 1
                    continue
                
                # Парсим дату
                try:
                    date_create = pd.to_datetime(row.get('dateCreate')).to_pydatetime()
                except:
                    date_create = datetime.now()
                
                # Формируем запись
                record = (
                    str(row.get('id', f'auto_{processed}')),  # review_id
                    text[:4000],  # text (ограничиваем длину)
                    min(max(int(row.get('grade', 1)), 1), 5),  # grade 1-5
                    'Автокредиты',  # service_category (переводим на русский)
                    date_create,  # date_create
                    'Газпромбанк',  # bank_name
                )
                
                records.append(record)
                processed += 1
                
                # Вставляем данные партиями по 1000
                if len(records) >= 1000:
                    insert_query = """
                        INSERT INTO reviews (review_id, text, grade, service_category, date_create, bank_name)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (review_id) DO NOTHING
                    """
                    
                    execute_batch(cursor, insert_query, records, page_size=500)
                    conn.commit()
                    
                    print(f"✅ Загружено {processed:,} записей (пропущено {skipped} коротких)")
                    records = []
                
            except Exception as e:
                print(f"⚠️ Ошибка обработки записи {row.get('id', 'N/A')}: {e}")
                skipped += 1
                continue
        
        # Вставляем оставшиеся записи
        if records:
            insert_query = """
                INSERT INTO reviews (review_id, text, grade, service_category, date_create, bank_name)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (review_id) DO NOTHING
            """
            
            execute_batch(cursor, insert_query, records, page_size=500)
            conn.commit()
            
            print(f"✅ Загружено финальных {len(records)} записей")
        
        # Проверяем результат
        cursor.execute("SELECT COUNT(*) FROM reviews")
        total = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT grade, COUNT(*) 
            FROM reviews 
            GROUP BY grade 
            ORDER BY grade
        """)
        grade_stats = cursor.fetchall()
        
        print(f"\n🎉 Загрузка завершена!")
        print(f"📊 Всего в БД: {total:,} реальных отзывов")
        print(f"📈 Статистика по рейтингам:")
        for grade, count in grade_stats:
            print(f"   ⭐ {grade} звезд: {count:,} отзывов")
        print(f"🚫 Пропущено коротких: {skipped}")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        conn.rollback()
        raise
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    load_xlsx_data()