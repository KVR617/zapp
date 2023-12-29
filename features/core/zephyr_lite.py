import requests
import itertools
import concurrent.futures
import traceback
from collections import OrderedDict
from urllib.parse import urljoin

from features.core.constants import (
    STATUSES,
    ZEPHYR_ADD_TEST,
    ZEPHYR_EXECUTION,
    ZEPHYR_STEP_RESULT,
    ZEPHYR_RESULTS_URL,
    ZEPHYR_ATTACHMENT
)
from features.core.settings import PROJECT_KEY, REMOTE_EXECUTOR, VIDEO, VIDEO_NAME, SELENOID_UI_URL
from features.core.utils import log
from features.core.zephyr import JiraProject, JiraIssue, TestStep, TestCycle, parse_tags


def parse_background_and_scenario(data: list):
    steps, results = [], []
    last_step_kw = None

    for step in data:
        if step.keyword == 'Given':
            steps.append(f'_*Дано*_ {step.name}')
            results.append('')

        elif step.keyword == 'When':
            steps.append(f'_*Когда*_ {step.name}')
            if last_step_kw == 'When':
                results.append('')

        elif step.keyword == 'Then':
            results.append(f'_*Тогда*_\t{step.name}')

        elif step.keyword == 'And':
            if step.step_type == 'when' or step.step_type == 'given':
                steps.append(f'{steps.pop()}\n\n_*И*_\t{step.name}')

            elif step.step_type == 'then':
                results.append(f'{results.pop()}\n\n_*И*_ {step.name}')

        last_step_kw = step.keyword
    return steps, results


