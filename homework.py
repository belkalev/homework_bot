import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import EmptyList, EndpointException, ErrorResponse

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
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        logger.error('Ошибка отправки сообщения')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(
        ENDPOINT,
        headers=HEADERS,
        params=params
    )
    if homework_statuses.status_code != HTTPStatus.OK:
        raise EndpointException('Нет ответа')
    else:
        return homework_statuses.json()


def check_response(response):
    """Проверяем ответ API."""
    if len(response) == 0:
        logger.error('Нет ответа')
        raise ErrorResponse('Нет ответа')
    if not isinstance(response, dict):
        raise TypeError('Нет ответа в словаре')
    try:
        homeworks = response['homeworks']
    except KeyError as e:
        logger.error('Key Error', e)
    if not isinstance(homeworks, list):
        raise TypeError("homework нет в списке")
    if len(homeworks) == 0:
        raise EmptyList("Empty list")
    logger.debug('Есть ответ от homework')
    return homeworks


def parse_status(homework):
    """Извлекает инфу о конкретном ДЗ."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def main():
    """Основная логика работы бота."""
    if not check_response:
        logger.critical('Отсутствуют одна или несколько переменных окружения')
        raise Exception('Отсутствуют одна или несколько переменных окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    STATUS = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            message = parse_status(check_response(response))
            if message != STATUS:
                send_message(bot, message)
                STATUS = message
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
