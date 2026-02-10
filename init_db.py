#!/usr/bin/env python3
"""
Инициализация базы данных на Render
"""

import sqlite3
import os
import random
import string

def init_database():
    """Создает базу данных с UID системой"""
    try:
        os.makedirs('data', exist_ok=True)
        
        conn = sqlite3.connect('data/unified.db')
        cursor = conn.cursor()
        
        # Создаем таблицу пользователей с UID
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT UNIQUE NOT NULL,
                telegram_id TEXT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                phone TEXT,
                balance_stars INTEGER DEFAULT 0,
                balance_rub REAL DEFAULT 0,
                balance_uah REAL DEFAULT 0,
                successful_deals INTEGER DEFAULT 0,
                verified BOOLEAN DEFAULT FALSE,
                session_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Создаем таблицу сделок
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id TEXT PRIMARY KEY,
                seller_id TEXT NOT NULL,
                buyer_id TEXT,
                nft_link TEXT,
                nft_username TEXT,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                paid_at TIMESTAMP,
                description TEXT,
                FOREIGN KEY (seller_id) REFERENCES users (telegram_id),
                FOREIGN KEY (buyer_id) REFERENCES users (telegram_id)
            )
        """)
        
        # Создаем индексы
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_uid ON users(uid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_deals_seller_id ON deals(seller_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_deals_buyer_id ON deals(buyer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status)')
        
        conn.commit()
        conn.close()
        
        print("✅ База данных инициализирована успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Инициализация базы данных...")
    init_database()
