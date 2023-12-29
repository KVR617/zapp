import os
import sys
import time
import datetime
import random
import decimal
import json
import importlib
from typing import Union

import validators
import re
import ast
import requests

from behave import *
from hamcrest import *
from retrying import retry

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

from features.core.selenium_support import patched_upload
from features.core.step_decorators import not_available_on_platform
from features.core.utils import (
    generate_tranzact_number,
    generate_phone_code,
    generate_valid_snils,
    strip_phone_number,
    variables,
    log,
    get_units_case,
    get_element_text,
    throw_deprecated_warn,
    doc,
    totp,
    get_last_downloaded_file,
    get_md5_hash,
    escaping_exceptions,
    get_from_variables,
    get_from_json,
    get_absolute_url,
    get_abs_file_path_from_cwd,
    format_delay,
    set_canary_cookie,
    get_notifications_secrets,
    get_element_text_value,
)
from features.core.js_scripts import (
    OUTLINE,
    OUTLINE_LIST,
    GET_TEXT,
    CAS_LOGOUT,
    CREATE_OVERLAY,
    REMOVE_OVERLAY,
)
from features.core.constants import (
    Section,
    EM_WAITING_TIMEOUT,
    IM_ELEMENT_NOT_VISIBLE,
    EM_API_REQUEST_NOT_FOUND,
    EM_INVALID_URL,
)
from features.core.screenshots import compare_element_screenshots, get_screenshot_name
from features.core.settings import SCREENSHOT_MODE, SMARTWAIT_DELAY as DEFAULT_DELAY, REMOTE_EXECUTOR, RETRY_DELAY
from features.core.smart_wait import SmartWait, LOCATORS
from features.core.api import Api
from features.core.database import execute_query as pg_query

from mimesis import Generic
from mimesis.builtins import RussiaSpecProvider
from mimesis.enums import Gender

generic = Generic('ru')
RussiaSpecProvider.Meta.name = 'ru'
generic.add_provider(RussiaSpecProvider)
gender = Gender.MALE if random.choice(['male', 'female']) == 'male' else Gender.FEMALE

WebElement._upload = patched_upload


@step('Я установил задержку ожидания загрузки элементов "{delay}" секунд')
@step('Я установил задержку ожидания загрузки элементов "{delay}" секунды')
@step('Я установил задержку ожидания загрузки элементов "{delay}" секунду')
@doc(Section.ACTION.SERVICE)
def change_smartwait_delay(context, delay):
    """ Изменить задержку ожидания перед заведомо длительными действиями. """
    if delay:
        context.smartwait_delay = format_delay(delay)
        log.info(f'Задержка ожидания загрузки элементов: {context.smartwait_delay} сек.')


@step('Я вернул задержку ожидания загрузки элементов на изначальную')
@doc(Section.ACTION.SERVICE)
def restore_smartwait_delay(context):
    """ Восстановить задержку ожидания на указанную при запуске тестов. """
    context.smartwait_delay = DEFAULT_DELAY
    log.info(f'Задержка ожидания загрузки элементов: {context.smartwait_delay} сек.')


@step('Я установил посимвольный ввод')
@step('Я установил посимвольный ввод с задержкой "{delay}" секунд')
@step('Я установил посимвольный ввод с задержкой "{delay}" секунды')
@step('Я установил посимвольный ввод с задержкой "{delay}" секунду')
@not_available_on_platform(platforms=('android', 'ios'))
@doc(Section.ACTION.SERVICE)
def change_send_keys_type(context, **kwargs):
    """ Изменить ввод на посимвольный с указанной задержкой или по умолчанию - 0,1 сек. """
    delay = kwargs.get('delay')
    context.char_input_delay = format_delay(delay) if delay else 0.1
    context.send_keys_as_granny = True
    log.info(f'Ввод значений: посимвольный с задержкой {context.char_input_delay} сек.')


@step('Я вернул ввод элементов на изначальный')
@not_available_on_platform(platforms=('android', 'ios'))
@doc(Section.ACTION.SERVICE)
def restore_send_keys_type(context):
    """ Восстановить обычный ввод. """
    context.send_keys_as_granny = False
    log.info('Ввод значений: обычный без задержки')


@given('Я перешел на главную страницу')
@when('Я перешел на главную страницу')
@then('Я вернулся на главную страницу')
@doc(Section.ACTION.NAVIGATION)
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
def go_to_main(context):
    """
        Открыть страницу, указанную при запуске в параметре TEST_STAND.
        Удобно использовать для возможности запуска одного теста на разных стендах.
    """
    go_to_url(context, context.host)


@given('Я переключился на фрейм "{target}"')
@when('Я переключился на фрейм "{target}"')
@doc(Section.ACTION.NAVIGATION)
def switch_to_frame(context, target):
    """
        Перейти в управление элементами внутри указанного фрейма.
        Для возврата использовать шаг "Я переключился на основную страницу"
    """
    SmartWait(context).wait_for_element(target=target, expected=EC.frame_to_be_available_and_switch_to_it)


@given('Я переключился на основную страницу')
@when('Я переключился на основную страницу')
@doc(Section.ACTION.NAVIGATION)
def return_to_default_content(context):
    """
        Вернуться в контекст основной страницы после перехода на управление внутри фрейма.
    """
    context.browser.switch_to.default_content()


