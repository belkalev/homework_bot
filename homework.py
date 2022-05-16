import json
import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from telegram import TelegramError

from exceptions import SendMessageError

load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(asctime)s, %(levelname)s, %(funcName)s, %(message)s',
    filemode='w'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('my_log.log')
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(funcName)s, %(message)s'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение."""
    try:
        logger.info('Сообщение отправлено')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TelegramError as error:
        raise SendMessageError(f'Ошибка отправки сообщения: {error}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    logger.debug('Получение статуса')
    logger.info(HEADERS)
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException:
        raise ConnectionError(f'Ошибка соединения с {homework_statuses}')
    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        logger.error(f'Ошибка {status_code}')
        raise Exception(f'Ошибка {status_code}')
    try:
        return homework_statuses.json()
    except json.decoder.JSONDecodeError:
        logger.error('Ошибка ответа json')
        raise json.decoder.JSONDecodeError('Ошибка ответа json')


def check_response(response):
    """Проверяем ответ API."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип данных')
    if 'homeworks' not in response:
        raise ValueError('В запросе нет ключа homeworks')
    try:
        homeworks = response.get('homeworks')
    except KeyError:
        logger.error('Ошибка словаря по ключу homeworks')
        raise KeyError('Ошибка словаря по ключу homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Неверный тип данных')
    return homeworks


def parse_status(homework):
    """Извлекает инфу о конкретном ДЗ."""
    homework_name = homework['homework_name']
    status = homework['status']
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "homework_status" в ответе API')
    if status not in HOMEWORK_STATUSES:
        raise ValueError(f'Неизветный статус {status}')
    verdict = HOMEWORK_STATUSES[status]
    return (f'Изменился статус проверки работы "{homework_name}". {verdict}')


def check_tokens():
    """Проверяем доступность переменных окружения."""
    logger.debug('Проверяем токены')
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    else:
        logger.error('Токены не работают')


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        raise ValueError('Ошибка токена')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
                current_timestamp = response.get(
                    'current_date', current_timestamp
                )

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            bot.send_message(bot, message)
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
