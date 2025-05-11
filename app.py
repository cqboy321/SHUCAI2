from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import sys
import logging
import pandas as pd
from io import BytesIO
from config import Config
from dotenv import load_dotenv
from sqlalchemy import func
from functools import lru_cache
from flask_wtf.csrf import CSRFProtect, CSRFError

# 配置日志
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# 获取当前文件所在目录的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
logger.debug(f"Current directory: {current_dir}")
logger.debug(f"Template folder: {os.path.join(current_dir, 'templates')}")
logger.debug(f"Static folder: {os.path.join(current_dir, 'static')}")

app = Flask(__name__, 
    template_folder=os.path.join(current_dir, 'templates'),
    static_folder=os.path.join(current_dir, 'static')
)

# 配置应用
app.config.from_object(Config)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///inventory.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_POOL_SIZE'] = 10
app.config['SQLALCHEMY_MAX_OVERFLOW'] = 20
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 添加缓存配置
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1年

# 初始化扩展
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
csrf = CSRFProtect(app)

# 添加错误处理
@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal Server Error: {str(error)}")
    db.session.rollback()
    return render_template('error.html', error="服务器内部错误，请稍后重试"), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"Not Found Error: {str(error)}")
    return render_template('error.html', error="页面未找到"), 404

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    logger.error(f"CSRF Error: {str(e)}")
    flash('表单提交失败，请刷新页面重试', 'danger')
    return redirect(request.referrer or url_for('index'))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        print(f"Checking admin status for user {self.username}: role = {self.role}")
        return self.role == 'admin'

class ProductPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sale_price = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.now)
    end_date = db.Column(db.DateTime, nullable=True)  # 如果为null表示价格一直有效
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint('name', 'start_date', name='unique_price_period'),
    )

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    
    user = db.relationship('User', backref=db.backref('activities', lazy=True))

def log_activity(user_id, action, details=None):
    log = ActivityLog(user_id=user_id, action=action, details=details)
    db.session.add(log)
    db.session.commit()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False, index=True)  # 'purchase', 'sale', or 'inventory_check'
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    actual_quantity = db.Column(db.Integer, default=0)  # For inventory check records
    loss_quantity = db.Column(db.Integer, default=0)
    date = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            user.last_login = datetime.now()
            db.session.commit()
            login_user(user)
            log_activity(user.id, '用户登录')
            return redirect(url_for('index'))
        flash('用户名或密码错误', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('两次输入的密码不一致', 'danger')
            return render_template('register.html')
        
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功，请登录', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/batch/<type>', methods=['GET', 'POST'])
@login_required
def batch_operation(type):
    if type not in ['purchase', 'sale', 'inventory_check']:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        today = datetime.now().date()
        
        # 验证日期是否为今天
        if date.date() > today:
            flash('不能添加未来日期的记录！', 'danger')
            return redirect(url_for('index'))
            
        notes = request.form.get('notes', '')
        
        vegetables = ['空心菜', '水白菜', '水萝卜', '油麦菜', '菜心', '塔菜', '白萝卜', '快白菜', '小白菜', '大白菜']
        total_items = 0
        items_details = []
        
        for i, vegetable in enumerate(vegetables, 1):
            quantity_str = request.form.get(f'quantity_{vegetable}', '')
            if not quantity_str:  # 如果数量为空，跳过这个商品
                continue
                
            try:
                quantity = float(quantity_str)
                if quantity <= 0:  # 如果数量小于等于0，跳过这个商品
                    continue
                    
                total_items += 1
                
                if type == 'sale':
                    # 获取预设价格
                    price_record = ProductPrice.query.filter_by(name=vegetable).first()
                    if not price_record:
                        flash(f'商品 {vegetable} 没有设置价格，请联系管理员', 'danger')
                        return redirect(url_for('index'))
                    price = price_record.sale_price
                elif type == 'purchase':
                    price = float(request.form.get(f'price_{vegetable}', 0))
                    if price <= 0:
                        flash(f'商品 {vegetable} 的价格必须大于0', 'danger')
                        return redirect(url_for('index'))
                else:  # inventory_check
                    price = float(request.form.get(f'price_{vegetable}', 0))
                    actual_quantity = float(request.form.get(f'actual_quantity_{vegetable}', 0))
                    loss_quantity = max(0, quantity - actual_quantity)  # 计算损耗数量
                    items_details.append(f"{vegetable}: 系统记录 {quantity}，实际盘点 {actual_quantity}，损耗 {loss_quantity}")
                
                if type == 'inventory_check':
                    product = Product(
                        name=vegetable,
                        type=type,
                        price=price,
                        quantity=quantity,
                        actual_quantity=actual_quantity,
                        loss_quantity=loss_quantity,
                        date=date,
                        notes=notes
                    )
                else:
                    product = Product(
                        name=vegetable,
                        type=type,
                        price=price,
                        quantity=quantity,
                        date=date,
                        notes=notes
                    )
                db.session.add(product)
                
                if type != 'inventory_check':
                    items_details.append(f"{vegetable}: {quantity}")
                
            except ValueError:
                flash(f'商品 {vegetable} 的数量或价格格式不正确', 'danger')
                return redirect(url_for('index'))
        
        if total_items == 0:
            flash('请至少输入一个商品的数量', 'danger')
            return redirect(url_for('index'))
            
        try:
            db.session.commit()
            log_activity(current_user.id, f'批量{type}操作', f'添加了 {total_items} 个商品: {", ".join(items_details)}')
            flash('操作成功！', 'success')
        except Exception as e:
            db.session.rollback()
            flash('操作失败，请重试', 'danger')
            print(f"Error: {str(e)}")
        
        return redirect(url_for('index'))
    
    # GET 请求处理
    now = datetime.now()
    price_dict = {p.name: p for p in ProductPrice.query.all()}
    return render_template('batch_operation.html', type=type, now=now, price_dict=price_dict)

