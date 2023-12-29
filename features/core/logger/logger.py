import sys
from io import StringIO

from features.core.logger.singleton import Singleton


class StdoutLogger(metaclass=Singleton):
    """Класс, агрегирующий stdout и stderr логи в единый буфер"""

    def __init__(self):
        self.__stdout = sys.stdout
        self.__stderr = sys.stderr

        self.intercepting = False
        self.stream = StringIO()
        self.stdout_interceptor = self.StreamInterceptor(self.stream, self.__stdout)
        self.stderr_interceptor = self.StreamInterceptor(self.stream, self.__stderr)

    def start_intercept(self):
        """Начинает перехват сообщений"""

        if self.intercepting:
            return

        sys.stdout = self.stdout_interceptor
        sys.stderr = self.stderr_interceptor
        self.intercepting = True

    def stop_intercept(self):
        """Останавливает перехват сообщений"""

        sys.stdout = self.__stdout
        sys.stderr = self.__stderr
        self.intercepting = False

    def get_log(self) -> str:
        """Возвращает весь лог в виде строки"""

        return self.stream.getvalue()

    def __del__(self):
        self.stop_intercept()
        self.stream.close()

    class StreamInterceptor:
        """
        Публикует сообщения во все стримы, переданные в args
        """

        def __init__(self, *args):
            self.streams = args

        def write(self, string_: str):
            """Публикует сообщения в каждый стрим"""

            for stream in self.streams:
                stream.write(string_)

        def flush(self):
            """Выполняет flush для каждого стрима"""

            for stream in self.streams:
                stream.flush()


logger = StdoutLogger()
