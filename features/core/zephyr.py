import requests
import traceback

from datetime import datetime
from babel.dates import format_datetime
from urllib.parse import urljoin

from features.core.settings import ENV, DEPLOY, PROJECT_KEY, VERSION_NAME
from features.core.constants import (
    JIRA_DATE_FORMAT,
    JIRA_PROJECT,
    JIRA_ISSUE,
    JIRA_ISSUE_VIEW,
    JIRA_ISSUE_LINK,
    JIRA_SEARCH_TEST,
    ZEPHYR_TEST_STEP,
    ZEPHYR_TEST_CYCLE,
    ZEPHYR_EXECUTION,
    ZEPHYR_STEP_RESULT,
    ZEPHYR_ADD_TEST,
    ZEPHYR_ATTACHMENT,
    ZEPHYR_RESULTS_URL,
    STATUSES,
)
from features.core.utils import log


def get_ids(data):
    ids = []
    try:
        for i in data:
            ids.append(i['id'])

    except (TypeError, KeyError) as e:
        log.error(f'Ошибка при обработке данных из Jira: {e}')

    finally:
        return ids


def format_bdd(steps, results):
    while len(steps) > len(results):
        results.append('')
    while len(steps) < len(results):
        steps.append('')
    return {str(i): {'step': steps[i], 'result': results[i]} for i in range(len(steps))}


def format_zephyr(data):
    try:
        return {str(i): {'step': data[i].get('step'), 'result': data[i].get('result')} for i in range(len(data))}

    except KeyError as e:
        log.error(f'Ошибка при обработке шагов теста из Jira: {e}')


def parse_zephyr(data):
    steps = []
    results = []
    for test_step in data:
        steps.append(test_step.get('step'))
        results.append(test_step.get('result'))

    return steps, results


def parse_background(background):
    background_steps = 'Background:\n\n'
    for step in background:
        background_steps += f'{step.keyword} {step.name}\n'
    return background_steps


def parse_tags(tags):
    zephyr_label = None
    story_key = None
    for tag in tags:
        if tag.find('ZephyrLabel') > -1:
            zephyr_label = tag
        if tag.find('JiraStory') > -1:
            _tag = tag.split('/')
            if len(_tag) > 1:
                story_key = _tag[1]
    return zephyr_label, story_key


def parse_scenario(scenario_steps):
    steps = []
    results = []

    for step in scenario_steps:
        if step.keyword == 'When':
            steps.append(f'*{step.keyword}* {step.name}')

        elif step.keyword == 'Then':
            results.append(f'*{step.keyword}* {step.name}')

        elif step.keyword == 'And':
            if step.step_type == 'when':
                steps.append(f'{steps.pop()}\n\n*{step.keyword}* {step.name}')

            elif step.step_type == 'then':
                results.append(f'{results.pop()}\n\n*{step.keyword}* {step.name}')

    return steps, results


def parse_step(context, step):
    if step.keyword == 'When':
        return f'*{step.keyword}* {step.name}'

    elif step.keyword == 'And' and step.step_type == 'when':
        return f'{context.last_step}\n\n*{step.keyword}* {step.name}'

    else:
        return ''


def interrupt_sync(context):
    if context.last_execution_id:
        Execution.update_execution_status(context, status='blocked')

    context.sync = False
    log.warning('Синхронизация с Zephyr прервана')


class TestCycle:
    @classmethod
    def create(cls, context):
        if not context.sync:
            return

        payload = {
            'description': 'Тестовый цикл был создан автоматически с помощью ZAPP',
            'environment': ENV,
            'name': f"{ENV} {format_datetime(datetime.now(), format='HH:mm d MMMM yyy', locale='ru')}",
            'startDate': format_datetime(datetime.now(), format=JIRA_DATE_FORMAT, locale='ru'),
            'projectId': context.project_id,
            'versionId': context.project_version_id,
            'build': context.project_version_name
        }

        try:
            resp = context.session.post(ZEPHYR_TEST_CYCLE, json=payload)
            resp.raise_for_status()
            return TestCycle.id_(resp.json(), context)

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [TC-C1] {e}')
            interrupt_sync(context)

    @staticmethod
    def id_(test_cycle, context):
        test_cycle_id = test_cycle.get('id')
        if not test_cycle_id:
            interrupt_sync(context)

        return test_cycle_id

    @classmethod
    def fill(cls, context):
        if not context.sync:
            return

        payload = {
            'cycleId': context.test_cycle_id,
            'issues': [context.issue_key],
            'projectId': context.project_id,
            'versionId': context.project_version_id
        }

        try:
            resp = context.session.post(ZEPHYR_ADD_TEST, json=payload)
            resp.raise_for_status()

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [TC-F1] {e}')
            interrupt_sync(context)

    @classmethod
    def update(cls, context):
        payload = {
            'id': context.test_cycle_id,
            'endDate': format_datetime(datetime.now(), format=JIRA_DATE_FORMAT, locale='ru')
        }

        try:
            test_cycle = context.session.put(ZEPHYR_TEST_CYCLE, json=payload)
            test_cycle.raise_for_status()

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [TC-U3] {e}')
            interrupt_sync(context)

        else:
            log.debug(f"TEST CYCLE {test_cycle.text}")


