import os
import time
import logging
import pandas as pd
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

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

def send_inactive_message(context: CallbackContext):
    """Отправляет сообщение о неактивности бота."""
    message = (
        "Бот сейчас не активен. "
        "Он вернется к работе в ближайший будний день в 8:00."
    )
    context.bot.send_message(chat_id=context.job.context, text=message)

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
            'A': pd.to_datetime(date_value).strftime("%Y-%m-%d") if pd.notna(date_value) else None,  # Дата
            'I': str(df.iloc[row, 8]).strip() if pd.notna(df.iloc[row, 8]) else None,  # Марка, номер а/м
            'L': str(df.iloc[row, 11]).strip() if pd.notna(df.iloc[row, 11]) else None,  # Номер РР
            'M': str(df.iloc[row, 12]).strip() if pd.notna(df.iloc[row, 12]) else None   # ФИО водителя
        }
        current_state[key] = values
    return current_state

def compare_states(previous, current):
    """Сравнивает предыдущее и текущее состояние планинга."""
    changes = []
    for key in current:
        if key not in previous:
            # Это новая строка
            order_number = current[key]['L']
            if order_number:
                changes.append(f"Новый заказ №{order_number} на дату {current[key]['A']}")
        elif previous[key] != current[key]:
            old_values = previous[key]
            new_values = current[key]
            order_number = new_values['L']

            # Проверяем, добавлен ли водитель
            if not old_values['M'] and new_values['M']:
                changes.append(f"На заказ №{order_number} добавили: {new_values['M']}")

            # Проверяем, добавлены ли данные о транспорте
            if not old_values['I'] and new_values['I']:
                changes.append(f"На заказ №{order_number} добавили: {new_values['I']}")

            # Проверяем другие изменения
            if old_values['I'] != new_values['I'] or old_values['M'] != new_values['M']:
                change_message = f"Изменение в заказе №{order_number} на дату {new_values['A']}: "
                if old_values['I'] != new_values['I']:
                    change_message += f"{old_values['I']} -> {new_values['I']}; "
                if old_values['M'] != new_values['M']:
                    change_message += f"{old_values['M']} -> {new_values['M']}; "
                changes.append(change_message.strip())
    return changes

def monitor_planning(context: CallbackContext):
    """Основная функция мониторинга планинга."""
    global previous_state
    try:
        if not is_working_time():
            send_inactive_message(context)
            return

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
                context.bot.send_message(chat_id=context.job.context, text=change)

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

def main():
    """Основная функция."""
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Регистрация команд
    dispatcher.add_handler(CommandHandler("start_monitoring", start_monitoring))
    dispatcher.add_handler(CommandHandler("stop_monitoring", stop_monitoring))

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
