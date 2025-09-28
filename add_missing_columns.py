
#!/usr/bin/env python3
"""
Добавление недостающих столбцов в таблицу reviews
Включает поддержку ответов представителей банка и дополнительных полей
"""

import psycopg2
import os

DATABASE_URL = os.getenv('DATABASE_URL')

def add_missing_columns():
    """Добавляет недостающие столбцы в таблицу reviews"""
    
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        print("🔧 Добавляем недостающие столбцы в таблицу reviews...")
        
        # Список новых столбцов для добавления
        new_columns = [
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS is_countable BOOLEAN DEFAULT true",
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS comment_count INTEGER DEFAULT 0", 
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS resolution_is_approved BOOLEAN DEFAULT null",
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS has_documents BOOLEAN DEFAULT false",
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS title TEXT DEFAULT ''",
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS user_name VARCHAR(255) DEFAULT ''",
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS agent_id VARCHAR(100) DEFAULT null",
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS agent_answer_text TEXT DEFAULT null",
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS company_id VARCHAR(100) DEFAULT null",
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS company_code VARCHAR(50) DEFAULT null", 
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS company_url VARCHAR(500) DEFAULT null",
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS bank_processed BOOLEAN DEFAULT false",
            "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS scraped_page VARCHAR(500) DEFAULT null"
        ]
        
        # Выполняем каждую команду добавления столбца
        for sql in new_columns:
            try:
                cur.execute(sql)
                column_name = sql.split('ADD COLUMN IF NOT EXISTS ')[1].split(' ')[0]
                print(f"✅ Добавлен столбец: {column_name}")
            except Exception as e:
                print(f"⚠️ Ошибка добавления столбца: {e}")
        
        # Создаем индексы для новых столбцов
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_reviews_agent_id ON reviews (agent_id)",
            "CREATE INDEX IF NOT EXISTS idx_reviews_company_id ON reviews (company_id)", 
            "CREATE INDEX IF NOT EXISTS idx_reviews_user_name ON reviews (user_name)",
            "CREATE INDEX IF NOT EXISTS idx_reviews_has_agent_answer ON reviews (agent_answer_text) WHERE agent_answer_text IS NOT NULL"
        ]
        
        print("\n🔍 Создаем индексы для новых столбцов...")
        for sql in indexes:
            try:
                cur.execute(sql)
                index_name = sql.split('CREATE INDEX IF NOT EXISTS ')[1].split(' ON')[0]
                print(f"✅ Создан индекс: {index_name}")
            except Exception as e:
                print(f"⚠️ Ошибка создания индекса: {e}")
        
        conn.commit()
        
        # Проверяем структуру таблицы
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'reviews' 
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        
        print(f"\n📋 Структура таблицы reviews ({len(columns)} столбцов):")
        for col_name, data_type, nullable, default in columns:
            nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
            default_str = f" DEFAULT {default}" if default else ""
            print(f"  • {col_name}: {data_type} {nullable_str}{default_str}")
        
        # Проверяем количество записей с ответами банка
        cur.execute("""
            SELECT 
                COUNT(*) as total_reviews,
                COUNT(agent_answer_text) as reviews_with_answers,
                COUNT(CASE WHEN agent_answer_text IS NOT NULL AND LENGTH(TRIM(agent_answer_text)) > 0 THEN 1 END) as reviews_with_non_empty_answers
            FROM reviews
        """)
        
        stats = cur.fetchone()
        print(f"\n📊 Статистика ответов банка:")
        print(f"  • Всего отзывов: {stats[0]:,}")
        print(f"  • С ответами банка: {stats[1]:,}")
        print(f"  • С непустыми ответами: {stats[2]:,}")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    add_missing_columns()
