from flask import Blueprint, render_template, request, flash
from flask_login import login_required, current_user
from app import db

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.profession = request.form.get('profession')
        current_user.notify = (request.form.get('notify') == 'on')
        db.session.commit()
        flash('Настройки профиля обновлены.', 'success')
    return render_template('profile.html', user=current_user)
