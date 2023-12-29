from appium.common.exceptions import NoSuchContextException
from features.core.settings import MOBILE_APP_PACKAGE
from features.core.mobiles import *
from features.steps.steps_library import *


@given('Я переключился на контекст вебвью')
@when('Я переключился на контекст вебвью')
@retry(retry_on_exception=escaping_exceptions, stop_max_delay=RETRY_DELAY, wait_fixed=2000, stop_max_attempt_number=3)
@doc(Section.ACTION.MOBILE)
def mobile_switch_to_webview_context(context):
    """
        Перейти в управление элементами внутри вебвью.
    """
    webview_context = f'WEBVIEW_{MOBILE_APP_PACKAGE}'
    context_list = context.browser.contexts
    log.debug(context_list)

    if webview_context in context_list:
        context.browser.switch_to.context(webview_context)
        context.is_webview = True
    else:
        raise NoSuchContextException

    context.mobile_avoids.restore_all(context)


@given('Я переключился на основной контекст')
@when('Я переключился на основной контекст')
@doc(Section.ACTION.MOBILE)
def mobile_return_to_default_context(context):
    """
        Вернуться в контекст нативного мобильного приложения.
        Нативный контекст является контекстом по умолчанию.
    """
    context.browser.switch_to.context('NATIVE_APP')
    context.is_webview = False
    context.mobile_avoids.avoid_all(context)


@when('Я нажал системную кнопку назад')
@doc(Section.ACTION.MOBILE)
def mobile_system_back(context):
    """
        Нажать на системную кнопку "Назад".
    """
    context.browser.press_keycode(4)


@when('Я свайпнул экран с "{start_x}, {start_y}", до "{end_x}, {end_y}"')
@doc(Section.ACTION.MOBILE)
def mobile_swipe_by_coordinates(context, start_x, start_y, end_x, end_y):
    """
        Скролл экрана по координатам. Использовать с осторожностью. В случае если
        координаты находятся за пределами физического экрана - будет ошибка

        Args:
            start_x: x-координата начала движения
            start_y: y-координата начала движения
            end_x: x-координата конца движения
            end_y: y-координата конца движения
    """
    context.browser.swipe(start_x, start_y, end_x, end_y)


@when('Я свайпнул экран вверх')
@doc(Section.ACTION.MOBILE)
def mobile_swipe_up(context):
    """
        Скролл экрана вверх. Листает примерно 1/2 экрана.
    """
    screen_dimensions = context.browser.get_window_size()
    dim_x = screen_dimensions["width"]
    dim_y = screen_dimensions["height"]
    mobile_swipe_by_coordinates(context, int(dim_x * 0.5), int(dim_y * 0.4), int(dim_x * 0.5), int(dim_y * 0.8))


@when('Я свайпнул экран вниз')
@doc(Section.ACTION.MOBILE)
def mobile_swipe_down(context):
    """
        Скролл экрана вниз. Листает примерно 1/2 экрана.
    """
    screen_dimensions = context.browser.get_window_size()
    dim_x = screen_dimensions["width"]
    dim_y = screen_dimensions["height"]
    mobile_swipe_by_coordinates(context, int(dim_x * 0.5), int(dim_y * 0.8), int(dim_x * 0.5), int(dim_y * 0.4))


@when('Я свайпнул экран относительно элемента "{target}" на "{number}" пикселей вправо')
@doc(Section.ACTION.MOBILE)
def android_swipe_from_elem_right_fix_coordinates(context, target, number):
    """
        Скроллит экран относительно элемента на n пикселей вправо

         Args:
            target: элемент от которого необходимо произвести свайп
            number: количество пикселей на которое нужно произвести свайп
    """
    element = SmartWait(context).wait_for_element(target=target)
    element_center_x = element.location['x'] + element.size['width'] / 2
    element_center_y = element.location['y'] + element.size['height'] / 2
    mobile_swipe_by_coordinates(context, element_center_x, element_center_y, int(element_center_x - int(number)),
                                element_center_y)


@when('Я свайпнул экран относительно элемента "{target}" на "{number}" пикселей влево')
@doc(Section.ACTION.MOBILE)
def android_swipe_from_elem_left_fix_coordinates(context, target, number):
    """
        Скроллит экран относительно элемента на n пикселей влево

        Args:
            target: элемент от которого необходимо произвести свайп
            number: количество пикселей на которое нужно произвести свайп
    """
    element = SmartWait(context).wait_for_element(target=target)
    element_center_x = element.location['x'] + element.size['width'] / 2
    element_center_y = element.location['y'] + element.size['height'] / 2
    mobile_swipe_by_coordinates(context, element_center_x, element_center_y, int(element_center_x + int(number)),
                                element_center_y)


