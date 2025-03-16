import psycopg2

class Database:
    def __init__(self, dbname, user, password, host='localhost'):
        self.conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host
        )
        self.cur = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                city VARCHAR(100)
            )
        ''')
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                product_id SERIAL PRIMARY KEY,  -- Автоматически генерируемый ID (INTEGER)
                user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                item_name TEXT NOT NULL,
                retail_price NUMERIC(10, 2),
                wholesale_price NUMERIC(10, 2),
                rating NUMERIC(3, 1),
                review_count INTEGER,
                store_count INTEGER
            )
        ''')
        self.cur.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                comment_id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES favorites(product_id) ON DELETE CASCADE,  -- Используем INTEGER
                username VARCHAR(100),
                rating NUMERIC(3, 1),
                review_date TIMESTAMP,
                review_text TEXT
            )
        ''')
        self.conn.commit()

    def save_user(self, user_info):
        try:
            self.cur.execute('''
                INSERT INTO users (email, first_name, last_name, city)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (email) DO NOTHING
            ''', (user_info['email'], user_info['first_name'],
                 user_info['last_name'], user_info['city']))
            self.cur.execute('''
                SELECT user_id FROM users WHERE email = %s
            ''', (user_info['email'],))
            user_id = self.cur.fetchone()[0]
            self.conn.commit()
            return user_id
        except Exception as e:
            self.conn.rollback()
            raise e

    def save_favorites(self, user_id, favorites):
        try:
            self.cur.execute('''
                DELETE FROM favorites WHERE user_id = %s
            ''', (user_id,))
            for product in favorites:
                self.cur.execute('''
                    INSERT INTO favorites 
                    (user_id, item_name, retail_price, wholesale_price, rating, review_count, store_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING product_id
                ''', (
                    user_id,
                    product['item_name'],
                    product['retail_price'],
                    product['wholesale_price'],
                    product['rating'],
                    product['review_count'],
                    product['store_count']
                ))

                product_id = self.cur.fetchone()[0]

                if product['reviews']:
                    self.cur.executemany('''
                        INSERT INTO reviews (product_id, username, rating, review_date, review_text)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', [
                        (product_id, review['username'], review['rating'], review['review_date'], review['review_text'])
                        for review in product['reviews']
                    ])

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e

    def close(self):
        self.cur.close()
        self.conn.close()