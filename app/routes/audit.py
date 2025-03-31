import csv
from io import StringIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, render_template
from flask_login import login_required, current_user
from packaging import version
from app.models import AuditItem, Product
from app import db
from app.controllers.product_updates import parse_version_with_annotation

audit_bp = Blueprint('audit', __name__)

@audit_bp.route('/audit', methods=['GET', 'POST'])
@login_required
def audit():
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        user_version = request.form.get('user_version')
        if product_id and user_version:
            product = db.session.get(Product, product_id)
            if product:
                audit_item = AuditItem(user_id=current_user.id, product_id=product.id, user_version=user_version)
                db.session.add(audit_item)
                db.session.commit()
                flash('Устройство добавлено в аудит.', 'success')
            else:
                flash('Устройство не найдено.', 'danger')
        else:
            flash('Заполните все поля.', 'warning')
        return redirect(url_for('audit.audit'))
    else:
        audit_items = AuditItem.query.filter_by(user_id=current_user.id).all()
        grouped = {}
        for item in audit_items:
            product = db.session.get(Product, item.product_id)
            if product.vendor not in grouped:
                grouped[product.vendor] = []
            try:
                current_v = version.parse(item.user_version)
                latest_v = version.parse(product.latest_version) if product.latest_version else None
            except Exception:
                current_v = None
                latest_v = None
            can_update = current_v and latest_v and current_v < latest_v
            grouped[product.vendor].append({
                'audit_id': item.id,
                'product_name': product.name,
                'user_version': item.user_version,
                'latest_version': product.latest_version,
                'can_update': can_update
            })
        products = Product.query.all()
        return render_template('audit.html', grouped=grouped, products=products)

@audit_bp.route('/audit/clear', methods=['POST'])
@login_required
def clear_audit():
    AuditItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Таблица аудита очищена.', 'success')
    return redirect(url_for('audit.audit'))

@audit_bp.route('/audit/export/csv')
@login_required
def export_audit_csv():
    audit_items = AuditItem.query.filter_by(user_id=current_user.id).all()
    grouped = {}
    for item in audit_items:
        product = db.session.get(Product, item.product_id)
        if product.vendor not in grouped:
            grouped[product.vendor] = []
        try:
            current_v, _ = parse_version_with_annotation(item.user_version)
            latest_v, _ = parse_version_with_annotation(product.latest_version) if product.latest_version else (
            None, None)
        except Exception:
            current_v = None
            latest_v = None
        needs_update = current_v and latest_v and current_v < latest_v
        grouped[product.vendor].append({
            'product_name': product.name,
            'user_version': item.user_version,
            'latest_version': product.latest_version,
            'needs_update': needs_update
        })

    output = StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    for vendor, items in grouped.items():
        writer.writerow([f"Vendor: {vendor}"])
        writer.writerow(['Устройство', 'Ваша версия', 'Актуальная версия', 'Needs Update'])
        for item in items:
            user_version_text = f'="{item["user_version"]}"'
            latest_version_text = f'="{item["latest_version"]}"' if item["latest_version"] else ""
            needs_update_text = "Yes" if item["needs_update"] else "No"
            writer.writerow([item["product_name"], user_version_text, latest_version_text, needs_update_text])
        writer.writerow([])  # пустая строка между группами
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=audit.csv"})

@audit_bp.route('/audit/export/html')
@login_required
def export_audit_html():
    audit_items = AuditItem.query.filter_by(user_id=current_user.id).all()
    grouped = {}
    for item in audit_items:
        product = db.session.get(Product, item.product_id)
        if product.vendor not in grouped:
            grouped[product.vendor] = []
        try:
            current_v = version.parse(item.user_version)
            latest_v = version.parse(product.latest_version) if product.latest_version else None
        except Exception:
            current_v = None
            latest_v = None
        can_update = current_v and latest_v and current_v < latest_v
        grouped[product.vendor].append({
            'product_name': product.name,
            'user_version': item.user_version,
            'latest_version': product.latest_version,
            'can_update': can_update
        })
    rendered = render_template('audit_export.html', grouped=grouped)
    return Response(rendered, mimetype="text/html",
                    headers={"Content-Disposition": "attachment;filename=audit.html"})
