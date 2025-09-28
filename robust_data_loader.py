
#!/usr/bin/env python3
"""
Надежный загрузчик данных из XLSX и CSV в PostgreSQL
Обрабатывает большие файлы по частям и корректно маппит колонки
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import os
import re
from datetime import datetime
import sys

# Настройки подключения к базе данных
DATABASE_URL = os.getenv('DATABASE_URL')

def clean_text(text):
    """Очистка HTML и некорректных символов"""
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
    """Парсинг даты из различных форматов"""
    if not date_str or pd.isna(date_str):
        return datetime.now()
    
    try:
        return pd.to_datetime(date_str).to_pydatetime()
    except:
        return datetime.now()

def normalize_grade(grade_value):
    """Нормализация оценки к диапазону 1-5"""
    if pd.isna(grade_value):
        return 3
    
    try:
        grade = int(float(grade_value))
        return max(1, min(5, grade))
    except:
        return 3

def map_columns(df):
    """Маппинг колонок к стандартным названиям"""
    # Возможные варианты названий колонок
    column_mapping = {
        # ID колонки
        'id': ['id', 'ID', 'review_id', 'reviewId', 'Код'],
        # Текст отзыва
        'text': ['text', 'Text', 'review_text', 'content', 'Текст', 'Отзыв'],
        # Оценка/рейтинг
        'grade': ['grade', 'Grade', 'rating', 'Rate', 'score', 'Оценка', 'Рейтинг'],
        # Категория услуги
        'service_category': ['service_category', 'category', 'Category', 'product', 'Категория', 'Продукт'],
        # Дата создания
        'date_create': ['date_create', 'dateCreate', 'created_at', 'date', 'Date', 'Дата'],
        # Название банка
        'bank_name': ['bank_name', 'company_name', 'bank', 'Bank', 'Банк']
    }
    
    # Создаем словарь для переименования
    rename_dict = {}
    
    for standard_name, possible_names in column_mapping.items():
        for col in df.columns:
            if col.lower() in [name.lower() for name in possible_names]:
                rename_dict[col] = standard_name
                break
    
    # Переименовываем колонки
    df_renamed = df.rename(columns=rename_dict)
    
    print(f"📋 Найденные колонки: {list(df.columns)}")
    print(f"🔄 Переименованные колонки: {rename_dict}")
    print(f"✅ Итоговые колонки: {list(df_renamed.columns)}")
    
    return df_renamed

def load_xlsx_file(file_path, chunk_size=1000):
    """Загрузка XLSX файла"""
    print(f"📂 Загружаем XLSX файл: {file_path}")
    
    try:
        # Читаем весь файл сразу для XLSX (обычно меньше CSV)
        df = pd.read_excel(file_path)
        print(f"📊 Загружено {len(df)} записей из XLSX")
        
        # Маппим колонки
        df = map_columns(df)
        
        # Обрабатываем по частям
        chunks = [df[i:i+chunk_size] for i in range(0, len(df), chunk_size)]
        return chunks
        
    except Exception as e:
        print(f"❌ Ошибка чтения XLSX: {e}")
        return []

def load_csv_file(file_path, chunk_size=1000):
    """Загрузка CSV файла по частям"""
    print(f"📂 Загружаем CSV файл: {file_path}")
    
    try:
        # Определяем кодировку
        encodings = ['utf-8', 'cp1251', 'latin-1', 'iso-8859-1']
        df_sample = None
        
        for encoding in encodings:
            try:
                df_sample = pd.read_csv(file_path, nrows=5, encoding=encoding)
                print(f"✅ Используем кодировку: {encoding}")
                break
            except:
                continue
        
        if df_sample is None:
            raise Exception("Не удалось определить кодировку файла")
        
        # Маппим колонки по образцу
        df_sample = map_columns(df_sample)
        
        # Читаем файл по частям
        chunks = []
        for chunk in pd.read_csv(file_path, chunksize=chunk_size, encoding=encoding):
            chunk = map_columns(chunk)
            chunks.append(chunk)
            
        print(f"📊 Загружено {len(chunks)} частей из CSV")
        return chunks
        
    except Exception as e:
        print(f"❌ Ошибка чтения CSV: {e}")
        return []

def process_chunk(chunk):
    """Обработка одной части данных"""
    records = []
    
    for _, row in chunk.iterrows():
        try:
            # Извлекаем и очищаем данные
            review_id = str(row.get('id', f'import_{len(records)}'))
            text = clean_text(row.get('text', ''))
            grade = normalize_grade(row.get('grade', 3))
            service_category = str(row.get('service_category', 'Неопределено'))[:100]
            date_create = parse_date(row.get('date_create'))
            bank_name = str(row.get('bank_name', 'Газпромбанк'))[:100]
            
            # Пропускаем очень короткие отзывы
            if len(text) < 10:
                continue
            
            record = (
                review_id,
                text[:4000],  # Ограничиваем длину
                grade,
                service_category,
                date_create,
                bank_name
            )
            
            records.append(record)
            
        except Exception as e:
            print(f"⚠️ Ошибка обработки записи: {e}")
            continue
    
    return records

def insert_data_batch(conn, records):
    """Вставка данных в БД батчами"""
    if not records:
        return 0
    
    try:
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO reviews (review_id, text, grade, service_category, date_create, bank_name)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (review_id) DO NOTHING
        """
        
        execute_batch(cursor, insert_query, records, page_size=500)
        conn.commit()
        cursor.close()
        
        return len(records)
        
    except Exception as e:
        print(f"❌ Ошибка вставки данных: {e}")
        conn.rollback()
        return 0

