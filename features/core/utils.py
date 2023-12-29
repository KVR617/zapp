import os
import re
import logging
from functools import wraps
from pathlib import Path

import colorlog
import importlib
import random
import validators
import hmac
import base64
import hashlib
import time
import array
import inspect
import json
import string
import requests

from urllib.parse import urljoin

import xmltodict
from behave.reporter.summary import SummaryReporter
from behave.reporter.base import Reporter
from behave.runner import Context
from nested_lookup import nested_lookup
from typing import Mapping, Sequence, TypeVar, Optional, Type
from requests.structures import CaseInsensitiveDict
from selenium.common.exceptions import WebDriverException

from features.core import vault
from features.core import settings
from features.core.js_scripts import TEXT_SEARCH, GET_TEXT
from features.core.constants import STEP_HELP, EXCEPTIONS_TO_RETRY


T = TypeVar('T')
R = TypeVar('R', bound=Reporter)

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(settings.LOG_FORMAT))

log = colorlog.getLogger(__name__)
log.setLevel(logging.DEBUG) if settings.DEBUG else log.setLevel(logging.INFO)
log.addHandler(handler)


def import_locators(path: str = 'features/steps',
                    postfix: str = '_locators.py',
                    name: str = 'locators'):
    locators = {}
    for current_dir, _, files in os.walk(path):
        for file in files:
            if file.endswith(postfix):
                module_name = f'{current_dir}.{file.rstrip(".py")}'.replace('/', '.')
                module = importlib.import_module(module_name)
                imported_locators = getattr(module, name, None)

                if imported_locators and isinstance(imported_locators, Mapping):
                    overridden_keys = locators.keys() & imported_locators.keys()
                    locators.update(imported_locators)

                    if overridden_keys:
                        log.warning('Обнаружены пересечения в словарях локаторов, проверьте поля %s. Один из '
                                    'дубликатов в файле %s', overridden_keys, file)

    return locators


def telegram_bot_sendnotify(notify_name, bot_message):
    send_url = f'https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/sendMessage'
    response = requests.get(send_url, json={'chat_id': settings.TG_CHAT_ID,
                                            'text': '\n'.join((notify_name, bot_message))})
    log.debug(f'{response.content}')

    return response.status_code


def get_stand_url(stand):
    if stand.startswith(('http://', 'https://')):
        return validate_url(stand, 'Параметр TEST_STAND должен содержать валидный URL')

    prefix = '' if stand.lower() in ('prod', 'production', 'zapp') else f'-{stand}'
    return validate_url(
        settings.STAND_TEMPLATE.format(prefix),
        'Параметр STAND_TEMPLATE должен содержать валидный URL-шаблон'
    )


def validate_url(url, error_text):
    if validators.url(url):
        return url
    raise Exception(error_text)


def save_screenshot(context):
    try:
        directory_name = slugify(str(context.metrics_start_date))
        directory_path = os.path.abspath(os.path.join(settings.SCREENSHOT_DIR, directory_name))
        os.makedirs(directory_path, exist_ok=True)

        file_name = slugify(context.scenario.name) + '.png'
        file_path = os.path.join(directory_path, file_name)
        context.browser.get_screenshot_as_file(file_path)
        return file_path

    except WebDriverException:
        return ''


def get_vault_secrets():
    if not settings.VAULT_USE:
        log.debug(f'VAULT_USE: {settings.VAULT_USE}')
        return {}

    log.debug('VAULT_SECRET_STORAGE_TOKEN: %s', 'Set' if settings.VAULT_SECRET_STORAGE_TOKEN else 'Not set')
    log.debug('VAULT_SECRET_STORAGE_PATH: %s', settings.VAULT_SECRET_STORAGE_PATH)
    if settings.VAULT_SECRET_STORAGE_TOKEN and settings.VAULT_SECRET_STORAGE_PATH:
        secret_storage = None
        try:
            vault_connection = vault.VaultConnection(settings.VAULT_HOST, settings.VAULT_SECRET_STORAGE_TOKEN)
            secret_storage = vault_connection.get_storage(settings.VAULT_SECRET_STORAGE,
                                                          settings.VAULT_SECRET_STORAGE_VERSION)
        except vault.VaultTokenError as e:
            log.warning(f'Не удалось обновить Vault Token: {e}')
        except vault.VaultException as e:
            log.critical(f'Ошибка Vault: {e}')

        if secret_storage is None:
            return dict()
        else:
            return secret_storage.get_keys(settings.VAULT_SECRET_STORAGE_PATH)

    else:
        log.info('Хранилище Vault недоступно: пропускаем загрузку переменных из Vault')
        return dict()


