# Hermes-Orchestra

**Управление проектами и задачами внутри Hermes Agent.**

Персистентное SQLite-хранилище для проектов, задач, подзадач и истории исполнения. Всё живёт в `~/.hermes/state.db` — той же базе, что и сессии Hermes. Не теряется при `/reset`, перезапуске или смене сессии.

## Возможности

- **Проекты**: создавай, обновляй, архивируй. Группировка по клиентам.
- **Задачи**: древовидная структура (родитель → подзадачи), статусы, приоритеты, дедлайны.
- **Разбивка**: `task_breakdown` атомарно дробит задачу на N подзадач.
- **Назначение**: `task_assign` закрепляет задачу за Hermes, Codex, Claude или любым другим агентом.
- **История**: каждое изменение статуса логируется в task_events.
- **Статистика**: `project_stats` показывает сколько задач в каждом статусе.

## Установка

**Одна команда:**

```bash
curl -fsSL https://raw.githubusercontent.com/NikolayGusev-astra/hermes-orchestra/main/install.sh | bash
```

Установщик:
1. Проверяет/устанавливает Hermes Agent
2. Клонирует репозиторий
3. Копирует тулы в tools directory Hermes
4. Устанавливает skill

## Использование

```bash
# Загрузить skill
hermes -s hermes-orchestra

# Или внутри сессии
# /skill hermes-orchestra
```

**В сессии Hermes:**

```
> project_create(name="Site Audit", client="Client A")
> task_create(project_id="proj-...", title="Analyze logs")
> task_breakdown(task_id="...", subtasks=[
    {title: "Parse format"},
    {title: "Build report"},
  ])
> task_assign(subtask_1, assignee="hermes")
> task_assign(subtask_2, assignee="claude")
> task_update(task_id, status="completed")
```

## Доступные тулы

### Проекты
| Тул | Описание |
|-----|----------|
| `project_create(name, description, client)` | Создать проект |
| `project_get(project_id)` | Детали проекта + статистика задач |
| `project_list(status, client)` | Список проектов с фильтрами |
| `project_update(project_id, ...)` | Обновить поля |
| `project_delete(project_id)` | Архивация (soft delete) |

### Задачи
| Тул | Описание |
|-----|----------|
| `task_create(project_id, title, description, parent_task_id)` | Создать задачу |
| `task_get(task_id)` | Детали задачи + ивенты |
| `task_list(project_id, status, assignee)` | Список с фильтрами |
| `task_update(task_id, title, description, status, assignee, priority, deadline)` | Обновить |
| `task_breakdown(parent_task_id, subtasks=[{title, description}])` | Разбить на подзадачи |
| `task_assign(task_id, assignee)` | Назначить агенту |
| `task_delete(task_id)` | Отменить (soft delete) |

## Как это работает

Hermes-Orchestra — это не форк Hermes, а **расширение**:
- 3 Python-файла в `tools/`: `project_store.py` (SQLite), `project_tool.py` (регистрация тулов), `task_tool.py` (регистрация тулов)
- 1 skill: `SKILL.md` с описанием workflow
- Установщик копирует файлы в нужные места и подключает тулсет `orchestra`

При импорте `project_tool.py` и `task_tool.py` вызывают `registry.register()`, и Hermes автоматически обнаруживает новые тулы.

## Архитектура

```
Hermes Agent session
  └── tools/project_tool.py   → registry.register("project_create", ...)
  └── tools/task_tool.py      → registry.register("task_create", ...)
  └── tools/project_store.py  → SQLite (state.db)
                                ├── projects
                                ├── tasks
                                └── task_events
```

## Лицензия

MIT
