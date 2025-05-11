from PIL import Image, ImageDraw

# 创建一个 256x256 的图像
img = Image.new('RGBA', (256, 256), (255, 255, 255, 0))
draw = ImageDraw.Draw(img)

# 绘制一个绿色的圆形
draw.ellipse([20, 20, 236, 236], fill=(76, 175, 80, 255))

# 绘制一个白色的蔬菜图标
draw.rectangle([80, 60, 176, 196], fill=(255, 255, 255, 255))
draw.ellipse([60, 40, 196, 176], fill=(255, 255, 255, 255))

# 保存为 ICO 文件
img.save('vegetable.ico', format='ICO') 