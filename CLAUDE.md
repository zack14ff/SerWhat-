# SerWhat?

Два независимых проекта:

- `nickbot/` — Telegram-бот NickForge (Python, aiogram 3): проверка ников и ИИ-подбор.
  Тесты: `cd nickbot && python -m pytest tests`.
- `serwhat/` — менеджер локальных серверов (Python + Eel).

## Подбор и проверка ников

Чтобы проверить, свободны ли ники в Telegram, запускай из корня репозитория:

```bash
python nickbot/nickcheck.py --json ник1 ник2 ...
```

Статус ника бери только из вывода этого скрипта. Полный порядок подбора —
в skill `/find-nick` (`.claude/skills/find-nick/SKILL.md`).
