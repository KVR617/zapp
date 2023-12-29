import base64
import os
import sys
import tempfile

from datetime import datetime, timedelta

from behave.contrib.scenario_autoretry import patch_scenario_with_autoretry

from behave.reporter.summary import SummaryReporter
from requests import RequestException

from features.core.backend import ZappBackend, ZappBackendSessionException
from features.core.logger.reporter import ZappReporter
from version import ZAPP_VERSION
from features.core.settings import (
    STAND,
    REMOTE_EXECUTOR,
    ZEPHYR_USE,
    ZEPHYR_LITE,
    BROWSER,
    LOCAL_SCREENSHOTS,
    SMARTWAIT_DELAY,
    FORCE_DELAY,
    RUN_TYPE,
    SCREENSHOT_MODE,
    SELENOID_UI_URL,
    BROWSER_LOGGING,
    VIDEO,
    VIDEO_NAME,
    VIDEO_DIR,
    CANARY_COOKIE,
    MOBILE_LOGGING,
    ENV,
    PROJECT,
    BACKEND_LOCAL_SESSION_REGISTER,
    TG_NOTIFICATION_MODE,
    RETRY_AFTER_FAIL,
    MAX_ATTEMPTS
)

from features.core.constants import UPDATE_STEPS_MESSAGE, BACKEND_RUN_TYPES, NON_REGISTRABLE_RUN_TYPES
from features.core.utils import (
    Seed,
    get_stand_url,
    save_screenshot,
    log_deprecated_steps,
    log,
    variables,
    vault_variables,
    set_canary_cookie,
    get_output_as_json,
    get_reporter,
    clean_xml_reports,
    telegram_bot_sendnotify,
    send_by_mode
)

from features.core.zephyr import ZephyrSync
from features.core.zephyr_lite import ZephyrSyncLite
from features.core.metrics import Metrics
from features.core.js_scripts import FREEZE_ANIMATIONS
from features.core.screenshots import RunInfo
from features.core.mobiles import (
    Mobile,
    MOBILES,
    MobileAvoids,
    get_android_app_version,
    local_save_android_logs
)
from features.core.browsers import BROWSERS, SELENOID_UI_BROWSERS
from features.core.browser_errors import print_page_errors

metrics_all_tests_count = 0
metrics_failed_tests_count = 0