@given('Я сохранил значение свойства "{property_name}" элемента "{target}" в переменную "{variable_name}"')
@when('Я сохранил значение свойства "{property_name}" элемента "{target}" в переменную "{variable_name}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.SERVICE)
def save_element_property(context, property_name, target, variable_name):
    """ Сохранить значение свойства  элемента (или атрибута, если свойство не найдено) в указанную переменную"""
    element = SmartWait(context).wait_for_element(target=target, expected=EC.presence_of_element_located)
    context.browser.execute_script(OUTLINE, element)
    element_property = element.get_attribute(property_name)

    if element_property:
        variables[variable_name] = element_property
        log.debug(f'VALUE "{element_property}" saved to variable "{variable_name}"')
    else:
        log.warning(f'Не найдено свойство "{property_name}" у элемента "{target}"')


@given('Я сохранил значение элемента "{target}" в переменную "{name}"')
@when('Я сохранил значение элемента "{target}" в переменную "{name}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.SERVICE)
def save_test_variable(context, target, name):
    """ Сохранить значение HTML-элемента в указанную переменную. Важно: регистр букв не учитывается. """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    value_from_element = get_element_text_value(context, element)

    if value_from_element:
        variables[name] = value_from_element
        log.debug(f'VALUE "{value_from_element}" saved to variable "{name}"')
    else:
        log.warning(f'Не найден текст на элементе "{target}"')


@given('Я ввел в поле "{target}" значение переменной "{variable}"')
@when('Я ввел в поле "{target}" значение переменной "{variable}"')
@when('Я ввел в поле "{target}" значение переменной "{variable}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.INPUT)
def fill_with_test_variable(context, target, variable):
    """
        Подставить в поле ввода значение переменной.

        target - название локатора,
        variable - название переменной или путь до неё, если в переменной лежит json

        Примеры:
        Я ввел в поле "Логин" значение переменной "color"
        Я ввел в поле "Логин" значение переменной "fruits > banana > color"
    """
    value = get_from_variables(variable)
    send_keys(context, target, value)


@when('Я вставил в поле "{target}" значение из буфера обмена')
@when('Я вставил в "{target}" значение из буфера обмена')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@not_available_on_platform(platforms='ios', fail=True)
@doc(Section.ACTION.INPUT)
def paste_from_clipboard(context, target):
    """ Вставить в указанное поле скопированное ранее значение. """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    action = ActionChains(context.browser).move_to_element(element)
    if context.is_mobile and context.browser_.name.lower() == 'android':
        action.perform()
        context.browser.press_keycode(124, 1)  # 124: Insert; 1: Meta Shift On
    else:
        action.send_keys(Keys.SHIFT + Keys.INSERT).perform()


@when('Я ввел в поле "{target}" сегодняшнюю дату')
@when('Я ввел в "{target}" сегодняшнюю дату')
@when('Я ввел в поле "{target}" сегодняшнюю дату в формате "{fmt}"')
@when('Я ввел в "{target}" сегодняшнюю дату в формате "{fmt}"')
@doc(Section.ACTION.INPUT)
def date_today(context, **kwargs):
    """ Подставить в поле ввода сегодняшнюю дату в указанном формате или по умолчанию в формате dd/mm/yyyy. """
    dt = datetime.date.today()
    send_keys(context, kwargs.get('target'), dt.strftime(kwargs.get('fmt', '%d/%m/%Y')))


@when('Я ввел в поле "{target}" вчерашнюю дату')
@when('Я ввел в "{target}" вчерашнюю дату')
@when('Я ввел в поле "{target}" вчерашнюю дату в формате "{fmt}"')
@when('Я ввел в "{target}" вчерашнюю дату в формате "{fmt}"')
@doc(Section.ACTION.INPUT)
def date_yesterday(context, **kwargs):
    """ Подставить в поле ввода вчерашнюю дату в указанном формате или по умолчанию в формате dd/mm/yyyy. """
    dt = datetime.date.today() - datetime.timedelta(days=1)
    send_keys(context, kwargs.get('target'), dt.strftime(kwargs.get('fmt', '%d/%m/%Y')))


@when('Я ввел в поле "{target}" завтрашнюю дату')
@when('Я ввел в "{target}" завтрашнюю дату')
@when('Я ввел в поле "{target}" завтрашнюю дату в формате "{fmt}"')
@when('Я ввел в "{target}" завтрашнюю дату в формате "{fmt}"')
@doc(Section.ACTION.INPUT)
def date_tomorrow(context, **kwargs):
    """ Подставить в поле ввода завтрашнюю дату в указанном формате или по умолчанию в формате dd/mm/yyyy. """
    dt = datetime.date.today() + datetime.timedelta(days=1)
    send_keys(context, kwargs.get('target'), dt.strftime(kwargs.get('fmt', '%d/%m/%Y')))


@when('Я ввел в поле "{target}" дату на {n} дней позже текущей')
@when('Я ввел в "{target}" дату на {n} дней позже текущей')
@when('Я ввел в поле "{target}" дату на {n} дней позже текущей в формате "{fmt}"')
@when('Я ввел в "{target}" дату на {n} дней позже текущей в формате "{fmt}"')
@doc(Section.ACTION.INPUT)
def date_later_then_now(context, **kwargs):
    """ Подставить в поле ввода дату позже на n дней в указанном формате или по умолчанию в формате dd/mm/yyyy. """
    dt = datetime.date.today() + datetime.timedelta(days=int(kwargs['n']))
    send_keys(context, kwargs.get('target'), dt.strftime(kwargs.get('fmt', '%d/%m/%Y')))


@when('Я ввел в поле "{target}" дату на {n} дней раньше текущей')
@when('Я ввел в "{target}" дату на {n} дней раньше текущей')
@when('Я ввел в поле "{target}" дату на {n} дней раньше текущей в формате "{fmt}"')
@when('Я ввел в "{target}" дату на {n} дней раньше текущей в формате "{fmt}"')
@doc(Section.ACTION.INPUT)
def date_earlier_then_now(context, **kwargs):
    """ Подставить в поле ввода дату позже на n дней в указанном формате или по умолчанию в формате dd/mm/yyyy. """
    dt = datetime.date.today() - datetime.timedelta(days=int(kwargs['n']))
    send_keys(context, kwargs.get('target'), dt.strftime(kwargs.get('fmt', '%d/%m/%Y')))


@given('Я перешел на страницу "{target}"')
@when('Я перешел на страницу "{target}"')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.NAVIGATION)
def go_to_page(context, target):
    """ Открыть указанную страницу по имени из списка локаторов. """
    go_to_url(context, LOCATORS.get(target))


@step('Я перешел по ссылке из переменной "{variable}"')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.NAVIGATION)
def go_to_url_from_variable(context, variable):
    """
        Открыть страницу, указанную в переменной.

        variable - название переменной или путь до неё, если в переменной лежит json

        Примеры:
        Я перешел по ссылке из переменной "test_link"
        Я перешел по ссылке из переменной "site > links > main"
    """
    go_to_url(context, get_from_variables(variable))


@step('Я перешел по ссылке "{link}" относительно тестового стенда')
@step('Я перешел по ссылке "{link}" относительно стенда из переменной "{stand_var}"')
@step('Я перешел по ссылке "{link}" с параметром "{link_appendix_var}" относительно тестового стенда')
@step('Я перешел по ссылке "{link}" с параметром "{link_appendix_var}" относительно стенда из переменной "{stand_var}"')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.NAVIGATION)
def go_to_relative_link(context, link, **kwargs):
    """
        Перейти по ссылке относительно стенда TEST_STAND или указанного в переменной stand_var.
        Для того, чтобы использовать ссылку с параметром (например, '/deals/89', где '89' - номер сделки,
        который генерится сам в процессе прогона тестов) нужно передать параметр через переменную окружения или
        использовать шаг для сохранения в переменную, а затем указать его вместо 'link_appendix_var'.
        Например, 'Я перешел по ссылке "/deals/" с параметром "deal_id"

        В ссылках допустим любой вариант использования слэшей: '/changelog', 'changelog', 'changelog/', '/changelog/'
    """
    go_to_url(context, get_absolute_url(link, **kwargs))


@step('Я перешел по ссылке "{url}"')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.NAVIGATION)
def go_to_url(context, url):
    """ Открыть указанный в шаге адрес. """
    if url is not None and validators.url(url):
        log.debug(f'GOING TO URL: {url}')
        context.browser.get(url)
    else:
        log.error(EM_INVALID_URL.format(url))


@then('Я убедился что URL текущей страницы содержит строку "{value}"')
@then('Я убедился что URL текущей страницы содержит значение переменной "{variable}"')
@not_available_on_platform(platforms=('android', 'ios'), field_filters={'is_webview': False}, fail=True)
@doc(Section.ASSERTION.VALUE)
def assert_url_contains(context, **kwargs):
    """ Проверить, что в текущем url содержится указанное значение. """
    value = kwargs.get('value')
    if value is None:
        variable_name = kwargs.get('variable')
        value = get_from_variables(variable_name)

    current_url = context.browser.current_url
    assert_that(current_url, contains_string(value))


@step('Я перешел в только что открывшееся окно')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.NAVIGATION)
def switch_window(context):
    """ Сделать активной новую вкладку. """
    context.browser.switch_to_window(context.browser.window_handles[-1])


@step('Я закрыл вкладку и вернулся на последнюю открытую')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.NAVIGATION)
def close_tab_return_to_last(context):
    """ Закрыть текущую вкладку и перейти на последнюю открытую в сессии. """
    context.browser.close()
    tabs = context.browser.window_handles
    context.browser.switch_to_window(tabs[-1])
    time.sleep(1)


@step('Я закрыл все вкладки кроме текущей')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.SERVICE)
def close_tabs(context):
    """ Закрыть все вкладки браузера кроме текущей """
    tabs = context.browser.window_handles
    current_tab = context.browser.current_window_handle
    for tab in tabs:
        if tab != current_tab:
            context.browser.switch_to_window(tab)
            context.browser.close()
    context.browser.switch_to_window(current_tab)


@step('Я очистил cookies')
@not_available_on_platform(platforms=('android', 'ios'), field_filters={'is_webview': False}, fail=True)
@doc(Section.ACTION.SERVICE)
def clear_cookies(context):
    """ Удалить все куки выставленные на текущем открытом домене. """
    context.browser.delete_all_cookies()


@step('Я выставил cookie с именем "{cookie_name}" и значением "{cookie_value}"')
@step('Я выставил cookie с именем из переменной "{cookie_name_var}" и значением из переменной "{cookie_value_var}"')
@not_available_on_platform(platforms=('android', 'ios'), field_filters={'is_webview': False}, fail=True)
@doc(Section.ACTION.SERVICE)
def set_cookie(context, **kwargs):
    """ Выставить cookie с именем и значением. Выставлять нужно после открытия домена, для которого она ставится. """
    cookie_name_var = kwargs.get('cookie_name_var')
    cookie_value_var = kwargs.get('cookie_value_var')

    if cookie_name_var is not None and cookie_value_var is not None:
        cookie_name = get_from_variables(cookie_name_var)
        cookie_value = get_from_variables(cookie_value_var)
    else:
        cookie_name = kwargs.get('cookie_name')
        cookie_value = kwargs.get('cookie_value')

    if cookie_name is not None and cookie_value is not None:
        cookie = {'name': cookie_name, 'value': cookie_value}
        context.browser.add_cookie(cookie)
        log.debug(f'На текущий открытый домен добавлена cookie с именем "{cookie_name}" и значением "{cookie_value}"')
    else:
        log.critical('При попытке выставить cookie переданы пустые значения')


