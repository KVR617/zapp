import re
from urllib.parse import urljoin
from enum import Enum

from features.core.settings import JIRA_HOST, ZAPP_SITE_URL
import selenium.common.exceptions as se_exc
import appium.common.exceptions as app_exc

JIRA_BASE = urljoin(JIRA_HOST, 'rest/api/2/')
JIRA_ISSUE = urljoin(JIRA_BASE, 'issue/')
JIRA_ISSUE_VIEW = urljoin(JIRA_HOST, 'browse/')
JIRA_PROJECT = urljoin(JIRA_BASE, 'project/')
JIRA_SEARCH_TEST = urljoin(JIRA_BASE, 'search?jql=issuetype=тест%20and%20labels%20in')
JIRA_ISSUE_LINK = urljoin(JIRA_BASE, 'issueLink/')
JIRA_DATE_FORMAT = 'd/MM/yy'

ZEPHYR_BASE = urljoin(JIRA_HOST, 'rest/zapi/latest/')
ZEPHYR_TEST_STEP = urljoin(ZEPHYR_BASE, 'teststep/')
ZEPHYR_TEST_CYCLE = urljoin(ZEPHYR_BASE, 'cycle/')
ZEPHYR_EXECUTION = urljoin(ZEPHYR_BASE, 'execution/')
ZEPHYR_STEP_RESULT = urljoin(ZEPHYR_BASE, 'stepResult/')
ZEPHYR_ADD_TEST = urljoin(ZEPHYR_EXECUTION, 'addTestsToCycle')
ZEPHYR_ATTACHMENT = urljoin(ZEPHYR_BASE, 'attachment')
ZEPHYR_RESULTS_URL = urljoin(JIRA_HOST, 'secure/enav/#/')

ZAPP_BACKEND_URL = {
    'QA': 'https://zapp-backend.example.com',
    'PROD': 'https://zapp-backend.example.com',
    'DEV': 'http://localhost:8000'
}

ZAPP_FRONTEND_URL = {
    'QA': 'https://zapp-front.example.com',
    'PROD': 'https://zapp-front.example.com',
    'DEV': 'http://localhost:3000'
}

SCREENSHOT_RESULTS_URL = urljoin(ZAPP_SITE_URL, 'screenshots/')
STEP_HELP = urljoin(ZAPP_SITE_URL, 'manual#steps/')

EM_ELEMENT_NOT_FOUND = 'Не найден элемент {} с локатором {}. Убедитесь, что элемент существует, видимый и не перекрыт \
 другими элементами. Попробуйте увеличить время ожидания элементов, проверьте правильность написания локатора.'
EM_LOCATOR_NOT_FOUND = 'Не найден локатор с именем {}. Убедитесь, что локатор добавлен в один из файлов *_locators.py'
EM_WAITING_TIMEOUT = 'Не удалось дождаться выполнения условия проверки элемента. Попробуйте увеличить время ожидания.'
IM_ELEMENT_NOT_VISIBLE = 'Не найден элемент {} с локатором {}, ожидаемый в состоянии невидимости.'

BROWSER_AWARE_MESSAGE = 'ZAPP поддерживает работу с браузером {} лишь частично, некоторые шаги могут быть не выполнены'

EM_INVALID_URL = 'Невозможно перейти по URL "{}"'
EM_API_REQUEST_NOT_FOUND = 'Не удалось найти результат выполнения запроса, убедитесь что шаг с запросом к api выполнен'

UPDATE_STEPS_MESSAGE = """\33[94m╭────────────────────────────────────────────────╮
            │                                                │
            │\33[34m       ДЛЯ ОБНОВЛЕНИЯ УСТАРЕВШИХ ШАГОВ          \33[94m│
            │\33[34m    ВЫПОЛНИТЕ ВНУТРИ ПАПКИ СКРИПТ               \33[94m│
            │\33[31m               migrate_steps                    \33[94m│
            │                                                │
            ╰────────────────────────────────────────────────╯"""

EXCEPTIONS_TO_RETRY = (se_exc.StaleElementReferenceException, se_exc.ElementNotInteractableException,
                       se_exc.ElementClickInterceptedException, se_exc.InvalidElementStateException, app_exc.NoSuchContextException)

STATUSES = {
    'passed': '1',
    'failed': '2',
    'in_progress': '3',
    'untested': '4',
    'blocked': '4',
    'skipped': '-1'
}

MOBILE_LOG_REG = re.compile(
        r'^(?P<timestamp>\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d{3})\s+(?P<pid>\d+)\s+'
        r'(?P<tid>\d+)\s(?P<level>\w)\s(?P<tag>.*?):\s(?P<message>.*)$')


class Section:
    """Навигация по библиотке шагов на сайте ZAPP"""

    class ACTION(Enum):
        """Действия"""
        CLICK = 'Нажатия мыши'
        PRESS_KEY = 'Нажатия клавиш на клавиатуре'
        INPUT = 'Ввод значений'
        RANDOM_INPUT = 'Ввод случайно сгенерированных значений'
        NAVIGATION = 'Навигация (переход по ссылкам, переключение окон)'
        SCROLL = 'Пролистывания'
        FILE = 'Загрузка/скачивание файлов'
        SERVICE = 'Служебные'
        MOBILE = 'Мобильные'

    class ASSERTION(Enum):
        """Проверки"""
        VISIBILITY = 'Видимость/невидимость'
        CLICKABILITY = 'Доступность/недоступность'
        VALUE = 'Сравнение значений'

    API = 'Работа с API'
    DB = 'Работа с базами данных'
    SCREENSHOT = 'Скриншот тестирование'


BACKEND_RUN_TYPES = ('backend', 'quality_gate', 'generator')
REGISTRABLE_RUN_TYPES = ('local', 'npm', 'ci')
NON_REGISTRABLE_RUN_TYPES = ('behave',)
