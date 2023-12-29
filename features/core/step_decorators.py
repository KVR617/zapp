"""Модуль декораторов, применимых к шагам"""
from functools import wraps
from typing import Callable, Iterable, Dict, Any

from features.core.utils import log


def not_available_on_platform(platforms: Iterable[str], field_filters: Dict[str, Any] = None, fail=False) -> Callable:
    """
    Функция полностью отключает шаг для указанных платформ. Выводит предупреждение в лог

    :param platforms: Имена платформ(context.browser_.name) для которой требуется отключить шаг.
                        Нечувствительно к регистру
    :param field_filters: Дополнительный фильтр по полям контекста behave.
    :param fail: Если флаг True, будет вызвано исключение и выполнение шага будет прервано

    :raises NotImplementedError, если шаг недопустим для платформы
    """

    if field_filters is None:
        field_filters = {}

    platforms_l = (platforms.lower(),) if isinstance(platforms, str) \
        else (p.lower() for p in platforms)

    def decorator(step) -> Callable:

        @wraps(step)
        def wrapper(context, *args, **kwargs):
            try:
                if context.browser_.name.lower() in platforms_l \
                        and any(getattr(context, f) == v for f, v in field_filters.items()):

                    msg = f'Реализация шага "{context.current_step.get("name", step.__name__)}" ' \
                          f'недоступна для платформы {context.browser_.name}'

                    if fail:
                        raise NotImplementedError(msg)
                    log.warning(msg)

                    return None
            except AttributeError as ex:
                log.error('Ошибка при фильтрации шага по атрибутам %s', field_filters)
                if fail:
                    raise ex

            return step(context, *args, **kwargs)

        return wrapper

    return decorator


def allow_script_for_mobile(function):
    """
    Декоратор, включающий все скрипты и куки для мобильных тестов
    """

    @wraps(function)
    def wrapper(context, *args, **kwargs):
        try:
            context.mobile_avoids.restore_all(context)
            result = function(context, *args, **kwargs)
        finally:
            context.mobile_avoids.avoid_all(context)
        return result

    return wrapper
