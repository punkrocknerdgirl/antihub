# AntiHub Build Notes

## 2026-07-01 - Viewer, OCR, and QBO search workflow

### Current confirmed workflow

- Unclutter file shelf is pointed at `01 Pending`.
- Dragging a receipt/image into Unclutter lands it in `01 Pending`.
- The existing `Done` button moves the current receipt from `01 Pending` to `02 Processed`.
- This is working as expected for now.
- QBO Global Search shortcut on Mac is confirmed: `Ctrl-Option-F` while inside QBO.
- If QBO Global Search does not find the transaction, user will manually search the bank feed inside QBO for now.
- Do not prioritize the Search Bank Feed button yet.

### Immediate build priorities

#### 1. Fix Next / Back navigation

Need working navigation in the image viewer.

Expected behavior:

- Load files from `01 Pending`.
- Maintain an ordered list of pending files.
- `Next` loads the next file in the list.
- `Back` loads the previous file in the list.
- Safely handle first/last file boundaries.
- Preferred sort order for v1: date modified ascending, so older pending items are processed first.
- Viewer state must track the current file path/index reliably because Rotate, Done, and Search QBO all depend on the active file.

#### 2. Add Rotate Image

Need a rotate control inside the image viewer.

Expected behavior:

- Add a `Rotate` button.
- Each click rotates the current image 90 degrees clockwise.
- Save the corrected orientation back over the original file.
- Do not create duplicate rotated files.
- Reload the viewer after saving so the displayed image matches the stored file.
- Rotation must work before clicking `Done`.

Implementation note:

- Preserve the original file path/name.
- Replace/overwrite the current image after rotation.
- If file type handling differs by extension, support common receipt/image types first: jpg, jpeg, png, heic if the current app stack supports it.

#### 3. Combine Copy to Clipboard + Search QBO

Current workflow:

1. Amount is entered or corrected in the Amount field.
2. User clicks Copy to Clipboard.
3. User searches QBO.

Desired workflow:

1. Amount is entered or corrected in the Amount field.
2. User clicks `Search QBO`.
3. App copies the Amount field value to clipboard.
4. App triggers Keyboard Maestro macro.
5. Keyboard Maestro activates the QBO browser/app window.
6. Keyboard Maestro presses `Ctrl-Option-F`.
7. Keyboard Maestro pastes the clipboard amount.
8. Keyboard Maestro presses Return.

The standalone `Copy to Clipboard` button can remain as a backup/manual utility if useful, but the main workflow should be one click: `Search QBO`.

#### 4. Add OCR total extraction

Need OCR to read the likely total from the receipt/ticket and populate the Amount field.

Expected behavior:

- OCR reads the currently displayed pending receipt/image.
- App extracts the most likely total/amount.
- Amount field is populated with the best guess.
- User can manually correct the amount before clicking `Search QBO`.
- Accuracy does not need to be perfect for v1.

Extraction hints:

- Prefer values near labels like `total`, `amount`, `balance due`, `grand total`, `sale`, `ticket total`.
- For trucking tickets, custom rules may be needed after collecting real examples.
- If OCR confidence is low or multiple candidate totals exist, populate the best guess and make manual correction easy.

### Suggested UI for v1

```text
[Back] [Next]
[Rotate]

Amount: [__________]

[Read Total / OCR]
[Search QBO]
[Done]
[Needs Review]
```

### Not in scope yet

- Automating QBO bank feed search.
- Direct attachment into QBO through the QBO API/software.
- Perfect OCR.
- Multi-step review queues beyond current `01 Pending` to `02 Processed` flow.
