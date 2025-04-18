import requests
from bs4 import BeautifulSoup
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
PLANNING_URL = "https://cloud.toplubricants.ru/s/yWSpybsLPZkjjzp"  # Замените на URL веб-страницы
BOT_TOKEN = "7738985245:AAEtSoP8Jc8vRuNEZd5RJQpJ-0NCMaW7Xys"
LOG_CHAT_ID = -1002017911073  # ID чата для отправки изменений планинга

# Глобальная переменная для хранения предыдущего состояния
previous_state = {}

def parse_planning():
    """Парсит данные из HTML-страницы."""
    try:
        response = requests.get(PLANNING_URL)
        if response.status_code != 200:
            logging.error(f"Ошибка при получении данных: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')  # Находим таблицу на странице
        if not table:
            logging.error("Таблица не найдена на странице.")
            return None

        data = []
        rows = table.find_all('tr')
        for row in rows[START_ROW:]:  # Начинаем с указанной строки
            cols = row.find_all('td')
            if len(cols) < 13:  # Проверяем, что строка содержит нужные столбцы
                continue
            date_value = cols[0].text.strip()  # Столбец A (дата)
            vehicle_info = cols[8].text.strip()  # Столбец I (Марка, номер а/м)
            order_number = cols[11].text.strip()  # Столбец L (Номер РР)
            driver_info = cols[12].text.strip()  # Столбец M (ФИО водителя)
            data.append({
                'A': date_value,
                'I': vehicle_info,
                'L': order_number,
                'M': driver_info
            })
        return data
    except Exception as e:
        logging.error(f"Ошибка при парсинге данных: {e}")
        return None

def compare_states(previous, current):
    """Сравнивает предыдущее и текущее состояние планинга."""
    changes = []
    for key, new_values in current.items():
        if key not in previous:
            # Это новая строка
            if new_values['L']:
                changes.append(f"Новый заказ №{new_values['L']} на дату {new_values['A']}")
        elif previous[key] != new_values:
            old_values = previous[key]
            change_message = f"Изменение в заказе №{new_values['L']} на дату {new_values['A']}: "
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
        # Парсим текущие данные
        current_data = parse_planning()
        if not current_data:
            return

        # Преобразуем данные в словарь для сравнения
        current_state = {f"row_{i}": data for i, data in enumerate(current_data)}

        # Сравниваем состояния
        changes = compare_states(previous_state, current_state)
        if changes:
            for change in changes:
                context.bot.send_message(chat_id=LOG_CHAT_ID, text=change)

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