def get_notifications_secrets():
    if not settings.VAULT_USE:
        log.debug(f'VAULT_USE: {settings.VAULT_USE}')
        return {}

    try:
        vault_connection = vault.VaultConnection(settings.VAULT_HOST, settings.VAULT_DB_TOKEN)
        db_storage = vault_connection.get_storage(settings.VAULT_DB_STORAGE, settings.VAULT_DB_STORAGE_VERSION)
        db_secrets = db_storage.get_keys(f'{settings.VAULT_DB_STORAGE_PATH}/{settings.ENV.lower()}/notifications_api')
        return db_secrets

    except vault.VaultException as e:
        log.critical(f'Ошибка Vault: {e}')
        return {}


def log_deprecated_steps(deprecated_steps):
    if deprecated_steps:
        with open('deprecated_steps.json', 'w') as output:
            json.dump(deprecated_steps, output)
    else:
        try:
            os.remove('deprecated_steps.json')
        except OSError:
            pass


def generate_tranzact_number():
    return random.randint(100000000, 9999999999)*10


def generate_phone_code():
    project_hash = int(hashlib.sha256(settings.PROJECT_KEY.encode('utf-8')).hexdigest(), 16)
    return '5' + str(project_hash)[-2:]


def strip_phone_number(number_text):
    phone = re.sub(r'(\+\s?7|[ ()\-])', "", number_text)
    return f'7{phone}' if len(phone) < 11 else phone


def format_delay(delay: str) -> float:
    return float(delay.replace(',', '.'))


def get_units_case_number(number: int) -> int:
    number = abs(number)
    number %= 100
    if 11 <= number <= 19:
        return 2
    tens = number % 10
    if tens == 1:
        return 0
    if 2 <= tens <= 4:
        return 1

    return 2


def get_units_case(number: int, cases: Sequence[T]) -> T:
    if len(cases) != 3:
        raise ValueError('case\'s length must be equal to 3: {}'.format(cases))

    case_index = get_units_case_number(number)
    return cases[case_index]


def get_element_value(context, element) -> str:
    """
    Функция возвращает значение элемента с учетом платформы
    :param context: контекст behave
    :param element: элемент для которого следует получить значение
    :return: значение элемента
    """

    if context.is_mobile and not context.is_webview:
        return element.get_attribute('text')

    return element.get_attribute('value')


def get_element_text_value(context, element) -> str:
    """
    Функция возвращает текстовое значение элемента с учетом платформы
    :param context: контекст behave
    :param element: элемент для которого следует получить текстовое значение
    :return: текстовое значение элемента
    """

    if context.is_mobile and not context.is_webview:
        return element.get_attribute('text')

    return context.browser.execute_script(GET_TEXT, element)


def get_element_text(context, elements, text):

    if context.is_mobile:
        for element in elements:
            if element.get_attribute('text') == text:
                return element
    else:
        return context.browser.execute_script(TEXT_SEARCH, elements, text)

    return False


def throw_deprecated_warn(context, example, new_func_name=None):
    func_name = inspect.stack()[1].function

    if context.current_step['filename'] == '<string>':
        for frame in inspect.stack():
            if frame.filename.endswith('_steps.py'):
                context.current_step['filename'] = frame.filename
                context.current_step['line'] = frame.lineno
                break

    hash_key = hash((func_name, context.current_step['filename'], context.current_step['line']))
    if hash_key not in context.metrics_deprecated_steps:
        context.metrics_deprecated_steps.update(
            {hash_key: dict(
                func_name=func_name,
                file=context.current_step['filename'],
                line=context.current_step['line'],
                old_step=context.current_step['name'],
                new_step=example
            )})

        log.warning(
            f"""ВЫ ИСПОЛЬЗУЕТЕ УСТАРЕВШИЙ ШАГ, КОТОРЫЙ МОЖЕТ БЫТЬ УДАЛЕН В СЛЕДУЮЩЕЙ ВЕРСИИ!
            Найдено в файле: {context.current_step['filename']} на {context.current_step['line']} строке
            Устаревший шаг: '{context.current_step['name']}'
            Замените на: '{example}'
            Подробнее: {STEP_HELP}{new_func_name or func_name.replace('_deprecated', '')}"""
        )


