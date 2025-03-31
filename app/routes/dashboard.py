import datetime
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import Product, Notification
from app.utils import get_user_product
from app import db

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../../templates')

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
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

@dashboard_bp.route('/apply/<int:product_id>', methods=['POST'])
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
    return redirect(url_for('dashboard.dashboard'))

@dashboard_bp.route('/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    notifications = Notification.query.filter_by(user_id=current_user.id, read=False).all()
    for note in notifications:
        note.read = True
    db.session.commit()
    flash("Уведомления отмечены как прочитанные.", "success")
    return redirect(url_for('dashboard.dashboard'))