@step('Я очистил localStorage')
@not_available_on_platform(platforms=('android', 'ios'), field_filters={'is_webview': False}, fail=True)
@doc(Section.ACTION.SERVICE)
def clear_local_storage(context):
    """ Очистить local storage. Рекомендуется использовать вместе с очисткой куки в предусловиях теста. """
    context.browser.execute_script('window.localStorage.clear();')


@step('Я очистил sessionStorage')
@not_available_on_platform(platforms=('android', 'ios'), field_filters={'is_webview': False}, fail=True)
@doc(Section.ACTION.SERVICE)
def clear_session_storage(context):
    """ Очистить session storage."""
    context.browser.execute_script('window.sessionStorage.clear();')


@given('Я установил функцию cleanup {path_to_func}')
@when('Я установил функцию cleanup {path_to_func}')
@doc(Section.ACTION.SERVICE)
def set_cleanup(context, path_to_func):
    """
    Устанавливает функцию cleanup, которая будет вызываться вне зависимости от того, провалился ли сценарий или нет.

    Если использовать @given (в блоке Background), cleanup будет вызываться после каждого сценария;
    Если использовать @when (в блоке Scenario), cleanup будет вызываться только после текущего сценария;

    path_to_func - путь до функции (<название_файла_с кастомными шагами_без_.py>.<название_функции_уборки>),
    которая будет вызываться в качестве cleanup.

    Пример: Я установил функцию cleanup zapp_steps.clean_fields
    """
    module_name, func = f'features.steps.{path_to_func}'.rsplit('.', 1)
    module = importlib.import_module(module_name)
    try:
        cleanup = getattr(module, func)
    except AttributeError:
        log.error(f'Не найдена {func} в {module}')
        raise

    context.add_cleanup(cleanup, context)
    log.debug(f'CLEANUP: Set. Will be executed after scenario: {func}')


@given('Я выбрал десктопную версию')
@when('Я выбрал десктопную версию')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.SERVICE)
def select_desktop_version(context):
    """ Установить размер окна под ноутбучное разрешение 1366х768. """
    context.browser.set_window_size(1366, 768)


@given('Я выбрал мобильную версию')
@when('Я выбрал мобильную версию')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.SERVICE)
def select_mobile_version(context):
    """ Установить размер окна 400х600 для имитации мобильного. """
    context.browser.set_window_size(400, 600)


@given('Я установил размер окна "{width}x{height}"')
@when('Я установил размер окна "{width}x{height}"')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.SERVICE)
def setup_window_size(context, width, height):
    """ Установить произвольный размер окна. """
    context.browser.set_window_size(width, height)


@step('Я обновил страницу')
@not_available_on_platform(platforms=('android', 'ios'), field_filters={'is_webview': False})
@doc(Section.ACTION.SERVICE)
def refresh_page(context):
    """ Обновить страницу в браузере. """
    context.browser.refresh()


@when('Я ввел в поле "{target}" значение "{value}"')
@when('Я ввел в "{target}" значение "{value}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.INPUT)
def send_keys(context, target, value):
    """
        Передать нажатия клавиш строки, указанной в параметре "value" в поле, указанное в словаре локаторов.
        При возникновении проблем, попробуйте переключится на посимвольный ввод.
    """
    if not value:
        log.error('Передано пустое значение на ввод')
        return

    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)

    if context.send_keys_as_granny:
        for char in value:
            element.send_keys(char)
            time.sleep(context.char_input_delay)
    else:
        element.send_keys(value)


