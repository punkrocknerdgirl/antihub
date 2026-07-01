from pathlib import Path
import base64
import shutil
import subprocess
import tempfile
import time

import fitz  # PyMuPDF
import streamlit as st


APP_DIR = Path(__file__).parent
ASSETS_DIR = APP_DIR.parent / "assets"
LOGO_PATHS = [
    ASSETS_DIR / "antihub_logo_graphic_left_receipt.png",
    APP_DIR / "antihub_logo_graphic_left_receipt.png",
]

PENDING_DIR = Path("/Users/erniehathaway/My Drive/05 Scans/01 Pending")
PROCESSED_DIR = Path("/Users/erniehathaway/My Drive/05 Scans/02 Processed")
NOT_IN_QBO_DIR = Path("/Users/erniehathaway/My Drive/05 Scans/03 Not in QBO")

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".heic", ".tif", ".tiff"}
QBO_HOME_URL = "https://qbo.intuit.com"


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
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)


def run_applescript(script: str):
    subprocess.run(["osascript", "-e", script], check=False)


def normalize_amount_text(value: str):
    return str(value or "").strip().replace("$", "").replace(",", "")


def trigger_keyboard_maestro_global_search():
    run_applescript(
        """
        tell application "System Events"
            keystroke "k" using {command down, option down}
        end tell
        """
    )


