#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import random
import requests
import telebot
import threading
import logging
from flask import Flask
from datetime import datetime, timedelta, timezone

# Логирование для отладки в панели Amvera
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "Weather Bot is Running"

def run_flask():
    # ИСПРАВЛЕНО: Amvera ожидает порт 80
    app.run(host='0.0.0.0', port=80)

# Инициализация бота
bot = telebot.TeleBot(os.environ.get('TELEGRAM_TOKEN', ''))

WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY', '')
UNSPLASH_ACCESS_KEY = os.environ.get('UNSPLASH_ACCESS_KEY', '')

# Координаты 3 районов Братска
LOCATIONS = {
    "Центральный район": {"lat": 56.13, "lon": 101.63},
    "Район Энергетик": {"lat": 56.31, "lon": 101.77},
    "Район Гидростроитель": {"lat": 56.45, "lon": 101.74}
}

def get_season():
    """Определить сезон для поиска фото"""
    month = datetime.now().month
    if month in [12, 1, 2]:
        return "winter"
    elif month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    else:
        return "autumn"

def get_background_url():
    """Получить случайное фото Сибири с Unsplash (ОПТИМИЗИРОВАННОЕ)"""
    season = get_season()
    
    # Разнообразные темы для поиска
    queries = [
        f"Siberia {season} nature",
        f"Siberian city landscape {season}",
        f"Lake Baikal {season}",
        "Russian winter landscape",
        "Siberian taiga forest"
    ]
    
    query = random.choice(queries)
    
    try:
        # 1. Запрос к API с уникальным sig для Unsplash
        api_url = f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape&client_id={UNSPLASH_ACCESS_KEY}&sig={random.getrandbits(32)}"
        res = requests.get(api_url, timeout=5).json()
        
        if isinstance(res, dict) and 'urls' in res:
            img_url = res['urls']['regular']
            # 2. ОПТИМИЗАЦИЯ: w=600 (ширина), q=75 (качество)
            # Вес: 40-50 КБ вместо 100+ КБ
            return f"{img_url}&w=600&q=75&t={random.getrandbits(32)}"
        else:
            logger.warning(f"Unsplash API вернул ошибку или лимит исчерпан: {res}")
    except Exception as e:
        logger.error(f"Ошибка получения фото: {e}")
    
    # Резервная картинка (если API не отвечает)
    return f"https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=600&q=75&refresh={random.randint(1,999)}"

def get_icon(weather_main):
    """Выбрать эмодзи для типа погоды"""
    icons = {
        "Clear": "☀️",
        "Clouds": "☁️",
        "Rain": "🌧",
        "Snow": "❄️",
        "Drizzle": "🌦",
        "Thunderstorm": "⛈",
        "Mist": "🌫",
        "Smoke": "💨"
    }
    return icons.get(weather_main, "🌡")

def get_aqi_info(aqi):
    """Описание качества воздуха"""
    data = {
        1: ("✅", "Чисто"),
        2: ("✅", "Норма"),
        3: ("🟨", "Умеренно"),
        4: ("🟧", "Смог"),
        5: ("🟥", "Опасно")
    }
    return data.get(aqi, ("⚪", "Нет данных"))