@when('Я ввел посимвольно в поле "{target}" значение "{value}"')
@when('Я ввел посимвольно в поле "{target}" значение переменной "{variable}"')
@when('Я ввел посимвольно в "{target}" значение "{value}"')
@when('Я ввел посимвольно в "{target}" значение переменной "{variable}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.INPUT)
def send_keys_as_granny(context, target, **kwargs):
    """
        Посимвольно, с задержкой в 0,1 сек передать нажатия клавиш строки, указанной в параметре "value" в поле,
        указанное в словаре локаторов.
    """
    change_send_keys_type(context)
    value = kwargs.get('value')
    if not value:
        variable_name = kwargs.get('variable')
        value = get_from_variables(variable_name)
    send_keys(context, target, value)
    restore_send_keys_type(context)


@when('Я очистил поле "{target}"')
@then('Я очистил поле "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.INPUT)
def clear(context, target):
    """ Очистить содержимое поля ввода """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    if not context.is_mobile or context.is_webview:
        element.click()
        length = len(element.get_attribute('value'))
        element.send_keys(length * Keys.BACKSPACE)
    element.clear()


@when('Я нажал на "{target}"')
@when('Я нажал на кнопку "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def click(context, target):
    """
        Выполнить нажатие на элемент с именем из списка локаторов.
        У Selenium есть принципиальное ограничение, клики выполняются только на ближайший к пользователю слой.
        Если элемент невидимый или перекрыт другим, тест упадет и выдаст соответствущее сообщение об ошибке.
    """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    ActionChains(context.browser).move_to_element(element).perform()
    element.click()
    # safari
    # context.browser.execute_script("arguments[0].click();", element)


@when('Я нажал правой кнопкой на "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def context_click(context, target):
    """
        Выполнить нажатие правой кнопкой на элемент с именем из списка локаторов.
    """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    ActionChains(context.browser).move_to_element(element).context_click().perform()


@when('Я сделал двойной клик на "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def double_click(context, target):
    """
        Выполнить двойное нажатие на элемент с именем из списка локаторов.
        У Selenium есть принципиальное ограничение – клики выполняются только на ближайший к пользователю слой.
        Если элемент невидимый или перекрыт другим, тест упадет и выдаст соответствущее сообщение об ошибке.
    """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    ActionChains(context.browser).move_to_element(element).double_click(element).perform()

@when('Я сделал ctrl-клик на "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def ctrl_click(context, target):
    """
        Выполнить нажатие с зажатой ctrl/cmd на элемент с именем из списка локаторов.
        У Selenium есть принципиальное ограничение – клики выполняются только на ближайший к пользователю слой.
        Если элемент невидимый или перекрыт другим, тест упадет и выдаст соответствущее сообщение об ошибке.
    """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    mod_key = Keys.CONTROL
    if sys.platform == "darwin":
        mod_key = Keys.COMMAND
    ActionChains(context.browser).move_to_element(element).key_down(mod_key).click().key_up(mod_key).perform()


@when('Я нажал на клавишу {key_const}')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.PRESS_KEY)
def press_key(context, key_const):
    """
        Выполнить нажатие клавиши на клавиатуре без фокуса на элементе.
        Чтобы сфокусироваться на элементе используйте шаг 'Я нажал на ...' или 'Я навел курсор на элемент ...'
        В параметре {key_const} указывается константа с названием клавиши, например: ENTER, TAB, ESCAPE.
        Полный список доступных клавиш:
        https://selenium-python.readthedocs.io/api.html#module-selenium.webdriver.common.keys
    """
    keys_dict = vars(Keys)
    actions = ActionChains(context.browser)
    actions.send_keys(keys_dict[key_const])
    actions.perform()


@when('Я нажал на первый элемент в списке "{target}"')
@when('Я нажал на первое значение в списке "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def click_first(context, target):
    """
        Нажать на первый элемент в списке элементов, найденных по общему локатору в словаре.
        В качестве локатора надо выбирать класс или атрибут, общий для всех элементов списка.
    """
    click_certain(context, 1, target)


@when('Я нажал на последний элемент в списке "{target}"')
@when('Я нажал на последнее значение в списке "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def click_last(context, target):
    """
        Нажать на последний элемент в списке элементов, найденных по общему локатору в словаре.
        В качестве локатора надо выбирать класс или атрибут, общий для всех элементов списка.
    """
    click_certain(context, 0, target)


@when('Я нажал на {index}-й элемент в списке "{target}"')
@when('Я нажал на {index}-е значение в списке "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def click_certain(context, index, target, **kwargs):
    """
        Нажать на соответствующий по номеру элемент в списке элементов, найденных по общему локатору в словаре.
        В качестве локатора надо выбирать класс или атрибут, общий для всех элементов списка.
    """
    elements = SmartWait(context).wait_for_elements(target=target)
    element = random.choice(elements) if kwargs.get('random') is True else elements[int(index) - 1]
    context.browser.execute_script(OUTLINE, element)
    ActionChains(context.browser).move_to_element(element).perform()
    element.click()


@when('Я нажал на случайный элемент в списке "{target}"')
@when('Я нажал на случайное значение в списке "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def click_random(context, target):
    """
        Нажать на соответствующий по номеру элемент в списке элементов, найденных по общему локатору в словаре.
        В качестве локатора надо выбирать класс или атрибут, общий для всех элементов списка.
    """
    click_certain(context, -42, target, random=True)


@when('Я нажал на точку со смещением "{x},{y}" от элемента "{target}"')
@then('Я нажал на точку со смещением "{x},{y}" от элемента "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def click_coordinates(context, x, y, target):
    """
        Шаг для работы с элементами, которые нельзя найти обычными локаторами (например, яндекс карты)
        или для имитации произвольных кликов пользователя.
        Цепляемся локатором к известному элементу, в пикселях указываем смещение от левого верхнего угла
        до требуемой точки клика.
    """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    ActionChains(context.browser).move_to_element_with_offset(element, float(x), float(y)).click().perform()


@given('Я навел курсор на элемент "{target}"')
@when('Я навел курсор на элемент "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def hover_on_element(context, target):
    """ Наводит курсор на элемент для срабатывания события hover (например, раскрытие выпадающих списков). """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    ActionChains(context.browser).move_to_element(element).perform()


@when('Я выбрал "{text}" в выпадающем меню "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.CLICK)
def select_dropdown(context, text, target):
    """ Выбрать элемент из списка по тексту. В качестве локатора - css селектор, общий для всех элементов списка. """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    text_select = Select(element)
    text_select.select_by_visible_text(text)


@when('Я загрузил файл "{file_path}", в форму "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.FILE)
def file_upload_absolute(context, file_path, target):
    """ Записывает абсолютный путь до файла в поле загрузки файла. """
    element = SmartWait(context).wait_for_elements(target=target, expected=EC.presence_of_all_elements_located)[0]
    element.send_keys(file_path)


@when('Я загрузил несколько файлов "{file_list}" в форму "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.FILE)
def file_multi_upload_absolute(context, file_list, target):
    """ Записывает абсолютные пути до файлов в поле загрузки файла, разделитель - символ ";". """
    file_path_list_string = file_list.replace(';', '\n')
    element = SmartWait(context).wait_for_elements(target=target, expected=EC.presence_of_all_elements_located)[0]
    element.send_keys(file_path_list_string)


@when('Я загрузил файл по пути относительно корня установки zapp "{relative_file_path}", в форму "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.FILE)
def file_upload_relative(context, relative_file_path, target):
    """
        Записывает путь до файла относительно папки с zapp в поле загрузки файла,
        например: "features/files/file1.jpg".
    """
    current_dir = os.getcwd()
    log.debug('CURRENT DIRECTORY: %s', current_dir)
    absolute_file_path = os.path.normpath(os.path.join(current_dir, relative_file_path))
    element = SmartWait(context).wait_for_elements(target=target, expected=EC.presence_of_all_elements_located)[0]
    element.send_keys(absolute_file_path)


@when('Я загрузил несколько файлов по пути относительно корня установки zapp "{relative_path_list}" в форму "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.FILE)
def file_multi_upload_relative(context, relative_path_list, target):
    """
        Записывает пути до файлов относительно папки с zapp в поле загрузки файла, разделитель - символ ";",
        например: "features/files/file1.jpg;features/files/file2".
    """
    relative_file_path_list = relative_path_list.split(';')
    abs_file_path_list = [get_abs_file_path_from_cwd(file_path) for file_path in relative_file_path_list]
    file_list_string = '\n'.join(abs_file_path_list)
    log.debug(file_list_string)
    element = SmartWait(context).wait_for_elements(target=target, expected=EC.presence_of_all_elements_located)[0]
    element.send_keys(file_list_string)


@when('Я загрузил последний скачанный файл в форму "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.FILE)
def downloaded_file_upload(context, target):
    """
        Записывает абсолютный путь до наиболее свежего файла во временной директории ОС в поле загрузки файла.
        Пытается ожидать окончания загрузки файла в течение выставленной задержки ожидания элементов.
        Шаг работает только локально.
    """
    if REMOTE_EXECUTOR:
        log.warning(f"Шаг {context.current_step['name']} не может быть выполнен на удаленной машине")
        return

    element = SmartWait(context).wait_for_elements(target=target, expected=EC.presence_of_all_elements_located)[0]
    downloaded_file_path = get_last_downloaded_file(context)

    if downloaded_file_path is None:
        log.error(f'Не удалось найти файлы в директории {context.tempdir}')

    else:
        log.debug('UPLOADING: %s', downloaded_file_path)
        element.send_keys(downloaded_file_path)


@then('Я убедился что у последнего скачанного файла MD5 совпадает со значением "{checksum}"')
@then('Я убедился что у последнего скачанного файла MD5 совпадает со значением из переменной "{variable_name}"')
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.ACTION.FILE)
def check_md5(context, **kwargs):
    """
        Пытается ожидать окончания загрузки файла в течение выставленной задержки ожидания элементов.
        Если файл найден во временной директории - сравнивает его MD5 с переданным в тест значением.
        Шаг работает только локально.
    """
    if REMOTE_EXECUTOR:
        log.warning(f"Шаг {context.current_step['name']} не может быть выполнен на удаленной машине")
        return

    checksum = kwargs.get('checksum')

    if not checksum:
        name = kwargs.get('variable_name')
        checksum = get_from_variables(name)

    if checksum:
        file = get_last_downloaded_file(context)
        log.debug(f'Checking MD5: "{file}"')
        if file:
            generated_hash = get_md5_hash(file)
            log.debug(f'Calculated MD5: "{generated_hash}"')

            assert_that(generated_hash, equal_to(checksum))
        else:
            raise Exception('В каталоге временных загрузок нет файлов')
    else:
        raise Exception('Не найдена контрольная сумма для сравнения')


@given('Я пролистал страницу до позиции "{x}","{y}" пикселей')
@when('Я пролистал страницу до позиции "{x}","{y}" пикселей')
@not_available_on_platform(platforms=('android', 'ios'), field_filters={'is_webview': False}, fail=True)
@doc(Section.ACTION.SCROLL)
def scroll_to_coord(context, x, y):
    """ Устанавливает заданную позицию скролла. """
    if not context.is_mobile or context.is_webview:
        context.browser.execute_script("window.scrollTo(arguments[0],arguments[1])", float(x), float(y))


@when('Я пролистал страницу на "{x}","{y}" пикселей')
@not_available_on_platform(platforms=('android', 'ios'), field_filters={'is_webview': False}, fail=True)
@doc(Section.ACTION.SCROLL)
def scroll_by(context, x, y):
    """ Пролистывает страницу на указанное расстояние. """
    if not context.is_mobile or context.is_webview:
        context.browser.execute_script("window.scrollBy(arguments[0],arguments[1])", float(x), float(y))


@when('Я пролистал контейнер "{target}" на "{x}","{y}" пикселей')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@not_available_on_platform(platforms=('android', 'ios'), field_filters={'is_webview': False}, fail=True)
@doc(Section.ACTION.SCROLL)
def scroll_container_by_coord(context, target, x, y):
    """ Пролистывает элемент, которому доступна прокрутка на указанное расстояние. """
    if context.browser.name == 'internet explorer':
        log.warning(f"Шаг {context.current_step['name']} не может быть выполнен браузером Internet Explorer")
        return
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    context.browser.execute_script("arguments[0].scrollBy(arguments[1],arguments[2])", element, float(x), float(y))


@step('Я подождал {} секунд')
@step('Я подождал {} секунды')
@step('Я подождал {} секунду')
@doc(Section.ACTION.SERVICE)
def silly_wait(context, value):
    """
        Остановить выполнение теста на указанное количество секунд.
        В Firefox возможно выпадение с ошибкой connection reset by peer при ожидании 5 и больше секунд.
        В фреймворке для всех действий реализовано автоматическое ожидание загрузки элементов.
        Использовать форсированную паузу в большинстве случаев нет необходимости.
        Если тест падает по таймауту, можно в настройках изменить таймаут на значение больше чем 7 секунд по-умолчанию.
    """
    time.sleep(format_delay(value))


@when('Я нажал на один из элементов "{target}" с текстом "{text}"')
@when('Я нажал "{target}" с текстом "{text}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def click_element_with_text_multiline(context, target, text):
    """
        Нажать на первый элемент, который найден по содержащемуся в нём тексту среди всех элементов по данному
        селектору. Для уточнения расположения элемента можно указать родство с контейнером в локаторе,
        например ".my-options button" (в этом случае поиск по тексту будет произведён во всех потомках
        .my-options с тегом button). Рекомендуется использовать шаг только для прототипирования тестов
        или если невозможно создать css-локатор.
    """
    found_element = WebDriverWait(context.browser, context.smartwait_delay).until(
        lambda webdriver: (get_element_text(context, SmartWait(context).wait_for_elements(
            target=target, expected=EC.presence_of_all_elements_located), text)), message=EM_WAITING_TIMEOUT
    )
    SmartWait(context).wait_for(expected=EC.visibility_of(found_element))
    context.browser.execute_script(OUTLINE, found_element)
    ActionChains(context.browser).move_to_element(found_element).perform()
    found_element.click()


@when('Я нажал на элемент с текстом "{text}"')
@when('Я нажал на ссылку с текстом "{text}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.CLICK)
def click_link_with_text(context, text):
    """
        Нажать на первый элемент, который найден по содержащемуся в нём тексту.
        Работа тестов без локаторов принципиально нестабильна.
        Есть проблема с multiline текстом, в большинстве случаев он не находится этим шагом.
        Возможно нахождение скрытых элементов из невидимой, но подгруженной мобильной верстки.
        Рекомендуется использовать шаг только для прототипирования тестов или если невозможно создать css-локатор.
    """
    if context.is_mobile and not context.is_webview:
        element = SmartWait(context).wait_for_element(locator=f'//*[@text="{text}" or @label="{text}"]')
    else:
        element = SmartWait(context).wait_for_element(locator=f"//*[contains(text(),'{text}')]")
    context.browser.execute_script(OUTLINE, element)
    ActionChains(context.browser).move_to_element(element).perform()
    element.click()


@then('Я убедился что я нахожусь на странице с названием "{value}"')
@not_available_on_platform(platforms=('android', 'ios'), field_filters={'is_webview': False})
@doc(Section.ASSERTION.VISIBILITY)
def assert_page_name(context, value):
    """ Проверить, что заголовок текущей страницы совпадает с указанной строкой. """
    SmartWait(context).wait_for(expected=EC.title_contains(value))
    assert_that(context.browser.title, equal_to(value))


@then('Я убедился что среди элементов "{target}" отображается элемент с текстом "{text}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VISIBILITY)
def assert_visible_in_scope_with_text(context, target, text):
    """
        Проверить наличие элемента с заданным текстом среди всех элементов по данному
        селектору. Для уточнения расположения элемента можно указать родство с контейнером в локаторе,
        например ".my-options button" (в этом случае поиск по тексту будет произведён во всех потомках
        .my-options с тегом button). Рекомендуется использовать шаг только для прототипирования тестов
        или если невозможно создать css-локатор.
    """
    found = WebDriverWait(context.browser, context.smartwait_delay).until(
        lambda webdriver: get_element_text(context, SmartWait(context).wait_for_elements(
            target=target, expected=EC.presence_of_all_elements_located), text), message=EM_WAITING_TIMEOUT
    )
    SmartWait(context).wait_for(expected=EC.visibility_of(found))
    context.browser.execute_script(OUTLINE, found)


@then('Я убедился что среди элементов "{target}" не отображается элемент с текстом "{text}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VISIBILITY)
def assert_invisible_in_scope_with_text(context, target, text):
    """
        Проверить отсутствие элемента (нет в DOM либо не виден пользователю) с заданным текстом среди всех элементов
        по данному селектору. Для уточнения расположения элемента можно указать родство с контейнером в локаторе,
        например ".my-options button" (в этом случае поиск по тексту будет произведён во всех потомках
        .my-options с тегом button). Рекомендуется использовать шаг только для прототипирования тестов
        или если невозможно создать css-локатор.
    """
    try:
        found = WebDriverWait(context.browser, 2).until(lambda webdriver: get_element_text(
            context, SmartWait(context).wait_for_elements(
                target=target, expected=EC.presence_of_all_elements_located), text))
    except TimeoutException:
        log.debug(IM_ELEMENT_NOT_VISIBLE.format(f'с текстом "{text}"', target))
    else:
        SmartWait(context).wait_for_element(expected=EC.visibility_of(found), wait_method='until_not')
        assert_that(found.is_displayed(), equal_to(False))


@then('Я убедился что "{target}" отображается')
@then('Я убедился что поле "{target}" отображается')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VISIBILITY)
def assert_visible(context, target):
    """ Проверить, что указанный элемент виден для пользователя. """
    element = SmartWait(context).wait_for_element(target=target)
    assert_that(element, all_of(not_none(), not_(False)))
    context.browser.execute_script(OUTLINE, element)


@then('Я убедился что "{target}" не отображается')
@then('Я убедился что поле "{target}" не отображается')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VISIBILITY)
def assert_not_visible(context, target):
    """ Проверить, что указанный элемент невиден для пользователя. """
    element = SmartWait(context).wait_for_element(target=target, expected=EC.invisibility_of_element_located)
    assert_that(element, all_of(not_none(), not_(False)))


@then('Я убедился что элемент с текстом "{text}" отображается')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VISIBILITY)
def assert_visible_with_text(context, text):
    """ Проверить, что первый найденный по содержащемуся в нем тексту элемент виден для пользователя. """
    element = SmartWait(context).wait_for_element(locator=f"//*[contains(text(),'{text}')]")
    assert_that(element, all_of(not_none(), not_(False)))
    context.browser.execute_script(OUTLINE, element)


@then('Я убедился что элемент с текстом "{text}" не отображается')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VISIBILITY)
def assert_not_visible_with_text(context, text):
    """ Проверить, что первый найденный по содержащемуся в нем тексту элемент не виден для пользователя. """
    element = SmartWait(context).wait_for_element(
        locator=f"//*[contains(text(),'{text}')]",
        expected=EC.invisibility_of_element_located
    )

    assert_that(element, all_of(not_none(), not_(False)))


@given('Я убедился что страница прогрузилась')
@then('Я убедился что страница прогрузилась')
@not_available_on_platform(platforms=('android', 'ios', 'internet explorer'),
                           field_filters={'is_webview': False})
@doc(Section.ASSERTION.VISIBILITY)
def assert_page_load(context):
    """ Проверить, что страница полностью загрузилась"""

    def check_document_state_ready():
        return str(context.browser.execute_script("return document.readyState;")) == "complete"

    WebDriverWait(context.browser, context.smartwait_delay).until(lambda webdriver: check_document_state_ready())


@then('Я убедился что поле "{target}" пустое')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VALUE)
def assert_field_is_empty(context, target):
    """ Проверить, что указанное поле ввода не содержит значения. """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    assert_that(get_element_text_value(context, element), equal_to(''))


@then('Я убедился что поле "{target}" не пустое')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VALUE)
def assert_field_is_not_empty(context, target):
    """ Проверить, что указанное поле ввода содержит значение. """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)
    assert_that(get_element_text_value(context, element), is_not(equal_to('')))


@then('Я убедился что "{target}" доступен для нажатия')
@then('Я убедился что "{target}" доступна для нажатия')
@then('Я убедился что "{target}" доступно для нажатия')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.CLICKABILITY)
def assert_clickable(context, target):
    """ Проверить, что указанный элемент кликабелен (виден и активен). """
    element = SmartWait(context).wait_for_element(target=target, expected=EC.element_to_be_clickable)
    assert_that(element, all_of(not_none(), not_(False)))
    context.browser.execute_script(OUTLINE, element)
    assert_that(element.is_enabled(), equal_to(True))


@then('Я убедился что "{target}" не доступен для нажатия')
@then('Я убедился что "{target}" не доступна для нажатия')
@then('Я убедился что "{target}" не доступно для нажатия')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.CLICKABILITY)
def assert_not_clickable(context, target):
    """ Проверить, что указанный элемент некликабелен (виден, но не активен). """
    element = SmartWait(context).wait_for_element(target=target)
    assert_that(element, all_of(not_none(), not_(False)))
    context.browser.execute_script(OUTLINE, element)
    assert_that(element.is_enabled(), equal_to(False))


@then('Я убедился что в списке "{target}" {value} значение')
@then('Я убедился что в списке "{target}" {value} значения')
@then('Я убедился что в списке "{target}" {value} значений')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VALUE)
def assert_list_len_eq(context, target, value):
    """ Проверка что в списке элементов, найденных по общему локатору заданное количество элементов. """
    elements = SmartWait(context).wait_for_elements(target=target)
    context.browser.execute_script(OUTLINE_LIST, elements)
    assert_that(elements, has_length(int(value)))


@then('Я убедился что отображается не {comparator} {value} элементов в списке "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VALUE)
@doc(Section.ASSERTION.VISIBILITY)
def assert_list_len_gte_or_lte(context, comparator, value, target):
    """
        Проверка что в списке элементов, найденных по общему локатору не более/менее заданного количества элементов.

        comparator - 'более' ИЛИ 'менее' (помним, что добавляется отрицание и получается 'не более', 'не менее')
    """
    elements = SmartWait(context).wait_for_elements(target=target)
    context.browser.execute_script(OUTLINE_LIST, elements)
    if comparator.lower() == 'более':
        assert_that(len(elements), less_than_or_equal_to(int(value)))
    elif comparator.lower() == 'менее':
        assert_that(len(elements), greater_than_or_equal_to(int(value)))


@then('Я убедился что значение переменной "{name}" совпадает со значением элемента "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VALUE)
def variable_equals_element(context, name, target):
    """
        Сравнить значение указанного элемента на совпадение со значением переменной окружения
        или ранее сохранённой переменной через шаг "Я сохранил значение элемента"
    """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)

    value_to_compare = get_from_variables(name)

    if context.is_mobile:
        value_from_element = element.get_attribute('text')
    else:
        value_from_element = context.browser.execute_script(GET_TEXT, element)

    assert_that(value_from_element, equal_to(value_to_compare))


@then('Я убедился что значение переменной "{name}" не совпадает с элементом "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VALUE)
def variable_not_equals_element(context, name, target):
    """
        Сравнить значение указанного элемента на НЕ совпадение со значением переменной окружения
        или ранее сохранённой переменной через шаг "Я сохранил значение элемента"
    """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)

    value_to_compare = get_from_variables(name)

    value_from_element = get_element_text_value(context, element)

    assert_that(value_to_compare, not_(equal_to(value_from_element)))


@then('Я убедился что численное значение из переменной "{name}" {comparator} чем на элементе "{target}"')
@then('Я убедился что численное значение параметра "{name}" {comparator} чем на элементе "{target}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VALUE)
def variable_greater_or_less_than_element(context, name, comparator, target):
    """
        Сравнить значение указанного элемента со значением переменной окружения
        или ранее сохранённой переменной через шаг "Я сохранил значение элемента"

        Элемент и переменная должны содержать только числа
        comparator - 'больше' ИЛИ 'меньше'
    """
    element = SmartWait(context).wait_for_element(target=target)
    context.browser.execute_script(OUTLINE, element)

    text_to_compare = get_element_text_value(context, element)
    text_value = get_from_variables(name)

    if comparator.lower() == 'больше':
        assert_that(decimal.Decimal(text_value), greater_than(decimal.Decimal(text_to_compare)))
    elif comparator.lower() == 'меньше':
        assert_that(decimal.Decimal(text_value), less_than(decimal.Decimal(text_to_compare)))


def get_element_property_and_parse_value(context, **kwargs):
    element = SmartWait(context).wait_for_element(target=kwargs.get('target'), expected=EC.presence_of_element_located)
    context.browser.execute_script(OUTLINE, element)

    property_name = kwargs.get('property')
    element_property = element.get_attribute(property_name)

    value = kwargs.get('value')
    if not value:
        variable_name = kwargs.get('var')
        value = get_from_variables(variable_name)

    return element_property, value


@then('Я убедился что значение свойства "{property}" элемента "{target}" имеет значение "{value}"')
@then('Я убедился что значение свойства "{property}" элемента "{target}" совпадает со значением переменной "{var}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VALUE)
def check_element_property(context, **kwargs):
    """
        Сравнить значение свойства  элемента (или атрибута, если свойство не найдено)
        с указаным значением на предмет совпадения.
    """
    element_property, value = get_element_property_and_parse_value(context, **kwargs)
    assert_that(element_property, equal_to(value))


@then('Я убедился что значение свойства "{property}" элемента "{target}" не имеет значение "{value}"')
@then('Я убедился что значение свойства "{property}" элемента "{target}" не совпадает со значением переменной "{var}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ASSERTION.VALUE)
def check_element_property_negative(context, **kwargs):
    """
        Сравнить значение свойства  элемента (или атрибута, если свойство не найдено)
        с указаным значением на предмет НЕ совпадения.
    """
    element_property, value = get_element_property_and_parse_value(context, **kwargs)
    assert_that(element_property, not_(equal_to(value)))


@when('Я ввел в поле "{target}" сгенерированное случайно имя')
@when('Я ввел в "{target}" сгенерированное случайно имя')
@doc(Section.ACTION.RANDOM_INPUT)
def random_first_name(context, target):
    """ Подставить в поле ввода сгенерированное случайно имя. """
    random_value = generic.person.name(gender=gender)
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированное случайно отчество')
@when('Я ввел в "{target}" сгенерированное случайно отчество')
@doc(Section.ACTION.RANDOM_INPUT)
def random_middle_name(context, target):
    """ Подставить в поле ввода сгенерированное случайно отчество. """
    random_value = generic.ru.patronymic(gender=gender)
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированную случайно фамилию')
@when('Я ввел в "{target}" сгенерированную случайно фамилию')
@doc(Section.ACTION.RANDOM_INPUT)
def random_last_name(context, target):
    """ Подставить в поле ввода сгенерированную случайно фамилию. """
    random_value = generic.person.last_name(gender=gender)
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированный случайно номер телефона')
@when('Я ввел в "{target}" сгенерированный случайно номер телефона')
@doc(Section.ACTION.RANDOM_INPUT)
def random_telephone(context, **kwargs):
    """
    Подставить в поле ввода случайный номер телефона из недоступного для звонка диапазона.
    Сгенерируется неотформатированный номер вида "XXXXXXXXXX". Например, "5167874562".
    """
    random_value = generic.person.telephone(mask=f'{generate_phone_code()}#######')
    send_keys(context, kwargs.get('target'), random_value)


@when('Я ввел в поле "{target}" сгенерированный случайно адрес')
@when('Я ввел в "{target}" сгенерированный случайно адрес')
@doc(Section.ACTION.RANDOM_INPUT)
def random_address(context, target):
    """ Подставить в поле ввода случайный физический адрес (улицу и номер дома). """
    random_value = generic.address.address()
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированный случайно e-mail')
@when('Я ввел в "{target}" сгенерированный случайно e-mail')
@doc(Section.ACTION.RANDOM_INPUT)
def random_email(context, target):
    """
        Подставить в поле ввода сгенерированный случайно e-mail вида xxxxx@diroms.ru
        Доступ к почтовому ящику по запросу.
    """
    random_value = generic.person.email(domains=['@diroms.ru'])
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированную случайно дату рождения')
@when('Я ввел в "{target}" сгенерированную случайно дату рождения')
@doc(Section.ACTION.RANDOM_INPUT)
def random_birthdate(context, target):
    """ Подставить в поле ввода дату из диапазона 1930-2000г. в формате dd/mm/yyyy. """
    random_value = generic.datetime.formatted_date(fmt='%d/%m/%Y', start=1930, end=2000)
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированную случайно дату в формате "{fmt}" и диапазоне от {start} до {end} года')
@when('Я ввел в "{target}" сгенерированную случайно дату в формате "{fmt}" и диапазоне от {start} до {end} года')
@doc(Section.ACTION.RANDOM_INPUT)
def random_date(context, target, fmt, start, end):
    """ Подставить в поле ввода случайную дату из заданного диапазона в указанном формате. Пример формата: %d.%m.%Y. """
    random_value = generic.datetime.formatted_date(fmt=fmt, start=int(start), end=int(end))
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированный случайно СНИЛС')
@when('Я ввел в "{target}" сгенерированный случайно СНИЛС')
@doc(Section.ACTION.RANDOM_INPUT)
def random_snils(context, target):
    """ Подставить в поле ввода случайный валидный номер СНИЛС."""
    send_keys(context, target, generate_valid_snils())


@when('Я ввел в поле "{target}" сгенерированный случайно ИНН')
@when('Я ввел в "{target}" сгенерированный случайно ИНН')
@doc(Section.ACTION.RANDOM_INPUT)
def random_inn(context, target):
    """ Подставить в поле ввода случайный валидный номер ИНН. """
    random_value = generic.ru.inn()
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированный случайно номер транзакт')
@when('Я ввел в "{target}" сгенерированный случайно номер транзакт')
@doc(Section.ACTION.RANDOM_INPUT)
def random_tranzact_number(context, target):
    """ Подставить в поле ввода сгенерированный случайно номер транзакт. """
    random_value = generate_tranzact_number()
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированную случайно серию паспорта')
@when('Я ввел в "{target}" сгенерированную случайно серию паспорта')
@doc(Section.ACTION.RANDOM_INPUT)
def random_passport_series(context, target):
    """ Подставить в поле ввода две пары случайных цифр, разделённых пробелом. """
    random_value = generic.ru.passport_series()
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированный случайно номер паспорта')
@when('Я ввел в "{target}" сгенерированный случайно номер паспорта')
@doc(Section.ACTION.RANDOM_INPUT)
def random_passport_number(context, target):
    """ Подставить в поле ввода случайные 6 цифр. """
    random_value = generic.ru.passport_number()
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированный случайно код подразделения')
@when('Я ввел в "{target}" сгенерированный случайно код подразделения')
@doc(Section.ACTION.RANDOM_INPUT)
def random_passport_unit_code(context, target):
    """ Подставить в поле ввода случайные 6 цифр. """
    random_value = generic.ru.passport_number()
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" сгенерированные случайно серию и номер паспорта')
@when('Я ввел в "{target}" сгенерированные случайно серию и номер паспорта')
@doc(Section.ACTION.RANDOM_INPUT)
def random_passport_series_number(context, target):
    """ Подставить в поле ввода случайные 10 цифр в формате XX XX XXXXXX. """
    random_value = generic.ru.series_and_number()
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" {digit} случайно сгенерированных цифр')
@when('Я ввел в поле "{target}" {digit} случайно сгенерированные цифры')
@when('Я ввел в поле "{target}" {digit} случайно сгенерированную цифру')
@when('Я ввел в "{target}" {digit} случайно сгенерированных цифр')
@when('Я ввел в "{target}" {digit} случайно сгенерированные цифры')
@when('Я ввел в "{target}" {digit} случайно сгенерированную цифру')
@doc(Section.ACTION.RANDOM_INPUT)
def random_digits(context, target, digit):
    """ Подставить в поле ввода n случайных цифр. """
    random_values = generic.numbers.integers(start=0, end=10, n=int(digit))
    send_keys(context, target, ''.join(map(str, random_values)))


@when('Я ввел в поле "{target}" случайно сгенерированное число от {start} до {end}')
@when('Я ввел в "{target}" случайно сгенерированное число от {start} до {end}')
@doc(Section.ACTION.RANDOM_INPUT)
def random_number(context, target, start, end):
    """ Подставить в поле ввода случайно сгенерированное число в указанном интервале. """
    random_value = random.randint(int(start), int(end))
    send_keys(context, target, random_value)


@when('Я ввел в поле "{target}" одноразовый код для секрета из переменной "{otp_secret_variable}"')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@doc(Section.ACTION.INPUT)
def send_otp_code(context, target, otp_secret_variable):
    """
        Ввести в указанное поле временный код аутентификации, сгенерированный из указанного в переменной ключа секрета.

        otp_secret_variable - название переменной, в которой лежит значение секретного ключа,
        полученное при регистрации.
        Пример кода: DT7QA5745F7DI5FIELC5ECYEPYAUFDQT
    """
    secret_code = get_from_variables(otp_secret_variable)
    otp_password = str(totp(secret_code))
    log.debug(f'Сгенерирован OTP-код: {otp_password}')
    send_keys(context, target, otp_password)


@when('Я выполнил {r_type} запрос к "{url}"')
@when('Я выполнил {r_type} запрос к "{url}" c аргументами {arguments}')
@doc(Section.API)
def perform_api_request(context, r_type, url, **kwargs):
    """
        Выполнить запрос к API.

        Обязательные параметры:
        r_type - тип запроса (GET, POST, PUT, PATCH, DELETE);
        url - путь к запрашиваемому документу; можно использовать относительный (в том числе с параметром) -
        аналогично шагу для перехода по относительной ссылке.
        В этом случае в arguments (о нем ниже) нужно добавить переменные stand_var и/или link_appendix_var.
        Для того, чтобы принудительно добавить статическую часть в конец url, используйте параметр
        link_postfix. Например, link_postfix = '/' добавит слэш в конец адреса. Будьте аккуратны, валидность
        url в этом случае не проверяется и не гарантируется. Используйте режим дебага и проверяйте отправляемый запрос.

        Опционально:
        arguments - словарь из параметров, которые будут переданы в запрос (headers, params, data и другие,
        подробнее в документации к requests: https://requests.readthedocs.io/en/master).

        По умолчанию, если запрос вернулся с status_code = 4XX или 5XX, то он будет выполнен повторно через 5 секунд.
        Чтобы изменить это поведение, добавьте в передаваемый словарь arguments параметр "retry" со значениями
        количества попыток и задержкой между запросами. Например, {"retry":[3, 10]} означает что на запрос будет
        отведено 3 попытки с интервалом 10 секунд. Чтобы не использовать retry, передайте значение {"retry":[1, 0]}.

        Примеры:
        Я выполнил GET запрос к "https://echo.com/cookies/set?foo1=bar1&foo2=bar2"
        Я выполнил GET запрос к "https://echo.com/get" c аргументами {"params":{"foo1":"bar1"}, "retry":[3, 10]}
        Я выполнил GET запрос к "/get/" c аргументами {"stand_var": "api_host", "link_appendix_var": "parameter_id"}

        Примеры вызова из кастомных шагов:
        arguments = {"headers": {"Content-Type": "application/json"}, "json": {"fb": {"foo1": "bar1","foo2": "bar2"}}}
        context.execute_steps(f'''When Я выполнил POST запрос к "https://echo.com/get" c аргументами {arguments}''')

        with open('my_file.xml') as my_file:
            my_file_data = my_file.read()
        arguments = {"headers": {"Content-Type": "application/xml"}, "data": my_file_data}
        context.execute_steps(f'''When Я выполнил POST запрос к "https://echo.com/post" c аргументами {arguments}''')

        arguments = {"files": [('file', ('my_file.xml', open('my_file.xml', 'rb').read(), 'multipart/form-data'))]}
        context.execute_steps(f'''When Я выполнил POST запрос к "https://echo.com/post" c аргументами {arguments}''')

        Ответ записывается во внутреннюю переменную context.api_resp, чтобы работать с ним дальше, используйте шаг
        'Я сохранил ответ с сервера в переменную "{variable_name}"' или другие, указанные в документации в разделе
        "Работа с API"
    """
    arguments = kwargs.get('arguments', '{}')
    if kwargs.get('prepared') is not True:
        for r in (("false", "False"), ("true", "True"), ("null", "None")):
            arguments = arguments.replace(*r)
        try:
            arguments = ast.literal_eval(arguments)
            if not isinstance(arguments, dict):
                raise ValueError

        except ValueError:
            log.error(f'Произошла ошибка при обработке аргументов, отправляемых с запросом.'
                      f' Проверьте корректность данных:\n{arguments}')
            raise

    url = get_absolute_url(url, arguments.pop('stand_var', None), arguments.pop('link_appendix_var', None))
    url += arguments.pop('link_postfix', '')

    context.api_resp = Api.request(r_type, url, context.browser.get_cookies(), **arguments)


@then('Я убедился что с сервера пришел ответ без ошибки')
@doc(Section.API)
def check_api_status_code_is_ok(context):
    """ Проверить, что после запроса вернулся ответ с кодом HTTP отличным от 4XX и 5XX."""
    try:
        assert_that(context.api_resp.ok, is_(True))

    except AttributeError as e:
        log.error(f'{EM_API_REQUEST_NOT_FOUND}. {e}')


@then('Я убедился что с сервера пришел ответ {status_codes_string}')
@doc(Section.API)
def check_api_status_code(context, status_codes_string):
    """
        Проверить, что после запроса вернулся один из ожидаемых кодов состояния HTTP.
        Примеры:
        Я убедился что с сервера пришел ответ 200
        Я убедился что с сервера пришел ответ 200 или 201
        Я убедился что с сервера пришел ответ 200, 201 или 204
    """
    try:
        assert_that(str(context.api_resp.status_code), is_in(re.findall(r'\d{3}', status_codes_string)))

    except AttributeError as e:
        log.error(f'{EM_API_REQUEST_NOT_FOUND}. {e}')


@then('Я убедился что в ответе с сервера поле "{field_name}" имеет значение "{field_value}"')
@then('Я убедился что в ответе с сервера поле "{field_name}" имеет значение  переменной "{variable_name}"')
@doc(Section.API)
def check_api_resp(context, **kwargs):
    """
        Сравнить значение поля из ответа на api запрос со указанным значением или переменной

        field_name - название поля из json либо путь до него: "color" ИЛИ "fruits > banana > color".
        Если не указывать путь - вернется первое найденное значение.

        field_value - значение, с которым сравниваем.
        ИЛИ
        variable_name - имя переменной, с которой сравниваем. Можно использовать переменную окружения
        или сохраненную ранее через шаг "Я сохранил значение элемента"
    """
    field_value = kwargs.get('field_value') or get_from_variables(kwargs.get('variable_name'))
    try:
        found_field = get_from_json(context.api_resp.json(), kwargs['field_name'])
        assert_that(str(found_field), equal_to(str(field_value)))

    except json.JSONDecodeError as e:
        log.error(f'Произошла ошибка при попытке обработать json для сравнения со значением {field_value}: {e}')

    except AttributeError as e:
        log.error(f'{EM_API_REQUEST_NOT_FOUND}. {e}')


@step('Я сохранил ответ с сервера в переменную "{variable_name}"')
@doc(Section.API)
def save_api_resp(context, variable_name):
    """
        Сохранить полный ответ (JSON) на api запрос в переменную для дальнейшего использования

        variable_name - название переменной, в которую хотим сохранить значение
    """
    save_field_from_api_resp(context, None, variable_name)


@step('Я сохранил значение поля "{field_name}" из ответа с сервера в переменную "{variable_name}"')
@doc(Section.API)
def save_field_from_api_resp(context, field_name, variable_name):
    """
        Сохранить значение поля из ответа на api запрос в переменную для дальнейшего использования

        field - название поля из json либо путь до него: "color" ИЛИ "fruits > [0] > color".
        Если указать название, вернется первое найденное значение.

        variable_name - название переменной, в которую хотим сохранить значение
    """
    try:
        resp_json = context.api_resp.json()
        value = resp_json if field_name is None else get_from_json(resp_json, field_name)

        if value is not None:
            variables[variable_name] = value
            log.debug(f'Value "{value}" saved to variable "{variable_name}"')

    except json.JSONDecodeError as e:
        log.error(f'Произошла ошибка при попытке обработать json для записи в переменную {variable_name}: {e}')

    except AttributeError as e:
        log.error(f'{EM_API_REQUEST_NOT_FOUND}. {e}')


@when('Я выполнил запрос "{query}" к БД "{database_var}"')
@when('Я выполнил запрос "{query}" к БД "{database_var}" с аргументами "{args}"')
@doc(Section.DB)
def execute_query(context, query: str, database_var: str, **kwargs):
    """
    Выполнение произвольного запроса в БД

    database_var - имя переменной, содержащей строку подключения к базе данных.
    Переменная должна содержать connection string и может храниться в Vault
    или быть передана через переменные окружения.

    На текущий момент поддерживается работа только postgresql.
        Например:
            pq://user@localhost/postgres?search_path=public

    query - произвольный SQL запрос. Возможно использование prepared statement
    args - аргументы для подстановки в prepared statement, через запятую

    Результат сохраняется для дальнейшего использования в переменной контекста db_query_result

    Пример:
    @When Я выполнил запрос "SELECT 'Hello' as fld1, $1 as fld2, $2 as smth3" к БД "db_mydatabase" с аргументами "Cruel, World"
        @And Я сохранил поле "fld2" результата запроса к БД в переменную "myvar"
        @And Я сохранил поле "smth3" результата запроса к БД в переменную "myvar2"

    В результате выполнения, переменная myvar будет содержать "Cruel",
    а переменная myvar2 - "World"
    """

    query_args = []
    args = kwargs.pop('args', None)

    if args is not None:
        query_args_raw = args.split(',')
        query_args = [arg.strip() for arg in query_args_raw]

    connection_string = variables[database_var]
    res = pg_query(connection_string, query, *query_args)
    log.debug("Database Query result: %s", res)
    context.db_query_result = res


@when('Я сохранил поле "{field}" результата запроса к БД в переменную "{variable_name}"')
@doc(Section.DB)
def save_query_result(context, field: Union[int, str], variable_name: str):
    """
    Сохранение поля результата выполнения запроса в переменную

    field: Имя или номер поля в строке результата запроса
    variable_name: Имя переменной в которую необходимо сохранить результат

    Пример:
    @When Я выполнил запрос "SELECT 'Hello' as fld1, 'World' as fld2" к БД "db_mydatabase"
        @And Я сохранил поле "fld1" результата запроса к БД в переменную "myvar"

    В результате выполнения, переменная myvar будет содержать "Hello"
    """

    variables[variable_name] = context.db_query_result[field]
    log.debug('Variable "%s" saved: %s', variable_name, variables[variable_name])


@then('Я убедился что отображение элемента "{target}" не изменилось')
@then('Я убедился что отображение элемента "{target}" в состоянии "{state}" не изменилось')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.SCREENSHOT)
def compare_screenshots(context, target, **kwargs):
    """
        Сравнить скриншот элемента с эталонным, сохранённым при первом прогоне шага.
        Если эталонного скриншота ещё нет, то он просто будет создан.
        Если скриншот отличается от эталонного, то разница сохранится в отдельном изображении и тест будет провален.

        Параметр state в шаге нужен для отделения состояний одного и того же элемента друг от друга.

        Пример:
        Then Я убедился что отображение элемента "Кнопка логина" не изменилось
        When Я навел курсор на элемент "Кнопка логина"
        Then Я убедился что отображение элемента "Кнопка логина" в состоянии "hover" не изменилось

        При этом скриншоты сохранятся в двух разных папках: "Кнопка логина" и "Кнопка логина - hover".
    """
    if not SCREENSHOT_MODE:
        log.error(
            'Для корректной работы шага по сравнению отображения элемента нужно запускать ZAPP'
            ' с параметром SCREENSHOT_MODE=True'
        )
        sys.exit(1)
    element = SmartWait(context).wait_for_element(target=target)
    # Проматываем элемент до середины экрана
    context.browser.execute_script(OUTLINE, element)
    state = kwargs.get('state')
    element_name = target if not state else f'{target} - {state}'
    screenshot_name = get_screenshot_name(element_name, context)
    diff_pixels_count = compare_element_screenshots(context, element, screenshot_name)
    if diff_pixels_count == -1:
        log.info(f'Скриншот элемента "{element_name}" сохранён в качестве эталона')
    elif diff_pixels_count > 0:
        diff_count_string = get_units_case(diff_pixels_count, ('пиксель', 'пикселя', 'пикселей'))
        log.error(f'Скриншот элемента "{element_name}" отличается на {diff_pixels_count} {diff_count_string}')


@then('Я отвел курсор и убедился что отображение элемента "{target}" не изменилось')
@then('Я отвел курсор и убедился что отображение элемента "{target}" в состоянии "{state}" не изменилось')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY)
@not_available_on_platform(platforms=('android', 'ios'), fail=True)
@doc(Section.SCREENSHOT)
def cursor_out(context, target, **kwargs):
    """ Сравнение скриншотов с предварительным отводом курсора в сторону, чтобы не было лишних ховеров. """
    context.browser.execute_script(CREATE_OVERLAY)
    compare_screenshots(context, target, **kwargs)
    context.browser.execute_script(REMOVE_OVERLAY)
