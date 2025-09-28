
#!/usr/bin/env python3
"""
Загрузка всех XLSX файлов из папки /upload в таблицу reviews
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import os
import re
import glob
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

def get_category_from_filename(filename):
    """Определяет категорию услуги по имени файла"""
    category_mapping = {
        'auto_credit': 'Автокредиты',
        'consumer_credit': 'Потребительские кредиты', 
        'credit_cards': 'Кредитные карты',
        'debet_cards': 'Дебетовые карты',
        'deposits': 'Вклады',
        'hypothec': 'Ипотека',
        'mobile_app': 'Мобильное приложение',
        'money_transfer': 'Денежные переводы',
        'other_individual': 'Другое (физ. лица)',
        'remote_service': 'Дистанционное обслуживание',
        'restructuring': 'Реструктуризация'
    }
    
    filename_lower = filename.lower()
    for key, category in category_mapping.items():
        if key in filename_lower:
            return category
    
    # Если не найдено соответствие, возвращаем имя файла без расширения
    return os.path.splitext(filename)[0].replace('gazprombank_', '').replace('_', ' ').title()

def load_xlsx_file(file_path, service_category):
    """Загрузка данных из одного XLSX файла"""
    print(f"\n📂 Обрабатываем файл: {file_path}")
    print(f"📋 Категория: {service_category}")
    
    try:
        # Читаем XLSX файл
        df = pd.read_excel(file_path)
        print(f"📊 Загружено {len(df):,} записей из файла")
        
        if len(df) == 0:
            print("⚠️ Файл пустой, пропускаем")
            return 0
        
        # Подключение к БД
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
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
                
                # Извлекаем дополнительные поля с безопасными значениями по умолчанию
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
                    str(row.get('id', f'upload_{processed}_{hash(text)}')),  # review_id (уникальный)
                    text[:4000],  # text (ограничиваем длину)
                    grade,  # grade 1-5
                    service_category,  # service_category
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
                
                # Вставляем данные партиями по 500
                if len(records) >= 500:
                    insert_query = """
                        INSERT INTO reviews (
                            review_id, text, grade, service_category, date_create, bank_name,
                            is_countable, comment_count, resolution_is_approved, has_documents,
                            title, user_name, agent_id, agent_answer_text, company_id, 
                            company_code, company_url, bank_processed, scraped_page
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (review_id) DO NOTHING
                    """
                    
                    execute_batch(cursor, insert_query, records, page_size=250)
                    conn.commit()
                    
                    print(f"  ✅ Загружено {processed:,} записей (пропущено {skipped} коротких)")
                    records = []
                
            except Exception as e:
                print(f"  ⚠️ Ошибка обработки записи {row.get('id', 'N/A')}: {e}")
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
                ON CONFLICT (review_id) DO NOTHING
            """
            
            execute_batch(cursor, insert_query, records, page_size=250)
            conn.commit()
            
            print(f"  ✅ Загружено финальных {len(records)} записей")
        
        print(f"  📊 Итого обработано: {processed:,} записей, пропущено: {skipped}")
        
        cursor.close()
        conn.close()
        
        return processed
        
    except Exception as e:
        print(f"  ❌ Ошибка загрузки файла {file_path}: {e}")
        return 0

def load_all_upload_files():
    """Загрузка всех XLSX файлов из папки upload"""
    print("🚀 Начинаем загрузку всех XLSX файлов из папки /upload...")
    
    # Проверяем существование папки
    upload_dir = './upload'
    if not os.path.exists(upload_dir):
        print(f"❌ Папка {upload_dir} не найдена")
        return
    
    # Находим все XLSX файлы
    xlsx_files = glob.glob(os.path.join(upload_dir, '*.xlsx'))
    
    if not xlsx_files:
        print("❌ XLSX файлы в папке upload не найдены")
        return
    
    print(f"📋 Найдено {len(xlsx_files)} XLSX файлов:")
    for file_path in xlsx_files:
        filename = os.path.basename(file_path)
        category = get_category_from_filename(filename)
        print(f"  • {filename} → {category}")
    
    total_processed = 0
    successful_files = 0
    
    # Обрабатываем каждый файл
    for file_path in xlsx_files:
        filename = os.path.basename(file_path)
        service_category = get_category_from_filename(filename)
        
        processed = load_xlsx_file(file_path, service_category)
        if processed > 0:
            successful_files += 1
            total_processed += processed
    
    # Финальная статистика
    print(f"\n🎉 Загрузка завершена!")
    print(f"📊 Обработано файлов: {successful_files}/{len(xlsx_files)}")
    print(f"📈 Всего загружено записей: {total_processed:,}")
    
    # Проверяем общее количество записей в БД
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM reviews")
        total_in_db = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT service_category, COUNT(*) 
            FROM reviews 
            GROUP BY service_category 
            ORDER BY COUNT(*) DESC
        """)
        category_stats = cursor.fetchall()
        
        print(f"🗄️ Всего записей в БД: {total_in_db:,}")
        print(f"📊 Распределение по категориям:")
        for category, count in category_stats:
            print(f"  • {category}: {count:,} отзывов")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"⚠️ Не удалось получить финальную статистику: {e}")

if __name__ == "__main__":
    load_all_upload_files()
