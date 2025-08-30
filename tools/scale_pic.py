from PIL import Image

def resize_preserve_transparency(input_path, output_path, scale_factor):
    """
    等比缩放PNG图片并保持透明度
    
    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
        scale_factor: 缩放比例
    """
    # 打开图片并转换为RGBA模式(确保透明度信息)
    with Image.open(input_path).convert("RGBA") as img:
        original_width, original_height = img.size
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        
        # 缩放图片
        resized_img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # 保存为PNG格式(保持透明度)
        resized_img.save(output_path, "PNG", optimize=True)
        print(f"已处理透明图片: {original_width}x{original_height} -> {new_width}x{new_height}")

# 使用示例
resize_preserve_transparency("input.png", "output.png", 0.2)