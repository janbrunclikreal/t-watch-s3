# file: touch.py
import board
import time
import adafruit_focaltouch

class TouchController:
    def __init__(self):
        self.ft = None
        try:
            touch_i2c = board.TOUCH_I2C()
            self.ft = adafruit_focaltouch.Adafruit_FocalTouch(touch_i2c, address=0x38)
        except Exception as e:
            print(f"[TOUCH-INIT-ERR] {e}")

        self.start_x = 0
        self.start_y = 0
        self.last_x = 0
        self.last_y = 0
        self.touch_start_time = 0
        self.is_down = False

    def get_event(self):
        if not self.ft:
            return None

        now = time.monotonic()

        try:
            if self.ft.touched:
                touches = self.ft.touches
                if touches:
                    x = touches[0]['x']
                    y = touches[0]['y']

                    if not self.is_down:
                        self.is_down = True
                        self.start_x = x
                        self.start_y = y
                        self.touch_start_time = now
                    
                    self.last_x = x
                    self.last_y = y
                    return ("HOLD", x, y)
            else:
                if self.is_down:
                    self.is_down = False
                    duration = now - self.touch_start_time
                    dx = self.last_x - self.start_x
                    dy = self.last_y - self.start_y

                    # Detekce gest (posun o více než 40 px)
                    if dy > 40:
                        return ("SWIPE_DOWN", self.start_x, self.start_y)
                    elif dy < -40:
                        return ("SWIPE_UP", self.start_x, self.start_y)
                    elif duration < 0.6:
                        return ("TAP", self.start_x, self.start_y)

        except (ValueError, OSError, RuntimeError):
            pass

        return None