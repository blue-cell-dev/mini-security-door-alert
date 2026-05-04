import serial
from datetime import datetime
import threading
import webbrowser

PORT = "COM4"          # change to your ESP32 port
BAUD = 115200
LOG_FILE = "security_log.txt"

ser = serial.Serial(PORT, BAUD, timeout=1)

def log_line(text):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {text}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def reader():
    while True:
        try:
            line = ser.readline().decode(errors="ignore").strip()
            if line:
                log_line(line)
                if line.startswith("ALERT:"):
                    try:
                        webbrowser.open("https://www.google.com", new=0)
                    except:
                        pass
        except Exception as e:
            log_line(f"ERROR reading serial: {e}")

def writer():
    print("Commands: ARM, DISARM, STATUS, CODE 2580, CLEAR, QUIT")
    while True:
        cmd = input("> ").strip()
        if not cmd:
            continue
        if cmd.upper() == "QUIT":
            break
        ser.write((cmd + "\n").encode())
    ser.close()

threading.Thread(target=reader, daemon=True).start()
writer()