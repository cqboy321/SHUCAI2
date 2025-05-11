from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, send_from_directory, make_response
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
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length
import sqlite3

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

# 检查模板目录是否存在
template_dir = os.path.join(current_dir, 'templates')
if os.path.exists(template_dir):
    logger.debug(f"Template directory exists: {template_dir}")
    logger.debug(f"Template files: {os.listdir(template_dir)}")
else:
    logger.error(f"Template directory does not exist: {template_dir}")

app = Flask(__name__, 
    template_folder=template_dir,
    static_folder=os.path.join(current_dir, 'static')
)

# 配置应用
app.config.from_object(Config)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///inventory.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 添加缓存配置
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1年

# 只有在非SQLite数据库时才添加连接池配置
if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
    app.config['SQLALCHEMY_POOL_SIZE'] = int(os.getenv('SQLALCHEMY_POOL_SIZE', 10))
    app.config['SQLALCHEMY_MAX_OVERFLOW'] = int(os.getenv('SQLALCHEMY_MAX_OVERFLOW', 20))
    app.config['SQLALCHEMY_POOL_TIMEOUT'] = int(os.getenv('SQLALCHEMY_POOL_TIMEOUT', 30))
    app.config['SQLALCHEMY_POOL_RECYCLE'] = int(os.getenv('SQLALCHEMY_POOL_RECYCLE', 1800))

# 初始化扩展
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
csrf = CSRFProtect(app)

# 定义表单类
class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(), Length(min=2, max=80)])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6, max=120)])
    submit = SubmitField('登录')

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
    
    # 安全设置日期时间值，防止格式不兼容问题
    def set_last_login(self, dt_value=None):
        if dt_value is None:
            dt_value = datetime.now()
        elif isinstance(dt_value, str):
            try:
                # 尝试解析可能的ISO格式日期
                if 'T' in dt_value:
                    dt_value = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
            except Exception as e:
                app.logger.error(f"解析日期时间失败: {e}")
                dt_value = datetime.now()
        self.last_login = dt_value

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
    
    # 安全设置日期时间值，防止格式不兼容问题
    def set_date_fields(self, field_name, dt_value):
        if dt_value is None:
            dt_value = datetime.now() if field_name != 'end_date' else None
        elif isinstance(dt_value, str):
            try:
                # 尝试解析可能的ISO格式日期
                if 'T' in dt_value:
                    dt_value = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
            except Exception as e:
                app.logger.error(f"解析日期时间失败: {e}")
                dt_value = datetime.now() if field_name != 'end_date' else None
        
        if field_name == 'start_date':
            self.start_date = dt_value
        elif field_name == 'end_date':
            self.end_date = dt_value
        elif field_name == 'created_at':
            self.created_at = dt_value
        elif field_name == 'updated_at':
            self.updated_at = dt_value

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    
    user = db.relationship('User', backref=db.backref('activities', lazy=True))

