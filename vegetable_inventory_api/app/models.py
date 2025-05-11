from sqlalchemy import Column, Integer, String, Boolean, Date, Numeric, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship, declarative_base
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(32), unique=True, index=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    
    purchases = relationship('Purchase', back_populates='user')
    sales = relationship('Sale', back_populates='user')

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(32), unique=True, nullable=False)
    
    purchases = relationship('Purchase', back_populates='product')
    sales = relationship('Sale', back_populates='product')

class Purchase(Base):
    __tablename__ = 'purchases'
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    purchase_date = Column(Date, nullable=False)
    purchase_price = Column(Numeric(10,2), nullable=False)
    quantity = Column(Numeric(10,2), nullable=False)
    total_amount = Column(Numeric(10,2), nullable=False)
    
    product = relationship('Product', back_populates='purchases')
    user = relationship('User', back_populates='purchases')

class Sale(Base):
    __tablename__ = 'sales'
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    sale_date = Column(Date, nullable=False)
    sale_price = Column(Numeric(10,2), nullable=False)
    quantity = Column(Numeric(10,2), nullable=False)
    total_amount = Column(Numeric(10,2), nullable=False)
    profit = Column(Numeric(10,2), nullable=False)
    
    product = relationship('Product', back_populates='sales')
    user = relationship('User', back_populates='sales') 