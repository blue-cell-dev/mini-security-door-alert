from machine import Pin
import time
import select
import sys

# === Pin assignments (exact wiring) ===
TRIG_PIN = 5              # HC-SR04 trigger pin
ECHO_PIN = 18             # HC-SR04 echo pin

BUZZER_PIN = 19           # Active buzzer (positive pin)
RED_LED_PIN = 4           # Alarm indicator LED
GREEN_LED_PIN = 2         # Armed/ready status LED

# Keypad: rows (outputs) and columns (inputs)
ROW_PINS = [13, 12, 14, 27]   # Drive these high one at a time
COL_PINS = [26, 25, 33, 32]   # Read these to detect which key is pressed

# === Configurable settings ===
ARM_CODE = "2"                 # Disarm code (can be multiple digits)
DIST_THRESHOLD_CM = 30         # Distance below this counts as intrusion
TRIGGER_CONFIRMATIONS = 2      # Number of consecutive close readings needed
ALARM_BEEP_MS = 180            # Alarm ON duration
ALARM_PAUSE_MS = 180           # Alarm OFF duration between beeps

# === State variables ===
armed = False                  # System is armed or disarmed
alarm_active = False           # Alarm currently sounding or latched
entered_code = ""              # Code typed on keypad so far
last_alert_ms = 0              # Last time an alert was sent over serial
alert_cooldown_ms = 3000       # Minimum time between ALERT messages (ms)

# === Hardware objects ===
trig = Pin(TRIG_PIN, Pin.OUT)
echo = Pin(ECHO_PIN, Pin.IN)
buzzer = Pin(BUZZER_PIN, Pin.OUT)
red_led = Pin(RED_LED_PIN, Pin.OUT)
green_led = Pin(GREEN_LED_PIN, Pin.OUT)

# Set up keypad rows as outputs and columns as inputs with pull-downs.
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

# Serial poller for PC commands coming from stdin (USB serial).
poller = select.poll()
poller.register(sys.stdin, select.POLLIN)

def set_outputs():
    """
    Update LEDs based on current system state.

    - Green LED on when system is armed and not in alarm.
    - Red LED on when alarm is active.
    """
    green_led.value(1 if armed and not alarm_active else 0)
    red_led.value(1 if alarm_active else 0)

def beep(times=1, on_ms=120, off_ms=120):
    """
    Simple blocking beep pattern on the active buzzer.

    Used for feedback on arm/disarm and invalid code.
    """
    for _ in range(times):
        buzzer.value(1)
        time.sleep_ms(on_ms)
        buzzer.value(0)
        time.sleep_ms(off_ms)

def send(msg: str):
    """
    Send a status or event line to the host over serial.

    All host messages are single lines printed via the REPL/USB serial.
    """
    print(msg)

def read_distance_cm():
    """
    Measure distance using HC-SR04 ultrasonic sensor.

    Returns:
        float distance in cm, or None if timeout occurs.
    """
    # Trigger a short pulse on TRIG.
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)

    timeout_us = 30000  # ~30 ms timeout to avoid blocking forever

    # Wait for echo to go HIGH (start of pulse).
    start = time.ticks_us()
    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), start) > timeout_us:
            return None

    pulse_start = time.ticks_us()

    # Wait for echo to go LOW (end of pulse).
    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), pulse_start) > timeout_us:
            return None

    pulse_end = time.ticks_us()
    pulse_duration = time.ticks_diff(pulse_end, pulse_start)

    # Convert pulse width to distance in cm (approximate HC-SR04 formula).
    distance = pulse_duration / 58.0
    return distance

def scan_keypad():
    """
    Scan the 4x4 matrix keypad.

    Drives each row HIGH in turn and checks all columns.
    Returns:
        Pressed key character, or None if no key is pressed.
    """
    # Set all rows low before scanning.
    for r in rows:
        r.value(0)

    # Activate each row one at a time.
    for row_idx, row in enumerate(rows):
        row.value(1)
        for col_idx, col in enumerate(cols):
            if col.value():
                # Debounce: ensure the key is still pressed.
                time.sleep_ms(25)
                if col.value():
                    # Wait until key is released to avoid repeats.
                    while col.value():
                        time.sleep_ms(10)
                    row.value(0)
                    return keys[row_idx][col_idx]
        row.value(0)
    return None

def arm_system():
    """
    Put the system into the armed state.

    Resets alarm state and code buffer, updates LEDs, and sends status.
    """
    global armed, alarm_active, entered_code
    armed = True
    alarm_active = False
    entered_code = ""
    set_outputs()
    beep(2, 80, 80)
    send("STATUS:ARMED")