def main():
    """Основная функция загрузки"""
    print("🚀 Запуск надежного загрузчика данных...")
    
    # Проверяем подключение к БД
    if not DATABASE_URL:
        print("❌ Переменная DATABASE_URL не найдена")
        return
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("✅ Подключение к БД установлено")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return
    
    # Ищем файлы для загрузки
    files_to_load = []
    
    # XLSX файлы
    xlsx_files = [
        'gazprombank_ml_dataset.xlsx',
        'attached_assets/gazprombank_auto_credit_1759018718881.xlsx'
    ]
    
    for file_path in xlsx_files:
        if os.path.exists(file_path):
            files_to_load.append(('xlsx', file_path))
    
    # CSV файлы
    csv_files = [
        'data/csv/gazprombank_reviews.csv',
        './gazprombank_reviews.csv'
    ]
    
    for file_path in csv_files:
        if os.path.exists(file_path):
            files_to_load.append(('csv', file_path))
    
    if not files_to_load:
        print("❌ Файлы для загрузки не найдены")
        print("📝 Разместите файлы в корне проекта или в папке data/csv/")
        return
    
    print(f"📋 Найдено файлов для загрузки: {len(files_to_load)}")
    
    total_inserted = 0
    
    # Обрабатываем каждый файл
    for file_type, file_path in files_to_load:
        print(f"\n📂 Обрабатываем файл: {file_path}")
        
        # Загружаем данные по частям
        if file_type == 'xlsx':
            chunks = load_xlsx_file(file_path)
        else:
            chunks = load_csv_file(file_path)
        
        if not chunks:
            print(f"⚠️ Не удалось загрузить данные из {file_path}")
            continue
        
        # Обрабатываем каждую часть
        file_inserted = 0
        for i, chunk in enumerate(chunks):
            print(f"📊 Обрабатываем часть {i+1}/{len(chunks)}...")
            
            # Обрабатываем данные
            records = process_chunk(chunk)
            
            # Вставляем в БД
            inserted = insert_data_batch(conn, records)
            file_inserted += inserted
            total_inserted += inserted
            
            print(f"✅ Вставлено {inserted} записей из части {i+1}")
        
        print(f"🎉 Из файла {file_path} загружено {file_inserted} записей")
    
    # Финальная статистика
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM reviews")
    total_in_db = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT grade, COUNT(*) 
        FROM reviews 
        GROUP BY grade 
        ORDER BY grade
    """)
    grade_stats = cursor.fetchall()
    
    print(f"\n🎉 Загрузка завершена!")
    print(f"📊 Загружено в этом сеансе: {total_inserted:,} записей")
    print(f"📊 Всего в БД: {total_in_db:,} записей")
    print(f"📈 Статистика по оценкам:")
    for grade, count in grade_stats:
        print(f"   ⭐ {grade} звезд: {count:,} отзывов")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
