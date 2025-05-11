from app import app, db, ProductPrice
from datetime import datetime

def migrate_database():
    with app.app_context():
        # 1. 备份现有价格数据
        old_prices = ProductPrice.query.all()
        price_data = []
        for price in old_prices:
            price_data.append({
                'name': price.name,
                'purchase_price': price.purchase_price,
                'sale_price': price.sale_price,
                'created_at': price.created_at,
                'updated_at': price.updated_at
            })
        
        # 2. 删除旧表
        db.drop_all()
        
        # 3. 创建新表
        db.create_all()
        
        # 4. 恢复价格数据，添加开始日期
        for price in price_data:
            new_price = ProductPrice(
                name=price['name'],
                purchase_price=price['purchase_price'],
                sale_price=price['sale_price'],
                start_date=datetime.now(),  # 设置当前时间为开始日期
                end_date=None,  # 设置为永久有效
                created_at=price['created_at'],
                updated_at=price['updated_at']
            )
            db.session.add(new_price)
        
        # 5. 提交更改
        db.session.commit()
        print("数据库迁移完成！")

if __name__ == '__main__':
    migrate_database() 