def before_all(context):
    context.backend = ZappBackend()
    context.config.reporters.append(ZappReporter(context.config, context.backend))

    log.info(f'Версия ZAPP: {ZAPP_VERSION}')
    log.info(f'Версия Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')

    if BACKEND_LOCAL_SESSION_REGISTER \
            and RUN_TYPE not in NON_REGISTRABLE_RUN_TYPES \
            and not context.backend.session_running:

        clean_xml_reports()

        try:
            context.backend.start_session(ENV, PROJECT, {})
            log.info('Зарегистрирована сессия в zapp-backend %s', context.backend.session_url)
        except (ZappBackendSessionException, RequestException) as ex:
            log.warning('Не удалось зарегистрировать сессию в zapp-backend')
            log.debug(ex, exc_info=ex)

    context.metrics_start_date = datetime.now()
    context.metrics_deprecated_steps = {}
    context.metrics_exceptions = []

    context.seed = Seed()
    context.seed.run = variables['run_seed'] = context.seed.generate_run_seed()
    variables['scenario_seed'] = context.seed.scenario

    try:
        auth = (variables.pop('JIRA_USER'), variables.pop('JIRA_PASSWORD'))
        context.sync = ZEPHYR_USE
        context.sync_lite = ZEPHYR_USE and ZEPHYR_LITE

        if context.sync_lite is True:
            context.zephyr = ZephyrSyncLite(auth)

        elif context.sync is True:
            ZephyrSync.before_all(context, auth)

    except KeyError:
        context.sync = context.sync_lite = False

    finally:
        log.info(f'Синхронизация с Jira/{"Zephyr (lite)" if ZEPHYR_LITE is True else "Zephyr"}: '
                 f'{"включена" if context.sync is True else "отключена"}')

    if RUN_TYPE in BACKEND_RUN_TYPES:
        if TG_NOTIFICATION_MODE.lower() != "disable":
            if TG_NOTIFICATION_MODE.lower() in ("always", "on_errors", "on_success"):
                log.info('Отправка уведомлений в telegram включена')
            else:
                log.warning('Параметр TG_NOTIFICATION_MODE содержит недопустимое значение')

    context.host = variables['context_host'] = get_stand_url(STAND)
    context.smartwait_delay = SMARTWAIT_DELAY
    context.send_keys_as_granny = False
    context.tempdir = tempfile.mkdtemp()

    context.is_webview = False

    if BROWSER.lower() in MOBILES:
        context.browser_ = Mobile()
        context.is_mobile = True

    else:
        browser = BROWSERS.get(BROWSER.lower()) or BROWSERS.get('chrome')
        context.browser_ = browser.remote(context.tempdir) if REMOTE_EXECUTOR else browser.local(context.tempdir)
        context.is_mobile = False

    context.browser = context.browser_.get_driver()

    if context.is_mobile is True:
        context.mobile_avoids = MobileAvoids(context)
        context.mobile_avoids.avoid_all(context)

    log.info(f'Версия {context.browser_.name}: {context.browser_.version} /{context.browser_.type}')
    log.debug(f'TEMPDIR: {context.tempdir}')

    if isinstance(context.browser_, SELENOID_UI_BROWSERS):
        log.info(f'Просмотр выполнения сценария на удалённой машине: '
                 f'{SELENOID_UI_URL}#/sessions/{context.browser.session_id}')

    if isinstance(context.browser_, Mobile) and VIDEO:
        log.warning(
            'Запись видео является нестабильной функциональностью. Функциональность может работать нестабильно или '
            'быть изменена без предупреждения'
        )
        try:
            context.browser.start_recording_screen()
            log.info('Запись видео начата')
        except Exception as ex:
            log.warning('Не удалось инициировать запись видео', exc_info=ex)

    if context.browser_.name.lower() == 'android':
        log.info(f'Версия мобильного приложения: {get_android_app_version(context)}')

    if context.backend.session_running:
        try:
            context.backend.update_session(platform=context.browser_.name)
        except (ZappBackendSessionException, RequestException) as ex:
            log.warning('Не удалось обновить сессию в zapp-backend')
            log.debug(ex, exc_info=ex)


def before_feature(context, feature):
    if RETRY_AFTER_FAIL is True:
        for scenario in feature.scenarios:
            if scenario.effective_tags:
                patch_scenario_with_autoretry(scenario, max_attempts=MAX_ATTEMPTS)


def before_scenario(context, scenario):
    log.info(f'Выполнение сценария "{scenario.name}" начато: {datetime.now()}')
    global metrics_all_tests_count
    metrics_all_tests_count += 1

    context.seed.scenario = variables['scenario_seed'] = context.seed.generate_scenario_seed()

    if context.sync_lite is True:
        context.zephyr.scenario_parser(scenario, context.feature, context.tags, context.seed.scenario)
    elif context.sync is True:
        ZephyrSync.before_scenario(context, scenario)

    context.run_info = RunInfo() if SCREENSHOT_MODE else None
    context.force_delay = FORCE_DELAY if "sloth" not in scenario.tags else 2
    log.debug(f'FORCE_DELAY: {context.force_delay}')

    if CANARY_COOKIE:
        context.browser.get(context.host)
        set_canary_cookie(context)


def before_step(context, step):
    context.current_step = dict(name=step.name, filename=step.filename, line=step.line)
    if context.sync is True and context.sync_lite is False:
        ZephyrSync.before_step(context, step)

    if SCREENSHOT_MODE:
        context.browser.execute_script(FREEZE_ANIMATIONS)


