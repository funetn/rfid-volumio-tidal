#!/bin/bash
echo "Running aggressive GPIO cleanup before RFID service..."
python3 -c '
import RPi.GPIO as GPIO
import time
GPIO.setwarnings(False)
GPIO.cleanup()
time.sleep(1.0)
print("GPIO cleanup completed.")
'
