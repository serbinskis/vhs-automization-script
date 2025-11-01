import time
import io
import sys
import base64
import collections
from PIL import Image, ImageEnhance, ImageFilter
from obsws_python import ReqClient
import cv2
import numpy as np
import easyocr
import warnings

# --- ADDED: Filter the specific UserWarning from PyTorch ---
warnings.filterwarnings("ignore", category=UserWarning, message=".*'pin_memory' argument is set as true*")

# --- Configuration ---
HOST = "localhost"
PORT = 4455
PASSWORD = "1234567890"        # Your OBS WebSocket password
SOURCE_NAME = "Video Capture Device"  # Must match your OBS source name
CHECK_INTERVAL = 0.1           # Seconds between OCR checks
CONFIRM_SECONDS = 0.1          # How many seconds the condition must be met.
BLACK_SCREEN_CONFIRM_SECONDS = 15.0

# --- Crop area (x=60→160, y=100→150) ---
CROP_BOX = (60, 100, 160, 150)  # (left, top, right, bottom)

# --- Window Size Configuration ---
WINDOW_SCALE_FACTOR = 2        # How many times to scale up the preview window.
WINDOW_SIZE = ((CROP_BOX[2] - CROP_BOX[0]) * WINDOW_SCALE_FACTOR, (CROP_BOX[3] - CROP_BOX[1]) * WINDOW_SCALE_FACTOR)

# --- Background Color Configuration ---
# A list of acceptable background colors in (B, G, R) format.
TARGET_COLORS_BGR = [
    (176, 43, 57),      # The original blue-ish color
    (121, 2, 23),       # The new dark-blue-ish color
    (200, 67, 78),
    (195, 99, 4),
    (0, 0, 0)
]
COLOR_TOLERANCE = 25

# --- Connect to OBS ---
client = ReqClient(host=HOST, port=PORT, password=PASSWORD)
print("Connected to OBS WebSocket.")

print("Loading OCR model...")
reader = easyocr.Reader(['en'], gpu=False)
print("OCR model loaded.")

black_screen_start_time = None
detection_start_time = None
frame_times = collections.deque(maxlen=30)

cv2.namedWindow("OCR Area", cv2.WINDOW_NORMAL)
cv2.resizeWindow("OCR Area", WINDOW_SIZE[0], WINDOW_SIZE[1])

def get_full_screenshot():
    """Grabs a full-resolution screenshot from OBS and returns it as a PIL Image."""
    # https://github.com/aatikturk/obsws-python/blob/f70583d7ca250c1f3a0df768d3cfd41663a6023b/obsws_python/reqs.py#L464
    response = client.get_source_screenshot(
        name=SOURCE_NAME,
        img_format="jpg",
        width=None,
        height=None,
        quality=-1
    )

    base64_string = response.image_data
    try: header, encoded_data = base64_string.split(",", 1)
    except ValueError: encoded_data = base64_string

    img_data = base64.b64decode(encoded_data)
    #return Image.open("C:/Users/User/Desktop/mpv-shot0001.jpg")
    return Image.open(io.BytesIO(img_data))

def preprocess(img):
    """Enhance contrast/sharpness for reliable OCR."""
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.5)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    return img.filter(ImageFilter.MedianFilter(size=3))

def contains_rew(img_np):
    """Detect 'REW' text via EasyOCR."""
    results = reader.readtext(img_np, detail=1)
    all_text = ", ".join([text for (bbox, text, prob) in results])
    return (all_text == "REW"), all_text

def is_correct_background(img_np_color, target_colors, tolerance):
    """Checks if the average color of the image is close to ANY of the target colors."""
    average_color = np.mean(img_np_color, axis=(0, 1))
    # Loop through each target color in the list
    for target in target_colors:
        diff = np.abs(average_color - target)
        # If we find a match, we can return True immediately.
        if np.all(diff < tolerance): return True, average_color
    # If the loop finishes without finding any matches, return False.
    return False, average_color

def is_black_screen(avg_color):
    """Checks if the average color is black (or very close to it)."""
    # Using a small threshold instead of == 0 is safer for floating point values
    return np.all(avg_color < 1)

