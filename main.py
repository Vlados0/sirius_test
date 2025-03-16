from sirius_parser.parser import SiriusParser
from sirius_parser.database import Database
from sirius_parser.config import DB_CONFIG

def main():
    username = input('Введите email: ')
    password = input('Введите пароль: ')

    parser = SiriusParser()
    try:
        parser.login(username, password)
        parser.get_personal_info()
        parser.get_favorites()
    except Exception as e:
        print(f'Ошибка: {e}')
        return

    db = Database(**DB_CONFIG)
    try:
        user_id = db.save_user(parser.user_info)
        db.save_favorites(user_id, parser.favorites)
        print('[LOG] Данные успешно сохранены в БД')
    except Exception as e:
        print(f'Cохранения в БД: {e}')
    finally:
        db.close()

if __name__ == '__main__':
    main()