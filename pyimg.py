from PIL import Image, ImageTk
import struct
import tkinter as tk
import sys
import os
import io
import zlib
import numpy as np
import threading
import time

def animateLoading(text):
    def anim():
        spinnerChars = ["|", "/", "—", "\\"]
        while waiting:
            for char in spinnerChars:
                if not waiting:
                    break
                sys.stdout.write("\b" + char)
                sys.stdout.flush()
                time.sleep(0.65)

    global waiting
    waiting = True
    sys.stdout.write(text)
    threading.Thread(target=anim).start()

def stopLoading():
    global waiting
    waiting = False
    sys.stdout.write("\b \n")
    sys.stdout.flush()

def image_to_rgb(image_path):
    """Extract RGB values from an image."""
    with Image.open(image_path) as img:
        img = img.convert('RGB')
        width, height = img.size

        rgb_values = [img.getpixel((x, y)) for y in range(height) for x in range(width)]

    return rgb_values, width, height

def read_rgb_values(file_path):
    """Read RGB values and dimensions from a compressed binary file."""
    with open(file_path, "rb") as f:
        compressed_data = f.read()
        rgb_data = zlib.decompress(compressed_data)
        
        header = rgb_data[:8]
        width, height = struct.unpack('II', header)
        
        filtered_rgb_data = rgb_data[8:]
        unfiltered_rgb_data = undo_paeth_filter(filtered_rgb_data, width, height)
        
        rgb_array = np.frombuffer(unfiltered_rgb_data, dtype=np.uint8).reshape((height, width, 3))

    return rgb_array, width, height

def create_image(rgb_array):
    """Create an image from RGB array."""
    img = Image.fromarray(rgb_array, 'RGB')
    image_bytes = io.BytesIO()
    img.save(image_bytes, format='PNG', optimize=True, compress_level=9)
    image_bytes.seek(0)
    return image_bytes

def preprocess_image(image_bytes, max_width=800, max_height=600):
    """Preprocess the image to resize it while maintaining aspect ratio."""
    with Image.open(image_bytes) as img:
        img.thumbnail((max_width, max_height), Image.LANCZOS)
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
    return img_bytes

def display_image(image_bytes, file_name):
    """Display the image in a tkinter window with preprocessing."""
    root = tk.Tk()
    
    preprocessed_image_bytes = preprocess_image(image_bytes)
    
    img = Image.open(preprocessed_image_bytes)
    img_tk = ImageTk.PhotoImage(img)

    label = tk.Label(root, image=img_tk)
    label.pack(padx=5, pady=5)

    margin = 10
    window_width = img_tk.width() + margin
    window_height = img_tk.height() + margin
    root.geometry(f"{window_width}x{window_height}")

    root.title(f"Decoded Image - {file_name}")
    root.attributes('-topmost', True)
    
    root.mainloop()

def paeth_predictor(a, b, c):
    """Paeth predictor function."""
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    elif pb <= pc:
        return b
    else:
        return c

def paeth_filter(data, width, height):
    """Apply Paeth filter to the image data."""
    filtered = bytearray()
    for y in range(height):
        for x in range(width):
            left = data[(y * width + x - 1) * 3:(y * width + x) * 3] if x > 0 else b'\x00\x00\x00'
            above = data[((y - 1) * width + x) * 3:((y - 1) * width + x + 1) * 3] if y > 0 else b'\x00\x00\x00'
            upper_left = data[((y - 1) * width + x - 1) * 3:((y - 1) * width + x) * 3] if x > 0 and y > 0 else b'\x00\x00\x00'
            pixel = data[(y * width + x) * 3:(y * width + x + 1) * 3]
            filtered += bytes((pixel[i] - paeth_predictor(left[i], above[i], upper_left[i])) % 256 for i in range(3))
    return filtered

def undo_paeth_filter(filtered_data, width, height):
    """Reverse the Paeth filter applied to the image data."""
    unfiltered = bytearray()
    for y in range(height):
        for x in range(width):
            left = unfiltered[(y * width + x - 1) * 3:(y * width + x) * 3] if x > 0 else b'\x00\x00\x00'
            above = unfiltered[((y - 1) * width + x) * 3:((y - 1) * width + x + 1) * 3] if y > 0 else b'\x00\x00\x00'
            upper_left = unfiltered[((y - 1) * width + x - 1) * 3:((y - 1) * width + x) * 3] if x > 0 and y > 0 else b'\x00\x00\x00'
            pixel = filtered_data[(y * width + x) * 3:(y * width + x + 1) * 3]
            unfiltered += bytes((pixel[i] + paeth_predictor(left[i], above[i], upper_left[i])) % 256 for i in range(3))
    return unfiltered

def main():
    if len(sys.argv) != 3:
        print("Usage: pyimg.py <encode/fwrite/view> <path_to_file>")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    file_path = sys.argv[2]

    if not os.path.isfile(file_path):
        print("The specified file does not exist.")
        sys.exit(1)

    if command not in {"encode", "view", "fwrite"}:
        print("Usage: pyimg.py <encode/fwrite/view> <path_to_file>")
        sys.exit(1)
    
    if command in {"view", "fwrite"}:
        if os.path.splitext(file_path)[1] != ".pyimg":
            print("You must specify a .pyimg file.")
            sys.exit(1)
        animateLoading("\nPlease wait... ")
        rgb_array, width, height = read_rgb_values(file_path)
        image_bytes = create_image(rgb_array)
        file_name = os.path.basename(file_path)
        print("\n\nDone!")
        stopLoading()

    if command == "encode":
        animateLoading("\nPlease wait... ")
        rgb_values, width, height = image_to_rgb(file_path)
        rgb_bytes = struct.pack('II', width, height)
        rgb_bytes += b''.join(struct.pack('BBB', r, g, b) for r, g, b in rgb_values)

        filtered_rgb_bytes = paeth_filter(rgb_bytes[8:], width, height)
        rgb_bytes = rgb_bytes[:8] + filtered_rgb_bytes

        compressed_rgb_bytes = zlib.compress(rgb_bytes, level=9)

        output_path = os.path.splitext(file_path)[0] + ".pyimg"
        with open(output_path, "wb") as f:
            f.write(compressed_rgb_bytes)
        print("\n\nDone!")
        stopLoading()
    elif command == "view":
        display_image(image_bytes, file_name)
    elif command == "fwrite":
        output_file = os.path.splitext(file_path)[0] + ".png"
        with open(output_file, "wb") as f:
            f.write(image_bytes.read())

if __name__ == "__main__":
    main()
