import subprocess
import re
import os
from pprint import pprint
from collections import defaultdict
import tempfile
import json
import pathlib
from getpass import getpass
import stat
import shutil
from datetime import datetime, timedelta


import click
import yaml
import pytest
from pytest_jsonreport.plugin import JSONReport
import requests
from github import Github


class CustomTasksType(click.ParamType):
    """
    Класс создает новый тип для click и преобразует
    допустимые варианты строк заданий в отдельные файлы тестов.

    Кроме того проверяет есть ли такой файл в текущем каталоге
    и оставляет только те, что есть.
    """

    def convert(self, value, param, ctx):
        if not re.fullmatch(r"all|\d[\da-l ,-]*", value):
            self.fail(
                "в строке заданий должны содержаться "
                "только числа, буквы и символы: "
                "запятая, пробел и -"
            )
        if value == "all":
            return value
        else:
            current_chapter = get_chapter()
            tasks_list = re.split(r"[ ,]+", value)
            tasks = []
            for task in tasks_list:
                if "-" in task:
                    start, end = task.split("-")
                    for t in range(int(start), int(end) + 1):
                        tasks.append(t)
                else:
                    tasks.append(int(task))
            all_test_files_in_current_dir = os.listdir(".")
            test_files = [f"test_task_{current_chapter}_{num}.py" for num in tasks]
            test_files = [
                test for test in test_files if test in all_test_files_in_current_dir
            ]
            return test_files