def get_district_report(name, coords):
    """Получить отчет о погоде для района"""
    try:
        # Текущая погода
        w_url = f"https://api.openweathermap.org/data/2.5/weather?lat={coords['lat']}&lon={coords['lon']}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        
        # Качество воздуха
        a_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={coords['lat']}&lon={coords['lon']}&appid={WEATHER_API_KEY}"
        
        # Прогноз
        f_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={coords['lat']}&lon={coords['lon']}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        
        w_res = requests.get(w_url, timeout=5).json()
        a_res = requests.get(a_url, timeout=5).json()
        f_res = requests.get(f_url, timeout=5).json()
        
        # Парсим основные параметры
        temp = round(w_res['main']['temp'])
        feels = round(w_res['main']['feels_like'])
        press = round(w_res['main']['pressure'] * 0.75006)  # в мм рт.ст.
        hum = w_res['main']['humidity']
        wind = round(w_res['wind']['speed'])
        desc = w_res['weather'][0]['description'].capitalize()
        icon = get_icon(w_res['weather'][0]['main'])
        
        # Восход/закат (в +8 timezone)
        sunrise = (datetime.fromtimestamp(w_res['sys']['sunrise'], tz=timezone.utc) + timedelta(hours=8)).strftime('%H:%M')
        sunset = (datetime.fromtimestamp(w_res['sys']['sunset'], tz=timezone.utc) + timedelta(hours=8)).strftime('%H:%M')
        
        # Качество воздуха
        aqi_icon, aqi_txt = get_aqi_info(a_res['list'][0]['main']['aqi'])
        
        # Тренд температуры
        trend = ""
        future_temp = round(f_res['list'][2]['main']['temp'])
        if future_temp - temp > 2:
            trend = "\n📈 Ожидается потепление"
        elif future_temp - temp < -2:
            trend = "\n📉 Станет холоднее"
        
        # Формируем отчет
        report = f"🏙 **{name.upper()}**\n"
        report += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        report += f"{icon} **{temp:+d}°C** (ощущается как {feels:+d}°C)\n"
        report += f"💬 {desc}{trend}\n\n"
        report += f"💧 Влажность: {hum}% | 📉 {press} мм\n"
        report += f"💨 Ветер: {wind} м/с | 🏭 Воздух: {aqi_icon} {aqi_txt}\n"
        report += f"🌅 {sunrise} — 🌇 {sunset}\n"
        
        return report
        
    except Exception as e:
        logger.error(f"Ошибка получения данных для {name}: {e}")
        return f"🏙 **{name}**: ⚠️ Ошибка данных\n"

def get_bratsk_full_report():
    """Получить полный отчет по всем районам"""
    full_report = ""
    
    # Добавляем отчеты для каждого района
    for name, coords in LOCATIONS.items():
        full_report += get_district_report(name, coords)
        full_report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    
    # Добавляем прогноз на 5 дней
    try:
        f_res = requests.get(
            f"https://api.openweathermap.org/data/2.5/forecast?lat=56.13&lon=101.63&appid={WEATHER_API_KEY}&units=metric&lang=ru",
            timeout=5
        ).json()
        
        days_found = []
        forecast_text = "📅 **ПРОГНОЗ НА 5 ДНЕЙ:**\n"
        today_str = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%d.%m')
        weekdays = {0: "ПН", 1: "ВТ", 2: "СР", 3: "ЧТ", 4: "ПТ", 5: "СБ", 6: "ВС"}
        
        for entry in f_res['list']:
            dt_local = datetime.fromtimestamp(entry['dt'], tz=timezone.utc) + timedelta(hours=8)
            date_str = dt_local.strftime('%d.%m')
            
            # Берем прогноз после 11:00 для каждого дня
            if date_str not in days_found and date_str != today_str and dt_local.hour >= 11:
                f_temp = round(entry['main']['temp'])
                f_icon = get_icon(entry['weather'][0]['main'])
                day_name = weekdays[dt_local.weekday()]
                forecast_text += f"▪️ {date_str} ({day_name}): {f_temp:+d}°C {f_icon}\n"
                days_found.append(date_str)
                
                if len(days_found) >= 5:
                    break
        
        full_report += forecast_text
        
    except Exception as e:
        logger.error(f"Ошибка получения прогноза: {e}")
    
    return full_report

@bot.message_handler(commands=['start', 'weather'])
def send_weather(message):
    """Обработчик команд /start и /weather"""
    bot.send_chat_action(message.chat.id, 'upload_photo')
    
    # Кнопка обновления
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🔄 Обновить прогноз", callback_data="upd_bratsk"))
    
    # Формируем и отправляем
    time_str = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%H:%M')
    report = f"🕒 Обновлено: {time_str}\n\n" + get_bratsk_full_report()
    
    bot.send_photo(
        message.chat.id,
        get_background_url(),
        caption=report,
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "upd_bratsk")
def callback_upd(call):
    """Обработчик кнопки обновления"""
    # Мгновенный ответ кнопке
    bot.answer_callback_query(call.id, "Обновляю...")
    
    try:
        time_str = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%H:%M')
        report = f"🕒 Обновлено: {time_str}\n\n" + get_bratsk_full_report()
        
        # Обновляем фото и текст
        bot.edit_message_media(
            media=telebot.types.InputMediaPhoto(
                get_background_url(),
                caption=report,
                parse_mode='Markdown'
            ),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=call.message.reply_markup
        )
    except Exception as e:
        logger.error(f"Ошибка обновления: {e}")

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("Bot is running on port 80")
    
    # Запускаем бота
    bot.infinity_polling()