def log_activity(user_id, action, details=None):
    log = ActivityLog(user_id=user_id, action=action, details=details)
    # 确保创建时间格式正确
    if hasattr(log, 'created_at') and isinstance(log.created_at, str) and 'T' in log.created_at:
        try:
            log.created_at = datetime.fromisoformat(log.created_at.replace('Z', '+00:00'))
        except Exception as e:
            app.logger.error(f"解析活动日志创建时间失败: {e}")
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
    
    # 安全设置日期时间值，防止格式不兼容问题
    def set_date(self, dt_value=None):
        if dt_value is None:
            dt_value = datetime.now()
        elif isinstance(dt_value, str):
            try:
                # 尝试解析可能的ISO格式日期
                if 'T' in dt_value:
                    dt_value = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
            except Exception as e:
                app.logger.error(f"解析产品日期失败: {e}")
                dt_value = datetime.now()
        self.date = dt_value

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            user.set_last_login()  # 使用安全方法设置登录时间
            db.session.commit()
            login_user(user)
            log_activity(user.id, '用户登录')
            
            # 获取next参数用于重定向
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
            
        flash('用户名或密码错误', 'danger')
    
    # 添加响应头防止缓存
    response = make_response(render_template('login.html', form=form))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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
        try:
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
                        loss_quantity = quantity - actual_quantity  # 计算损耗数量
                        items_details.append(f"{vegetable}: 系统记录 {quantity}，实际盘点 {actual_quantity}，损耗 {loss_quantity}")
                    
                    if type == 'inventory_check':
                        product = Product(
                            name=vegetable,
                            type=type,
                            price=price,
                            quantity=quantity,
                            actual_quantity=actual_quantity,
                            loss_quantity=loss_quantity,
                            notes=notes
                        )
                        # 使用安全的日期设置方法
                        product.set_date(date)
                    else:
                        product = Product(
                            name=vegetable,
                            type=type,
                            price=price,
                            quantity=quantity,
                            notes=notes
                        )
                        # 使用安全的日期设置方法
                        product.set_date(date)
                    
                    db.session.add(product)
                    items_details.append(f"{vegetable}: {quantity} x {price}")
                except Exception as e:
                    flash(f'处理商品 {vegetable} 时出错: {str(e)}', 'danger')
                    return redirect(url_for('index'))
            
            if total_items == 0:
                flash('请至少添加一项商品', 'warning')
                return redirect(url_for('batch_operation', type=type))
            
            db.session.commit()
            
            action_type = {
                'purchase': '进货',
                'sale': '销售',
                'inventory_check': '盘点'
            }
            
            log_activity(current_user.id, action_type[type], '; '.join(items_details))
            flash(f'{action_type[type]}记录已添加', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'添加记录时发生错误: {str(e)}', 'danger')
            return redirect(url_for('index'))
    
    return render_template(f'batch_{type}.html')

