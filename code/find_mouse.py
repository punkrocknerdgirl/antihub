import time
import pyautogui

print("Move your mouse over the Bank Feed search/filter field or button you want the robot to click.")
print("Do not click. Just hover there.")
print("Reading position in 5 seconds...")

for seconds_left in range(5, 0, -1):
    print(seconds_left)
    time.sleep(1)

position = pyautogui.position()

print("")
print(f"Mouse position: x={position.x}, y={position.y}")
print("")
print("Copy those numbers back to Ed.")
