from PIL import Image, ImageDraw, ImageFilter

def create_bubble_icon(size=256):
    # Dark background
    img = Image.new('RGBA', (size, size), (6, 8, 12, 255))
    draw = ImageDraw.Draw(img)

    # Calculate bubble center and radius
    center = (size // 2, size // 2)
    radius = int(size * 0.35)

    bbox = [
        center[0] - radius, center[1] - radius,
        center[0] + radius, center[1] + radius
    ]

    # Outer Glow (Cyan)
    glow_radius = int(size * 0.45)
    glow_bbox = [
        center[0] - glow_radius, center[1] - glow_radius,
        center[0] + glow_radius, center[1] + glow_radius
    ]

    # Create a separate layer for the glow
    glow_layer = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.ellipse(glow_bbox, fill=(34, 211, 238, 60)) # Cyan glow
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(15))

    # Paste glow
    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)

    # Core Bubble (Cyan gradient approximation)
    draw.ellipse(bbox, fill=(34, 211, 238, 255), outline=(8, 145, 178, 255), width=2)

    # Specular Highlight
    hl_bbox = [
        center[0] - int(radius*0.6), center[1] - int(radius*0.8),
        center[0] + int(radius*0.2), center[1] - int(radius*0.2)
    ]
    draw.ellipse(hl_bbox, fill=(255, 255, 255, 140))

    return img

if __name__ == "__main__":
    img = create_bubble_icon(256)
    img.save("assets/icon.png")

    # Create ICO file with multiple sizes
    icon_sizes = [(16,16), (32, 32), (48, 48), (64,64), (128, 128), (256, 256)]
    img.save("assets/icon.ico", format="ICO", sizes=icon_sizes)
    print("Icon generated successfully at assets/icon.png and assets/icon.ico")
