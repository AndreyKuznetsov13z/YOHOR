import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import secrets

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection(db_name='software_shop.db'):
    """Подключение к базе данных"""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_name='software_shop.db'):
    """Инициализация всех таблиц базы данных"""
    conn = get_db_connection(db_name)
    cursor = conn.cursor()

    try:
        # Таблица пользователей
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            role TEXT DEFAULT 'user' CHECK(role IN ('user', 'moder', 'admin', 'seller')),
            is_active BOOLEAN DEFAULT 1
        )
        ''')

        # Таблица категорий
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

            # Заявки на регистрацию продавцов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'in_review', 'approved', 'rejected')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # Таблица товаров/услуг
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS software (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL CHECK(price >= 0),
            category_id INTEGER NOT NULL,
            developer TEXT NOT NULL,
            downloads INTEGER DEFAULT 0,
            rating_avg REAL DEFAULT 0.0 CHECK(rating_avg >= 0 AND rating_avg <= 5),
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
        )
        ''')

        # Таблица квартир
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            builder TEXT,
            price REAL NOT NULL CHECK(price >= 0),
            category_room_id INTEGER NOT NULL,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_room_id) REFERENCES categories_room(id) ON DELETE RESTRICT
        )
        ''')


        # Таблица корзины (активная корзина пользователя)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            total_price REAL NOT NULL DEFAULT 0 CHECK(total_price >= 0),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        ''')

        # Таблица товаров в корзине
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cart_id INTEGER NOT NULL,
            software_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
            price_at_add REAL NOT NULL CHECK(price_at_add >= 0),
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cart_id) REFERENCES cart(id) ON DELETE CASCADE,
            FOREIGN KEY (software_id) REFERENCES software(id) ON DELETE RESTRICT,
            UNIQUE(cart_id, software_id)
        )
        ''')

        # Таблица обращений в службу поддержки
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Таблица истории покупок (завершённые заказы)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_price REAL NOT NULL CHECK(total_price >= 0),
            payment_method TEXT,
            status TEXT DEFAULT 'completed' CHECK(status IN ('completed', 'refunded')),
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        ''')

        # Таблица товаров в покупке (копия Cart_Items из момента покупки)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER NOT NULL,
            software_id INTEGER NOT NULL,
            software_name TEXT NOT NULL,
            developer TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            price_at_purchase REAL NOT NULL CHECK(price_at_purchase >= 0),
            FOREIGN KEY (purchase_id) REFERENCES purchase_history(id) ON DELETE CASCADE,
            FOREIGN KEY (software_id) REFERENCES software(id) ON DELETE RESTRICT
        )
        ''')

        # Таблица отзывов
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            software_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (software_id) REFERENCES software(id) ON DELETE CASCADE,
            UNIQUE(user_id, software_id)
        )
        ''')
        # Таблица для категорий комнат
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories_room (
            id INTEGER PRIMARY KEY AUTOINCREMENT,    
            name VARCHAR(100) NOT NULL UNIQUE,    
            description TEXT,    
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        logger.info('Database initialized successfully')
    except Exception as e:
        logger.error(f'Database initialization failed: {e}')
        conn.rollback()
        raise
    finally:
        conn.close()


# ======================== USERS (ПОЛЬЗОВАТЕЛИ) ========================

def add_user(email: str, password: str, name: str, phone: str = None, role: str = 'user', db_name='software_shop.db') -> int:
    """Добавление нового пользователя"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (email, password, name, phone, role) VALUES (?, ?, ?, ?, ?)',
            (email, password, name, phone, role)
        )
        
        # Автоматически создаём корзину для нового пользователя
        user_id = cursor.lastrowid
        cursor.execute(
            'INSERT INTO cart (user_id, total_price) VALUES (?, ?)',
            (user_id, 0)
        )
        
        conn.commit()
        logger.info(f'User added: {email} with ID: {user_id}')
        return user_id
    except sqlite3.IntegrityError as e:
        logger.error(f'Failed to add user {email}: {e}')
        raise
    finally:
        conn.close()


def get_user_by_email(email: str, db_name='software_shop.db') -> Optional[sqlite3.Row]:
    """Получить пользователя по email"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        user = cursor.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        return user
    finally:
        conn.close()

def get_user_by_id(user_id: int, db_name='software_shop.db') -> Optional[sqlite3.Row]:
    """Получить пользователя по ID"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        user = cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        return user
    finally:
        conn.close()


def get_all_users(db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить всех пользователей"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        users = cursor.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
        return users
    finally:
        conn.close()

def add_support_ticket(name, email, subject, message, user_id=None, db_name="software_shop.db"):
    conn = get_db_connection(db_name)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO support_tickets (user_id, name, email, subject, message)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, name, email, subject, message))

    conn.commit()
    conn.close()


def get_tickets_by_status(status: str | None = None, db_name="software_shop.db") -> list[sqlite3.Row]:
    conn = get_db_connection(db_name)
    try:
        cur = conn.cursor()
        if status:
            rows = cur.execute(
                """
                SELECT * FROM support_tickets
                WHERE status = ?
                ORDER BY created_at DESC
                """,
                (status,),
            ).fetchall()
        else:
            rows = cur.execute(
                """
                SELECT * FROM support_tickets
                ORDER BY created_at DESC
                """
            ).fetchall()
        return rows
    finally:
        conn.close()


def update_ticket_status(ticket_id: int, status: str, db_name="software_shop.db"):
    """Изменить статус тикета: new / in_progress / closed"""
    if status not in ("new", "in_progress", "closed"):
        raise ValueError("Invalid ticket status")

    conn = get_db_connection(db_name)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE support_tickets SET status = ? WHERE id = ?",
            (status, ticket_id),
        )
        conn.commit()
    finally:
        conn.close()


def count_active_tickets(db_name="software_shop.db") -> int:
    """Количество активных тикетов (new + in_progress)"""
    conn = get_db_connection(db_name)
    try:
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM support_tickets
            WHERE status IN ('new', 'in_progress')
            """
        ).fetchone()
        return row["cnt"]
    finally:
        conn.close()