@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_product(id):
    product = Product.query.get_or_404(id)
    
    if request.method == 'POST':
        # 保存原始数据用于活动日志
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
        # 使用安全的日期设置方法
        try:
            date_value = datetime.strptime(request.form['date'], '%Y-%m-%d')
            product.set_date(date_value)
        except ValueError as e:
            app.logger.error(f"日期格式错误: {e}")
            flash(f'日期格式错误: {e}', 'danger')
            return render_template('update_product.html', product=product)
        product.notes = request.form['notes']
        
        if product.type == 'inventory_check':
            product.actual_quantity = int(request.form['actual_quantity'])
            product.loss_quantity = product.quantity - product.actual_quantity
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
        
        # 添加密码长度验证
        if len(password) < 6:
            flash('密码长度必须至少为6个字符', 'danger')
            return render_template('add_user.html')
        
        if len(password) > 120:
            flash('密码长度不能超过120个字符', 'danger')
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
            password = request.form.get('password')
            # 添加密码长度验证
            if len(password) < 6:
                flash('密码长度必须至少为6个字符', 'danger')
                return render_template('edit_user.html', user=user)
            
            if len(password) > 120:
                flash('密码长度不能超过120个字符', 'danger')
                return render_template('edit_user.html', user=user)
                
            user.set_password(password)
        
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
    
    vegetables = ['空心菜', '水白菜', '水萝卜', '油麦菜', '菜心', '塔菜', '白萝卜', '快白菜', '小白菜', '大白菜']
    
    if request.method == 'POST':
        new_prices = {}
        start_date = None
        
        try:
            # 解析开始日期
            start_date_str = request.form.get('start_date')
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                # 设置为当天的开始时间
                start_date = datetime.combine(start_date.date(), datetime.min.time())
            else:
                start_date = datetime.combine(datetime.now().date(), datetime.min.time())
            
            # 收集所有输入的价格数据
            for vegetable in vegetables:
                price_str = request.form.get(f'price_{vegetable}')
                if price_str:
                    try:
                        price = float(price_str)
                        if price > 0:
                            new_prices[vegetable] = price
                    except ValueError:
                        flash(f'{vegetable} 的价格格式不正确', 'danger')
                        return redirect(url_for('admin_prices'))
            
            # 确保至少有一个价格被设置
            if not new_prices:
                flash('至少需要设置一个商品的价格', 'danger')
                return redirect(url_for('admin_prices'))
            
            # 生效开始日期的前一天结束现有价格
            update_count = 0
            for vegetable, new_price in new_prices.items():
                # 查找当前有效的价格记录
                current_price = ProductPrice.query.filter(
                    ProductPrice.name == vegetable,
                    (ProductPrice.end_date == None) | (ProductPrice.end_date >= start_date)
                ).order_by(ProductPrice.start_date.desc()).first()
                
                if current_price and current_price.sale_price == new_price and current_price.start_date <= start_date:
                    # 价格相同，不需要创建新记录
                    continue
                
                if current_price and current_price.end_date is None:
                    # 将当前有效价格设置结束日期
                    end_date = start_date - timedelta(seconds=1)
                    # 使用安全的日期设置方法
                    current_price.set_date_fields('end_date', end_date)
                
                # 创建新价格记录
                new_price_record = ProductPrice(
                    name=vegetable,
                    sale_price=new_price
                )
                # 使用安全的日期设置方法
                new_price_record.set_date_fields('start_date', start_date)
                
                db.session.add(new_price_record)
                update_count += 1
            
            db.session.commit()
            
            if update_count > 0:
                price_details = ", ".join([f"{v}: {p}" for v, p in new_prices.items()])
                log_activity(current_user.id, '更新商品价格', f"从 {start_date.strftime('%Y-%m-%d')} 开始 - {price_details}")
                flash(f'成功更新 {update_count} 个商品的价格', 'success')
            else:
                flash('没有价格需要更新', 'info')
            
            return redirect(url_for('admin_prices'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'更新价格时出错: {str(e)}', 'danger')
            return redirect(url_for('admin_prices'))
    
    # 获取当前价格
    current_prices = {}
    for vegetable in vegetables:
        price_record = ProductPrice.query.filter(
            ProductPrice.name == vegetable,
            (ProductPrice.end_date == None) | (ProductPrice.end_date > datetime.now())
        ).order_by(ProductPrice.start_date.desc()).first()
        
        if price_record:
            current_prices[vegetable] = {
                'price': price_record.sale_price,
                'start_date': price_record.start_date.strftime('%Y-%m-%d')
            }
        else:
            current_prices[vegetable] = {'price': 0, 'start_date': '未设置'}
    
    return render_template('edit_prices.html', vegetables=vegetables, current_prices=current_prices)

# 修改获取价格的函数
def get_current_price(vegetable_name):
    now = datetime.now()
    price = ProductPrice.query.filter(
        ProductPrice.name == vegetable_name,
        ProductPrice.start_date <= now,
        (ProductPrice.end_date == None) | (ProductPrice.end_date > now)
    ).order_by(ProductPrice.start_date.desc()).first()
    return price

@app.route('/admin/prices/import_excel', methods=['GET', 'POST'])
@login_required
def import_prices_excel():
    if not current_user.is_admin():
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('没有找到上传的文件', 'danger')
            return redirect(url_for('admin_prices'))
        
        file = request.files['file']
        if file.filename == '':
            flash('没有选择文件', 'danger')
            return redirect(url_for('admin_prices'))
        
        if not file.filename.endswith(('.xls', '.xlsx')):
            flash('请上传Excel文件 (.xls 或 .xlsx)', 'danger')
            return redirect(url_for('admin_prices'))
        
        try:
            # 读取Excel文件
            df = pd.read_excel(file)
            
            # 检查必要的列
            required_columns = ['商品名称', '销售价格', '生效日期']
            for col in required_columns:
                if col not in df.columns:
                    flash(f'Excel文件缺少必要的列: {col}', 'danger')
                    return redirect(url_for('admin_prices'))
            
            # 处理每一行数据
            success_count = 0
            error_messages = []
            now = datetime.now()
            
            for index, row in df.iterrows():
                try:
                    vegetable_name = str(row['商品名称']).strip()
                    sale_price = float(row['销售价格'])
                    
                    # 处理日期
                    if pd.isna(row['生效日期']):
                        start_date = now
                    else:
                        start_date_value = row['生效日期']
                        if isinstance(start_date_value, (datetime, pd.Timestamp)):
                            start_date = start_date_value.to_pydatetime() if hasattr(start_date_value, 'to_pydatetime') else start_date_value
                        elif isinstance(start_date_value, str):
                            try:
                                # 尝试解析各种格式的日期字符串
                                if '/' in start_date_value:
                                    start_date = datetime.strptime(start_date_value, '%Y/%m/%d')
                                elif '-' in start_date_value:
                                    start_date = datetime.strptime(start_date_value, '%Y-%m-%d')
                                elif 'T' in start_date_value:
                                    start_date = datetime.fromisoformat(start_date_value.replace('Z', '+00:00'))
                                else:
                                    # 尝试一些常见格式
                                    formats = ['%Y%m%d', '%d%m%Y', '%m%d%Y']
                                    for fmt in formats:
                                        try:
                                            start_date = datetime.strptime(start_date_value, fmt)
                                            break
                                        except ValueError:
                                            continue
                                    else:
                                        raise ValueError(f"无法解析日期格式: {start_date_value}")
                            except ValueError as e:
                                error_messages.append(f"行 {index+2}: {vegetable_name} - 日期格式错误: {str(e)}")
                                continue
                        else:
                            error_messages.append(f"行 {index+2}: {vegetable_name} - 无法识别的日期类型")
                            continue
                    
                    # 设置为当天的开始时间
                    start_date = datetime.combine(start_date.date(), datetime.min.time())
                    
                    # 处理结束日期，如果存在
                    end_date = None
                    if '结束日期' in df.columns and not pd.isna(row['结束日期']):
                        end_date_value = row['结束日期']
                        if isinstance(end_date_value, (datetime, pd.Timestamp)):
                            end_date = end_date_value.to_pydatetime() if hasattr(end_date_value, 'to_pydatetime') else end_date_value
                        elif isinstance(end_date_value, str):
                            try:
                                # 尝试解析各种格式的日期字符串
                                if '/' in end_date_value:
                                    end_date = datetime.strptime(end_date_value, '%Y/%m/%d')
                                elif '-' in end_date_value:
                                    end_date = datetime.strptime(end_date_value, '%Y-%m-%d')
                                elif 'T' in end_date_value:
                                    end_date = datetime.fromisoformat(end_date_value.replace('Z', '+00:00'))
                                else:
                                    # 尝试一些常见格式
                                    formats = ['%Y%m%d', '%d%m%Y', '%m%d%Y']
                                    for fmt in formats:
                                        try:
                                            end_date = datetime.strptime(end_date_value, fmt)
                                            break
                                        except ValueError:
                                            continue
                                    else:
                                        raise ValueError(f"无法解析结束日期格式: {end_date_value}")
                            except ValueError as e:
                                error_messages.append(f"行 {index+2}: {vegetable_name} - 结束日期格式错误: {str(e)}")
                                continue
                        
                        # 设置为当天的结束时间
                        end_date = datetime.combine(end_date.date(), datetime.max.time())
                    
                    # 查找当前有效的价格记录
                    current_price = ProductPrice.query.filter(
                        ProductPrice.name == vegetable_name,
                        (ProductPrice.end_date == None) | (ProductPrice.end_date > start_date)
                    ).order_by(ProductPrice.start_date.desc()).first()
                    
                    if current_price and current_price.sale_price == sale_price and current_price.start_date <= start_date:
                        # 价格相同，不需要创建新记录
                        continue
                    
                    if current_price and current_price.end_date is None:
                        # 将当前有效价格设置结束日期
                        # 使用安全的日期设置方法
                        new_end_date = start_date - timedelta(seconds=1)
                        current_price.set_date_fields('end_date', new_end_date)
                    
                    # 创建新价格记录
                    new_price = ProductPrice(
                        name=vegetable_name,
                        sale_price=sale_price
                    )
                    # 使用安全的日期设置方法
                    new_price.set_date_fields('start_date', start_date)
                    if end_date:
                        new_price.set_date_fields('end_date', end_date)
                    
                    db.session.add(new_price)
                    success_count += 1
                
                except Exception as e:
                    error_messages.append(f"行 {index+2}: {vegetable_name if 'vegetable_name' in locals() else '未知'} - {str(e)}")
            
            if error_messages:
                # 如果有错误，回滚事务
                db.session.rollback()
                for msg in error_messages:
                    flash(msg, 'danger')
                return redirect(url_for('admin_prices'))
            
            # 提交事务
            db.session.commit()
            
            log_activity(current_user.id, '导入价格Excel', f"成功导入 {success_count} 条价格记录")
            flash(f'成功导入 {success_count} 条价格记录', 'success')
            return redirect(url_for('admin_prices'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'导入Excel时出错: {str(e)}', 'danger')
            return redirect(url_for('admin_prices'))
    
    return render_template('import_prices.html')

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
                # 损耗数量计算修改：系统记录-实际数量，可以为负数（表示有额外增加）
                loss_quantity = system_quantity - actual_quantity
                
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

@app.route('/tencent5199302822537009200.txt')
def tencent_verify():
    return 'tencent5199302822537009200'

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/admin/backup', methods=['GET', 'POST'])
@login_required
def admin_backup():
    if not current_user.is_admin():
        flash('您没有权限访问此页面', 'danger')
        return redirect(url_for('index'))
    
    # 获取备份文件列表
    backup_files = []
    excel_backups = []
    sql_backups = []
    
    # 查找Excel备份文件
    for file in os.listdir('.'):
        if file.startswith('data_backup_') and file.endswith('.xlsx'):
            file_path = os.path.join('.', file)
            file_size = os.path.getsize(file_path) / 1024  # KB
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            excel_backups.append({
                'name': file,
                'path': file_path,
                'size': f"{file_size:.2f} KB",
                'type': 'Excel备份',
                'time': file_time
            })
    
    # 查找SQL备份文件
    for file in os.listdir('.'):
        if file.startswith('sql_backup_') and file.endswith('.sql'):
            file_path = os.path.join('.', file)
            file_size = os.path.getsize(file_path) / 1024  # KB
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            sql_backups.append({
                'name': file,
                'path': file_path,
                'size': f"{file_size:.2f} KB",
                'type': 'SQL脚本备份',
                'time': file_time
            })
    
    # 查找SQLite备份文件
    for file in os.listdir('.'):
        if file.startswith('db_backup_') and file.endswith('.sqlite'):
            file_path = os.path.join('.', file)
            file_size = os.path.getsize(file_path) / 1024  # KB
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            backup_files.append({
                'name': file,
                'path': file_path,
                'size': f"{file_size:.2f} KB",
                'type': 'SQLite数据库',
                'time': file_time
            })
    
    # 合并并按时间排序
    all_backups = excel_backups + sql_backups + backup_files
    all_backups.sort(key=lambda x: x['time'], reverse=True)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_backup':
            try:
                # 生成SQL备份
                from render_backup import backup_to_sql, export_to_excel
                
                backup_success = False
                if backup_to_sql():
                    flash('SQL备份创建成功！', 'success')
                    backup_success = True
                
                if export_to_excel():
                    flash('Excel备份创建成功！', 'success')
                    backup_success = True
                
                if not backup_success:
                    flash('备份创建失败，请查看日志', 'danger')
                
                # 重定向以刷新文件列表
                return redirect(url_for('admin_backup'))
            
            except Exception as e:
                flash(f'备份创建失败: {str(e)}', 'danger')
                return redirect(url_for('admin_backup'))
        
        elif action == 'backup_sqlite':
            try:
                # 创建SQLite数据库的完整备份
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                db_path = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
                if db_path.startswith('sqlite:///'):
                    db_path = db_path[10:]  # 移除 'sqlite:///'
                
                backup_filename = f"db_backup_{timestamp}.sqlite"
                
                # 使用SQLite的备份功能
                conn = sqlite3.connect(db_path)
                backup_conn = sqlite3.connect(backup_filename)
                conn.backup(backup_conn)
                backup_conn.close()
                conn.close()
                
                log_activity(current_user.id, '创建数据库备份', f'创建了SQLite备份: {backup_filename}')
                flash('数据库备份创建成功！', 'success')
                return redirect(url_for('admin_backup'))
            
            except Exception as e:
                flash(f'数据库备份创建失败: {str(e)}', 'danger')
                return redirect(url_for('admin_backup'))

        elif action == 'restore_sqlite':
            backup_file = request.form.get('backup_file')
            if not backup_file:
                flash('未选择备份文件', 'danger')
                return redirect(url_for('admin_backup'))
                
            if not os.path.exists(backup_file) or not backup_file.startswith('db_backup_') or not backup_file.endswith('.sqlite'):
                flash('无效的备份文件', 'danger')
                return redirect(url_for('admin_backup'))
                
            try:
                # 恢复SQLite数据库备份
                db_path = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
                if db_path.startswith('sqlite:///'):
                    db_path = db_path[10:]  # 移除 'sqlite:///'
                
                # 确保数据库连接已关闭
                db.session.remove()
                
                # 创建当前数据库的备份，以防恢复失败
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                auto_backup_filename = f"auto_backup_before_restore_{timestamp}.sqlite"
                current_conn = sqlite3.connect(db_path)
                auto_backup_conn = sqlite3.connect(auto_backup_filename)
                current_conn.backup(auto_backup_conn)
                auto_backup_conn.close()
                current_conn.close()
                
                # 恢复备份
                backup_conn = sqlite3.connect(backup_file)
                restored_conn = sqlite3.connect(db_path)
                backup_conn.backup(restored_conn)
                restored_conn.close()
                backup_conn.close()
                
                log_activity(current_user.id, '恢复数据库备份', f'从文件 {backup_file} 恢复了数据库')
                flash('数据库恢复成功！应用程序将重新启动以应用更改。', 'success')
                
                # 这里应该有一个机制来重启应用，但在本地开发环境中，我们只能请求用户手动重启
                # 如果在Render上，可以在这里触发重启API
                
                return redirect(url_for('admin_backup'))
            
            except Exception as e:
                flash(f'数据库恢复失败: {str(e)}', 'danger')
                return redirect(url_for('admin_backup'))
                
        elif action == 'restore_sql':
            backup_file = request.form.get('backup_file')
            if not backup_file:
                flash('未选择备份文件', 'danger')
                return redirect(url_for('admin_backup'))
                
            if not os.path.exists(backup_file) or not backup_file.startswith('sql_backup_') or not backup_file.endswith('.sql'):
                flash('无效的备份文件', 'danger')
                return redirect(url_for('admin_backup'))
                
            try:
                # 执行SQL脚本恢复
                db_path = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
                if db_path.startswith('sqlite:///'):
                    db_path = db_path[10:]  # 移除 'sqlite:///'
                
                # 确保数据库连接已关闭
                db.session.remove()
                
                # 创建当前数据库的备份，以防恢复失败
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                auto_backup_filename = f"auto_backup_before_restore_{timestamp}.sqlite"
                current_conn = sqlite3.connect(db_path)
                auto_backup_conn = sqlite3.connect(auto_backup_filename)
                current_conn.backup(auto_backup_conn)
                auto_backup_conn.close()
                
                # 读取SQL脚本
                with open(backup_file, 'r', encoding='utf-8') as sql_file:
                    sql_script = sql_file.read()
                
                # 执行恢复操作
                cursor = current_conn.cursor()
                
                # 备份已有的表数据
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                tables = cursor.fetchall()
                
                # 创建表的备份
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"CREATE TABLE IF NOT EXISTS backup_{table_name} AS SELECT * FROM {table_name};")
                
                # 删除已有数据
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"DELETE FROM {table_name};")
                
                # 执行SQL脚本
                # 按照语句分割执行
                sql_statements = sql_script.split(';')
                for statement in sql_statements:
                    if statement.strip():
                        try:
                            cursor.execute(statement)
                        except Exception as e:
                            # 如果某条语句执行失败，记录但继续执行
                            print(f"Error executing SQL: {statement}")
                            print(f"Error message: {str(e)}")
                
                current_conn.commit()
                current_conn.close()
                
                log_activity(current_user.id, '恢复SQL备份', f'从文件 {backup_file} 恢复了数据库')
                flash('数据库通过SQL脚本恢复成功！', 'success')
                return redirect(url_for('admin_backup'))
            
            except Exception as e:
                flash(f'SQL恢复失败: {str(e)}', 'danger')
                return redirect(url_for('admin_backup'))

        # 处理上传的SQLite文件恢复
        elif action == 'upload_restore_sqlite':
            if 'backup_file' not in request.files:
                flash('未选择备份文件', 'danger')
                return redirect(url_for('admin_backup'))
                
            uploaded_file = request.files['backup_file']
            if uploaded_file.filename == '':
                flash('未选择备份文件', 'danger')
                return redirect(url_for('admin_backup'))
                
            # 检查文件格式
            if not (uploaded_file.filename.endswith('.sqlite') or 
                    uploaded_file.filename.endswith('.db') or 
                    uploaded_file.filename.endswith('.sqlite3')):
                flash('无效的SQLite备份文件格式', 'danger')
                return redirect(url_for('admin_backup'))
                
            try:
                # 保存上传的文件
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                upload_filename = f"uploaded_db_backup_{timestamp}.sqlite"
                uploaded_file.save(upload_filename)
                
                # 恢复数据库
                db_path = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
                if db_path.startswith('sqlite:///'):
                    db_path = db_path[10:]  # 移除 'sqlite:///'
                
                # 确保数据库连接已关闭
                db.session.remove()
                
                # 创建当前数据库的备份，以防恢复失败
                auto_backup_filename = f"auto_backup_before_restore_{timestamp}.sqlite"
                current_conn = sqlite3.connect(db_path)
                auto_backup_conn = sqlite3.connect(auto_backup_filename)
                current_conn.backup(auto_backup_conn)
                auto_backup_conn.close()
                current_conn.close()
                
                # 恢复备份
                backup_conn = sqlite3.connect(upload_filename)
                restored_conn = sqlite3.connect(db_path)
                backup_conn.backup(restored_conn)
                restored_conn.close()
                backup_conn.close()
                
                log_activity(current_user.id, '恢复上传的数据库备份', f'从上传的文件 {uploaded_file.filename} 恢复了数据库')
                flash('数据库恢复成功！应用程序将重新启动以应用更改。', 'success')
                
                return redirect(url_for('admin_backup'))
            
            except Exception as e:
                flash(f'数据库恢复失败: {str(e)}', 'danger')
                return redirect(url_for('admin_backup'))
                
        # 处理上传的SQL脚本恢复
        elif action == 'upload_restore_sql':
            if 'backup_file' not in request.files:
                flash('未选择备份文件', 'danger')
                return redirect(url_for('admin_backup'))
                
            uploaded_file = request.files['backup_file']
            if uploaded_file.filename == '':
                flash('未选择备份文件', 'danger')
                return redirect(url_for('admin_backup'))
                
            # 检查文件格式
            if not uploaded_file.filename.endswith('.sql'):
                flash('无效的SQL备份文件格式', 'danger')
                return redirect(url_for('admin_backup'))
                
            try:
                # 保存上传的文件
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                upload_filename = f"uploaded_sql_backup_{timestamp}.sql"
                uploaded_file.save(upload_filename)
                
                # 执行SQL脚本恢复
                db_path = os.environ.get('DATABASE_URL', 'sqlite:///inventory.db')
                if db_path.startswith('sqlite:///'):
                    db_path = db_path[10:]  # 移除 'sqlite:///'
                
                # 确保数据库连接已关闭
                db.session.remove()
                
                # 创建当前数据库的备份，以防恢复失败
                auto_backup_filename = f"auto_backup_before_restore_{timestamp}.sqlite"
                current_conn = sqlite3.connect(db_path)
                auto_backup_conn = sqlite3.connect(auto_backup_filename)
                current_conn.backup(auto_backup_conn)
                auto_backup_conn.close()
                
                # 读取SQL脚本
                with open(upload_filename, 'r', encoding='utf-8') as sql_file:
                    sql_script = sql_file.read()
                
                # 执行恢复操作
                cursor = current_conn.cursor()
                
                # 备份已有的表数据
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                tables = cursor.fetchall()
                
                # 创建表的备份
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"CREATE TABLE IF NOT EXISTS backup_{table_name} AS SELECT * FROM {table_name};")
                
                # 删除已有数据
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"DELETE FROM {table_name};")
                
                # 执行SQL脚本
                # 按照语句分割执行
                sql_statements = sql_script.split(';')
                for statement in sql_statements:
                    if statement.strip():
                        try:
                            cursor.execute(statement)
                        except Exception as e:
                            # 如果某条语句执行失败，记录但继续执行
                            print(f"Error executing SQL: {statement}")
                            print(f"Error message: {str(e)}")
                
                current_conn.commit()
                current_conn.close()
                
                log_activity(current_user.id, '恢复上传的SQL备份', f'从上传的文件 {uploaded_file.filename} 恢复了数据库')
                flash('数据库通过上传的SQL脚本恢复成功！', 'success')
                return redirect(url_for('admin_backup'))
            
            except Exception as e:
                flash(f'SQL恢复失败: {str(e)}', 'danger')
                return redirect(url_for('admin_backup'))
    
    return render_template('admin_backup.html', backups=all_backups)

