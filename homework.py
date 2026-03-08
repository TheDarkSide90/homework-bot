import logging
import os
import requests
import sys
import time

from dotenv import load_dotenv
from telebot import TeleBot


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
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.critical('Отсутствуют обязательные переменные окружения')
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения при получение обновления."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение успешно отправлено: {message}')
    except Exception as error:
        logger.error(f'Не удалось отправить сообщение: {error}')


def get_api_answer(timestamp):
    """Получить ответ от API."""
    params = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise Exception(f'Ошибка, вернулся статус {response.status_code}')
        return response.json()
    except requests.RequestException as error:
        raise SystemError(f'Ошибка запроса к API: {error}')


def check_response(response):
    """Проверка ответа от API."""
    if not isinstance(response, dict):
        raise TypeError('API вернул не словарь')

    if 'homeworks' not in response:
        logger.error('В ответе API отсутствует ключ homeworks')
        raise KeyError('Отсутствует ключ homeworks')

    if 'current_date' not in response:
        logger.error('В ответе API отсутствует ключ current_date')
        raise KeyError('Отсутствует ключ current_date')

    if not isinstance(response['homeworks'], list):
        raise TypeError('homeworks не является списком')

    return response['homeworks']


def parse_status(homework):
    """Получение информации из ответа от API."""
    if 'homework_name' not in homework:
        logger.error('В ответе API отсутствует ключ homework_name')
        raise KeyError('Отсутствует ключ homework_name')

    if 'status' not in homework:
        logger.error('В ответе API отсутствует ключ status')
        raise KeyError('Отсутствует ключ status')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        logger.error(f'Получен неизвестный статус домашней работы: {status}')
        raise ValueError(f'Неизвестный статус {status}')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise SystemExit('Отсутствуют токены')

    bot = TeleBot(token=TELEGRAM_TOKEN)

    last_error_message = ''

    while True:
        try:
            timestamp = int(time.time()) - RETRY_PERIOD
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if not homeworks:
                logger.debug('В ответе API нет новых статусов')
            else:
                homework = homeworks[0]
                message = parse_status(homework)
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)

            if message != last_error_message:
                send_message(bot, message)
                last_error_message = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
