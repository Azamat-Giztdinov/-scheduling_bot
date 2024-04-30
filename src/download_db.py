import pandas as pd
import sqlite3
import datetime
import re
from openpyxl import load_workbook
from dotenv import load_dotenv
import os
import hashlib
import gc



load_dotenv()
key = os.getenv("TELEGRAM_KEY")  
 

def encrypt(text):
    return ''.join(chr(ord(text[i]) ^ ord(key[i % len(key)])) for i in range(len(text)))


def decrypt(encrypted_text):
    decrypted_text = ""
    for i in range(len(encrypted_text)):
        decrypted_text += chr(ord(encrypted_text[i]) ^ ord(key[i % len(key)]))
    return decrypted_text


def hash_password(password):
    password_bytes = password.encode('utf-8')
    hasher = hashlib.sha256()
    hasher.update(password_bytes)
    hashed_password = hasher.hexdigest()
    return hashed_password


def name_abbreviation(username): 
    parts = username.strip().split(' ')
    if len(parts) == 3:
        parts[0] = parts[0][0] + '.'
        parts[0], parts[1]= parts[1], parts[0]
        parts[1], parts[2]= parts[2], parts[1]
    return encrypt(' '.join(parts))


def create_database():
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL Unique,
            telegram_id TEXT Unique,
            access BOOLEAN DEFAULT FALSE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            password TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedule (
            date DATE,
            user_id INTEGER,
            duty TEXT,
            PRIMARY KEY (date, user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message (
            date DATE,
            message_id INTEGER
        )
    ''')
    conn.commit()
    cursor.execute('SELECT * FROM admin')
    check = cursor.fetchone()
    if not check:
        cursor.execute('INSERT INTO admin (password) VALUES (?)', (hash_password("admin"),))
    conn.commit()
    conn.close()
    gc.collect()


def update_lines_db(lines):
    data1 = lines.iloc[0].values
    data2 = lines.iloc[1].values
    updated_data = []
    prev_month = None
    year = int(re.search(r'\d+', str(data2[0])).group())
    data2[0] = 'user_name'
    for item1, item2 in zip(data1, data2):
        if isinstance(item2, str):
            updated_data.append(item2)
        elif not pd.isna(item1) and item1.strip().endswith(')'):
            month_number = int(item1.split('(')[-1].replace(')', '').strip())
            prev_month = month_number
            updated_data.append(datetime.date(year, month_number, int(item2)))
        elif prev_month:
            updated_data.append(datetime.date(year, prev_month, int(item2)))
        else:
            updated_data.append(item2)
    return updated_data


def import_database():
    path = 'grafic.xlsx'
    wb = load_workbook(path)
    ws = wb.active
    ws.delete_rows(0,1)
    excel_data = pd.read_excel(wb, engine='openpyxl')
    wb.close()
    excel_data = excel_data.iloc[:, :-1]
    excel_data.columns = range(len(excel_data.columns))
    excel_data = excel_data.drop([0,2,3], axis=1)
    first_two_rows = excel_data.iloc[:2]
    line = update_lines_db(first_two_rows)
    excel_data = excel_data.drop(excel_data.index[:3])
    excel_data.columns = line
    excel_data['user_name'] = excel_data['user_name'].apply(lambda x: name_abbreviation(x))
    import_users(set(excel_data['user_name']))
    transform_data(excel_data)
    # gc.collect()


def transform_data(excel_data):
    excel_data = excel_data.transpose()
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM schedule")
    for date, row in excel_data.iterrows():
        for i, val in row.items():
            if val in {'у', 'в', 'н'}:
                user_id = int(username_to_index(excel_data[i].iloc[0]))
                cursor.execute('INSERT INTO schedule (date, user_id, duty) VALUES (?, ?, ?)', 
                                (date.isoformat(), user_id, val))
    conn.commit()     
    conn.close()
    del excel_data
    # del excel_data_t
    gc.collect()



def username_to_index(username): 
    conn = sqlite3.connect('schedule.db') 
    res = pd.read_sql_query(f'SELECT id FROM users WHERE username = "{username}"', conn)     
    conn.close() 
    if not res.empty:
        return res['id'].iloc[0]
    return 0



def import_users(person_df):
    conn = sqlite3.connect('schedule.db')
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users")
    all_users = set(row[0] for row in cursor.fetchall())
    users_to_delete = all_users - person_df
    for user in users_to_delete:
        cursor.execute("DELETE FROM users WHERE username = ?", (user,))
    for name in person_df:
        cursor.execute('SELECT * FROM users WHERE username = ?', (name,))
        existing_user = cursor.fetchone()
        if not existing_user:
            cursor.execute('INSERT INTO users (username) VALUES (?)', (name,))
    conn.commit()
    # res = pd.read_sql_query("SELECT * FROM users", conn)
    # print(res)
    conn.close()
    # gc.collect()



def download_excel():
    try:
        import_database()
        gc.collect()
        return True
    except Exception as e:
        # print(f"Ошибка при загрузке Excel-файла: {e}")
        gc.collect()
        return False