class Execution:
    @staticmethod
    def last_execution_id(context):
        if not context.sync:
            return

        params = {
            'cycleId': context.test_cycle_id,
            'projectId': context.project_id,
            'versionId': context.project_version_id
        }

        try:
            resp = context.session.get(ZEPHYR_EXECUTION, params=params)
            resp.raise_for_status()
            executions = resp.json().get('executions')
            if not executions:
                log.error(f'Ошибка при выполнении запроса к Zephyr. Убедитесь, что тест {context.issue_key} '
                          f'находится в проекте {PROJECT_KEY} или измените метку теста')
                interrupt_sync(context)
                return

            execution_ids = get_ids(executions)
            log.debug('EXECUTION IDS: %s', execution_ids)
            last_execution_id = max(execution_ids) if execution_ids else None
            return last_execution_id

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [EX-I2] {e}')
            interrupt_sync(context)

    @classmethod
    def update(cls, context, payload):
        if not context.sync:
            return

        try:
            resp = context.session.put(
                f'{urljoin(ZEPHYR_EXECUTION, str(context.last_execution_id))}/execute', json=payload)
            resp.raise_for_status()

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [EX-U3] {e}')
            interrupt_sync(context)

    @staticmethod
    def update_execution_status(context, status):
        Execution.update(context, payload={'status': STATUSES.get(status), 'comment': context.background_steps})

    @staticmethod
    def assign(context):
        Execution.update(
            context,
            payload={"assigneeType": "assignee", "assignee": context.project_lead, "changeAssignee": True}
        )


class TestStep:
    @classmethod
    def ids(cls, context):
        if not context.sync:
            return

        try:
            resp = context.session.get(urljoin(ZEPHYR_TEST_STEP, context.issue_id))
            resp.raise_for_status()
            ids_json = resp.json()
            ids_list = ids_json.get(next(iter(ids_json)), [])
            ids = get_ids(ids_list)
            return ids

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [TS-I2] {e}')
            interrupt_sync(context)

    @staticmethod
    def create(context, payload):
        try:
            context.session.post(urljoin(ZEPHYR_TEST_STEP, context.issue_id), json=payload)

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [TS-C1] {e}')
            interrupt_sync(context)

    @staticmethod
    def delete(context, step_id):
        try:
            context.session.delete(f'{urljoin(ZEPHYR_TEST_STEP, context.issue_id)}/{step_id}')

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [TS-D4] {e}')
            interrupt_sync(context)


class StepResult:
    @classmethod
    def create(cls, context):
        if not context.sync or not context.test_step_ids:
            return

        try:
            payload = {
                'stepId': str(context.test_step_ids.pop(0)),
                'issueId': context.issue_id,
                'executionId': str(context.last_execution_id),
                'status': STATUSES.get('in_progress')
            }

            resp = context.session.post(ZEPHYR_STEP_RESULT, json=payload)
            resp.raise_for_status()
            return resp.json().get('id')

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [SR-C1] {e}')
            log.debug('Do not enter the execution of cycle manually  until tests complete!')
            interrupt_sync(context)

    @classmethod
    def update_status(cls, context, step):
        try:
            payload = {
                'status': STATUSES.get(step.status.name),
                'comment': str(step.exception) if step.exception else None
            }

            resp = context.session.put(urljoin(ZEPHYR_STEP_RESULT, str(context.last_step_result_id)), json=payload)
            resp.raise_for_status()

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [SR-U3] {e}')
            interrupt_sync(context)

    @classmethod
    def upload_attachments(cls, context, step):
        try:
            StepResult.prepare_traceback(step.exc_traceback)

            params = {'entityType': 'TESTSTEPRESULT', 'entityId': str(context.last_step_result_id)}
            files = [('file', ('screenshot.png', context.browser.get_screenshot_as_png(), 'multipart/form-data')),
                     ('file', ('traceback.txt', open('traceback.txt', 'rb'), 'multipart/form-data'))]

            resp = context.session.post(ZEPHYR_ATTACHMENT, params=params, files=files)
            log.debug(f'ATTACHMENT: {resp.text}')
            resp.raise_for_status()

        except traceback.TracebackException as e:
            log.error(f'Ошибка при записи лога в файл. {e}')

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [SR-A1] {e}')
            interrupt_sync(context)

    @staticmethod
    def prepare_traceback(tb):
        with open('traceback.txt', 'w') as output:
            traceback.print_tb(tb, file=output)