def update_user(user_id: int, name: str = None, phone: str = None, role: str = None, db_name='software_shop.db'):
    """Обновить данные пользователя"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        updates = []
        params = []
        
        if name is not None:
            updates.append('name = ?')
            params.append(name)
        if phone is not None:
            updates.append('phone = ?')
            params.append(phone)
        if role is not None:
            updates.append('role = ?')
            params.append(role)
        
        if updates:
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            logger.info(f'User {user_id} updated')
    finally:
        conn.close()


def delete_user(user_id: int, db_name='software_shop.db'):
    """Удалить пользователя"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        logger.info(f'User {user_id} deleted')
    finally:
        conn.close()

def update_user_profile(user_id, name, email, phone=None, db_name="software_shop.db"):
    """
    Обновляет данные пользователя в таблице users.

    :param user_id: ID пользователя (int)
    :param name: новое имя (str)
    :param email: новый email (str)
    :param phone: новый телефон (str или None)
    :param db_name: имя файла БД
    """
    conn = get_db_connection(db_name)
    cur = conn.cursor()

    sql = """
        UPDATE users
        SET name = ?, email = ?, phone = ?
        WHERE id = ?
    """
    cur.execute(sql, (name, email, phone, user_id))
    conn.commit()
    conn.close()


# ======================== CATEGORIES (КАТЕГОРИИ ТОВАРОВ) ========================

def add_category(name: str, description: str = None, db_name='software_shop.db') -> int:
    """Добавить новую категорию"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO categories (name, description) VALUES (?, ?)',
            (name, description)
        )
        conn.commit()
        category_id = cursor.lastrowid
        logger.info(f'Category added: {name} with ID: {category_id}')
        return category_id
    except sqlite3.IntegrityError as e:
        logger.error(f'Failed to add category {name}: {e}')
        raise
    finally:
        conn.close()


def get_all_categories(db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить все категории"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        categories = cursor.execute('SELECT * FROM categories ORDER BY name').fetchall()
        return categories
    finally:
        conn.close()


def get_category_by_id(category_id: int, db_name='software_shop.db') -> Optional[sqlite3.Row]:
    """Получить категорию по ID"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        category = cursor.execute('SELECT * FROM categories WHERE id = ?', (category_id,)).fetchone()
        return category
    finally:
        conn.close()


def update_category(category_id: int, name: str = None, description: str = None, db_name='software_shop.db'):
    """Обновить категорию"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        updates = []
        params = []
        
        if name is not None:
            updates.append('name = ?')
            params.append(name)
        if description is not None:
            updates.append('description = ?')
            params.append(description)
        
        if updates:
            params.append(category_id)
            query = f"UPDATE categories SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            logger.info(f'Category {category_id} updated')
    finally:
        conn.close()


def delete_category(category_id: int, db_name='software_shop.db'):
    """Удалить категорию"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM categories WHERE id = ?', (category_id,))
        conn.commit()
        logger.info(f'Category {category_id} deleted')
    except sqlite3.IntegrityError as e:
        logger.error(f'Cannot delete category {category_id}: {e}')
        raise
    finally:
        conn.close()
        


# ======================== SOFTWARE (ТОВАРЫ И УСЛУГИ) ========================

