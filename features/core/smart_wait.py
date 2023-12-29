import time
from retrying import retry

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from features.core.constants import (
    EM_ELEMENT_NOT_FOUND,
    EM_LOCATOR_NOT_FOUND,
    EM_WAITING_TIMEOUT,
    IM_ELEMENT_NOT_VISIBLE
)
from features.core.utils import log, import_locators, escaping_exceptions

LOCATORS = import_locators()
INVISIBILITY = (EC.invisibility_of_element_located,)
VISIBILITY = (EC.visibility_of_element_located, EC.visibility_of_all_elements_located,
              EC.visibility_of_any_elements_located, EC.visibility_of)


class SmartWait:
    def __init__(self, context):
        """Custom wrap on Selenium WebDriverWait

        Args:
            context: Behave inner variable, which contains browser instance and delay setting as well.
        """
        self.__webdriver_wait = WebDriverWait(context.browser, context.smartwait_delay)
        self.__wait_method = self.__webdriver_wait.until
        self.expected = None
        self.force_delay = context.force_delay

    @staticmethod
    def _search_locator(target):
        if target:
            try:
                return LOCATORS[target]

            except KeyError:
                log.error(EM_LOCATOR_NOT_FOUND.format(target))
                raise

    @staticmethod
    def _get_locator_type(locator):
        if locator and locator.startswith(('/html/', '/')):
            return By.XPATH
        return By.CSS_SELECTOR

    @staticmethod
    def _prepare_method(locator, by, expected):
        if getattr(expected, '__module__') == EC.__name__ and locator:
            expected = expected((by, locator))
        return expected

    @property
    def _invisibility(self):
        invisible = self.expected in INVISIBILITY
        not_visible = self.expected in VISIBILITY and getattr(self.__wait_method, '__name__') == 'until_not'
        return invisible or not_visible

    @retry(retry_on_exception=escaping_exceptions, stop_max_delay=100000)
    def __wait(self, **kwargs):
        target = kwargs.get('target', '')
        locator = kwargs.get('locator') or self._search_locator(target)
        by = kwargs.get('by') or self._get_locator_type(locator)

        self.expected = kwargs.get('expected')
        if kwargs.get('wait_method') == 'until_not':
            self.__wait_method = self.__webdriver_wait.until_not

        try:
            if self._invisibility and self.force_delay < 0.5:
                time.sleep(0.5)  # prevents from false positive invisibility check

            else:
                time.sleep(self.force_delay)

            result = self.__wait_method(method=self._prepare_method(locator, by, self.expected))

            if self._invisibility and result is True:
                    log.debug(IM_ELEMENT_NOT_VISIBLE.format(target, locator))

            return result

        except TimeoutException:
            if self._invisibility:
                return False

            elif target and locator:
                log.error(EM_ELEMENT_NOT_FOUND.format(target, locator))
                raise

            else:
                log.error(EM_WAITING_TIMEOUT)
                raise

    def wait_for_element(self, **kwargs):
        """
        Keyword Args:
            target (str): Locator name.
            locator (str): Only if you want to directly pass a locator, not its name.
            by (object): Type of locator. Will be determined (CSS_SELECTOR or XPATH) if not passed.
            expected (object): A method from expected_conditions module (EC) or custom object returning boolean value;
                has value 'EC.visibility_of_element_located' by default.
            wait_method (str): Type of waiting; has value 'until' by default.

        Returns:
            Web element, if found;
            True if element is not found and expected to be invisible;
            False otherwise.
        """
        if not kwargs.get('expected'):
            kwargs['expected'] = EC.visibility_of_element_located

        return self.__wait(**kwargs)

    def wait_for_elements(self, **kwargs):
        """
        Keyword Args:
            target (str): Locator name.
            locator (str): Only if you want to directly pass a locator, not its name.
            by (object): Type of locator. Will be determined (CSS_SELECTOR or XPATH) if not passed.
            expected (object): A method from expected_conditions module (EC) or custom object returning boolean value;
                has value 'EC.visibility_of_all_elements_located' by default.
            wait_method (str): Type of waiting; has value 'until' by default.

        Returns:
            Web elements, if found;
            True if elements are not found and expected to be invisible;
            False otherwise.
        """
        if not kwargs.get('expected'):
            kwargs['expected'] = EC.visibility_of_all_elements_located

        return self.__wait(**kwargs)

    def wait_for(self, **kwargs):
        """
        Keyword Args:
            target (str): Locator name.
            locator (str): Only if you want to directly pass a locator, not its name.
            by (object): Type of locator. Will be determined (CSS_SELECTOR or XPATH) if not passed.
            expected (object): A method from expected_conditions module (EC) or custom object returning boolean value;
            wait_method (str): Type of waiting; has value 'until' by default.

        Returns:
            None; Just waits for some condition to happen.
        """
        self.__wait(**kwargs)
