import os
import requests
import binascii
import json
import datetime
from collections import defaultdict
from PIL import Image, ImageChops, ImageOps
from io import BytesIO
from features.core.utils import log, get_units_case
from features.core.constants import (
    SCREENSHOT_RESULTS_URL,
)
from features.core.settings import (
    PROJECT_KEY,
    SCREENSHOT_DIR,
    REMOTE_STORAGE_URL,
)


# Генерация имени скриншота
def get_screenshot_name(name, context):
    window_size = context.browser.get_window_size()
    window_width = window_size['width']
    window_height = window_size['height']
    return f'{name} -- {context.browser.name} -- {window_width}x{window_height}'


# Генерация идентификатора прогона
def get_run_id():
    run_hash = binascii.hexlify(os.urandom(8)).decode('utf-8')
    run_date = datetime.datetime.now()
    run_date_str = run_date.strftime('%Y-%m-%d_%H-%M')
    return f'{run_date_str}_{run_hash}'


# Получение скриншота элемента страницы
def get_element_screenshot(context, element):
    # Снимаем скриншот текущего viewport страницы
    png = element.screenshot_as_png
    image = Image.open(BytesIO(png)).convert('RGB')

    return image


# Получение изображения, где разница двух исходных отмечается чёрными пикселями
def get_image_difference(ref_image, new_image):
    diff_image = ImageChops.difference(ref_image, new_image)
    if (ref_image.width != diff_image.width) or (ref_image.height != diff_image.height):
        new_width = max(ref_image.width, diff_image.width)
        new_height = max(ref_image.height, diff_image.height)
        diff_image = diff_image.transform((new_width, new_height), Image.EXTENT, (0, 0, new_width, new_height))
    diff_image = ImageOps.colorize(diff_image.convert('L'), 'white', 'black', None, 5, 6)
    return diff_image


# Подсчёт количества чёрных пикселей (на изображении разницы)
def get_black_pixels(image):
    bbox = image.getbbox()
    if not bbox:
        return 0
    return sum(image.crop(bbox)
               .point(lambda x: 255 if not x else 0)
               .convert('L')
               .point(bool)
               .getdata())


# Генерация осветлённого изображения для подложки подсветки разницы
def increase_image_brightness(image):
    width, height = image.size
    pixels = image.load()
    for x in range(width):
        for y in range(height):
            pixel = image.getpixel((x, y))
            # Создаём серый цвет в диапазоне от 255 - 64 до 255 суммарной интенсивности суммы всех каналов
            gray = int(255 - 64 + 64 * ((pixel[0] + pixel[1] + pixel[2]) / (255 * 3)))
            pixels[x, y] = (gray, gray, gray)
    return image


# Класс для сохранения и загрузки скриншотов локально
class LocalImageIO:
    def __init__(self, name, run_info):
        self.name = name
        self.run_info = run_info
        self.directory_path = os.path.abspath(os.path.join(SCREENSHOT_DIR, name))
        os.makedirs(self.directory_path, exist_ok=True)

    def get_ref_image(self):
        ref_image_path = os.path.join(self.directory_path, self.name + ' (ref).png')
        if os.path.isfile(ref_image_path):
            ref_image = Image.open(ref_image_path).convert('RGB')
            return ref_image
        return None

    def save_ref_image(self, image):
        ref_image_path = os.path.join(self.directory_path, self.name + ' (ref).png')
        image.save(ref_image_path)

    def save_new_image(self, image):
        new_image_path = os.path.join(self.directory_path, self.name + ' (new).png')
        image.save(new_image_path)

    def save_diff_image(self, image):
        diff_image_path = os.path.join(self.directory_path, self.name + ' (diff).png')
        image.save(diff_image_path)
        self.run_info.diff_count += 1


def compare_element_screenshots(context, element, name):
    image_io = LocalImageIO(name, context.run_info)

    ref_image = image_io.get_ref_image()
    new_image = get_element_screenshot(context, element)

    # Если уже есть эталон, сравниваем с ним
    if ref_image:
        diff_image = get_image_difference(ref_image, new_image)
        # Получаем количество отличающихся пикселей
        diff_pixels = get_black_pixels(diff_image)

        if diff_pixels > 0 or (ref_image.width != new_image.width) or (ref_image.height != new_image.height):
            # Высветляем исходное изображение для лучшей подсветки изменений
            ref_image_bright = increase_image_brightness(ref_image)
            # Создаём фон с цветом подсветки изменений
            magenta = Image.new('RGB', ref_image.size, 'magenta')
            # Накладываем фон на высветленный оригинал используя diff_image как маску
            overlayed_diff_image = ImageChops.composite(ref_image_bright, magenta, diff_image.convert('L'))
            # Сохраняем изображение с подсветкой изменений
            image_io.save_diff_image(overlayed_diff_image)
            # Сохраняем новый скриншот
            image_io.save_new_image(new_image)

            context.run_info.add_status(name, 'different')
        else:
            context.run_info.add_status(name, 'equal')

        return diff_pixels
    # Иначе сохраняем в качестве эталона новый скриншот
    else:
        image_io.save_ref_image(new_image)
        context.run_info.add_status(name, 'new')
        return -1


# Класс для хранения результатов прогона
class RunInfo:
    def __init__(self):
        # Генерируем рандомный идентификатор прогона
        run_id = get_run_id()
        self.run_id = run_id
        self.diff_count = 0
        # Создаём словарь для хранения данных об элементах, участвующих в прогоне
        self.elements = defaultdict(lambda: dict(images=dict()))
        # URL для доступа к JSON прогона на сервере
        self.json_url = f'{REMOTE_STORAGE_URL}{PROJECT_KEY}/{run_id}/info.json'
        # URL для просмотра web-интерфейса с результатом прогона
        self.run_url = f'{SCREENSHOT_RESULTS_URL}{PROJECT_KEY}/{run_id}/'

    # Добавление эталона скриншота элемента
    def add_ref(self, name, url):
        self.elements[name]['images']['ref'] = url

    # Добавление нового скриншота элемента
    def add_new(self, name, url):
        self.elements[name]['images']['new'] = url

    # Добавление скриншота элемента с отличиями от предыдущего эталона
    def add_diff(self, name, url):
        self.elements[name]['images']['diff'] = url
        self.diff_count += 1

    # Проставление статуса элемента (новый, совпадает, отличается)
    def add_status(self, name, status):
        self.elements[name]['status'] = status

    # Сохранение данных прогона в JSON на сервере
    def save_run(self):
        json_str = json.dumps(self.elements)
        requests.put(self.json_url, data=json_str)

    def print_results(self):
        if self.diff_count > 0:
            diff_count_string = get_units_case(
                self.diff_count,
                (
                    'Обнаружен %d отличающийся элемент',
                    'Обнаружено %d отличающихся элемента',
                    'Обнаружены %d отличающихся элементов'
                )
            )
            raise RuntimeError(diff_count_string % self.diff_count)