def after_step(context, step):
    if context.sync_lite is True:
        context.zephyr.every_step(step, context.scenario)
    elif context.sync is True:
        ZephyrSync.after_step(context, step)

    if step.exception:
        exception_type = type(step.exception).__name__
        log.debug(f'EXCEPTION_TYPE: {exception_type}')
        context.metrics_exceptions.append(exception_type)

        if REMOTE_EXECUTOR and VIDEO:
            log.warning(f'Примерное время ошибки на видео: {timedelta(seconds=round(context.feature.duration))}')


def after_scenario(context, scenario):
    log.info(f'Выполнение сценария "{scenario.name}" закончено: {datetime.now()}')
    if context.sync_lite is True:
        screenshot_path = save_screenshot(context) if scenario.status.name == 'failed' else ''
        duration = timedelta(seconds=round(context.feature.duration)) if scenario.status.name == 'failed' else None
        context.zephyr.every_scenario(scenario, screenshot_path, duration)

    elif context.sync is True:
        ZephyrSync.after_scenario(context, scenario)

    if MOBILE_LOGGING is True:
        local_save_android_logs(context, scenario)

    if context.run_info:
        context.run_info.print_results()

    if scenario.status.name == 'failed':
        global metrics_failed_tests_count
        metrics_failed_tests_count += 1

        if BROWSER_LOGGING and context.is_mobile is False:
            print_page_errors(context)

        if LOCAL_SCREENSHOTS and context.sync_lite is False:
            save_screenshot(context)


def after_all(context):
    video_url = ''
    if VIDEO:
        if REMOTE_EXECUTOR:
            video_url = f'{SELENOID_UI_URL}video/{VIDEO_NAME}'
            log.info(f'Запись прохождения теста будет доступна по ссылке: {video_url}')

        if isinstance(context.browser_, Mobile):
            filepath = os.path.join(VIDEO_DIR, VIDEO_NAME)

            try:
                os.makedirs(VIDEO_DIR, exist_ok=True)
                video_rawdata = context.browser.stop_recording_screen()
                with open(filepath, "xb") as vd:
                    vd.write(base64.b64decode(video_rawdata))

                if RUN_TYPE in ('npm', 'local', 'behave'):
                    log.info(f'Запись прохождения теста доступна по пути:"{filepath}"')
            except Exception as ex:
                log.error("Не удалось сохранить запись видео", exc_info=ex)

    if RUN_TYPE in BACKEND_RUN_TYPES:
        send_by_mode(context, TG_NOTIFICATION_MODE)

    if context.sync_lite is True:
        zephyr_sync_results = context.zephyr.synchronize()
    elif context.sync is True:
        zephyr_sync_results = ZephyrSync.after_all(context)
    else:
        zephyr_sync_results = {}

    if context.backend.session_running:
        export_data = dict(
            video_url=video_url,
            zephyr_sync_results=zephyr_sync_results,
            export_variables={k: v for k, v in variables.items() if k not in {**vault_variables, **os.environ}},
        )

        tests_passed = False
        summary_reporter = get_reporter(context, SummaryReporter)
        if summary_reporter:
            tests_passed = summary_reporter.scenario_summary['passed'] > 0 \
                           and summary_reporter.scenario_summary['failed'] == 0

        if RUN_TYPE not in BACKEND_RUN_TYPES:
            export_data.update(
                tests_passed=tests_passed,
                output_json=get_output_as_json(),
                zapp_raw_logs='',
            )

        zapp_reporter = get_reporter(context, ZappReporter)
        zapp_reporter.export_data = export_data

    if context.metrics_deprecated_steps and sys.platform == "darwin" and RUN_TYPE == 'npm':
        log.warning(UPDATE_STEPS_MESSAGE)

    log_deprecated_steps(context.metrics_deprecated_steps)
    Metrics(
        all_tests_count=metrics_all_tests_count,
        failed_tests_count=metrics_failed_tests_count,
        start_date=context.metrics_start_date,
        deprecated_steps=context.metrics_deprecated_steps,
        exceptions=context.metrics_exceptions,
        browser_name=context.browser_.name,
        browser_version=context.browser_.version,
        run_seed=context.seed.run
    ).send()
    context.browser.quit()