class ZephyrSyncLite:
    sync = True
    zephyr_run_results = {}
    scenario = None
    zephyr_label = None
    story_key = None
    bdd_steps = None
    bdd_results = None
    background_steps = None
    issue_id = None
    issue_key = None
    issues = []
    last_execution_id = None
    last_step = ''
    step_count = 0
    step_ids = {}
    step_statuses = {}
    project_version_id = None
    project_version_name = None
    test_cycle_id = None

    def __init__(self, auth):
        self.session = requests.Session()
        self.session.auth = auth
        project = JiraProject(self)
        self.project_id = project.id_
        self.project_version_id, self.project_version_name = project.version

    def _add_tests_to_cycle(self):
        resp = self._send_to_zephyr([{
            'req': self.session.post,
            'url': ZEPHYR_ADD_TEST,
            'json': dict(
                method='1',
                cycleId=self.test_cycle_id,
                issues=[issue['key'] for issue in self.issues],
                projectId=self.project_id,
                versionId=self.project_version_id
            )
        }])

        job_token = resp.json()['jobProgressToken']
        progress = 0.0
        while progress < 1.0:
            resp = self.session.get(f'{ZEPHYR_EXECUTION}jobProgress/{job_token}?type=add_tests_to_cycle_job_progress')
            progress = resp.json()['progress']

    def _create_execution(self, issue_id):
        resp = self._send_to_zephyr([
            {
                'req': self.session.post,
                'url': ZEPHYR_EXECUTION,
                'json': dict(
                    cycleId=self.test_cycle_id,
                    issueId=issue_id,
                    projectId=self.project_id,
                    versionId=self.project_version_id
                )
            }
        ])
        return next(iter(resp.json()))

    def _prepare_attachments(self, issue):
        files = []
        try:
            if path := issue['screenshot_path']:
                files.append(('file', ('screenshot.png', open(path, 'rb'), 'multipart/form-data')))

            files.append(('file', (
                'traceback.txt',
                ''.join(traceback.format_tb(issue['exception']['tb'])).encode(),
                'multipart/form-data')
            ))

            return dict(
                req=self.session.post,
                url=ZEPHYR_ATTACHMENT,
                params={'entityType': 'SCHEDULE', 'entityId': str(self.last_execution_id)},
                files=files
            )

        except Exception as e:
            log.error(f'Произошла ошибка при записи лога в файл. {e}')

    @staticmethod
    def _send_to_zephyr(data: list):
        def send(req, url, **kwargs):
            resp = req(url, **kwargs)
            resp.raise_for_status()
            return resp

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            for future in concurrent.futures.as_completed(
                (executor.submit(send, **values_dict) for values_dict in data),
                timeout=2
            ):
                try:
                    return future.result()
                except Exception as e:
                    log.error(f'Ошибка при отправке результатов в Zephyr [SL-S1]: {e}')

    def scenario_parser(self, scenario, feature, tags, scenario_seed):
        self.scenario = scenario
        self.zephyr_label, self.story_key = parse_tags(tags)
        if not self.zephyr_label:
            log.error(f'Синхронизация с Zephyr невозможна; Сценарий "{scenario.name}" '
                      f'должен быть отмечен тэгом @ZephyrLabel/{PROJECT_KEY}/{scenario_seed}')
            return
        background_steps = feature.background.steps if feature.background is not None else []
        self.bdd_steps, self.bdd_results = parse_background_and_scenario(background_steps + scenario.steps)

    def every_scenario(self, scenario, screenshot_path, duration):
        if not self.zephyr_label:
            return

        issue = JiraIssue(self)
        if not issue.issue:
            self.sync = True
            return

        self.issue_id = issue.id_
        self.issue_key = issue.key

        if scenario.exception is not None:
            msg = str(scenario.exception)
            scenario.exception = msg[:100] + (msg[100:] and '...')

        self.issues.append(dict(
            id=issue.id_,
            key=issue.key,
            scenario_name=scenario.name,
            status=scenario.status.name,
            screenshot_path=screenshot_path,
            exception=dict(msg=scenario.exception, tb=scenario.exc_traceback, ts=duration)
        ))

        issue.sync(self)
        issue.link(self)

        self.step_ids[scenario.name] = TestStep.ids(self)

    def every_step(self, step, scenario):
        if self.step_statuses.get(scenario.name) is None:
            self.step_statuses[scenario.name] = OrderedDict()
            self.step_count = 0

        if step.filename != scenario.filename:
            return

        if step.keyword == 'When' or step.keyword == 'Given':
            self.step_count += 1

        statuses = self.step_statuses[scenario.name].get(self.step_count, [])
        statuses.append(int(STATUSES[step.status.name]))
        self.step_statuses[scenario.name][self.step_count] = statuses

        if step.status.name == 'failed':
            scenario.exception, scenario.exc_traceback = step.exception, step.exc_traceback

    def synchronize(self):
        if not self.issues:
            return {}

        self.test_cycle_id = TestCycle.create(self)
        if self.test_cycle_id is None:
            return {}

        self._add_tests_to_cycle()

        data = []

        for issue in self.issues:
            issue['execution_id'] = self.last_execution_id = self._create_execution(issue['id'])
            cmt = f'Запись прохождения: {SELENOID_UI_URL}video/{VIDEO_NAME}\n' if REMOTE_EXECUTOR and VIDEO else ''
            cmt += f"Время ошибки на видео: ~{issue['exception']['ts']}" if cmt and issue['status'] == 'failed' else ''

            data.append({
                'req': self.session.put,
                'url': f'{urljoin(ZEPHYR_EXECUTION, str(self.last_execution_id))}/execute',
                'json': dict(
                    status=STATUSES.get(issue['status']),
                    comment=cmt
                )
            })

            if issue['status'] == 'failed':
                data.append(self._prepare_attachments(issue))

            for step_id, step_status in itertools.zip_longest(
                self.step_ids[issue['scenario_name']],
                self.step_statuses[issue['scenario_name']].values(),
                fillvalue=STATUSES['untested']
            ):
                step_status = str(max(step_status))
                data.append({
                    'req': self.session.post,
                    'url': ZEPHYR_STEP_RESULT,
                    'json': dict(
                        stepId=step_id,
                        issueId=issue['id'],
                        executionId=issue['execution_id'],
                        status=step_status,
                        comment=issue['exception']['msg'] if step_status == '2' else ''
                        )
                })

            self.zephyr_run_results[issue['scenario_name']] = f"{ZEPHYR_RESULTS_URL}{issue['execution_id']}"

        self._send_to_zephyr(data)

        log.info(f'Результаты выполнения сценариев:')
        for scenario_name, zephyr_result_link in self.zephyr_run_results.items():
            log.info(f'\t"{scenario_name}": {zephyr_result_link}')

        return self.zephyr_run_results
