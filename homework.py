import os
import sys
import time
import logging
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('YA_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TG_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
handler.setFormatter(formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)


def check_tokens():
    """Проверяет наличие важных переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = [name for name, value in tokens.items() if not value]
    if missing_tokens:
        for token in missing_tokens:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: "{token}"'
            )
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение: "{message}"')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API Практикум.Домашка и возвращает ответ."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise Exception(
                f'Эндпоинт {ENDPOINT} недоступен.'
                f'Код ответа API: {response.status_code}'
            )
        return response.json()
    except requests.RequestException as error:
        raise Exception(f'Ошибка запроса к API: {error}')


def check_response(response):
    """Проверяет структуру ответа."""
    logger.debug('Проверка структуры ответа.')
    if not isinstance(response, dict):
        raise TypeError('Ответ не является словарём.')
    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError('В ответе API отсутствуют необходимые ключи.')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ключ "homeworks" не является списком.')
    logger.debug('Структура ответа валидна.')


def parse_status(homework):
    """Извлекает статус домашней работы и возвращает сообщение."""
    logger.debug('Парсинг статуса домашней работы.')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в домашке.')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в домашке.')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неопределенный статус: {status}.')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]
    logger.debug(f'Распознан статус: {status}.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(
            'Программа остановлена из-за отсутствия переменных окружения.'
        )
        sys.exit(1)

    logger.info('Бот запущен!')
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int((datetime.now() - timedelta(days=30)).timestamp())
    last_status = None
    last_error = None

    while True:
        try:
            logger.debug('Начало нового цикла запроса API.')
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks', [])

            if homeworks:
                homework = homeworks[0]
                current_status = homework.get('status')
                if current_status != last_status:
                    message = parse_status(homework)
                    send_message(bot, message)
                    last_status = current_status
                    logger.info(
                        f'Обнаружено изменение статуса: {current_status}.'
                    )
                else:
                    logger.debug('Новых статусов нет.')
            else:
                logger.debug('Список домашних работ пуст.')

            timestamp = response.get('current_date', timestamp)
            logger.debug(f'Обновлена временная метка: {timestamp}.')
            last_error = None

        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logger.error(error_message)
            if str(error) != last_error:
                send_message(bot, error_message)
                last_error = str(error)

        finally:
            logger.debug(f'Ожидаем {RETRY_PERIOD // 60} минут.')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
