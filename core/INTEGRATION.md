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

В `main` коммитом `2945aa1` опубликованы `helpers/contractors.json` и production
loader `helpers.utils.load_contractors()`. Проверено полное совпадение загруженных
66 профилей с CSV, включая даты и флаги. Конвертация в `core/test_catalog.py`
служит независимым эталоном для тестов, не заменяет production loader.

## UI — участнику ветки light

Проверена версия `10cebf5`: импорт `core.generator.run_pipeline` совместим.
Её загрузчик ищет `helpers.utils.load_contractors()`, затем JSON или встроенный
демо-каталог. Теперь helpers доступны: после объединения с обновлённым `main`
этот путь загрузки может использовать реальный каталог. Сам UI в нашей ветке
не запускался; проверена связка loader → Core → `safe_pipeline_call`.

```python
from core import run_pipeline
from helpers.utils import load_contractors, safe_pipeline_call

result = safe_pipeline_call(run_pipeline, request, load_contractors())
assert result["fallback"] is False  # Для корректного запроса при штатной работе.
```

Корректный запрос возвращает `matched`, `no_category_in_city` или
`no_eligible_candidates`. Некорректный запрос вызывает `ValueError`;
обёртка UI/helpers должна обработать ошибку ввода.

## Проверенные сценарии реального каталога

Алматы, Фотограф, свадьба, 400000 ₸, 8 часов, русский:

| Дата | ID результатов в порядке рейтинга |
| --- | --- |
| 2026-11-14 | HK-68220, HK-76268, HK-91112 |
| 2026-11-15 | HK-68220, HK-91112 |

Общие проверки: `python -B -m unittest discover -v`.
Проверены все три статуса через настоящую обёртку helpers, опциональные поля,
нормализация даты/бюджета/длительности и отсутствие скрытого перехода на mock.
Тесты реального каталога дополнительно проверяют каждую занятую дату каждого профиля.