@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_product(id):
    product = Product.query.get_or_404(id)
    
    if request.method == 'POST':
        old_data = {
            'name': product.name,
            'type': product.type,
            'price': product.price,
            'quantity': product.quantity,
            'date': product.date.strftime('%Y-%m-%d'),
            'notes': product.notes
        }
        
        product.name = request.form['name']
        product.type = request.form['type']
        product.price = float(request.form['price'])
        product.quantity = int(request.form['quantity'])
        product.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        product.notes = request.form['notes']
        
        if product.type == 'inventory_check':
            product.actual_quantity = int(request.form['actual_quantity'])
            product.loss_quantity = max(0, product.quantity - product.actual_quantity)
        else:
            product.actual_quantity = 0
            product.loss_quantity = 0
        
        db.session.commit()
        
        # 记录修改的详细信息
        changes = []
        if old_data['name'] != product.name:
            changes.append(f"商品名称: {old_data['name']} -> {product.name}")
        if old_data['type'] != product.type:
            changes.append(f"类型: {old_data['type']} -> {product.type}")
        if old_data['price'] != product.price:
            changes.append(f"价格: {old_data['price']} -> {product.price}")
        if old_data['quantity'] != product.quantity:
            changes.append(f"数量: {old_data['quantity']} -> {product.quantity}")
        if old_data['date'] != product.date.strftime('%Y-%m-%d'):
            changes.append(f"日期: {old_data['date']} -> {product.date.strftime('%Y-%m-%d')}")
        if old_data['notes'] != product.notes:
            changes.append(f"备注: {old_data['notes']} -> {product.notes}")
        
        log_activity(current_user.id, '更新商品记录', '; '.join(changes))
        flash('记录已更新！', 'success')
        return redirect(url_for('index'))
    
    return render_template('update_product.html', product=product)