@when('Я свайпнул экран относительно элемента "{target}" на "{number}" пикселей вверх')
@doc(Section.ACTION.MOBILE)
def android_swipe_from_elem_up_fix_coordinates(context, target, number):
    """
        Скроллит экран относительно элемента на n пикселей вверх

        Args:
            target: элемент от которого необходимо произвести свайп
            number: количество пикселей на которое нужно произвести свайп
    """
    element = SmartWait(context).wait_for_element(target=target)
    element_center_x = element.location['x'] + element.size['width'] / 2
    element_center_y = element.location['y'] + element.size['height'] / 2
    mobile_swipe_by_coordinates(context, element_center_x, element_center_y, element_center_x,
                                int(element_center_y - int(number)))


@when('Я свайпнул экран относительно элемента "{target}" на "{number}" пикселей вниз')
@doc(Section.ACTION.MOBILE)
def android_swipe_from_elem_down_fix_coordinates(context, target, number):
    """
        Скроллит экран относительно элемента на n пикселей вниз

        Args:
            target: элемент от которого необходимо произвести свайп
            number: количество пикселей на которое нужно произвести свайп
    """
    element = SmartWait(context).wait_for_element(target=target)
    element_center_x = element.location['x'] + element.size['width'] / 2
    element_center_y = element.location['y'] + element.size['height'] / 2
    mobile_swipe_by_coordinates(context, element_center_x, element_center_y, element_center_x,
                                int(element_center_y + int(number)))


@when('Я сохранил значение мобильного элемента "{target}" в переменную "{name}"')  # deprecated
@doc(Section.ACTION.MOBILE)
def mobile_save_variable(context, target, name):
    """
        Сохранить значение мобильного элемента в указанную переменную. Важно: регистр букв не учитывается.

        Args:
            target: элемент, текст которого необходимо сохранить
            name: название переменной в которую необходимо сохранить
    """

    example = f'Я сохранил значение элемента "{target}" в переменную "{name}"'
    throw_deprecated_warn(context, example, 'save_test_variable')

    save_test_variable(context, target, name)


@when('Я скрыл клавиатуру')
@doc(Section.ACTION.MOBILE)
def mobile_android_hide_keyboard(context):
    """
        Скрытие нативной клавиатуры в случае ее наличия на экране
    """
    log.debug(f'Статус нативной клавиатуры: {context.browser.is_keyboard_shown()}')
    context.browser.hide_keyboard()


@then('Я убедился что нативная клавиатура отображается')
@doc(Section.ACTION.MOBILE)
def mobile_android_is_keyboard_shown(context):
    """
        Проверка наличия нативной клавиатуры на экране
    """
    log.debug(f'Статус нативной клавиатуры: {context.browser.is_keyboard_shown()}')
    assert_that(context.browser.is_keyboard_shown(), equal_to(True))


@then('Я убедился что нативная клавиатура не отображается')
@doc(Section.ACTION.MOBILE)
def mobile_android_is_keyboard_unshown(context):
    """
        Проверка отсутствия нативной клавиатуры на экране
    """
    log.debug(f'Статус нативной клавиатуры: {context.browser.is_keyboard_shown()}')
    assert_that(context.browser.is_keyboard_shown(), equal_to(False))


@then('Я убедился что тестируемое приложение не активно')
@then('Я убедился что приложение "{package_name}" не активно')
def check_is_app_not_active(context, package_name=MOBILE_APP_PACKAGE):
    """
        Проверка на то что приложение не находится на переднем плане

        Args:
            package_name - название пакета проверяемого приложения. По умолчанию com.example.application.debug
    """
    SmartWait(context).wait_for(expected=AppNotInForeground(package_name))


@then('Я убедился что тестируемое приложение активно')
@then('Я убедился что приложение "{package_name}" активно')
def check_is_app_active(context, package_name=MOBILE_APP_PACKAGE):
    """
        Проверка на то что приложение активно, и находится на переднем плане. Во время ожидания делает попытку вызвать его в foreground

        Args:
            package_name - название пакета проверяемого приложения. По умолчанию com.example.application.debug
    """
    SmartWait(context).wait_for(expected=AppStateIs(4, package_name))
