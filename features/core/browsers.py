import platform
import os

from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from abc import ABC, abstractmethod
from collections import namedtuple

from features.core.install_driver import install_geckodriver, install_chromedriver
from features.core.constants import BROWSER_AWARE_MESSAGE
from features.core.settings import (
    VIDEO,
    VIDEO_NAME,
    REMOTE_EXECUTOR,
    ENV,
    PROJECT_KEY,
    BROWSER_LOGGING,
    BROWSER_VERSION,
    BROWSER_USERAGENT,
    CHROME_OPTIONS
)
from features.core.utils import log, get_abs_file_path_from_cwd

CHROME_LOGGING_PREFS = {'goog:loggingPrefs': dict(browser='ALL', driver='ALL', performance='ALL')}
BASIC_REMOTE_CAPS = dict(
    name=f'PROJECT={PROJECT_KEY}, ENV={ENV}',
    version=BROWSER_VERSION,
    enableVNC=True,
    enableVideo=bool(VIDEO)
)
if BASIC_REMOTE_CAPS.get('enableVideo'):
    BASIC_REMOTE_CAPS['videoName'] = VIDEO_NAME


def safari_patch(self):
    return self.parent.execute_script(
        "return (%s).apply(null, arguments);" % webdriver.remote.webelement.isDisplayed_js,
        self)


class AbstractBrowser(ABC):
    def __init__(self, tempdir=''):
        self._tempdir = tempdir
        self._config = self._configure()
        self._driver = self._prepare()
        self.name = self._driver.capabilities.get('browserName').capitalize()
        self.version = self._driver.capabilities.get('browserVersion', 'неизвестна')
        self.type = 'remote' if self._driver._is_remote else 'local'

    @abstractmethod
    def _prepare(self):
        pass

    @abstractmethod
    def _configure(self):
        pass

    def get_driver(self):
        return self._driver


class AbstractChromiumBrowser(AbstractBrowser):
    @abstractmethod
    def _prepare(self):
        pass

    def _configure(self):
        prefs = {
            "profile.default_content_setting_values.automatic_downloads": False,
            "profile.default_content_settings.popups": False,
            "profile.default_content_setting_values.notifications": 2,
            "download.directory_upgrade": True,
            "download.default_directory": self._tempdir
        }

        perf_logging_prefs = {
            "traceCategories": 'browser,devtools.timeline,devtools',
            "enableNetwork": True,
        }

        options = webdriver.ChromeOptions()
        arguments = [
            '--force-device-scale-factor=1', '--enable-screenshot-testing-with-mode', '--disable-gpu',
            '--ignore-certificate-errors', '--disable-web-security', '--ignore-ssl-errors=yes'
        ]

        if CHROME_OPTIONS:
            arguments += CHROME_OPTIONS.split(' ')
            log.debug(arguments)

        for arg in set(arguments):
            options.add_argument(arg)

        if BROWSER_USERAGENT is not None:
            options.add_argument(f'--user-agent="{BROWSER_USERAGENT}"')

        if BROWSER_LOGGING:
            options.add_argument('--enable-logging')
            options.add_experimental_option("perfLoggingPrefs", perf_logging_prefs)

        options.add_experimental_option("prefs", prefs)

        return options


class AbstractFirefoxBrowser(AbstractBrowser):
    @abstractmethod
    def _prepare(self):
        pass

    def _configure(self):
        return {
            'browser.download.folderList': 2,
            'browser.download.manager.showWhenStarting': False,
            'browser.safebrowsing.downloads.enabled': False,
            'pdfjs.disabled': True,
            'browser.download.dir': self._tempdir,
            'browser.helperApps.neverAsk.saveToDisk':
                'application/pdf,application/x-pdf,application/octet-stream,application/zip,text/html,text/plain'
        }


class AbstractIeBrowser(AbstractBrowser):
    @abstractmethod
    def _prepare(self):
        pass

    def _configure(self):
        log.warning(BROWSER_AWARE_MESSAGE.format('Internet Explorer'))


