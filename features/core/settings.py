import validators
import re
from envparse import env
import datetime

RUN_TYPE = env.str('RUN_TYPE', default='behave')
SESSION_ID = env.str('SESSION_ID', default=None)
BACKEND_ORIGIN = env.str('BACKEND_ORIGIN', default='')

LINUX_REMOTE_EXECUTOR = "https://vnc-browser.example.com/wd/hub"
WINDOWS_REMOTE_EXECUTOR = "http://win-vnc.example.com:4444/wd/hub"
MACOS_REMOTE_EXECUTOR = "http://mac-vnc.example.com:4444"
MOBILE_REMOTE_EXECUTOR = "http://mobile-vnc.example.com:4723/wd/hub"
MOBILE_LOCAL_EXECUTOR = "http://localhost:4723/wd/hub"

STAND_TEMPLATE = env.str('STAND_TEMPLATE', default='localhost:8080')
STAND = TEST_STAND = env.str('TEST_STAND')

JIRA_HOST = env.str('JIRA_HOST', default='https://jira.example.com/')
JIRA_USER = env.str('JIRA_USER', default='')
if not re.match(r'^[A-Za-z0-9_]*$', JIRA_USER):
    raise Exception('Параметр JIRA_USER должен содержать только строку логина (не email, без спецсимволов)')
JIRA_PASSWORD = env.str('JIRA_PASSWORD', default='')
VERSION_NAME = VERSION = env.str('VERSION', default=None)
PROJECT_KEY = PROJECT = env.str('PROJECT')
if not re.match(r'^[A-Z]+$', PROJECT_KEY):
    raise Exception('Параметр PROJECT должен содержать идентификатор проекта в том виде, в котором он указывается' +
                    'в строке URL в Jira (большими латинскими буквами)')

DEBUG = env.bool('DEBUG', default=False)
DEPLOY = env.bool('DEPLOY', default=False)
ENV = env.str('ENV', default='QA')
if not re.match(r'^(QA|STAGE|PROD)$', ENV):
    raise Exception('Параметр ENV может принимать значения QA, STAGE или PROD')

ZEPHYR_CONDITION = not (ENV.lower() == 'qa' and not DEPLOY)
ZEPHYR_TOGGLE = env.bool('USE_ZEPHYR', default=False)
ZEPHYR_USE = ZEPHYR_CONDITION and ZEPHYR_TOGGLE
ZEPHYR_LITE = env.bool('ZEPHYR_LITE', default=True)

BROWSER = env.str('BROWSER', default='chrome')
BROWSER_VERSION = env.str('BROWSER_VERSION', default='')
BROWSER_USERAGENT = env.str('BROWSER_USERAGENT', default=None)
BROWSER_LOGGING = env.bool('BROWSER_LOGGING', default=True)

CHROME_OPTIONS = env.str('CHROME_OPTIONS', default='')

CANARY_COOKIE = env.str('CANARY_COOKIE', default='')

default_path = ''

REMOTE_EXECUTOR = env.str('REMOTE_EXECUTOR', default='')
if REMOTE_EXECUTOR.lower() in ('1', 'true', 'default'):

    if BROWSER.lower() in ('ie', 'edge', 'explorer'):
        REMOTE_EXECUTOR = WINDOWS_REMOTE_EXECUTOR
    elif BROWSER.lower() in ('safari',):
        REMOTE_EXECUTOR = MACOS_REMOTE_EXECUTOR
    elif BROWSER.lower() in ('mobile', 'android', 'ios'):
        REMOTE_EXECUTOR = MOBILE_REMOTE_EXECUTOR
        if BROWSER.lower() == 'android':
            if ENV.upper() == "STAGE":
                default_path = '/Users/mobilefarm/Documents/Android/ship-debug-stage.apk'
            elif ENV.upper() == "PROD":
                default_path = '/Users/mobilefarm/Documents/Android/ship-debug-prod.apk'
            else:
                default_path = '/Users/mobilefarm/Documents/Android/ship-debug.apk'

    else:
        REMOTE_EXECUTOR = LINUX_REMOTE_EXECUTOR

if REMOTE_EXECUTOR.lower() in ('0', 'false', ''):
    if BROWSER.lower() in ('mobile', 'android', 'ios'):
        REMOTE_EXECUTOR = MOBILE_LOCAL_EXECUTOR

if REMOTE_EXECUTOR and not validators.url(REMOTE_EXECUTOR):
    raise Exception('Параметр REMOTE_EXECUTOR должен содержать валидный URL')

SELENOID_UI_URL = env.str('SELENOID_UI_URL', default='https://zapp-vnc.example.com/')
if not validators.url(SELENOID_UI_URL):
    raise Exception('Параметр SELENOID_UI_URL должен содержать валидный URL')

