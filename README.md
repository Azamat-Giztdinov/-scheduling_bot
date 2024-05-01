# Уведомляющий бот о дежурствах

Этот телеграм бот предназначен для уведомления сотрудников о предстоящем дежурстве в общей бесседе. Он также отображает информацию о дежурствах сотрудника и его коллег, зарегистрированных в боте.

## Установка



1. **Настройте токен бота**:

   В директории `srs` создайте файл `.env` и добавьте в него токен вашего телеграм бота и ключ:

   ```
   TELEGRAM_API_TOKEN=
   TELEGRAM_KEY=
   ```
2. **Запуск через docker-compose**:

   ```bash
   docker-compose up --build -d
   ```

## Использование

1. **Регистрация администратора**:

    Пользователь заходить как администратор через команду `/admin`, загружает расписание в виде excel-файла и закрепляет бота в нужную группу при помощи команды `/adm`.


2. **Регистрация сотрудников**:

    Регистрация сотрудника выполняется командой `/start`.

3. **Уведомления о дежурствах**:

   Бот будет автоматически уведомлять зарегистрированных сотрудников о предстоящем дежурстве в общем чате.

4. **Просмотр информации о дежурствах**:

   После регистрации сотруднику открывается меню с выбором просмотра профиля, своего дежурства, состояние оповещаний, и информации о том кто дежурит по дате и по нику.


## Разработка

- Этот бот разработан с использованием python и библиотеки [telebot](https://pypi.org/project/pyTelegramBotAPI/) для работы с Telegram API.

## Автор

- [annabelw](https://github.com/annabelwy)
- [quayleco](https://github.com/Azamat-Giztdinov)

