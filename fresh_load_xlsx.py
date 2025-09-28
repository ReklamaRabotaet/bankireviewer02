
#!/usr/bin/env python3
"""
Полная очистка таблицы reviews и загрузка данных из XLSX файла
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import os
import re
from datetime import datetime

# Настройки подключения к базе данных
DATABASE_URL = os.getenv('DATABASE_URL')

def clean_html_text(text):
    """Очистка HTML тегов и форматирование текста"""
    if not text or pd.isna(text):
        return ""
    
    text = str(text)
    # Убираем HTML теги
    text = re.sub(r'<[^>]+>', '', text)
    # Убираем HTML entities
    text = re.sub(r'&[#\w]+;', ' ', text)
    # Убираем лишние пробелы и переносы
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def parse_date(date_str):
    """Парсинг даты"""
    if not date_str or pd.isna(date_str):
        return datetime.now()
    
    try:
        return pd.to_datetime(date_str).to_pydatetime()
    except:
        return datetime.now()

def clear_and_load_data():
    """Очистка таблицы и загрузка новых данных"""
    print("🚀 Начинаем очистку и загрузку данных...")
    
    # Подключение к БД
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # 1. Очистка таблицы
        print("🧹 Очищаем таблицу reviews...")
        cursor.execute("DELETE FROM reviews")
        conn.commit()
        print("✅ Таблица очищена")
        
        # 2. Сброс последовательности ID
        cursor.execute("ALTER SEQUENCE reviews_id_seq RESTART WITH 1")
        conn.commit()
        print("✅ Последовательность ID сброшена")
        
        # 3. Загрузка данных из XLSX
        xlsx_file = 'attached_assets/gazprombank_auto_credit_1759018718881.xlsx'
        
        print(f"📂 Читаем XLSX файл: {xlsx_file}")
        df = pd.read_excel(xlsx_file)
        print(f"📊 Загружено {len(df):,} записей из XLSX")
        
        # 4. Обработка и подготовка данных
        records = []
        processed = 0
        skipped = 0
        
        for _, row in df.iterrows():
            try:
                # Очищаем текст отзыва
                text = clean_html_text(row.get('text', ''))
                
                # Пропускаем очень короткие отзывы
                if not text.strip() or len(text) < 20:
                    skipped += 1
                    continue
                
                # Парсим дату
                try:
                    date_create = pd.to_datetime(row.get('dateCreate')).to_pydatetime()
                except:
                    date_create = datetime.now()
                
                # Нормализуем оценку
                grade = row.get('grade', 1)
                try:
                    grade = max(1, min(5, int(grade)))
                except:
                    grade = 1
                
                # Извлекаем дополнительные поля
                is_countable = bool(row.get('isCountable', True))
                comment_count = int(row.get('commentCount', 0)) if pd.notna(row.get('commentCount')) else 0
                resolution_is_approved = bool(row.get('resolutionIsApproved')) if pd.notna(row.get('resolutionIsApproved')) else None
                has_documents = bool(row.get('hasDocuments', False))
                title = clean_html_text(row.get('title', ''))[:500]
                user_name = str(row.get('userName', ''))[:255]
                agent_id = str(row.get('agentId', '')) if pd.notna(row.get('agentId')) else None
                agent_answer_text = clean_html_text(row.get('agentAnswerText', '')) if pd.notna(row.get('agentAnswerText')) else None
                company_id = str(row.get('company_id', '')) if pd.notna(row.get('company_id')) else None
                company_code = str(row.get('company_code', '')) if pd.notna(row.get('company_code')) else None
                company_name = str(row.get('company_name', 'Газпромбанк'))[:100]
                company_url = str(row.get('company_url', '')) if pd.notna(row.get('company_url')) else None
                bank_processed = bool(row.get('bank_processed', False))
                scraped_page = str(row.get('scraped_page', '')) if pd.notna(row.get('scraped_page')) else None
                
                # Формируем запись
                record = (
                    str(row.get('id', f'auto_{processed}')),  # review_id
                    text[:4000],  # text (ограничиваем длину)
                    grade,  # grade 1-5
                    'Автокредиты',  # service_category
                    date_create,  # date_create
                    company_name,  # bank_name
                    is_countable,  # is_countable
                    comment_count,  # comment_count
                    resolution_is_approved,  # resolution_is_approved
                    has_documents,  # has_documents
                    title,  # title
                    user_name,  # user_name
                    agent_id,  # agent_id
                    agent_answer_text,  # agent_answer_text
                    company_id,  # company_id
                    company_code,  # company_code
                    company_url,  # company_url
                    bank_processed,  # bank_processed
                    scraped_page  # scraped_page
                )
                
                records.append(record)
                processed += 1
                
                # Вставляем данные партиями по 1000
                if len(records) >= 1000:
                    insert_query = """
                        INSERT INTO reviews (
                            review_id, text, grade, service_category, date_create, bank_name,
                            is_countable, comment_count, resolution_is_approved, has_documents,
                            title, user_name, agent_id, agent_answer_text, company_id, 
                            company_code, company_url, bank_processed, scraped_page
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                INSERT INTO reviews (
                    review_id, text, grade, service_category, date_create, bank_name,
                    is_countable, comment_count, resolution_is_approved, has_documents,
                    title, user_name, agent_id, agent_answer_text, company_id, 
                    company_code, company_url, bank_processed, scraped_page
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            execute_batch(cursor, insert_query, records, page_size=500)
            conn.commit()
            
            print(f"✅ Загружено финальных {len(records)} записей")
        
        # 5. Финальная статистика
        cursor.execute("SELECT COUNT(*) FROM reviews")
        total = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT grade, COUNT(*) 
            FROM reviews 
            GROUP BY grade 
            ORDER BY grade
        """)
        grade_stats = cursor.fetchall()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_reviews,
                COUNT(CASE WHEN agent_answer_text IS NOT NULL AND agent_answer_text != '' THEN 1 END) as with_agent_answers,
                COUNT(CASE WHEN agent_id IS NOT NULL AND agent_id != '' THEN 1 END) as with_agent_id
            FROM reviews
        """)
        answer_stats = cursor.fetchone()
        
        print(f"\n🎉 Загрузка завершена!")
        print(f"📊 Всего в БД: {total:,} реальных отзывов")
        print(f"📈 Статистика по рейтингам:")
        for grade, count in grade_stats:
            print(f"   ⭐ {grade} звезд: {count:,} отзывов")
        print(f"🚫 Пропущено коротких: {skipped}")
        print(f"📞 С ответами банка: {answer_stats[1]:,} отзывов")
        print(f"👤 С агентами: {answer_stats[2]:,} отзывов")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        conn.rollback()
        raise
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    clear_and_load_data()