class JiraIssue:
    def __init__(self, context):
        self.issue = self.search(context)

    def search(self, context):
        if not context.sync:
            return

        try:
            resp = context.session.get(f'{JIRA_SEARCH_TEST}("{context.zephyr_label}")')
            resp.raise_for_status()

            jira_data = resp.json()
            issues_found = jira_data.get('total')

            if issues_found == 1:
                issue = jira_data.get('issues')[0]
                return issue

            elif issues_found == 0:
                log.warning(f'Не найден тест в Jira с меткой {context.zephyr_label}')
                return self.create(context)

            else:
                log.error(f'Метка "{context.zephyr_label}" должна быть уникальной для каждого теста. Найдена в:')
                for issue in jira_data.get('issues'):
                    log.error(f'{JIRA_ISSUE_VIEW}{issue["key"]}')
                interrupt_sync(context)
                return {}

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Jira. [JI-S5] {e}')
            interrupt_sync(context)

    @staticmethod
    def create(context):
        payload = {
            'fields': {
                'project': {'id': context.project_id},
                'summary': context.scenario.name,
                'issuetype': {'id': '11500'},
                'labels': [context.zephyr_label],
                'description': context.background_steps or '',
                'assignee': {'name': ''}
            }
        }

        try:
            resp = context.session.post(JIRA_ISSUE, json=payload)
            resp.raise_for_status()
            issue = resp.json()
            log.info(f"Создан новый тест в Jira: {JIRA_ISSUE_VIEW}{issue.get('key')}")
            return issue

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Jira. [JI-C1] {e}')
            interrupt_sync(context)

    @property
    def id_(self):
        return self.issue.get('id')

    @property
    def key(self):
        return self.issue.get('key')

    @staticmethod
    def update(context):
        try:
            resp = context.session.put(
                urljoin(JIRA_ISSUE, context.issue_id),
                json={'fields': {'summary': context.scenario.name, 'description': context.background_steps or ''}}
            )
            resp.raise_for_status()
            log.info(f'Тест {JIRA_ISSUE_VIEW}{context.issue_key} успешно обновлен')

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Jira. [JI-U3] {e}')
            interrupt_sync(context)

    def sync(self, context):
        if not context.sync:
            return

        issue_description = self.issue.get('fields', {}).get('description')
        issue_summary = self.issue.get('fields', {}).get('summary')

        try:
            assert issue_description == context.background_steps and issue_summary == context.scenario.name

        except AssertionError:
            log.warning('Название сценария и/или его предусловия не совпадают с указанными в Jira')
            self.update(context)

        try:
            resp = context.session.get(urljoin(ZEPHYR_TEST_STEP, self.id_))
            resp.raise_for_status()
            zephyr_data_json = resp.json()
            zephyr_data_list = zephyr_data_json.get(next(iter(zephyr_data_json)), [])
            zephyr_data = format_zephyr(zephyr_data_list)
            bdd_data = format_bdd(context.bdd_steps, context.bdd_results)

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к Zephyr. [JI-S2] {e}')
            interrupt_sync(context)
            return

        try:
            assert bdd_data == zephyr_data
            log.info('Шаги сценария совпадают с указанными в Jira')

        except AssertionError:
            log.warning('Шаги сценария не совпадают с указанными в Jira')
            ids = get_ids(zephyr_data_list)

            for step_id in ids:
                TestStep.delete(context, str(step_id))

            for i in bdd_data:
                payload = {'step': bdd_data[i]['step'], 'result': bdd_data[i]['result']}
                TestStep.create(context, payload)

            log.info(f'Шаги сценария успешно добавлены/обновлены в Jira: {JIRA_ISSUE_VIEW}{context.issue_key}')

        return self.key, self.id_

    @staticmethod
    def link(context):
        if not context.sync or not context.story_key:
            return

        payload = {
            'type': {'name': 'Связан'},
            'inwardIssue': {'key': context.story_key},
            'outwardIssue': {'key': context.issue_key}
        }

        try:
            resp = context.session.post(JIRA_ISSUE_LINK, json=payload)
            resp.raise_for_status()
            log.info(f'Тест {JIRA_ISSUE_VIEW}{context.issue_key} связан с задачей {JIRA_ISSUE_VIEW}{context.story_key}')

        except requests.exceptions.RequestException as e:
            log.error(f'Не удалось связать тест {JIRA_ISSUE_VIEW}{context.issue_key} '
                      f'с задачей {JIRA_ISSUE_VIEW}{context.story_key}. {e}')
            interrupt_sync(context)
            return


