from features.steps.steps_library import *
from behave import *

TESTFILE = 'api_test_file.xml'


@then('DEMO STEP: Я проверил ввод данных')
def check_data(context):
    context.execute_steps(
        """
        When Я нажал на "Проверочное поле"
        Then Я убедился что поле "Проверочное поле" не пустое
        When Я очистил поле "Поле ввода"
        """
    )


@then('DEMO STEP: Я проверил ввод данных во фрейме')
def check_iframe_data(context):
    context.execute_steps(
        """
        When Я нажал на "Проверочное поле во фрейме"
        Then Я убедился что поле "Проверочное поле во фрейме" не пустое
        When Я очистил поле "Поле ввода во фрейме"
        """
    )


@then('DEMO STEP: Я проверил загрузку файла на zapp-site')
def check_upload(context):
    assert_that(context.browser.execute_script("return document.body.innerHTML;"), equal_to('ok'))


@step('DEMO STEP: Я проверил апи')
def test_api_through_custom_steps(context):
    with open(TESTFILE, 'w') as output:
        output.write("""<?xml version="1.0" encoding="UTF-8"?>
        <note>
          <to>You</to>
          <from>ZAPP</from>
          <heading>Reminder</heading>
          <body>Don't forget to update your tests!</body>
        </note>""")

    post_template = """
        When Я выполнил POST запрос к "https://postman-echo.com/post" c аргументами {arguments}
        Then Я убедился что с сервера пришел ответ без ошибки
    """

    arguments = {'json': {'foobar': {'foo1': 'bar1', 'foo2': 'bar2'}}}
    context.execute_steps(post_template.format(arguments=arguments))

    arguments = {"files": [('file', (TESTFILE, open(TESTFILE, 'rb').read(), 'multipart/form-data'))]}
    context.execute_steps(post_template.format(arguments=arguments))

    with open(TESTFILE) as my_file:
        my_file_data = my_file.read()
    arguments = {"headers": {"Content-Type": "application/xml"}, "data": my_file_data}
    context.execute_steps(post_template.format(arguments=arguments))


# cleanup функция, вызываемая через шаг 'Я установил cleanup ...'
# для вызова функции только при падении теста обернуть в условие "if str(context.scenario.status) == 'Status.failed':"
def clean_fields(context):
    context.execute_steps(
        """
        Then Я очистил поле "Логин"
        Then Я очистил поле "Пароль"
        Then Я очистил поле "Поле ввода"
        When Я нажал на "Пароль"
        """
    )
    log.debug('CLEANUP: Done')


# Пример составного шага с поддержкой обработки значений и переменных
@when('DEMO STEP: Я нашёл проект с названием "{project_name}"')
@when('DEMO STEP: Я нашёл проект с названием из переменной "{project_name_var}"')
def search_project(context, **kwargs):
    project_name_var = kwargs.get('project_name_var')

    if project_name_var is not None:
        project_name = get_from_variables(project_name_var)
    else:
        project_name = kwargs.get('project_name')

    context.execute_steps(
        f"""
        When Я ввел в поле "Поиск по проектам" значение "{project_name}"
        And Я нажал на кнопку "Тестовый проект"
        """
    )
