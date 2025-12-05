import sqlite3
import os
import logging
import pandas as pd

# Настройка логирования
logger = logging.getLogger('db_manager')

# Определение пути к базе данных
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DATABASE_PATH = os.path.join(DATA_DIR, 'kvk_data.db')


def create_tables():
    """
    Создает таблицы базы данных, если они не существуют.
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Таблица для статистики игроков (Результаты периода)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kvk_stats (
                player_id INTEGER,
                player_name TEXT NOT NULL,
                power INTEGER,
                kill_points INTEGER,
                deaths INTEGER,
                t1_kills INTEGER,
                t2_kills INTEGER,
                t3_kills INTEGER,
                t4_kills INTEGER,
                t5_kills INTEGER,
                kvk_name TEXT NOT NULL,
                period_key TEXT NOT NULL,
                PRIMARY KEY (player_id, kvk_name, period_key)
            )
        ''')

        # Таблица для сырых снимков (Start/End)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kvk_snapshots (
                player_id INTEGER,
                player_name TEXT NOT NULL,
                power INTEGER,
                kill_points INTEGER,
                deaths INTEGER,
                t1_kills INTEGER,
                t2_kills INTEGER,
                t3_kills INTEGER,
                t4_kills INTEGER,
                t5_kills INTEGER,
                kvk_name TEXT NOT NULL,
                period_key TEXT NOT NULL,
                snapshot_type TEXT NOT NULL, -- 'start' or 'end'
                PRIMARY KEY (player_id, kvk_name, period_key, snapshot_type)
            )
        ''')

        # Таблица требований
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kvk_requirements (
                kvk_name TEXT NOT NULL,
                min_power INTEGER,
                max_power INTEGER,
                required_kill_points INTEGER,
                required_deaths INTEGER,
                PRIMARY KEY (kvk_name, min_power)
            )
        ''')

        # Таблица для связи Discord ID с игровыми ID
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS linked_accounts (
                discord_id INTEGER,
                player_id INTEGER,
                is_main_account INTEGER DEFAULT 0,
                PRIMARY KEY (discord_id, player_id)
            )
        ''')

        # Таблица для хранения настроек KVK
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kvk_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
        ''')

        conn.commit()
        logger.info("Таблицы базы данных успешно созданы или проверены.")
    except sqlite3.Error as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
    finally:
        if conn:
            conn.close()


def import_snapshot(file_path: str, kvk_name: str, period_key: str, snapshot_type: str):
    """
    Импортирует снимок (Start/End) из Excel в таблицу kvk_snapshots.
    """
    conn = None
    try:
        df = pd.read_excel(file_path)
        required_cols = [
            'Governor ID', 'Governor Name', 'Power', 'Kill Points', 'Deads',
            'Tier 1 Kills', 'Tier 2 Kills', 'Tier 3 Kills', 'Tier 4 Kills', 'Tier 5 Kills'
        ]
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Файл Excel не содержит все необходимые столбцы: {required_cols}")
            return False

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Очистка старого снимка того же типа для этого периода, если нужно перезаписать
        cursor.execute("DELETE FROM kvk_snapshots WHERE kvk_name = ? AND period_key = ? AND snapshot_type = ?",
                       (kvk_name, period_key, snapshot_type))

        for index, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT INTO kvk_snapshots (
                        player_id, player_name, power, kill_points, deaths,
                        t1_kills, t2_kills, t3_kills, t4_kills, t5_kills,
                        kvk_name, period_key, snapshot_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    int(row['Governor ID']), str(row['Governor Name']), int(row['Power']),
                    int(row['Kill Points']), int(row['Deads']), int(row['Tier 1 Kills']),
                    int(row['Tier 2 Kills']), int(row['Tier 3 Kills']), int(row['Tier 4 Kills']),
                    int(row['Tier 5 Kills']), kvk_name, period_key, snapshot_type
                ))
            except (ValueError, KeyError) as e:
                logger.error(f"Ошибка при обработке строки {index + 2}: {e}")
                continue

        conn.commit()
        logger.info(f"Снимок '{snapshot_type}' для '{kvk_name}' - '{period_key}' успешно импортирован.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при импорте снимка: {e}")
        return False
    finally:
        if conn:
            conn.close()


def import_requirements(file_path: str, kvk_name: str):
    """
    Импортирует требования к KVK из Excel.
    Ожидаемые столбцы: Min Power, Max Power, Required KP, Required Deaths
    """
    conn = None
    try:
        df = pd.read_excel(file_path)
        # Нормализация имен колонок (удаление пробелов, нижний регистр) для гибкости
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Маппинг ожидаемых колонок
        col_map = {
            'min power': 'min_power',
            'max power': 'max_power',
            'required kp': 'required_kill_points',
            'required deaths': 'required_deaths'
        }
        
        # Проверка наличия колонок
        if not all(k in df.columns for k in col_map.keys()):
             # Попробуем альтернативные названия или вернем ошибку
             # Для простоты требуем точного совпадения (в нижнем регистре)
             logger.error(f"Файл требований должен содержать столбцы: {list(col_map.keys())}")
             return False

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Очистка старых требований для этого KVK
        cursor.execute("DELETE FROM kvk_requirements WHERE kvk_name = ?", (kvk_name,))

        for index, row in df.iterrows():
            try:
                cursor.execute('''
                    INSERT INTO kvk_requirements (
                        kvk_name, min_power, max_power, required_kill_points, required_deaths
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    kvk_name, int(row['min power']), int(row['max power']),
                    int(row['required kp']), int(row['required deaths'])
                ))
            except Exception as e:
                logger.error(f"Ошибка строки {index + 2} требований: {e}")
                continue

        conn.commit()
        logger.info(f"Требования для '{kvk_name}' успешно импортированы.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при импорте требований: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_snapshot_data(kvk_name: str, period_key: str, snapshot_type: str):
    """Получает данные снимка как словарь {player_id: row}."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM kvk_snapshots WHERE kvk_name = ? AND period_key = ? AND snapshot_type = ?",
                       (kvk_name, period_key, snapshot_type))
        rows = cursor.fetchall()
        return {row['player_id']: row for row in rows}
    except Exception as e:
        logger.error(f"Ошибка получения снимка: {e}")
        return {}
    finally:
        if conn: conn.close()


