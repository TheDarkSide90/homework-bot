from http import HTTPStatus
import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
from telebot import TeleBot

import exceptions

load_dotenv()

formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)

stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)

PRACTICUM_TOKEN = os.getenv('TOKEN_PRACTICUM')
TELEGRAM_TOKEN = os.getenv('TOKEN_TELEGRAM')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID_TELEGRAM')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Возвращает True если есть токены, возвращает False если нет токенов."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }

    missing_tokens = []

    for name, value in tokens.items():
        if not value:
            missing_tokens.append(name)

    return missing_tokens


def send_message(bot, message):
    """Отправка сообщения при получение обновления."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение успешно отправлено: %s', message)
    except Exception as error:
        logger.error('Не удалось отправить сообщение: %s', error)


def get_api_answer(timestamp):
    """Получить ответ от API."""
    params = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise exceptions.WrongAPIResponseError(
                f'Ошибка, вернулся статус {response.status_code}'
            )
        return response.json()
    except requests.RequestException as error:
        raise exceptions.APIResponseError(f'Ошибка запроса к API: {error}')


def check_response(response):
    """Проверка ответа от API."""
    if not isinstance(response, dict):
        raise TypeError('API вернул не словарь')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks')

    if 'current_date' not in response:
        raise KeyError('Отсутствует ключ current_date')

    if not isinstance(response['homeworks'], list):
        raise TypeError('homeworks не является списком')

    return response['homeworks']


def parse_status(homework):
    """Получение информации из ответа от API."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ homework_name')

    if 'status' not in homework:
        raise KeyError('Отсутствует ключ status')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус {status}')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    missing_tokens = check_tokens()

    if missing_tokens:
        logger.critical(
            'Отсутствуют обязательные переменные окружения: %s', missing_tokens
        )
        raise SystemExit('Отсутствуют обязательные переменные окружения')

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    last_error_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if not homeworks:
                logger.debug('В ответе API нет новых статусов')
            else:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)
                timestamp = int(time.time())
        except Exception as error:
            logger.error('Сбой в работе программы: %s', error)

            if message != last_error_message:
                send_message(bot, message)
                last_error_message = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
