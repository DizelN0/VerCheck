from apscheduler.schedulers.background import BackgroundScheduler
from app.controllers import product_updates

def scheduled_update():
    product_updates.update_kaspersky_internal()
    product_updates.update_usergate_ngfw_internal_7()
    product_updates.update_usergate_management_center_internal_7()
    product_updates.update_usergate_ngfw_internal_6()
    product_updates.update_usergate_management_center_internal_6()
    product_updates.update_securitycode_internal()
    # Если нужно, можно добавить логирование или отправку уведомлений

scheduler = BackgroundScheduler()
# Запускаем задачу один раз в 24 часа:
scheduler.add_job(scheduled_update, 'interval', hours=24)
scheduler.start()