@app.route('/admin/backup/download/<filename>')
@login_required
def download_backup(filename):
    if not current_user.is_admin():
        flash('您没有权限访问此资源', 'danger')
        return redirect(url_for('index'))
    
    # 安全检查，确保只能下载备份文件
    if (filename.startswith('db_backup_') and filename.endswith('.sqlite')) or \
       (filename.startswith('data_backup_') and filename.endswith('.xlsx')) or \
       (filename.startswith('sql_backup_') and filename.endswith('.sql')):
        
        if os.path.exists(filename):
            log_activity(current_user.id, '下载备份', f'下载了备份文件: {filename}')
            return send_file(filename, as_attachment=True)
        else:
            flash('备份文件不存在', 'danger')
            return redirect(url_for('admin_backup'))
    else:
        flash('无效的备份文件名', 'danger')
        return redirect(url_for('admin_backup'))

@app.route('/admin/backup/delete/<filename>')
@login_required
def delete_backup(filename):
    if not current_user.is_admin():
        flash('您没有权限执行此操作', 'danger')
        return redirect(url_for('index'))
    
    # 安全检查，确保只能删除备份文件
    if (filename.startswith('db_backup_') and filename.endswith('.sqlite')) or \
       (filename.startswith('data_backup_') and filename.endswith('.xlsx')) or \
       (filename.startswith('sql_backup_') and filename.endswith('.sql')):
        
        if os.path.exists(filename):
            try:
                os.remove(filename)
                log_activity(current_user.id, '删除备份', f'删除了备份文件: {filename}')
                flash('备份文件已删除', 'success')
            except Exception as e:
                flash(f'删除备份文件失败: {str(e)}', 'danger')
        else:
            flash('备份文件不存在', 'danger')
    else:
        flash('无效的备份文件名', 'danger')
    
    return redirect(url_for('admin_backup'))

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