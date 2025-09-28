#!/usr/bin/env python3
"""
Скрипт миграции реальных данных из CSV в PostgreSQL
Загружает данные из gazprombank_reviews.csv (378MB) в базу данных
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import os
import re
from datetime import datetime
from html import unescape
import html2text

# Настройки подключения к базе данных
DATABASE_URL = os.getenv('DATABASE_URL')

def clean_html_text(html_content):
    """Очищает HTML теги и конвертирует в чистый текст"""
    if not html_content or pd.isna(html_content):
        return ""
    
    # Конвертируем HTML в текст
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    clean_text = h.handle(str(html_content))
    
    # Убираем лишние переносы и пробелы
    clean_text = re.sub(r'\n+', ' ', clean_text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return clean_text

def parse_date(date_str):
    """Парсит дату из строки CSV"""
    if not date_str or pd.isna(date_str):
        return None
    
    try:
        # Пробуем стандартный формат
        return pd.to_datetime(date_str).to_pydatetime()
    except:
        return datetime.now()

def migrate_csv_to_db():
    """Основная функция миграции"""
    print("🚀 Начинаем миграцию данных из CSV в PostgreSQL...")
    
    # Подключение к БД
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Читаем CSV файл по частям (chunks)
        csv_file = './data/csv/gazprombank_reviews.csv'
        chunk_size = 1000  # Обрабатываем по 1000 записей
        
        print(f"📂 Читаем файл: {csv_file}")
        
        total_inserted = 0
        chunk_number = 0
        
        # Читаем CSV по частям
        for chunk in pd.read_csv(csv_file, chunksize=chunk_size):
            chunk_number += 1
            print(f"📊 Обрабатываем chunk #{chunk_number} ({len(chunk)} записей)...")
            
            # Подготавливаем данные для вставки
            records = []
            
            for _, row in chunk.iterrows():
                try:
                    # Очищаем HTML текст
                    clean_text = clean_html_text(row.get('text', ''))
                    
                    # Пропускаем пустые отзывы
                    if not clean_text.strip():
                        continue
                    
                    # Подготавливаем запись
                    record = (
                        str(row.get('id', '')),  # review_id
                        clean_text[:5000],  # text (ограничиваем длину)
                        int(row.get('grade', 3)) if pd.notna(row.get('grade')) else 3,  # grade
                        row.get('service_category', 'Неопределено'),  # service_category
                        parse_date(row.get('dateCreate')),  # date_create
                        row.get('company_name', 'Газпромбанк'),  # bank_name
                    )
                    
                    records.append(record)
                    
                except Exception as e:
                    print(f"⚠️ Ошибка обработки записи: {e}")
                    continue
            
            # Вставляем данные в БД партиями
            if records:
                insert_query = """
                    INSERT INTO reviews (review_id, text, grade, service_category, date_create, bank_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                
                execute_batch(cursor, insert_query, records, page_size=500)
                conn.commit()
                
                total_inserted += len(records)
                print(f"✅ Вставлено {len(records)} записей. Всего: {total_inserted}")
        
        print(f"🎉 Миграция завершена! Всего загружено: {total_inserted} отзывов")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
        raise
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    migrate_csv_to_db()