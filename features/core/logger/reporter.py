"""Модуль реализаций Behave Reporter"""

from behave.reporter.base import Reporter
from features.core.backend import ZappBackend
from features.core.logger import logger


class ZappReporter(Reporter):
    """Behave Reporter для сбора статистики ZAPP и отправки на backend"""

    def __init__(self, config, backend: ZappBackend):
        self.backend = backend
        self.export_data = {}

        super().__init__(config)

    def feature(self, feature):
        pass

    def end(self):
        if self.backend.session_running:
            if 'zapp_raw_logs' in self.export_data:
                self.export_data['zapp_raw_logs'] = logger.get_log()

            self.backend.stop_session(**self.export_data)