def doc(section):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            return function(*args, **kwargs)
        return wrapper
    return decorator


def truncate(hmac_sha1):
    offset = int(hmac_sha1[-1], 16)
    binary = int(hmac_sha1[(offset * 2):((offset * 2) + 8)], 16) & 0x7fffffff
    return str(binary)


def long_to_byte_array(long_num):
    byte_array = array.array('B')
    for _ in reversed(range(0, 8)):
        byte_array.insert(0, long_num & 0xff)
        long_num >>= 8
    return byte_array


def hotp(key, counter, digits=6):
    counter_bytes = long_to_byte_array(counter)
    hmac_sha1 = hmac.new(key=key, msg=counter_bytes, digestmod=hashlib.sha1).hexdigest()
    return truncate(hmac_sha1)[-digits:]


def totp(key, digits=6, window=30):
    key = base64.b32decode(key, True)
    counter = int(time.time() / window)
    return hotp(key, counter, digits=digits)


def get_last_downloaded_file(context):
    time_counter = 0
    while True:
        time.sleep(1)
        dirs = os.listdir(context.tempdir)

        if not dirs:
            return

        filename = max(
            [f for f in dirs if not f.startswith('.')],
            key=lambda xa: os.path.getctime(os.path.join(context.tempdir, xa))
        )
        if time_counter > context.smartwait_delay:
            raise Exception('Waited too long for file to download')
        time_counter += 1
        if not ('.part' or '.crdownload') in filename:
            break

    log.debug('FILENAME: %s', filename)
    downloaded_file_path = os.path.join(context.tempdir, filename)
    return downloaded_file_path


