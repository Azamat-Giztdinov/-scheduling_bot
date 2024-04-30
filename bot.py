import telebot
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler
from telebot import types
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.triggers.cron import CronTrigger
from datetime import timedelta, datetime
import pytz
import calendar
import datetime
from dotenv import load_dotenv
import os
import download_db as db
from datetime import datetime, date


load_dotenv()
bot = telebot.TeleBot(os.getenv('TELEGRAM_API_TOKEN'))

bot.remove_webhook()
bot.set_webhook()

PASSWORD_CHECK = {}
PASSWORD_UPDATE = {}

@bot.message_handler(func=lambda message: message.chat.type == 'private' and PASSWORD_CHECK.get(message.chat.id))
def check_password(message):
    if command_slash(message):
        del PASSWORD_CHECK[message.chat.id]
        return
    password = message.text
    if db.hash_password(password) == get_admin_pass():
        update_admin(message.from_user.id)
        admin_command(message)
    else:
        bot.send_message(message.chat.id, "❗️ Упс, пароль неверный. Попробуйте снова через команду /admin")
    # Удаляем состояние проверки пароля
    del PASSWORD_CHECK[message.chat.id]


@bot.message_handler(commands=['admin'], func=lambda message: message.chat.type == 'private')
def admin_command(message):
    if PASSWORD_UPDATE.get(message.chat.id): del PASSWORD_UPDATE[message.chat.id]

    if message.from_user.id == get_admin_id():
        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        upload_button = types.KeyboardButton(text="Загрузить Excel⠀")
        update_nick_button = types.KeyboardButton(text="Удалить ник⠀")
        update_password_button = types.KeyboardButton(text="Сменить пароль⠀")
        keyboard.add(upload_button, update_nick_button, update_password_button)
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=keyboard)
   
    else:
        bot.send_message(message.chat.id, "🔐 Чтобы двигаться дальше, введите пароль администратора.")
        # Сохраняем состояние для проверки пароля
        PASSWORD_CHECK[message.chat.id] = True