def save_period_results(results: list):
    """Сохраняет рассчитанные результаты периода."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        for res in results:
            cursor.execute('''
                INSERT OR REPLACE INTO kvk_stats (
                    player_id, player_name, power, kill_points, deaths,
                    t1_kills, t2_kills, t3_kills, t4_kills, t5_kills,
                    kvk_name, period_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                res['player_id'], res['player_name'], res['power'],
                res['kill_points'], res['deaths'], res['t1_kills'],
                res['t2_kills'], res['t3_kills'], res['t4_kills'],
                res['t5_kills'], res['kvk_name'], res['period_key']
            ))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения результатов: {e}")
        return False
    finally:
        if conn: conn.close()


def get_requirements(kvk_name: str, power: int):
    """Возвращает требования для заданного KVK и мощности игрока."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ищем диапазон, в который попадает power
        cursor.execute('''
            SELECT * FROM kvk_requirements 
            WHERE kvk_name = ? AND ? >= min_power AND ? <= max_power
        ''', (kvk_name, power, power))
        
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка получения требований: {e}")
        return None
    finally:
        if conn: conn.close()


def get_all_requirements(kvk_name: str):
    """Возвращает все требования для заданного KVK, отсортированные по убыванию силы."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM kvk_requirements 
            WHERE kvk_name = ?
            ORDER BY min_power DESC
        ''', (kvk_name,))
        
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка получения списка требований: {e}")
        return []
    finally:
        if conn: conn.close()


def save_requirements_batch(kvk_name: str, requirements: list):
    """
    Сохраняет список требований для KVK.
    requirements: list of dicts {'min_power', 'max_power', 'required_kill_points', 'required_deaths'}
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Очистка старых требований
        cursor.execute("DELETE FROM kvk_requirements WHERE kvk_name = ?", (kvk_name,))

        for req in requirements:
            cursor.execute('''
                INSERT INTO kvk_requirements (
                    kvk_name, min_power, max_power, required_kill_points, required_deaths
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                kvk_name, req['min_power'], req['max_power'],
                req['required_kill_points'], req['required_deaths']
            ))

        conn.commit()
        logger.info(f"Сохранено {len(requirements)} требований для '{kvk_name}'.")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения требований: {e}")
        return False
    finally:
        if conn: conn.close()


def archive_kvk_data(current_name: str, archive_name: str):
    """
    Архивирует данные KVK, переименовывая их в таблицах статистики и снимков.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Обновляем kvk_stats
        cursor.execute("UPDATE kvk_stats SET kvk_name = ? WHERE kvk_name = ?", (archive_name, current_name))
        
        # Обновляем kvk_snapshots
        cursor.execute("UPDATE kvk_snapshots SET kvk_name = ? WHERE kvk_name = ?", (archive_name, current_name))

        # Требования оставляем как шаблон (не переименовываем), чтобы можно было использовать снова.
        # Или можно скопировать их для архива?
        # Пользователь просил "архив данных". Требования - это настройки.
        # Давайте скопируем требования в архивное имя, чтобы знать, какие они были ТОГДА.
        
        # 1. Получаем текущие требования
        cursor.execute("SELECT * FROM kvk_requirements WHERE kvk_name = ?", (current_name,))
        reqs = cursor.fetchall()
        
        # 2. Вставляем их под новым именем
        for req in reqs:
            cursor.execute('''
                INSERT INTO kvk_requirements (kvk_name, min_power, max_power, required_kill_points, required_deaths)
                VALUES (?, ?, ?, ?, ?)
            ''', (archive_name, req[1], req[2], req[3], req[4])) # Индексы зависят от порядка колонок в SELECT *

        conn.commit()
        logger.info(f"Данные KVK '{current_name}' успешно архивированы в '{archive_name}'.")
        return True
    except Exception as e:
        logger.error(f"Ошибка архивации данных: {e}")
        return False
    finally:
        if conn: conn.close()


def link_account(discord_id: int, player_id: int, is_main: bool = False):
    """
    Привязывает игровой аккаунт к Discord аккаунту.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        if is_main:
            cursor.execute("UPDATE linked_accounts SET is_main_account = 0 WHERE discord_id = ?", (discord_id,))

        cursor.execute('''
            INSERT OR REPLACE INTO linked_accounts (discord_id, player_id, is_main_account)
            VALUES (?, ?, ?)
        ''', (discord_id, player_id, int(is_main)))

        conn.commit()
        logger.info(f"Аккаунт {player_id} успешно привязан к Discord ID {discord_id}.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при привязке аккаунта: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_linked_accounts(discord_id: int):
    """
    Возвращает список всех привязанных игровых аккаунтов для Discord ID.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT player_id, is_main_account FROM linked_accounts WHERE discord_id = ?", (discord_id,))
        rows = cursor.fetchall()

        accounts = [{'player_id': row[0], 'is_main': bool(row[1])} for row in rows]
        return accounts
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении привязанных аккаунтов: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_current_kvk_name():
    """
    Возвращает текущее название KVK из базы данных.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT setting_value FROM kvk_settings WHERE setting_key = 'current_kvk_name'")
        result = cursor.fetchone()

        return result[0] if result else None
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении текущего KVK: {e}")
        return None
    finally:
        if conn:
            conn.close()


def set_current_kvk_name(kvk_name: str):
    """
    Устанавливает текущее название KVK в базе данных.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO kvk_settings (setting_key, setting_value)
            VALUES ('current_kvk_name', ?)
        ''', (kvk_name,))

        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Ошибка при установке текущего KVK: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_player_stats(player_id: int, kvk_name: str, period_key: str):
    """
    Получает статистику игрока по его ID для конкретного KVK и периода.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM kvk_stats
            WHERE player_id = ? AND kvk_name = ? AND period_key = ?
        ''', (player_id, kvk_name, period_key))

        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении статистики игрока: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_total_player_stats(player_id: int, kvk_name: str):
    """
    Получает суммарную статистику игрока для всех периодов в рамках KVK.
    """
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT MAX(power) as total_power,
                   SUM(kill_points) as total_kill_points,
                   SUM(deaths) as total_deaths,
                   SUM(t1_kills) as total_t1_kills,
                   SUM(t2_kills) as total_t2_kills,
                   SUM(t3_kills) as total_t3_kills,
                   SUM(t4_kills) as total_t4_kills,
                   SUM(t5_kills) as total_t5_kills,
                   player_name
            FROM kvk_stats
            WHERE player_id = ? AND kvk_name = ?
            GROUP BY player_id
        ''', (player_id, kvk_name))

        return cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при получении суммарной статистики игрока: {e}")
        return None
    finally:
        if conn:
            conn.close()
