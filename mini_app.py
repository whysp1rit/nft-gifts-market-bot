from flask import Flask, render_template, request, jsonify, session, make_response
import sqlite3
import uuid
from datetime import datetime
import os
import requests
import asyncio

app = Flask(__name__)
app.secret_key = 'nft-gifts-mini-app-secret-key'

# Конфигурация бота для уведомлений
BOT_TOKEN = "8512489092:AAFghx4VAurEYdi8gDZVUJ71pqGRnC8-n4M"
ADMIN_ID = 8566238705

def get_or_create_user(telegram_id, username=None, first_name=None):
    """
    Получает существующего пользователя или создает нового с уникальным UID
    UID создается только один раз и никогда не изменяется
    """
    import random
    import string
    
    conn = sqlite3.connect('data/unified.db')
    cursor = conn.cursor()
    
    try:
        # Сначала ищем пользователя по telegram_id
        cursor.execute('''
            SELECT uid, telegram_id, username, first_name, balance_stars, balance_rub, successful_deals, verified, phone, created_at
            FROM users WHERE telegram_id = ?
        ''', (str(telegram_id),))
        
        existing_user = cursor.fetchone()
        
        if existing_user:
            # Пользователь существует - обновляем только имя и username если они изменились
            current_username = existing_user[2]
            current_first_name = existing_user[3]
            
            if (username and username != current_username) or (first_name and first_name != current_first_name):
                cursor.execute('''
                    UPDATE users 
                    SET username = COALESCE(?, username), 
                        first_name = COALESCE(?, first_name)
                    WHERE telegram_id = ?
                ''', (username, first_name, str(telegram_id)))
                conn.commit()
                print(f"🔄 Обновлены данные пользователя {telegram_id}")
            
            # Возвращаем обновленные данные
            cursor.execute('''
                SELECT uid, telegram_id, username, first_name, balance_stars, balance_rub, successful_deals, verified, phone, created_at
                FROM users WHERE telegram_id = ?
            ''', (str(telegram_id),))
            user_data = cursor.fetchone()
            
        else:
            # Пользователь не существует - создаем нового с уникальным UID
            while True:
                uid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                cursor.execute('SELECT uid FROM users WHERE uid = ?', (uid,))
                if not cursor.fetchone():
                    break
            
            # Создаем нового пользователя
            cursor.execute('''
                INSERT INTO users (uid, telegram_id, username, first_name, balance_stars, balance_rub, successful_deals, verified)
                VALUES (?, ?, ?, ?, 0, 0, 0, FALSE)
            ''', (uid, str(telegram_id), username, first_name))
            
            conn.commit()
            print(f"➕ Создан новый пользователь {telegram_id} с UID: {uid}")
            
            # Получаем созданного пользователя
            cursor.execute('''
                SELECT uid, telegram_id, username, first_name, balance_stars, balance_rub, successful_deals, verified, phone, created_at
                FROM users WHERE telegram_id = ?
            ''', (str(telegram_id),))
            user_data = cursor.fetchone()
        
        conn.close()
        return user_data
        
    except Exception as e:
        conn.close()
        print(f"❌ Ошибка работы с пользователем {telegram_id}: {e}")
        return None

def notify_admin_about_deal(deal_id, seller_name, amount, currency, description):
    """Отправляет уведомление администратору о новой сделке через Telegram Bot API"""
    try:
        currency_symbols = {
            'stars': '⭐',
            'rub': '₽',
            'uah': '₴',
            'usd': '$',
            'eur': '€'
        }
        
        symbol = currency_symbols.get(currency, '')
        
        text = f"🆕 <b>Новая сделка создана!</b>\n\n" \
               f"🆔 <b>ID сделки:</b> #{deal_id}\n" \
               f"👤 <b>Продавец:</b> {seller_name}\n" \
               f"💰 <b>Сумма:</b> {symbol}{amount}\n" \
               f"📝 <b>Описание:</b> {description or 'Не указано'}\n\n" \
               f"⏳ <b>Статус:</b> Ожидает подтверждения"
        
        # Создаем inline клавиатуру
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Подтвердить сделку",
                        "callback_data": f"confirm_deal_{deal_id}"
                    }
                ],
                [
                    {
                        "text": "❌ Отклонить сделку", 
                        "callback_data": f"reject_deal_{deal_id}"
                    }
                ],
                [
                    {
                        "text": "🔍 Посмотреть сделку",
                        "url": f"https://nft-gifts-market-bot.onrender.com/deal/{deal_id}"
                    }
                ]
            ]
        }
        
        # Отправляем сообщение через Telegram Bot API
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ADMIN_ID,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ Уведомление о сделке {deal_id} отправлено администратору")
        else:
            print(f"❌ Ошибка отправки уведомления: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка уведомления администратора: {e}")