def trigger_keyboard_maestro_bank_feed_search():
    run_applescript(
        """
        tell application "System Events"
            keystroke "h" using {command down, option down}
        end tell
        """
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

    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    pix.save(temp_file.name)

    page_count = doc.page_count
    doc.close()

    return temp_file.name, page_count


def file_to_base64(file_path: Path):
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


def get_logo_path():
    for logo_path in LOGO_PATHS:
        if logo_path.exists():
            return logo_path
    return None


def render_header_logo():
    logo_path = get_logo_path()

    if logo_path:
        encoded = file_to_base64(logo_path)
        st.markdown(
            f"""
            <div class="header-logo-box">
                <img src="data:image/png;base64,{encoded}" class="header-logo-img" alt="AntiHub" />
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="missing-header-logo">ANTIHUB</div>', unsafe_allow_html=True)


def show_image_in_receipt_frame(image_path: Path, mime_type: str = "image/png", scale: float = 1.0):
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
            show_image_in_receipt_frame(Path(image_path), mime_type="image/png", scale=viewer_scale)
            nav1, nav2, nav3 = st.columns([1, 1.1, 1])

            with nav1:
                previous_disabled = page_count <= 1 or st.session_state[page_key] <= 0
                if st.button("Previous Page", use_container_width=True, disabled=previous_disabled):
                    st.session_state[page_key] = max(0, st.session_state[page_key] - 1)
                    st.rerun()

            with nav2:
                st.markdown(
                    f'<div class="page-count">Page {st.session_state[page_key] + 1} of {page_count}</div>',
                    unsafe_allow_html=True,
                )

            with nav3:
                next_disabled = page_count <= 1 or st.session_state[page_key] >= page_count - 1
                if st.button("Next Page", use_container_width=True, disabled=next_disabled):
                    st.session_state[page_key] = min(page_count - 1, st.session_state[page_key] + 1)
                    st.rerun()
        else:
            st.warning("Could not preview this PDF.")

    elif suffix in {".png", ".jpg", ".jpeg"}:
        mime_type = "image/png" if suffix == ".png" else "image/jpeg"
        show_image_in_receipt_frame(file_path, mime_type=mime_type, scale=viewer_scale)
        st.markdown('<div class="page-count">Single image receipt</div>', unsafe_allow_html=True)

    else:
        st.info("Preview not available for this file type yet. Use Open Receipt.")


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
    st.session_state["last_status"] = {"message": message, "status_type": status_type}


def show_status():
    status = st.session_state.get("last_status")

    if not status:
        return

    st.markdown(
        f'<div class="status-line status-{status.get("status_type", "info")}">{status.get("message", "")}</div>',
        unsafe_allow_html=True,
    )


def clear_qbo_search_amount():
    st.session_state["qbo_search_amount"] = ""
    set_status("Amount cleared.", "info")


def render_right_panel(pending_count: int, processed_count: int, not_in_qbo_count: int, total_started: int, current_file: Path):
    with st.container(border=True):
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
            f'<div class="progress-text">Processed {processed_count} of {total_started} / {pending_count} remaining.</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="section-title first-section">QBO Search</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="helper-text">Enter the receipt amount. Buttons copy it and fire Keyboard Maestro.</div>',
            unsafe_allow_html=True,
        )

        amount_input = st.text_input(
            "Receipt amount",
            key="qbo_search_amount",
            placeholder="117.98",
        )

        clean_amount = normalize_amount_text(amount_input)

        copy_col, clear_col, undo_col = st.columns([1, 1, 1])

        with copy_col:
            if st.button("Copy Amount", use_container_width=True):
                if clean_amount:
                    copy_to_clipboard(clean_amount)
                    set_status(f"Copied {clean_amount}.", "success")
                else:
                    set_status("Enter an amount first.", "warning")

        with clear_col:
            st.button("Clear Amount", use_container_width=True, on_click=clear_qbo_search_amount)

        with undo_col:
            undo_disabled = "last_move" not in st.session_state
            if st.button("Undo Move", use_container_width=True, disabled=undo_disabled):
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
            st.markdown(f'<div class="last-move-small">Last moved: {moved_path.name}</div>', unsafe_allow_html=True)

        show_status()
        st.markdown(
            '<div class="small-note">Chrome should already have the correct client QBO file available. Keyboard Maestro handles the clicky nonsense.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)


st.set_page_config(page_title="AntiHub", page_icon="🧾", layout="wide")
ensure_viewer_state()

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700;900&display=swap');

        :root {
            --antihub-ink: #421333;
            --antihub-berry: #8B325B;
            --antihub-pink: #E25A8A;
            --antihub-blush: #FEEBF1;
            --antihub-soft: #F8D8E3;
            --antihub-white: #FFFFFF;
            --antihub-muted: rgba(66, 19, 51, 0.62);
        }

        html,
        body,
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            min-height: 100%;
            overflow-y: auto !important;
        }

        * { font-family: 'DM Sans', sans-serif; }

        .stApp {
            background: radial-gradient(circle at top left, rgba(226, 90, 138, 0.28), transparent 32rem),
                        linear-gradient(135deg, var(--antihub-ink) 0%, #2a0c21 100%);
            color: var(--antihub-ink);
        }

        .block-container {
            max-width: 1560px;
            margin: 1.15rem auto 2.5rem auto;
            background: var(--antihub-white);
            border-radius: 1.8rem;
            padding: 2.1rem 2.8rem 3rem 2.8rem !important;
            box-shadow: 0 28px 90px rgba(66, 19, 51, 0.46);
            overflow: visible !important;
        }

        div[data-testid="stVerticalBlock"] { gap: 0.72rem !important; }
        div[data-testid="column"] { padding-top: 0 !important; }

        .header-logo-box {
            width: 560px;
            max-width: 100%;
            height: 120px;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            overflow: visible;
        }

        .header-logo-img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            object-position: left center;
            display: block;
        }

        .missing-header-logo {
            color: var(--antihub-ink);
            border: 2px solid var(--antihub-pink);
            border-radius: 0.72rem;
            padding: 1rem 2rem;
            font-weight: 900;
            font-size: 2rem;
        }

        .header-tagline {
            font-size: 1.35rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            text-align: right;
            white-space: nowrap;
            padding-top: 0.45rem;
        }

        .tag-blue { color: var(--antihub-berry); }
        .tag-pink { color: var(--antihub-pink); }

        .receipt-frame {
            background: linear-gradient(180deg, var(--antihub-blush), #ffffff);
            border: 1px solid rgba(139, 50, 91, 0.12);
            border-radius: 1.1rem;
            height: min(62vh, 720px);
            min-height: 500px;
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
            box-shadow: 0 2px 12px rgba(66, 19, 51, 0.12);
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border: 1.5px solid var(--antihub-pink) !important;
            border-radius: 1.35rem !important;
            padding: 1.25rem !important;
            box-shadow: 0 18px 45px rgba(226, 90, 138, 0.12);
        }

        .stat-box {
            background: var(--antihub-blush);
            color: var(--antihub-ink);
            border: 1px solid rgba(139, 50, 91, 0.10);
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
            color: var(--antihub-berry);
        }

        .stat-label {
            font-size: 0.58rem;
            opacity: 0.72;
            margin-top: 0.28rem;
            text-transform: uppercase;
            letter-spacing: 0.07em;
        }

        .progress-text,
        .helper-text,
        .zoom-note,
        .page-count,
        .small-note {
            color: var(--antihub-muted);
            line-height: 1.35;
        }

        .progress-text { font-size: 0.68rem; margin: 0.15rem 0 1.25rem 0; }
        .helper-text { font-size: 0.64rem; margin: 0 0 0.45rem 0; }
        .zoom-note, .page-count { text-align: center; font-size: 0.62rem; padding-top: 0.35rem; }
        .small-note { font-size: 0.58rem; margin-top: 0.5rem; }

        .section-title {
            font-size: 0.78rem;
            font-weight: 800;
            color: var(--antihub-berry);
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin: 1.7rem 0 0.6rem 0;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid rgba(139, 50, 91, 0.14);
        }

        .first-section { margin-top: 0.2rem; }
        .current-file { font-size: 0.78rem; margin: 1rem 0 0.8rem 0; color: var(--antihub-ink); }
        .current-file code { background: var(--antihub-blush); color: var(--antihub-berry); padding: 0.15rem 0.42rem; border-radius: 0.35rem; font-size: 0.72rem; }
        .panel-box { background: var(--antihub-blush); border: 1px solid rgba(139, 50, 91, 0.10); border-radius: 1rem; padding: 1rem 1.1rem; margin-top: 1.8rem; }
        .last-move-small { background: #ffffff; border: 1px solid rgba(226, 90, 138, 0.25); border-radius: 0.65rem; padding: 0.6rem 0.75rem; margin-bottom: 0.6rem; color: var(--antihub-berry); font-size: 0.65rem; line-height: 1.3; }
        .status-line { border-radius: 0.65rem; padding: 0.6rem 0.75rem; margin-top: 0.2rem; font-size: 0.65rem; line-height: 1.3; }
        .status-success, .status-info { background: #ffffff; border: 1px solid rgba(226, 90, 138, 0.25); color: var(--antihub-berry); }
        .status-warning { background: var(--antihub-blush); border: 1px solid rgba(226, 90, 138, 0.42); color: var(--antihub-ink); }
        .stTextInput label { color: var(--antihub-berry); font-size: 0.78rem; font-weight: 800; letter-spacing: 0.02em; }
        .stTextInput input { background: #ffffff; color: var(--antihub-ink); border: 1px solid rgba(139, 50, 91, 0.22); border-radius: 0.75rem; min-height: 3rem; font-size: 1.05rem; padding: 0 1rem; }
        .stTextInput input:focus { border-color: var(--antihub-pink); box-shadow: 0 0 0 0.12rem rgba(226, 90, 138, 0.16); }
        .stButton > button { min-height: 2.6rem; padding: 0 1.1rem; background: #ffffff; color: var(--antihub-ink); border: 1px solid rgba(139, 50, 91, 0.24); border-radius: 0.75rem; font-weight: 600; font-size: 0.78rem; letter-spacing: 0.01em; transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s; }
        .stButton > button:hover { border-color: var(--antihub-pink); box-shadow: 0 2px 8px rgba(226, 90, 138, 0.14); color: var(--antihub-ink); transform: translateY(-1px); }
        .stButton > button[kind="primary"] { background: linear-gradient(105deg, var(--antihub-berry) 0%, var(--antihub-pink) 100%); color: white; border: none; font-weight: 700; font-size: 0.82rem; min-height: 2.85rem; }
        .stButton > button[kind="primary"]:hover { background: linear-gradient(105deg, var(--antihub-ink) 0%, var(--antihub-berry) 100%); color: white; border: none; box-shadow: 0 6px 20px rgba(226, 90, 138, 0.36); }
        hr { margin-top: 0.6rem; margin-bottom: 0.6rem; border-color: rgba(139, 50, 91, 0.12); }
        #MainMenu, header, footer { visibility: hidden; }
        [data-testid="stHeader"] { height: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

pending_files = get_receipt_files(PENDING_DIR)
processed_files = get_receipt_files(PROCESSED_DIR)
not_in_qbo_files = get_receipt_files(NOT_IN_QBO_DIR)

pending_count = len(pending_files)
processed_count = len(processed_files)
not_in_qbo_count = len(not_in_qbo_files)
total_started = pending_count + processed_count + not_in_qbo_count

header_left, header_right = st.columns([0.95, 1.55])

with header_left:
    render_header_logo()

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

if pending_count == 0:
    left, right = st.columns([1.0, 1.25], gap="large")
    with left:
        st.markdown(
            '<div class="panel-box"><div class="section-title first-section">All caught up</div><div class="helper-text">No pending receipts in 01 Pending.</div></div>',
            unsafe_allow_html=True,
        )
    st.stop()

current_file = pending_files[0]
left, right = st.columns([1.15, 1.0], gap="large")

with left:
    st.markdown(
        f'<div class="current-file"><b>Current Receipt:</b> <code>{current_file.name}</code></div>',
        unsafe_allow_html=True,
    )
    show_receipt_preview(current_file)

    zoom_col1, zoom_col2, zoom_col3 = st.columns([1, 1, 1])

    with zoom_col1:
        if st.button("Zoom Out", use_container_width=True):
            st.session_state["viewer_scale"] = max(0.50, round(st.session_state["viewer_scale"] - 0.08, 2))
            st.rerun()

    with zoom_col2:
        if st.button("Reset Zoom", use_container_width=True):
            st.session_state["viewer_scale"] = 0.92
            st.rerun()

    with zoom_col3:
        if st.button("Zoom In", use_container_width=True):
            st.session_state["viewer_scale"] = min(2.0, round(st.session_state["viewer_scale"] + 0.08, 2))
            st.rerun()

    st.markdown(
        f'<div class="zoom-note">Viewer zoom: {int(st.session_state["viewer_scale"] * 100)}%</div>',
        unsafe_allow_html=True,
    )

with right:
    render_right_panel(pending_count, processed_count, not_in_qbo_count, total_started, current_file)
