import datetime
import re
import requests
from bs4 import BeautifulSoup
from packaging import version
from flask import flash
from ..models import Product, ProductVersion, Notification, User
from ..utils import get_user_product
from .. import db
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def parse_version_with_annotation(ver):
    # Ищем первую последовательность вида 1.2.3... в строке
    match = re.search(r'(\d+(?:\.\d+)+)', ver)
    if match:
        numeric_part = match.group(1)
        annotation = ver[match.end():].strip()  # Остальная часть строки
        return version.parse(numeric_part), annotation
    else:
        raise ValueError(f"Неверный формат версии: {ver}")


def update_kaspersky_internal():
    url = "https://support.kaspersky.ru/corporate/lifecycle?type=limited,full&view=table"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            product_blocks = soup.select("div.product-gantt__list-items > div.product-gantt__list-item")
            latest_versions = {}
            for block in product_blocks:
                title_tag = block.select_one("div.product-gantt__list-item-title")
                version_tag = block.select_one("div.product-gantt__list-item-version")
                if title_tag and version_tag:
                    product_name = title_tag.get_text(strip=True)
                    product_version = version_tag.get_text(strip=True)
                    if product_version in ["—", "", None]:
                        continue
                    release_date = None
                    info_items = block.select("div.product-gantt__extra-info-item")
                    for item in info_items:
                        title_div = item.find("div", class_="product-gantt__extra-info-title")
                        value_div = item.find("div", class_="product-gantt__extra-info-value")
                        if title_div and "Релиз" in title_div.get_text() and value_div:
                            release_date = value_div.get_text(strip=True)
                            break

                    # Получаем числовую часть для сравнения
                    try:
                        numeric_current, _ = parse_version_with_annotation(product_version)
                    except Exception as e:
                        # Если версия не соответствует формату, пропускаем её
                        continue

                    if product_name not in latest_versions:
                        latest_versions[product_name] = (product_version, release_date)
                    else:
                        stored_version = latest_versions[product_name][0]
                        try:
                            numeric_stored, _ = parse_version_with_annotation(stored_version)
                        except Exception:
                            numeric_stored = None
                        if numeric_stored is None or numeric_current > numeric_stored:
                            latest_versions[product_name] = (product_version, release_date)

            updated_versions = []
            for product_name, (latest_version, release_date) in latest_versions.items():
                prod = Product.query.filter_by(vendor="Kaspersky", name=product_name).first()
                if not prod:
                    prod = Product(vendor="Kaspersky", name=product_name, latest_version=latest_version)
                    db.session.add(prod)
                    db.session.commit()
                existing_version = ProductVersion.query.filter_by(product_id=prod.id, version=latest_version).first()
                if not existing_version:
                    new_version_entry = ProductVersion(
                        product_id=prod.id,
                        version=latest_version,
                        release_date=release_date,
                        full_title=product_name
                    )
                    db.session.add(new_version_entry)
                    updated_versions.append((prod.vendor, prod.name, latest_version))
                    users = User.query.filter_by(notify=True).all()
                    for user in users:
                        user_prod = get_user_product(user.id, prod)
                        try:
                            current_numeric, _ = parse_version_with_annotation(latest_version)
                            if user_prod.accepted_version:
                                accepted_numeric, _ = parse_version_with_annotation(user_prod.accepted_version)
                            else:
                                accepted_numeric = None
                        except Exception:
                            continue
                        if accepted_numeric is None or current_numeric > accepted_numeric:
                            message = f"Новая версия для {prod.vendor} {prod.name}: {latest_version}"
                            notification = Notification(user_id=user.id, message=message)
                            db.session.add(notification)
                # Обновляем latest_version, сравнивая только числовые части
                try:
                    current_numeric, _ = parse_version_with_annotation(latest_version)
                    prod_numeric, _ = parse_version_with_annotation(prod.latest_version)
                    if prod_numeric < current_numeric:
                        prod.latest_version = latest_version
                except Exception:
                    prod.latest_version = latest_version

            db.session.commit()
            if updated_versions:
                return f'Добавлено новых версий: {len(updated_versions)}'
            else:
                return 'Новых версий не обнаружено'
        else:
            return "Ошибка при получении данных с сайта Kaspersky."
    except Exception as e:
        return f"Ошибка: {str(e)}"