# Убираем все предупреждения и добавляем CORS
@app.after_request
def after_request(response):
    """Убираем предупреждения и добавляем нужные заголовки"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['ngrok-skip-browser-warning'] = 'true'
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Content-Security-Policy'] = "frame-ancestors *"
    return response

# Инициализация единой базы данных для Mini App
def init_mini_app_db():
    """Инициализирует базу данных или проверяет подключение"""
    try:
        # Создаем папку data если её нет
        os.makedirs('data', exist_ok=True)
        
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        # Проверяем, существует ли таблица users
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("📊 База данных не найдена. Запустите init_db.py для инициализации.")
            conn.close()
            return
        
        # Проверяем подключение
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        print(f"📊 Подключение к единой базе: {user_count} пользователей")
        
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        print("💡 Запустите init_db.py для создания базы данных")

# Главная страница Mini App
@app.route('/')
def index():
    response = make_response(render_template('mini_app/index.html'))
    return response

# Тестовая страница для отладки UID
@app.route('/test-uid')
def test_uid():
    """Простая тестовая страница для проверки UID системы"""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>UID Test Page</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; text-align: center; }
            .card { background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px auto; max-width: 400px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🆔 UID Test Page</h1>
            <p>UID система работает корректно!</p>
            <p>Этот эндпоинт используется для тестирования.</p>
            <button onclick="window.location.href='/'">🏠 На главную</button>
        </div>
    </body>
    </html>
    """

