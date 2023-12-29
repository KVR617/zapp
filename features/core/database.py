"""Работа с базами данных в шагах"""
from typing import Union

import postgresql


def execute_query(connection_string: str, query: str, *args) -> Union[list, dict]:
    """
    Выполняет запрос к базе данных и возвращает результаты запроса
    :param connection_string: Строка подключения к базе данных
        Значение должно представлять собой connection string:
            protocol://user:password@host:port/database?[driver_setting]=value&server_setting=value

        Например:
            pq://user@localhost/postgres?search_path=public

        В текущий момент поддерживаться только postgresql (pq)

    :param query: Запрос к базе данных
        Запрос может быть параметризованным с использованием стандартных позиционных аргументов.
        Например:
            "SELECT $1"

    :param args: Позиционные параметры для запроса
    :return: Возвращает первую строку из запроса в виде Dict-like объект для именованных полей ()
        и List-like объект для неименованных
    """

    with postgresql.open(connection_string) as connection:
        res = connection.prepare(query).first(*args)

    return res