def disarm_system(source="KEYPAD"):
    """
    Disarm the system and clear any active alarm.

    'source' identifies how disarm happened (KEYPAD, SERIAL, SERIAL_CODE).
    """
    global armed, alarm_active, entered_code
    armed = False
    alarm_active = False
    entered_code = ""
    buzzer.value(0)  # Ensure buzzer is off.
    set_outputs()
    beep(1, 300, 0)
    send("STATUS:DISARMED source={}".format(source))

def trigger_alarm(distance):
    """
    Trigger the alarm based on a detected intrusion.

    Sends an ALERT message to the host (rate-limited), latches alarm_active,
    and updates LEDs.
    """
    global alarm_active, last_alert_ms
    now = time.ticks_ms()

    # Only send ALERT message if cooldown has passed.
    if time.ticks_diff(now, last_alert_ms) >= alert_cooldown_ms:
        send("ALERT:INTRUSION distance_cm={:.1f}".format(distance))
        last_alert_ms = now

    alarm_active = True
    set_outputs()

def process_serial():
    """
    Handle commands coming from the host over serial (stdin).

    Supported commands:
      - ARM
      - DISARM
      - STATUS
      - CODE <digits>
      - CLEAR
    """
    global entered_code
    # Non-blocking poll; returns immediately.
    if poller.poll(0):
        cmd = sys.stdin.readline().strip().upper()

        if cmd == "ARM":
            arm_system()
        elif cmd == "DISARM":
            disarm_system("SERIAL")
        elif cmd == "STATUS":
            send("STATE armed={} alarm_active={}".format(armed, alarm_active))
        elif cmd.startswith("CODE "):
            # Use an external code from host instead of keypad.
            code = cmd[5:].strip()
            if code == ARM_CODE:
                disarm_system("SERIAL_CODE")
            else:
                send("CODE:INVALID")
        elif cmd == "CLEAR":
            entered_code = ""
            send("CODE:CLEARED")

def process_keypad():
    """
    Read and interpret keypad input.

    - 'A' arms the system.
    - '*' clears the entered code.
    - '#' submits the current code for validation.
    - Digits are appended to the disarm code buffer.
    """
    global entered_code
    key = scan_keypad()
    if not key:
        return

    send("KEY:{}".format(key))

    # A = arm system.
    if key == "A":
        arm_system()
        return

    # * = clear code buffer.
    if key == "*":
        entered_code = ""
        send("CODE:CLEARED")
        return

    # # = submit code.
    if key == "#":
        if entered_code == ARM_CODE:
            disarm_system("KEYPAD")
        else:
            send("CODE:INVALID")
            beep(3, 70, 70)
            entered_code = ""
        return

    # Digits append to code buffer (up to 8 digits).
    if key.isdigit():
        if len(entered_code) < 8:
            entered_code += key
            send("CODE:LEN={}".format(len(entered_code)))

def run_alarm_pattern():
    """
    Run one cycle of the active alarm pattern.

    Alternates buzzer and red LED on/off based on ALARM_BEEP_MS/ALARM_PAUSE_MS.
    """
    buzzer.value(1)
    red_led.value(1)
    time.sleep_ms(ALARM_BEEP_MS)
    buzzer.value(0)
    red_led.value(0)
    time.sleep_ms(ALARM_PAUSE_MS)

def monitor_distance():
    """
    Check ultrasonic distance and trigger alarm if intrusion is detected.

    Requires multiple consecutive readings below DIST_THRESHOLD_CM to reduce noise.
    """
    if not armed:
        return

    hits = 0
    # Take several readings to confirm intrusion.
    for _ in range(TRIGGER_CONFIRMATIONS):
        d = read_distance_cm()
        if d is not None and d < DIST_THRESHOLD_CM:
            hits += 1
        time.sleep_ms(60)

    # If enough close readings, trigger the alarm.
    if hits >= TRIGGER_CONFIRMATIONS:
        d = read_distance_cm()
        if d is None:
            d = -1  # -1 used to mark an unknown distance in the alert.
        trigger_alarm(d)

# === Main loop ===

send("BOOT:READY")   # Notify host that the system booted and is ready.
set_outputs()        # Initialize LED states.

while True:
    # Always check for serial commands and keypad input.
    process_serial()
    process_keypad()

    if alarm_active and armed:
        # When alarm is active, keep running the alarm pattern
        # but still allow serial/keypad to interact between cycles.
        run_alarm_pattern()
        process_serial()
        process_keypad()
    else:
        # Normal monitoring mode: check distance periodically.
        monitor_distance()
        time.sleep_ms(80)
