from flask import Flask, render_template, request, redirect, url_for, flash
import datetime
from collections import defaultdict
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from packaging import version

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///szi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')
    full_name = db.Column(db.String(100))
    profession = db.Column(db.String(100))
    notify = db.Column(db.Boolean, default=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    latest_version = db.Column(db.String(50))
    last_updated = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    error = db.Column(db.String(200))

class UserProduct(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    accepted_version = db.Column(db.String(50))
    accepted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255))
    read = db.Column(db.Boolean, default=False)


class ProductVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    version = db.Column(db.String(50), nullable=False)
    release_date = db.Column(db.String(50))
    full_title = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))




with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            password=generate_password_hash('admin'),
            role='admin'
        )
        db.session.add(admin_user)
        db.session.commit()
    if Product.query.count() == 0:
        sample_products = [
            Product(vendor='Kaspersky', name='Антивирус', latest_version=''),
            Product(vendor='Huawei', name='USG', latest_version='2.3'),
            Product(vendor='SafeInspect', name='SafeInspect', latest_version='3.5')
        ]
        db.session.bulk_save_objects(sample_products)
        db.session.commit()



def get_user_product(user_id, product):
    user_prod = UserProduct.query.filter_by(user_id=user_id, product_id=product.id).first()
    if not user_prod:
        user_prod = UserProduct(
            user_id=user_id,
            product_id=product.id,
            accepted_version=product.latest_version,
            accepted_at=datetime.datetime.utcnow()
        )
        db.session.add(user_prod)
        db.session.commit()
    return user_prod



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if not user:
            flash('Неверное имя пользователя', 'danger')
        elif not check_password_hash(user.password, password):
            flash('Неверный пароль', 'danger')
        else:
            login_user(user)
            flash('Вход выполнен успешно.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('login'))



@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    products = Product.query.all()
    grouped_products = {}
    for prod in products:
        user_prod = get_user_product(current_user.id, prod)
        if prod.vendor not in grouped_products:
            grouped_products[prod.vendor] = []
        grouped_products[prod.vendor].append({
            'id': prod.id,
            'name': prod.name,
            'accepted_version': user_prod.accepted_version,
            'latest_version': prod.latest_version
        })
    notifications = Notification.query.filter_by(user_id=current_user.id, read=False).all()
    return render_template('dashboard.html', grouped_products=grouped_products, notifications=notifications)


@app.route('/apply/<int:product_id>', methods=['POST'])
@login_required
def apply_change(product_id):
    product = Product.query.get_or_404(product_id)
    user_prod = get_user_product(current_user.id, product)
    if product.latest_version and product.latest_version != user_prod.accepted_version:
        user_prod.accepted_version = product.latest_version
        user_prod.accepted_at = datetime.datetime.utcnow()
        db.session.commit()
        flash(f'Изменения приняты для {product.vendor} {product.name}.', 'success')
    else:
        flash('Нет новых изменений для применения.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    notifications = Notification.query.filter_by(user_id=current_user.id, read=False).all()
    for note in notifications:
        note.read = True
    db.session.commit()
    flash("Уведомления отмечены как прочитанные.", "success")
    return redirect(url_for('dashboard'))


@app.route('/update_kaspersky')
@login_required
def update_kaspersky_versions():
    url = "https://support.kaspersky.ru/corporate/lifecycle?type=limited,full&view=table"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            product_blocks = soup.select("div.product-gantt__list-items > div.product-gantt__list-item")

            latest_versions = {}  # {product_name: (latest_version, release_date)}

            for block in product_blocks:
                title_tag = block.select_one("div.product-gantt__list-item-title")
                version_tag = block.select_one("div.product-gantt__list-item-version")

                if title_tag and version_tag:
                    product_name = title_tag.get_text(strip=True)
                    product_version = version_tag.get_text(strip=True)

                    # Пропускаем, если версия не указана корректно
                    if product_version in ["—", "", None]:
                        continue

                    # Извлекаем дату релиза
                    release_date = None
                    info_items = block.select("div.product-gantt__extra-info-item")
                    for item in info_items:
                        title_div = item.find("div", class_="product-gantt__extra-info-title")
                        value_div = item.find("div", class_="product-gantt__extra-info-value")
                        if title_div and "Релиз" in title_div.get_text() and value_div:
                            release_date = value_div.get_text(strip=True)
                            break

                    # Сравниваем версии по тексту, если версия содержит недопустимые символы
                    if product_name not in latest_versions or product_version > latest_versions[product_name][0]:
                        latest_versions[product_name] = (product_version, release_date)

            updated_versions = []

            for product_name, (latest_version, release_date) in latest_versions.items():
                prod = Product.query.filter_by(vendor="Kaspersky", name=product_name).first()
                if not prod:
                    prod = Product(vendor="Kaspersky", name=product_name, latest_version=latest_version)
                    db.session.add(prod)
                    db.session.commit()

                # Проверяем, добавлена ли эта версия в базу
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

                    # Создаем уведомления
                    users = User.query.filter_by(notify=True).all()
                    for user in users:
                        user_prod = get_user_product(user.id, prod)
                        if user_prod.accepted_version != latest_version:
                            message = f"Новая версия для {prod.vendor} {prod.name}: {latest_version}"
                            notification = Notification(user_id=user.id, message=message)
                            db.session.add(notification)

                # Обновляем latest_version
                if not prod.latest_version or prod.latest_version < latest_version:
                    prod.latest_version = latest_version

            db.session.commit()
            if updated_versions:
                flash('Добавлено новых версий: ' + str(len(updated_versions)), 'success')
            else:
                flash('Новых версий не обнаружено.', 'info')

            return redirect(url_for('dashboard'))

        else:
            flash('Ошибка при получении данных с сайта Kaspersky.', 'danger')
            return redirect(url_for('dashboard'))

    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))



@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if current_user.role != 'admin':
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        if 'new_user' in request.form:
            new_username = request.form['username']
            new_password = request.form['password']
            role = request.form['role']
            if User.query.filter_by(username=new_username).first():
                flash('Пользователь уже существует.', 'warning')
            else:
                new_user = User(
                    username=new_username,
                    password=generate_password_hash(new_password),
                    role=role
                )
                db.session.add(new_user)
                db.session.commit()
                flash(f'Пользователь {new_username} создан.', 'success')
        if 'change_password' in request.form:
            current_password = request.form['current_password']
            new_password = request.form['new_password']
            if check_password_hash(current_user.password, current_password):
                current_user.password = generate_password_hash(new_password)
                db.session.commit()
                flash('Пароль изменён.', 'success')
            else:
                flash('Неверный текущий пароль.', 'danger')
    users = User.query.all()
    return render_template('settings.html', users=users)



@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.profession = request.form.get('profession')
        current_user.notify = (request.form.get('notify') == 'on')
        db.session.commit()
        flash('Настройки профиля обновлены.', 'success')
    return render_template('profile.html', user=current_user)


if __name__ == '__main__':
    app.run(debug=True)
