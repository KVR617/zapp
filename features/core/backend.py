"""Модуль взаимодействия с zapp-backend"""

from typing import Dict
from urllib.parse import urljoin

import requests

from features.core import settings
from features.core.constants import ZAPP_BACKEND_URL, ZAPP_FRONTEND_URL


class ZappBackend:
    """Класс реализующий взаимодействие с zapp-backend"""

    def __init__(self):
        self.session_id = settings.SESSION_ID
        self.session_running = bool(settings.SESSION_ID)
        self.backend_url = ZAPP_BACKEND_URL.get(settings.BACKEND_ORIGIN, ZAPP_BACKEND_URL['PROD'])
        self.frontend_url = ZAPP_FRONTEND_URL.get(settings.BACKEND_ORIGIN, ZAPP_FRONTEND_URL['PROD'])

    def start_session(self, env_type: str, project: str, run_params: Dict[str, str]) -> str:
        """
        Метод регистрирует запуск локальной сессии в zapp-backend

        :param env_type: тип окружения
        :param project: наименование проекта
        :param run_params: параметры запуска ZAPP
        :return: id сессии

        :raises:
            ZappBackendSessionException если сессия уже запущена
            RequestException при ошибках запроса к бекенду
        """

        if self.session_running:
            raise ZappBackendSessionException(f'Session {self.session_id} already started')

        payload = {
            'env_type': env_type,
            'bb_project': project,
            'run_params': run_params,
        }

        resp_json = self._post('api/v1/sessions/run_local', json=payload)
        self.session_id = resp_json.get('zapp_session_id')
        self.session_running = True

        return self.session_id

    def update_session(self, **kwargs):
        """
        Метод выполняет обновление параметров запущенной сессии.
        Может быть использован для передачи промежуточных состояний сессии.

        :param kwargs: любые параметры сессии
        :returns: json-ответ бекенда
        :raises:
            ZappBackendSessionException если сессия уже остановлена
            RequestException при ошибках запроса к бекенду
        """

        if not self.session_running:
            raise ZappBackendSessionException(f'Session {self.session_id} already stopped')

        return self._patch(f'api/v1/sessions/{self.session_id}/add_results', json=kwargs)

    def stop_session(self, **kwargs):
        """
        Метод регистрирует завершение локальной сессии в zapp-backend с отправкой результатов

        :param kwargs:
            tests_passed: завершились ли все тесты успехом
            output_json: Результаты тестов
            logs: plaintext логи ZAPP
            video_url: url для просмотра записи удаленного прогона
            zephyr_sync_results: Результаты Zephyr
            export_variables: Безопасные для отображения переменные запуска

        :raises:
            ZappBackendSessionException если сессия уже остановлена
            RequestException при ошибках запроса к бекенду
        """

        if not self.session_running:
            raise ZappBackendSessionException(f'Session {self.session_id} already stopped')

        payload = {
            'infra_ok': True,
            'output_json': kwargs.pop('output_json', {}),
            'zephyr_sync_results': kwargs.pop('zephyr_sync_results', {}),
            'export_variables': kwargs.pop('export_variables', {}),
        }

        payload.update(kwargs)

        self.update_session(**payload)
        self.session_running = False

    @property
    def session_url(self) -> str:
        """
        Возвращает url для просмотра запуска текущей сессии на zapp-frontend

        :raises ZappBackendSessionException если сессия не зарегистрирована
        """

        if not self.session_running:
            raise ZappBackendSessionException('No session registered')

        return urljoin(self.frontend_url, f'test-runs/{self.session_id}')

    def _request(self, method, path, **request_kwargs):
        url = urljoin(self.backend_url, path)
        req = requests.request(method, url, **request_kwargs)
        req.raise_for_status()

        return req.json()

    def _post(self, path, **request_kwargs):
        return self._request('POST', path, **request_kwargs)

    def _put(self, path, **request_kwargs):
        return self._request('PUT', path, **request_kwargs)

    def _patch(self, path, **request_kwargs):
        return self._request('PATCH', path, **request_kwargs)


class ZappBackendException(RuntimeError):
    """Generic Backend Exception"""


class ZappBackendSessionException(ZappBackendException):
    """Ошибка взаимодействия с сессией"""
