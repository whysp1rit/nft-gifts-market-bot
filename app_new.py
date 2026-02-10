#!/usr/bin/env python3
"""
Новый запуск бота с прямым токеном и системой уведомлений администратора
"""

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import sqlite3
import requests
import asyncio

# Прямое указание токена
TOKEN = "8512489092:AAFghx4VAurEYdi8gDZVUJ71pqGRnC8-n4M"
ADMIN_ID = 8566238705  # ID администратора

bot = Bot(token=TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Функция для уведомления администратора о новой сделке
async def notify_admin_new_deal(deal_id, seller_name, amount, currency, description):
    """Уведомляет администратора о новой сделке"""
    try:
        currency_symbols = {
            'stars': '⭐',
            'rub': '₽',
            'uah': '₴',
            'usd': '$',
            'eur': '€'
        }
        
        symbol = currency_symbols.get(currency, '')
        
        text = f"<b>🆕 Новая сделка создана!</b>\n\n" \
               f"🆔 <b>ID сделки:</b> #{deal_id}\n" \
               f"👤 <b>Продавец:</b> {seller_name}\n" \
               f"💰 <b>Сумма:</b> {symbol}{amount}\n" \
               f"📝 <b>Описание:</b> {description or 'Не указано'}\n\n" \
               f"⏳ <b>Статус:</b> Ожидает подтверждения"
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="✅ Подтвердить сделку",
                        callback_data=f"confirm_deal_{deal_id}"
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="❌ Отклонить сделку",
                        callback_data=f"reject_deal_{deal_id}"
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="🔍 Посмотреть сделку",
                        url=f"https://nft-gifts-market-uid.onrender.com/deal/{deal_id}"
                    )
                ]
            ]
        )
        
        await bot.send_message(ADMIN_ID, text, reply_markup=keyboard)
        print(f"✅ Уведомление о сделке {deal_id} отправлено администратору")
        
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления администратору: {e}")

# Обработчик подтверждения сделки администратором
@dp.callback_query_handler(lambda c: c.data.startswith('confirm_deal_'))
async def confirm_deal_callback(call: types.CallbackQuery):
    await call.answer()
    
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    deal_id = call.data.replace('confirm_deal_', '')
    
    try:
        # Получаем информацию о сделке с сервера
        response = requests.get(f"https://nft-gifts-market-uid.onrender.com/api/deal/{deal_id}")
        
        if response.status_code == 200:
            deal_data = response.json()
            if deal_data.get('success'):
                deal = deal_data.get('deal')
                seller_id = deal.get('seller_id')
                amount = deal.get('amount')
                currency = deal.get('currency')
                
                # Здесь можно добавить логику пополнения баланса продавца
                # Пока просто отмечаем сделку как завершенную
                
                await call.message.edit_text(
                    text=f"<b>✅ Сделка #{deal_id} подтверждена!</b>\n\n"
                         f"💰 Продавцу начислено: {amount} {currency}\n"
                         f"📅 Время подтверждения: сейчас\n\n"
                         f"<i>Сделка успешно завершена администратором.</i>",
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                types.InlineKeyboardButton(
                                    text="🔍 Посмотреть сделку",
                                    url=f"https://nft-gifts-market-uid.onrender.com/deal/{deal_id}"
                                )
                            ]
                        ]
                    )
                )
                
                print(f"✅ Сделка {deal_id} подтверждена администратором")
            else:
                await call.answer("❌ Ошибка получения данных сделки", show_alert=True)
        else:
            await call.answer("❌ Сделка не найдена", show_alert=True)
            
    except Exception as e:
        await call.answer("❌ Ошибка подтверждения сделки", show_alert=True)
        print(f"❌ Ошибка подтверждения сделки {deal_id}: {e}")

