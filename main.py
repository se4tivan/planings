import os
import time
import logging
import pandas as pd
import requests
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)

# Константы
PLANNING_URL = "https://cloud.toplubricants.ru/s/yWSpybsLPZkjjzp"
BOT_TOKEN = "7738985245:AAEtSoP8Jc8vRuNEZd5RJQpJ-0NCMaW7Xys"
START_ROW = 787  # Начинаем с 787 строки
MONITOR_COLUMNS = ['I', 'L', 'M']
WORK_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
WORK_HOURS = (8, 18)
GROUP_CHAT_ID = -1002017911073  # ID группы для отправки изменений

# Глобальная переменная для хранения состояния планинга
previous_state = {}

def is_working_time():
    """Проверяет, является ли текущее время рабочим."""
    now = datetime.now()
    current_day = now.strftime("%A")
    current_hour = now.hour
    if current_day not in WORK_DAYS or current_hour < WORK_HOURS[0] or current_hour >= WORK_HOURS[1]:
        return False
    return True

def download_planning():
    """Скачивает файл планинга и сохраняет его локально."""
    try:
        response = requests.get(PLANNING_URL)
        if response.status_code == 200:
            with open("planning.xlsx", "wb") as file:
                file.write(response.content)
            logging.info("Планинг успешно скачан.")
        else:
            logging.error(f"Ошибка при скачивании планинга: {response.status_code}")
    except Exception as e:
        logging.error(f"Ошибка при скачивании планинга: {e}")

def read_planning():
    """Читает данные из файла планинга."""
    try:
        df = pd.read_excel("planning.xlsx", sheet_name=0, header=None)
        return df
    except Exception as e:
        logging.error(f"Ошибка при чтении планинга: {e}")
        return None

def get_current_state(df):
    """Получает текущее состояние мониторинговых столбцов."""
    current_state = {}
    for row in range(START_ROW, len(df)):
        key = f"row_{row}"
        date_value = df.iloc[row, 0]  # Столбец A (дата)
        values = {
            'A': pd.to_datetime(date_value).strftime("%y/%m/%d") if pd.notna(date_value) else None,  # Дата
            'L': str(df.iloc[row, 11]).strip() if pd.notna(df.iloc[row, 11]) else None,  # Номер РР
        }
        current_state[key] = values
    return current_state

def compare_states(previous, current):
    """Сравнивает предыдущее и текущее состояние планинга."""
    changes = []
    for key in current:
        if key not in previous:
            # Это новая строка
            order_date = current[key]['A']
            order_number = current[key]['L']
            if order_number:
                changes.append(f"Новый заказ на дату {order_date}: №{order_number}")
        elif previous[key] != current[key]:
            old_values = previous[key]
            new_values = current[key]
            order_date = new_values['A']
            order_number = new_values['L']

            change_message = f"Изменение заказа на дату {order_date}: "
            if old_values['L'] != new_values['L']:
                change_message += f"{old_values['L']} -> {new_values['L']}; "
            changes.append(change_message.strip())
    return changes

def monitor_planning(context: CallbackContext):
    """Основная функция мониторинга планинга."""
    global previous_state
    try:
        # Скачиваем и читаем планинг
        download_planning()
        df = read_planning()
        if df is None:
            return

        # Получаем текущее состояние
        current_state = get_current_state(df)

        # Сравниваем состояния
        changes = compare_states(previous_state, current_state)
        if changes:
            for change in changes:
                context.bot.send_message(chat_id=GROUP_CHAT_ID, text=change)

        # Обновляем предыдущее состояние
        previous_state = current_state
    except Exception as e:
        logging.error(f"Ошибка при мониторинге планинга: {e}")

def start_monitoring(update: Update, context: CallbackContext):
    """Команда для запуска мониторинга."""
    chat_id = update.message.chat_id
    context.job_queue.run_repeating(
        monitor_planning,
        interval=600,  # Каждые 10 минут
        first=0,
        context=chat_id,
        name=str(chat_id)
    )
    update.message.reply_text("Мониторинг планинга запущен.")

def stop_monitoring(update: Update, context: CallbackContext):
    """Команда для остановки мониторинга."""
    chat_id = update.message.chat_id
    job = context.job_queue.get_jobs_by_name(str(chat_id))
    if job:
        for j in job:
            j.schedule_removal()
        update.message.reply_text("Мониторинг планинга остановлен.")
    else:
        update.message.reply_text("Мониторинг не был запущен.")

def handle_message(update: Update, context: CallbackContext):
    """Обрабатывает любые текстовые сообщения."""
    if is_working_time():
        update.message.reply_text("Ведется активный мониторинг планинга.")
    else:
        update.message.reply_text("Мониторинг планинга не ведется.")

def show_today_orders(update: Update, context: CallbackContext):
    """Показывает заказы на сегодняшний день."""
    try:
        download_planning()
        df = read_planning()
        if df is None:
            update.message.reply_text("Не удалось получить данные о заказах.")
            return

        today = datetime.now().strftime("%y/%m/%d")
        orders = []
        for row in range(START_ROW, len(df)):
            date_value = df.iloc[row, 0]
            order_number = df.iloc[row, 11]
            if pd.notna(date_value) and pd.to_datetime(date_value).strftime("%y/%m/%d") == today and pd.notna(order_number):
                orders.append(f"{today} - Номер РР {str(order_number).strip()}")

        if orders:
            update.message.reply_text("\n".join(orders), reply_markup=ReplyKeyboardRemove())
        else:
            update.message.reply_text("На сегодня заказов нет.", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        logging.error(f"Ошибка при получении заказов на сегодня: {e}")
        update.message.reply_text("Произошла ошибка при получении заказов.")

def main():
    """Основная функция."""
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Регистрация команд
    dispatcher.add_handler(CommandHandler("start_monitoring", start_monitoring))
    dispatcher.add_handler(CommandHandler("stop_monitoring", stop_monitoring))

    # Обработка текстовых сообщений
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Кнопка "Сегодня"
    def button_handler(update: Update, context: CallbackContext):
        query = update.callback_query
        if query.data == "today":
            show_today_orders(update, context)

    dispatcher.add_handler(CallbackQueryHandler(button_handler))

    # Команда для показа кнопки "Сегодня"
    def show_today_button(update: Update, context: CallbackContext):
        keyboard = [[{"text": "Сегодня", "callback_data": "today"}]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        update.message.reply_text("Нажмите кнопку 'Сегодня', чтобы увидеть заказы на сегодня:", reply_markup=reply_markup)

    dispatcher.add_handler(CommandHandler("today", show_today_button))

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
