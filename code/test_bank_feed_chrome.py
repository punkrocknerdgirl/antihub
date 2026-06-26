import subprocess
import time

import pyautogui

BANK_URL = "https://qbo.intuit.com/app/banking?jobId=accounting"
BANK_SEARCH_X = 408
BANK_SEARCH_Y = 582
TEST_AMOUNT = "117.98"


def copy_to_clipboard(text: str):
    subprocess.run(
        ["pbcopy"],
        input=text.encode("utf-8"),
        check=False,
    )


def run_applescript(script: str):
    subprocess.run(
        ["osascript", "-e", script],
        check=False,
    )


print("Copying test amount to clipboard...")
copy_to_clipboard(TEST_AMOUNT)

print("Opening Bank Transactions page in Chrome...")
subprocess.run(["open", "-a", "Google Chrome", BANK_URL], check=False)

print("Waiting for page to load...")
time.sleep(3.0)

print(f"Clicking Bank Feed search box at x={BANK_SEARCH_X}, y={BANK_SEARCH_Y}...")
pyautogui.click(BANK_SEARCH_X, BANK_SEARCH_Y)

time.sleep(0.5)

print("Clearing search box...")
run_applescript(
    '''
    tell application "System Events"
        keystroke "a" using {command down}
        delay 0.2
        key code 51
    end tell
    '''
)

time.sleep(0.5)

print("Clicking search box again...")
pyautogui.click(BANK_SEARCH_X, BANK_SEARCH_Y)

time.sleep(0.4)

print("Pasting amount and pressing Enter...")
run_applescript(
    '''
    tell application "System Events"
        keystroke "v" using {command down}
        delay 0.3
        key code 36
    end tell
    '''
)

print("Done.")
