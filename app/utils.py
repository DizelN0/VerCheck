import datetime
from .models import UserProduct
from . import db

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