class AbstractYandexBrowser(AbstractChromiumBrowser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Yandex'

    @abstractmethod
    def _prepare(self):
        pass

    def _configure(self):
        options = super()._configure()

        if platform.system() == "Darwin":
            options.binary_location = "/Applications/Yandex.app/Contents/MacOS/Yandex"

        elif platform.system() == "Windows":
            options.binary_location = os.path.join(os.environ['USERPROFILE'],
                                                   "AppData\\Local\\Yandex\\YandexBrowser\\Application\\browser.exe")
        elif platform.system() == "Linux":
            options.binary_location = "/usr/bin/yandex-browser-beta"

        return options


class AbstractSafariBrowser(AbstractBrowser):
    @abstractmethod
    def _prepare(self):
        pass

    def _configure(self):
        log.warning(BROWSER_AWARE_MESSAGE.format('Safari'))
        webdriver.remote.webelement.WebElement.is_displayed = safari_patch


class LocalChromeBrowser(AbstractChromiumBrowser):
    def __repr__(self):
        return 'Chrome-local'

    def _prepare(self):
        driver = None
        caps = self._config.to_capabilities()
        if BROWSER_LOGGING:
            caps.update(CHROME_LOGGING_PREFS)

        try:
            return webdriver.Chrome(desired_capabilities=caps)
        
        except SessionNotCreatedException:
            log.error('Браузер Chrome не найден. Установите или обновите до последней версии и повторите попытку.')
        
        except WebDriverException:
            log.info(f'Установлен chromedriver: {install_chromedriver()}')
            return webdriver.Chrome(desired_capabilities=caps)


class AbstractSberBrowser(AbstractChromiumBrowser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Sber'

    @abstractmethod
    def _prepare(self):
        pass

    def _configure(self):
        options = super()._configure()

        if platform.system() == "Darwin":
            options.binary_location = "/Applications/SberBrowser.app"

        elif platform.system() == "Windows":
            options.binary_location = os.path.join(os.environ['USERPROFILE'],
                                                   "AppData\\Local\\Sber\\SberBrowser\\Application\\browser.exe")
        elif platform.system() == "Linux":
            options.binary_location = "/usr/bin/sberbrowser-browser"

        return options


class RemoteChromeBrowser(AbstractChromiumBrowser):
    def __repr__(self):
        return 'Chrome-remote'

    def _prepare(self):
        caps = self._config.to_capabilities()
        caps.update(BASIC_REMOTE_CAPS)

        if BROWSER_LOGGING:
            caps.update(CHROME_LOGGING_PREFS)

        return webdriver.Remote(
            command_executor=REMOTE_EXECUTOR,
            desired_capabilities=caps
        )


class LocalFirefoxBrowser(AbstractFirefoxBrowser):
    def __repr__(self):
        return 'Firefox-local'

    def _prepare(self):
        profile = webdriver.FirefoxProfile()
        for key, value in self._config.items():
            profile.set_preference(key, value)

        try:
            return webdriver.Firefox(firefox_profile=profile)
        
        except SessionNotCreatedException:
            log.error('Браузер Firefox не найден. Установите или обновите до последней версии и повторите попытку.')
        
        except WebDriverException:
            log.info(f'Установлен geckodriver: {install_geckodriver()}')
            return webdriver.Firefox(firefox_profile=profile)


class RemoteFirefoxBrowser(AbstractFirefoxBrowser):
    def __repr__(self):
        return 'Firefox-remote'

    def _prepare(self):
        caps = {'browserName': 'firefox', 'moz:firefoxOptions': {'prefs': self._config}}
        caps.update(BASIC_REMOTE_CAPS)

        return webdriver.Remote(
            command_executor=REMOTE_EXECUTOR,
            desired_capabilities=caps
        )


class LocalIeBrowser(AbstractIeBrowser):
    def __repr__(self):
        return 'IE-local'

    def _prepare(self):
        caps = {
            'requireWindowFocus': False
        }
        opts = webdriver.Ie.create_options(self)
        opts.ignore_protected_mode_settings = True
        opts.ignore_zoom_level = True
        opts.require_window_focus = False
        opts.ensure_clean_session = True
        opts.native_events = True
        opts.introduceFlakinessByIgnoringProtectedModeSettings = True
        opts.persistent_hover = False

        return webdriver.Ie(
            capabilities=caps,
            options=opts
        )


class RemoteIeBrowser(AbstractIeBrowser):
    def __repr__(self):
        return 'IE-remote'

    def _prepare(self):
        opts = webdriver.Ie.create_options(self)
        opts.ignore_protected_mode_settings = True
        opts.ignore_zoom_level = True
        opts.require_window_focus = False
        opts.ensure_clean_session = True
        opts.native_events = True
        opts.introduceFlakinessByIgnoringProtectedModeSettings = True
        opts.persistent_hover = False

        caps = {
            'browserName': 'internet explorer',
            'platform': "windows",
            'enableVNC': False,
            'enableVideo': False,
            'name': f"Project={PROJECT_KEY}, ENV={ENV}",
            'requireWindowFocus': False,
            # 'enablePersistentHovering': False,  //проверить правильный ввод через caps
            # 'ie.nativeEvents': False,   // через opts настройки точно подхватываются
            # 'ie.ensureCleanSession': True,
        }

        return webdriver.Remote(
            command_executor=REMOTE_EXECUTOR,
            desired_capabilities=caps,
            options=opts
        )


class LocalYandexBrowser(AbstractYandexBrowser):
    def __repr__(self):
        return 'Yandex-local'

    def _prepare(self):
        caps = self._config.to_capabilities()
        if BROWSER_LOGGING:
            caps.update(CHROME_LOGGING_PREFS)
        return webdriver.Opera(desired_capabilities=caps)


class RemoteYandexBrowser(AbstractYandexBrowser):
    def __repr__(self):
        return 'Yandex-remote'

    def _prepare(self):
        self._config.binary_location = "/usr/bin/yandex-browser-beta"
        caps = self._config.to_capabilities()
        if BROWSER_LOGGING:
            caps.update(CHROME_LOGGING_PREFS)
        caps.update(BASIC_REMOTE_CAPS)
        caps.update({'browserName': 'yandex'})

        return webdriver.Remote(
            command_executor=REMOTE_EXECUTOR,
            desired_capabilities=caps
        )


class LocalSafariBrowser(AbstractSafariBrowser):
    def __repr__(self):
        return 'Safari-local'

    def _prepare(self):
        caps = webdriver.DesiredCapabilities.SAFARI
        caps.update({'safari.options': {'technologyPreview': False}, 'safari.options.technologyPreview': False})
        return webdriver.Safari(desired_capabilities=caps)


class RemoteSafariBrowser(AbstractSafariBrowser):
    def __repr__(self):
        return 'Safari-remote'

    def _prepare(self):
        caps = webdriver.DesiredCapabilities.SAFARI
        return webdriver.Remote(command_executor=REMOTE_EXECUTOR, desired_capabilities=caps)


class LocalEdgeBrowser(AbstractChromiumBrowser):
    def __repr__(self):
        return 'Edge(Chromium)-local'

    def _prepare(self):
        # selenium 4.0
        pass


class RemoteEdgeBrowser(AbstractChromiumBrowser):
    def __repr__(self):
        return 'Edge(Chromium)-remote'

    def _prepare(self):
        # selenium 4.0
        pass

class LocalSberBrowser(AbstractSberBrowser):
    def __repr__(self):
        return 'Sber-local'

    def _prepare(self):
        caps = self._config.to_capabilities()
        if BROWSER_LOGGING:
            caps.update(CHROME_LOGGING_PREFS)
        driver_path = get_abs_file_path_from_cwd('bin/sberdriver')
        return webdriver.Opera(desired_capabilities=caps, executable_path=driver_path)


class RemoteSberBrowser(AbstractSberBrowser):
    def __repr__(self):
        return 'Sber-remote'

    def _prepare(self):
        self._config.binary_location = "/usr/bin/sberbrowser-browser"
        caps = self._config.to_capabilities()
        if BROWSER_LOGGING:
            caps.update(CHROME_LOGGING_PREFS)
        caps.update(BASIC_REMOTE_CAPS)
        caps.update({'browserName': 'sber'})

        return webdriver.Remote(
            command_executor=REMOTE_EXECUTOR,
            desired_capabilities=caps
        )


Browser = namedtuple('Browser', 'local remote')
BROWSERS = {
    'chrome': Browser(local=LocalChromeBrowser, remote=RemoteChromeBrowser),
    'firefox': Browser(local=LocalFirefoxBrowser, remote=RemoteFirefoxBrowser),
    'ff': Browser(local=LocalFirefoxBrowser, remote=RemoteFirefoxBrowser),
    'yandex': Browser(local=LocalYandexBrowser, remote=RemoteYandexBrowser),
    'safari': Browser(local=LocalSafariBrowser, remote=RemoteSafariBrowser),
    'explorer': Browser(local=LocalIeBrowser, remote=RemoteIeBrowser),
    'ie': Browser(local=LocalIeBrowser, remote=RemoteIeBrowser),
    'sber': Browser(local=LocalSberBrowser, remote=RemoteSberBrowser)
}
SELENOID_UI_BROWSERS = (RemoteChromeBrowser, RemoteFirefoxBrowser, RemoteYandexBrowser, RemoteSberBrowser)