def call_command(command, verbose=True):
    """
    Функция вызывает указанную command через subprocess
    и выводит stdout и stderr, если флан verbose=True.
    """
    result = subprocess.run(
        command,
        shell=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    std = result.stdout
    if verbose:
        print("#" * 20, command)
        if std:
            print(std)
    return std


def post_comment_to_last_commit(msg, repo, delta_days=14):
    """
    Написать комментарий о сдаче заданий в последнем коммите.
    Комментарий пишется через Github API.

    Для работы функции должен быть настроен git.
    Функция пытается определить имя пользователя git из вывода git config --list,
    Если это не получается, запрашивает имя пользователя.

    Пароль берется из переменной окружения GITHUB_PASS или запрашивается.
    """
    token = os.environ.get("GITHUB_TOKEN")
    since = datetime.now() - timedelta(days=delta_days)

    g = Github(token)
    repo_name = f"pyneng/{repo}"
    repo_obj = g.get_repo(repo_name)
    commits = repo_obj.get_commits(since=since)

    try:
        last = commits[0]
    except IndexError:
        print("За указанный период времени не найдено коммитов")
    else:
        last.create_comment(msg)


def send_tasks_to_check(passed_tasks):
    """
    Функция отбирает все задания, которые прошли
    тесты при вызове ptest, делает git add для файлов заданий,
    git commit с сообщением какие задания сделаны
    и git push для добавления изменений на Github.
    После этого к этому коммиту добавляется сообщение о том,
    что задания сдаются на проверку с помощью функции post_comment_to_last_commit.
    """
    ok_tasks = [test.replace("test_", "") for test in passed_tasks]
    tasks_num_only = [task.replace("task_", "").replace(".py", "") for task in ok_tasks]
    message = f"Сделаны задания {' '.join(tasks_num_only)}"

    for task in ok_tasks:
        call_command(f"git add {task}")
    call_command(f'git commit -m "{message}"')
    call_command("git push origin main")

    pth = str(pathlib.Path().absolute())
    # repo_match = re.search(r"preparation-pyneng-10-jan-apr-2021", pth)
    repo_match = re.search(r"online-\d+-\w+-\w+", pth)
    if repo_match:
        repo = repo_match.group()
    else:
        raise ValueError("Не найден репозиторий online-10-имя-фамилия")
    post_comment_to_last_commit(message, repo)


def get_chapter():
    """
    Функция возвращает номер текущего раздела, где вызывается ptest.
    """
    pth = str(pathlib.Path().absolute())
    last_dir = os.path.split(pth)[-1]
    current_chapter = int(last_dir.split("_")[0])
    return current_chapter


def parse_json_report(report):
    """
    Отбирает нужные части из отчета запуска pytest в формате JSON.
    Возвращает список тестов, которые прошли.
    """
    if report and report["summary"]["total"] != 0:
        all_tests = defaultdict(list)
        summary = report["summary"]

        test_names = [test["nodeid"] for test in report["collectors"][0]["result"]]
        for test in report["tests"]:
            name = test["nodeid"].split("::")[0]
            all_tests[name].append(test["outcome"] == "passed")
        all_passed_tasks = [name for name, outcome in all_tests.items() if all(outcome)]
        return all_passed_tasks
    else:
        return []


def copy_answers(passed_tasks):
    """
    Функция клонирует репозиторий с ответами и копирует ответы для заданий,
    которые прошли тесты.
    """
    pth = str(pathlib.Path().absolute())
    current_chapter_name = os.path.split(pth)[-1]
    current_chapter_number = int(current_chapter_name.split("_")[0])

    homedir = pathlib.Path.home()
    os.chdir(homedir)
    call_command(
        "git clone --depth=1 https://github.com/natenka/pyneng-answers",
        verbose=False,
    )
    os.chdir(f"pyneng-answers/answers/{current_chapter_name}")
    copy_answer_files(passed_tasks, pth)
    click.secho(
        (
            "\nОтветы на задания, которые прошли тесты "
            "скопированы в файлы answer_task_x.py\n"
        ),
        fg="green",
    )
    os.chdir(homedir)
    shutil.rmtree("pyneng-answers", onerror=remove_readonly)
    os.chdir(pth)


def remove_readonly(func, path, _):
    """
    Вспомогательная функция для Windows, которая позволяет удалять
    read only файлы из каталога .git
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


def copy_answer_files(passed_tasks, pth):
    """
    Функция копирует ответы для указанных заданий.
    """
    for test_file in passed_tasks:
        task_name = test_file.replace("test_", "")
        answer_name = test_file.replace("test_", "answer_")
        if not os.path.exists(f"{pth}/{answer_name}"):
            call_command(
                f"cp {task_name} {pth}/{answer_name}",
                verbose=False,
            )


@click.command(
    context_settings=dict(
        ignore_unknown_options=True, help_option_names=["-h", "--help"]
    )
)
@click.argument("tasks", default="all", type=CustomTasksType())
@click.option(
    "--disable-verbose", "-d", is_flag=True, help="Отключить подробный вывод pytest"
)
@click.option(
    "--answer",
    "-a",
    is_flag=True,
    help=(
        "Скопировать ответы для заданий, которые "
        "прошли тесты. При добавлении этого флага, "
        "не выводится traceback для тестов."
    ),
)
@click.option(
    "--check",
    "-c",
    is_flag=True,
    help=(
        "Сдать задания на проверку. "
        "При добавлении этого флага, "
        "не выводится traceback для тестов."
    ),
)
def cli(tasks, disable_verbose, answer, check):
    """
    Запустить тесты для заданий TASKS. По умолчанию запустятся все тесты.

    Примеры запуска:

    \b
        ptest            запустить все тесты для текущего раздела
        ptest 1,2a,5     запустить тесты для заданий 1, 2a и 5
        ptest "1 2a 5"
        ptest 1-5        запустить тесты для заданий 1-5
        ptest 1-5 -a     запустить тесты и записать ответы на задания,
                         которые прошли тесты, в файлы answer_task_x.py
        ptest 1-5 -c     запустить тесты и сдать на проверку задания,
                         которые прошли тесты.
        ptest -a -c      запустить все тесты, записать ответы на задания
                         и сдать на проверку задания, которые прошли тесты.

    Флаг -d отключает подробный вывод pytest, который включен по умолчанию.
    Флаг -a записывает ответы в файлы answer_task_x.py, если тесты проходят.
    Флаг -c сдает на проверку задания (пишет комментарий на github)
    для которых прошли тесты.
    Для сдачи заданий на проверку надо создать переменную окружения GITHUB_PASS
    или указать пароль при запуске скрипта с флагом -c (--check).
    """
    json_plugin = JSONReport()

    if disable_verbose:
        pytest_args = ["--json-report-file=none", "--tb=short", "--disable-warnings"]
    else:
        pytest_args = ["-vv", "--json-report-file=none", "--disable-warnings"]

    if answer or check:
        pytest_args = ["--json-report-file=none", "--tb=no", "--disable-warnings"]

    # запуск pytest
    if tasks == "all":
        pytest.main(pytest_args, plugins=[json_plugin])
    else:
        pytest.main(tasks + pytest_args, plugins=[json_plugin])

    # получить результаты pytest в формате JSON
    passed_tasks = parse_json_report(json_plugin.report)

    if passed_tasks:
        # скопировать ответы в файлы answer_task_x.py
        if answer:
            copy_answers(passed_tasks)

        # сдать задания на проверку через github API
        if check:
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                raise ValueError(
                    "Для сдачи заданий на проверку надо сгенерировать токен github."
                    "Подробнее в инструкции: ..."
                )
            send_tasks_to_check(passed_tasks)


if __name__ == "__main__":
    cli()
