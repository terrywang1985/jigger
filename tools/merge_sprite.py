from PIL import Image

# 你的帧图列表
frames = ["frame1.png", "frame2.png", "frame3.png"]
images = [Image.open(f) for f in frames]

# 假设所有帧大小相同
w, h = images[0].size
sprite_sheet = Image.new("RGBA", (w * len(images), h))

# 横向拼接
for i, img in enumerate(images):
    sprite_sheet.paste(img, (i * w, 0))

sprite_sheet.save("sprite_sheet.png")