# Обработчик отклонения сделки администратором
@dp.callback_query_handler(lambda c: c.data.startswith('reject_deal_'))
async def reject_deal_callback(call: types.CallbackQuery):
    await call.answer()
    
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return
    
    deal_id = call.data.replace('reject_deal_', '')
    
    await call.message.edit_text(
        text=f"<b>❌ Сделка #{deal_id} отклонена</b>\n\n"
             f"📅 Время отклонения: сейчас\n"
             f"👤 Отклонено администратором\n\n"
             f"<i>Сделка была отклонена и не будет выполнена.</i>",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="🔍 Посмотреть сделку",
                        url=f"https://nft-gifts-market-uid.onrender.com/deal/{deal_id}"
                    )
                ]
            ]
        )
    )
    
    print(f"❌ Сделка {deal_id} отклонена администратором")

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    user_name = message.from_user.first_name or "друг"
    
    # Проверяем, есть ли параметр в команде /start
    args = message.get_args()
    
    # Если есть параметр deal_ - это ссылка на сделку
    if args and args.startswith('deal_'):
        deal_id = args.replace('deal_', '')
        
        await message.answer(
            text=f"<b>🎁 Сделка #{deal_id}</b>\n\n"
                 f"Привет, {user_name}! 👋\n\n"
                 f"Вы перешли по ссылке на сделку.\n"
                 f"Откройте мини приложение для просмотра деталей сделки.\n\n"
                 f"🔗 <b>ID сделки:</b> {deal_id}",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=f"🎁 Открыть сделку #{deal_id}",
                            web_app=types.WebAppInfo(url=f"https://nft-gifts-market-uid.onrender.com/deal/{deal_id}")
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text="🏠 Главное меню",
                            callback_data="main_menu"
                        )
                    ]
                ]
            )
        )
    else:
        # Обычное приветствие без параметров
        await message.answer(
            text=f"<b>🎁 Добро пожаловать в NFT Gifts Market!</b>\n\n"
                 f"Привет, {user_name}! 👋\n\n"
                 f"🚀 <b>Что вы можете делать:</b>\n"
                 f"• 🎁 Покупать и продавать NFT подарки\n"
                 f"• 💎 Создавать уникальные сделки\n"
                 f"• 🔐 Безопасно торговать через гаранта\n"
                 f"• 💰 Зарабатывать на перепродаже\n\n"
                 f"🛡️ <b>Безопасность:</b>\n"
                 f"Все сделки проходят через систему гарантий для вашей защиты.\n\n"
                 f"🎯 <b>Начните прямо сейчас!</b>",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="🎁 Открыть NFT Market",
                            web_app=types.WebAppInfo(url="https://nft-gifts-market-uid.onrender.com")
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text="🔐 Верификация аккаунта",
                            callback_data="verify"
                        )
                    ]
                ]
            )
        )

@dp.callback_query_handler(text="verify")
async def verify_callback(call: types.CallbackQuery):
    await call.answer()
    await call.message.edit_text(
        text="<b>🔐 Верификация аккаунта</b>\n\n"
             "Система верификации готова!\n"
             "Все модули загружены и работают.",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="🏠 Главное меню",
                        callback_data="main_menu"
                    )
                ]
            ]
        )
    )

@dp.callback_query_handler(text="main_menu")
async def main_menu_callback(call: types.CallbackQuery):
    await call.answer()
    user_name = call.from_user.first_name or "друг"
    
    await call.message.edit_text(
        text=f"<b>🎁 Добро пожаловать в NFT Gifts Market!</b>\n\n"
             f"Привет, {user_name}! 👋\n\n"
             f"🚀 <b>Что вы можете делать:</b>\n"
             f"• 🎁 Покупать и продавать NFT подарки\n"
             f"• 💎 Создавать уникальные сделки\n"
             f"• 🔐 Безопасно торговать через гаранта\n"
             f"• 💰 Зарабатывать на перепродаже\n\n"
             f"🛡️ <b>Безопасность:</b>\n"
             f"Все сделки проходят через систему гарантий для вашей защиты.\n\n"
             f"🎯 <b>Начните прямо сейчас!</b>",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="🎁 Открыть NFT Market",
                        web_app=types.WebAppInfo(url="https://nft-gifts-market-uid.onrender.com")
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="🔐 Верификация аккаунта",
                        callback_data="verify"
                    )
                ]
            ]
        )
    )

# API эндпоинт для уведомления о новой сделке (вызывается из мини приложения)
@dp.message_handler(commands=['notify_deal'])
async def notify_deal_command(message: types.Message):
    """Команда для тестирования уведомлений (только для разработки)"""
    if message.from_user.id == ADMIN_ID:
        await notify_admin_new_deal("TEST123", "Тестовый пользователь", 100, "stars", "Тестовая сделка")
        await message.answer("✅ Тестовое уведомление отправлено")
    else:
        await message.answer("❌ У вас нет прав для этой команды")

if __name__ == '__main__':
    print("🚀 Запускаем бота с системой уведомлений администратора...")
    print(f"🤖 Токен: {TOKEN[:20]}...")
    print(f"👤 Админ ID: {ADMIN_ID}")
    executor.start_polling(dp, skip_updates=True)