while True:
    try:
        t0 = time.time()
        full_img_color = get_full_screenshot()
        full_cv_image_color = cv2.cvtColor(np.array(full_img_color), cv2.COLOR_RGB2BGR)

        background_color_match, avg_color = is_correct_background(full_cv_image_color, TARGET_COLORS_BGR, COLOR_TOLERANCE)
        is_black = is_black_screen(avg_color) # FOR PAUSE/RESUME LOGIC WITH IMMEDIATE RESUME ---
        status = client.get_record_status()

        cropped_img = full_img_color.crop(CROP_BOX)
        img_processed = preprocess(cropped_img)
        cv_image_processed = np.array(img_processed)
        text_is_present, all_text = contains_rew(cv_image_processed)
        
        cv2.imshow("OCR Area", cv_image_processed)
        cv2.waitKey(1)

        # --- Black Screen Logic (Pause after 5 seconds) ---
        if is_black:
            # If we just detected a black screen, start the timer.
            if black_screen_start_time is None:
                black_screen_start_time = time.time()
            # If the timer is running, check if 5 seconds have passed.
            else:
                if time.time() - black_screen_start_time >= BLACK_SCREEN_CONFIRM_SECONDS:
                    # If 5s have passed, pause the recording (if it's active and not already paused).
                    if status.output_active and not status.output_paused:
                        print(f"[{time.strftime('%H:%M:%S')}] *** Screen black for {BLACK_SCREEN_CONFIRM_SECONDS}s. PAUSING recording. ***")
                        client.pause_record()
                        # Reset the timer immediately after pausing to prevent spamming the command.
                        black_screen_start_time = None
        # --- Video Detected Logic (Resume Immediately) ---
        else:
            # If the screen is NOT black, reset the black screen timer.
            black_screen_start_time = None
            # And resume immediately if the recording is currently paused.
            if status.output_active and status.output_paused:
                print(f"[{time.strftime('%H:%M:%S')}] *** Video detected. RESUMING recording. ***")
                client.resume_record()
        # --- END MODIFIED LOGIC ---

        # --- Final Pause & Exit Logic (Unchanged from your version) ---
        if text_is_present and background_color_match:
            if detection_start_time is None:
                detection_start_time = time.time()
                print(f"[{time.strftime('%H:%M:%S')}] *** Final exit condition met. Starting {CONFIRM_SECONDS}s timer... ***")
            else:
                elapsed_time = time.time() - detection_start_time
                if elapsed_time >= CONFIRM_SECONDS:
                    print(f"\n[{time.strftime('%H:%M:%S')}] *** Exit condition held for {elapsed_time:.2f}s. Confirmed! ***")
                    status = client.get_record_status()
                    if status.output_active and not status.output_paused: client.pause_record()
                    if status.output_active and not status.output_paused: break
        else:
            if detection_start_time is not None:
                held_duration = time.time() - detection_start_time
                print(f"[{time.strftime('%H:%M:%S')}] *** Exit condition lost after being held for {held_duration:.2f}s. Resetting timer. ***")
                detection_start_time = None
        
        # --- Status Logging and Timing (Unchanged from your version) ---
        processing_time = time.time() - t0
        sleep_time = CHECK_INTERVAL - processing_time
        total_cycle_time = processing_time + sleep_time if sleep_time > 0 else processing_time
        frame_times.append(total_cycle_time)
        avg_fps = len(frame_times) / sum(frame_times) if frame_times else 0

        if not status.output_active: record_status_str = "Inactive"
        elif status.output_paused: record_status_str = "Paused"
        else: record_status_str = "Recording"

        status_text = (
            f"[{time.strftime('%H:%M:%S')}] "
            f"REC: {record_status_str:<9} | "
            f"Text: {str(text_is_present):<5} | "
            f"BG Match: {str(background_color_match):<5} | Avg Color: ({avg_color[0]:>3.0f}, {avg_color[1]:>3.0f}, {avg_color[2]:>3.0f}) | "
            f"Avg FPS: {avg_fps:<4.2f} | "
            f"OCR: ('{all_text}')"
        )
        print(status_text)
        if sleep_time > 0: time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\nStopped manually.")
        break
    except Exception as e:
        print(f"\nError: {e}")
        time.sleep(1)

# Clean up and close the OpenCV window
print("\n---")
input("Press ENTER in this console to exit...")
cv2.destroyAllWindows()
