import requests
from lxml import html
import time
import re
from urllib.parse import urlparse
from datetime import datetime


class SiriusParser:
    def __init__(self):
        self.session = requests.Session()
        self.home_url = 'https://siriust.ru'
        self.user_info = {}
        self.favorites = []

        self.session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept-Language': 'ru-RU,ru',
        'Referer': self.home_url
    })

    def login(self, username, password):
        self.session.get(self.home_url)

        data = {
            'user_login': username,
            'password': password,
            'dispatch[auth.login]': ''
        }

        response = self.session.post(self.home_url, data=data, allow_redirects=True)

        if response.status_code != 200:
            raise Exception(f'Ошибка авторизации. Код: {response.status_code}')
        
        tree = html.fromstring(response.content)
        logout_button = tree.xpath('//a[contains(@href, "auth.logout")]')

        if not logout_button:
            raise Exception('Не удалось авторизоваться: неверные данные или проблема с сессией')

        print('[LOG] успешная авторизация')

    def get_personal_info(self):
        profile_url = f'{self.home_url}/profiles-update/'
        response = self.session.get(profile_url)

        tree = html.fromstring(response.content)

        self.user_info = {
            'email': tree.xpath('//input[@id="email"]/@value')[0].strip(),
            'first_name': tree.xpath('//input[@id="elm_15"]/@value')[0].strip()
            if tree.xpath('//input[@id="elm_15"]') else None,
            'last_name': tree.xpath('//input[@id="elm_17"]/@value')[0].strip()
            if tree.xpath('//input[@id="elm_17"]') else None,
            'city': tree.xpath('//input[@id="elm_23"]/@value')[0].strip()
            if tree.xpath('//input[@id="elm_23"]') else None
        }
        print('[LOG] Персональные данные получены')

    def get_favorites(self):
        favorites_url = f'{self.home_url}/wishlist/?nocache={time.time()}'
        response = self.session.get(favorites_url)

        tree = html.fromstring(response.content)
        items = tree.xpath('//div[contains(@class, "ty-grid-list__item") '
                          'and not(.//div[contains(@class, "ty-grid-list__item")])]')

        for item in items:
            try:
                name_element = item.xpath('.//a[@class="product-title"]')
                item_name = name_element[0].text.strip() if name_element else None
                print(f"[LOG] Найден товар: {item_name}")
                product_url = item.xpath('.//a[@class="product-title"]/@href')[0]
                product_details = self.parse_product_details(product_url)

                self.favorites.append({
                    'item_name': item_name,
                    'retail_price': product_details['retail_price'],
                    'wholesale_price': product_details['wholesale_price'],
                    'rating': product_details['rating_stars'],
                    'product_url': product_url,
                    'review_count': product_details['review_count'],
                    'store_count': product_details['store_count'],
                    'reviews': product_details['reviews']
                })
            except Exception as e:
                print(f'Ошибка парсинга товара: {e}')
                continue

        print('[LOG] Данные избранного собраны')

    def parse_product_details(self, product_url):
        response = self.session.get(product_url)
        tree = html.fromstring(response.text)

        retail_price = 0.00
        try:
            price_element = tree.xpath('//span[contains(@class, "two_prices_title") '
                                      'and contains(text(), "Розничная")]/preceding-sibling::'
                                      'span[@class="ty-price"]//span[@class="ty-price-num"]')
            if price_element:
                price_text = price_element[0].text.strip()
                retail_price = float(''.join([c for c in price_text if c.isdigit() or c == '.']))
            else:
                print("Ошибка: Розничная цена не найдена")
        except Exception as e:
            print(f"Ошибка парсинга розничной цены: {e}")

        wholesale_price = 0.00
        try:
            price_element = tree.xpath('//span[contains(@class, "two_prices_title") '
                                      'and contains(text(), "Оптовая")]/preceding-sibling::'
                                      'span[@class="ty-price"]//span[@class="ty-price-num"]')
            if price_element:
                price_text = price_element[0].text.strip()
                wholesale_price = float(''.join([c for c in price_text if c.isdigit() or c == '.']))
            else:
                print("Ошибка: Розничная цена не найдена")
        except Exception as e:
            print(f"Ошибка парсинга розничной цены: {e}")

        try:
            stars = tree.xpath('//div[contains(@class, "ty-product-block__rating")]'
                              '//i[contains(@class, "ty-icon-star")]')
            rating_stars = 0.0
            for star in stars:
                if 'ty-icon-star-half' in star.classes:
                    rating_stars += 0.5
                elif 'ty-icon-star' in star.classes:
                    rating_stars += 1.0
            rating_stars = min(rating_stars, 5.0)
            rating_stars = round(rating_stars, 1)
        except Exception as e:
            print(f"Ошибка парсинга рейтинга: {e}")
            rating_stars = 0.0

        review_count = 0
        try:
            review_link = tree.xpath('//a[contains(@class, "ty-discussion__review-a") '
                                    'and contains(text(), "Отзыв")]')
            if review_link:
                review_text = review_link[0].text_content().strip()
                c = re.search(r'(\d+)', review_text)
                review_count = int(c.group(1)) if c else 0
        except Exception as e:
            print(f"Ошибка парсинга отзывов: {e}")

        reviews = self.parse_reviews(product_url)
        print(f"[LOG] Найдено отзывов для товара: {len(reviews)}")

        store_count = 0
        try:
            store_images = tree.xpath('''
                //img[
                    contains(@src, "avail_") 
                    and not(contains(@src, "zero_cross"))
                ]
            ''')
            store_count = len(store_images)
        except Exception as e:
            print(f"Ошибка парсинга количества городов: {e}")
            store_count = 0

        return {
            'review_count': review_count,
            'store_count': store_count,
            'reviews': reviews,
            'retail_price': retail_price,
            'wholesale_price': wholesale_price,
            'rating_stars': rating_stars
        }

    def parse_reviews(self, product_url):
        try:
            reviews = []
            page = 1
            parsed_url = urlparse(product_url)
            home_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"

            while True:
                paginated_url = f"{home_url}?selected_section=discussion&page={page}"
                try:
                    response = self.session.get(paginated_url, timeout=10)
                    response.raise_for_status()
                except Exception as e:
                    print(f"Ошибка запроса: {str(e)}")
                    break

                tree = html.fromstring(response.content)
                review_blocks = tree.xpath('//div[contains(@class, "ty-discussion-post")]')
                if not review_blocks:
                    break

                page_reviews = self.parse_reviews_page(tree)
                reviews.extend(page_reviews)

                next_page = tree.xpath('//a[contains(@class, "ty-pagination__next") '
                                     'and not(@aria-disabled)]')
                if not next_page:
                    break

                page += 1
                time.sleep(2)

            return reviews
        except Exception as e:
            print(f"Ошибка парсинга отзывов: {str(e)}")
            return []

    def parse_reviews_page(self, tree):
        reviews = []
        review_blocks = tree.xpath('//div[contains(concat(" ", normalize-space(@class), " "), '
                                  '" ty-discussion-post ")]')
        for block in review_blocks:
            try:
                username = block.xpath('.//span[@class="ty-discussion-post__author"]/text()')
                username = username[0].strip() if username else None

                rating = block.xpath('.//meta[@itemprop="ratingValue"]/@content')
                rating = float(rating[0]) if rating else 0.0

                review_date = block.xpath('.//span[@class="ty-discussion-post__date"]/text()')
                review_date = review_date[0].strip() if review_date else None
                if review_date:
                    review_date = datetime.strptime(review_date, '%d.%m.%Y, %H:%M')

                meta_review = block.xpath('.//meta[@itemprop="reviewBody"]/@content')
                if meta_review:
                    review_text = meta_review[0].strip()
                else:
                    message_div = block.xpath('.//div[contains(@class, "ty-discussion-post__message")]')
                    if message_div:
                        review_text = message_div[0].text_content().strip()
                        review_text = re.sub(r'\s+', ' ', review_text)
                    else:
                        review_text = None

                if review_text:
                    reviews.append({
                        'username': username,
                        'rating': rating,
                        'review_date': review_date,
                        'review_text': review_text
                    })
            except Exception as e:
                print(f"Ошибка парсинга: {str(e)}")
                continue

        return reviews