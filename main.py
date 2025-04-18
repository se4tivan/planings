import os
import logging
import pandas as pd
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

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
LOG_CHAT_ID = -1002017911073  # ID чата для отправки данных

def download_planning():
    """Скачивает файл планинга и сохраняет его локально."""
    try:
        response = requests.get(PLANNING_URL)
        if response.status_code == 200:
            with open("planning.xlsx", "wb") as file:
                file.write(response.content)
            logging.info("Планинг успешно скачан.")
            return True
        else:
            logging.error(f"Ошибка при скачивании планинга: {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"Ошибка при скачивании планинга: {e}")
        return False

def read_planning():
    """Читает данные из файла планинга."""
    try:
        if not os.path.exists("planning.xlsx"):
            logging.error("Файл планинга не найден.")
            return None

        df = pd.read_excel("planning.xlsx", sheet_name=0, header=None)
        logging.info("Планинг успешно прочитан.")
        return df
    except Exception as e:
        logging.error(f"Ошибка при чтении планинга: {e}")
        return None

def parse_planning(df):
    """Парсит данные из планинга."""
    parsed_data = []
    for row in range(START_ROW, len(df)):
        date_value = pd.to_datetime(df.iloc[row, 0]).strftime("%y/%m/%d") if pd.notna(df.iloc[row, 0]) else None  # Дата
        vehicle_info = str(df.iloc[row, 8]).strip() if pd.notna(df.iloc[row, 8]) else None  # Марка, номер а/м
        order_number = str(df.iloc[row, 11]).strip() if pd.notna(df.iloc[row, 11]) else None  # Номер РР
        driver_info = str(df.iloc[row, 12]).strip() if pd.notna(df.iloc[row, 12]) else None  # ФИО водителя

        if order_number:
            parsed_data.append({
                'date': date_value,
                'vehicle': vehicle_info,
                'order': order_number,
                'driver': driver_info
            })
    return parsed_data

def send_parsed_data(context: CallbackContext):
    """Скачивает, парсит и отправляет данные из планинга в чат."""
    if not download_planning():
        context.bot.send_message(chat_id=LOG_CHAT_ID, text="Не удалось скачать файл планинга.")
        return

    df = read_planning()
    if df is None:
        context.bot.send_message(chat_id=LOG_CHAT_ID, text="Не удалось получить данные из планинга.")
        return

    parsed_data = parse_planning(df)
    if not parsed_data:
        context.bot.send_message(chat_id=LOG_CHAT_ID, text="Нет новых данных в планинге.")
        return

    message = "Данные из планинга:\n"
    for entry in parsed_data:
        message += (
            f"Дата: {entry['date']}, "
            f"Номер РР: {entry['order']}, "
            f"Марка/номер а/м: {entry['vehicle']}, "
            f"ФИО водителя: {entry['driver']}\n"
        )
    context.bot.send_message(chat_id=LOG_CHAT_ID, text=message)

def handle_message(update: Update, context: CallbackContext):
    """Обрабатывает любые текстовые сообщения."""
    user_message = update.message.text.lower()
    chat_id = update.message.chat_id

    if user_message == "сегодня":
        # Отправляем список заказов за сегодня
        if not download_planning():
            update.message.reply_text("Не удалось скачать файл планинга.")
            return

        df = read_planning()
        if df is None:
            update.message.reply_text("Не удалось получить данные из планинга.")
            return

        today_date = datetime.now().strftime("%y/%m/%d")
        parsed_data = parse_planning(df)
        orders_today = [
            f"{entry['date']} - Номер РР №{entry['order']}"
            for entry in parsed_data
            if entry['date'] == today_date
        ]

        if orders_today:
            update.message.reply_text("\n".join(orders_today))
        else:
            update.message.reply_text(f"За сегодня ({today_date}) заказов нет.")
    else:
        update.message.reply_text("Введите 'Сегодня', чтобы получить заказы за текущую дату.")

def main():
    """Основная функция."""
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Регистрация обработчиков
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
