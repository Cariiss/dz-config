import sys
import json
import re
import argparse
from pathlib import Path


# Глобальные переменные для хранения состояния
CONSTANTS = {}
RESULT = {}

# Удаляем комменты
def remove_comments(text: str) -> str:
    lines = text.split('\n')
    clean_lines = []
    
    for line in lines:
        # Находим символ комментария
        comment_index = line.find('#')
        if comment_index != -1:
            # Оставляем только часть до комментария
            line = line[:comment_index]
        clean_lines.append(line)
    
    return '\n'.join(clean_lines)

# Парсим строку как число
def parse_number(value_str: str):
    # Убираем пробелы
    value_str = value_str.strip()
    
    if '.' in value_str:
        # Если есть точка - это float
        return float(value_str)
    else:
        # Иначе - int
        return int(value_str)

# Парсим строку в формате [[текст]] и удаляем скобки
def parse_string(value_str: str) -> str:
    if value_str.startswith('[[') and value_str.endswith(']]'):
        # Убираем [[ и ]]
        return value_str[2:-2]
    return value_str

# Парсим массив (проверяем он или не он и тд)
def parse_array(value_str: str):
    # Проверяем, что это действительно массив
    if not (value_str.startswith('list(') and value_str.endswith(')')):
        return value_str
    
    # Убираем 'list(' и ')'
    inner = value_str[5:-1].strip()
    
    # Если массив пустой
    if not inner:
        return []
    
    # Разделяем элементы, учитывая вложенные структуры
    items = []
    current = ""
    depth = 0  # глубина вложенных скобок
    in_string = False  # находимся ли внутри строки [[...]]
    
    for char in inner:
        if char == '[' and not in_string:
            # Начинается строка [[
            in_string = True
            current += char
        elif char == ']' and in_string:
            # Заканчивается строка ]]
            in_string = False
            current += char
        elif char == '(' and not in_string:
            # Начинается вложенная структура
            depth += 1
            current += char
        elif char == ')' and not in_string:
            # Заканчивается вложенная структура
            depth -= 1
            current += char
        elif char == ',' and depth == 0 and not in_string:
            # Разделитель элементов на верхнем уровне
            if current.strip():
                items.append(parse_value(current.strip()))
            current = ""
        else:
            current += char
    
    # Добавляем последний элемент
    if current.strip():
        items.append(parse_value(current.strip()))
    
    return items

# Проверяем на константу |const| true or false
def is_constant_usage(value_str: str) -> bool:
    value_str = value_str.strip()
    return value_str.startswith('|') and value_str.endswith('|')

# Извлекаем имя константы
def get_constant_name(value_str: str) -> str:
    # Убираем | и пробелы
    return value_str[1:-1].strip()

# Основная функция для проверки типа значения
def parse_value(value_str: str):
    global CONSTANTS
    
    value_str = value_str.strip()
    
    # Если строка пустая
    if not value_str:
        return None
    
    # Если это использование константы
    if is_constant_usage(value_str):
        const_name = get_constant_name(value_str)
        if const_name in CONSTANTS:
            return CONSTANTS[const_name]
        else:
            raise ValueError(f"Неизвестная константа: {const_name}")
    
    # Если это число (целое или с плавающей точкой)
    # Регулярное выражение: одна или больше цифр, потом может быть точка и цифры
    if re.match(r'^\d+(\.\d*)?$', value_str):
        return parse_number(value_str)
    
    # Если это строка в формате [[...]]
    if value_str.startswith('[[') and value_str.endswith(']]'):
        return parse_string(value_str)
    
    # Если это массив
    if value_str.startswith('list(') and value_str.endswith(')'):
        return parse_array(value_str)
    
    # Если это булево значение
    if value_str.lower() in ['true', 'false']:
        return value_str.lower() == 'true'
    
    # Если это имя переменной (только буквы, цифры и подчеркивания)
    if re.match(r'^[a-zA-Z][_a-zA-Z0-9]*$', value_str):
        # Проверяем, не ключевое ли это слово
        if value_str in ['global', 'list']:
            return value_str
        
        # Если это не ключевое слово, считаем строкой
        return value_str
    
    # Во всех остальных случаях считаем строкой
    return value_str

