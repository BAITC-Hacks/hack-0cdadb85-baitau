# Core: заметка для интеграции

Публичный вызов: `from core import run_pipeline`, затем
`run_pipeline(request, contractors)`. Внешние зависимости и API-ключи не нужны.
Объяснения пока детерминированные, LLM не подключена.

## Загрузка данных — участнику helpers

Источник: `given_data/hackathon dataset anonymized .csv`, 66 профилей.
Core принимает подготовленный `list[dict]`, а не строки CSV:

- `categories`, `event_formats`, `languages`, `busy_dates`: разделить по `|`;
- `price_from_kzt`: `int`;
- `max_hours`: `int`, пустое значение → `None`;
- `synthetic`, `city_imputed`, `price_imputed`: строки `True`/`False` → `bool`.
  Не использовать `bool(text)`: `bool("False")` возвращает `True`.
- Сохранить все даты занятости и флаги происхождения данных.

Конвертация в `core/test_catalog.py` служит только тестам, не заменяет production loader.

## UI — участнику ветки light

Проверена версия `10cebf5`: импорт `core.generator.run_pipeline` совместим.
Её загрузчик пока ищет `helpers.utils.load_contractors()`,
`helpers/contractors.json` или `data/contractors.json`, затем использует встроенный
демо-каталог. Само наличие `given_data` не подключает реальные профили к UI.
Для сборки нужен loader helpers или подготовленный JSON по одному из этих путей.

Корректный запрос возвращает `matched`, `no_category_in_city` или
`no_eligible_candidates`. Некорректный запрос вызывает `ValueError`;
обёртка UI/helpers должна обработать ошибку ввода.

## Проверенные сценарии реального каталога

Алматы, Фотограф, свадьба, 400000 ₸, 8 часов, русский:

| Дата | ID результатов в порядке рейтинга |
| --- | --- |
| 2026-11-14 | HK-68220, HK-76268, HK-91112 |
| 2026-11-15 | HK-68220, HK-91112 |

Проверки: `python -B -m unittest core.test_generator core.test_catalog -v`.
Тесты реального каталога дополнительно проверяют каждую занятую дату каждого профиля.