@lru_cache(maxsize=128)
def get_products_for_date(date_str):
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        selected_date = datetime.now()
    
    start_date = datetime.combine(selected_date, datetime.min.time())
    end_date = datetime.combine(selected_date, datetime.max.time())
    
    return Product.query.filter(
        Product.date >= start_date,
        Product.date <= end_date
    ).order_by(Product.date.desc()).all()

@app.route('/', methods=['GET'])
@login_required
def index():
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        selected_date = datetime.now()
    
    start_date = datetime.combine(selected_date, datetime.min.time())
    end_date = datetime.combine(selected_date, datetime.max.time())
    
    # 获取所有商品名称
    vegetables = ['空心菜', '水白菜', '水萝卜', '油麦菜', '菜心', '塔菜', '白萝卜', '快白菜', '小白菜', '大白菜']
    
    # 初始化库存数据
    inventory_data = {}
    for vegetable in vegetables:
        inventory_data[vegetable] = {
            'purchase_quantity': 0,
            'purchase_amount': 0,
            'sale_quantity': 0,
            'sale_amount': 0,
            'actual_quantity': 0,
            'loss_quantity': 0,
            'profit': 0,
            'current_stock': 0
        }
    
    # 获取当天的进货记录
    purchases = Product.query.filter(
        Product.date >= start_date,
        Product.date <= end_date,
        Product.type == 'purchase'
    ).all()
    
    # 获取当天的销售记录
    sales = Product.query.filter(
        Product.date >= start_date,
        Product.date <= end_date,
        Product.type == 'sale'
    ).all()
    
    # 获取当天的盘点记录
    inventory_checks = Product.query.filter(
        Product.date >= start_date,
        Product.date <= end_date,
        Product.type == 'inventory_check'
    ).all()
    
    # 获取历史库存数据（从最早记录到选定日期）
    historical_purchases = Product.query.filter(
        Product.date <= end_date,
        Product.type == 'purchase'
    ).all()
    
    historical_sales = Product.query.filter(
        Product.date <= end_date,
        Product.type == 'sale'
    ).all()
    
    # 计算历史库存
    for purchase in historical_purchases:
        if purchase.name in inventory_data:
            inventory_data[purchase.name]['current_stock'] += purchase.quantity
    
    for sale in historical_sales:
        if sale.name in inventory_data:
            inventory_data[sale.name]['current_stock'] -= sale.quantity
    
    # 统计当天的进货数据
    for purchase in purchases:
        if purchase.name in inventory_data:
            inventory_data[purchase.name]['purchase_quantity'] += purchase.quantity
            inventory_data[purchase.name]['purchase_amount'] += purchase.price * purchase.quantity
    
    # 统计当天的销售数据
    for sale in sales:
        if sale.name in inventory_data:
            inventory_data[sale.name]['sale_quantity'] += sale.quantity
            inventory_data[sale.name]['sale_amount'] += sale.price * sale.quantity
            # 计算利润（销售金额 - 进货金额）
            if inventory_data[sale.name]['purchase_quantity'] > 0:
                avg_purchase_price = inventory_data[sale.name]['purchase_amount'] / inventory_data[sale.name]['purchase_quantity']
                inventory_data[sale.name]['profit'] += (sale.price - avg_purchase_price) * sale.quantity
    
    # 统计当天的盘点数据
    for check in inventory_checks:
        if check.name in inventory_data:
            inventory_data[check.name]['actual_quantity'] = check.actual_quantity
            inventory_data[check.name]['loss_quantity'] = check.loss_quantity
            inventory_data[check.name]['current_stock'] = check.actual_quantity
    
    # 获取所有记录用于详细记录表格
    products = Product.query.filter(
        Product.date >= start_date,
        Product.date <= end_date
    ).order_by(Product.date.desc()).all()
    
    # 计算总金额
    total_purchase_value = sum(data['purchase_amount'] for data in inventory_data.values())
    total_sales_value = sum(data['sale_amount'] for data in inventory_data.values())
    
    return render_template('index.html',
                         date=selected_date,
                         products=products,
                         inventory_data=inventory_data,
                         total_purchase_value=total_purchase_value,
                         total_sales_value=total_sales_value)

