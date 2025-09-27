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

# Create Flask app with proper configuration
app = Flask(__name__)

# Configure Flask for production
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'fallback-secret-key-for-development')
app.config['JSON_AS_ASCII'] = False  # Support for Russian characters
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Словарь для перевода названий категорий продуктов
CATEGORY_TRANSLATIONS = {
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

def translate_category_name(category_name):
    """Перевод названия категории с английского на русский"""
    return CATEGORY_TRANSLATIONS.get(category_name, category_name)

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
def load_dashboard_data(use_mock=True):
    """Загрузка данных для отображения в дашборде"""
    
    try:
        if use_mock:
            return create_mock_dashboard_data()
            
        # Загружаем основной файл с отзывами
        csv_paths = ['data/csv/gazprombank_reviews.csv', 'gazprombank_reviews.csv']
        df = None
        for path in csv_paths:
            if os.path.exists(path):
                df = pd.read_csv(path, nrows=50000)  # Ограничиваем для производительности
                break
        if df is None:
            # Если основного файла нет, создаем mock данные
            df = create_mock_dashboard_data()
            
        return df
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return create_mock_dashboard_data()

def create_mock_dashboard_data():
    """Создание mock данных для демонстрации дашборда"""
    
    # Все категории из CATEGORY_TRANSLATIONS для гарантированного покрытия
    categories = [
        'debet_cards', 'credit_cards', 'hypothec', 'auto_credit', 
        'consumer_credit', 'restructuring', 'deposits', 'money_transfer',
        'remote_service', 'other_individual', 'mobile_app', 'individual_service',
        'service_individual'
    ]
    
    # Генерируем равное количество отзывов для каждой категории
    reviews_per_category = 1000  
    data = []
    
    # Период с 1 января 2024 до 31 мая 2025 (всего 516 дней)
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2025, 5, 31)
    total_days = (end_date - start_date).days
    
    # Генерируем отзывы для каждой категории
    for category in categories:
        for i in range(reviews_per_category):
            review_date = start_date + timedelta(days=random.randint(0, total_days))
            review_id = len(data)
            
            data.append({
                'id': f'mock_{review_id}',
                'dateCreate': review_date.strftime('%Y-%m-%d %H:%M:%S'),
                'grade': random.randint(1, 5),
                'service_category': category,
                'text': f'Mock отзыв #{review_id} о {CATEGORY_TRANSLATIONS.get(category, category)}',
                'title': f'Отзыв {review_id}',
                'bank_name': 'Газпромбанк'
            })
    
    return pd.DataFrame(data)

# Расчет статистики для дашборда
def calculate_dashboard_stats(df):
    """Расчет статистики для дашборда"""
    
    # Общая статистика
    total_reviews = len(df)
    
    # Распределение по тональности (на основе рейтинга)
    positive = len(df[df['grade'] >= 4]) / total_reviews * 100
    neutral = len(df[df['grade'] == 3]) / total_reviews * 100
    negative = len(df[df['grade'] <= 2]) / total_reviews * 100
    
    # Статистика по категориям (исключаем категорию "all")
    category_stats = []
    for category in df['service_category'].unique():
        if category == 'all':  # Пропускаем категорию "all"
            continue
        cat_df = df[df['service_category'] == category]
        cat_positive = len(cat_df[cat_df['grade'] >= 4]) / len(cat_df) * 100
        cat_neutral = len(cat_df[cat_df['grade'] == 3]) / len(cat_df) * 100
        cat_negative = len(cat_df[cat_df['grade'] <= 2]) / len(cat_df) * 100
        
        category_stats.append({
            'name': translate_category_name(category),
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
        
        # Добавляем разбивку по категориям для каждого месяца
        for category in df['service_category'].unique():
            if category == 'all':  # Пропускаем категорию "all"
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
        'category_stats': category_stats,
        'monthly_stats': monthly_stats
    }

@app.route('/')
def dashboard():
    """Главная страница дашборда"""
    
    # Всегда используем только реальные данные
    df = load_dashboard_data(use_mock=False)
    stats = calculate_dashboard_stats(df)
    stats['use_mock'] = False
    
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
    
    # Всегда используем только реальные данные
    df = load_dashboard_data(use_mock=False)
    stats = calculate_dashboard_stats(df)
    stats['use_mock'] = False
    
    return jsonify(stats)

@app.route('/api/download-test-data')
def download_test_data():
    """Загрузка тестовых 250 отзывов в JSON формате"""
    try:
        # Загружаем реальные данные
        df = load_dashboard_data(use_mock=False)
        
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
    use_mock = request.args.get('use_mock', 'false').lower() == 'true'
    df = load_dashboard_data(use_mock=use_mock)
    
    # Получаем последние 20 отзывов
    recent_reviews = df.head(20).to_dict('records')
    
    stats = {
        'total_reviews': len(df),
        'use_mock': use_mock,
        'recent_reviews': recent_reviews
    }
    
    return render_template('reviews.html', stats=stats)

@app.route('/products')
def products_page():
    """Страница продуктов"""
    use_mock = request.args.get('use_mock', 'false').lower() == 'true'
    df = load_dashboard_data(use_mock=use_mock)
    
    # Статистика по категориям (исключаем категорию "all")
    category_stats = []
    for category in df['service_category'].unique():
        if category == 'all':  # Пропускаем категорию "all"
            continue
        cat_df = df[df['service_category'] == category]
        category_stats.append({
            'name': translate_category_name(category),
            'total': len(cat_df),
            'avg_rating': round(cat_df['grade'].mean(), 1),
            'positive': len(cat_df[cat_df['grade'] >= 4]),
            'neutral': len(cat_df[cat_df['grade'] == 3]),
            'negative': len(cat_df[cat_df['grade'] <= 2])
        })
    
    category_stats.sort(key=lambda x: x['total'], reverse=True)
    
    stats = {
        'total_reviews': len(df),
        'use_mock': use_mock,
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