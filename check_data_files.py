
#!/usr/bin/env python3
"""
Скрипт для анализа структуры файлов данных
Помогает понять, какие колонки есть в файлах
"""

import pandas as pd
import os

def analyze_file(file_path, file_type='auto'):
    """Анализ структуры файла"""
    print(f"\n📂 Анализируем файл: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        return
    
    try:
        # Определяем тип файла
        if file_type == 'auto':
            if file_path.endswith('.xlsx'):
                file_type = 'xlsx'
            elif file_path.endswith('.csv'):
                file_type = 'csv'
            else:
                print("❌ Неизвестный тип файла")
                return
        
        # Читаем первые несколько строк
        if file_type == 'xlsx':
            df = pd.read_excel(file_path, nrows=5)
        else:
            # Пробуем разные кодировки для CSV
            encodings = ['utf-8', 'cp1251', 'latin-1']
            df = None
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, nrows=5, encoding=encoding)
                    print(f"✅ Кодировка: {encoding}")
                    break
                except:
                    continue
            
            if df is None:
                print("❌ Не удалось прочитать файл с доступными кодировками")
                return
        
        print(f"📊 Размер файла: {os.path.getsize(file_path) / 1024 / 1024:.1f} MB")
        print(f"📋 Колонки ({len(df.columns)}):")
        
        for i, col in enumerate(df.columns):
            sample_value = str(df[col].iloc[0]) if len(df) > 0 else "N/A"
            print(f"   {i+1}. {col} (пример: {sample_value[:50]}...)")
        
        print(f"📈 Примерное количество строк в образце: {len(df)}")
        
        # Пытаемся оценить полный размер
        if file_type == 'csv':
            try:
                full_df = pd.read_csv(file_path, encoding=encoding)
                print(f"📊 Общее количество строк: {len(full_df):,}")
            except:
                print("📊 Не удалось подсчитать общее количество строк")
        
    except Exception as e:
        print(f"❌ Ошибка анализа файла: {e}")

def main():
    """Анализ всех найденных файлов данных"""
    print("🔍 Поиск и анализ файлов данных...")
    
    # Список возможных файлов
    files_to_check = [
        'gazprombank_ml_dataset.xlsx',
        'attached_assets/gazprombank_auto_credit_1759018718881.xlsx',
        'data/csv/gazprombank_reviews.csv',
        './gazprombank_reviews.csv'
    ]
    
    found_files = []
    for file_path in files_to_check:
        if os.path.exists(file_path):
            found_files.append(file_path)
    
    if not found_files:
        print("❌ Файлы данных не найдены")
        print("📝 Разместите файлы в следующих местах:")
        for file_path in files_to_check:
            print(f"   - {file_path}")
        return
    
    print(f"✅ Найдено {len(found_files)} файлов")
    
    # Анализируем каждый найденный файл
    for file_path in found_files:
        analyze_file(file_path)
    
    print("\n📝 Рекомендации:")
    print("1. Убедитесь, что в файлах есть колонки:")
    print("   - ID отзыва (id, review_id)")
    print("   - Текст отзыва (text, content)")
    print("   - Оценка (grade, rating, score)")
    print("   - Категория (service_category, category)")
    print("   - Дата (date_create, created_at)")
    print("2. Запустите robust_data_loader.py для загрузки данных")

if __name__ == "__main__":
    main()