def add_software(name: str, description: str, price: float, category_id: int, developer: str, 
                 image_url: str = None, db_name='software_shop.db') -> int:
    """Добавить новый товар/услугу"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO software (name, description, price, category_id, developer, image_url)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (name, description, price, category_id, developer, image_url)
        )
        conn.commit()
        software_id = cursor.lastrowid
        logger.info(f'Software added: {name} with ID: {software_id}')
        return software_id
    finally:
        conn.close()


def get_all_software(db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить все товары/услуги"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        software = cursor.execute('''
            SELECT s.*, c.name as category_name 
            FROM software s 
            LEFT JOIN categories c ON s.category_id = c.id 
            ORDER BY s.created_at DESC
        ''').fetchall()
        return software
    finally:
        conn.close()

def get_all_rooms(db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить все квартиры"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        rooms = cursor.execute('''
            SELECT s.*, c.name as category_name 
            FROM rooms s 
            LEFT JOIN categories_room c ON s.category_room_id = c.id 
            ORDER BY s.created_at DESC
        ''').fetchall()
        return rooms
    finally:
        conn.close()


def get_software_by_id(software_id: int, db_name='software_shop.db') -> Optional[sqlite3.Row]:
    """Получить товар/услугу по ID"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        software = cursor.execute('''
            SELECT s.*, c.name as category_name 
            FROM software s 
            LEFT JOIN categories c ON s.category_id = c.id 
            WHERE s.id = ?
        ''', (software_id,)).fetchone()
        return software
    finally:
        conn.close()


def get_software_by_category(category_id: int, db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить все товары\услуги в категории"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        software = cursor.execute('''
            SELECT * FROM software WHERE category_id = ? ORDER BY rating_avg DESC
        ''', (category_id,)).fetchall()
        return software
    finally:
        conn.close()


def update_software(software_id: int, name: str = None, description: str = None, price: float = None,
                    category_id: int = None, developer: str = None, image_url: str = None, 
                    db_name='software_shop.db'):
    """Обновить ПО"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        updates = []
        params = []
        
        if name is not None:
            updates.append('name = ?')
            params.append(name)
        if description is not None:
            updates.append('description = ?')
            params.append(description)
        if price is not None:
            updates.append('price = ?')
            params.append(price)
        if category_id is not None:
            updates.append('category_id = ?')
            params.append(category_id)
        if developer is not None:
            updates.append('developer = ?')
            params.append(developer)
        if image_url is not None:
            updates.append('image_url = ?')
            params.append(image_url)
        
        if updates:
            params.append(software_id)
            query = f"UPDATE software SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            logger.info(f'Software {software_id} updated')
    finally:
        conn.close()


def increment_downloads(software_id: int, db_name='software_shop.db'):
    """Увеличить счетчик загрузок"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cursor.execute('UPDATE software SET downloads = downloads + 1 WHERE id = ?', (software_id,))
        conn.commit()
    finally:
        conn.close()


def delete_software(software_id: int, db_name='software_shop.db'):
    """Удалить Товар/услугу"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM software WHERE id = ?', (software_id,))
        conn.commit()
        logger.info(f'Software {software_id} deleted')
    except sqlite3.IntegrityError as e:
        logger.error(f'Cannot delete software {software_id}: {e}')
        raise
    finally:
        conn.close()


def user_has_purchased_software(user_id: int, software_id: int, db_name="software_shop.db") -> bool:
    """Проверка, покупал ли пользователь данный софт с успешной оплатой"""
    conn = get_db_connection(db_name)
    try:
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT 1
            FROM purchase_items pi
            JOIN purchase_history ph ON ph.id = pi.purchase_id
            WHERE ph.user_id = ?
              AND pi.software_id = ?
              AND ph.status = 'completed'
            LIMIT 1
            """,
            (user_id, software_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def get_user_review_for_software(user_id: int, software_id: int, db_name="software_shop.db"):
    """Получить отзыв пользователя на конкретный софт (если есть)"""
    conn = get_db_connection(db_name)
    try:
        cur = conn.cursor()
        return cur.execute(
            """
            SELECT * FROM reviews
            WHERE user_id = ? AND software_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, software_id),
        ).fetchone()
    finally:
        conn.close()


def add_or_update_review(user_id: int, software_id: int, rating: int, text: str,
                         db_name: str = "software_shop.db"):
    """Создать новый отзыв или обновить существующий от этого пользователя по этому софту."""
    conn = get_db_connection(db_name)
    try:
        cur = conn.cursor()

        # есть ли уже отзыв этого пользователя на этот софт
        existing = cur.execute(
            """
            SELECT id FROM reviews
            WHERE user_id = ? AND software_id = ?
            """,
            (user_id, software_id),
        ).fetchone()

        if existing:
            review_id = existing[0]          # fetchone() -> (id,)
            cur.execute(
                """
                UPDATE reviews
                SET rating = ?, comment = ?
                WHERE id = ?
                """,
                (rating, text, review_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO reviews (user_id, software_id, rating, comment)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, software_id, rating, text),
            )

        # пересчитать средний рейтинг по этому ПО
        avg_row = cur.execute(
            "SELECT AVG(rating) AS avg FROM reviews WHERE software_id = ?",
            (software_id,),
        ).fetchone()
        avg_rating = avg_row[0] or 0.0

        cur.execute(
            "UPDATE software SET rating_avg = ? WHERE id = ?",
            (avg_rating, software_id),
        )

        conn.commit()
    finally:
        conn.close()


def get_reviews_for_software(software_id: int, db_name="software_shop.db"):
    """Список отзывов по софту с именами пользователей"""
    conn = get_db_connection(db_name)
    try:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT r.*, u.name as user_name
            FROM reviews r
            JOIN users u ON u.id = r.user_id
            WHERE r.software_id = ?
            ORDER BY r.created_at DESC
            """,
            (software_id,),
        ).fetchall()
        return rows
    finally:
        conn.close()

def get_recent_reviews(limit: int = 100, db_name: str = "software_shop.db"):
    """Последние отзывы с данными пользователя и софта"""
    conn = get_db_connection(db_name)
    try:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT
                r.*,
                u.name AS user_name,
                u.email AS user_email,
                s.name AS software_name
            FROM reviews r
            JOIN users u ON u.id = r.user_id
            JOIN software s ON s.id = r.software_id
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows
    finally:
        conn.close()

# ======================== CART (КОРЗИНА) ========================

def get_user_cart(user_id: int, db_name='software_shop.db') -> Optional[sqlite3.Row]:
    """Получить корзину пользователя"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cart = cursor.execute('SELECT * FROM cart WHERE user_id = ?', (user_id,)).fetchone()
        return cart
    finally:
        conn.close()


def get_cart_by_id(cart_id: int, db_name='software_shop.db') -> Optional[sqlite3.Row]:
    """Получить корзину по ID"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cart = cursor.execute('SELECT * FROM cart WHERE id = ?', (cart_id,)).fetchone()
        return cart
    finally:
        conn.close()


def add_to_cart(user_id: int, software_id: int, quantity: int = 1, db_name='software_shop.db') -> int:
    """Добавить товар в корзину или обновить количество"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        
        # Получить корзину пользователя
        cart = cursor.execute('SELECT id FROM cart WHERE user_id = ?', (user_id,)).fetchone()
        if not cart:
            raise ValueError(f'Cart not found for user {user_id}')
        
        cart_id = cart['id']
        
        # Получить текущую цену ПО
        software = cursor.execute('SELECT price FROM software WHERE id = ?', (software_id,)).fetchone()
        if not software:
            raise ValueError(f'Software {software_id} not found')
        
        price_at_add = software['price']
        
        # Проверить, есть ли уже этот товар в корзине
        existing_item = cursor.execute(
            'SELECT id, quantity FROM cart_items WHERE cart_id = ? AND software_id = ?',
            (cart_id, software_id)
        ).fetchone()
        
        if existing_item:
            # Обновить количество
            new_quantity = existing_item['quantity'] + quantity
            cursor.execute(
                'UPDATE cart_items SET quantity = ? WHERE id = ?',
                (new_quantity, existing_item['id'])
            )
            item_id = existing_item['id']
        else:
            # Добавить новый товар
            cursor.execute(
                'INSERT INTO cart_items (cart_id, software_id, quantity, price_at_add) VALUES (?, ?, ?, ?)',
                (cart_id, software_id, quantity, price_at_add)
            )
            item_id = cursor.lastrowid
        
        # Обновить total_price корзины
        cursor.execute('''
            UPDATE cart SET total_price = (
                SELECT COALESCE(SUM(quantity * price_at_add), 0) FROM cart_items WHERE cart_id = ?
            ), updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (cart_id, cart_id))
        
        conn.commit()
        logger.info(f'Added to cart (user {user_id}): software {software_id}, quantity {quantity}')
        return item_id
    finally:
        conn.close()


