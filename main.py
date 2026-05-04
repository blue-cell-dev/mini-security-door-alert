from machine import Pin
import time
import select
import sys

# === Pin assignments (exact wiring) ===
TRIG_PIN = 5
ECHO_PIN = 18

BUZZER_PIN = 19          # active buzzer +
RED_LED_PIN = 4         # alarm LED
GREEN_LED_PIN = 2        # armed/ready LED

# Keypad: rows (outputs) and columns (inputs)
ROW_PINS = [13, 12, 14, 27]
COL_PINS = [26, 25, 33, 32]

# === Configurable settings ===
ARM_CODE = "2"          # keypad disarm code
DIST_THRESHOLD_CM = 30     # intrusion distance
TRIGGER_CONFIRMATIONS = 2  # number of close readings required
ALARM_BEEP_MS = 180
ALARM_PAUSE_MS = 180

# === State variables ===
armed = False
alarm_active = False
entered_code = ""
last_alert_ms = 0
alert_cooldown_ms = 3000   # at most one alert every 3 s

# === Hardware objects ===
trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)
buzzer = Pin(BUZZER_PIN, Pin.OUT)
red_led = Pin(RED_LED_PIN, Pin.OUT)
green_led = Pin(GREEN_LED_PIN, Pin.OUT)

rows = [Pin(p, Pin.OUT) for p in ROW_PINS]
cols = [Pin(p, Pin.IN, Pin.PULL_DOWN) for p in COL_PINS]

# Key layout 4x4:
#  1 2 3 A
#  4 5 6 B
#  7 8 9 C
#  * 0 # D
keys = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D']
]

# Serial poller for PC commands
poller = select.poll()
poller.register(sys.stdin, select.POLLIN)

def set_outputs():
    green_led.value(1 if armed and not alarm_active else 0)
    red_led.value(1 if alarm_active else 0)

def beep(times=1, on_ms=120, off_ms=120):
    for _ in range(times):
        buzzer.value(1)
        time.sleep_ms(on_ms)
        buzzer.value(0)
        time.sleep_ms(off_ms)

def send(msg: str):
    # send a line to host over serial
    print(msg)

def read_distance_cm():
    # Trigger pulse
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    timeout_us = 30000

    # Wait for echo to go HIGH
    start = time.ticks_us()
    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), start) > timeout_us:
            return None

    pulse_start = time.ticks_us()
    # Wait for echo to go LOW
    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), pulse_start) > timeout_us:
            return None

    pulse_end = time.ticks_us()
    pulse_duration = time.ticks_diff(pulse_end, pulse_start)
    distance = pulse_duration / 58.0   # standard HC-SR04 formula
    return distance

def scan_keypad():
    # drive each row HIGH one at a time, read columns
    for r in rows:
        r.value(0)

    for row_idx, row in enumerate(rows):
        row.value(1)
        for col_idx, col in enumerate(cols):
            if col.value():
                time.sleep_ms(25)
                if col.value():
                    # wait until released
                    while col.value():
                        time.sleep_ms(10)
                    row.value(0)
                    return keys[row_idx][col_idx]
        row.value(0)
    return None

def arm_system():
    global armed, alarm_active, entered_code
    armed = True
    alarm_active = False
    entered_code = ""
    set_outputs()
    beep(2, 80, 80)
    send("STATUS:ARMED")

def disarm_system(source="KEYPAD"):
    global armed, alarm_active, entered_code
    armed = False
    alarm_active = False
    entered_code = ""
    buzzer.value(0)
    set_outputs()
    beep(1, 300, 0)
    send("STATUS:DISARMED source={}".format(source))

def trigger_alarm(distance):
    global alarm_active, last_alert_ms
    now = time.ticks_ms()
    if time.ticks_diff(now, last_alert_ms) >= alert_cooldown_ms:
        send("ALERT:INTRUSION distance_cm={:.1f}".format(distance))
        last_alert_ms = now
    alarm_active = True
    set_outputs()

def process_serial():
    global entered_code
    if poller.poll(0):
        cmd = sys.stdin.readline().strip().upper()
        if cmd == "ARM":
            arm_system()
        elif cmd == "DISARM":
            disarm_system("SERIAL")
        elif cmd == "STATUS":
            send("STATE armed={} alarm_active={}".format(armed, alarm_active))
        elif cmd.startswith("CODE "):
            code = cmd[5:].strip()
            if code == ARM_CODE:
                disarm_system("SERIAL_CODE")
            else:
                send("CODE:INVALID")
        elif cmd == "CLEAR":
            entered_code = ""
            send("CODE:CLEARED")

def process_keypad():
    global entered_code
    key = scan_keypad()
    if not key:
        return

    send("KEY:{}".format(key))

    # A = arm system
    if key == "A":
        arm_system()
        return

    # * = clear code
    if key == "*":
        entered_code = ""
        send("CODE:CLEARED")
        return

    # # = submit code
    if key == "#":
        if entered_code == ARM_CODE:
            disarm_system("KEYPAD")
        else:
            send("CODE:INVALID")
            beep(3, 70, 70)
            entered_code = ""
        return

    # digits append to code
    if key.isdigit():
        if len(entered_code) < 8:
            entered_code += key
            send("CODE:LEN={}".format(len(entered_code)))

def run_alarm_pattern():
    buzzer.value(1)
    red_led.value(1)
    time.sleep_ms(ALARM_BEEP_MS)
    buzzer.value(0)
    red_led.value(0)
    time.sleep_ms(ALARM_PAUSE_MS)

def monitor_distance():
    if not armed:
        return

    hits = 0
    for _ in range(TRIGGER_CONFIRMATIONS):
        d = read_distance_cm()
        if d is not None and d < DIST_THRESHOLD_CM:
            hits += 1
        time.sleep_ms(60)

    if hits >= TRIGGER_CONFIRMATIONS:
        d = read_distance_cm()
        if d is None:
            d = -1
        trigger_alarm(d)

# === Main loop ===
send("BOOT:READY")
set_outputs()

while True:
    process_serial()
    process_keypad()

    if alarm_active and armed:
        run_alarm_pattern()
        process_serial()
        process_keypad()
    else:
        monitor_distance()
        time.sleep_ms(80)
        
