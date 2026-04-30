from PIL import Image, ImageDraw

def generate_rgb_pointillist_mask(filename="pointillist_grid.png", size=2048, spacing=16, radius=4):
    # Create an RGB background (0, 0, 0 = black)
    img = Image.new('RGB', (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Generate a grid of white dots (255, 255, 255 = white)
    for x in range(0, size, spacing):
        for y in range(0, size, spacing):
            left_up = (x - radius, y - radius)
            right_down = (x + radius, y + radius)
            draw.ellipse([left_up, right_down], fill=(255, 255, 255))

    img.save(filename)
    print(f"Successfully generated RGB mask: {filename}")

if __name__ == "__main__":
    generate_rgb_pointillist_mask()