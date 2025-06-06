# 蔬菜批发进销存管理系统

这是一个用于管理蔬菜批发业务的进销存系统，可以跟踪产品的进货、销售和库存情况。

## 功能特点

- 产品信息管理（名称、价格、数量等）
- 进货管理（价格、数量、金额）
- 销售管理（价格、数量、金额）
- 利润计算
- 库存管理（数量、金额）
- 数据持久化存储

## 安装要求

- Python 3.7 或更高版本
- 依赖包：
  - ttkbootstrap
  - pillow

## 安装步骤

1. 克隆或下载本项目
2. 安装依赖包：
   ```
   pip install -r requirements.txt
   ```

## 使用方法

1. 运行主程序：
   ```
   python main.py
   ```

2. 在界面中输入产品信息：
   - 产品名称
   - 进货价
   - 进货数量
   - 销售价
   - 销售数量

3. 点击"添加/更新"按钮保存数据

4. 可以查看、编辑和删除已有记录

## 数据说明

- 系统会自动计算：
  - 进货金额 = 进货价 × 进货数量
  - 销售金额 = 销售价 × 销售数量
  - 利润 = 销售金额 - (进货价 × 销售数量)
  - 库存数量 = 进货数量 - 销售数量
  - 库存金额 = 库存数量 × 进货价