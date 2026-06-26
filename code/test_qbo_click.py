import subprocess
import time

import pyautogui

SEARCH_X = 890
SEARCH_Y = 148
TEST_AMOUNT = "117.98"

def copy_to_clipboard(text: str):
    subprocess.run(
        ["pbcopy"],
        input=text.encode("utf-8"),
        check=False,
    )

print("Copying test amount...")
copy_to_clipboard(TEST_AMOUNT)

print("Opening QBO app...")
subprocess.run(["open", "-a", "QBO"], check=False)

print("Waiting for QBO to activate...")
time.sleep(1.25)

print(f"Clicking search box at x={SEARCH_X}, y={SEARCH_Y}...")
pyautogui.click(SEARCH_X, SEARCH_Y)

time.sleep(0.25)

print("Clearing search box...")
pyautogui.hotkey("command", "a")
time.sleep(0.15)
pyautogui.press("delete")
time.sleep(0.15)

print("Pasting amount...")
pyautogui.hotkey("command", "v")

time.sleep(0.25)

print("Pressing Enter...")
pyautogui.press("enter")

print("Done.")
