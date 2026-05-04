import serial
from datetime import datetime
import threading
import webbrowser
from pathlib import Path

PORT = "COM4"          # change to ESP32 port
BAUD = 115200
# Log file is created in the same directory as this Python script.
LOG_FILE = Path(__file__).with_name("security_log.txt")

print("Log file path:", LOG_FILE)

# Open serial connection to the ESP32 with a 1-second timeout.
ser = serial.Serial(PORT, BAUD, timeout=1)

def log_line(text):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {text}"
    print(line)
     # Append to the log file, preserving previous entries.
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
# Initial marker that the host-side logger has started running.
log_line("Host logger started")

def reader():
    while True:
        try:
            # Read a line from serial, ignore any invalid bytes.
            line = ser.readline().decode(errors="ignore").strip()
            if line:
                log_line(line)
                # Trigger browser action for alert messages from the ESP32.
                if line.startswith("ALERT:"):
                    try:
                        webbrowser.open("https://www.google.com", new=0)
                    except:
                        # Ignore browser errors so the reader keeps running.
                        pass
        except Exception as e:
            # Log any unexpected errors but keep the loop alive.
            log_line(f"ERROR reading serial: {e}")

def writer():
    print("Commands: ARM, DISARM, STATUS, CODE 2580, CLEAR, QUIT")
    while True:
        # Get a command from the keyboard.
        cmd = input("> ").strip()
        if not cmd:
            # Ignore empty lines.
            continue
        if cmd.upper() == "QUIT":
            # Exit the loop and close the serial connection
            break
         # Send the command plus newline to the ESP32.
        ser.write((cmd + "\n").encode())
        # Clean up the serial port when done.
    ser.close()

# Start the reader in a daemon thread so it runs in the background
# and automatically exits when the main program exits.
threading.Thread(target=reader, daemon=True).start()
# Run the writer loop in the main thread to handle user input
writer()
