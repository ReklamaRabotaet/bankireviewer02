#!/usr/bin/env python3
"""
Dashboard for Bank Reviews Analysis
Веб-дашборд для анализа отзывов банков с ML API интеграцией
"""

from flask import Flask, render_template, request, jsonify
import pandas as pd
import json
import os
import random
from datetime import datetime, timedelta
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import psycopg2.pool

# Create Flask app with proper configuration
app = Flask(__name__)

# Configure Flask for production
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'fallback-secret-key-for-development')
app.config['JSON_AS_ASCII'] = False  # Support for Russian characters
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Create connection pool
connection_pool = psycopg2.pool.SimpleConnectionPool(1, 20, DATABASE_URL)

def get_db_connection():
    """Get database connection from pool"""
    return connection_pool.getconn()

def return_db_connection(conn):
    """Return connection back to pool"""
    connection_pool.putconn(conn)

def ensure_database_schema():
    """Проверяет и создает необходимые таблицы в БД"""
    
    conn = None
    try:
        conn = get_db_connection()
        
        with conn.cursor() as cur:
            # Создаем таблицу reviews если не существует
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id SERIAL PRIMARY KEY,
                    review_id VARCHAR(100) UNIQUE NOT NULL,
                    text TEXT NOT NULL,
                    grade INTEGER NOT NULL CHECK (grade >= 1 AND grade <= 5),
                    service_category VARCHAR(50) NOT NULL,
                    date_create TIMESTAMP NOT NULL,
                    bank_name VARCHAR(100) DEFAULT 'Газпромбанк',
                    
                    -- Дополнительные поля отзыва
                    is_countable BOOLEAN DEFAULT true,
                    comment_count INTEGER DEFAULT 0,
                    resolution_is_approved BOOLEAN DEFAULT null,
                    has_documents BOOLEAN DEFAULT false,
                    title TEXT DEFAULT '',
                    user_name VARCHAR(255) DEFAULT '',
                    
                    -- Поля ответа представителя банка
                    agent_id VARCHAR(100) DEFAULT null,
                    agent_answer_text TEXT DEFAULT null,
                    
                    -- Информация о компании
                    company_id VARCHAR(100) DEFAULT null,
                    company_code VARCHAR(50) DEFAULT null,
                    company_url VARCHAR(500) DEFAULT null,
                    bank_processed BOOLEAN DEFAULT false,
                    scraped_page VARCHAR(500) DEFAULT null,
                    
                    -- ML анализ
                    ml_topics TEXT[], -- Массив тем из ML
                    ml_sentiments TEXT[], -- Массив тональностей из ML  
                    
                    -- Служебные поля
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Создаем индексы если не существуют
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews (date_create);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_category ON reviews (service_category);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_grade ON reviews (grade);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_date_category ON reviews (date_create, service_category);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_agent_id ON reviews (agent_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_company_id ON reviews (company_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_user_name ON reviews (user_name);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reviews_has_agent_answer ON reviews (agent_answer_text) WHERE agent_answer_text IS NOT NULL;")
            
            # Создаем таблицу uploaded_datasets если не существует
            cur.execute("""
                CREATE TABLE IF NOT EXISTS uploaded_datasets (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    total_reviews INTEGER NOT NULL,
                    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processing_status VARCHAR(20) DEFAULT 'pending',
                    ml_processing_time INTERVAL,
                    topics_found TEXT[],
                    avg_sentiment_score DECIMAL(3,2)
                );
            """)
            
            conn.commit()
            print("✅ Схема базы данных проверена/создана")
            
    except Exception as e:
        print(f"❌ Ошибка создания схемы БД: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_db_connection(conn)

def get_product_classes():
    """Получение списка классов продуктов из таблицы classes"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT class_name, class_label_ru, description, total_reviews 
                FROM classes 
                ORDER BY total_reviews DESC
            """)
            classes = cur.fetchall()
            return {row['class_name']: row['class_label_ru'] for row in classes}
    except Exception as e:
        print(f"❌ Ошибка получения классов продуктов: {e}")
        # Fallback к старому словарю
        return {
            'debet_cards': 'Дебетовые карты',
            'credit_cards': 'Кредитные карты', 
            'hypothec': 'Ипотека',
            'auto_credit': 'Автокредиты',
            'consumer_credit': 'Потребительские кредиты',
            'restructuring': 'Реструктуризация',
            'deposits': 'Вклады',
            'money_transfer': 'Денежные переводы',
            'remote_service': 'Дистанционное обслуживание',
            'other_individual': 'Другое (физ. лица)',
            'mobile_app': 'Мобильное приложение',
            'individual_service': 'Обслуживание физ. лиц',
            'service_individual': 'Обслуживание физических лиц'
        }
    finally:
        if conn:
            return_db_connection(conn)

def translate_category_name(category_name):
    """Перевод названия категории с английского на русский используя таблицу classes"""
    product_classes = get_product_classes()
    return product_classes.get(category_name, category_name)

# Mock ML API responses - заглушки для тестирования фронтенда
def mock_ml_analysis_v2(reviews):
    """Новая заглушка ML API для формата согласно ML_API_CONTRACT.md
    
    Принимает: [{"id": "123", "text": "..."}]
    Возвращает: [{"id": "123", "topics": [...], "sentiments": [...]}]
    """
    
    # Справочники из ML_API_CONTRACT.md
    topics_mapping = {
        'credit_cards': ['кредит', 'карт', 'кредитн'],
        'debit_cards': ['дебет', 'карт', 'платеж'],
        'mortgage': ['ипотек', 'жилье', 'недвижим'],
        'auto_credit': ['авто', 'машин', 'транспорт'],
        'deposits': ['депозит', 'вклад', 'процент'],
        'support': ['поддержк', 'помощ', 'консульт'],
        'mobile_app': ['приложен', 'мобильн', 'телефон'],
        'transfers': ['перевод', 'отправ'],
        'cash_withdrawal': ['наличн', 'банкомат', 'снят'],
        'online_banking': ['интернет', 'онлайн', 'сайт'],
        'other': ['прочее', 'другое']
    }
    
    results = []
    
    for review in reviews:
        review_id = review.get('id', 'unknown')
        text = review.get('text', '').lower()
        
        # Простой анализ тем на основе ключевых слов
        detected_topics = []
        for topic, keywords in topics_mapping.items():
            if any(keyword in text for keyword in keywords):
                detected_topics.append(topic)
        
        # Если ничего не найдено, используем fallback
        if not detected_topics:
            detected_topics = ['other']
        
        # Простой анализ тональности на основе слов
        positive_words = ['отлично', 'хорошо', 'удобно', 'быстро', 'рекомендую', 'довольн']
        negative_words = ['плохо', 'медленно', 'ужасно', 'проблем', 'долго', 'не работает']
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            sentiment = 'positive'
        elif negative_count > positive_count:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        # Создаем массивы тональности соответствующие темам (правило выравнивания)
        sentiments = [sentiment] * len(detected_topics)
        
        results.append({
            'id': review_id,
            'topics': detected_topics,
            'sentiments': sentiments
        })
    
    return {
        'results': results,
        'errors': []  # Пока ошибок нет, массив пустой
    }

def mock_ml_analysis(texts):
    """Заглушка ML API для тестирования фронтенда"""
    categories = [
        'debet_cards', 'credit_cards', 'hypothec', 'auto_credit', 
        'consumer_credit', 'restructuring', 'deposits', 'money_transfer',
        'remote_service', 'other_individual', 'mobile_app'
    ]
    
    results = {
        'sentiment': [],
        'categories': [],
        'confidence': []
    }
    
    for text in texts:
        # Mock sentiment: -1 to 1 (negative to positive)
        sentiment = random.uniform(-1, 1)
        results['sentiment'].append(round(sentiment, 2))
        
        # Mock category prediction
        category = random.choice(categories)
        results['categories'].append(category)
        
        # Mock confidence: 0 to 1
        confidence = random.uniform(0.6, 0.95)
        results['confidence'].append(round(confidence, 2))
    
    return results

# Загрузка данных для дашборда
def load_dashboard_data_from_db():
    """Загрузка данных для отображения в дашборде из PostgreSQL"""
    
    # Сначала убеждаемся что схема существует
    ensure_database_schema()
    
    conn = None
    try:
        conn = get_db_connection()
        
        # Проверяем есть ли данные в БД
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as count FROM reviews")
            count = cur.fetchone()['count']
            
            # Временно отключена автогенерация mock данных для миграции реальных данных
            if False:  # count == 0:
                print("📊 База пустая, ожидаем загрузки реальных данных...")
                # populate_sample_data()  # ОТКЛЮЧЕНО
                # Повторно считываем после создания данных
                cur.execute("SELECT COUNT(*) as count FROM reviews") 
                count = cur.fetchone()['count']
                print(f"✅ Создано {count} образцов отзывов")
            
            # Загружаем данные из БД
            cur.execute("""
                SELECT 
                    review_id as id,
                    text,
                    grade,
                    service_category,
                    date_create as "dateCreate",
                    bank_name,
                    ml_topics,
                    ml_sentiments
                FROM reviews 
                ORDER BY date_create DESC
            """)
            
            rows = cur.fetchall()
            
            # Конвертируем в DataFrame
            df = pd.DataFrame(rows)
            if len(df) > 0:
                df['dateCreate'] = pd.to_datetime(df['dateCreate'])
                
            return df
            
    except Exception as e:
        print(f"❌ Ошибка загрузки данных из БД: {e}")
        # В случае ошибки создаем минимальный набор данных
        return create_minimal_fallback_data()
    finally:
        if conn:
            return_db_connection(conn)

def populate_sample_data():
    """Заполнение БД образцом данных для демонстрации"""
    
    conn = None
    try:
        conn = get_db_connection()
        
        # Все категории из CATEGORY_TRANSLATIONS 
        categories = [
            'debet_cards', 'credit_cards', 'hypothec', 'auto_credit', 
            'consumer_credit', 'restructuring', 'deposits', 'money_transfer',
            'remote_service', 'other_individual', 'mobile_app', 'individual_service',
            'service_individual'
        ]
        
        # Генерируем данные для каждой категории
        reviews_per_category = 1000  
        
        # Период с 1 января 2024 до 31 мая 2025
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2025, 5, 31)
        total_days = (end_date - start_date).days
        
        with conn.cursor() as cur:
            review_counter = 0
            for category in categories:
                for i in range(reviews_per_category):
                    review_date = start_date + timedelta(days=random.randint(0, total_days))
                    review_counter += 1
                    
                    cur.execute("""
                        INSERT INTO reviews 
                        (review_id, text, grade, service_category, date_create, bank_name)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        f'sample_{review_counter}',
                        f'Образец отзыва #{review_counter} о {CATEGORY_TRANSLATIONS.get(category, category)}',
                        random.randint(1, 5),
                        category,
                        review_date,
                        'Газпромбанк'
                    ))
            
            conn.commit()
            print(f"✅ Создано {review_counter} образцов отзывов в БД")
            
    except Exception as e:
        print(f"❌ Ошибка создания образцов данных: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_db_connection(conn)

def create_minimal_fallback_data():
    """Создание минимального набора данных в случае проблем с БД"""
    data = []
    for i in range(100):
        data.append({
            'id': f'fallback_{i}',
            'dateCreate': datetime.now() - timedelta(days=random.randint(0, 365)),
            'grade': random.randint(1, 5),
            'service_category': 'credit_cards',
            'text': f'Резервный отзыв #{i}',
            'bank_name': 'Газпромбанк'
        })
    
    return pd.DataFrame(data)

# Расчет статистики для дашборда
def calculate_dashboard_stats(df, product_filter=None, period_filter=None):
    """Расчет статистики для дашборда с поддержкой фильтрации"""
    
    # Применяем фильтры
    filtered_df = df.copy()
    
    # Фильтр по продукту
    if product_filter and product_filter != 'all':
        product_classes = get_product_classes()
        # Ищем ключ продукта по названию или самому ключу
        product_key = product_filter
        for key, name in product_classes.items():
            if name == product_filter or key == product_filter:
                product_key = key
                break
        filtered_df = filtered_df[filtered_df['service_category'] == product_key]
    
    # Фильтр по периоду
    if period_filter:
        filtered_df['date'] = pd.to_datetime(filtered_df['dateCreate'])
        current_date = datetime.now()
        
        if period_filter.startswith('2024-') or period_filter.startswith('2025-'):
            # Фильтр по месяцу (YYYY-MM)
            if len(period_filter) == 7:
                year, month = period_filter.split('-')
                filtered_df = filtered_df[
                    (filtered_df['date'].dt.year == int(year)) & 
                    (filtered_df['date'].dt.month == int(month))
                ]
            # Фильтр по году (YYYY)
            elif len(period_filter) == 4:
                filtered_df = filtered_df[filtered_df['date'].dt.year == int(period_filter)]
        elif 'Q' in period_filter:
            # Фильтр по кварталу (YYYY-QX)
            year, quarter = period_filter.split('-Q')
            quarter_months = {
                '1': [1, 2, 3],
                '2': [4, 5, 6], 
                '3': [7, 8, 9],
                '4': [10, 11, 12]
            }
            if quarter in quarter_months:
                filtered_df = filtered_df[
                    (filtered_df['date'].dt.year == int(year)) & 
                    (filtered_df['date'].dt.month.isin(quarter_months[quarter]))
                ]
    
    # Общая статистика
    total_reviews = len(filtered_df)
    
    # Проверка пустого DataFrame или отсутствия колонок
    if total_reviews == 0 or filtered_df.empty:
        return {
            'total_reviews': 0,
            'avg_rating': 0.0,
            'positive_percent': 0.0,
            'neutral_percent': 0.0,
            'negative_percent': 0.0,
            'positive_change': 0.0,
            'neutral_change': 0.0,
            'negative_change': 0.0,
            'total_change': 0.0,
            'category_stats': [],
            'monthly_stats': []
        }
    
    # Проверяем наличие нужных колонок
    required_columns = ['grade', 'service_category', 'dateCreate']
    missing_columns = [col for col in required_columns if col not in filtered_df.columns]
    
    if missing_columns:
        print(f"⚠️ Отсутствуют колонки: {missing_columns}")
        print(f"📋 Доступные колонки: {list(filtered_df.columns)}")
        return {
            'total_reviews': total_reviews,
            'avg_rating': 0.0,
            'positive_percent': 0.0,
            'neutral_percent': 0.0,
            'negative_percent': 0.0,
            'positive_change': 0.0,
            'neutral_change': 0.0, 
            'negative_change': 0.0,
            'total_change': 0.0,
            'category_stats': [],
            'monthly_stats': []
        }
    
    # Распределение по тональности (на основе рейтинга)
    positive = len(filtered_df[filtered_df['grade'] >= 4]) / total_reviews * 100 if total_reviews > 0 else 0
    neutral = len(filtered_df[filtered_df['grade'] == 3]) / total_reviews * 100 if total_reviews > 0 else 0
    negative = len(filtered_df[filtered_df['grade'] <= 2]) / total_reviews * 100 if total_reviews > 0 else 0
    
    # Расчет изменений к предыдущему периоду
    filtered_df['date'] = pd.to_datetime(filtered_df['dateCreate'])
    current_date = datetime.now()
    
    # Определяем период для сравнения (30 дней назад)
    previous_period_start = current_date - timedelta(days=60)
    previous_period_end = current_date - timedelta(days=30)
    current_period_start = current_date - timedelta(days=30)
    
    # Данные за предыдущий период
    prev_df = filtered_df[
        (filtered_df['date'] >= previous_period_start) & 
        (filtered_df['date'] < previous_period_end)
    ]
    
    # Данные за текущий период  
    curr_df = filtered_df[
        (filtered_df['date'] >= current_period_start)
    ]
    
    # Расчет изменений
    def calculate_change(current_count, previous_count):
        if previous_count == 0:
            return 0.0 if current_count == 0 else 100.0
        return ((current_count - previous_count) / previous_count) * 100
    
    prev_total = len(prev_df)
    curr_total = len(curr_df)
    
    prev_positive = len(prev_df[prev_df['grade'] >= 4]) / prev_total * 100 if prev_total > 0 else 0
    curr_positive = len(curr_df[curr_df['grade'] >= 4]) / curr_total * 100 if curr_total > 0 else 0
    
    prev_neutral = len(prev_df[prev_df['grade'] == 3]) / prev_total * 100 if prev_total > 0 else 0
    curr_neutral = len(curr_df[curr_df['grade'] == 3]) / curr_total * 100 if curr_total > 0 else 0
    
    prev_negative = len(prev_df[prev_df['grade'] <= 2]) / prev_total * 100 if prev_total > 0 else 0
    curr_negative = len(curr_df[curr_df['grade'] <= 2]) / curr_total * 100 if curr_total > 0 else 0
    
    positive_change = calculate_change(curr_positive, prev_positive)
    neutral_change = calculate_change(curr_neutral, prev_neutral)
    negative_change = calculate_change(curr_negative, prev_negative)
    total_change = calculate_change(curr_total, prev_total)
    
    # Статистика по категориям (используем таблицы classes)
    category_stats = []
    product_classes = get_product_classes()
    
    # Если фильтр по продукту НЕ установлен, показываем все категории
    if not product_filter or product_filter == 'all':
        for category in df['service_category'].unique():
            if category == 'all':  # Пропускаем категорию "all"
                continue
            cat_df = df[df['service_category'] == category]
            
            # Применяем фильтр по периоду если есть
            if period_filter:
                cat_df['date'] = pd.to_datetime(cat_df['dateCreate'])
                if period_filter.startswith('2024-') or period_filter.startswith('2025-'):
                    if len(period_filter) == 7:
                        year, month = period_filter.split('-')
                        cat_df = cat_df[
                            (cat_df['date'].dt.year == int(year)) & 
                            (cat_df['date'].dt.month == int(month))
                        ]
                    elif len(period_filter) == 4:
                        cat_df = cat_df[cat_df['date'].dt.year == int(period_filter)]
                elif 'Q' in period_filter:
                    year, quarter = period_filter.split('-Q')
                    quarter_months = {
                        '1': [1, 2, 3], '2': [4, 5, 6], 
                        '3': [7, 8, 9], '4': [10, 11, 12]
                    }
                    if quarter in quarter_months:
                        cat_df = cat_df[
                            (cat_df['date'].dt.year == int(year)) & 
                            (cat_df['date'].dt.month.isin(quarter_months[quarter]))
                        ]
            
            # Пропускаем пустые категории
            if len(cat_df) == 0:
                continue
                
            cat_positive = len(cat_df[cat_df['grade'] >= 4]) / len(cat_df) * 100
            cat_neutral = len(cat_df[cat_df['grade'] == 3]) / len(cat_df) * 100
            cat_negative = len(cat_df[cat_df['grade'] <= 2]) / len(cat_df) * 100
            
            category_stats.append({
                'name': product_classes.get(category, category),
                'category_key': category,  # Добавляем ключ для фильтрации
                'total': len(cat_df),
                'positive': round(cat_positive, 1),
                'neutral': round(cat_neutral, 1),
                'negative': round(cat_negative, 1),
                'avg_rating': round(cat_df['grade'].mean(), 1)
            })
    else:
        # Если установлен фильтр по продукту, показываем только эту категорию
        product_key = product_filter
        for key, name in product_classes.items():
            if name == product_filter or key == product_filter:
                product_key = key
                break
        
        cat_df = filtered_df  # Уже отфильтрованные данные
        if len(cat_df) > 0:
            cat_positive = len(cat_df[cat_df['grade'] >= 4]) / len(cat_df) * 100
            cat_neutral = len(cat_df[cat_df['grade'] == 3]) / len(cat_df) * 100
            cat_negative = len(cat_df[cat_df['grade'] <= 2]) / len(cat_df) * 100
            
            category_stats.append({
                'name': product_classes.get(product_key, product_key),
                'category_key': product_key,
                'total': len(cat_df),
                'positive': round(cat_positive, 1),
                'neutral': round(cat_neutral, 1),
                'negative': round(cat_negative, 1),
                'avg_rating': round(cat_df['grade'].mean(), 1)
            })
    
    # Сортируем по количеству отзывов
    category_stats.sort(key=lambda x: x['total'], reverse=True)
    
    # Динамика по времени (с 1 января 2024 до 31 мая 2025)
    df['date'] = pd.to_datetime(df['dateCreate'])
    monthly_stats = []
    
    # Определяем период анализа
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 5, 31)
    
    # Генерируем все месяцы в указанном периоде
    current_date = start_date.replace(day=1)  # Начинаем с 1 числа
    
    while current_date <= end_date:
        # Определяем границы текущего месяца
        if current_date.month == 12:
            next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            next_month = current_date.replace(month=current_date.month + 1, day=1)
        
        # Фильтруем данные за текущий месяц
        month_df = df[(df['date'] >= current_date) & (df['date'] < next_month)]
        
        month_stat = {
            'month': current_date.strftime('%Y-%m'),
            'total': len(month_df),
            'positive': len(month_df[month_df['grade'] >= 4]),
            'neutral': len(month_df[month_df['grade'] == 3]),
            'negative': len(month_df[month_df['grade'] <= 2]),
            'categories': {}
        }
        
        # Добавляем разбивку по категориям для каждого месяца (используем таблицу classes)
        product_classes = get_product_classes()
        for category in df['service_category'].unique():
            if category == 'all':  # Пропускаем категорию "all"
                continue
            # Проверяем что категория есть в таблице classes
            if category not in product_classes:
                continue
                
            cat_month_df = month_df[month_df['service_category'] == category]
            month_stat['categories'][category] = {
                'total': len(cat_month_df),
                'positive': len(cat_month_df[cat_month_df['grade'] >= 4]),
                'neutral': len(cat_month_df[cat_month_df['grade'] == 3]),
                'negative': len(cat_month_df[cat_month_df['grade'] <= 2])
            }
        
        monthly_stats.append(month_stat)
        
        # Переходим к следующему месяцу
        current_date = next_month
    
    return {
        'total_reviews': total_reviews,
        'positive_percent': round(positive, 1),
        'neutral_percent': round(neutral, 1),
        'negative_percent': round(negative, 1),
        'positive_change': round(positive_change, 1),
        'neutral_change': round(neutral_change, 1),
        'negative_change': round(negative_change, 1),
        'total_change': round(total_change, 1),
        'category_stats': category_stats,
        'monthly_stats': monthly_stats
    }

@app.route('/')
def dashboard():
    """Главная страница дашборда"""
    
    # Всегда используем только реальные данные
    df = load_dashboard_data_from_db()
    stats = calculate_dashboard_stats(df)
    # Всегда используем реальные данные из БД
    
    return render_template('dashboard.html', stats=stats)

@app.route('/api/analyze', methods=['POST'])
def analyze_reviews():
    """API endpoint для анализа отзывов ML моделью
    
    Принимает формат: {"reviews": [{"id": "123", "text": "..."}]}
    Возвращает: {"results": [{"id": "123", "topics": [...], "sentiments": [...]}]}
    """
    import signal
    from functools import wraps
    import time
    
    def timeout_handler(signum, frame):
        raise TimeoutError("ML model analysis timeout (3 minutes exceeded)")
    
    data = None  # Инициализируем для обработки timeout
    
    try:
        # Устанавливаем 3-минутный таймаут
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(180)  # 3 минуты = 180 секунд
        
        data = request.get_json()
        
        # Валидация входного формата согласно ML_API_CONTRACT.md
        if not data or 'reviews' not in data:
            return jsonify({
                'error': 'Требуется поле reviews с массивом отзывов',
                'expected_format': {'reviews': [{'id': 'string', 'text': 'string'}]}
            }), 400
            
        reviews = data['reviews']
        
        if not isinstance(reviews, list):
            return jsonify({'error': 'Поле reviews должно быть массивом'}), 400
            
        # Валидация каждого отзыва
        for i, review in enumerate(reviews):
            if not isinstance(review, dict):
                return jsonify({'error': f'Отзыв {i} должен быть объектом'}), 400
            if 'id' not in review or 'text' not in review:
                return jsonify({'error': f'Отзыв {i} должен содержать поля id и text'}), 400
        
        # Анализ через ML модель (временная заглушка)
        ml_response = mock_ml_analysis_v2(reviews)
        
        # Отменяем таймаут при успешном завершении
        signal.alarm(0)
        
        # Возвращаем результат как есть (уже содержит results и errors)
        return jsonify(ml_response)
        
    except TimeoutError:
        signal.alarm(0)
        # Возвращаем fallback результаты при таймауте
        fallback_results = []
        if data and 'reviews' in data:
            for review in data['reviews']:
                fallback_results.append({
                'id': review.get('id', 'unknown'),
                'topics': ['none'],
                'sentiments': ['neutral']
            })
        
        return jsonify({
            'results': fallback_results,
            'errors': ['ML model timeout after 3 minutes']
        }), 408
        
    except Exception as e:
        signal.alarm(0)
        return jsonify({
            'results': [],
            'errors': [f'Internal ML model error: {str(e)}']
        }), 500

@app.route('/api/stats')
def api_stats():
    """API endpoint для получения статистики"""
    
    # Получаем параметры фильтрации
    product_filter = request.args.get('product')
    period_filter = request.args.get('period')
    
    # Всегда используем только реальные данные
    df = load_dashboard_data_from_db()
    stats = calculate_dashboard_stats(df, product_filter, period_filter)
    # Всегда используем реальные данные из БД
    
    return jsonify(stats)

@app.route('/api/products')
def api_products():
    """API endpoint для получения списка продуктов из таблицы classes"""
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT class_name, class_label_ru, description, total_reviews 
                FROM classes 
                ORDER BY total_reviews DESC
            """)
            classes = cur.fetchall()
            
            products = []
            for row in classes:
                products.append({
                    'key': row['class_name'],
                    'name': row['class_label_ru'],
                    'description': row['description'],
                    'total_reviews': row['total_reviews']
                })
            
            return jsonify({'products': products})
            
    except Exception as e:
        return jsonify({'error': f'Ошибка получения продуктов: {str(e)}'}), 500
    finally:
        if conn:
            return_db_connection(conn)

@app.route('/api/download-test-data')
def download_test_data():
    """Загрузка тестовых 250 отзывов в JSON формате"""
    try:
        # Загружаем реальные данные
        df = load_dashboard_data_from_db()
        
        # Ограничиваем до 250 отзывов
        test_data = df.head(250)
        
        # Преобразуем в формат для ML API согласно ML_API_CONTRACT.md
        result = {
            'reviews': []
        }
        
        for _, row in test_data.iterrows():
            review = {
                'id': str(row.get('id', '')),
                'text': str(row.get('text', ''))
            }
            result['reviews'].append(review)
        
        response = jsonify(result)
        response.headers['Content-Disposition'] = 'attachment; filename=gazprombank_test_reviews_250.json'
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        
        return response
        
    except Exception as e:
        return jsonify({'error': f'Ошибка экспорта данных: {str(e)}'}), 500

@app.route('/reviews')
def reviews_page():
    """Страница отзывов"""
    # Всегда используем реальные данные из БД  
    df = load_dashboard_data_from_db()
    
    # Получаем последние 20 отзывов
    recent_reviews = df.head(20).to_dict('records')
    
    stats = {
        'total_reviews': len(df),

        'recent_reviews': recent_reviews
    }
    
    return render_template('reviews.html', stats=stats)

@app.route('/products')
def products_page():
    """Страница продуктов"""
    # Всегда используем реальные данные из БД  
    df = load_dashboard_data_from_db()
    
    # Статистика по категориям (используем таблицу classes)
    category_stats = []
    product_classes = get_product_classes()
    
    for category in df['service_category'].unique():
        if category == 'all':  # Пропускаем категорию "all"
            continue
        # Проверяем что категория есть в таблице classes
        if category not in product_classes:
            continue
            
        cat_df = df[df['service_category'] == category]
        if len(cat_df) == 0:  # Пропускаем пустые категории
            continue
            
        category_stats.append({
            'name': product_classes[category],
            'category_key': category,
            'total': len(cat_df),
            'avg_rating': round(cat_df['grade'].mean(), 1),
            'positive': len(cat_df[cat_df['grade'] >= 4]),
            'neutral': len(cat_df[cat_df['grade'] == 3]),
            'negative': len(cat_df[cat_df['grade'] <= 2])
        })
    
    category_stats.sort(key=lambda x: x['total'], reverse=True)
    
    stats = {
        'total_reviews': len(df),

        'category_stats': category_stats
    }
    
    return render_template('products.html', stats=stats)

@app.route('/health')
def health_check():
    """Health check для мониторинга"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()}), 200

@app.route('/favicon.ico')
def favicon():
    """Favicon endpoint to prevent 404 errors"""
    return '', 204

# Make sure app is available for gunicorn import
application = app

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV', 'production') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)