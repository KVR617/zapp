import sys
import requests
import datetime


from nested_lookup import nested_lookup

import version
from features.core import settings
from features.core.utils import log


class Metrics:
    def __init__(self, **kwargs):
        self.metrics = kwargs
        self.record = 'main'
        self.now = datetime.datetime.now()

    @property
    def _fields(self):
        return dict(
            time_length=(self.now - self.metrics['start_date']).total_seconds() * 1000,
            tests_count=self.metrics['all_tests_count'],
            failed_tests_count=self.metrics['failed_tests_count']
        )

    @property
    def _tags(self):
        return dict(
            BROWSER=self.metrics['browser_name'],
            BROWSER_VERSION=self.metrics['browser_version'],
            DEBUG=settings.DEBUG,
            DEPLOY=settings.DEPLOY,
            ENV=settings.ENV,
            FORCE_DELAY=settings.FORCE_DELAY,
            LOCAL_SCREENSHOTS=settings.LOCAL_SCREENSHOTS,
            PROJECT_KEY=settings.PROJECT_KEY,
            RECORD=self.record,
            REMOTE_EXECUTOR=settings.REMOTE_EXECUTOR,
            RUN_TYPE=settings.RUN_TYPE,
            SCREENSHOT_MODE=settings.SCREENSHOT_MODE,
            SMARTWAIT_DELAY=settings.SMARTWAIT_DELAY,
            STAND=settings.STAND,
            ZEPHYR_USE=settings.ZEPHYR_USE,
            VERSION_NAME=settings.VERSION_NAME,
            ZAPP_VERSION=version.ZAPP_VERSION,
            PYTHON_VERSION=f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
            RUN_SEED=self.metrics['run_seed']
        )

    def send(self):
        if not settings.INFLUX_USE:
            log.debug(f'INFLUX_USE: {settings.INFLUX_USE}')
            return

        Influx(self._tags, self._fields).send(self.record)

        if self.metrics['exceptions']:
            self.send_exceptions()

        if self.metrics['deprecated_steps']:
            self.send_deprecated()

    def send_exceptions(self):
        self.record = 'exception'
        tags = self._tags
        tags['RECORD'] = self.record
        for exception in self.metrics['exceptions']:
            tags['EXCEPTION'] = exception
            Influx(tags, self._fields).send(self.record)

    def send_deprecated(self):
        self.record = 'deprecated_step'
        tags = self._tags
        tags['RECORD'] = self.record
        func_names = set(nested_lookup('func_name', self.metrics['deprecated_steps']))
        for fn in func_names:
            tags['DEPRECATED_STEP'] = fn
            Influx(tags, self._fields).send(self.record)


class Influx:
    def __init__(self, tags, fields):
        self.influx_url = f'{settings.INFLUX_HOST}:{settings.INFLUX_PORT}/write?db={settings.INFLUX_DB}'
        self.data_string = self.build_data_string(tags, fields)

    def send(self, record='main'):
        try:
            resp = requests.post(self.influx_url, data=self.data_string.encode('utf-8'))
            resp.raise_for_status()
            log.debug(f'METRICS: record={record}, status=sent({resp.status_code})')

        except requests.exceptions.RequestException as e:
            log.error(f'METRICS: record={record}, status=fail({e})')

    @staticmethod
    def build_data_string(tags, fields, measurement='zapp_test_run', timestamp=None):
        tags_string = ','.join('{}={}'.format(k, str(v)) for (k, v) in tags.items() if v)
        fields_string = ','.join('{}={}'.format(k, v) for (k, v) in fields.items() if v)
        timestamp_string = ' ' + timestamp if timestamp else ''
        return f'{measurement},{tags_string} {fields_string}{timestamp_string}'