VIDEO = env.bool('VIDEO', default=False)
video_name_timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
VIDEO_NAME = env.str('VIDEO_NAME', default=f'{PROJECT_KEY}_{ENV}_{video_name_timestamp}.mp4')

VIDEO_DIR = env.str('VIDEO_DIR', default='video')

RETRY_DELAY = ON_SRE_DELAY = env.int('RETRY_DELAY', default=100000)
SMARTWAIT_DELAY = env.float('SMARTWAIT_DELAY', default=7)
FORCE_DELAY = env.float('FORCE_DELAY', default=0)
if FORCE_DELAY > 2:
    raise Exception('Параметр FORCE_DELAY должен иметь значение не более 2 секунд')

LOG_FORMAT = '\r %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s'

SCREENSHOT_MODE = env.bool('SCREENSHOT_MODE', default=False)
ZAPP_SITE_URL = env.str('ZAPP_SITE_URL', default='https://zapp.example.com/')
if not validators.url(ZAPP_SITE_URL):
    raise Exception('Параметр ZAPP_SITE_URL должен содержать валидный URL')

SCREENSHOT_DIR = env.str('SCREENSHOT_DIR', default='_screenshots')
LOCAL_SCREENSHOTS = env.bool('LOCAL_SCREENSHOTS', default=False) and RUN_TYPE in ('npm', 'local')

REMOTE_STORAGE_URL = env.str('REMOTE_STORAGE_URL', default='http://kube.example.com/tools/service-s3-proxy-zapp/')


VAULT_USE = env.bool('VAULT_USE', default=False)
VAULT_HOST = env.str('VAULT_HOST', default='vault.example.com')
VAULT_DB_TOKEN = env.str('VAULT_DB_TOKEN', default=None) or env.str('VAULT_TOKEN', default='example')
VAULT_DB_STORAGE = env.str('VAULT_DB_STORAGE', default='kv')
VAULT_DB_STORAGE_VERSION = env.int('VAULT_DB_STORAGE_VERSION', default=2)
VAULT_DB_STORAGE_PATH = env.str('VAULT_DB_STORAGE_PATH', default='zapp/db')
VAULT_SECRET_STORAGE_TOKEN = env.str('VAULT_SECRET_STORAGE_TOKEN', default='example')
VAULT_SECRET_STORAGE = env.str('VAULT_SECRET_STORAGE', default='kv')
VAULT_SECRET_STORAGE_VERSION = env.int('VAULT_SECRET_STORAGE_VERSION', default=2)
VAULT_SECRET_STORAGE_PATH = env.str('VAULT_SECRET_STORAGE_PATH', default='zapp/test_secrets')

INFLUX_USE = env.bool('INFLUX_USE', default=False)
INFLUX_HOST = env.str('INFLUX_HOST', default='http://influx.example.com')
INFLUX_PORT = env.str('INFLUX_PORT', default='8086')
INFLUX_DB = env.str('INFLUX_DB', default='zapp_metrics')

MOBILE_NO_RESET = env.bool('MOBILE_NO_RESET', default=False)
MOBILE_FULL_RESET = env.bool('MOBILE_FULL_RESET', default=not MOBILE_NO_RESET)
MOBILE_DEVICE = env.str('MOBILE_DEVICE', default='remote_sim')
MOBILE_DEVICE_NAME = env.str('MOBILE_DEVICE_NAME', default='default')
MOBILE_PLATFORM_NAME = env.str('MOBILE_PLATFORM_NAME', default='default')
MOBILE_PLATFORM_VERSION = env.str('MOBILE_PLATFORM_VERSION', default='default')
MOBILE_AUTOMATION_NAME = env.str('MOBILE_AUTOMATION_NAME', default='uiautomator2')
MOBILE_UDID = env.str('MOBILE_UDID', default='default')

MOBILE_APP_PATH = env.str('MOBILE_APP_PATH', default=default_path)
MOBILE_APP_PACKAGE = env.str('MOBILE_APP_PACKAGE', default='com.example.application.debug')

MOBILE_LOGGING = env.bool('MOBILE_LOGGING', default='False')
MOBILE_LOGS_DIR = env.str('MOBILE_LOGS_DIR', default='_mobile_logs')

BACKEND_LOCAL_SESSION_REGISTER = env.bool('BACKEND_LOCAL_SESSION_REGISTER', default=False)

TG_NICKNAME_FOR_NOTIFICATION = env.str('TG_NICKNAME_FOR_NOTIFICATION', default='')
TG_BOT_TOKEN = env.str('TG_BOT_TOKEN', default='')
TG_CHAT_ID = env.str('TG_CHAT_ID', default='')
TG_NOTIFICATION_MODE = env.str('TG_NOTIFICATION_MODE', default='disable')

RETRY_AFTER_FAIL = env.bool('RETRY_AFTER_FAIL', default=False)
MAX_ATTEMPTS = env.int('MAX_ATTEMPTS', default=2)
