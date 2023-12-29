import os
import sys
import argparse
import json

from behave.__main__ import main as behave_main

from features.core.logger import logger

is_windows = sys.platform.startswith('win')
zapp_path = os.path.dirname(os.path.abspath(__file__))

# Цветной вывод в консоль
if is_windows:
    os.system('color')
CRED = '\033[91m'
CEND = '\033[0m'
CBLUE = '\33[34m'
CYELLOW = '\033[33m'


def get_venv_path():
    ''' Получить путь к папке виртуального окружения '''

    venv_folder = 'Scripts' if is_windows else 'bin'
    return os.path.join(zapp_path, venv_folder)


def get_cli_args():
    ''' Получить все параметры, переданные через аргументы командной строки при запуске скрипта '''

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--feature', type=str, help=' feature file name (in "features" folder)')
    parser.add_argument('--config', type=str, default='zapp.config.json', help=' config file name')
    parser.add_argument('--verbose', action='store_true', help=' behave verbose mode')
    parser.add_argument('--junit', action='store_true', default=argparse.SUPPRESS, help=' behave junit mode')
    parser.add_argument('--tags', type=str, action='append', help=' feature tags envolved')
    first_args, unknown = parser.parse_known_args()
    # Добавляем все кастомные аргументы в парсер
    new_args = {}
    for arg in unknown:
        if arg[0:2] == '--':
            # Обрабатываем ситуацию, когда аргументы передаются через '='
            name_end = arg.find('=')
            arg_name = arg
            if name_end >= 0:
                arg_name = arg[0:name_end]
            # Если аргумент уже есть, то присваиваем ему значение append, чтобы парсер брал из него массив
            if arg_name not in new_args:
                new_args[arg_name] = 'store'
    for arg_name in new_args:
        parser.add_argument(arg_name, type=str, action=new_args[arg_name])
    # Прогоняем парсер ещё раз, чтобы включить туда кастомные аргументы
    args = vars(parser.parse_args())
    # Удаляем несуществующие аргументы, чтобы не перекрывать ими опции из конфига
    if args['tags'] is None:
        del args['tags']
    if args['feature'] is None:
        del args['feature']
    if args['verbose'] is not True:
        del args['verbose']
    return args


def is_param_present(params, param_name):
    return (param_name in params) and params[param_name]


def is_param_true(params, param_name):
    return (
        (param_name in params) and
        (type(params[param_name]) is str) and
        (params[param_name].lower() in ('true', '1'))
    )


def get_behave_run_params(params):
    ''' Получить массив параметров командной строки для запуска behave '''

    run_params = ['-k', '--junit']

    if is_param_present(params, 'verbose') or is_param_true(params, 'DEBUG'):
        run_params.append('--verbose')
    if is_param_present(params, 'feature'):
        run_params.append('features/' + params['feature'])
    if is_param_present(params, 'tags'):
        if type(params['tags']) is list:
            for tag in params['tags']:
                run_params.append('--tags=' + tag)
        else:
            run_params.append('--tags=' + params['tags'])

    is_screenshot_mode = is_param_true(params, 'SCREENSHOT_MODE')
    run_params.append('--tags=@screenshots' if is_screenshot_mode else '--tags=~@screenshots')

    return run_params


def get_custom_env(params):
    ''' Получить словарь переменных окружения, добавив поверх текущих переданные параметры '''
    custom_env = {}
    for arg in params:
        # Игнорируем параметры, которые мы обрабатываем по-другому
        if arg not in ('tags', 'feature', 'config', 'verbose', 'junit'):
            custom_env[arg] = params[arg]
    return custom_env


def get_env(custom_env):
    ''' Получить словарь переменных окружения, добавив поверх текущих переданные параметры '''

    env = {**os.environ, **custom_env}

    if env.get('RUN_TYPE') is None:
        env['RUN_TYPE'] = 'local'

    env['PYTHONIOENCODING'] = 'utf_8'
    env['PYTHONHOME'] = ''
    venv_path = get_venv_path()
    env['PATH'] = venv_path + os.pathsep + env['PATH']
    return env


def load_config(filename):
    ''' Загрузить параметры из json-конфига '''

    try:
        file_path = os.path.join(zapp_path, filename)
        with open(file_path, "r") as json_file:
            data = json.load(json_file)
            return data
    except FileNotFoundError:
        print(CYELLOW + f'Файл {filename} не найден в директории {zapp_path}!' + CEND)
        return {}


def print_params(run_params, params):
    ''' Вывести параметры запуска behave в консоль '''

    print(CBLUE + ' '.join(run_params) + CEND)
    for param in params:
        value = params[param] if 'password' not in param.lower() else '********'
        print(f'{CBLUE}{param}:{CEND} {value}')


def run_behave():
    logger.start_intercept()

    args = get_cli_args()
    config = load_config(args['config'])
    del args['config']
    # Накладываем параметры из командной строки поверх конфига
    params = {**config, **args}
    run_params = get_behave_run_params(params)
    custom_env = get_custom_env(params)
    env = get_env(custom_env)
    os.environ = env
    print_params(run_params, custom_env)

    # Выводим stdout чтобы не мешать лог с логом процесса behave
    sys.stdout.flush()

    return_code = behave_main(run_params)
    logger.stop_intercept()

    return return_code


if __name__ == '__main__':
    run_behave()