@bot.message_handler(func=lambda message: message.chat.type == 'private' and PASSWORD_UPDATE.get(message.chat.id))
def update_password(message):
    if command_slash(message):
        return
    if message.text.endswith('⠀'):
        del PASSWORD_UPDATE[message.chat.id]
        handle_main_menu_option(message)
        return
    if get_admin_id() != message.from_user.id:
        bot.send_message(message.chat.id, "Ошибка: Вы не являетесь администратором.")
    else:
        new_password = message.text
        if message.text.startswith("/") or len(message.text) < 6:  # Проверяем, что это не команда
            bot.send_message(message.chat.id, "😶 Ой-ой, пароль должен быть длиннее 6 символов и не может начинаться с '/'.")
            del PASSWORD_UPDATE[message.chat.id]  # Сбрасываем флаг
            admin_command(message)
            return
        conn = sqlite3.connect('schedule.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE admin SET password = ? WHERE id = ?", (db.hash_password(new_password), 1))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "🔑 Пароль обновлен.")  
    # Удаляем состояние обновления пароля
    del PASSWORD_UPDATE[message.chat.id]


def update_admin(admin_id):
    conn = sqlite3.connect('schedule.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("UPDATE admin SET admin_id = ? WHERE id = ?", (admin_id, 1))
    conn.commit()
    conn.close()


def get_admin():
    conn = sqlite3.connect('schedule.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admin")
    result = cursor.fetchone()
    conn.close()
    return result

def get_admin_id():
    admin_info = get_admin()
    return admin_info['admin_id']

def get_admin_pass():
    admin_info = get_admin()
    return admin_info['password']


# Функция для загрузки файла Excel
def upload_excel_function(message):
    # Путь к файлу Excel
    excel_path = './example/schedule.xlsx'
    bot.send_message(message.chat.id, "*Пожалуйста, загрузите файл Excel (.xlsx).*\n\nУбедитесь, что в файле только один лист с дежурствами, и удалите легенду.\n_(пример правильного файла прикрепляю ⬇️)_ ", parse_mode="Markdown" )
    # Отправить файл Excel
    bot.send_document(message.chat.id, open(excel_path, 'rb'))
    bot.register_next_step_handler(message,lambda m: handle_document(m)) 


def handle_document(message):
    if get_admin_id() == message.from_user.id and message.content_type == 'document':
        if message.document.mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            start_message = bot.send_message(message.chat.id, "Начинаю обрабатывать файл. Дайте мне немножечко времени, пожалуйста...")
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            file_name = 'grafic.xlsx'
            with open(file_name, 'wb') as new_file:
                new_file.write(downloaded_file)
            bot.send_chat_action(message.chat.id, 'upload_document')
            if db.download_excel():
                bot.edit_message_text("Отлично! Ваш файл успешно загружен и обработан. 😊", message.chat.id, start_message.message_id)
            else:
                bot.edit_message_text("Неверный формат", message.chat.id, start_message.message_id)
            for file in os.listdir('.'):
                if file.endswith('.xlsx'):
                    os.remove(file)
        else:
            bot.send_message(message.chat.id, "Ой, что-то пошло не так.. Пожалуйста, попробуйте еще раз загрузить Excel файл (.xlsx).")
    elif message.content_type != 'document':
        if message.text.endswith("⠀"):
            handle_main_menu_option(message)
            return
        if command_slash(message):
            return
        bot.send_message(message.chat.id, "Ой, что-то пошло не так.. Пожалуйста, попробуйте еще раз загрузить Excel файл (.xlsx).")        
        bot.register_next_step_handler(message,lambda m: handle_document(m))

def enter_nick(message, user_id):
    keyboard = InlineKeyboardMarkup()
    yes_button = InlineKeyboardButton(text="Да", callback_data=f"yes_delete#{user_id}")
    no_button = InlineKeyboardButton(text="Нет", callback_data="no_delete#")
    keyboard.add(yes_button, no_button)
    rewrite(message, f"Вы хотите удалить ник для {get_username_by_id_table(user_id)}?", keyboard)


# Функция для обновления ника
def update_nick_function(message):
    users_without_nick = get_users_with_nick()  # Получаем список пользователей ника из базы данных
    if users_without_nick: 
        # Сортируем пользователей по имени в алфавитном порядке
        users_without_nick_sorted = sorted(users_without_nick, key=lambda user: db.decrypt(user['username']))
        keyboard = InlineKeyboardMarkup()
        for user in users_without_nick_sorted:
            if check_tgid_for_group(user['telegram_id']):
                user_button = InlineKeyboardButton(text=f"{db.decrypt(user['username'])} @{get_nickname_by_tgid(user['telegram_id'])}", callback_data=f"select_user#{user['id']}")
                keyboard.row(user_button)
        sent_message = bot.send_message(message.chat.id, "Выберите пользователя, чей ник нужно удалить:", reply_markup=keyboard)
        scheduler.add_job(delete_message, 'date', run_date=datetime.now() + timedelta(minutes=2), args=[sent_message.chat.id, sent_message.message_id])
    else:
        bot.send_message(message.chat.id, "Пользователи еще не успели зарегистрироваться. Вы всегда можете удалить их позже! 😉")

def get_users_with_nick():
    conn = sqlite3.connect('schedule.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id IS NOT NULL")
    result = cursor.fetchall()
    conn.close()
    return result   


# Обработчик для нажатия кнопки "Да" или "Нет"
@bot.callback_query_handler(func=lambda call: call.data in ["yes", "no"])
def callback_handler(call):
    if call.data == "yes":
        text = "*Введите ваше Имя Отчество Ф.:*\n\n❗️ Пожалуйста, не пишите фамилию целиком. Оставьте только одну букву.\n_прим: Венера Николаевна Т._"
        rewrite(call.message, text)
        bot.register_next_step_handler(call.message,  lambda m: get_user_name(m, 1))
    elif call.data == "no":
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(types.InlineKeyboardButton("Да", callback_data="yes2"),
                        types.InlineKeyboardButton("Нет", callback_data="no2"))
        text = "Хорошо, может вы хотите взаимодействовать с ботом?"
        rewrite(call.message, text, keyboard)


# Обработчик для нажатия кнопки "Да" или "Нет"
@bot.callback_query_handler(func=lambda call: call.data in ["yes2", "no2"])
def callback_handler(call):
    if call.data == "yes2":
        text = "*Введите ваше Имя Отчество Ф.:*\n\n❗️ Пожалуйста, не пишите фамилию целиком. Оставьте только одну букву.\n_прим: Венера Николаевна Т._"
        rewrite(call.message, text)
        bot.register_next_step_handler(call.message,  lambda m: get_user_name(m, 0))
    elif call.data == "no2":
        rewrite(call.message, "Понял, принял, обработал:) Когда нужна будет помощь, просто нажмите /start")
        

# Обработчик для Inline-кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data.startswith("select_user#"):
        data_parts = call.data.split("#")
        user_id = int(data_parts[1])
        if get_admin_id() == call.message.chat.id:
            enter_nick(call.message, user_id)
        else:
            rewrite(call.message, "Вы больше не администратор")
        return
    elif call.data.startswith("yes_delete#"):
        data_parts = call.data.split('#')
        user_id = int(data_parts[1])
        if get_admin_id() == call.message.chat.id:
            delete_tg_id(user_id)
            rewrite(call.message, f"Пользователь {get_username_by_id_table(user_id)} больше не зарегистрирован.")
        else:
            rewrite(call.message, "Вы больше не администратор")
        return
    elif call.data == "no_delete#":
        rewrite(call.message, "Пользователь не удален")
        return
    elif call.data.startswith("confirm_yes#"):
        data_parts = call.data.split("#")
        update_user_info(data_parts[1], call.message.chat.id, int(data_parts[2]))
        rewrite(call.message, "Приветствую!\nПомните, что настройка оповещений о дежурствах всегда под рукой. Просто выберите _Состояние оповещений_ в меню.")
        get_duty_menu(call.message)
    elif call.data == "confirm_no":
        rewrite(call.message, "Кажется, пора начать все с чистого листа. Просто отправьте /start, чтобы начать регистрацию заново. Удачи!")
    else:
        check_button(call)
    
def check_button(call):
    if not check_tgid_for_group(call.message.chat.id) or not get_userid_by_tgid(call.message.chat.id):
        if get_userid_by_tgid(call.message.chat.id):
            delete_tg_id(call.message.chat.id)
        rewrite(call.message, "Нет доступа.")
        return
    
    elif call.data.startswith("get_user_schedule#"):
        data_parts = call.data.split("#")
        table_id = int(data_parts[1])
        get_all_duty_sec(call.message,table_id, call.message.message_id, 1)

    elif call.data.startswith("yes_delete_me#"):
        data_parts = call.data.split('#')
        id = int(data_parts[1])
        delete_tg_id(id)
        rewrite(call.message, f"Чтобы вернуться, просто наберите /start 😎")
    elif call.data == "no_delete_me#":
        rewrite(call.message, "Можете продолжать работу. Вы с нами:)")
    elif call.data == "yes_unmark":
        unmark_realization(call.message)
        get_duty_menu(call.message)
    elif call.data == "no_unmark":
        rewrite(call.message, "Оповещения в группе остались включены.")
    elif call.data == "yes_mark":
        mark_realization(call.message)
        get_duty_menu(call.message)
    elif call.data == "no_mark":
        rewrite(call.message, "Оповещения в группе остались отключены.")
    elif call.data.startswith("month#"):  
        _, selected_month, user_id, all_duty = call.data.split("#")  
        duty_days = get_duty_days_by_month(selected_month, int(user_id), int(all_duty))  
        # Формируем текст для сообщения  
        duty_days_text = "\n".join(str(day) for day in duty_days) if duty_days else "Дежурства отсутствуют."  
        # Создаем клавиатуру с кнопкой "Назад"  
        keyboard = types.InlineKeyboardMarkup()  
        keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data=f"backtomonthselection#{user_id}#{call.message.message_id}#{all_duty}"))  
        # Отправляем сообщение с дежурствами и кнопкой "Назад"  
        rewrite(call.message, f"*{selected_month}*:\n{duty_days_text}", keyboard) 
    elif call.data.startswith("backtomonthselection#"): 
        _, user_id, message_id, all_duty = call.data.split("#")        
        get_all_duty_sec(call.message, int(user_id), int(message_id), int(all_duty))
    elif call.data.startswith("backtousersection#"):
        get_nicks_for_schedule(call.message)
    else:
        bot.send_message(call.message.chat.id, "Ошибка: неверный формат данных.")


def rewrite(message, text, keyboard=None):
    return bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id,  
                            text=text,  
                            reply_markup=keyboard, parse_mode="Markdown")


def delete_tg_id(id):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET telegram_id = ?, access = false WHERE id = ?", (None, id))
    conn.commit()
    conn.close()


def update_user_info(id, telegram_id, arg):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET telegram_id = ?, access = ? WHERE id = ?", (telegram_id, arg, id))
    conn.commit()
    conn.close()


@bot.message_handler(commands=['start'], func=lambda message: message.chat.type == 'private' and not PASSWORD_UPDATE.get(message.chat.id))
def start(message):
    if PASSWORD_UPDATE.get(message.chat.id): del PASSWORD_UPDATE[message.chat.id]

    if not get_group_id():
        bot.reply_to(message, "Ой, кажется, я еще не присоединился к группе. Пожалуйста, запустите команду /start позже.")
        return
    user_id = message.from_user.id
    if not get_chat_member(user_id):
        bot.reply_to(message, 'Ошибка в студии!\n\nВы не состоите в рабочей группе. Попросите админа добавить вас и затем запустите /start снова.')
        return
    if message.from_user.username:
        if not check_table():
            bot.send_message(message.chat.id, "Ой, кажется у меня еще нет вашего графика. Пожалуйста, запустите команду /start позже.")
            return
        conn = sqlite3.connect('schedule.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE telegram_id = ? LIMIT 1', (user_id,))
        existing_user = cursor.fetchone()
        conn.close()
        if not existing_user:
            # Создаем клавиатуру с inline-кнопками "Да" и "Нет"
            keyboard = types.InlineKeyboardMarkup()
            keyboard.row(types.InlineKeyboardButton("Да", callback_data="yes"),
                        types.InlineKeyboardButton("Нет", callback_data="no"))
            # Отправляем сообщение с вопросом о получении отметок
            bot.send_message(message.chat.id, "Хотите, чтобы я оповещал вас в рабочей группе о предстоящем дежурстве?", reply_markup=keyboard)
        else:
            get_duty_menu(message)
    else:
        bot.send_message(message.chat.id, "Похоже, у вас еще нет никнейма в Telegram. Пожалуйста, добавьте его и начните регистрацию заново, отправив команду /start.")


def get_duty_menu(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    profile_button = types.KeyboardButton("👤 Профиль⠀")
    duties_button = types.KeyboardButton("📅 Моё дежурство⠀")
    mark_button = types.KeyboardButton("✅ Состояние оповещений⠀")
    who_is_duty_button = types.KeyboardButton("❓ Кто дежурит⠀")
    keyboard.add(profile_button, duties_button, mark_button, who_is_duty_button)
    bot.send_message(message.chat.id,'Выберите опцию.', reply_markup=keyboard)


def check_table():
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM schedule LIMIT 1')
    check = cursor.fetchone()
    conn.close()
    return True if check else False


def update_password_query(message):
    bot.send_message(message.chat.id, "Давайте зададим новый пароль.\nПожалуйста, введите его:")
    # Сохраняем состояние для обновления пароля
    PASSWORD_UPDATE[message.chat.id] = True


@bot.message_handler(func=lambda message: message.chat.type == 'private', content_types=['text'] )
def handle_main_menu_option(message):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username FROM users WHERE telegram_id = ? LIMIT 1', (message.from_user.id,))
    res = cursor.fetchone()
    username = res[1] if res else None
    id = res[0] if res else None
    conn.close()
    if check_message_adm(message.text):
        if message.from_user.id == get_admin_id():
            if message.text == "Загрузить Excel⠀":
                upload_excel_function(message)
                return
            elif message.text == "Удалить ник⠀":
                update_nick_function(message)
                return
            elif message.text == "Сменить пароль⠀":
                update_password_query(message)
                return
        else:
            remove_menu(message.chat.id)
    if username and get_chat_member(message.from_user.id):
        if message.text == "👤 Профиль⠀":
            profile_click(message, message.from_user.username, username)
        elif message.text == "📅 Моё дежурство⠀":
            duty_click(message)
        elif message.text == "✅ Состояние оповещений⠀":
            mark_click(message)
        elif message.text == "📍 Ближайшее дежурство⠀":
            get_first_duty(message, id)
        elif message.text == "🏠 Ближайший выходной⠀":
            get_duty_off(message, id)
        elif message.text == "📆 Расписание⠀":
            get_all_duty_sec(message, id)
        elif message.text == "⏪ Назад⠀":
            get_duty_menu(message)
        elif message.text == "⛔️ Отключить оповещения в группе⠀":
            unmark(message)
        elif message.text == "✅ Включить оповещения в группе⠀":
            mark(message)
        elif message.text == "❓ Кто дежурит⠀":
            who_is_duty_click(message)
        elif message.text == "🗑️ Удалить профиль⠀":
            profile_delete(message, id)
        elif message.text == "🔢 По дате⠀":
            bot.send_message(message.chat.id, f"Пожалуйста, введите дату, за которую хотите посмотреть дежурных, в формате: *dd.mm*\n\n*(прим: 12.10)*", parse_mode="Markdown")
            bot.register_next_step_handler(message,  lambda m: get_duties_by_date(m))
        elif message.text == "👤 По нику⠀":
            get_nicks_for_schedule(message)
    elif message.from_user.id == get_admin_id():
        return
    elif username and message.text.endswith("⠀"):
        remove_user_id(message.from_user.id)
        remove_menu(message.chat.id)
    elif message.text.endswith("⠀"):
        remove_menu(message.chat.id)


def profile_click(message, tg_name, username):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    delete_profile = types.KeyboardButton("🗑️ Удалить профиль⠀")
    back_button = types.KeyboardButton("⏪ Назад⠀")
    keyboard.add(delete_profile, back_button)
    bot.send_message(message.chat.id, f"👤Пользователь: {db.decrypt(username)}\n#️⃣Ник: @{tg_name}",reply_markup=keyboard)


# Функция для поиска дежурства по нику
def get_nicks_for_schedule(message):
    users_with_nick = get_users_with_nick()  # Получаем список пользователей ника из базы данных
    if users_with_nick: 
        # Создаем список никнеймов и сортируем его
        nicknames = [get_nickname_by_tgid(user['telegram_id']) for user in users_with_nick if get_nickname_by_tgid(user['telegram_id']) is not None]
        sorted_nicknames = sorted(nicknames, key=lambda x: x.lower())

        keyboard = InlineKeyboardMarkup()
        for nickname in sorted_nicknames:
            for user in users_with_nick:
                if get_nickname_by_tgid(user['telegram_id']) == nickname and check_tgid_for_group(user['telegram_id']):
                    user_button = InlineKeyboardButton(text=f"@{nickname}", callback_data=f"get_user_schedule#{user['id']}")
                    keyboard.row(user_button)
                    break

        text = "Выберите пользователя, чье расписание вы хотите узнать:"
        if message.text == "👤 По нику⠀":
            bot.send_message(message.chat.id, text, reply_markup=keyboard)
        else:
            rewrite(message, text, keyboard)
    else:
        bot.send_message(message.chat.id, "Пользователи еще не успели зарегистрироваться. Вы всегда можете посмотреть их расписание позже! 😉")


def check_message_adm(text):
    return text == "Загрузить Excel⠀" or text == "Удалить ник⠀" or text == "Сменить пароль⠀"


def remove_menu(chat_id):
    bot.send_message(chat_id, "Нет доступа.", reply_markup=types.ReplyKeyboardRemove())


def remove_user_id(telegram_id):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET telegram_id = ? WHERE telegram_id = ?", (None, telegram_id))
    conn.commit()
    conn.close()


def unmark_realization(message):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET access = ? WHERE telegram_id = ?", (0, message.chat.id))
    conn.commit()
    conn.close()
    rewrite(message, "Вы отключили оповещения в группе о предстоящем дежурстве.")


def unmark(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(types.InlineKeyboardButton("Да", callback_data=f"yes_unmark"),
                        types.InlineKeyboardButton("Нет", callback_data="no_unmark"))            
    # Отправляем сообщение с вопросом о получении отметок
    bot.send_message(message.chat.id, "Хотите остановить получение оповещений?", reply_markup=keyboard)


def profile_delete(message, id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(types.InlineKeyboardButton("Да", callback_data=f"yes_delete_me#{id}"),
                        types.InlineKeyboardButton("Нет", callback_data="no_delete_me#"))            
    # Отправляем сообщение с вопросом о получении отметок
    bot.send_message(message.chat.id, "Хотите удалить профиль?", reply_markup=keyboard)


def mark(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(types.InlineKeyboardButton("Да", callback_data=f"yes_mark"),
                        types.InlineKeyboardButton("Нет", callback_data="no_mark"))
    # Отправляем сообщение с вопросом о получении отметок
    bot.send_message(message.chat.id, "Хотите включить оповещения в группе?", reply_markup=keyboard)


def mark_realization(message):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET access = ? WHERE telegram_id = ?", (1, message.chat.id))
    conn.commit()
    conn.close()
    rewrite(message, "Вы подключили оповещения в группе о предстоящем дежурстве.")


def mark_click(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute('SELECT access FROM users WHERE telegram_id = ? LIMIT 1', (message.from_user.id,))
    res_access = cursor.fetchone()
    access = res_access[0] if res_access else None
    conn.close()
    back_button = types.KeyboardButton("⏪ Назад⠀")
    str =""
    if access:
        turn_of_button = types.KeyboardButton("⛔️ Отключить оповещения в группе⠀")
        str = "На данный момент оповещения включены."
    else:
        turn_of_button = types.KeyboardButton("✅ Включить оповещения в группе⠀")
        str = "На данный момент оповещения отключены."
    keyboard.add(turn_of_button, back_button)
    bot.send_message(message.chat.id, str , reply_markup=keyboard)


def duty_click(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    first_duty_button = types.KeyboardButton("📍 Ближайшее дежурство⠀")
    first_day_off_button = types.KeyboardButton("🏠 Ближайший выходной⠀")
    all_duty_button = types.KeyboardButton("📆 Расписание⠀")
    back_button = types.KeyboardButton("⏪ Назад⠀")
    keyboard.add(first_duty_button, first_day_off_button, all_duty_button, back_button)
    bot.send_message(message.chat.id, 'Что вас интересует?',reply_markup=keyboard)


def who_is_duty_click(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    by_date_button = types.KeyboardButton("🔢 По дате⠀")
    by_nick_button = types.KeyboardButton("👤 По нику⠀")
    back_button = types.KeyboardButton("⏪ Назад⠀")
    keyboard.add(by_date_button, by_nick_button, back_button)
    bot.send_message(message.chat.id, 'Выберите нужный фильтр для поиска дежурства.',reply_markup=keyboard)

def command_slash(message):
    if message.text.startswith("/"):
        if message.text == "/start":
            start(message)
        elif message.text == "/admin":
            admin_command(message)
        else:
            bot.reply_to(message, 'Данная команда не существует. Попробуйте заново /start')
        return True
    return False


def get_user_name(message,access):
    if message.content_type != 'text':
        bot.reply_to(message, 'Хм🤔, кажется тут есть ошибка. Пожалуйста, проверьте все ли верно и пришлите мне своё Имя Отчество Ф. еще раз.')
        bot.register_next_step_handler(message,lambda m: get_user_name(m, access))
        return
    if command_slash(message):
        return
    user_name = message.text.strip()
    if user_name[-1] != '.':
        user_name += '.'
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? LIMIT 1', (db.encrypt(user_name),))
    existing_user = cursor.fetchone()
    if not existing_user:
        bot.reply_to(message, 'Хм🤔, кажется тут есть ошибка. Пожалуйста, проверьте все ли верно и пришлите мне своё Имя Отчество Ф. еще раз.')
        # Запускаем обработчик ввода ФИО
        bot.register_next_step_handler(message,lambda m: get_user_name(m, access))
    elif existing_user[2] is not None:
        bot.reply_to(message, 'Этот пользователь уже имеет id. Если это вы, попросите администратора удалить ваш прошлый id. ')
    else:
        cursor.execute('SELECT * FROM users WHERE telegram_id = ? LIMIT 1', (message.from_user.id,))
        check_id = cursor.fetchone()
        if not check_id:
            send_registration_confirmation(message, existing_user[0], user_name, access)
        else:
            bot.reply_to(message, "Ваш телеграм id уже используется.")
    conn.close()


def send_registration_confirmation(message, user_id,  username, access):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(types.InlineKeyboardButton("Да", callback_data=f"confirm_yes#{user_id}#{access}"),
                 types.InlineKeyboardButton("Нет", callback_data="confirm_no"))
    bot.send_message(message.chat.id, f"Отлично! {username}, теперь к вам можно обращаться по нику @{message.from_user.username}, верно?", reply_markup=keyboard)


def get_duty_days_by_month(month, user_id, all_duty=0):
    today = date.today()
    month_number = {
        'Январь': '01',
        'Февраль': '02',
        'Март': '03',
        'Апрель': '04',
        'Май': '05',
        'Июнь': '06',
        'Июль': '07',
        'Август': '08',
        'Сентябрь': '09',
        'Октябрь': '10',
        'Ноябрь': '11',
        'Декабрь': '12'
    }
    duty_info = {
        'у': 'утро',
        'в': 'вечер',
        'н': '🏠'
    }
    conn = sqlite3.connect('schedule.db') 
    cursor = conn.cursor() 
    if all_duty:
        cursor.execute('''
        SELECT date, duty FROM schedule WHERE strftime("%m", date) = ? AND user_id = ? ORDER BY date
    ''', (month_number.get(month), user_id))
    else:
        cursor.execute('''
        SELECT date, duty FROM schedule WHERE strftime("%m", date) = ? AND date >= ? AND user_id = ? ORDER BY date
    ''', (month_number.get(month), today.isoformat(), user_id))
    duty_dates = cursor.fetchall() 
    formatted_dates = []
    conn.close()
    for dat, type in duty_dates:
        formatted_dates.append(f"\t\t{format_date(dat)}\t\t|\t\t{duty_info[type]}")
    return formatted_dates


def get_all_duty_sec(message, user_id, message_id=None, all_duty=0):  # если нужна кнопка назад, то 1, если не нужна то ноль
    month_names_mapping = {
    'January': 'Январь',
    'February': 'Февраль',
    'March': 'Март',
    'April': 'Апрель',
    'May': 'Май',
    'June': 'Июнь',
    'July': 'Июль',
    'August': 'Август',
    'September': 'Сентябрь',
    'October': 'Октябрь',
    'November': 'Ноябрь',
    'December': 'Декабрь'
    }
    unique_months = set()
    # Получаем все даты дежурств пользователя
    duty_morn = get_user_duty(user_id, 'у', False, all_duty)
    duty_even = get_user_duty(user_id, 'в', False, all_duty)
    duty_week = get_user_duty(user_id, 'н', False, all_duty)
    for dat in duty_morn:
        date_datetime = datetime.strptime(dat, "%Y-%m-%d")
        month_name = date_datetime.strftime('%B')  # Получаем название месяца
        unique_months.add(month_name)
    for dat in duty_even:
        date_datetime = datetime.strptime(dat, "%Y-%m-%d")
        month_name = date_datetime.strftime('%B')  # Получаем название месяца
        unique_months.add(month_name)
    for dat in duty_week:
        date_datetime = datetime.strptime(dat, "%Y-%m-%d")
        month_name = date_datetime.strftime('%B')  # Получаем название месяца
        unique_months.add(month_name)
    months_in_order = list(calendar.month_name[1:])
    unique_months = [month for month in months_in_order if month in unique_months]
    # Создаем объект клавиатуры Inline
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    # Добавляем кнопки для каждого месяца из unique_months
    for month in unique_months:
        ru_month = month_names_mapping.get(month)
        # Добавляем кнопку с названием месяца на русском языке
        button = types.InlineKeyboardButton(text=ru_month, callback_data=f"month#{ru_month}#{user_id}#{all_duty}")
        keyboard.add(button)
    # Отправляем сообщение с клавиатурой Inline
    if (all_duty==1):
        button = types.InlineKeyboardButton(text="⬅️ к выбору пользователя", callback_data=f"backtousersection#{user_id}")
        keyboard.add(button)
    if len(unique_months)==0:
        bot.send_message(message.chat.id, "Поздравляем вас с завершением дежурств на этот год! ", reply_markup=keyboard)
    else: 
        if message_id and all_duty: 
            if (get_nickname_by_tgid(get_tgid_by_id(user_id))==None):
                button_only = types.InlineKeyboardButton(text="⬅️ к выбору пользователя", callback_data=f"backtousersection#{user_id}")
                keyboard_only = types.InlineKeyboardMarkup(row_width=1)
                keyboard_only.add(button_only)
                rewrite(message, f"Пользователь больше не зарегистрирован.", keyboard_only)
            else:
                rewrite(message, f"Выберите месяц для @{get_nickname_by_tgid(get_tgid_by_id(user_id))}:", keyboard)
        elif message_id:
            rewrite(message, f"Выберите месяц:", keyboard)
        else: 
            bot.send_message(message.chat.id, "Выберите месяц:", reply_markup=keyboard)


def get_user_duty(user_id, time, limit=False, all_duty=None):
    today = date.today()
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    if all_duty==1:
        cursor.execute(f"SELECT date FROM schedule WHERE duty = ? AND user_id = ?", (time,  user_id))
    else:
        if (limit == False):
            cursor.execute(f"SELECT date FROM schedule WHERE duty = ? AND user_id = ? and date>= ?", (time,  user_id, today.isoformat()))
        else:
            cursor.execute(f"SELECT date FROM schedule WHERE duty = ? AND user_id = ? and date > ? LIMIT 1", (time,  user_id, today.isoformat()))
    rows = cursor.fetchall()
    conn.close()
    if rows:
        return [row[0] for row in rows]
    return []


def format_date(date):
    return datetime.strptime(date, '%Y-%m-%d').strftime("%d.%m.%Y")


def get_first_duty(message, user_id):
    today = date.today()
    conn = sqlite3.connect('schedule.db') 
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM schedule WHERE user_id = ? AND date > ? AND duty != 'н' ORDER BY date LIMIT 1", (user_id, today.isoformat()))
    existing = cursor.fetchone()
    conn.close()
    if existing:
        time = '☀️  утро: ' if existing[2] == 'у' else '🌑  вечер: '
        bot.send_message(message.chat.id, f'{time} {format_date(existing[0])}')
    else:
        bot.send_message(message.chat.id, 'Дежурства в этом году закончились! 🎉 Но наши обязанности не прекращаются. Продолжаем двигаться вперед!')


def get_duty_off(message, user_id):
    list = get_user_duty(user_id, 'н', 1)
    if len(list):
        bot.send_message(message.chat.id, f'🏠  выходной: {format_date(list[0])}')
    else:
        bot.send_message(message.chat.id, 'Ой, у вас больше нет выходных в этом году! 😢 Но не переживайте, они обязательно будут в следующем!')



@bot.message_handler(commands=['adm'], func=lambda message: message.chat.type != 'private')
def start_root(message):
    if message.from_user.id == get_admin_id():
        text = "Приветствую всех!\nЯ новый участник этой группы. Буду напоминать вам о предстоящем дежурстве😉"
        conn = sqlite3.connect('schedule.db') 
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bot_groups")
        existing_group = cursor.fetchone()
        if not existing_group:
            cursor.execute("INSERT INTO bot_groups (group_id) VALUES (?)", (message.chat.id,))
            bot.send_message(message.chat.id, text)
        else:
            if existing_group[1] == message.chat.id:
                bot.reply_to(message, "Рассылка уже запущена.")
            else:
                cursor.execute("UPDATE bot_groups SET group_id = ? WHERE id = ?", (message.chat.id, existing_group[0]))
                bot.send_message(message.chat.id, text)
        conn.commit()
        conn.close()


def get_username_by_id_table(id):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id = ?", (id,))
    username = cursor.fetchone()[0]
    conn.close()
    return db.decrypt(username)


def get_nickname_by_tgid(telegram_id):
    try:
        chat_member = get_chat_member(telegram_id)
        if chat_member:
            return chat_member.user.username
    except Exception as e:
        print(f"Error: {e}")
    return None


def get_chat_member(telegram_id):
    group_id = get_group_id()
    if group_id:
        return is_user_in_chat(group_id, telegram_id)
    return None


def is_user_in_chat(chat_id, telegram_id):
    try:
        chat_member = bot.get_chat_member(chat_id, telegram_id)
        return chat_member if chat_member.status != 'left' else False
    except Exception as e:
        print(f"Ошибка при проверке членства пользователя: {e}")
        return False

def check_tgid_for_group(telegram_id):
    if not get_chat_member(telegram_id):
        delete_tg_id(telegram_id)
        return False
    return True

def get_tgid_by_id(user_id):   
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users WHERE id = ?", (user_id,))
    telegram_id = cursor.fetchone()
    conn.close()
    return telegram_id[0] if telegram_id else telegram_id


def get_userid_by_tgid(telegram_id):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    user_id = cursor.fetchone()
    conn.close()
    return user_id[0] if user_id else user_id


def format_date_without_year(date):  # возвращает строку без года с экранированной точкой
    return date.strftime("%d\.%m")


def send_duty_message(day, arg):
    users_tomorrow = text_get_duties_by_date(day)
    message_text = "Напоминаю🤫\n\n"
    message_text += "График дежурных на завтра " if arg == 0 or arg == "сб" else "График дежурных на воскресенье " if arg == "вс" else "График дежурных на понедельник "
    date_text = f"||\( {format_date_without_year(day)} \)||"
    if users_tomorrow == "Дежурства не найдены.":
        return
    message_text += date_text + ":\n" + users_tomorrow
    sent_message = bot.send_message(get_group_id(), message_text, parse_mode="MarkdownV2") 
    if sent_message:
        add_message_id(day, sent_message.message_id)


def add_message_id(day, message_id):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO message (date, message_id) VALUES (?, ?)", (day.isoformat(), message_id))
    conn.commit()
    conn.close


def send_daily_message():
    today = date.today() 
    tomorrow = today + timedelta(days=1)
    
    if today.weekday() != 5 and today.weekday() != 6:
        if today.weekday() != 4:
            send_duty_message(tomorrow, 0)
        else:
            send_duty_message(tomorrow, "сб")
            send_duty_message(tomorrow + timedelta(days=1), "вс")
            send_duty_message(tomorrow + timedelta(days=2), "пн")        


def delete_message_from_group():
    day = date.today()
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("SELECT message_id FROM message WHERE date <= ?", (day.isoformat(), ))
    messages = cursor.fetchone()
    if messages:
        delete_message(get_group_id(), messages[0])
        cursor.execute("DELETE  FROM message WHERE date <= ?", (day.isoformat(),))
        conn.commit()
    conn.close()        


def delete_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        print(f"Ошибка при удалении сообщения: {e}")   


def get_users_with_status(day):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    day = day.strftime('%Y-%m-%d')
    cursor.execute(f"SELECT user_id, duty FROM schedule WHERE date = ?", (day,))
    duties = cursor.fetchall()
    users_map = {}
    for user_id, duty in duties:
        users_map[user_id] = duty
    conn.close()
    return users_map


def text_get_duties_by_date(date_obj, case = 1): # 1 - daily, 2 - по дате
    message_text = ""
    users_map = get_users_with_status(date_obj)
    # Sort users by duty
    existing_duties = set(users_map.values())
    duty_order = {'у': 0, 'в': 1, 'н': 2}
    sorted_duties = sorted(existing_duties, key=lambda x: duty_order.get(x, float('inf')))
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    for duty in sorted_duties:
        for user_id, user_duty in users_map.items():
            if user_duty == duty:
                if case == 1:
                    cursor.execute("SELECT telegram_id FROM users WHERE id = ? and access = TRUE", (user_id,))
                else:
                    cursor.execute("SELECT telegram_id FROM users WHERE id = ?", (user_id,))
                telegram_id = cursor.fetchone()
                if telegram_id and telegram_id[0] and check_tgid_for_group(telegram_id[0]):
                    nickname = get_nickname_by_tgid(telegram_id[0])
                else:
                    nickname = "unknоwn"
                if duty == 'у':
                    message_text += f"☀️ утро: @{nickname}\n"
                elif duty == 'в':
                    message_text += f"🌑 вечер: @{nickname}\n"
                else:
                    message_text += f"🏡 выходной: @{nickname}\n"
    conn.close()
    if (message_text==""):
        message_text="Дежурства не найдены."
    return message_text


def get_duties_by_date(message):
    try:
        if message.content_type != 'text':
            raise ValueError("Получено сообщение не в текстовом формате")
        if message.text.endswith("⠀"):
            handle_main_menu_option(message)
            return
        if command_slash(message):
            return
        date_str = message.text.strip().replace(" ", "")
        if date_str.endswith('.'):
            date_str = date_str[:-1]
        # Если введена только дата без года, добавляем текущий год
        if len(date_str.split(".")) == 2:
           date_str += "." + str(datetime.now().year)

        parts = date_str.split(".")
        if len(parts) < 3:
            raise ValueError("Некорректный формат даты")
        for i in range(2):
            if len(parts[i]) == 1:
                parts[i] = "0" + parts[i]
        # Проверяем длину года и преобразуем его, если он состоит из двух цифр
        
        if len(parts[-1]) == 2:
            parts[-1] = "20" + parts[-1]
        date_str = ".".join(parts)
        date_obj = datetime.strptime(date_str, "%d.%m.%Y")
       
        if date_obj.year != datetime.now().year:
            raise ValueError

        message_text = f"Дежурство на {date_obj.strftime('%d.%m.%Y')}:\n\n"
        res_users=text_get_duties_by_date(date_obj, 2)
        if (res_users=="Дежурства не найдены."):
            bot.send_message(message.chat.id, f"Кажется, на указанную дату ( {date_obj.strftime('%d.%m.%Y')} ) дежурств нет.")
        else:
            message_text+=res_users
            bot.send_message(message.chat.id, message_text)   
        bot.register_next_step_handler(message,  lambda m: get_duties_by_date(m))

    except ValueError:
        bot.send_message(message.chat.id, "Хм, вы уверены, что ввели дату правильно?\n\n👁️‍🗨️ Проверьте, чтобы она выглядела как *12.10* и самое важное - дата должна быть *в нашем графике*!", parse_mode="Markdown" )
        bot.register_next_step_handler(message,lambda m: get_duties_by_date(m))

def get_group_id():
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT group_id FROM bot_groups")
    group_id = cursor.fetchone()
    if group_id: group_id = group_id[0]
    conn.close()
    return group_id


scheduler = BackgroundScheduler()
# # Создание объекта для работы с часовыми поясами
moscow_tz = pytz.timezone('Europe/Moscow')
# # Запуск задачи по удалению каждый день в 14:58 по московскому времени
scheduler.add_job(delete_message_from_group, CronTrigger(hour=14, minute=58, second=0, timezone=moscow_tz))
# # Запуск задачи по расписанию каждый день в 15:00 по московскому времени
scheduler.add_job(send_daily_message, CronTrigger(hour=15, minute=00, second=0, timezone=moscow_tz))
# # Запуск планировщика
scheduler.start()

if __name__ == "__main__":
    db.create_database()
    bot.polling()