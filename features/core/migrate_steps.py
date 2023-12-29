#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Known issues:
# UnicodeDecodeError in input when retyping after cyrillic symbol
# No double-checking before updating files - diff can be with no differences

import os
import re
import json
import difflib
import webbrowser
from collections import namedtuple

CEND = '\33[0m'
CRED = '\33[31m'
CCYAN = '\33[36m'
CBLUE = '\33[34m'
CBLUE2 = '\33[94m'

ORIGIN_FILE = 'deprecated_steps.json'
DIFF_FILE = 'deprecated_steps_diff.html'


def get_abs_path(filename: str) -> str:
    return os.path.join(os.path.abspath(os.curdir), filename)


class HtmlDiffPatched(difflib.HtmlDiff):
    def make_html_diff(self, table):
        charset = 'utf-8'
        return (self._file_template % dict(
            styles=self._styles,
            legend='',
            table=table,
            charset=charset
        )).encode(charset, 'xmlcharrefreplace').decode(charset)


class MigrateSteps:
    def __init__(self):
        self.deprecated_steps = self._retrieve_deprecated_steps()

    def _retrieve_deprecated_steps(self):
        try:
            with open(ORIGIN_FILE) as file:
                return self._parse_steps(json.load(file))

        except (OSError, json.JSONDecodeError) as e:
            print(f'{CRED}Не удалось открыть файл c данными тестового прогона. {e}{CEND}')
            return {}

    @staticmethod
    def _parse_steps(raw_data: dict) -> dict:
        data = {}
        Step = namedtuple('Step', 'line, old, new')

        for k, v in raw_data.items():
            file = v['file']
            step = Step(v['line'], v['old_step'], v['new_step'])
            if file in data:
                data[file].append(step)
            else:
                data[file] = [step]
        return data

    @property
    def _files(self):
        return [f for f in self.deprecated_steps]

    @property
    def _temp_files(self):
        return [re.sub(r'(\w+?_\w+\.\w{2,})', r'~\1', f) for f in self.deprecated_steps]

    def _create_changed_copies(self):
        for origin_filename, temp_filename in zip(self._files, self._temp_files):
            with open(origin_filename) as origin_file:
                print(f'\nFile: {CCYAN}{origin_filename}{CEND}')
                content = origin_file.read()

            with open(get_abs_path(temp_filename), 'w') as temp_file:
                for step in self.deprecated_steps[origin_filename]:
                    content = content.replace(step.old, step.new)
                    print(f' [{step.line}]: "{CBLUE2}{step.old}{CEND}" ---> "{CBLUE}{step.new}{CEND}"')
                temp_file.write(content)

    def _create_diff_file(self):
        diff_table = ''
        for origin_filename, temp_filename in zip(self._files, self._temp_files):
            with open(origin_filename) as origin_file:
                with open(temp_filename) as temp_file:
                    result = HtmlDiffPatched().make_table(origin_file.readlines(),
                                                          temp_file.readlines(),
                                                          context=True)
                    diff_table += f'\n<h3>{origin_filename} ---> {temp_filename}</h3>\n{result}'

        with open(DIFF_FILE, 'w') as output:
            output.writelines(HtmlDiffPatched().make_html_diff(diff_table))

        diff_filepath = f'file://{os.path.abspath(output.name)}'
        print(f'\nDiff: {diff_filepath}')
        return diff_filepath

    @staticmethod
    def _print_diff(filepath: str):
        webbrowser.open(filepath, new=2)

    @staticmethod
    def _delete_files(files: list):
        for file in files:
            try:
                os.remove(file)
            except OSError as e:
                print(f'{CRED}Произошла ошибка при попытке удалить файл {file}, {e}{CEND}')

    @staticmethod
    def _replace_files(as_is: list, to_be: list):
        for ai_filename, tb_filename in zip(as_is, to_be):
            try:
                os.replace(ai_filename, tb_filename)
                print(f'Обновлен файл "{CBLUE2}{ai_filename}{CEND}" ---> "{CBLUE}{tb_filename}{CEND}"')
            except OSError as e:
                print(f'{CRED}Произошла ошибка при попытке обновить файл {ai_filename}, {e}{CEND}')

    def make(self):
        if not self.deprecated_steps:
            print(f'{CBLUE}Чтобы начать миграцию, попробуйте:'
                  f'\n- перейти в папку с тестами (cd testcase)'
                  f'\n- запустить тестовый сценарий, в котором есть устаревшие шаги'
                  f'\nА затем повторите вызов.{CEND}')

            return False

        try:
            self._create_changed_copies()
            diff_file = self._create_diff_file()

            if input(f'{CBLUE}Открыть diff в браузере? (y/n): {CEND}').lower() == 'y':
                self._print_diff(diff_file)
            return True

        except Exception as e:
            print(f'{CRED}Произошла ошибка, изменения будут отменены. {e.__repr__()}{CEND}')
            self.rollback()
            return False

    def apply(self):
        self._delete_files([ORIGIN_FILE, DIFF_FILE])
        self._replace_files(self._temp_files, self._files)

    def rollback(self):
        self._delete_files(self._temp_files + [DIFF_FILE])
        print(f'Изменения отменены; временные файлы удалены')


if __name__ == '__main__':
    migration = MigrateSteps()

    if migration.make() is True:
        if input(f'{CBLUE}Применить изменения? (y/n): {CEND}').lower() == 'y':
            migration.apply()
        else:
            migration.rollback()