def get_cart_items(user_id: int, db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить все товары в корзине пользователя"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        items = cursor.execute('''
            SELECT ci.*, s.name, s.developer, s.image_url
            FROM cart_items ci 
            JOIN cart c ON ci.cart_id = c.id
            JOIN software s ON ci.software_id = s.id 
            WHERE c.user_id = ?
            ORDER BY ci.added_at DESC
        ''', (user_id,)).fetchall()
        return items
    finally:
        conn.close()


def update_cart_item_quantity(item_id: int, quantity: int, db_name='software_shop.db'):
    """Обновить количество товара в корзине"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        
        if quantity <= 0:
            # Если количество <= 0, удалить товар
            remove_from_cart(item_id, db_name)
            return
        
        # Получить cart_id
        item = cursor.execute('SELECT cart_id FROM cart_items WHERE id = ?', (item_id,)).fetchone()
        cart_id = item['cart_id']
        
        # Обновить количество
        cursor.execute('UPDATE cart_items SET quantity = ? WHERE id = ?', (quantity, item_id))
        
        # Обновить total_price корзины
        cursor.execute('''
            UPDATE cart SET total_price = (
                SELECT COALESCE(SUM(quantity * price_at_add), 0) FROM cart_items WHERE cart_id = ?
            ), updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (cart_id, cart_id))
        
        conn.commit()
        logger.info(f'Cart item {item_id} quantity updated to {quantity}')
    finally:
        conn.close()


def remove_from_cart(item_id: int, db_name='software_shop.db'):
    """Удалить товар из корзины"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        
        # Получить cart_id
        item = cursor.execute('SELECT cart_id FROM cart_items WHERE id = ?', (item_id,)).fetchone()
        if not item:
            raise ValueError(f'Cart item {item_id} not found')
        
        cart_id = item['cart_id']
        
        # Удалить товар
        cursor.execute('DELETE FROM cart_items WHERE id = ?', (item_id,))
        
        # Обновить total_price корзины
        cursor.execute('''
            UPDATE cart SET total_price = (
                SELECT COALESCE(SUM(quantity * price_at_add), 0) FROM cart_items WHERE cart_id = ?
            ), updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (cart_id, cart_id))
        
        conn.commit()
        logger.info(f'Item {item_id} removed from cart')
    finally:
        conn.close()


def clear_cart(user_id: int, db_name='software_shop.db'):
    """Очистить корзину пользователя"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        
        # Получить cart_id
        cart = cursor.execute('SELECT id FROM cart WHERE user_id = ?', (user_id,)).fetchone()
        if not cart:
            raise ValueError(f'Cart not found for user {user_id}')
        
        cart_id = cart['id']
        
        # Удалить все товары
        cursor.execute('DELETE FROM cart_items WHERE cart_id = ?', (cart_id,))
        
        # Обновить корзину
        cursor.execute('UPDATE cart SET total_price = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (cart_id,))
        
        conn.commit()
        logger.info(f'Cart cleared for user {user_id}')
    finally:
        conn.close()


# ======================== PURCHASE_HISTORY (ИСТОРИЯ ПОКУПОК) ========================

def create_purchase(user_id: int, payment_method: str = None, db_name='software_shop.db') -> int:
    """Создать покупку из корзины пользователя"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        
        # Получить корзину
        cart = cursor.execute('''
            SELECT c.id, c.total_price FROM cart c WHERE c.user_id = ?
        ''', (user_id,)).fetchone()
        
        if not cart:
            raise ValueError(f'Cart not found for user {user_id}')
        
        if cart['total_price'] == 0:
            raise ValueError(f'Cart is empty for user {user_id}')
        
        cart_id = cart['id']
        total_price = cart['total_price']
        
        # Создать запись в purchase_history
        cursor.execute(
            '''INSERT INTO purchase_history (user_id, total_price, payment_method)
               VALUES (?, ?, ?)''',
            (user_id, total_price, payment_method)
        )
        
        purchase_id = cursor.lastrowid
        
        # Копировать товары из cart_items в purchase_items
        cart_items = cursor.execute('''
            SELECT ci.software_id, ci.quantity, ci.price_at_add,
                   s.name, s.developer
            FROM cart_items ci
            JOIN software s ON ci.software_id = s.id
            WHERE ci.cart_id = ?
        ''', (cart_id,)).fetchall()
        
        for item in cart_items:
            cursor.execute(
                '''INSERT INTO purchase_items 
                   (purchase_id, software_id, software_name, developer, quantity, price_at_purchase)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (purchase_id, item['software_id'], item['name'], item['developer'], 
                 item['quantity'], item['price_at_add'])
            )
            
            # Увеличить счётчик загрузок
            cursor.execute(
                'UPDATE software SET downloads = downloads + ? WHERE id = ?',
                (item['quantity'], item['software_id'])
            )
        
        # Очистить корзину
        cursor.execute('DELETE FROM cart_items WHERE cart_id = ?', (cart_id,))
        cursor.execute(
            'UPDATE cart SET total_price = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (cart_id,)
        )
        
        conn.commit()
        logger.info(f'Purchase created: {purchase_id} for user {user_id}, total: {total_price}')
        return purchase_id
    finally:
        conn.close()


def get_user_purchases(user_id: int, db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить историю покупок пользователя"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        purchases = cursor.execute('''
            SELECT * FROM purchase_history WHERE user_id = ? ORDER BY purchased_at DESC
        ''', (user_id,)).fetchall()
        return purchases
    finally:
        conn.close()


def get_purchase_by_id(purchase_id: int, db_name='software_shop.db') -> Optional[sqlite3.Row]:
    """Получить покупку по ID"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        purchase = cursor.execute(
            'SELECT * FROM purchase_history WHERE id = ?',
            (purchase_id,)
        ).fetchone()
        return purchase
    finally:
        conn.close()