@app.route('/delete/<int:id>', methods=['GET', 'POST'])
@login_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    product_info = f"商品: {product.name}, 类型: {product.type}, 数量: {product.quantity}, 日期: {product.date.strftime('%Y-%m-%d')}"
    db.session.delete(product)
    db.session.commit()
    log_activity(current_user.id, '删除商品记录', product_info)
    flash('记录已删除！', 'success')
    return redirect(url_for('index'))

@app.route('/export', methods=['GET'])
@login_required
def export_excel():
    today = datetime.now().date()
    start_date = datetime.combine(today, datetime.min.time())
    end_date = datetime.combine(today, datetime.max.time())
    
    products = Product.query.filter(
        Product.date >= start_date,
        Product.date <= end_date
    ).order_by(Product.type, Product.name).all()
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # 进货记录
        purchase_data = []
        for p in products:
            if p.type == 'purchase':
                purchase_data.append({
                    '商品名称': p.name,
                    '进货价格': p.price,
                    '数量': p.quantity,
                    '进货日期': p.date.strftime('%Y-%m-%d'),
                    '备注': p.notes
                })
        if purchase_data:
            pd.DataFrame(purchase_data).to_excel(writer, sheet_name='进货记录', index=False)
        
        # 销售记录
        sale_data = []
        for p in products:
            if p.type == 'sale':
                sale_data.append({
                    '商品名称': p.name,
                    '销售价格': p.price,
                    '数量': p.quantity,
                    '销售日期': p.date.strftime('%Y-%m-%d'),
                    '备注': p.notes
                })
        if sale_data:
            pd.DataFrame(sale_data).to_excel(writer, sheet_name='销售记录', index=False)
        
        # 盘点记录
        inventory_data = []
        for p in products:
            if p.type == 'inventory_check':
                inventory_data.append({
                    '商品名称': p.name,
                    '进货价格': p.price,
                    '盘点数量': p.quantity,
                    '实际数量': p.actual_quantity,
                    '亏损数量': p.loss_quantity,
                    '盘点日期': p.date.strftime('%Y-%m-%d'),
                    '备注': p.notes
                })
        if inventory_data:
            pd.DataFrame(inventory_data).to_excel(writer, sheet_name='盘点记录', index=False)
    
    output.seek(0)
    log_activity(current_user.id, '导出Excel', f'导出日期: {today.strftime("%Y-%m-%d")}')
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'库存记录_{today.strftime("%Y%m%d")}.xlsx'
    )

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if not current_user.check_password(current_password):
            flash('当前密码错误', 'danger')
            return render_template('change_password.html')
        
        if new_password != confirm_password:
            flash('两次输入的新密码不一致', 'danger')
            return render_template('change_password.html')
        
        current_user.set_password(new_password)
        db.session.commit()
        flash('密码修改成功', 'success')
        return redirect(url_for('index'))
    
    return render_template('change_password.html')

