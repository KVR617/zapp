Feature: Тестовая фича для работы с API

  Background:
    Given Я перешел на главную страницу
      And Я выставил cookie с именем "zapp_1" и значением "test_1"

  @api @demo
  Scenario: Работа с API внутри ZAPP
    When Я выполнил GET запрос к "https://postman-echo.com/cookies/set?zapp_3=test_3&zapp_4=test_4"
    Then Я убедился что с сервера пришел ответ 200

    When Я выполнил GET запрос к "https://postman-echo.com/basic-auth" c аргументами {"headers":{"Authorization":"Basic cG9zdG1hbjpwYXNzd29yZA=="}}
    Then Я убедился что с сервера пришел ответ без ошибки
      And Я убедился что в ответе с сервера поле "authenticated" имеет значение "True"
      And Я выставил cookie с именем из переменной "test_cookie.name" и значением из переменной "test_cookie.value"

    When Я выполнил POST запрос к "https://postman-echo.com/post" c аргументами {"headers":{"Content-Type":"application/json"}, "json":{"fruit":"banana", "color": "yellow", "eatable": true}}
      And Я сохранил значение поля "data > fruit" из ответа с сервера в переменную "post_echo_resp_fruit"
      And Я сохранил ответ с сервера в переменную "post_echo_resp_full"
    Then Я убедился что с сервера пришел ответ 200 или 201
      And Я убедился что в ответе с сервера поле "data.fruit" имеет значение "banana"
      And Я убедился что в ответе с сервера поле "data, fruit" имеет значение  переменной "post_echo_resp_fruit"
      And Я убедился что в ответе с сервера поле "data>fruit" имеет значение  переменной "post_echo_resp_full.data > fruit"
      And Я очистил cookies

    When Я выполнил PUT запрос к "https://postman-echo.com" c аргументами {"json": [{"api_host": "https://postman-echo.com/"}, {"status":"503"}], "link_postfix":"/put"}
      And Я сохранил значение поля "json" из ответа с сервера в переменную "put_echo_resp"
    Then Я убедился что с сервера пришел ответ без ошибки

    When Я выполнил GET запрос к "/status/418" c аргументами {"stand_var": "put_echo_resp.[0].api_host", "retry":[1,0]}
    Then Я убедился что с сервера пришел ответ 418

    When Я выполнил GET запрос к "/status/" c аргументами {"stand_var": "put_echo_resp.[0].api_host", "link_appendix_var": "put_echo_resp.[1].status", "retry":[2,1]}
    Then Я убедился что с сервера пришел ответ 503

    Then DEMO STEP: Я проверил апи