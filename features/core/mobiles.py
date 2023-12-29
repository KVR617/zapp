import os

from appium import webdriver
from pathlib import Path
from collections import namedtuple
from features.core.constants import MOBILE_LOG_REG

from features.core.smart_wait import SmartWait

from features.core.settings import (
    MOBILE_DEVICE,
    MOBILE_NO_RESET,
    MOBILE_APP_PATH,
    MOBILE_APP_PACKAGE,
    MOBILE_DEVICE_NAME,
    MOBILE_PLATFORM_NAME,
    MOBILE_PLATFORM_VERSION,
    MOBILE_AUTOMATION_NAME,
    MOBILE_UDID,
    MOBILE_LOGS_DIR,
    MOBILE_FULL_RESET,
    REMOTE_EXECUTOR,
)
from features.core.step_decorators import allow_script_for_mobile
from features.core.utils import log


@allow_script_for_mobile
def get_android_app_version(context):
    result = context.browser.execute_script('mobile: shell', {
        'command': 'dumpsys',
        'args': [f'package {MOBILE_APP_PACKAGE} | grep versionName'],
        'includeStderr': True,
        'timeout': 5000
    })

    return result['stdout'].strip('    versionName=')


@allow_script_for_mobile
def get_pid_for_app(context, app_package=MOBILE_APP_PACKAGE):
    pid = context.browser.execute_script('mobile: shell', {
        'command': 'pidof',
        'args': [f'-s {app_package}'],
        'includeStderr': True,
        'timeout': 5000
    })
    return pid['stdout'].strip()


class AppStateIs(object):
    """
        В случае проверки на статус "активно" - пытаемся поднять свёрнутое приложение
    """
    def __init__(self, app_status, MOBILE_APP_PACKAGE):
        self.app_status = app_status
        self.MOBILE_APP_PACKAGE = MOBILE_APP_PACKAGE

    def __call__(self, driver):
        if self.app_status == 4:
            driver.activate_app(MOBILE_APP_PACKAGE)
        return self.app_status == driver.query_app_state(MOBILE_APP_PACKAGE)


class AppNotInForeground(object):
    """
        Проверяем что приложение не активно
    """
    def __init__(self, MOBILE_APP_PACKAGE):
        self.MOBILE_APP_PACKAGE = MOBILE_APP_PACKAGE

    def __call__(self, driver):
        return not (driver.query_app_state(MOBILE_APP_PACKAGE) == 4)


def try_to_raise_android_app(context):
    SmartWait(context).wait_for(expected=AppNotInForeground(MOBILE_APP_PACKAGE))
    SmartWait(context).wait_for(expected=AppStateIs(4, MOBILE_APP_PACKAGE))


def local_save_android_logs(context, scenario):
    app_pid = get_pid_for_app(context)
    log.debug(f'{MOBILE_APP_PACKAGE} PID = {app_pid}')

    logcat = context.browser.get_log('logcat')
    filepath = os.path.abspath(os.path.join(MOBILE_LOGS_DIR,
                                            str(context.metrics_start_date), scenario.name + ".txt"))
    try:
        os.makedirs(os.path.join(MOBILE_LOGS_DIR, str(context.metrics_start_date)), exist_ok=True)
        with open(filepath, "wt") as logfile:
            for line in logcat:
                if (message := line.get('message')) \
                        and (match := MOBILE_LOG_REG.match(message)) \
                        and (match.group('pid') == app_pid):
                    logfile.write(message + '\n')

        log.info(f'Логи сценария доступны по пути: {filepath}')

    except OSError as e:
        log.error("Не удалось записать логи сценария")
        log.debug(e)


Device = namedtuple('Device', 'platform_name, platform_version, automation_name, udid, device_name, unlock_type, unlock_key')
MOBILES = ('mobile', 'android', 'ios')

DEVICES = dict(
    huawei=Device(
        platform_name='Android',
        platform_version='9.0',
        automation_name='uiautomator2',
        udid='ABC1234567890000',
        device_name='Smartphone',
        unlock_type='',
        unlock_key=''
    ),
    remote_sim=Device(
        platform_name='Android',
        platform_version='12.0',
        automation_name='uiautomator2',
        udid='emulator-1234',
        device_name='emulator64_x86_64_arm64',
        unlock_type='',
        unlock_key=''
    )
)
DEVICES['default'] = DEVICES['remote_sim']
devices_str = ", ".join(DEVICES.keys())


class Mobile:
    def __init__(self):

        if MOBILE_DEVICE is None:
            device = Device(
                platform_name=MOBILE_PLATFORM_NAME,
                platform_version=MOBILE_PLATFORM_VERSION,
                automation_name=MOBILE_AUTOMATION_NAME,
                udid=MOBILE_UDID,
                device_name=MOBILE_DEVICE_NAME,
                unlock_type='',
                unlock_key=''
            )

            if empty_params := [f'MOBILE_{k.upper()}' for k, v in device._asdict().items() if v == 'default']:
                log.error(f"Необходимо заполнить параметры: {', '.join(empty_params)} "
                          f"или передать в параметре MOBILE_DEVICE устройство из списка доступных: {devices_str}")
                raise AttributeError

        else:
            device = DEVICES.get(MOBILE_DEVICE.lower())

            if device is None:
                log.error(f'Мобильное устройство "{MOBILE_DEVICE}" не найдено в списке доступных: {devices_str}')
                raise KeyError

        if not MOBILE_APP_PATH:
            log.error(f'Необходимо указать путь до мобильного приложения в параметре MOBILE_APP_PATH')
            raise AttributeError

        app_path = Path(Path.cwd(), MOBILE_APP_PATH)

        self.name = device.platform_name.capitalize()
        self.version = device.platform_version
        self.type = 'remote'

        self.caps = {
            "platformName": device.platform_name,
            "platformVersion": device.platform_version,
            "automationName": device.automation_name,
            "udid": device.udid,
            "deviceName": device.device_name,
            "app": str(app_path),
            "appPackage": MOBILE_APP_PACKAGE,
            "noReset": MOBILE_NO_RESET,
            "fullReset": MOBILE_FULL_RESET,
            "gpsEnabled": "true",
        }

        if device.unlock_type:
            self.caps.update(dict(
                unlockType=device.unlock_type,
                unlockKey=device.unlock_key
            ))

        log.debug(f'MOBILE_CAPABILITIES: {self.caps}')
        log.debug(f'MOBILE_APP_PATH: {MOBILE_APP_PATH}')

    def get_driver(self):
        try:
            return webdriver.Remote(REMOTE_EXECUTOR, desired_capabilities=self.caps)
        except Exception as ex:
            log.error(f'Не удалось подключиться к Appium серверу по адресу {REMOTE_EXECUTOR}')
            raise ex


class MobileAvoids:
    def __init__(self, context):
        self.execute_script = context.browser.execute_script
        self.get_cookies = context.browser.get_cookies
        self.delete_all_cookies = context.browser.delete_all_cookies

    def avoid_all(self, context):
        context.browser.execute_script = self.avoid_execute_script
        context.browser.get_cookies = self.avoid_get_cookies
        context.browser.delete_all_cookies = self.avoid_delete_all_cookies

    def restore_all(self, context):
        context.browser.execute_script = self.execute_script
        context.browser.get_cookies = self.get_cookies
        context.browser.delete_all_cookies = self.delete_all_cookies

    @staticmethod
    def avoid_execute_script(*args, **kwargs):
        return

    @staticmethod
    def avoid_get_cookies(*args, **kwargs):
        return []

    @staticmethod
    def avoid_delete_all_cookies(*args, **kwargs):
        return
