# mini-security-door-alert
# Mini Security / Door Alert System

An ESP32 based security project that uses an HC-SR04 to detect nearby motion or proximity, a 4x4 keypad for arming and disarming with a PIN, LEDs and an active buzzer for alarm output, and a Python host script for serial logging on a computer.

Overview

This project was built as an automation capstone to combine hardware interfacing, embedded programming, serial communication, and host-computer scripting into one complete system. When the system is armed, the ESP32 monitors the ultrasonic sensor. If an object moves within the configured threshold distance, the system triggers an alarm pattern and sends an alert to the host computer over the serial port. The user can then disarm the system by entering the correct code on the keypad.


Features
- Ultrasonic distance sensing with the HC-SR04
- Armed and disarmed system states
- 4x4 keypad code entry for local control
- Active buzzer alarm output
- Red and green LED status indicators
- Serial communication between the ESP32 and a host computer
- Python event logging with timestamps


Hardware Used
- ESP32 development board
- HC-SR04 ultrasonic sensor
- 4x4 matrix keypad
- Active buzzer
- Red LED
- Green LED
- 220 ohm resistors for LEDs
- Resistors for the Echo voltage divider
- Breadboard and jumper wires


Software Used
- MicroPython on the ESP32
- Thonny IDE for uploading and editing ESP32 code
- Python 3 on the host computer
- `pyserial` for serial communication in the host script
- Git and GitHub for version control and backup


Repository Structure

GitHub README best practices recommend placing the main `README.md` in the repository root and using it to explain the project structure, setup, and usage clearly


Pin Setup

| Component | Connection |
| HC-SR04 VCC | VIN |
| HC-SR04 TRIG | GPIO 5 |
| HC-SR04 ECHO | GPIO 18 through voltage divider |
| HC-SR04 GND | GND |
| Buzzer + | GPIO 19 |
| Buzzer - | GND |
| Red LED anode | GPIO 4 through 220 ohm resistor |
| Red LED cathode | GND |
| Green LED anode | GPIO 2 through 220 ohm resistor |
| Green LED cathode | GND |
| Keypad pins | GPIO 13, 12, 14, 27, 26, 25, 33, 32 |


How It Works

1. The ESP32 boots and loads `main.py` from the board
2. The system starts in a disarmed state until it is armed by keypad input or a serial command
3. When armed, the ESP32 repeatedly reads distance values from the HC-SR04
4. If an object is detected within the set threshold distance, the ESP32 turns on the alarm pattern using the buzzer and red LED
5. The ESP32 also sends status and alert messages to the host computer through the serial connection
6. The Python host script logs those messages with timestamps
7. The user can disarm the system by entering the correct keypad code and pressing `#`


Setup Instructions

ESP32 firmware setup

1. Connect the ESP32 to the computer with a USB cable
2. Open Thonny and select the MicroPython ESP32 interpreter
3. Copy the project firmware into a file named `main.py`
4. Save `main.py` directly to the MicroPython device so it runs on boot
5. Reset or reconnect the ESP32 to start the program


Host computer setup

1. Make sure Python 3 is installed on the computer
2. Install `pyserial`
3. Open `host_logger.py` and change the serial port value if needed, for example `COM4` on Windows
4. Run the script using local Python, not the ESP32 MicroPython interpreter


Usage

1. Power the ESP32 and allow `main.py` to start
2. Press `A` on the keypad to arm the system.
3. Confirm the green LED indicates the armed state.
4. Move a hand or object near the ultrasonic sensor.
5. The buzzer and red LED should activate when the intrusion threshold is reached.
6. Enter the correct PIN code on the keypad and press `#` to disarm the system.
7. Watch the host computer log the events in real time


Example Serial Messages

BOOT:READY
STATUS:ARMED
ALERT:INTRUSION distance_cm=18.4
STATUS:DISARMED source=KEYPAD
