
#!/usr/bin/env python3
"""
Загрузка данных из листа Classes файла gazprombank_ml_dataset.xlsx в таблицу classes
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import os
import re
from datetime import datetime

# Настройки подключения к базе данных
DATABASE_URL = os.getenv('DATABASE_URL')

def load_classes_data():
    """Загрузка данных из листа Classes в таблицу classes"""
    print("🚀 Начинаем загрузку данных из листа Classes...")
    
    # Подключение к БД
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # 1. Создание таблицы classes если не существует
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id SERIAL PRIMARY KEY,
                class_name VARCHAR(100) NOT NULL,
                class_label_ru VARCHAR(200) NOT NULL,
                description TEXT,
                total_reviews INTEGER DEFAULT 0,
                selected_examples TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("✅ Таблица classes создана/проверена")
        
        # 2. Очистка таблицы
        print("🧹 Очищаем таблицу classes...")
        cursor.execute("DELETE FROM classes")
        conn.commit()
        print("✅ Таблица очищена")
        
        # 3. Загрузка данных из XLSX листа Classes
        xlsx_file = 'gazprombank_ml_dataset.xlsx'
        
        print(f"📂 Читаем лист Classes из файла: {xlsx_file}")
        df = pd.read_excel(xlsx_file, sheet_name='Classes')
        print(f"📊 Загружено {len(df)} записей из листа Classes")
        print(f"📋 Колонки в файле: {list(df.columns)}")
        
        # 4. Обработка и подготовка данных
        records = []
        
        for _, row in df.iterrows():
            try:
                # Извлекаем данные из каждой колонки
                class_name = str(row.get('class_name', '')).strip()
                class_label_ru = str(row.get('class_label_ru', '')).strip()
                description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else None
                total_reviews = int(row.get('total_reviews', 0)) if pd.notna(row.get('total_reviews')) else 0
                selected_examples = str(row.get('selected_examples', '')).strip() if pd.notna(row.get('selected_examples')) else None
                
                # Пропускаем пустые записи
                if not class_name or not class_label_ru:
                    continue
                
                record = (
                    class_name,
                    class_label_ru,
                    description,
                    total_reviews,
                    selected_examples
                )
                
                records.append(record)
                
            except Exception as e:
                print(f"⚠️ Ошибка обработки записи: {e}")
                continue
        
        # 5. Вставка данных в БД
        if records:
            insert_query = """
                INSERT INTO classes (class_name, class_label_ru, description, total_reviews, selected_examples)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            execute_batch(cursor, insert_query, records, page_size=100)
            conn.commit()
            
            print(f"  ✅ Загружено финальных {len(records)} записей")
        
        # 6. Финальная статистика
        cursor.execute("SELECT COUNT(*) FROM classes")
        total = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT class_name, class_label_ru, total_reviews 
            FROM classes 
            ORDER BY total_reviews DESC
        """)
        class_stats = cursor.fetchall()
        
        print(f"\n🎉 Загрузка завершена!")
        print(f"📈 Всего загружено записей: {len(records)}")
        print(f"🗄️ Всего записей в таблице classes: {total}")
        print(f"📊 Распределение по категориям:")
        
        category_count = {}
        for class_name, class_label_ru, total_reviews in class_stats:
            # Группируем по общим категориям
            if any(keyword in class_name.lower() for keyword in ['general', 'общ']):
                category = 'general'
            elif any(keyword in class_name.lower() for keyword in ['product', 'продукт']):
                category = 'product'
            elif any(keyword in class_name.lower() for keyword in ['service', 'сервис']):
                category = 'service'
            else:
                category = 'other'
            
            category_count[category] = category_count.get(category, 0) + 1
        
        for category, count in category_count.items():
            print(f"  • {category}: {count} классов")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        conn.rollback()
        raise
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    load_classes_data()
