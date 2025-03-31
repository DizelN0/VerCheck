from flask import Blueprint, flash, redirect, url_for
from flask_login import login_required
from app.controllers import product_updates

update_bp = Blueprint('update', __name__)

@update_bp.route('/update_usergate_ngfw_6')
@login_required
def update_usergate_ngfw_6():
    result = product_updates.update_usergate_ngfw_internal_6()
    return result

@update_bp.route('/update_securitycode_internal')
@login_required
def update_securitycode_internal():
    result = product_updates.update_securitycode_internal()
    return result

@update_bp.route('/update_usergate_management_center_6')
@login_required
def update_usergate_management_center_6():
    result = product_updates.update_usergate_management_center_internal_6()
    return result

@update_bp.route('/update_usergate_ngfw_7')
@login_required
def update_usergate_ngfw_7():
    result = product_updates.update_usergate_ngfw_internal_7()
    return result

@update_bp.route('/update_usergate_management_center_7')
@login_required
def update_usergate_management_center_7():
    result = product_updates.update_usergate_management_center_internal_7()
    return result

@update_bp.route('/update_all_versions')
@login_required
def update_all_versions():
    msg_kaspersky = product_updates.update_kaspersky_internal()
    msg_ngfw_7 = product_updates.update_usergate_ngfw_internal_7()
    msg_management_7 = product_updates.update_usergate_management_center_internal_7()
    msg_ngfw_6 = product_updates.update_usergate_ngfw_internal_6()
    msg_management_6 = product_updates.update_usergate_management_center_internal_6()
    msg_securitycode = product_updates.update_securitycode_internal()
    flash(f"Kaspersky: {msg_kaspersky} | NGFW: {msg_ngfw_6}, {msg_ngfw_7} | Management Center: {msg_management_6}, {msg_management_7} | Security Code: {msg_securitycode}", "success")
    return redirect(url_for('dashboard.dashboard'))