# Обрабатывает объявление глобальной константы(global a = ...) -> true or false
def process_global_declaration(line: str) -> bool:
    global CONSTANTS
    
    # Убираем пробелы в начале и конце
    line = line.strip()
    
    # Проверяем, начинается ли строка с "global "
    if not line.startswith('global '):
        return False
    
    # Убираем "global " и точку с запятой в конце
    content = line[7:].rstrip(';').strip()
    
    # Должен быть знак равенства
    if '=' not in content:
        raise ValueError(f"Некорректное объявление константы: {line}")
    
    # Разделяем на имя и значение
    parts = content.split('=', 1)
    name = parts[0].strip()
    value_str = parts[1].strip()
    
    # Проверяем корректность имени
    # Имя должно начинаться с буквы, может содержать буквы, цифры и подчеркивания
    if not re.match(r'^[a-zA-Z][_a-zA-Z0-9]*$', name):
        raise ValueError(f"Некорректное имя константы: {name}")
    
    # Парсим значение
    value = parse_value(value_str)
    
    # Сохраняем константу
    CONSTANTS[name] = value
    return True

# Обработка присваивания значений
def process_assignment(line: str) -> bool:
    global RESULT
    
    # Убираем пробелы и точку с запятой
    line = line.strip().rstrip(';')
    
    # Должен быть знак равенства
    if '=' not in line:
        return False
    
    # Разделяем на имя и значение
    parts = line.split('=', 1)
    if len(parts) != 2:
        return False
    
    name = parts[0].strip()
    value_str = parts[1].strip()
    
    # Проверяем корректность имени
    if not re.match(r'^[a-zA-Z][_a-zA-Z0-9]*$', name):
        raise ValueError(f"Некорректное имя переменной: {name}")
    
    # Парсим значение
    value = parse_value(value_str)
    
    # Сохраняем в результат
    RESULT[name] = value
    return True

# Главная функция - проверка начального файла и вывод в словарь
def parse_config(config_text: str) -> dict:
    global CONSTANTS, RESULT
    
    # Очищаем глобальные переменные
    CONSTANTS.clear()
    RESULT.clear()
    
    # Удаляем комментарии
    clean_text = remove_comments(config_text)
    
    # Разбиваем на строки
    lines = clean_text.split('\n')
    
    # Первый проход: сбор констант
    for line in lines:
        line = line.strip()
        if line:  # Пропускаем пустые строки
            process_global_declaration(line)
    
    # Второй проход: обработка остальных строк
    for line in lines:
        line = line.strip()
        
        # Пропускаем пустые строки
        if not line:
            continue
        
        # Пропускаем объявления констант (они уже обработаны)
        if line.startswith('global '):
            continue
        
        # Пробуем обработать как присваивание
        if not process_assignment(line):
            # Если не присваивание, возможно это просто значение
            # Например, в корневом уровне JSON
            try:
                value = parse_value(line.rstrip(';'))
                # Создаем уникальное имя
                key = f"item_{len(RESULT)}"
                RESULT[key] = value
            except:
                # Если не получается распарсить, пропускаем
                pass
    
    return RESULT.copy()  # Возвращаем копию, чтобы защитить оригинал


def save_to_json(data: dict, output_file: str = None):
    # Преобразуем в JSON с форматированием
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(json_str)
    print(f"Результат сохранен в файл: {output_file}")



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file')
    parser.add_argument('-o', '--output')
    
    # Парсим аргументы
    args = parser.parse_args()
    
    # Проверяем существование входного файла
    if not Path(args.input_file).exists():
        print(f"Ошибка: файл '{args.input_file}' не найден", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Читаем входной файл
        with open(args.input_file, 'r', encoding='utf-8') as f:
            config_text = f.read()
        
        # Парсим конфигурацию
        result = parse_config(config_text)
        
        # Сохраняем или выводим результат
        save_to_json(result, args.output)
        
    except Exception as e:
        print(f"Ошибка при обработке файла: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    # Если программа запущена без аргументов, то выводим ошибку
    if len(sys.argv) == 1:
        print("Недостаточно агрументов для запуска")
    else:
        main()