@app.route('/admin/users', methods=['GET'])
@login_required
def admin_users():
    if not current_user.is_admin():
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if not current_user.is_admin():
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
            return render_template('add_user.html')
        
        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        log_activity(current_user.id, f'添加用户: {username}')
        flash('用户添加成功', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('add_user.html')

@app.route('/admin/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if not current_user.is_admin():
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(id)
    
    if request.method == 'POST':
        user.username = request.form['username']
        user.role = request.form['role']
        
        if request.form.get('password'):
            user.set_password(request.form['password'])
        
        db.session.commit()
        log_activity(current_user.id, f'编辑用户: {user.username}')
        flash('用户更新成功', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('edit_user.html', user=user)

@app.route('/admin/users/delete/<int:id>', methods=['GET'])
@login_required
def delete_user(id):
    if not current_user.is_admin():
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('不能删除当前登录的用户', 'danger')
        return redirect(url_for('admin_users'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    log_activity(current_user.id, f'删除用户: {username}')
    flash('用户删除成功', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/activities', methods=['GET'])
@login_required
def admin_activities():
    if not current_user.is_admin():
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    # 获取搜索参数
    username = request.args.get('username', '')
    date_str = request.args.get('date', '')
    
    # 构建查询
    query = ActivityLog.query.join(User)
    
    if username:
        query = query.filter(User.username.like(f'%{username}%'))
    
    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            next_day = date + timedelta(days=1)
            query = query.filter(
                ActivityLog.created_at >= date,
                ActivityLog.created_at < next_day
            )
        except ValueError:
            pass
    
    # 按时间倒序排序
    activities = query.order_by(ActivityLog.created_at.desc()).all()
    return render_template('admin_activities.html', activities=activities)

@app.route('/inventory', methods=['GET'])
@login_required
def inventory():
    # 获取日期参数，默认为今天
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        selected_date = datetime.now()
    
    # 获取所有商品名称
    vegetables = ['空心菜', '水白菜', '水萝卜', '油麦菜', '菜心', '塔菜', '白萝卜', '快白菜', '小白菜', '大白菜']
    
    # 获取选定日期的所有记录
    start_date = datetime.combine(selected_date, datetime.min.time())
    end_date = datetime.combine(selected_date, datetime.max.time())
    
    # 获取当天的进货记录
    purchases = Product.query.filter(
        Product.date >= start_date,
        Product.date <= end_date,
        Product.type == 'purchase'
    ).all()
    
    # 获取当天的销售记录
    sales = Product.query.filter(
        Product.date >= start_date,
        Product.date <= end_date,
        Product.type == 'sale'
    ).all()
    
    # 获取当天的盘点记录
    inventory_checks = Product.query.filter(
        Product.date >= start_date,
        Product.date <= end_date,
        Product.type == 'inventory_check'
    ).all()
    
    # 计算每个商品的库存情况
    inventory_data = {}
    for vegetable in vegetables:
        inventory_data[vegetable] = {
            'purchase_quantity': 0,
            'purchase_amount': 0,
            'sale_quantity': 0,
            'sale_amount': 0,
            'actual_quantity': 0,
            'loss_quantity': 0,
            'profit': 0,
            'current_stock': 0
        }
    
    # 获取历史库存数据（从最早记录到选定日期）
    historical_purchases = Product.query.filter(
        Product.date <= end_date,
        Product.type == 'purchase'
    ).all()
    
    historical_sales = Product.query.filter(
        Product.date <= end_date,
        Product.type == 'sale'
    ).all()
    
    # 计算历史库存
    for purchase in historical_purchases:
        if purchase.name in inventory_data:
            inventory_data[purchase.name]['current_stock'] += purchase.quantity
    
    for sale in historical_sales:
        if sale.name in inventory_data:
            inventory_data[sale.name]['current_stock'] -= sale.quantity
    
    # 统计当天的进货数据
    for purchase in purchases:
        if purchase.name in inventory_data:
            inventory_data[purchase.name]['purchase_quantity'] += purchase.quantity
            inventory_data[purchase.name]['purchase_amount'] += purchase.price * purchase.quantity
    
    # 统计当天的销售数据
    for sale in sales:
        if sale.name in inventory_data:
            inventory_data[sale.name]['sale_quantity'] += sale.quantity
            inventory_data[sale.name]['sale_amount'] += sale.price * sale.quantity
            # 计算利润（销售金额 - 进货金额）
            purchase_price = inventory_data[sale.name]['purchase_amount'] / inventory_data[sale.name]['purchase_quantity'] if inventory_data[sale.name]['purchase_quantity'] > 0 else 0
            inventory_data[sale.name]['profit'] += (sale.price - purchase_price) * sale.quantity
    
    # 统计当天的盘点数据
    for check in inventory_checks:
        if check.name in inventory_data:
            inventory_data[check.name]['actual_quantity'] = check.actual_quantity
            inventory_data[check.name]['loss_quantity'] = check.loss_quantity
            inventory_data[check.name]['current_stock'] = check.actual_quantity
    
    # 计算总金额
    total_purchase = sum(data['purchase_amount'] for data in inventory_data.values())
    total_sales = sum(data['sale_amount'] for data in inventory_data.values())
    total_profit = sum(data['profit'] for data in inventory_data.values())
    
    return render_template('inventory.html',
                         date=selected_date,
                         inventory_data=inventory_data,
                         total_purchase=total_purchase,
                         total_sales=total_sales,
                         total_profit=total_profit)

@app.route('/admin/prices', methods=['GET'])
@login_required
def admin_prices():
    if not current_user.is_admin():
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    # 获取当前有效的价格
    current_prices = ProductPrice.query.filter(
        (ProductPrice.end_date == None) | (ProductPrice.end_date > datetime.now())
    ).order_by(ProductPrice.name, ProductPrice.start_date.desc()).all()
    
    # 获取所有历史价格
    historical_prices = ProductPrice.query.filter(
        ProductPrice.end_date <= datetime.now()
    ).order_by(ProductPrice.name, ProductPrice.start_date.desc()).all()
    
    return render_template('admin_prices.html', 
                         current_prices=current_prices,
                         historical_prices=historical_prices,
                         now=datetime.now())

@app.route('/admin/prices/edit', methods=['GET', 'POST'])
@login_required
def edit_prices():
    if not current_user.is_admin():
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        vegetables = ['空心菜', '水白菜', '水萝卜', '油麦菜', '菜心', '塔菜', '白萝卜', '快白菜', '小白菜', '大白菜']
        
        for vegetable in vegetables:
            sale_price = float(request.form.get(f'sale_price_{vegetable}', 0))
            start_date_str = request.form.get(f'start_date_{vegetable}')
            end_date_str = request.form.get(f'end_date_{vegetable}')
            
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else None
                
                # 检查是否有重叠的时间段
                existing_price = ProductPrice.query.filter(
                    ProductPrice.name == vegetable,
                    ProductPrice.start_date <= start_date,
                    (ProductPrice.end_date == None) | (ProductPrice.end_date >= start_date)
                ).first()
                
                if existing_price:
                    flash(f'商品 {vegetable} 在所选时间段内已有价格设置', 'danger')
                    return redirect(url_for('edit_prices'))
                
                price = ProductPrice(
                    name=vegetable,
                    sale_price=sale_price,
                    start_date=start_date,
                    end_date=end_date
                )
                db.session.add(price)
                
            except ValueError:
                flash(f'商品 {vegetable} 的日期格式不正确', 'danger')
                return redirect(url_for('edit_prices'))
        
        db.session.commit()
        log_activity(current_user.id, '更新销售价格')
        flash('价格更新成功', 'success')
        return redirect(url_for('admin_prices'))
    
    # GET请求处理
    current_prices = ProductPrice.query.filter(
        (ProductPrice.end_date == None) | (ProductPrice.end_date > datetime.now())
    ).order_by(ProductPrice.name, ProductPrice.start_date.desc()).all()
    
    price_dict = {price.name: price for price in current_prices}
    return render_template('edit_prices.html', price_dict=price_dict, now=datetime.now())

# 修改获取价格的函数
def get_current_price(vegetable_name):
    now = datetime.now()
    price = ProductPrice.query.filter(
        ProductPrice.name == vegetable_name,
        ProductPrice.start_date <= now,
        (ProductPrice.end_date == None) | (ProductPrice.end_date > now)
    ).order_by(ProductPrice.start_date.desc()).first()
    return price

@app.route('/batch/inventory_check', methods=['GET', 'POST'])
@login_required
def inventory_check():
    if request.method == 'POST':
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')
        notes = request.form.get('notes', '')
        
        # 获取所有蔬菜的当前库存和最近进货价格
        price_dict = {}
        for vegetable in ['空心菜', '水白菜', '水萝卜', '油麦菜', '菜心', '塔菜', '白萝卜', '快白菜', '小白菜', '大白菜']:
            # 获取当前库存
            current_stock = Product.query.filter_by(
                name=vegetable,
                type='purchase'
            ).with_entities(func.sum(Product.quantity)).scalar() or 0
            
            # 减去销售数量
            sold_quantity = Product.query.filter_by(
                name=vegetable,
                type='sale'
            ).with_entities(func.sum(Product.quantity)).scalar() or 0
            
            current_stock -= sold_quantity
            
            # 获取最近一次进货记录的价格
            latest_purchase = Product.query.filter_by(
                name=vegetable,
                type='purchase'
            ).order_by(Product.date.desc()).first()
            
            price_dict[vegetable] = type('PriceInfo', (), {
                'quantity': current_stock,
                'price': latest_purchase.price if latest_purchase else 0
            })
        
        # 处理每个蔬菜的盘点数据
        for vegetable in ['空心菜', '水白菜', '水萝卜', '油麦菜', '菜心', '塔菜', '白萝卜', '快白菜', '小白菜', '大白菜']:
            actual_quantity = request.form.get(f'actual_quantity_{vegetable}')
            system_quantity = request.form.get(f'quantity_{vegetable}')
            
            if actual_quantity:  # 只处理有实际数量的商品
                actual_quantity = float(actual_quantity)
                system_quantity = float(system_quantity) if system_quantity else 0
                loss_quantity = max(0, system_quantity - actual_quantity)
                
                # 创建盘点记录
                product = Product(
                    name=vegetable,
                    type='inventory_check',
                    price=price_dict[vegetable].price,
                    quantity=system_quantity,
                    actual_quantity=actual_quantity,
                    loss_quantity=loss_quantity,
                    date=date,
                    notes=notes
                )
                db.session.add(product)
        
        db.session.commit()
        flash('盘点完成！', 'success')
        return redirect(url_for('index'))
    
    # 获取所有蔬菜的当前库存和最近进货价格
    price_dict = {}
    for vegetable in ['空心菜', '水白菜', '水萝卜', '油麦菜', '菜心', '塔菜', '白萝卜', '快白菜', '小白菜', '大白菜']:
        # 获取当前库存
        current_stock = Product.query.filter_by(
            name=vegetable,
            type='purchase'
        ).with_entities(func.sum(Product.quantity)).scalar() or 0
        
        # 减去销售数量
        sold_quantity = Product.query.filter_by(
            name=vegetable,
            type='sale'
        ).with_entities(func.sum(Product.quantity)).scalar() or 0
        
        current_stock -= sold_quantity
        
        # 获取最近一次进货记录的价格
        latest_purchase = Product.query.filter_by(
            name=vegetable,
            type='purchase'
        ).order_by(Product.date.desc()).first()
        
        price_dict[vegetable] = type('PriceInfo', (), {
            'quantity': current_stock,
            'price': latest_purchase.price if latest_purchase else 0
        })
    
    return render_template('batch_operation.html', type='inventory_check', price_dict=price_dict, now=datetime.now())

if __name__ == '__main__':
    with app.app_context():
        # 备份用户数据
        users = User.query.all()
        user_data = []
        for user in users:
            user_data.append({
                'username': user.username,
                'password_hash': user.password_hash,
                'role': user.role,
                'last_login': user.last_login,
                'created_at': user.created_at
            })
        
        # 重新创建数据库
        db.drop_all()
        db.create_all()
        
        # 恢复用户数据
        for user in user_data:
            new_user = User(
                username=user['username'],
                password_hash=user['password_hash'],
                role=user['role'],
                last_login=user['last_login'],
                created_at=user['created_at']
            )
            db.session.add(new_user)
        
        # 如果没有用户数据，创建管理员账号
        if not user_data:
            admin = User(username='ADMIN', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            print('Admin account created successfully!')
        
        db.session.commit()
    app.run(host='0.0.0.0', port=5000, debug=True) 