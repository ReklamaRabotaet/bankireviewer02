
#!/usr/bin/env python3
"""
Загрузка листа Classes из gazprombank_ml_dataset.xlsx в новую таблицу classes
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import os
from datetime import datetime

# Настройки подключения к базе данных
DATABASE_URL = os.getenv('DATABASE_URL')

def create_classes_table(conn):
    """Создание таблицы classes если не существует"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id SERIAL PRIMARY KEY,
                class_name VARCHAR(255) NOT NULL,
                class_code VARCHAR(100),
                description TEXT,
                category VARCHAR(100),
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Создаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_name ON classes (class_name);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_code ON classes (class_code);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_category ON classes (category);")
        
        conn.commit()
        print("✅ Таблица classes создана/проверена")
        
    except Exception as e:
        print(f"❌ Ошибка создания таблицы classes: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()

def load_classes_data():
    """Загрузка данных из листа Classes"""
    print("🚀 Начинаем загрузку данных из листа Classes...")
    
    # Проверяем существование файла
    xlsx_file = 'gazprombank_ml_dataset.xlsx'
    if not os.path.exists(xlsx_file):
        print(f"❌ Файл {xlsx_file} не найден")
        return
    
    try:
        # Читаем лист Classes
        print(f"📂 Читаем лист Classes из файла: {xlsx_file}")
        df = pd.read_excel(xlsx_file, sheet_name='Classes')
        print(f"📊 Загружено {len(df):,} записей из листа Classes")
        
        if len(df) == 0:
            print("⚠️ Лист Classes пустой")
            return
        
        print(f"📋 Колонки в файле: {list(df.columns)}")
        
        # Подключение к БД
        conn = psycopg2.connect(DATABASE_URL)
        
        # Создаем таблицу
        create_classes_table(conn)
        
        cursor = conn.cursor()
        
        # Очищаем таблицу перед загрузкой
        print("🧹 Очищаем таблицу classes...")
        cursor.execute("DELETE FROM classes")
        conn.commit()
        print("✅ Таблица очищена")
        
        # Подготавливаем данные для вставки
        records = []
        processed = 0
        
        for _, row in df.iterrows():
            try:
                # Извлекаем данные из строки (адаптируем под реальную структуру)
                class_name = str(row.get('class_name', row.get('name', row.get('title', f'Class_{processed}'))))
                class_code = str(row.get('class_code', row.get('code', row.get('id', ''))))
                description = str(row.get('description', row.get('desc', '')))
                category = str(row.get('category', row.get('type', 'general')))
                is_active = bool(row.get('is_active', row.get('active', True)))
                
                # Очищаем пустые значения
                if pd.isna(row.get('class_code')) or class_code == 'nan':
                    class_code = None
                if pd.isna(row.get('description')) or description == 'nan':
                    description = None
                if pd.isna(row.get('category')) or category == 'nan':
                    category = 'general'
                
                record = (
                    class_name[:255],  # class_name
                    class_code[:100] if class_code else None,  # class_code
                    description,  # description
                    category[:100],  # category
                    is_active  # is_active
                )
                
                records.append(record)
                processed += 1
                
                # Вставляем данные партиями по 1000
                if len(records) >= 1000:
                    insert_query = """
                        INSERT INTO classes (
                            class_name, class_code, description, category, is_active
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    
                    execute_batch(cursor, insert_query, records, page_size=500)
                    conn.commit()
                    
                    print(f"  ✅ Загружено {processed:,} записей")
                    records = []
                
            except Exception as e:
                print(f"  ⚠️ Ошибка обработки записи {processed}: {e}")
                continue
        
        # Вставляем оставшиеся записи
        if records:
            insert_query = """
                INSERT INTO classes (
                    class_name, class_code, description, category, is_active
                )
                VALUES (%s, %s, %s, %s, %s)
            """
            
            execute_batch(cursor, insert_query, records, page_size=500)
            conn.commit()
            
            print(f"  ✅ Загружено финальных {len(records)} записей")
        
        # Финальная статистика
        cursor.execute("SELECT COUNT(*) FROM classes")
        total_in_db = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT category, COUNT(*) 
            FROM classes 
            GROUP BY category 
            ORDER BY COUNT(*) DESC
        """)
        category_stats = cursor.fetchall()
        
        print(f"\n🎉 Загрузка завершена!")
        print(f"📈 Всего загружено записей: {processed:,}")
        print(f"🗄️ Всего записей в таблице classes: {total_in_db:,}")
        print(f"📊 Распределение по категориям:")
        for category, count in category_stats:
            print(f"  • {category}: {count:,} классов")
        
        cursor.close()
        conn.close()
        
    except FileNotFoundError:
        print(f"❌ Файл {xlsx_file} не найден")
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    load_classes_data()
