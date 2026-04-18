from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random
import os

def resize_with_aspect_ratio(img, target_size=(1280, 720)):
    target_w, target_h = target_size
    img_w, img_h = img.size
    scale = min(target_w / img_w, target_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 255))
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas

def create_local_gradient(text_w, text_h, target_color):
    buffer_h = int(text_h * 1.2)
    gradient = Image.new("RGBA", (text_w, buffer_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(gradient)
    tr, tg, tb = target_color

    for y in range(buffer_h):
        ratio = y / buffer_h
        r = int(255 * (1 - ratio) + tr * ratio)
        g = int(255 * (1 - ratio) + tg * ratio)
        b = int(255 * (1 - ratio) + tb * ratio)
        draw.line([(0, y), (text_w, y)], fill=(r, g, b, 255))
    return gradient

def generate_thumbnail(
    id,
    template_path="D:\\CODE\\Python\\Projects\\YTAuto\\assets\\logo_thumbnail.png",
    history_path="D:\\CODE\\Python\\Projects\\YTAuto\\assets\\last_color.txt",
    title_text="LOVE ROLLERCOASTER",
):
    # --- COLOR SELECTION ---
    colors = [
        (0, 210, 255),   # Cyan
        (255, 0, 127),   # Hot Pink
        (150, 0, 255),   # Purple
        (0, 255, 150),   # Mint
        (255, 100, 0),   # Orange
        (255, 230, 0)    # Yellow
    ]
    output_path= f"D:\\CODE\\Python\\Projects\\YTAuto\\data\\{id}_thumbnail.png"
    # Persistent color tracking
    last_color_str = ""
    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            last_color_str = f.read().strip()

    # Filter out the last used color
    available_colors = [c for c in colors if str(c) != last_color_str]
    selected_color = random.choice(available_colors)

    # Save current choice for next time
    with open(history_path, "w") as f:
        f.write(str(selected_color))
    
    base = Image.open(template_path).convert("RGBA")
    base = resize_with_aspect_ratio(base, (1280, 720))

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 160))
    base = Image.alpha_composite(base, overlay)

    draw = ImageDraw.Draw(base)
    font_path = "C:\\Windows\\Fonts\\BAUHS93.ttf"
    font = ImageFont.truetype(font_path, 130)

    # --- TEXT WRAPPING ---
    max_width = base.width * 0.85
    words = title_text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=font, anchor="lt")
        if (bbox[2] - bbox[0]) <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line: lines.append(current_line)

    # --- POSITIONING ---
    line_spacing = 30
    line_data = []
    total_text_height = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, anchor="lt")
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        line_data.append((line, w, h))
        total_text_height += h
    total_text_height += line_spacing * (len(lines) - 1)
    current_y = (base.height - total_text_height) // 2

    for line, w, h in line_data:
        x = (base.width - w) // 2

        # 1. --- BLURRED SHADOW ---
        shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shadow_draw.text((x + 6, current_y + 6), line, font=font, fill=(0, 0, 0, 220), anchor="lt")
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=10))
        base = Image.alpha_composite(base, shadow_layer)

        # 2. --- GLOW ---
        for radius, alpha in [(10, 200), (25, 130), (50, 70)]:
            glow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_layer)
            glow_draw.text((x, current_y), line, font=font, fill=(*selected_color, alpha), anchor="lt")
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=radius))
            base = Image.alpha_composite(base, glow_layer)

        # 3. --- BLACK STROKE ---
        stroke_mask = Image.new("L", base.size, 0)
        stroke_draw = ImageDraw.Draw(stroke_mask)
        stroke_draw.text((x, current_y), line, font=font, fill=255, stroke_width=4, anchor="lt")
        black_stroke = Image.new("RGBA", base.size, (0, 0, 0, 255))
        black_stroke.putalpha(stroke_mask)
        base = Image.alpha_composite(base, black_stroke)

        # 4. --- GRADIENT TEXT ---
        text_mask = Image.new("L", base.size, 0)
        mask_draw = ImageDraw.Draw(text_mask)
        mask_draw.text((x, current_y), line, font=font, fill=255, anchor="lt")

        line_grad_img = create_local_gradient(w, h, selected_color)
        full_grad_canvas = Image.new("RGBA", base.size, (0, 0, 0, 0))
        full_grad_canvas.paste(line_grad_img, (x, current_y))
        full_grad_canvas.putalpha(text_mask)
        base = Image.alpha_composite(base, full_grad_canvas)

        current_y += h + line_spacing

    base.save(output_path)
    print(f"Shadowed Gradient Thumbnail Saved: {output_path} (Color: {selected_color})")
    return output_path

if __name__ == "__main__":
    generate_thumbnail()