class JiraProject:
    def __init__(self, context):
        try:
            resp = context.session.get(urljoin(JIRA_PROJECT, PROJECT_KEY))
            resp.raise_for_status()
            self.project = resp.json()

        except requests.exceptions.RequestException as e:
            log.error(f'Ошибка при выполнении запроса к JIRA. [JP-S2] {e}')
            interrupt_sync(context)
            self.project = {}

    @property
    def id_(self):
        return self.project.get('id')

    @property
    def lead(self):
        return self.project.get('lead', {}).get('name')

    @property
    def version(self):
        versions = self.project.get('versions')
        environment = ENV.lower()

        if not versions:
            version = {}

        elif VERSION_NAME:
            filtered = list(filter(lambda v: v['name'] == VERSION_NAME, versions))
            version = filtered[0] if filtered else {}

        elif environment == 'stage':
            version = max(
                filter(lambda v: v['released'] is False and v['archived'] is False, versions),
                key=lambda x: int(x['id'])
            )

        elif environment == 'prod':
            version = max(
                filter(lambda v: v['released'] != DEPLOY and v['archived'] is False, versions),
                key=lambda x: int(x['id'])
            )

        else:
            version = {}

        version_id = version.get('id', '-1')
        version_name = version.get('name', 'Unplanned')

        return version_id, version_name


class ZephyrSync:
    @staticmethod
    def before_all(context, auth):
        context.zephyr_run_results = {}
        context.session = requests.Session()
        context.session.auth = auth

        project = JiraProject(context)
        context.project_id = project.id_
        context.project_lead = project.lead
        context.project_version_id, context.project_version_name = project.version

        log.debug(f'PROJECT LEAD: {context.project_lead}')
        log.debug(f'PROJECT VERSION: name={context.project_version_name}, id={context.project_version_id}')

        context.test_cycle_id = TestCycle.create(context)

    @staticmethod
    def before_scenario(context, scenario):
        context.last_execution_id = None
        context.bdd_steps, context.bdd_results = parse_scenario(scenario.steps)

        if context.feature.background:
            context.background_steps = parse_background(context.feature.background.steps)
        else:
            context.background_steps = None

        context.zephyr_label, context.story_key = parse_tags(context.tags)

        if not context.zephyr_label:
            log.error('Для синхронизации с Zephyr в feature файле должен быть указан тэг ZephyrLabel. ')
            interrupt_sync(context)
            return context.sync

        issue = JiraIssue(context)
        context.issue_id = issue.id_
        context.issue_key = issue.key

        issue.sync(context)
        TestCycle.fill(context)
        context.last_execution_id = Execution.last_execution_id(context)

        Execution.update_execution_status(context, status='in_progress')
        context.test_step_ids = TestStep.ids(context)
        context.last_step = 'default'
        context.last_step_result_id = StepResult.create(context)
        context.default_result = True

        JiraIssue.link(context)

    @staticmethod
    def before_step(context, step):
        if step.filename == context.scenario.filename:
            context.last_step = parse_step(context, step)

            if context.last_step in context.bdd_steps:
                context.bdd_steps.remove(context.last_step)

                if context.default_result is False:
                    context.last_step_result_id = StepResult.create(context)

                else:
                    context.default_result = False

    @staticmethod
    def after_step(context, step):
        if step.filename == context.scenario.filename:
            StepResult.update_status(context, step)

            if step.status.name == 'failed':
                StepResult.upload_attachments(context, step)

    @staticmethod
    def after_scenario(context, scenario):
        Execution.update_execution_status(context, status=scenario.status.name)
        context.zephyr_run_results[scenario.name] = f'{ZEPHYR_RESULTS_URL}{context.last_execution_id}'

        if scenario.status.name == 'failed':
            Execution.assign(context)

    @staticmethod
    def after_all(context):
        TestCycle.update(context)
        log.info('Результаты тестового прогона сценариев:')
        for scenario_name, zephyr_result_link in context.zephyr_run_results.items():
            log.info(f'\t"{scenario_name}": {zephyr_result_link}')
        return context.zephyr_run_results
