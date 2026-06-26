from pathlib import Path
import base64
import shutil
import subprocess
import tempfile
import time

import fitz  # PyMuPDF
import streamlit as st


APP_DIR = Path(__file__).parent
LOGO_PATH = APP_DIR / "kwisatz_logo_round_rect.png"

PENDING_DIR = Path("/Users/erniehathaway/My Drive/05 Scans/01 Pending")
PROCESSED_DIR = Path("/Users/erniehathaway/My Drive/05 Scans/02 Processed")
NOT_IN_QBO_DIR = Path("/Users/erniehathaway/My Drive/05 Scans/03 Not in QBO")

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".heic", ".tif", ".tiff"}
QBO_HOME_URL = "https://qbo.intuit.com"


# -----------------------------
# File / OS helpers
# -----------------------------
def get_receipt_files(folder: Path):
    if not folder.exists():
        return []

    return sorted(
        [
            file
            for file in folder.iterdir()
            if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
        ],
        key=lambda file: file.name.lower(),
    )


def open_path(path: Path):
    subprocess.run(["open", str(path)], check=False)


def open_chrome_url(url: str):
    subprocess.run(["open", "-a", "Google Chrome", url], check=False)


def open_qbo_chrome():
    open_chrome_url(QBO_HOME_URL)


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


# -----------------------------
# Amount / Keyboard Maestro helpers
# -----------------------------
def normalize_amount_text(value: str):
    value = str(value or "").strip()
    value = value.replace("$", "").replace(",", "")
    return value


def trigger_keyboard_maestro_global_search():
    run_applescript(
        '''
        tell application "System Events"
            keystroke "k" using {command down, option down}
        end tell
        '''
    )


def trigger_keyboard_maestro_bank_feed_search():
    run_applescript(
        '''
        tell application "System Events"
            keystroke "h" using {command down, option down}
        end tell
        '''
    )


def search_qbo_global_with_keyboard_maestro(amount: str):
    clean_amount = normalize_amount_text(amount)

    if not clean_amount:
        return False, "Enter an amount first."

    copy_to_clipboard(clean_amount)
    time.sleep(0.2)
    trigger_keyboard_maestro_global_search()

    return True, f"Sent {clean_amount} to QBO Global search."


def search_bank_feed_with_keyboard_maestro(amount: str):
    clean_amount = normalize_amount_text(amount)

    if not clean_amount:
        return False, "Enter an amount first."

    copy_to_clipboard(clean_amount)
    time.sleep(0.2)
    trigger_keyboard_maestro_bank_feed_search()

    return True, f"Sent {clean_amount} to Bank Feed search."


# -----------------------------
# Move / undo helpers
# -----------------------------
def unique_destination_path(destination: Path):
    if not destination.exists():
        return destination

    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 2

    while destination.exists():
        destination = parent / f"{stem} ({counter}){suffix}"
        counter += 1

    return destination


def move_file(source: Path, destination_folder: Path):
    destination_folder.mkdir(parents=True, exist_ok=True)
    destination = unique_destination_path(destination_folder / source.name)
    shutil.move(str(source), str(destination))
    return destination


def move_file_back(source: Path, original_path: Path):
    original_path.parent.mkdir(parents=True, exist_ok=True)
    destination = unique_destination_path(original_path)
    shutil.move(str(source), str(destination))
    return destination


def undo_last_move():
    if "last_move" not in st.session_state:
        return False, "Nothing to undo."

    last_move = st.session_state["last_move"]
    moved_path = Path(last_move["moved_path"])
    original_path = Path(last_move["original_path"])

    if not moved_path.exists():
        return False, "Could not undo. The moved file is no longer where expected."

    restored_to = move_file_back(moved_path, original_path)
    del st.session_state["last_move"]

    return True, f"Restored: {restored_to.name}"


# -----------------------------
# Preview helpers
# -----------------------------
def ensure_viewer_state():
    if "viewer_scale" not in st.session_state:
        st.session_state["viewer_scale"] = 0.92


def render_pdf_page_to_png(pdf_path: Path, page_number: int = 0, zoom: float = 2.2):
    doc = fitz.open(str(pdf_path))

    if doc.page_count == 0:
        doc.close()
        return None, 0

    page_number = max(0, min(page_number, doc.page_count - 1))
    page = doc.load_page(page_number)

    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    pix.save(temp_file.name)

    page_count = doc.page_count
    doc.close()

    return temp_file.name, page_count


