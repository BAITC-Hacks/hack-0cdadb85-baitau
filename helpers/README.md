# Data / Utils / Mock fallback

`contractors.json` содержит все 66 профилей из
`given_data/hackathon dataset anonymized .csv`; `mock_data.json` — подходящие
реальные профили для демо. Исходные busy_dates и provenance-флаги сохранены.
Статистика: Алматы — 50, Астана — 15, Зарубежье — 1; synthetic — 13;
пропусков цен/городов, неверных дат и невалидных записей — 0.

Из корня репозитория:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m helpers.prepare_data 'given_data/hackathon dataset anonymized .csv'
PYTHONDONTWRITEBYTECODE=1 python -m unittest helpers.test_utils helpers.test_dataset -v
```

Конвертер выводит колонки, типы list-полей и статистику, проверяет 66 уникальных
записей, затем сохраняет `helpers/contractors.json` и строит `helpers/mock_data.json`
из реальных подходящих профилей. Демо начинается с 2026-11-14; если все кандидаты
заняты, выбирается ближайший свободный день в течение года. Если подходящих
профилей нет, каталог сохраняется, создание mock завершается с ошибкой.
Названия колонок должны совпадать с контрактом; несовпадения требуют явного
mapping после изучения исходника. Неполные цены/города не выдумываются.
Даты принимаются в YYYY-MM-DD или DD.MM.YYYY и сохраняются в YYYY-MM-DD.

Интеграция Core/UI:

```python
from helpers.utils import load_contractors, load_mock_data, safe_pipeline_call
from core.generator import run_pipeline

contractors = load_contractors()
result = safe_pipeline_call(run_pipeline, request, contractors)
# result["fallback"] == True: аварийное демо, query может отличаться от запроса UI.
```

`load_contractors()` явно сообщает об отсутствующем/некорректном каталоге;
UI может показать `load_mock_data()` при ошибке загрузки. `safe_pipeline_call()`
обрабатывает исключения, None, нарушение контракта и ожидание дольше 15 секунд.
Необязательный keyword `timeout_seconds` позволяет изменить лимит.
Фоновый daemon thread не может отменить сетевой запрос; Core должен выставлять
собственный HTTP timeout. Одновременно допускается максимум четыре вызова;
при исчерпании слотов сразу возвращается fallback. Входные данные копируются.

Если mock отсутствует или повреждён, возвращается валидный пустой ответ
с `fallback: true` и `meta.diagnostics.fallback_reason: "demo_data_unavailable"`.
Это аварийный ответ, а не подтверждение отсутствия подрядчиков в реальном каталоге.
Broken-Core тест с реальным mock возвращает `matched`.

Поле `fallback: bool` добавлено согласно заданию; остальные имена полей сохранены.
Совместимость проверена с `core.generator` из `origin/feature/auth`, коммит
`898b2d1`: все три статуса, необязательные поля, provenance-флаги и лимит трёх
карточек. Бюджет нормализуется в строго положительное целое согласно Core.
Исходный датасет опубликован в `origin/main` коммитом `713a37a`; `app.py` отсутствует.
Совместные тесты после появления Core в checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest helpers.test_utils helpers.test_core_integration core.test_generator -v
```

Передача команде после конвертации:

- Core: `helpers/contractors.json`, `list[dict]`, 66 записей;
  `from helpers.utils import load_contractors`.
- UI: `helpers/mock_data.json`; `from helpers.utils import load_mock_data, safe_pipeline_call`.
  При `fallback` показывать пометку демо и значения `result["query"]`.