# Тестовая страница для отладки параметров startapp
@app.route('/test-startapp')
def test_startapp():
    """Страница для отладки параметров startapp"""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>StartApp Parameters Test</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            .info { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; }
            pre { background: #e9ecef; padding: 10px; border-radius: 4px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>🔗 Тест параметров StartApp</h1>
        <div id="info"></div>
        <button onclick="window.location.href='/'">🏠 На главную</button>
        
        <script>
            let tg = window.Telegram.WebApp;
            tg.ready();
            
            const info = document.getElementById('info');
            const initData = tg.initDataUnsafe;
            const urlParams = new URLSearchParams(window.location.search);
            
            info.innerHTML = `
                <div class="info">
                    <h3>Данные инициализации:</h3>
                    <pre>${JSON.stringify(initData, null, 2)}</pre>
                </div>
                <div class="info">
                    <h3>URL параметры:</h3>
                    <pre>${JSON.stringify(Object.fromEntries(urlParams), null, 2)}</pre>
                </div>
                <div class="info">
                    <h3>Полный URL:</h3>
                    <pre>${window.location.href}</pre>
                </div>
            `;
        </script>
    </body>
    </html>
    """
    with open('test_startapp_params.html', 'r', encoding='utf-8') as f:
        content = f.read()
    return content

# Создание сделки
@app.route('/create')
def create_deal():
    return render_template('mini_app/create.html')

# Мои сделки
@app.route('/deals')
def my_deals():
    return render_template('mini_app/deals.html')

# Профиль
@app.route('/profile')
def profile():
    return render_template('mini_app/profile.html')

# Страница привязки UID к Telegram аккаунту
@app.route('/link-uid')
def link_uid():
    return render_template('mini_app/link_uid.html')

# API для привязки UID
@app.route('/api/link_uid', methods=['POST'])
def api_link_uid():
    try:
        data = request.get_json()
        telegram_user = data.get('telegram_user')
        target_uid = data.get('uid', '').strip().upper()
        
        if not telegram_user or not target_uid:
            return jsonify({'success': False, 'message': 'Не указаны данные пользователя или UID'})
        
        if len(target_uid) != 8:
            return jsonify({'success': False, 'message': 'UID должен содержать 8 символов'})
        
        telegram_id = str(telegram_user['id'])
        username = telegram_user.get('username')
        first_name = telegram_user.get('first_name')
        
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        # Проверяем, существует ли UID
        cursor.execute('SELECT telegram_id, first_name FROM users WHERE uid = ?', (target_uid,))
        existing_user = cursor.fetchone()
        
        if not existing_user:
            conn.close()
            return jsonify({'success': False, 'message': f'UID {target_uid} не найден в системе'})
        
        # Обновляем данные пользователя с этим UID
        cursor.execute('''
            UPDATE users SET 
                telegram_id = ?,
                username = ?,
                first_name = ?
            WHERE uid = ?
        ''', (telegram_id, username, first_name, target_uid))
        
        # Удаляем возможные дубликаты по telegram_id
        cursor.execute('''
            DELETE FROM users 
            WHERE telegram_id = ? AND uid != ?
        ''', (telegram_id, target_uid))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'UID {target_uid} успешно привязан к вашему аккаунту',
            'uid': target_uid,
            'telegram_id': telegram_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# Админ панель
@app.route('/admin')
def admin_panel():
    return render_template('mini_app/admin.html')

# API для создания сделки (БЕЗ UID системы)
@app.route('/api/create_deal', methods=['POST'])
def api_create_deal():
    try:
        data = request.get_json()
        
        # Получаем данные пользователя из Telegram WebApp
        telegram_user = data.get('telegram_user')
        if not telegram_user:
            return jsonify({'success': False, 'message': 'Не удалось получить данные пользователя'})
        
        deal_id = str(uuid.uuid4())[:8].upper()
        
        # Получаем или создаем пользователя (упрощённо, без обязательного UID)
        telegram_id = telegram_user['id']
        username = telegram_user.get('username')
        first_name = telegram_user.get('first_name')
        
        # Создаём пользователя если его нет
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT telegram_id FROM users WHERE telegram_id = ?', (str(telegram_id),))
        if not cursor.fetchone():
            # Создаём нового пользователя без UID (UID опционален)
            cursor.execute('''
                INSERT INTO users (telegram_id, username, first_name, balance_stars, balance_rub, successful_deals, verified)
                VALUES (?, ?, ?, 0, 0, 0, FALSE)
            ''', (str(telegram_id), username, first_name))
            conn.commit()
        
        # Создаем сделку
        cursor.execute('''
            INSERT INTO deals (id, seller_id, nft_link, nft_username, amount, currency, status, description)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        ''', (deal_id, str(telegram_id), data.get('nft_link'), data.get('nft_username'), 
              data.get('amount'), data.get('currency'), data.get('description')))
        
        conn.commit()
        conn.close()
        
        # Получаем текущий хост для создания ссылки
        base_url = request.host_url.rstrip('/')
        
        # Для локального тестирования используем localhost
        if 'localhost' in request.host or '127.0.0.1' in request.host:
            base_url = 'http://localhost:3000'
        # Если мы на Render, используем правильный домен
        elif 'onrender.com' in request.host or 'render.com' in request.host:
            base_url = 'https://nft-gifts-market-bot.onrender.com'
        
        # Создаем ссылку для бота в Telegram (обычная ссылка, не мини приложение)
        deal_url = f"https://t.me/noscamnftrbot?start=deal_{deal_id}"
        
        # Уведомляем администратора о новой сделке
        try:
            notify_admin_about_deal(deal_id, first_name or username or str(telegram_id), 
                                  data.get('amount'), data.get('currency'), 
                                  data.get('description'))
        except Exception as e:
            print(f"❌ Ошибка уведомления администратора: {e}")
        
        return jsonify({
            'success': True, 
            'deal_id': deal_id,
            'deal_url': deal_url,
            'warning': 'Вы сможете забрать средства после передачи NFT. Для вывода нужна авторизация и обращение к поддержке @noscamnftsup'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# Просмотр сделки
@app.route('/deal/<deal_id>')
def view_deal(deal_id):
    return render_template('mini_app/deal.html', deal_id=deal_id)

# API для получения сделки
@app.route('/api/deal/<deal_id>')
def api_get_deal(deal_id):
    try:
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM deals WHERE id = ?', (deal_id,))
        deal = cursor.fetchone()
        conn.close()
        
        if not deal:
            return jsonify({'success': False, 'message': 'Сделка не найдена'})
        
        deal_data = {
            'id': deal[0],
            'seller_id': deal[1],
            'buyer_id': deal[2],
            'nft_link': deal[3],
            'nft_username': deal[4],
            'amount': deal[5],
            'currency': deal[6],
            'status': deal[7],
            'created_at': deal[8],
            'description': deal[11] if len(deal) > 11 else None
        }
        
        return jsonify({'success': True, 'deal': deal_data})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# API для получения моих сделок
@app.route('/api/my_deals')
def api_my_deals():
    try:
        telegram_user_id = request.args.get('user_id')
        
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        # Сделки где пользователь продавец
        cursor.execute('''
            SELECT * FROM deals WHERE seller_id = ? ORDER BY created_at DESC LIMIT 50
        ''', (telegram_user_id,))
        seller_deals = cursor.fetchall()
        
        # Сделки где пользователь покупатель
        cursor.execute('''
            SELECT * FROM deals WHERE buyer_id = ? ORDER BY created_at DESC LIMIT 50
        ''', (telegram_user_id,))
        buyer_deals = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'seller_deals': seller_deals,
            'buyer_deals': buyer_deals
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# API для получения данных пользователя
@app.route('/api/user_profile')
def api_user_profile():
    try:
        telegram_user_id = request.args.get('user_id')
        username = request.args.get('username')
        first_name = request.args.get('first_name')
        
        if not telegram_user_id:
            return jsonify({'success': False, 'message': 'Не указан ID пользователя'})
        
        # Получаем или создаем пользователя (UID создается только один раз)
        user_data = get_or_create_user(telegram_user_id, username, first_name)
        if not user_data:
            return jsonify({'success': False, 'message': 'Ошибка получения данных пользователя'})
        
        # Формируем ответ
        user_response = {
            'uid': user_data[0],
            'telegram_id': user_data[1],
            'username': user_data[2],
            'first_name': user_data[3],
            'balance_stars': user_data[4],
            'balance_rub': user_data[5],
            'successful_deals': user_data[6],
            'verified': bool(user_data[7]) if user_data[7] is not None else False,
            'phone': user_data[8],
            'created_at': user_data[9],
            'is_new_user': False  # Пользователь существует в системе
        }
        
        return jsonify({'success': True, 'user': user_response})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# API для подтверждения сделки админом (начисление баланса продавцу)
@app.route('/api/admin/confirm_deal', methods=['POST'])
def api_admin_confirm_deal():
    try:
        data = request.get_json()
        deal_id = data.get('deal_id')
        admin_id = data.get('admin_id')
        
        # Проверка прав админа
        if str(admin_id) != str(ADMIN_ID):
            return jsonify({'success': False, 'message': 'Нет прав администратора'})
        
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        # Получаем информацию о сделке
        cursor.execute('SELECT seller_id, amount, currency, status FROM deals WHERE id = ?', (deal_id,))
        deal = cursor.fetchone()
        
        if not deal:
            conn.close()
            return jsonify({'success': False, 'message': 'Сделка не найдена'})
        
        seller_id, amount, currency, status = deal
        
        if status != 'pending':
            conn.close()
            return jsonify({'success': False, 'message': 'Сделка уже обработана'})
        
        # Начисляем баланс продавцу
        if currency == 'stars':
            cursor.execute('UPDATE users SET balance_stars = balance_stars + ? WHERE telegram_id = ?', 
                         (amount, seller_id))
        elif currency in ['rub', 'uah']:
            cursor.execute('UPDATE users SET balance_rub = balance_rub + ? WHERE telegram_id = ?', 
                         (amount, seller_id))
        
        # Обновляем статус сделки
        cursor.execute('UPDATE deals SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?', 
                      ('completed', deal_id))
        
        # Увеличиваем счётчик успешных сделок
        cursor.execute('UPDATE users SET successful_deals = successful_deals + 1 WHERE telegram_id = ?', 
                      (seller_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Сделка подтверждена. Продавцу начислено {amount} {currency}',
            'deal_id': deal_id
        })
        
    except Exception as e:
        print(f"Ошибка подтверждения сделки: {e}")
        return jsonify({'success': False, 'message': f'Ошибка сервера: {str(e)}'})

# API для отклонения сделки админом
@app.route('/api/admin/reject_deal', methods=['POST'])
def api_admin_reject_deal():
    try:
        data = request.get_json()
        deal_id = data.get('deal_id')
        admin_id = data.get('admin_id')
        
        # Проверка прав админа
        if str(admin_id) != str(ADMIN_ID):
            return jsonify({'success': False, 'message': 'Нет прав администратора'})
        
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        # Обновляем статус сделки
        cursor.execute('UPDATE deals SET status = ? WHERE id = ?', ('rejected', deal_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Сделка отклонена',
            'deal_id': deal_id
        })
        
    except Exception as e:
        print(f"Ошибка отклонения сделки: {e}")
        return jsonify({'success': False, 'message': f'Ошибка сервера: {str(e)}'})

# API для получения списка пользователей (админ)
@app.route('/api/admin/users')
def api_admin_users():
    try:
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT uid, telegram_id, username, first_name, balance_stars, balance_rub, successful_deals, verified, created_at
            FROM users ORDER BY created_at DESC
        ''')
        users = cursor.fetchall()
        conn.close()
        
        users_list = []
        for user in users:
            users_list.append({
                'uid': user[0],
                'telegram_id': user[1],
                'username': user[2] or 'Не указан',
                'first_name': user[3] or 'Не указано',
                'balance_stars': user[4],
                'balance_rub': user[5],
                'successful_deals': user[6],
                'verified': bool(user[7]) if user[7] is not None else False,
                'created_at': user[8]
            })
        
        return jsonify({'success': True, 'users': users_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# API для получения статистики (админ)
@app.route('/api/admin/stats')
def api_admin_stats():
    try:
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE verified = TRUE')
        verified_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(balance_stars), SUM(balance_rub) FROM users')
        balances = cursor.fetchone()
        total_stars = balances[0] or 0
        total_rub = balances[1] or 0
        
        cursor.execute('SELECT COUNT(*) FROM deals')
        total_deals = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'verified_users': verified_users,
                'total_stars': total_stars,
                'total_rub': total_rub,
                'total_deals': total_deals
            }
        })
        
    except Exception as e:
        print(f"Ошибка API статистики: {e}")
        return jsonify({'success': False, 'message': f'Ошибка сервера: {str(e)}'})

# API для пополнения баланса по UID (админ)
@app.route('/api/admin/add_balance', methods=['POST'])
def api_admin_add_balance():
    try:
        data = request.get_json()
        uid = data.get('uid', '').strip().upper()
        stars = int(data.get('stars', 0))
        rub = float(data.get('rub', 0))
        
        if not uid:
            return jsonify({'success': False, 'message': 'UID не указан'})
        
        if len(uid) != 8:
            return jsonify({'success': False, 'message': 'UID должен содержать 8 символов'})
        
        if stars == 0 and rub == 0:
            return jsonify({'success': False, 'message': 'Укажите сумму для пополнения'})
        
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь с таким UID
        cursor.execute('SELECT telegram_id, username, first_name FROM users WHERE uid = ?', (uid,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': f'Пользователь с UID {uid} не найден'})
        
        telegram_id, username, first_name = user
        
        # Пополняем баланс
        cursor.execute('''
            UPDATE users SET 
                balance_stars = balance_stars + ?,
                balance_rub = balance_rub + ?
            WHERE uid = ?
        ''', (stars, rub, uid))
        
        conn.commit()
        conn.close()
        
        user_info = f"{first_name} (@{username}) | ID: {telegram_id}"
        
        return jsonify({
            'success': True,
            'message': f'Баланс пополнен для {user_info}',
            'user_info': user_info,
            'added': {
                'stars': stars,
                'rub': rub
            }
        })
        
    except Exception as e:
        print(f"Ошибка пополнения баланса: {e}")
        return jsonify({'success': False, 'message': f'Ошибка сервера: {str(e)}'})

# API для накрутки успешных сделок (админ)
@app.route('/api/admin/update_deals', methods=['POST'])
def api_admin_update_deals():
    try:
        data = request.get_json()
        telegram_id = data.get('telegram_id')
        deals_count = int(data.get('deals_count', 0))
        
        if not telegram_id or deals_count < 0:
            return jsonify({'success': False, 'message': 'Неверные данные'})
        
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        # Создаем пользователя если не существует
        cursor.execute('''
            INSERT OR IGNORE INTO users (telegram_id) VALUES (?)
        ''', (telegram_id,))
        
        # Обновляем количество сделок
        cursor.execute('''
            UPDATE users SET successful_deals = ? WHERE telegram_id = ?
        ''', (deals_count, telegram_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Количество сделок установлено: {deals_count}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# API для накрутки успешных сделок по UID (админ)
@app.route('/api/admin/update_deals_by_uid', methods=['POST'])
def api_admin_update_deals_by_uid():
    try:
        data = request.get_json()
        uid = data.get('uid', '').strip().upper()
        deals_count = int(data.get('deals_count', 0))
        
        if not uid:
            return jsonify({'success': False, 'message': 'UID не указан'})
        
        if len(uid) != 8:
            return jsonify({'success': False, 'message': 'UID должен содержать 8 символов'})
        
        if deals_count < 0:
            return jsonify({'success': False, 'message': 'Количество сделок не может быть отрицательным'})
        
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь с таким UID
        cursor.execute('SELECT telegram_id, username, first_name FROM users WHERE uid = ?', (uid,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': f'Пользователь с UID {uid} не найден'})
        
        telegram_id, username, first_name = user
        
        # Обновляем количество сделок
        cursor.execute('''
            UPDATE users SET successful_deals = ? WHERE uid = ?
        ''', (deals_count, uid))
        
        conn.commit()
        conn.close()
        
        user_info = f"{first_name} (@{username}) | ID: {telegram_id}"
        
        return jsonify({
            'success': True,
            'message': f'Количество сделок установлено: {deals_count} для {user_info}',
            'user_info': user_info,
            'deals_count': deals_count
        })
        
    except Exception as e:
        print(f"Ошибка обновления сделок: {e}")
        return jsonify({'success': False, 'message': f'Ошибка сервера: {str(e)}'})

# API для сброса баланса пользователя (админ)
@app.route('/api/admin/reset_balance', methods=['POST'])
def api_admin_reset_balance():
    try:
        data = request.get_json()
        telegram_id = data.get('telegram_id')
        
        if not telegram_id:
            return jsonify({'success': False, 'message': 'Не указан Telegram ID'})
        
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET balance_stars = 0, balance_rub = 0, successful_deals = 0 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Баланс и сделки сброшены'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Ошибка: {str(e)}'})

# Обработка ошибок
@app.errorhandler(404)
def not_found(error):
    return render_template('mini_app/index.html'), 200

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'Внутренняя ошибка сервера'}), 500

if __name__ == '__main__':
    init_mini_app_db()
    print("🚀 Запуск Mini App с UID системой и админ панелью...")
    print("📱 Mini App будет доступен по адресу: http://localhost:3000")
    print("🔧 Для остановки нажмите Ctrl+C")
    print("-" * 50)
    app.run(debug=True, host='0.0.0.0', port=3000)