def file_to_base64(file_path: Path):
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


def render_header_logo():
    if LOGO_PATH.exists():
        encoded = file_to_base64(LOGO_PATH)
        st.markdown(
            f"""
            <img src="data:image/png;base64,{encoded}" class="header-logo-img" />
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="missing-header-logo">KWISATZ</div>
            """,
            unsafe_allow_html=True,
        )


def show_image_in_receipt_frame(
    image_path: Path,
    mime_type: str = "image/png",
    scale: float = 1.0,
):
    encoded = file_to_base64(image_path)

    st.markdown(
        f"""
        <div class="receipt-frame">
            <div class="receipt-canvas">
                <img
                    src="data:{mime_type};base64,{encoded}"
                    class="receipt-image"
                    style="transform: scale({scale});"
                />
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_receipt_preview(file_path: Path):
    suffix = file_path.suffix.lower()
    viewer_scale = st.session_state.get("viewer_scale", 0.92)

    if suffix == ".pdf":
        page_key = f"page_number_{file_path.name}"

        if page_key not in st.session_state:
            st.session_state[page_key] = 0

        image_path, page_count = render_pdf_page_to_png(
            file_path,
            page_number=st.session_state[page_key],
        )

        if image_path:
            show_image_in_receipt_frame(
                Path(image_path),
                mime_type="image/png",
                scale=viewer_scale,
            )

            nav1, nav2, nav3 = st.columns([1, 1.1, 1])

            with nav1:
                previous_disabled = page_count <= 1 or st.session_state[page_key] <= 0
                if st.button("Previous Page", use_container_width=True, disabled=previous_disabled):
                    st.session_state[page_key] = max(0, st.session_state[page_key] - 1)
                    st.rerun()

            with nav2:
                st.markdown(
                    f"""
                    <div class="page-count">
                        Page {st.session_state[page_key] + 1} of {page_count}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with nav3:
                next_disabled = page_count <= 1 or st.session_state[page_key] >= page_count - 1
                if st.button("Next Page", use_container_width=True, disabled=next_disabled):
                    st.session_state[page_key] = min(
                        page_count - 1,
                        st.session_state[page_key] + 1,
                    )
                    st.rerun()
        else:
            st.warning("Could not preview this PDF.")

    elif suffix in {".png", ".jpg", ".jpeg"}:
        mime_type = "image/png" if suffix == ".png" else "image/jpeg"
        show_image_in_receipt_frame(file_path, mime_type=mime_type, scale=viewer_scale)
        st.markdown('<div class="page-count">Single image receipt</div>', unsafe_allow_html=True)

    else:
        st.info("Preview not available for this file type yet. Use Open Receipt.")


# -----------------------------
# UI helpers
# -----------------------------
def stat_box(label: str, value: int):
    st.markdown(
        f"""
        <div class="stat-box">
            <div class="stat-value">{value}</div>
            <div class="stat-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def set_status(message: str, status_type: str = "info"):
    st.session_state["last_status"] = {
        "message": message,
        "status_type": status_type,
    }


def show_status():
    status = st.session_state.get("last_status")
    if not status:
        return

    status_type = status.get("status_type", "info")
    message = status.get("message", "")

    st.markdown(
        f"""
        <div class="status-line status-{status_type}">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="Kwisatz",
    page_icon="🧾",
    layout="wide",
)

ensure_viewer_state()

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700;900&display=swap');

        * {
            font-family: 'DM Sans', sans-serif;
        }

        .stApp {
            background: #0a0a0a;
            color: #111827;
        }

        .block-container {
            max-width: 1560px;
            margin: 1.15rem auto;
            background: #ffffff;
            border-radius: 1.8rem;
            padding: 0 !important;
            box-shadow: 0 28px 90px rgba(0, 0, 0, 0.45);
            overflow: hidden;
        }

        .app-body {
            padding: 2.25rem 2.8rem 2rem 2.8rem;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.72rem !important;
        }

        div[data-testid="column"] {
            padding-top: 0 !important;
        }

        .app-header {
            background: #000000;
            padding: 2rem 3.2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 2rem;
        }

        .header-logo-box {
            border-radius: 0.72rem;
            padding: 0;
            width: 430px;
            height: 108px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .header-logo-img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
        }

        .missing-header-logo {
            color: white;
            border: 2px solid #e879f9;
            border-radius: 0.72rem;
            padding: 1rem 2rem;
            width: 430px;
            height: 108px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
            font-size: 2rem;
        }

        .header-tagline {
            font-size: 1.72rem;
            font-weight: 500;
            letter-spacing: -0.03em;
            text-align: right;
            white-space: nowrap;
        }

        .tag-blue {
            color: #0ea5e9;
        }

        .tag-pink {
            color: #d946ef;
        }

        .receipt-frame {
            background: #d9d9d9;
            border: 1px solid rgba(17, 24, 39, 0.08);
            border-radius: 1.1rem;
            height: calc(100vh - 16.5rem);
            min-height: 520px;
            max-height: 780px;
            overflow: auto;
            padding: 1rem;
            margin-bottom: 0.7rem;
        }

        .receipt-canvas {
            width: 100%;
            min-height: 100%;
            display: flex;
            align-items: flex-start;
            justify-content: center;
        }

        .receipt-image {
            display: block;
            max-width: 100%;
            height: auto;
            transform-origin: top center;
            border-radius: 0.3rem;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
        }

        .right-panel-spacer {
            height: 2.2rem;
        }

        .right-panel {
            border: 1.5px solid #f542d4;
            border-radius: 1.35rem;
            padding: 2.15rem 1.85rem 1.75rem 1.85rem;
            min-height: 620px;
        }

        .stat-box {
            background: #f8f9fa;
            color: #111827;
            border: 1px solid rgba(17, 24, 39, 0.07);
            border-radius: 1rem;
            padding: 0.9rem 0.5rem 1rem 0.5rem;
            text-align: center;
            margin-bottom: 0;
        }

        .stat-value {
            font-size: 1.75rem;
            font-weight: 900;
            line-height: 1.0;
            letter-spacing: -0.04em;
        }

        .stat-label {
            font-size: 0.58rem;
            opacity: 0.55;
            margin-top: 0.28rem;
            text-transform: uppercase;
            letter-spacing: 0.07em;
        }

        .progress-text {
            font-size: 0.68rem;
            color: #9ca3af;
            line-height: 1.35;
            margin: 0.15rem 0 1.25rem 0;
        }

        .section-title {
            font-size: 0.78rem;
            font-weight: 800;
            color: #374151;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin: 1.7rem 0 0.6rem 0;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #ebebeb;
        }

        .first-section {
            margin-top: 0.2rem;
        }

        .helper-text {
            font-size: 0.64rem;
            color: #9ca3af;
            line-height: 1.35;
            margin: 0 0 0.45rem 0;
        }

        .current-file {
            font-size: 0.78rem;
            margin: 0 0 0.8rem 0;
            color: #374151;
        }

        .current-file code {
            background: #eef2ff;
            color: #3730a3;
            padding: 0.15rem 0.42rem;
            border-radius: 0.35rem;
            font-size: 0.72rem;
        }

        .zoom-note,
        .page-count {
            color: #9ca3af;
            text-align: center;
            font-size: 0.62rem;
            padding-top: 0.35rem;
        }

        .panel-box {
            background: #f8f9fa;
            border: 1px solid rgba(17, 24, 39, 0.07);
            border-radius: 1rem;
            padding: 1rem 1.1rem;
            margin-top: 1.8rem;
        }

        .last-move-small {
            background: #eff6ff;
            border: 1px solid rgba(59, 130, 246, 0.18);
            border-radius: 0.65rem;
            padding: 0.6rem 0.75rem;
            margin-bottom: 0.6rem;
            color: #1e4fa8;
            font-size: 0.65rem;
            line-height: 1.3;
        }

        .status-line {
            border-radius: 0.65rem;
            padding: 0.6rem 0.75rem;
            margin-top: 0.2rem;
            font-size: 0.65rem;
            line-height: 1.3;
        }

        .status-success {
            background: #eff6ff;
            border: 1px solid #c7d2fe;
            color: #3730a3;
        }

        .status-warning {
            background: #faf5ff;
            border: 1px solid #e9d5ff;
            color: #7e22ce;
        }

        .status-info {
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            color: #1d4ed8;
        }

        .small-note {
            font-size: 0.58rem;
            color: #9ca3af;
            line-height: 1.35;
            margin-top: 0.5rem;
        }

        .stTextInput input {
            background: #ffffff;
            color: #111827;
            border: 1px solid rgba(17, 24, 39, 0.14);
            border-radius: 0.75rem;
            min-height: 2.6rem;
            font-size: 0.88rem;
            padding: 0 0.85rem;
        }

        .stButton > button {
            min-height: 2.6rem;
            padding: 0 1.1rem;
            background: #ffffff;
            color: #111827;
            border: 1px solid rgba(17, 24, 39, 0.16);
            border-radius: 0.75rem;
            font-weight: 600;
            font-size: 0.78rem;
            letter-spacing: 0.01em;
            transition: border-color 0.15s, box-shadow 0.15s;
        }

        .stButton > button:hover {
            border-color: rgba(17, 24, 39, 0.32);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
            color: #111827;
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(105deg, #1a3fcc 0%, #7c22e8 50%, #a21caf 100%);
            color: white;
            border: none;
            font-weight: 700;
            font-size: 0.82rem;
            min-height: 2.85rem;
        }

        .stButton > button[kind="primary"]:hover {
            background: linear-gradient(105deg, #1530a8 0%, #6b1fd4 50%, #8b179a 100%);
            color: white;
            border: none;
            box-shadow: 0 6px 20px rgba(124, 34, 232, 0.4);
        }

        hr {
            margin-top: 0.6rem;
            margin-bottom: 0.6rem;
            border-color: rgba(17, 24, 39, 0.07);
        }

        #MainMenu,
        header,
        footer {
            visibility: hidden;
        }

        [data-testid="stHeader"] {
            height: 0;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Data
# -----------------------------
pending_files = get_receipt_files(PENDING_DIR)
processed_files = get_receipt_files(PROCESSED_DIR)
not_in_qbo_files = get_receipt_files(NOT_IN_QBO_DIR)

pending_count = len(pending_files)
processed_count = len(processed_files)
not_in_qbo_count = len(not_in_qbo_files)
total_started = pending_count + processed_count + not_in_qbo_count


# -----------------------------
# Header
# -----------------------------
st.markdown('<div class="app-header">', unsafe_allow_html=True)

header_left, header_right = st.columns([0.8, 1.7])

with header_left:
    st.markdown('<div class="header-logo-box">', unsafe_allow_html=True)
    render_header_logo()
    st.markdown('</div>', unsafe_allow_html=True)

with header_right:
    st.markdown(
        """
        <div class="header-tagline">
            <span class="tag-blue">a smart tool for dumb shit</span>
            <span class="tag-pink">&nbsp;|&nbsp;by punkrocknerdgirl</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<div class="app-body">', unsafe_allow_html=True)


# -----------------------------
# Empty state
# -----------------------------
if pending_count == 0:
    left, right = st.columns([1.0, 1.25], gap="large")

    with left:
        st.markdown(
            """
            <div class="panel-box">
                <div class="section-title first-section">All caught up</div>
                <div class="helper-text">No pending receipts in 01 Pending.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# -----------------------------
# Main layout
# -----------------------------
current_file = pending_files[0]

left, right = st.columns([1.15, 1.0], gap="large")


# Left: receipt viewer
with left:
    st.markdown(
        f"""
        <div class="current-file">
            <b>Current Receipt:</b> <code>{current_file.name}</code>
        </div>
        """,
        unsafe_allow_html=True,
    )

    show_receipt_preview(current_file)

    zoom_col1, zoom_col2, zoom_col3 = st.columns([1, 1, 1])

    with zoom_col1:
        if st.button("Zoom Out", use_container_width=True):
            st.session_state["viewer_scale"] = max(
                0.50,
                round(st.session_state["viewer_scale"] - 0.08, 2),
            )
            st.rerun()

    with zoom_col2:
        if st.button("Reset Zoom", use_container_width=True):
            st.session_state["viewer_scale"] = 0.92
            st.rerun()

    with zoom_col3:
        if st.button("Zoom In", use_container_width=True):
            st.session_state["viewer_scale"] = min(
                2.0,
                round(st.session_state["viewer_scale"] + 0.08, 2),
            )
            st.rerun()

    st.markdown(
        f"""
        <div class="zoom-note">
            Viewer zoom: {int(st.session_state["viewer_scale"] * 100)}%
        </div>
        """,
        unsafe_allow_html=True,
    )


# Right: controls
with right:
    st.markdown('<div class="right-panel-spacer"></div>', unsafe_allow_html=True)
    st.markdown('<div class="right-panel">', unsafe_allow_html=True)

    stat1, stat2, stat3, stat4 = st.columns(4)

    with stat1:
        stat_box("Pending", pending_count)

    with stat2:
        stat_box("Done", processed_count)

    with stat3:
        stat_box("Not QBO", not_in_qbo_count)

    with stat4:
        stat_box("Total", total_started)

    st.markdown(
        f"""
        <div class="progress-text">
            Processed {processed_count} of {total_started} / {pending_count} remaining.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title first-section">QBO Search</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="helper-text">
            Enter the receipt amount. Buttons copy it and fire Keyboard Maestro.
        </div>
        """,
        unsafe_allow_html=True,
    )

    amount_col, copy_col, clear_col, undo_col = st.columns([1.45, 0.72, 0.72, 0.9])

    with amount_col:
        amount_input = st.text_input(
            "Amount",
            key="qbo_search_amount",
            placeholder="117.98",
            label_visibility="collapsed",
        )

    clean_amount = normalize_amount_text(amount_input)

    with copy_col:
        if st.button("Copy", use_container_width=True):
            if clean_amount:
                copy_to_clipboard(clean_amount)
                set_status(f"Copied {clean_amount}.", "success")
            else:
                set_status("Enter an amount first.", "warning")

    with clear_col:
        if st.button("Clear", use_container_width=True):
            st.session_state["qbo_search_amount"] = ""
            set_status("Amount cleared.", "info")
            st.rerun()

    with undo_col:
        undo_disabled = "last_move" not in st.session_state

        if st.button("Undo", use_container_width=True, disabled=undo_disabled):
            success, message = undo_last_move()
            set_status(message, "success" if success else "warning")
            st.rerun()

    search1, search2 = st.columns([1, 1])

    with search1:
        if st.button("Search QBO Global", type="primary", use_container_width=True):
            success, message = search_qbo_global_with_keyboard_maestro(clean_amount)
            set_status(message, "success" if success else "warning")

    with search2:
        if st.button("Search Bank Feed", type="primary", use_container_width=True):
            success, message = search_bank_feed_with_keyboard_maestro(clean_amount)
            set_status(message, "success" if success else "warning")

    st.markdown('<div class="section-title">Actions</div>', unsafe_allow_html=True)

    action1, action2 = st.columns([1, 1])

    with action1:
        if st.button("Open Receipt", use_container_width=True):
            open_path(current_file)

    with action2:
        if st.button("Open QBO Chrome", use_container_width=True):
            open_qbo_chrome()

    action3, action4, action5 = st.columns([1, 1, 1])

    with action3:
        if st.button("Mark Done", type="primary", use_container_width=True):
            original_path = current_file
            moved_to = move_file(current_file, PROCESSED_DIR)

            st.session_state["last_move"] = {
                "original_path": str(original_path),
                "moved_path": str(moved_to),
                "action": "processed",
            }

            set_status(f"Moved to Processed: {moved_to.name}", "success")
            st.rerun()

    with action4:
        if st.button("Not in QBO", type="primary", use_container_width=True):
            original_path = current_file
            moved_to = move_file(current_file, NOT_IN_QBO_DIR)

            st.session_state["last_move"] = {
                "original_path": str(original_path),
                "moved_path": str(moved_to),
                "action": "not_in_qbo",
            }

            set_status(f"Moved to Not in QBO: {moved_to.name}", "warning")
            st.rerun()

    with action5:
        if st.button("Skip / Next", type="primary", use_container_width=True):
            set_status("Skip sorting comes later. For now, leave it where it is.", "info")

    st.markdown('<div class="panel-box">', unsafe_allow_html=True)

    if "last_move" in st.session_state:
        moved_path = Path(st.session_state["last_move"]["moved_path"])
        st.markdown(
            f"""
            <div class="last-move-small">
                Last moved: {moved_path.name}
            </div>
            """,
            unsafe_allow_html=True,
        )

    show_status()

    st.markdown(
        """
        <div class="small-note">
            Chrome should already have the correct client QBO file available. Keyboard Maestro handles the clicky nonsense.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)