def get_md5_hash(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def escaping_exceptions(exception: Exception):
    if isinstance(exception, EXCEPTIONS_TO_RETRY):
        log.debug(f'Catching {exception.__class__.__name__}, retrying...')
        return True
    return False


def escaping_stale_elements(exception: Exception):
    log.warning('Пожалуйста, замените "escaping_stale_elements" на "escaping_exceptions" в файлах составных шагов')
    return escaping_exceptions(exception)


vault_variables = get_vault_secrets()
variables = CaseInsensitiveDict(**vault_variables, **os.environ)


def get_from_variables(name):
    value = get_field_by_chain(name, variables)

    if value is not None:
        log.debug(f'VARIABLES "{name}": {value}')
    else:
        log.error(f'Не найдено значение переменной "{name}"')

    return value


def get_field_by_chain(key_string, structure):
    if key_string is None or structure is None:
        return

    keys = re.split('[,.>]', key_string)
    while len(keys) > 0:
        key = keys.pop(0).strip()
        match = re.findall(r'\[(\d+)]', key)

        if match and isinstance(structure, Sequence):
            structure = structure[int(match[0])]

        elif isinstance(structure, Mapping):
            structure = structure.get(key)

        else:
            structure = None
            break

    return structure


def get_from_json(data, name):
    log.debug(f'JSON: {data}')

    match = re.findall('[,.>]', name)
    if match:
        result = get_field_by_chain(name, data)

    else:
        result = nested_lookup(name, data)
        log.debug(f'ALL VALUES FOUND BY KEY "{name}": {result}')
        result = result[0] if result else None

    log.debug(f'FOUND IN JSON: "{name}": {result}')

    return result


def get_absolute_url(link, stand_var=None, link_appendix_var=None):
    test_stand = get_from_variables(stand_var) if stand_var else get_from_variables('context_host')
    link_appendix = get_from_variables(link_appendix_var) if link_appendix_var is not None else ''
    return urljoin(test_stand, urljoin(link, str(link_appendix)))


def get_abs_file_path_from_cwd(relative_file_path):
    current_dir = os.getcwd()
    absolute_file_path = os.path.normpath(os.path.join(current_dir, relative_file_path))
    log.debug(f"Absolute path for '{relative_file_path}': '{absolute_file_path}'")
    return absolute_file_path


def set_canary_cookie(context):
    if settings.CANARY_COOKIE and isinstance(settings.CANARY_COOKIE, str):
        canary_cookie_name, canary_cookie_value = settings.CANARY_COOKIE.split('=')
        context.browser.add_cookie(cookie_dict={'name': canary_cookie_name, 'value': canary_cookie_value})
        log.info(f'Добавлена cookie для канареечного деплоя:'
                 f' name={canary_cookie_name}, value={canary_cookie_value} на {context.browser.current_url}')
        context.browser.refresh()


class Seed:
    run = None
    scenario = None

    @staticmethod
    def _generate(of):
        slug = ''.join([random.choice(string.ascii_lowercase) for _ in range(4)])
        project = settings.PROJECT_KEY.lower() + slug.capitalize()
        moment = str(time.time()) + slug[::-1]
        return of[0] + moment[:18].replace('.', project[0:5])

    def generate_run_seed(self):
        return self._generate('run')

    def generate_scenario_seed(self):
        return self._generate('scenario')


def generate_valid_snils() -> str:
    snils_number = str(random.randint(5001001999, 5999999999))[1:]
    control_sum = 0
    for index, digit in zip(range(9, 0, -1), snils_number):
        control_sum += index * int(digit)

    if control_sum > 101:
        control_sum %= 101

    snils_code = '{:02}'.format(control_sum) if control_sum < 100 else '00'
    return snils_number + snils_code


def clean_xml_reports(features_path=Path('./')):
    """Удаление всех локальных xml report"""
    try:
        path = Path(features_path, 'reports').glob('*.xml')
        for file in (f for f in path if f.is_file()):
            file.unlink(missing_ok=True)

    except FileNotFoundError:
        pass


def get_output_as_json(features_path=Path('./')) -> dict:
    output = {}
    try:
        p = Path(features_path, 'reports').glob('*.xml')
        files = [f for f in p if f.is_file()]
        for file in files:
            with open(Path(file)) as xml_file:
                output.update({str(file).rsplit('/', maxsplit=1)[-1]: xmltodict.parse(xml_file.read())})

    except FileNotFoundError:
        pass

    return output


def get_reporter(context: Context, cls: Type[R]) -> Optional[R]:
    """
    Возвращает reporter behave заданного класса

    :param context: контекст behave
    :param cls: класс репортера

    :returns Reporter или None, если заданный reporter не найден
    """

    return next((r for r in context.config.reporters if isinstance(r, cls)), None)


def get_run_status(context):
    """
        Возвращает признак успешно завершенного прогона или None в случае если прогон неуспешно запустился
    """
    summary_reporter = get_reporter(context, SummaryReporter)
    if summary_reporter:
        if summary_reporter.scenario_summary['failed'] == 0 and \
                summary_reporter.scenario_summary['passed'] > 0:
            return True
        if summary_reporter.scenario_summary['failed'] > 0:
            return False
        if summary_reporter.scenario_summary['failed'] == 0 and \
                summary_reporter.scenario_summary['passed'] == 0:
            return None


def send_by_mode(context, mode):
    """
        Отправляет уведомление в telegram по выбранному режиму работы. Режим работы устанавливается в
        переменной TG_NOTIFICATION_MODE в конфигурационном файле. По умолчанию disable

        Args:
            context - текущий контекст окружения
            mode - режим отправки уведомлений, задается в конфигурационном файле
        TG_NOTIFICATION_MODE params:
            disable - отправка уведомлений выключена при любых результатах
            on_success - отправка уведомлений только в случае успеха
            on_errors - отправка уведомлений в случае если тесты упали или произошла ошибка при запуске тестов
            always - отправка уведомлений в случае любых результатов
        """
    log.debug(f'get_run_status={get_run_status(context)}')
    run_status = get_run_status(context)

    if run_status and mode.lower() in ("on_success", "always"):
        telegram_bot_sendnotify(settings.TG_NICKNAME_FOR_NOTIFICATION,
                                f'Тесты прошли успешно, ссылка на результаты: {context.backend.session_url}')

    if run_status is False and mode.lower() in ("on_errors", "always"):
        telegram_bot_sendnotify(settings.TG_NICKNAME_FOR_NOTIFICATION,
                                f'Тесты прошли неуспешно, ссылка на результаты: {context.backend.session_url}')

    if run_status is None and mode.lower() in ("on_errors", "always"):
        telegram_bot_sendnotify(settings.TG_NICKNAME_FOR_NOTIFICATION,
                                f'В процессе запуска что-то пошло не так, ссылка на результаты: {context.backend.session_url}')


def slugify(input_str: str) -> str:
    slug = []
    for symbol in input_str:
        code = ord(symbol)%128
        symbol = "-"
        if 48 < code < 58 or 64 < code < 91 or 96 < code < 123:
            symbol = chr(code)

        slug.append(symbol)

    return "".join(slug)
