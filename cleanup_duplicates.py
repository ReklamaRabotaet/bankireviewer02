
#!/usr/bin/env python3
"""
Удаление дублированных отзывов в категории Автокредиты
"""

import psycopg2
import os

DATABASE_URL = os.getenv('DATABASE_URL')

def cleanup_auto_credit_duplicates():
    """Удаляет дублированные отзывы в категории Автокредиты"""
    
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Проверяем текущее состояние
        cur.execute("""
            SELECT service_category, COUNT(*) 
            FROM reviews 
            GROUP BY service_category 
            ORDER BY COUNT(*) DESC
        """)
        
        print("📊 Текущее состояние категорий:")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]} отзывов")
        
        # Находим дубликаты в категории Автокредиты по review_id
        cur.execute("""
            SELECT review_id, COUNT(*) as cnt
            FROM reviews 
            WHERE service_category = 'auto_credit' OR service_category = 'Автокредиты'
            GROUP BY review_id
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
        """)
        
        duplicates = cur.fetchall()
        print(f"\n🔍 Найдено дубликатов по review_id: {len(duplicates)}")
        
        if duplicates:
            # Удаляем дубликаты, оставляя только одну запись с наименьшим id
            for review_id, count in duplicates:
                cur.execute("""
                    DELETE FROM reviews 
                    WHERE review_id = %s 
                    AND id NOT IN (
                        SELECT MIN(id) 
                        FROM reviews 
                        WHERE review_id = %s
                    )
                """, (review_id, review_id))
                
            print(f"✅ Удалено дубликатов: {sum(count-1 for _, count in duplicates)}")
        
        # Также проверяем и удаляем дубликаты по тексту в категории Автокредиты
        cur.execute("""
            WITH duplicates AS (
                SELECT text, COUNT(*) as cnt, MIN(id) as keep_id
                FROM reviews 
                WHERE (service_category = 'auto_credit' OR service_category = 'Автокредиты')
                AND LENGTH(text) > 50
                GROUP BY text
                HAVING COUNT(*) > 1
            )
            DELETE FROM reviews 
            WHERE id IN (
                SELECT r.id 
                FROM reviews r
                INNER JOIN duplicates d ON r.text = d.text
                WHERE r.id != d.keep_id
                AND (r.service_category = 'auto_credit' OR r.service_category = 'Автокредиты')
            )
        """)
        
        deleted_by_text = cur.rowcount
        print(f"✅ Удалено дубликатов по тексту: {deleted_by_text}")
        
        # Унифицируем названия категорий
        cur.execute("""
            UPDATE reviews 
            SET service_category = 'Автокредиты'
            WHERE service_category = 'auto_credit'
        """)
        
        updated = cur.rowcount
        if updated > 0:
            print(f"✅ Унифицировано названий категорий: {updated}")
        
        conn.commit()
        
        # Проверяем финальное состояние
        cur.execute("""
            SELECT service_category, COUNT(*) 
            FROM reviews 
            GROUP BY service_category 
            ORDER BY COUNT(*) DESC
        """)
        
        print("\n📊 Финальное состояние категорий:")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]} отзывов")
            
        # Специально проверяем Автокредиты
        cur.execute("""
            SELECT COUNT(*) 
            FROM reviews 
            WHERE service_category = 'Автокредиты'
        """)
        
        auto_credit_count = cur.fetchone()[0]
        print(f"\n🎯 Итого отзывов по Автокредитам: {auto_credit_count}")
        
    except Exception as e:
        print(f"❌ Ошибка очистки: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    cleanup_auto_credit_duplicates()