def get_purchase_items(purchase_id: int, db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить все товары в покупке"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        items = cursor.execute('''
            SELECT * FROM purchase_items WHERE purchase_id = ?
        ''', (purchase_id,)).fetchall()
        return items
    finally:
        conn.close()

def get_purchases_with_items(user_id: int, limit: int | None = None, db_name: str = "software_shop.db") -> list[sqlite3.Row]:
    """
    Возвращает список покупок пользователя, где у каждой покупки есть поле items
    (список словарей с товарами).
    """
    conn = get_db_connection(db_name)
    try:
        cur = conn.cursor()

        # сами покупки
        sql = """
        SELECT * FROM purchase_history
        WHERE user_id = ?
        ORDER BY purchased_at DESC
        """
        params: list = [user_id]
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        purchases = cur.execute(sql, params).fetchall()

        if not purchases:
            return []

        purchase_ids = [p["id"] for p in purchases]

        # все товары по этим покупкам
        q_marks = ",".join("?" for _ in purchase_ids)
        items_rows = cur.execute(
            f"""
            SELECT
                pi.*,
                s.name AS software_name
            FROM purchase_items pi
            JOIN software s ON s.id = pi.software_id
            WHERE pi.purchase_id IN ({q_marks})
            ORDER BY pi.id
            """,
            purchase_ids,
        ).fetchall()

        # группируем товары по purchase_id
        items_by_purchase: dict[int, list[dict]] = {}
        for row in items_rows:
            items_by_purchase.setdefault(row["purchase_id"], []).append(
                {
                    "id": row["id"],
                    "software_id": row["software_id"],
                    "name": row["software_name"],
                    "quantity": row["quantity"],
                    "price": row["price_at_purchase"],
                }
            )

        # превращаем Row в dict + добавляем items
        result: list[dict] = []
        for p in purchases:
            p_dict = dict(p)
            p_dict["items"] = items_by_purchase.get(p["id"], [])
            result.append(p_dict)

        return result
    finally:
        conn.close()



def get_all_purchases(db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить все покупки (для админов)"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        purchases = cursor.execute('''
            SELECT ph.*, u.name as user_name, u.email
            FROM purchase_history ph
            JOIN users u ON ph.user_id = u.id
            ORDER BY ph.purchased_at DESC
        ''').fetchall()
        return purchases
    finally:
        conn.close()


# ======================== REVIEWS (ОТЗЫВЫ) ========================

def add_review(user_id: int, software_id: int, rating: int, comment: str = None, db_name='software_shop.db') -> int:
    """Добавить отзыв"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        
        # Добавить отзыв
        cursor.execute(
            'INSERT INTO reviews (user_id, software_id, rating, comment) VALUES (?, ?, ?, ?)',
            (user_id, software_id, rating, comment)
        )
        
        # Обновить средний рейтинг ПО
        avg_rating = cursor.execute(
            'SELECT AVG(rating) as avg FROM reviews WHERE software_id = ?',
            (software_id,)
        ).fetchone()['avg']

        cursor.execute(
            'UPDATE software SET rating_avg = ? WHERE id = ?',
            (avg_rating, software_id)
        )

        
        conn.commit()
        review_id = cursor.lastrowid
        logger.info(f'Review added: user {user_id} rated software {software_id} with {rating} stars')
        return review_id
    except sqlite3.IntegrityError as e:
        logger.error(f'Review already exists for user {user_id} and software {software_id}')
        raise
    finally:
        conn.close()


def get_reviews_for_software(software_id: int, db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить все отзывы ПО"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        reviews = cursor.execute('''
            SELECT r.*, u.name, u.email 
            FROM reviews r 
            JOIN users u ON r.user_id = u.id 
            WHERE r.software_id = ? 
            ORDER BY r.created_at DESC
        ''', (software_id,)).fetchall()
        return reviews
    finally:
        conn.close()


def get_user_review(user_id: int, software_id: int, db_name='software_shop.db') -> Optional[sqlite3.Row]:
    """Получить отзыв пользователя для ПО"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        review = cursor.execute(
            'SELECT * FROM reviews WHERE user_id = ? AND software_id = ?',
            (user_id, software_id)
        ).fetchone()
        return review
    finally:
        conn.close()


def update_review(review_id: int, rating: int = None, comment: str = None, db_name='software_shop.db'):
    """Обновить отзыв"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        updates = []
        params = []
        
        if rating is not None:
            updates.append('rating = ?')
            params.append(rating)
        if comment is not None:
            updates.append('comment = ?')
            params.append(comment)
        
        if updates:
            params.append(review_id)
            query = f"UPDATE reviews SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            
            # Обновить средний рейтинг
            review = cursor.execute('SELECT software_id FROM reviews WHERE id = ?', (review_id,)).fetchone()
            software_id = review['software_id']
            
            avg_rating = cursor.execute(
                'SELECT AVG(rating) as avg FROM reviews WHERE software_id = ?',
                (software_id,)
            ).fetchone()['avg']
            
            cursor.execute('UPDATE software SET rating_avg = ? WHERE id = ?', (avg_rating, software_id))
            
            conn.commit()
            logger.info(f'Review {review_id} updated')
    finally:
        conn.close()


def delete_review(review_id: int, db_name='software_shop.db'):
    """Удалить отзыв"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        
        review = cursor.execute('SELECT software_id FROM reviews WHERE id = ?', (review_id,)).fetchone()
        software_id = review['software_id']
        
        cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
        
        # Обновить средний рейтинг
        avg_rating = cursor.execute(
            'SELECT AVG(rating) as avg FROM reviews WHERE software_id = ?',
            (software_id,)
        ).fetchone()['avg'] or 0.0
        
        cursor.execute('UPDATE software SET rating_avg = ? WHERE id = ?', (avg_rating, software_id))
        
        conn.commit()
        logger.info(f'Review {review_id} deleted')
    finally:
        conn.close()


# Админ панель

def search_users(
    query: str | None = None,
    sort: str | None = None,
    direction: str = "desc",
    db_name: str = "software_shop.db",
) -> list[sqlite3.Row]:
    """
    Получить пользователей с суммой покупок.
    sort: one of id, name, email, role, is_active, created_at, total_spent
    direction: asc / desc
    """
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()

        # базовый запрос + суммарные траты пользователя
        sql = """
        SELECT
            u.*,
            COALESCE(SUM(ph.total_price), 0) AS total_spent
        FROM users u
        LEFT JOIN purchase_history ph ON ph.user_id = u.id
        """
        params: list = []

        if query:
            like = f"%{query}%"
            sql += " WHERE u.name LIKE ? OR u.email LIKE ?"
            params.extend([like, like])

        sql += " GROUP BY u.id"

        allowed_sort = {
            "id": "u.id",
            "name": "u.name",
            "email": "u.email",
            "role": "u.role",
            "is_active": "u.is_active",
            "created_at": "u.created_at",
            "total_spent": "total_spent",
        }
        col = allowed_sort.get(sort or "created_at", "u.created_at")
        dir_sql = "ASC" if direction == "asc" else "DESC"
        sql += f" ORDER BY {col} {dir_sql}"

        return cursor.execute(sql, params).fetchall()
    finally:
        conn.close()



def set_user_role(user_id: int, role: str, db_name='software_shop.db'):
    """Сменить роль пользователя (user / moder / admin)"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET role = ? WHERE id = ?',
            (role, user_id)
        )
        conn.commit()
    finally:
        conn.close()


def set_user_active(user_id: int, is_active: bool, db_name='software_shop.db'):
    """Заблокировать или разблокировать пользователя"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE users SET is_active = ? WHERE id = ?',
            (1 if is_active else 0, user_id)
        )
        conn.commit()
    finally:
        conn.close()



# ======================== UTILITY FUNCTIONS (ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ) ========================

def get_bestsellers(limit: int = 10, db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить бестселлеры (самые скачиваемые)"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        software = cursor.execute('''
            SELECT * FROM software ORDER BY downloads DESC LIMIT ?
        ''', (limit,)).fetchall()
        return software
    finally:
        conn.close()


def get_top_rated(limit: int = 10, db_name='software_shop.db') -> List[sqlite3.Row]:
    """Получить топ по рейтингу"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        software = cursor.execute('''
            SELECT * FROM software WHERE rating_avg > 0 ORDER BY rating_avg DESC LIMIT ?
        ''', (limit,)).fetchall()
        return software
    finally:
        conn.close()


def search_software(query: str, db_name='software_shop.db') -> List[sqlite3.Row]:
    """Поиск ПО по названию или описанию"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        search_query = f'%{query}%'
        software = cursor.execute('''
            SELECT * FROM software 
            WHERE name LIKE ? OR description LIKE ? OR developer LIKE ?
            ORDER BY downloads DESC
        ''', (search_query, search_query, search_query)).fetchall()
        return software
    finally:
        conn.close()


def get_sales_statistics(db_name='software_shop.db') -> Dict:
    """Получить статистику продаж"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()
        
        stats = {
            'total_purchases': cursor.execute('SELECT COUNT(*) as count FROM purchase_history').fetchone()['count'],
            'total_revenue': cursor.execute('SELECT COALESCE(SUM(total_price), 0) as sum FROM purchase_history').fetchone()['sum'],
            'active_carts': cursor.execute('SELECT COUNT(*) as count FROM cart WHERE total_price > 0').fetchone()['count'],
            'total_users': cursor.execute('SELECT COUNT(*) as count FROM users').fetchone()['count'],
            'total_software': cursor.execute('SELECT COUNT(*) as count FROM software').fetchone()['count'],
        }
        return stats
    finally:
        conn.close()

def add_application(name: str, phone: str, email: str, dbname: str = "software_shop.db") -> int:
    conn = get_db_connection(dbname)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO applications (name, phone, email)
            VALUES (?, ?, ?)
            """,
            (name, phone, email),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def approve_application(application_id: int, dbname: str = "software_shop.db") -> int:
    """Подтверждает заявку и создаёт пользователя с данными из неё"""
    conn = get_db_connection(dbname)
    try:
        cur = conn.cursor()
        
        # Получаем данные заявки
        app = cur.execute(
            "SELECT name, phone, email FROM applications WHERE id = ?",
            (application_id,)
        ).fetchone()
        
        if not app:
            raise ValueError("Заявка не найдена")
        
        name, phone, email = app
        
        # Проверяем, нет ли уже такого пользователя
        existing = get_user_by_email(email)
        if existing:
            raise ValueError("Пользователь с таким email уже существует")
        
        temp_password = secrets.token_urlsafe(12)  # Временный пароль
       
        userid = add_user(
            email=email,
            password=temp_password, 
            name=name,
            phone=phone,
            role="seller"  # новая роль для продавцов
        )
        
        # Меняем статус заявки
        cur.execute(
            "UPDATE applications SET status = 'approved' WHERE id = ?",
            (application_id,)
        )
        
        conn.commit()
        logger.info(f"Application {application_id} approved, user {userid} created for {email}")
        
        return userid, temp_password  # возвращаем ID и временный пароль
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to approve application {application_id}: {e}")
        raise
    finally:
        conn.close()


def get_applications_by_status(status: str | None = None, dbname: str = "software_shop.db"):
    conn = get_db_connection(dbname)
    try:
        cur = conn.cursor()
        if status:
            cur.execute(
                "SELECT * FROM applications WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        else:
            cur.execute(
                "SELECT * FROM applications ORDER BY created_at DESC"
            )
        return cur.fetchall()
    finally:
        conn.close()


def update_application_status(application_id: int, status: str, dbname: str = "software_shop.db") -> None:
    if status not in ("new", "in_review", "approved", "rejected"):
        raise ValueError("Invalid application status")
    conn = get_db_connection(dbname)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE applications SET status = ? WHERE id = ?",
            (status, application_id),
        )
        conn.commit()
    finally:
        conn.close()


def count_active_applications(dbname: str = "software_shop.db") -> int:
    conn = get_db_connection(dbname)
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT COUNT(*) AS cnt FROM applications WHERE status IN ('new', 'in_review')"
        ).fetchone()
        return row["cnt"]
    finally:
        conn.close()


        
def get_filtered_software(
    q: str = "",
    category_id: int | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    db_name: str = "software_shop.db"
) -> list[sqlite3.Row]:
    """Поиск ПО по названию, описанию, разработчику, категории и ценовому диапазону"""
    conn = get_db_connection(db_name)
    try:
        cursor = conn.cursor()

        sql = """
        SELECT s.*, c.name AS category_name
        FROM software s
        LEFT JOIN categories c ON s.category_id = c.id
        WHERE 1=1
        """
        params: list = []

        # Поиск по строке (название, описание, разработчик, категория)
        if q:
            like = f"%{q}%"
            sql += """
            AND (
                s.name LIKE ?
                OR s.description LIKE ?
                OR s.developer LIKE ?
                OR c.name LIKE ?
            )
            """
            params.extend([like, like, like, like])

        # Фильтр по категории
        if category_id:
            sql += " AND s.category_id = ?"
            params.append(category_id)

        # Фильтр по цене
        if price_min is not None and price_min != "":
            sql += " AND s.price >= ?"
            params.append(float(price_min))
        if price_max is not None and price_max != "":
            sql += " AND s.price <= ?"
            params.append(float(price_max))

        # Сортировка: сначала по загрузкам, потом по рейтингу
        sql += " ORDER BY s.downloads DESC, s.rating_avg DESC, s.name ASC"

        return cursor.execute(sql, params).fetchall()
    finally:
        conn.close()
        

def check_db(db_name='software_shop.db') -> bool:
    """Проверить подключение к базе данных"""
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT sqlite_version();")
        cursor.fetchone()
        conn.close()
        return True
    except Exception as e:
        logger.error(f'Database connection failed: {e}')
        return False

def seed_initial_data(db_name: str = "software_shop.db"):
    """
    Первичное наполнение БД:
    - 4 пользователя (admin, moder, user, seller)
    - категории
    - программное обеспечение
    Функция безопасна при повторном запуске: сначала проверяет наличие записей.
    """
    conn = get_db_connection(db_name)
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM categories_room")
        if cur.fetchone()[0] == 0:
            room_categories = [
                ("1-комнатные", "Однокомнатные квартиры"),
                ("2-комнатные", "Двухкомнатные квартиры"), 
                ("3-комнатные", "Трёхкомнатные квартиры"),
                ("Студии", "Компактные студии"),
                ("Пентхаусы", "Элитные пентхаусы"),
                ("Новостройки", "Квартиры в новостройках"),
                ("Вторичка", "Квартиры на вторичном рынке"),
                ("Элитное жильё", "Премиум-класс"),
                ("Эконом-класс", "Бюджетное жильё"),
                ("Коммерческая недвижимость", "Офисы и магазины")
            ]
            
            for name, description in room_categories:
                cur.execute(
                    "INSERT INTO categories_room (name, description) VALUES (?, ?)",
                    (name, description)
                )
        
        # --- USERS ---
        existing_users = cur.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
        if existing_users == 0:
            users_data = [
                ("admin@example.com", "admin123", "Администратор", "+7-900-000-00-00", "admin"),
                ("user@example.com", "user123", "Тестовый пользователь", "+7-900-111-11-11", "user"),
                ("moder@example.com", "moder123", "Тестовый модератор", "+7-900-222-22-22", "moder"),
                ("seller@example.com", "seller123", "Тестовый селлер", "+7-900-333-33-33", "seller"),
            ]
            for email, password, name, phone, role in users_data:
                cur.execute(
                    """
                    INSERT INTO users (email, password, name, phone, role)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (email, password, name, phone, role),
                )
                user_id = cur.lastrowid
                # создаём корзину для пользователя
                cur.execute(
                    "INSERT INTO cart (user_id, total_price) VALUES (?, ?)",
                    (user_id, 0.0),
                )

        # --- CATEGORIES ---
        existing_cats = cur.execute("SELECT COUNT(*) AS cnt FROM categories").fetchone()["cnt"]
        if existing_cats == 0:
            categories_data = [
                ("Услуги", ""),
                ("Напольные покрытия", ""),
                ("Сантехника", ""),
                ("Освещение", ""),
                ("Инструменты", ""),
                ("Стройматериалы", ""),
                ("Мебель", ""),
                ("Краски", ""),
                ("Двери", ""),
                ("Декор", ""),
            ]
            for name, desc in categories_data:
                cur.execute(
                    "INSERT INTO categories (name, description) VALUES (?, ?)",
                    (name, desc),
                )

        # Получаем id категорий
        cur.execute("SELECT id, name FROM categories")
        cats = {row["name"]: row["id"] for row in cur.fetchall()}

        # --- SOFTWARE ---
        existing_sw = cur.execute("SELECT COUNT(*) AS cnt FROM software").fetchone()["cnt"]
        if existing_sw == 0:
            software_data = [
                # цены и category_name подставь под свою таблицу, пути к картинкам — под свои файлы
                ("Сантехник",
                 "Демонтаж. монтаж унитазов, демонтаж, монтаж смесителя радиаторов отопления, замена труб полипропилен, металл, замена стояков, замена полотенцесушителей, замена блочных кранов, установка счётчиков, сантехника, монтаж, установка водоснабжения, отопления, канализации.",
                 1000.0,
                 "Услуги",
                 "Валерий",
                 "/static/plumber.png"),
                ("Ламинат",
                 "Кварцевый SPC ламинат Fargo Parquet — это напольное покрытие под дерево, рисунок ДУБ с микро фаской, 41 классом истираемости и толщиной 3.5 мм. Возможна ка обычная укладка, так и елочкой. SPC ламинат отлично подходит для коммерческого и бытового применения. Материал полностью водостойкий и не имеет линейного расширения.",
                 2690.0,
                 "Напольные покрытия",
                 "ПолАрт",
                 "/static/floor.png"),
                ("Смеситель для раковины",
                 "Смеситель для раковины KONSENSA Прато однорычажный цвет хром",
                 4942.0,
                 "Сантехника",
                 "KONSENSA",
                 "/static/sink_faucet.png"),
                ("Лампа светодиодная",
                 "Лампа светодиодная GX53 170-240 В 12 Вт круг матовая 1300 лм нейтральный белый свет",
                 206.0,
                 "Освещение",
                 "Китай",
                 "/static/lamp.png"),
                ("Набор инструментов",
                 "Набор инструментов Deko DKMT196, 196 предм.",
                 3750.0,
                 "Инструменты",
                 "Deko",
                 "/static/tool.png"),
                ("Гипсокартон",
                 "Гипсокартон 12.5 мм Knauf 1500x600 мм 0.9 м²",
                 201.0,
                 "Стройматериалы",
                 "Knauf",
                 "/static/drywall.png"),
                ("Тумба с ящиками и полками",
                 "Тумба под ТВ МОНО ЛАЙТ с ящиками и полками 54х140х32 бежевый",
                 6354.0,
                 "Мебель",
                 "Россия",
                 "/static/pedestal.png"),
                ("Краска для стен",
                 "Краска для стен Luxens матовая белая база А 1 л",
                 412.0,
                 "Краски",
                 "Luxens",
                 "/static/wall_paint.png"),
                ("Входная дверь",
                 "Входная дверь Двери регионов Президент Лайн правый 205x96.5см цемент светлый",
                 44900.0,
                 "Двери",
                 "Двери регионов",
                 "/static/front_door.png"),
                ("Полотенцесушитель электрически",
                 "Полотенцесушитель электрический Equation 450x600 мм 130 Вт с терморегулятором и полкой лесенка цвет черный",
                 9783.0,
                 "Сантехника",
                 "Equation",
                 "/static/heated_towel_rail.png"),
                ("Зеркало",
                 "Зеркало напольное и настенное Inspire Альпы прямоугольное 40x160 см цвет белый",
                 3925.0,
                 "Декор",
                 "Inspire",
                 "/static/mirror.png"),
                ("Раковина",
                 "Раковина Оникс 60 см на стиральную машину",
                 6615.0,
                 "Сантехника",
                 "Россия",
                 "/static/sink.png"),
            ]

            for name, desc, price, cat_name, dev, img in software_data:
                category_id = cats.get(cat_name)
                if not category_id:
                    continue
                cur.execute(
                    """
                    INSERT INTO software (name, description, price, category_id, developer, image_url)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (name, desc, price, category_id, dev, img),
                )

        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Seeding initial data failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    # Инициализация базы данных при запуске скрипта
    init_db()
    seed_initial_data()
    print('Database initialized successfully!')
