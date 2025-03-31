from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import User
from app import db

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if current_user.role != 'admin':
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('dashboard.dashboard'))
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