def get_final_response(url, headers):
    session = requests.Session()
    response = session.get(url, headers=headers, verify=False, allow_redirects=True)
    return response

def extract_build_number(ver_str):
    m = re.search(r'build\s+(\d+(\.\d+)+)', ver_str, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def extract_highest_stable_version(soup):
    valid_versions = []
    for tag in soup.find_all("skip-glossary"):
        full_text = tag.get_text(strip=True)
        # Ищем ближайший div с классом textBlock, где указан статус
        status_block = tag.find_next("div", class_="textBlock")
        if not status_block:
            continue
        status_text = status_block.get_text(strip=True)
        if "Стабильно" not in status_text:
            continue
        try:
            # Пытаемся найти версию после слова "build"
            m = re.search(r'build\s+(\d+(\.\d+)+)', full_text, re.IGNORECASE)
            if m:
                ver_str = m.group(1)
            else:
                # Если не найдено, находим первую числовую последовательность
                m = re.search(r'(\d+(\.\d+)+)', full_text)
                if m:
                    ver_str = m.group(1)
                else:
                    continue
            valid_versions.append((ver_str, full_text))
        except Exception:
            continue
    if not valid_versions:
        return None, None
    highest_version = max(valid_versions, key=lambda v: version.parse(v[0]))
    return highest_version

def update_usergate_ngfw_internal_7():
    url = "https://docs.usergate.com/izmeneniya-v-ngfw-7-243/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
    }
    try:
        response = get_final_response(url, headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            ver_number, full_text = extract_highest_stable_version(soup)
            if ver_number and full_text:
                prod = Product.query.filter_by(vendor="UserGate 7.x", name="NGFW").first()
                if not prod:
                    prod = Product(vendor="UserGate 7.x", name="NGFW", latest_version=full_text)
                    db.session.add(prod)
                else:
                    prod.latest_version = full_text

                # Добавляем уведомления для пользователей, сравнивая номер сборки
                current_build = extract_build_number(full_text)
                if not current_build:
                    # Если не удалось извлечь номер сборки, пропускаем уведомление
                    pass
                else:
                    users = User.query.filter_by(notify=True).all()
                    for user in users:
                        user_prod = get_user_product(user.id, prod)
                        if user_prod.accepted_version:
                            accepted_build = extract_build_number(user_prod.accepted_version)
                        else:
                            accepted_build = None
                        # Если принятой версии нет или текущая сборка больше, создаём уведомление
                        if accepted_build is None or version.parse(current_build) > version.parse(accepted_build):
                            message = f"Новая версия для {prod.vendor} {prod.name}: {full_text}"
                            notification = Notification(user_id=user.id, message=message)
                            db.session.add(notification)

                db.session.commit()
                flash(f"UserGate 7.x NGFW обновлено: {full_text}", "success")
                return f"UserGate NGFW 7.x обновлено: {full_text}"
            else:
                flash("Подходящих версий для UserGate 7x NGFW не найдено.", "info")
                return "Подходящих версий для UserGate 7.x NGFW не найдено."
        else:
            flash("Ошибка получения данных для UserGate 7.x NGFW.", "danger")
            return "Ошибка получения данных для UserGate 7.x NGFW."
    except Exception as e:
        flash(f"Ошибка: {str(e)}", "danger")
        return f"Ошибка: {str(e)}"

def update_usergate_management_center_internal_7():
    url = "https://docs.usergate.com/izmeneniya-v-usergate-management-center-7-247/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
    }
    try:
        response = get_final_response(url, headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            ver_number, full_text = extract_highest_stable_version(soup)
            if ver_number and full_text:
                prod = Product.query.filter_by(vendor="UserGate 7.x", name="Management Center").first()
                if not prod:
                    prod = Product(vendor="UserGate 7.x", name="Management Center", latest_version=full_text)
                    db.session.add(prod)
                else:
                    prod.latest_version = full_text

                # Добавляем уведомления для пользователей
                users = User.query.filter_by(notify=True).all()
                for user in users:
                    user_prod = get_user_product(user.id, prod)
                    try:
                        current_numeric, _ = parse_version_with_annotation(full_text)
                        if user_prod.accepted_version:
                            accepted_numeric, _ = parse_version_with_annotation(user_prod.accepted_version)
                        else:
                            accepted_numeric = None
                    except Exception:
                        continue
                    if accepted_numeric is None or current_numeric > accepted_numeric:
                        message = f"Новая версия для {prod.vendor} {prod.name}: {full_text}"
                        notification = Notification(user_id=user.id, message=message)
                        db.session.add(notification)

                db.session.commit()
                flash(f"UserGate 7.x Management Center обновлено: {full_text}", "success")
                return f"UserGate 7.x Management Center обновлено: {full_text}"
            else:
                flash("Подходящих версий для UserGate 7.x Management Center не найдено.", "info")
                return "Подходящих версий для UserGate 7.x Management Center не найдено."
        else:
            flash("Ошибка получения данных для UserGate 7.x Management Center.", "danger")
            return "Ошибка получения данных для UserGate 7.x Management Center."
    except Exception as e:
        flash(f"Ошибка: {str(e)}", "danger")
        return f"Ошибка: {str(e)}"


def update_usergate_ngfw_internal_6():
    url = "https://docs.usergate.com/izmeneniya-v-ngfw-6-240/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
    }
    try:
        response = get_final_response(url, headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            ver_number, full_text = extract_highest_stable_version(soup)
            if ver_number and full_text:
                prod = Product.query.filter_by(vendor="UserGate 6.x", name="NGFW").first()
                if not prod:
                    prod = Product(vendor="UserGate 6.x", name="NGFW", latest_version=full_text)
                    db.session.add(prod)
                else:
                    prod.latest_version = full_text

                # Добавляем уведомления для пользователей, сравнивая номер сборки
                current_build = extract_build_number(full_text)
                if not current_build:
                    # Если не удалось извлечь номер сборки, пропускаем уведомление
                    pass
                else:
                    users = User.query.filter_by(notify=True).all()
                    for user in users:
                        user_prod = get_user_product(user.id, prod)
                        if user_prod.accepted_version:
                            accepted_build = extract_build_number(user_prod.accepted_version)
                        else:
                            accepted_build = None
                        # Если принятой версии нет или текущая сборка больше, создаём уведомление
                        if accepted_build is None or version.parse(current_build) > version.parse(accepted_build):
                            message = f"Новая версия для {prod.vendor} {prod.name}: {full_text}"
                            notification = Notification(user_id=user.id, message=message)
                            db.session.add(notification)

                db.session.commit()
                flash(f"UserGate 6.x NGFW обновлено: {full_text}", "success")
                return f"UserGate NGFW 6.x обновлено: {full_text}"
            else:
                flash("Подходящих версий для UserGate 6x NGFW не найдено.", "info")
                return "Подходящих версий для UserGate 6.x NGFW не найдено."
        else:
            flash("Ошибка получения данных для UserGate 6.x NGFW.", "danger")
            return "Ошибка получения данных для UserGate 6.x NGFW."
    except Exception as e:
        flash(f"Ошибка: {str(e)}", "danger")
        return f"Ошибка: {str(e)}"

def update_usergate_management_center_internal_6():
    url = "https://docs.usergate.com/izmeneniya-v-usergate-management-center-6-241/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
    }
    try:
        response = get_final_response(url, headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            ver_number, full_text = extract_highest_stable_version(soup)
            if ver_number and full_text:
                prod = Product.query.filter_by(vendor="UserGate 6.x", name="Management Center").first()
                if not prod:
                    prod = Product(vendor="UserGate 6.x", name="Management Center", latest_version=full_text)
                    db.session.add(prod)
                else:
                    prod.latest_version = full_text

                # Добавляем уведомления для пользователей
                users = User.query.filter_by(notify=True).all()
                for user in users:
                    user_prod = get_user_product(user.id, prod)
                    try:
                        current_numeric, _ = parse_version_with_annotation(full_text)
                        if user_prod.accepted_version:
                            accepted_numeric, _ = parse_version_with_annotation(user_prod.accepted_version)
                        else:
                            accepted_numeric = None
                    except Exception:
                        continue
                    if accepted_numeric is None or current_numeric > accepted_numeric:
                        message = f"Новая версия для {prod.vendor} {prod.name}: {full_text}"
                        notification = Notification(user_id=user.id, message=message)
                        db.session.add(notification)

                db.session.commit()
                flash(f"UserGate 6.x Management Center обновлено: {full_text}", "success")
                return f"UserGate 6.x Management Center обновлено: {full_text}"
            else:
                flash("Подходящих версий для UserGate 6.x Management Center не найдено.", "info")
                return "Подходящих версий для UserGate 6.x Management Center не найдено."
        else:
            flash("Ошибка получения данных для UserGate 6.x Management Center.", "danger")
            return "Ошибка получения данных для UserGate 6.x Management Center."
    except Exception as e:
        flash(f"Ошибка: {str(e)}", "danger")
        return f"Ошибка: {str(e)}"


def update_securitycode_internal():
    url = "https://www.securitycode.ru/products/lifecycle/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            container = soup.select_one("body > div.container > div.inside-container > div > div:nth-child(5)")
            if not container:
                return "Контейнер с данными не найден."
            rows = container.find_all("tr", class_="common-table__row-non-rwd")
            latest_versions = {}
            for row in rows:
                cells = row.find_all("td", class_="common-table__cell-non-rwd")
                if len(cells) < 3:
                    continue
                product_name = cells[0].get_text(strip=True)
                version_text = cells[1].get_text(strip=True)
                release_date = cells[2].get_text(strip=True)
                if version_text in ["—", "", None]:
                    continue
                try:
                    numeric_version, _ = parse_version_with_annotation(version_text)
                except Exception:
                    continue
                if product_name not in latest_versions:
                    latest_versions[product_name] = (version_text, release_date)
                else:
                    stored_version = latest_versions[product_name][0]
                    try:
                        numeric_stored, _ = parse_version_with_annotation(stored_version)
                    except Exception:
                        numeric_stored = None
                    if numeric_stored is None or numeric_version > numeric_stored:
                        latest_versions[product_name] = (version_text, release_date)

            updated_versions = []
            for product_name, (latest_version, release_date) in latest_versions.items():
                prod = Product.query.filter_by(vendor="Код Безопасности", name=product_name).first()
                if not prod:
                    prod = Product(vendor="Код Безопасности", name=product_name, latest_version=latest_version)
                    db.session.add(prod)
                    db.session.commit()
                existing_version = ProductVersion.query.filter_by(product_id=prod.id, version=latest_version).first()
                if not existing_version:
                    new_version_entry = ProductVersion(
                        product_id=prod.id,
                        version=latest_version,
                        release_date=release_date,
                        full_title=product_name
                    )
                    db.session.add(new_version_entry)
                    updated_versions.append((prod.vendor, prod.name, latest_version))
                    users = User.query.filter_by(notify=True).all()
                    for user in users:
                        user_prod = get_user_product(user.id, prod)
                        try:
                            current_numeric, _ = parse_version_with_annotation(latest_version)
                            if user_prod.accepted_version:
                                accepted_numeric, _ = parse_version_with_annotation(user_prod.accepted_version)
                            else:
                                accepted_numeric = None
                        except Exception:
                            continue
                        if accepted_numeric is None or current_numeric > accepted_numeric:
                            message = f"Новая версия для {prod.vendor} {prod.name}: {latest_version}"
                            notification = Notification(user_id=user.id, message=message)
                            db.session.add(notification)
                # Обновляем latest_version, сравнивая только числовые части
                try:
                    current_numeric, _ = parse_version_with_annotation(latest_version)
                    prod_numeric, _ = parse_version_with_annotation(prod.latest_version)
                    if prod_numeric < current_numeric:
                        prod.latest_version = latest_version
                except Exception:
                    prod.latest_version = latest_version

            db.session.commit()
            if updated_versions:
                return f'Добавлено новых версий: {len(updated_versions)}'
            else:
                return 'Новых версий не обнаружено'
        else:
            return "Ошибка при получении данных с сайта Код Безопасности."
    except Exception as e:
        return f"Ошибка: {str(e)}"