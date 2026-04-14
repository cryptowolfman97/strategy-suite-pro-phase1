import requests
import certifi
import sys
import hashlib
import hmac
import random
import json
import os
import math
import statistics
import threading
import time
import base64
import zlib
from dataclasses import dataclass
import webbrowser
from urllib.parse import quote
from datetime import datetime, timezone
from functools import wraps

try:
    import rsa
except Exception:
    rsa = None

from decimal import Decimal, getcontext
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.widget import Widget
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from kivy.metrics import dp
from kivy.clock import Clock

# Theme Configuration
STAKE_DARK = '#000000'
STAKE_INPUT = '#10243a'
STAKE_GREEN = '#7ec8ff'
STAKE_RED = '#ff4e4e'
STAKE_TEXT = '#d6e8ff'

SOFT_RED = '#7a0c0c'
DIVIDER_COLOR = '#16314a'
SUBTITLE_TEXT = '#9dc7ea'

DICE_COLOR = '#5fa8ff'
LIMBO_COLOR = '#7ec8ff'
KENO_COLOR = '#9dc7ea'
MINES_COLOR = '#6ab6ff'
SPORTS_COLOR = '#4f9dff'
UTILITY_COLOR = '#18324a'
LIBRARY_COLOR = STAKE_GREEN

# --- Owner-editable support / pricing settings ---
SUPPORT_WHATSAPP_NUMBER = "+94771363462"
SUPPORT_EMAIL_ADDRESS = "shhirimuthugoda@gmail.com"
PRO_PRICE_TEXT = "$24.99 lifetime"
PRO_PLUS_PRICE_TEXT = "$39.99 lifetime"
SUPPORT_WHATSAPP_LINK = f"https://wa.me/{SUPPORT_WHATSAPP_NUMBER.replace('+', '').replace(' ', '')}"

Window.clearcolor = get_color_from_hex(STAKE_DARK)
getcontext().prec = 40


def safe_float(text, default=0.0):
    try:
        return float(str(text).strip())
    except Exception:
        return default


def safe_int(text, default=0):
    try:
        return int(float(str(text).strip()))
    except Exception:
        return default


def _ui_call(fn, *args, **kwargs):
    Clock.schedule_once(lambda dt: fn(*args, **kwargs), 0)


# ── Share Result Utility ─────────────────────────────────────────────────────
APP_NAME = "Strategy Suite Pro"
APP_VERSION_LABEL = "1.0"
CLEAN_BUILD = True
COMPANY_NAME = "SH Vertex Technologies"

def share_result(title, lines):
    """
    Share a formatted result card via Android share sheet or clipboard fallback.
    lines: list of strings, e.g. ["Average Net Units: 0.1234", "Positive Rate: 77.90%"]
    """
    separator = "─" * 32
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = "\n".join(lines)
    text = (
        f"[ {get_display_app_name()} ]\n"
        f"{separator}\n"
        f"  {get_title_display_from_text(title)}\n"
        f"{separator}\n"
        f"{body}\n"
        f"{separator}\n"
        f"Time: {timestamp}\n"
        f"© {COMPANY_NAME}"
    )

    try:
        if sys.platform == "android":
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            String = autoclass("java.lang.String")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            intent = Intent(Intent.ACTION_SEND)
            intent.setType("text/plain")
            intent.putExtra(Intent.EXTRA_TEXT, String(text))
            chooser = Intent.createChooser(intent, String("Share via"))
            PythonActivity.mActivity.startActivity(chooser)
        else:
            # Desktop fallback — copy to clipboard
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(text)
            _show_share_copied_popup()
    except Exception:
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(text)
            _show_share_copied_popup()
        except Exception:
            pass


def _show_share_copied_popup(*args):
    content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
    lbl = Label(
        text="Result copied to clipboard!\nPaste it anywhere to share.",
        color=get_color_from_hex(STAKE_TEXT),
        halign='center',
        valign='middle',
        size_hint_y=None,
        height=dp(60)
    )
    lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
    btn = Button(
        text="OK",
        size_hint_y=None,
        height=dp(42),
        background_normal='',
        background_color=get_color_from_hex(STAKE_GREEN),
        color=(0, 0, 0, 1)
    )
    content.add_widget(lbl)
    content.add_widget(btn)
    popup = Popup(
        title="Copied",
        content=content,
        size_hint=(0.78, 0.32),
        separator_color=get_color_from_hex(STAKE_GREEN)
    )
    btn.bind(on_release=popup.dismiss)
    popup.open()
# ─────────────────────────────────────────────────────────────────────────────



def get_app_data_dir():
    try:
        if sys.platform == "android":
            from android.storage import app_storage_path
            data_dir = app_storage_path()
        else:
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data")
    except Exception:
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data")

    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_strategy_file():
    return os.path.join(get_app_data_dir(), "strategies_master.json")


def get_tracker_file():
    return os.path.join(get_app_data_dir(), "tracker_state.json")


def get_history_file():
    return os.path.join(get_app_data_dir(), "session_history.json")


# ── Session History Helpers ───────────────────────────────────────────────────
def load_session_history():
    try:
        with open(get_history_file(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def save_session_history(entries):
    try:
        with open(get_history_file(), 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"save_session_history error: {e}")


def log_history_entry(amount):
    """Append one result entry to history. Called on every UPDATE."""
    entries = load_session_history()
    entries.append({
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "amount": round(float(amount), 8),
    })
    save_session_history(entries)


def clear_session_history():
    """Wipe history file. Called when tracker is reset."""
    save_session_history([])
# ─────────────────────────────────────────────────────────────────────────────


# ── Risk Profile System ─────────────────────────────────────────────────────────────────────────────────
def get_profile_file():
    return os.path.join(get_app_data_dir(), "risk_profile.json")


def load_risk_profile():
    try:
        with open(get_profile_file(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get('completed'):
            return data
    except Exception:
        pass
    return None


def save_risk_profile(profile):
    try:
        with open(get_profile_file(), 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"save_risk_profile error: {e}")


def clear_risk_profile():
    save_risk_profile({})


def get_profile_badge_text():
    p = load_risk_profile()
    if not p or not p.get('completed') or p.get('skipped'):
        return ""
    bankroll = p.get('bankroll', '')
    risk     = p.get('risk', '')
    game     = clean_display_label(p.get('game', ''))
    return f"{bankroll}  |  {risk}  |  {game}"


def show_onboarding_wizard(on_complete=None):
    profile = {}
    STEPS = [
        {
            "title": "Step 1 of 3 — Capital Size",
            "question": "What's your typical analysis capital?",
            "key": "bankroll",
            "options": [
                ("Micro",  "Under 10u",   "#95a5a6"),
                ("Small",  "10u – 50u",   DICE_COLOR),
                ("Medium", "50u – 200u",  LIMBO_COLOR),
                ("Large",  "200u+",       STAKE_GREEN),
            ],
        },
        {
            "title": "Step 2 of 3 — Risk Appetite",
            "question": "How do you like to model risk?",
            "key": "risk",
            "options": [
                ("Conservative", "Low risk, slow growth",  STAKE_GREEN),
                ("Balanced",     "Mix of both",            DICE_COLOR),
                ("Aggressive",   "High risk, high variance", MINES_COLOR),
                ("Degen",        "Maximum variance",        STAKE_RED),
            ],
        },
        {
            "title": "Step 3 of 3 — Primary Game",
            "question": "What model do you use most?",
            "key": "game",
            "options": [
                ("RNG",   "Variance models",   DICE_COLOR),
                ("Grid",   "Spatial models",           KENO_COLOR),
                ("Grid-Risk",  "Risk node models",          MINES_COLOR),
                ("Market", "Market models", SPORTS_COLOR),
            ],
        },
    ]
    state = {"step": 0, "popup": None}

    def show_step(step_index):
        step = STEPS[step_index]
        content = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(8))

        dot_row = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(6))
        dot_row.add_widget(Widget())
        for i in range(len(STEPS)):
            dot_color = STAKE_GREEN if i <= step_index else "#333333"
            dot_row.add_widget(Label(text="o", color=get_color_from_hex(dot_color),
                                     font_size='14sp', size_hint_x=None, width=dp(22)))
        dot_row.add_widget(Widget())
        content.add_widget(dot_row)

        q_lbl = Label(text=step["question"], color=get_color_from_hex(STAKE_TEXT),
                      font_size='14sp', bold=True, size_hint_y=None, height=dp(34),
                      halign='center', valign='middle')
        q_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        content.add_widget(q_lbl)

        for label, desc, color in step["options"]:
            btn = Button(
                text=f"{label}\n[size=11][color=#9a9a9a]{desc}[/color][/size]",
                markup=True, background_normal='',
                background_color=get_color_from_hex(STAKE_INPUT),
                size_hint_y=None, height=dp(50),
                halign='center', valign='middle',
                font_size='13sp', bold=True,
            )
            with btn.canvas.before:
                Color(rgba=get_color_from_hex(color))
                btn._left = Rectangle(pos=btn.pos, size=(dp(4), btn.height))
            def _upd(inst, val):
                inst._left.pos = inst.pos
                inst._left.size = (dp(4), inst.height)
            btn.bind(pos=_upd, size=_upd)

            def on_choice(b, lbl=label, k=step["key"], si=step_index):
                profile[k] = lbl
                if state["popup"]:
                    state["popup"].dismiss()
                nxt = si + 1
                if nxt < len(STEPS):
                    show_step(nxt)
                else:
                    show_summary()
            btn.bind(on_release=on_choice)
            content.add_widget(btn)

        if step_index == 0:
            skip_btn = Button(text="Skip for now", background_normal='',
                              background_color=(0,0,0,0),
                              color=get_color_from_hex(SUBTITLE_TEXT),
                              size_hint_y=None, height=dp(30), font_size='11sp')
            def do_skip(*a):
                if state["popup"]:
                    state["popup"].dismiss()
                save_risk_profile({"completed": True, "skipped": True,
                                   "bankroll": "", "risk": "", "game": ""})
                if on_complete:
                    on_complete()
            skip_btn.bind(on_release=do_skip)
            content.add_widget(skip_btn)

        popup = Popup(title=step["title"], content=content,
                      size_hint=(0.94, 0.80),
                      separator_color=get_color_from_hex(STAKE_GREEN))
        state["popup"] = popup
        popup.open()

    def show_summary():
        bankroll = profile.get('bankroll', '')
        risk     = profile.get('risk', '')
        game     = clean_display_label(profile.get('game', ''))
        risk_colors = {'Conservative': STAKE_GREEN, 'Balanced': DICE_COLOR,
                       'Aggressive': MINES_COLOR, 'Degen': STAKE_RED}
        rc = risk_colors.get(risk, STAKE_GREEN)

        content = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(10))
        content.add_widget(Label(text="Profile Complete!",
                                  color=get_color_from_hex(STAKE_GREEN),
                                  font_size='18sp', bold=True,
                                  size_hint_y=None, height=dp(36),
                                  halign='center', valign='middle'))

        profile_lbl = Label(
            text=f"Capital:   {bankroll}\nRisk:          {risk}\nModel:      {clean_display_label(game)}",
            color=get_color_from_hex(STAKE_TEXT), font_size='14sp',
            size_hint_y=None, height=dp(72), halign='center', valign='middle')
        profile_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        content.add_widget(profile_lbl)

        badge_lbl = Label(
            text=f"{bankroll}  |  {risk}  |  {game}",
            color=get_color_from_hex(rc), font_size='12sp', bold=True,
            size_hint_y=None, height=dp(26), halign='center', valign='middle')
        badge_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        content.add_widget(badge_lbl)

        note = Label(
            text="Your profile badge is shown on the main menu.\nReset anytime from the menu.",
            color=get_color_from_hex(SUBTITLE_TEXT), font_size='11sp',
            size_hint_y=None, height=dp(36), halign='center', valign='middle')
        note.bind(size=lambda i, v: setattr(i, 'text_size', v))
        content.add_widget(note)

        done_btn = StyledButton(text="LET'S GO", bg_color=STAKE_GREEN)
        popup = Popup(title='Your Risk Profile', content=content,
                      size_hint=(0.88, 0.68),
                      separator_color=get_color_from_hex(STAKE_GREEN))

        def do_done(*a):
            popup.dismiss()
            final = {
                "completed": True, "skipped": False,
                "bankroll": bankroll, "risk": risk, "game": game,
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            }
            save_risk_profile(final)
            if on_complete:
                on_complete()
        done_btn.bind(on_release=do_done)
        content.add_widget(done_btn)
        popup.open()

    show_step(0)
# ─────────────────────────────────────────────────────────────────────────────


class BankrollManager:
    def __init__(self):
        self.session_profit = 0.0
        self.start_time_epoch = time.time()
        self.total_sessions = 0
        self.strategies = []
        self.load_tracker_state()
        self.load_strategies()

    def get_duration(self):
        elapsed = max(0, int(time.time() - self.start_time_epoch))
        mins, secs = divmod(elapsed, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def save_tracker_state(self):
        payload = {
            "session_profit": self.session_profit,
            "start_time_epoch": self.start_time_epoch,
            "total_sessions": self.total_sessions,
        }
        try:
            with open(get_tracker_file(), 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"save_tracker_state error: {e}")

    def load_tracker_state(self):
        try:
            with open(get_tracker_file(), 'r', encoding='utf-8') as f:
                raw = json.load(f)
            self.session_profit = float(raw.get("session_profit", 0.0))
            self.start_time_epoch = float(raw.get("start_time_epoch", time.time()))
            self.total_sessions = int(raw.get("total_sessions", 0))
        except Exception:
            self.session_profit = 0.0
            self.start_time_epoch = time.time()
            self.total_sessions = 0

    def reset_tracker_state(self):
        self.session_profit = 0.0
        self.start_time_epoch = time.time()
        self.total_sessions = 0
        self.save_tracker_state()

    def save_strategies(self):
        cleaned = [normalize_strategy(s) for s in self.strategies]
        try:
            with open(get_strategy_file(), 'w', encoding='utf-8') as f:
                json.dump(cleaned, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"save_strategies error: {e}")

    def load_strategies(self):
        try:
            with open(get_strategy_file(), 'r', encoding='utf-8') as f:
                raw = json.load(f)
                if isinstance(raw, list):
                    self.strategies = [normalize_strategy(s) for s in raw]
                else:
                    self.strategies = []
        except Exception:
            self.strategies = []

def normalize_strategy(raw):
    if not isinstance(raw, dict):
        raw = {}

    return {
        "name": str(raw.get("name", "Untitled Strategy")),
        "category": str(raw.get("category", "Manual Custom")),
        "game": str(raw.get("game", "general")),
        "source": str(raw.get("source", "manual")),
        "bank": str(raw.get("bank", "")),
        "base": str(raw.get("base", "")),
        "multi": str(raw.get("multi", "")),
        "win_action": str(raw.get("win_action", "Reset")),
        "loss_action": str(raw.get("loss_action", "")),
        "max_bets": str(raw.get("max_bets", "")),
        "created_at": str(raw.get("created_at", "")),
        "notes": str(raw.get("notes", "")),
    }


GLOBAL_BANK = BankrollManager()

DEMO = "demo"
PRO = "pro"
PRO_PLUS = "pro_plus"
LICENSE_SECRET = "ctp6_sh_2026_v1"
PUBLIC_KEY_PEM = """\
-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAzMmXgqCMEbS/AuRiFYTV2iFaSYmO7gCKC+OCkISzKG+huBMMI/p5
pSZmkynpN0Hn5FXGbthpaNKJ0CbAUGhUNjQeX03ZF7JVVguXUnRQNPHvikKxEB5X
06VHWQEGii+BkEjUkRkAnKIQObEl6z+Me/GIWPiLn0nkFQuBTkSOEqL6yUXnqCPv
DPkdoI+CX1DczOvLry8RJ+1EPFOE68dXez/IR0dQT8MhQmjm3inXCUMOhT/HxU9J
KxoDvkMT02qfpgAGaaV102/zL7Ii90ZQG6Q7oOu9iJMOopzWawO9P8C9wzVAvLhP
najA8MoRjxLuhCUiWgUmyyH1S0NJUxaofQIDAQAB
-----END RSA PUBLIC KEY-----
"""
PUBLIC_KEY_N = 25852022852892632977692566049765578908762307538611562693319874576805662800609467753524814707971304996423354716169138505307870061100734829427406974307886117955210911890548606570056405058758019025372077837783322483761045879158995734623238018992711217549190304213830775499574402769613830688604043005186088188535676126088546411514129221694380686741121785949203154225444688638128950647426181429080323724713868053016868251919605155604329460772294542748103098104778689755476552645341882975329325295183048269485137901714735440621133642092633469162402446463108482829439176065831912897252621810466121315146206135768608048326781
PUBLIC_KEY_E = 0

REVOCATION_URL = "https://raw.githubusercontent.com/therealwolfman97/casino-tools-revocations/main/revoked_licenses.json"
REVOCATION_FILE_NAME = "revoked_licenses.json"
REVOCATION_CHECK_HOURS = 24

FEATURE_TIERS = {
    "strats": PRO,
    "dice_sim": PRO,
    "dice": PRO,
    "mc": PRO,
    "dice_opt": PRO_PLUS,
    "dice_gen": PRO,
    "forge": PRO_PLUS,
    "dice_evo": PRO_PLUS,
    "limbo_evo": PRO_PLUS,
    "keno_evo": PRO_PLUS,
    "mines_evo": PRO_PLUS,
    "stress_lab": PRO,
    "survival_lab": PRO_PLUS,
    "keno_mc": PRO_PLUS,
    "mines": PRO,
    "bj": PRO,
    "sports_lab": PRO,
    "sports_kelly": PRO,
    "sports_parlay": PRO,
    "sports_value": PRO,
    "sports_arb": PRO,
    "compound": PRO,
    "pattern": PRO,
    "converter": DEMO,
}

TOOL_TITLES = {
    "strats": "Logic Templates",
    "dice_sim": "RNG Variance Engine",
    "dice": "Threshold Multiplier",
    "mc": "Monte Carlo Simulator",
    "dice_opt": "Model Efficiency Lab",
    "dice_gen": "Sequence Automator",
    "forge": "Logic Builder",
    "dice_evo": "Probability Evolution",
    "limbo_evo": "Exponential Growth Lab",
    "keno_evo": "Pattern Evolution",
    "mines_evo": "Grid-Risk Evolution",
    "stress_lab": "Strategy Stress Test",
    "survival_lab": "Capital Sustainability",
    "keno_mc": "Spatial Distribution Lab",
    "mines": "Grid-Risk Analyst",
    "bj": "Statistical Deck Engine",
    "sports_lab": "Athletic Data Lab",
    "sports_kelly": "Kelly Criterion Tool",
    "sports_parlay": "Compounded Risk Analyst",
    "sports_value": "Edge Discovery Tool",
    "sports_arb": "Market Convergence Calc",
    "compound": "Compound Growth",
    "pattern": "Pattern Master",
    "converter": "Crypto Converter",
}


PRESENTATION_APP_NAME = "Strategy Suite Pro"
PRESENTATION_SUBTITLE = "Advanced risk analytics toolkit"
PRESENTATION_MODE_FILE = "presentation_mode.json"
PRESENTATION_DARK = '#000000'
PRESENTATION_PANEL = '#10243a'
PRESENTATION_ACCENT = '#7ec8ff'
PRESENTATION_ACCENT_ALT = '#3d7fb1'
PRESENTATION_SECTION_TEXT = '#9dc7ea'

PRESENTATION_TOOL_TITLES = {
    "strats": "Logic Templates",
    "dice_sim": "RNG Variance Engine",
    "dice": "Threshold Multiplier",
    "mc": "Monte Carlo Simulator",
    "dice_opt": "Model Efficiency Lab",
    "dice_gen": "Sequence Automator",
    "forge": "Logic Builder",
    "dice_evo": "Probability Evolution",
    "limbo_evo": "Exponential Growth Lab",
    "keno_evo": "Pattern Evolution",
    "mines_evo": "Grid-Risk Evolution",
    "stress_lab": "Stress Test",
    "survival_lab": "Capital Sustainability",
    "keno_mc": "Spatial Distribution Lab",
    "mines": "Probability Path Analysis",
    "bj": "Statistical Deck Engine",
    "sports_lab": "Athletic Data Lab",
    "sports_kelly": "Kelly Criterion Tool",
    "sports_parlay": "Compounded Risk Analyst",
    "sports_value": "Edge Discovery Tool",
    "sports_arb": "Market Convergence Calc",
    "compound": "Compound Growth",
    "pattern": "Pattern Master",
    "converter": "Crypto Converter",
}

MENU_TILE_LABELS = {
    "strats": "Strategies\nLibrary",
    "dice_sim": "RNG Variance\nEngine",
    "dice": "Threshold\nMultiplier",
    "mc": "Monte Carlo\nSimulator",
    "dice_opt": "Model Efficiency Lab",
    "dice_gen": "Sequence\nAutomator",
    "forge": "Logic Builder",
    "dice_evo": "Probability\nEvolution",
    "limbo_evo": "Exponential Growth\nLab",
    "keno_evo": "Pattern\nEvolution",
    "mines_evo": "Risk Nodes Evolution",
    "stress_lab": "Stress Test",
    "survival_lab": "Capital Survival",
    "keno_mc": "Spatial Distribution Lab",
    "mines": "Grid-Risk Analyst",
    "bj": "Statistical Deck\nEngine",
    "sports_lab": "Athletic Data Lab",
    "sports_kelly": "Kelly Criterion\nTool",
    "sports_parlay": "Compounded Risk Analyst",
    "sports_value": "Edge Discovery\nTool",
    "sports_arb": "Market Convergence\nCalc",
    "compound": "Compound Growth",
    "pattern": "Pattern Master",
    "converter": "Crypto Converter",
}

PRESENTATION_MENU_TILE_LABELS = {
    "strats": "Logic\nTemplates",
    "dice_sim": "RNG Variance\nEngine",
    "dice": "Threshold\nMultiplier",
    "mc": "Monte Carlo\nSimulator",
    "dice_opt": "Model Efficiency\nLab",
    "dice_gen": "Sequence\nAutomator",
    "forge": "Logic Builder",
    "dice_evo": "Probability\nEvolution",
    "limbo_evo": "Exponential Growth\nLab",
    "keno_evo": "Pattern\nEvolution",
    "mines_evo": "Grid-Risk\nEvolution",
    "stress_lab": "Stress Test",
    "survival_lab": "Capital\nSustainability",
    "keno_mc": "Spatial Distribution\nLab",
    "mines": "Probability Path\nAnalysis",
    "bj": "Statistical Deck\nEngine",
    "sports_lab": "Athletic Data\nLab",
    "sports_kelly": "Kelly Criterion\nTool",
    "sports_parlay": "Compounded Risk\nAnalyst",
    "sports_value": "Edge Discovery\nTool",
    "sports_arb": "Market Convergence\nCalc",
    "compound": "Compound Growth",
    "pattern": "Pattern Master",
    "converter": "Crypto Converter",
}

MENU_SECTION_LABELS = {
    "evolution": "EVOLUTION LAB",
    "research": "RESEARCH LAB",
    "analytics": "PROBABILITY LAB",
    "sports": "MARKET MODELS",
    "utilities": "UTILITIES",
}

PRESENTATION_SECTION_LABELS = {
    "evolution": "EVOLUTION LAB",
    "research": "RESEARCH LAB",
    "analytics": "PROBABILITY LAB",
    "sports": "MARKET MODELS",
    "utilities": "UTILITIES",
}

def _normalize_title_key(text):
    txt = str(text or '').replace('\n', ' ').replace('/', ' ').replace('-', ' ')
    return ' '.join(txt.lower().split())


TOOL_TITLE_TO_SID = {}
for _sid, _label in TOOL_TITLES.items():
    TOOL_TITLE_TO_SID[_normalize_title_key(_label)] = _sid
for _sid, _label in PRESENTATION_TOOL_TITLES.items():
    TOOL_TITLE_TO_SID[_normalize_title_key(_label)] = _sid
for _sid, _label in MENU_TILE_LABELS.items():
    TOOL_TITLE_TO_SID[_normalize_title_key(_label)] = _sid
for _sid, _label in PRESENTATION_MENU_TILE_LABELS.items():
    TOOL_TITLE_TO_SID[_normalize_title_key(_label)] = _sid


def resolve_tool_sid_from_title(title_text):
    return TOOL_TITLE_TO_SID.get(_normalize_title_key(title_text), '')


def refresh_dynamic_presentation_titles(widget):
    if widget is None:
        return

    try:
        sid = getattr(widget, '_dynamic_title_sid', '')
        title_label = getattr(widget, '_dynamic_title_label', None)
        if sid and title_label is not None:
            title_label.text = get_tool_display_title(sid).upper()
    except Exception:
        pass

    try:
        direct_sid = getattr(widget, '_dynamic_title_sid', '')
        if direct_sid and isinstance(widget, Label) and not hasattr(widget, '_dynamic_title_label'):
            widget.text = get_tool_display_title(direct_sid).upper()
    except Exception:
        pass

    for child in getattr(widget, 'children', []) or []:
        refresh_dynamic_presentation_titles(child)

DEMO_LIMITS = {
    "strats_save": 2,
    "dice_sim_rolls": 50,
    "dice": 10,
    "mc": 10,
    "stress_lab": 3,
    "mines": 10,
    "bj": 15,
    "sports_kelly": 10,
    "sports_parlay": 5,
    "sports_value": 10,
    "sports_arb": 10,
    "compound": 10,
    "pattern": 10,
}

def get_license_file():
    return os.path.join(get_app_data_dir(), "license_state.json")

def get_demo_usage_file():
    return os.path.join(get_app_data_dir(), "demo_usage.json")

def get_device_file():
    return os.path.join(get_app_data_dir(), "device_identity.json")

def _load_json_file(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def _save_json_file(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"save json error: {e}")


def get_presentation_mode_file():
    return os.path.join(get_app_data_dir(), PRESENTATION_MODE_FILE)


def load_presentation_mode_state():
    raw = _load_json_file(get_presentation_mode_file(), {"enabled": False})
    return bool(raw.get('enabled', False))


def save_presentation_mode_state(enabled):
    _save_json_file(get_presentation_mode_file(), {"enabled": bool(enabled)})


def is_presentation_mode_active():
    app = App.get_running_app()
    if app and hasattr(app, 'is_presentation_mode_active'):
        try:
            return bool(app.is_presentation_mode_active())
        except Exception:
            return False
    return False


def get_display_unit_prefix():
    return 'U'


def get_display_app_name():
    return PRESENTATION_APP_NAME


def get_display_subtitle():
    return PRESENTATION_SUBTITLE


def clean_display_label(value):
    raw = str(value or '').strip()
    mapping = {
        'Dice': 'RNG', 'dice': 'RNG',
        'Limbo': 'Threshold', 'limbo': 'Threshold',
        'Keno': 'Spatial', 'keno': 'Spatial',
        'Mines': 'Grid-Risk', 'mines': 'Grid-Risk',
        'Sports': 'Market', 'sports': 'Market',
        'Blackjack': 'Statistical Deck', 'blackjack': 'Statistical Deck',
        'Dice Optimizer': 'Model Efficiency Lab',
        'Dice Auto Generator': 'Sequence Automator',
        'Dice Evolution': 'Probability Evolution',
        'Limbo Evolution': 'Exponential Growth Lab',
        'Keno Evolution': 'Pattern Evolution',
        'Mines Evolution': 'Grid-Risk Evolution',
        'Sports Betting Lab': 'Athletic Data Lab',
        'Kelly Calculator': 'Kelly Criterion Tool',
        'Arbitrage Calc': 'Market Convergence Calc',
        'Value Bet Calc': 'Edge Discovery Tool',
    }
    return mapping.get(raw, raw)


def get_tool_display_title(sid):
    sid = str(sid)
    return PRESENTATION_TOOL_TITLES.get(sid, TOOL_TITLES.get(sid, sid))


def get_title_display_from_text(title_text):
    sid = TOOL_TITLE_TO_SID.get(str(title_text).strip())
    if sid:
        return get_tool_display_title(sid)
    return str(title_text)

def get_device_code():
    stored = _load_json_file(get_device_file(), {})
    code = str(stored.get("device_code", "")).strip()
    if code:
        return code
    raw = ""
    try:
        if sys.platform == "android":
            from jnius import autoclass
            Secure = autoclass('android.provider.Settings$Secure')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            raw = Secure.getString(activity.getContentResolver(), Secure.ANDROID_ID) or ""
    except Exception:
        raw = ""
    if not raw:
        raw = f"fallback-{random.random()}-{time.time()}-{os.getpid()}"
    digest = hashlib.sha256((raw + "|casino_tools_pro_v6").encode()).hexdigest()[:8].upper()
    code = f"CTP6-DEV-{digest}"
    _save_json_file(get_device_file(), {"device_code": code})
    return code

def build_expected_license(tier, device_code=None):
    if device_code is None:
        device_code = get_device_code()
    tier = str(tier).strip().lower()
    if tier not in (PRO, PRO_PLUS):
        return ""
    device_suffix = device_code.split('-')[-1]
    tier_tag = "PRO" if tier == PRO else "PPLUS"
    payload = f"{tier}|{device_suffix}|casino_tools_pro"
    sig = hmac.new(LICENSE_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:12].upper()
    return f"CTP6-{tier_tag}-{device_suffix}-{sig}"

def verify_legacy_license_key(key, device_code=None):
    if device_code is None:
        device_code = get_device_code()
    cleaned = str(key).strip().upper().replace(" ", "")
    if cleaned == build_expected_license(PRO, device_code).upper():
        return True, PRO
    if cleaned == build_expected_license(PRO_PLUS, device_code).upper():
        return True, PRO_PLUS
    return False, DEMO

def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def parse_iso_ts(value):
    if not value:
        return None
    try:
        txt = str(value).strip()
        if txt.endswith('Z'):
            txt = txt[:-1] + '+00:00'
        return datetime.fromisoformat(txt).timestamp()
    except Exception:
        return None

def get_public_key_pem():
    pem = str(PUBLIC_KEY_PEM or '').strip()
    if 'BEGIN PUBLIC KEY' in pem or 'BEGIN RSA PUBLIC KEY' in pem:
        return pem
    return ''

def get_public_key():
    if rsa is None:
        return None
    try:
        if int(PUBLIC_KEY_N) > 0 and int(PUBLIC_KEY_E) > 0:
            return rsa.PublicKey(int(PUBLIC_KEY_N), int(PUBLIC_KEY_E))
    except Exception:
        pass
    pem = get_public_key_pem()
    if not pem:
        return None
    try:
        return rsa.PublicKey.load_pkcs1(pem.encode('utf-8'))
    except Exception:
        try:
            return rsa.PublicKey.load_pkcs1_openssl_pem(pem.encode('utf-8'))
        except Exception:
            return None

def canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')

def verify_signature(payload_dict, sig_b64):
    pub = get_public_key()
    if pub is None or rsa is None:
        return False
    try:
        padded = sig_b64 + ('=' * ((4 - len(sig_b64) % 4) % 4))
        sig = base64.urlsafe_b64decode(padded.encode('ascii'))
        rsa.verify(canonical_json(payload_dict), sig, pub)
        return True
    except Exception:
        return False

def decode_activation_code(code):
    cleaned = str(code).strip().replace('\n', '').replace(' ', '')
    if cleaned.startswith('CTP6A-'):
        cleaned = cleaned[6:]
    cleaned = cleaned.replace('.', '')
    cleaned += '=' * ((4 - len(cleaned) % 4) % 4)
    raw = base64.urlsafe_b64decode(cleaned.encode('ascii'))
    data = json.loads(zlib.decompress(raw).decode('utf-8'))
    return data.get('p', {}), data.get('s', '')

def verify_signed_license_key(key, device_code=None):
    if device_code is None:
        device_code = get_device_code()
    if rsa is None:
        return False, DEMO, 'rsa package not installed', {}
    if not str(key).strip().startswith('CTP6A-'):
        return False, DEMO, 'not signed code', {}
    if get_public_key() is None:
        return False, DEMO, 'public key not configured', {}
    try:
        payload, sig = decode_activation_code(key)
    except Exception:
        return False, DEMO, 'invalid activation code', {}
    if not verify_signature(payload, sig):
        return False, DEMO, 'signature check failed', {}
    if str(payload.get('app', 'casino_tools_pro')).strip() != 'casino_tools_pro':
        return False, DEMO, 'wrong app code', {}
    tier = str(payload.get('tier', DEMO)).strip().lower()
    if tier not in (PRO, PRO_PLUS):
        return False, DEMO, 'invalid tier', {}
    bound_device = str(payload.get('device_code', '')).strip()
    if bound_device and bound_device != str(device_code).strip():
        return False, DEMO, 'device code mismatch', {}
    expires_at = str(payload.get('expires_at', payload.get('expiry', ''))).strip()
    exp_ts = parse_iso_ts(expires_at)
    if exp_ts is not None and exp_ts < time.time():
        return False, DEMO, 'license expired', payload
    status = str(payload.get('status', 'active')).strip().lower()
    if status not in ('active', 'issued'):
        return False, DEMO, 'license is not active', payload
    return True, tier, 'ok', payload

def verify_license_key(key, device_code=None):
    if str(key).strip().startswith('CTP6A-'):
        ok, tier, msg, payload = verify_signed_license_key(key, device_code)
        return ok, tier, msg, payload
    ok, tier = verify_legacy_license_key(key, device_code)
    return ok, tier, ('ok' if ok else 'invalid legacy key'), {}

def verify_revocation_bundle(data):
    if rsa is None or get_public_key() is None:
        return False, {}
    try:
        payload = data.get('payload', {})
        signature = data.get('signature', '')
        if str(payload.get('app', 'casino_tools_pro')).strip() != 'casino_tools_pro':
            return False, {}
        if int(payload.get('version', 0)) != 1:
            return False, {}
        if not verify_signature(payload, signature):
            return False, {}
        return True, payload
    except Exception:
        return False, {}

class LicenseState:
    def __init__(self):
        self.tier = DEMO
        self.license_key = ''
        self.license_id = ''
        self.source = ''
        self.label = ''
        self.note = ''
        self.device_code = ''
        self.expires_at = ''
        self.issued_at = ''
        self.activated_at = ''
        self.status = 'demo'
        self.last_revocation_check = 0.0
        self.last_revocation_error = ''
        self.load()

    def load(self):
        raw = _load_json_file(get_license_file(), {})
        self.tier = str(raw.get('tier', DEMO)).strip().lower()
        if self.tier not in (DEMO, PRO, PRO_PLUS):
            self.tier = DEMO
        self.license_key = str(raw.get('license_key', '')).strip()
        self.license_id = str(raw.get('license_id', '')).strip()
        self.source = str(raw.get('source', '')).strip()
        self.label = str(raw.get('label', '')).strip()
        self.note = str(raw.get('note', '')).strip()
        self.device_code = str(raw.get('device_code', '')).strip()
        self.expires_at = str(raw.get('expires_at', '')).strip()
        self.issued_at = str(raw.get('issued_at', '')).strip()
        self.activated_at = str(raw.get('activated_at', '')).strip()
        self.status = str(raw.get('status', 'demo')).strip().lower()
        self.last_revocation_check = float(raw.get('last_revocation_check', 0.0) or 0.0)
        self.last_revocation_error = str(raw.get('last_revocation_error', '')).strip()

    def to_dict(self):
        return {
            'tier': self.tier,
            'license_key': self.license_key,
            'license_id': self.license_id,
            'source': self.source,
            'label': self.label,
            'note': self.note,
            'device_code': self.device_code,
            'expires_at': self.expires_at,
            'issued_at': self.issued_at,
            'activated_at': self.activated_at,
            'status': self.status,
            'last_revocation_check': self.last_revocation_check,
            'last_revocation_error': self.last_revocation_error,
        }

    def save(self):
        _save_json_file(get_license_file(), self.to_dict())

    def clear(self):
        self.tier = DEMO
        self.license_key = ''
        self.license_id = ''
        self.source = ''
        self.label = ''
        self.note = ''
        self.device_code = ''
        self.expires_at = ''
        self.issued_at = ''
        self.activated_at = ''
        self.status = 'demo'
        self.last_revocation_error = ''
        self.save()

    def activate(self, key):
        ok, tier, msg, payload = verify_license_key(key, get_device_code())
        if not ok:
            return False, DEMO, msg
        self.tier = tier
        self.license_key = str(key).strip()
        self.license_id = str(payload.get('license_id', 'LEGACY')).strip()
        self.source = str(payload.get('source', 'legacy')).strip()
        self.label = str(payload.get('label', '')).strip()
        self.note = str(payload.get('note', '')).strip()
        self.device_code = str(payload.get('device_code', get_device_code())).strip()
        self.expires_at = str(payload.get('expires_at', payload.get('expiry', ''))).strip()
        self.issued_at = str(payload.get('issued_at', '')).strip()
        self.activated_at = utc_now_iso()
        self.status = 'active'
        self.last_revocation_error = ''
        self.save()
        return True, tier, 'License activated successfully'

    def effective_tier(self):
        if self.status == 'revoked':
            return DEMO
        if self.expires_at:
            exp_ts = parse_iso_ts(self.expires_at)
            if exp_ts is not None and exp_ts < time.time():
                return DEMO
        return self.tier

    def revoked_or_expired_message(self):
        if self.status == 'revoked':
            return 'License revoked'
        if self.expires_at:
            exp_ts = parse_iso_ts(self.expires_at)
            if exp_ts is not None and exp_ts < time.time():
                return 'License expired'
        return ''

    def needs_revocation_check(self):
        if not self.license_id or not REVOCATION_URL or get_public_key() is None:
            return False
        return (time.time() - float(self.last_revocation_check or 0.0)) >= (REVOCATION_CHECK_HOURS * 3600)

    def apply_revocation_bundle(self, data):
        ok, payload = verify_revocation_bundle(data)
        self.last_revocation_check = time.time()
        if not ok:
            self.last_revocation_error = 'Invalid revocation bundle'
            self.save()
            return False, 'invalid bundle'
        revoked_ids = set(str(x).strip() for x in payload.get('revoked_ids', []))
        if self.license_id and self.license_id in revoked_ids:
            self.status = 'revoked'
            self.last_revocation_error = ''
            self.save()
            return True, 'revoked'
        self.last_revocation_error = ''
        self.save()
        return True, 'ok'

def show_revoked_popup():
    content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))

    msg = Label(
        text="License revoked.\nContact support for assistance.",
        color=get_color_from_hex(STAKE_TEXT),
        halign='center'
    )

    btn = StyledButton(text="OK", bg_color=STAKE_GREEN)

    content.add_widget(msg)
    content.add_widget(btn)

    popup = Popup(title="License Status", content=content, size_hint=(0.8, 0.35))

    def close_and_reset(*args):
        LICENSE_STATE.clear()
        popup.dismiss()

    btn.bind(on_release=close_and_reset)
    popup.open()


def fetch_and_apply_revocation(force=True, on_complete=None):
    app = App.get_running_app()
    if app and hasattr(app, 'run_revocation_check'):
        app.run_revocation_check(force=force, on_complete=on_complete)
        return

    def worker():
        ok = False
        message = 'License status check failed'
        try:
            if not LICENSE_STATE.license_id:
                message = 'No activated license to check'
            else:
                res = requests.get(REVOCATION_URL, timeout=10, verify=certifi.where())
                res.raise_for_status()
                data = res.json()
                ok, status = LICENSE_STATE.apply_revocation_bundle(data)
                if ok and status == 'revoked':
                    message = 'License revoked'
                    _ui_call(show_revoked_popup)
                elif ok:
                    message = LICENSE_STATE.revoked_or_expired_message() or 'License active'
                else:
                    message = 'Invalid revocation bundle'
        except Exception as e:
            LICENSE_STATE.last_revocation_check = time.time()
            LICENSE_STATE.last_revocation_error = str(e)
            LICENSE_STATE.save()
            message = f'Check failed: {e}'
        if on_complete:
            _ui_call(on_complete, ok, message)

    threading.Thread(target=worker, daemon=True).start()

class DemoUsageManager:
    def __init__(self):
        self.usage = {}
        self.load()

    def load(self):
        raw = _load_json_file(get_demo_usage_file(), {})
        self.usage = {str(k): int(v) for k, v in raw.items() if str(k) in DEMO_LIMITS}

    def save(self):
        _save_json_file(get_demo_usage_file(), self.usage)
        app = App.get_running_app()
        if app and hasattr(app, 'refresh_status_labels'):
            Clock.schedule_once(lambda dt: app.refresh_status_labels(), 0)

    def get_used(self, key):
        return int(self.usage.get(key, 0))

    def remaining(self, key):
        limit = DEMO_LIMITS.get(key, 0)
        return max(0, limit - self.get_used(key))

    def can_use(self, key, amount=1):
        if key not in DEMO_LIMITS:
            return True
        return self.get_used(key) + amount <= DEMO_LIMITS[key]

    def consume(self, key, amount=1):
        if key not in DEMO_LIMITS:
            return True
        if not self.can_use(key, amount):
            return False
        self.usage[key] = self.get_used(key) + amount
        self.save()
        return True

LICENSE_STATE = LicenseState()
DEMO_USAGE = DemoUsageManager()

def show_upgrade_popup(title, required_tier=PRO, reason="Preview mode only."):
    content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
    title = get_title_display_from_text(title)
    msg = Label(text=f"{title}\n\n{reason}\n\nUpgrade to {'Pro+' if required_tier == PRO_PLUS else 'Pro'} to use this tool.",
                color=get_color_from_hex(STAKE_TEXT), halign='center', valign='middle')
    msg.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
    row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
    close_btn = StyledButton(text='CLOSE', bg_color=UTILITY_COLOR)
    close_btn.color = (1,1,1,1)
    license_btn = StyledButton(text='LICENSE', bg_color=STAKE_GREEN)
    row.add_widget(close_btn)
    row.add_widget(license_btn)
    content.add_widget(msg)
    content.add_widget(row)
    popup = Popup(title='Upgrade Required', content=content, size_hint=(0.86, 0.42))
    close_btn.bind(on_release=lambda *a: popup.dismiss())
    license_btn.bind(on_release=lambda *a: (popup.dismiss(), App.get_running_app().show_license_popup()))
    popup.open()

# --- Shared UI Components ---
class StyledInput(TextInput):
    def __init__(self, **kwargs):
        kwargs.setdefault('multiline', False)
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(38)
        self.background_color = get_color_from_hex(STAKE_INPUT)
        self.foreground_color = (1, 1, 1, 1)
        self.padding = [dp(10), dp(8)]
        self.cursor_color = get_color_from_hex(STAKE_GREEN)
        self.font_size = '13sp'


class StyledButton(Button):
    def __init__(self, **kwargs):
        color_hex = kwargs.pop('bg_color', STAKE_GREEN)
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(42)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)  # transparent — drawn by canvas
        self.bold = True
        self.color = (0, 0, 0, 1) if color_hex == STAKE_GREEN else (1, 1, 1, 1)
        self._btn_color_hex = color_hex
        with self.canvas.before:
            Color(rgba=get_color_from_hex(color_hex))
            self._btn_bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        def _upd_btn(inst, val):
            inst._btn_bg.pos = inst.pos
            inst._btn_bg.size = inst.size
        self.bind(pos=_upd_btn, size=_upd_btn)


class SimpleNav(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(50)
        self.padding = [0, dp(5)]
        btn = StyledButton(text="BACK TO HOME", bg_color=STAKE_INPUT)
        btn.color = get_color_from_hex(STAKE_GREEN)
        btn.bind(on_release=lambda x: setattr(App.get_running_app().root, 'current', 'menu'))
        self.add_widget(btn)


def show_info_popup(title, message):
    content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))
    scroll = ScrollView()
    body = Label(
        text=message,
        color=get_color_from_hex(STAKE_TEXT),
        font_size='13sp',
        halign='left',
        valign='top',
        size_hint_y=None,
    )

    def _refresh(*_args):
        width = max(dp(220), scroll.width - dp(20))
        body.text_size = (width, None)
        body.texture_update()
        body.height = max(dp(180), body.texture_size[1] + dp(12))

    scroll.bind(size=lambda *_: _refresh())
    body.bind(texture_size=lambda *_: _refresh())
    Clock.schedule_once(lambda dt: _refresh(), 0)
    scroll.add_widget(body)
    content.add_widget(scroll)

    ok_btn = StyledButton(text='OK', bg_color=STAKE_GREEN, height=dp(40))
    popup = Popup(title=title, content=content, size_hint=(0.9, 0.72))
    ok_btn.bind(on_release=lambda *_: popup.dismiss())
    content.add_widget(ok_btn)
    popup.open()


def build_info_header(title_text, help_text=None):
    row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
    title = Label(
        text=title_text,
        font_size='20sp',
        bold=True,
        color=get_color_from_hex(STAKE_GREEN),
        halign='left',
        valign='middle',
    )
    title.bind(size=lambda instance, value: setattr(instance, 'text_size', value))
    row.add_widget(title)

    row._dynamic_title_sid = resolve_tool_sid_from_title(title_text)
    row._dynamic_title_label = title

    if help_text:
        help_btn = StyledButton(text='!', bg_color='#2c3e50', height=dp(36), size_hint_x=None, width=dp(42))
        help_btn.color = (1, 1, 1, 1)
        help_btn.bind(
            on_release=lambda *_: show_info_popup(
                get_tool_display_title(row._dynamic_title_sid).upper() if getattr(row, '_dynamic_title_sid', '') else title_text,
                help_text
            )
        )
        row.add_widget(help_btn)
    return row


def apply_result_card_style(widget):
    """Apply a dark card background with green left border to a result container widget."""
    def _update(instance, value):
        if hasattr(instance, '_rc_bg'):
            instance._rc_bg.pos = instance.pos
            instance._rc_bg.size = instance.size
        if hasattr(instance, '_rc_bar'):
            instance._rc_bar.pos = instance.pos
            instance._rc_bar.size = (dp(4), instance.height)
    with widget.canvas.before:
        Color(rgba=get_color_from_hex(STAKE_INPUT))
        widget._rc_bg = Rectangle(pos=widget.pos, size=widget.size)
        Color(rgba=get_color_from_hex(STAKE_GREEN))
        widget._rc_bar = Rectangle(pos=widget.pos, size=(dp(4), widget.height))
    widget.bind(pos=_update, size=_update)


def clear_input_widgets(*groups):
    def _walk(item):
        if item is None:
            return
        if isinstance(item, dict):
            for value in item.values():
                yield from _walk(value)
            return
        if isinstance(item, (list, tuple, set)):
            for value in item:
                yield from _walk(value)
            return
        yield item

    for widget in _walk(groups):
        try:
            if hasattr(widget, 'text'):
                widget.text = ''
        except Exception:
            pass


MONTE_CARLO_HELP = """Monte Carlo simulates the same analytical setup across many sessions so you can see how it behaves over time.

Recommended defaults:
• Number of Sessions: 5,000 for balanced testing
• Max Entries / Session: 100 for standard testing, 200 for deeper testing
• Increase on Negative Result % should match the progression you plan to test
• Stop Net Units / Stop Deficit can stay at 0 if you want an uncapped session

Multiplier and Positive Event are linked using the app's 99 / multiplier rule, so changing the multiplier auto-fills win chance."""

STRATEGY_FORGE_HELP = """Strategy Forge searches for promising strategy templates before you save them to the library.

Key fields:
• Population Size: how many candidate strategies exist in each generation
• Generations: how many improvement rounds are run
• Elite Keep: how many top strategies survive unchanged each generation
• Children Per Generation: how many new variants are created each round
• Sessions / Strategy: how many simulations each candidate gets
• Max Entries / Session: session length cap
• Top Results: how many finalists are shown at the end

Balanced starting point: Population 24, Generations 6, Elite Keep 6, Children 24, Sessions 400."""

DICE_EVO_HELP = """Probability Evolution mutates and ranks RNG progressions across generations.

Use it when you want the app to evolve stronger RNG setups automatically.

Key fields:
• Positive Event %: base hit chance used for all simulated strategies
• Population Size: strategies per generation
• Generations: number of evolution rounds
• Elite Keep: best strategies carried forward unchanged
• Children Per Generation: new mutated strategies created each round
• Sessions / Strategy: tests per strategy
• Max Entries / Session: practical cap for each simulation
• Top Results: how many final winners are displayed

Balanced default: Population 40, Generations 5, Elite 8, Children 40, Sessions 2,000."""

LIMBO_EVO_HELP = """Exponential Growth Lab evolves threshold-multiplier strategies across generations.

It works like Probability Evolution, but the event probability is derived from each target multiplier.

Use higher Sessions / Strategy for more stable rankings, and increase Max Entries / Session for long recovery systems."""

KENO_EVO_HELP = """Pattern Evolution evolves grid-distribution setups using tiles, target samples, progression and selection pressure.

Population, Generations, Elite Keep and Children Per Generation control how broad and how deep the search becomes.
Sessions / Strategy controls reliability, while Max Entries / Session caps how long each simulated run can recover."""

MINES_EVO_HELP = """Grid-Risk Evolution evolves grid-risk setups using risk-node count, clear-pick logic and progression rules.

Use it to search for high-quality grid-risk combinations automatically, then save the strongest results to the strategy library.

Higher Sessions / Strategy improves confidence; higher Max Entries / Session allows deeper recovery paths."""

def analyze_strategy_rating(strategy):
    s = normalize_strategy(strategy)
    notes = str(s.get("notes", "") or "")

    avg_profit = 0.0
    bust_rate = 0.0

    try:
        if "Avg " in notes:
            avg_part = notes.split("Avg ", 1)[1].split(" |", 1)[0].strip()
            avg_profit = float(avg_part)
    except Exception:
        avg_profit = 0.0

    try:
        if "Threshold " in notes:
            bust_part = notes.split("Threshold ", 1)[1].split("%", 1)[0].strip()
            bust_rate = float(bust_part)
    except Exception:
        bust_rate = 0.0

    rating = max(0.0, min(10.0, (avg_profit * 1.2) - (bust_rate * 0.15) + 5.0))

    if bust_rate <= 0.10:
        risk = "Safe"
        color = STAKE_GREEN
    elif bust_rate <= 1.00:
        risk = "Balanced"
        color = "#f1c40f"
    elif bust_rate <= 3.00:
        risk = "Aggressive"
        color = "#e67e22"
    else:
        risk = "Extreme"
        color = STAKE_RED

    return {
        "avg_profit": avg_profit,
        "bust_rate": bust_rate,
        "rating": round(rating, 2),
        "risk": risk,
        "color": color,
    }

# --- Strategy Library Screen ---
class StrategyLibraryScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        self.selected_category = "All"
        self._compare_selected = None   # holds first strategy chosen for comparison
        self._compare_label = None      # status label shown at top during compare mode

        self.layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        self.header_label = Label(
            text=get_tool_display_title('strats').upper(),
            font_size='20sp',
            bold=True,
            color=get_color_from_hex(STAKE_GREEN),
            size_hint_y=None,
            height=dp(40)
        )
        self.header_label._dynamic_title_sid = 'strats'
        self.layout.add_widget(self.header_label)

        filter_row = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(42))
        filter_row.add_widget(Label(
            text="Category",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='12sp'
        ))

        self.category_spinner = Spinner(
            text='All',
            values=(
                'All',
                'Model Efficiency Lab',
                'Sequence Automator',
                'Spatial',
                'Grid-Risk',
                'Manual Custom',
                'Experimental',
                'Imported'
            ),
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex(STAKE_INPUT),
            color=(1, 1, 1, 1)
        )
        self.category_spinner.bind(text=self.on_category_change)
        filter_row.add_widget(self.category_spinner)
        self.layout.add_widget(filter_row)

        self.scroll = ScrollView()
        self.strat_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(12))
        self.strat_list.bind(minimum_height=self.strat_list.setter('height'))
        self.scroll.add_widget(self.strat_list)
        self.layout.add_widget(self.scroll)

        btn_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))

        add_btn = StyledButton(text="NEW STRAT", bg_color=STAKE_GREEN, size_hint_x=0.5)
        add_btn.bind(on_release=self.show_add_popup)

        export_btn = StyledButton(text="EXPORT TXT", bg_color=UTILITY_COLOR, size_hint_x=0.5)
        export_btn.color = (1, 1, 1, 1)
        export_btn.bind(on_release=self.export_to_txt)

        btn_box.add_widget(add_btn)
        btn_box.add_widget(export_btn)
        self.layout.add_widget(btn_box)

        # Compare mode status bar
        self._compare_label = Label(
            text="",
            color=get_color_from_hex(LIMBO_COLOR),
            font_size='11sp',
            bold=True,
            size_hint_y=None,
            height=dp(0),
            halign='center',
            valign='middle',
        )
        self._compare_label.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        self.layout.add_widget(self._compare_label)

        self.layout.add_widget(SimpleNav())
        self.add_widget(self.layout)

    def get_game_color(self, game):
        game = str(game).lower().strip()
        if game == 'dice':
            return DICE_COLOR
        if game == 'limbo':
            return LIMBO_COLOR
        if game == 'keno':
            return KENO_COLOR
        if game == 'mines':
            return MINES_COLOR
        if game == 'sports':
            return SPORTS_COLOR
        return UTILITY_COLOR

    def on_pre_enter(self, *args):
        refresh_dynamic_presentation_titles(self)
        self.refresh_list()

    def on_category_change(self, instance, value):
        self.selected_category = value
        self.refresh_list()

    def get_filtered_strategies(self):
        normalized = [normalize_strategy(s) for s in GLOBAL_BANK.strategies]
        if self.selected_category == "All":
            return normalized
        return [s for s in normalized if s.get("category", "Manual Custom") == self.selected_category]

    def refresh_list(self, *args):
        self.strat_list.clear_widgets()
        filtered = self.get_filtered_strategies()

        if not filtered:
            self.strat_list.add_widget(Label(
                text="No strategies in this category",
                color=get_color_from_hex(STAKE_TEXT),
                size_hint_y=None,
                height=dp(40)
            ))
            return

        for index, s in enumerate(GLOBAL_BANK.strategies):
            s = normalize_strategy(s)
            if self.selected_category != "All" and s["category"] != self.selected_category:
                continue

            game_name = s.get('game', 'other')
            stripe_color = self.get_game_color(game_name)
            analysis = analyze_strategy_rating(s)

            card = BoxLayout(
                orientation='vertical',
                size_hint_y=None,
                height=dp(305),
                padding=dp(10),
                spacing=dp(5)
            )

            def update_card_rect(instance, value):
                if hasattr(instance, '_bg_rect'):
                    instance._bg_rect.pos = instance.pos
                    instance._bg_rect.size = instance.size
                if hasattr(instance, '_stripe_rect'):
                    instance._stripe_rect.pos = instance.pos
                    instance._stripe_rect.size = (dp(5), instance.height)

            with card.canvas.before:
                Color(rgba=get_color_from_hex(STAKE_INPUT))
                card._bg_rect = Rectangle(pos=card.pos, size=card.size)
                Color(rgba=get_color_from_hex(stripe_color))
                card._stripe_rect = Rectangle(pos=card.pos, size=(dp(5), card.height))

            card.bind(pos=update_card_rect, size=update_card_rect)

            title_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))

            badge = Label(
                text=game_name.upper(),
                size_hint_x=None,
                width=dp(68),
                bold=True,
                color=(0, 0, 0, 1) if stripe_color != UTILITY_COLOR else (1, 1, 1, 1)
            )
            with badge.canvas.before:
                Color(rgba=get_color_from_hex(stripe_color))
                badge._bg_rect = Rectangle(pos=badge.pos, size=badge.size)

            def _update_badge(instance, value):
                if hasattr(instance, '_bg_rect'):
                    instance._bg_rect.pos = instance.pos
                    instance._bg_rect.size = instance.size

            badge.bind(pos=_update_badge, size=_update_badge)

            name_lbl = Label(
                text=s['name'].upper(),
                bold=True,
                color=get_color_from_hex(analysis['color']),
                halign='left'
            )

            rename_btn = Button(
                text='RENAME',
                size_hint_x=None,
                width=dp(72),
                background_color=(0,0,0,0),
                background_normal='',
                font_size='10sp',
                bold=True
            )
            with rename_btn.canvas.before:
                Color(rgba=get_color_from_hex(UTILITY_COLOR))
                rename_btn._rbg = RoundedRectangle(pos=rename_btn.pos, size=rename_btn.size, radius=[dp(8)])
            rename_btn.bind(
                pos=lambda i,v: setattr(i._rbg,'pos',v),
                size=lambda i,v: setattr(i._rbg,'size',v)
            )
            rename_btn.bind(on_release=lambda x, i=index: self.show_rename_popup(i))

            del_btn = Button(
                text='X',
                size_hint_x=None,
                width=dp(30),
                background_color=(0,0,0,0),
                background_normal=''
            )
            with del_btn.canvas.before:
                Color(rgba=get_color_from_hex(SOFT_RED))
                del_btn._dbg = RoundedRectangle(pos=del_btn.pos, size=del_btn.size, radius=[dp(8)])
            del_btn.bind(
                pos=lambda i,v: setattr(i._dbg,'pos',v),
                size=lambda i,v: setattr(i._dbg,'size',v)
            )
            del_btn.bind(on_release=lambda x, i=index: self.delete_strat(i))

            title_row.add_widget(badge)
            title_row.add_widget(name_lbl)
            title_row.add_widget(rename_btn)
            title_row.add_widget(del_btn)
            card.add_widget(title_row)

            meta_row = GridLayout(cols=2, spacing=dp(2), size_hint_y=None, height=dp(66))
            for txt, col in [
                (f"Category: {s['category']}", STAKE_TEXT),
                (f"Model: {clean_display_label(s['game'])}", STAKE_TEXT),
                (f"Source: {s['source']}", STAKE_TEXT),
                (f"Max Entries: {s['max_bets'] or '--'}", STAKE_TEXT),
                (f"Rating: {analysis['rating']}/10", STAKE_GREEN),
                (f"Risk: {analysis['risk']}", analysis['color'])
            ]:
                meta_row.add_widget(Label(text=txt, font_size='11sp', color=get_color_from_hex(col)))
            card.add_widget(meta_row)

            grid = GridLayout(cols=2, spacing=dp(2), size_hint_y=None, height=dp(52))
            details = [
                f"Bank: {s['bank']}",
                f"Multi: {s['multi']}x",
                f"Base: {s['base']}",
                f"Positive: {s['win_action']}",
                f"Negative: {s['loss_action']}"
            ]
            for d in details:
                grid.add_widget(Label(text=d, font_size='11sp', color=get_color_from_hex(STAKE_TEXT)))
            card.add_widget(grid)

            notes_lbl = Label(
                text=f"Note: {s.get('notes', '')}",
                font_size='10sp',
                italic=True,
                color=get_color_from_hex(SUBTITLE_TEXT),
                size_hint_y=None,
                height=dp(34),
                text_size=(Window.width - dp(40), None),
                halign='left'
            )
            card.add_widget(notes_lbl)

            actions = BoxLayout(size_hint_y=None, height=dp(70), spacing=dp(5), orientation='vertical')
            row_a = BoxLayout(spacing=dp(5))
            run_sim = Button(text='RUN SIM', background_color=(0,0,0,0), background_normal='', font_size='11sp', bold=True)
            with run_sim.canvas.before:
                Color(rgba=get_color_from_hex('#2980b9'))
                run_sim._rsbg = RoundedRectangle(pos=run_sim.pos, size=run_sim.size, radius=[dp(8)])
            run_sim.bind(pos=lambda i,v: setattr(i._rsbg,'pos',v), size=lambda i,v: setattr(i._rsbg,'size',v))
            run_sim.bind(on_release=lambda x, data=s: self.run_in_sim(data))
            run_calc = Button(text='RUN CALC', background_color=(0,0,0,0), background_normal='', font_size='11sp', bold=True)
            with run_calc.canvas.before:
                Color(rgba=get_color_from_hex('#8e44ad'))
                run_calc._rcbg = RoundedRectangle(pos=run_calc.pos, size=run_calc.size, radius=[dp(8)])
            run_calc.bind(pos=lambda i,v: setattr(i._rcbg,'pos',v), size=lambda i,v: setattr(i._rcbg,'size',v))
            run_calc.bind(on_release=lambda x, data=s: self.run_in_calc(data))
            row_a.add_widget(run_sim)
            row_a.add_widget(run_calc)

            row_b = BoxLayout(spacing=dp(5))
            stress_btn = Button(text='STRESS TEST', background_color=(0,0,0,0), background_normal='', font_size='11sp', bold=True)
            with stress_btn.canvas.before:
                Color(rgba=get_color_from_hex(UTILITY_COLOR))
                stress_btn._stbg = RoundedRectangle(pos=stress_btn.pos, size=stress_btn.size, radius=[dp(8)])
            stress_btn.bind(pos=lambda i,v: setattr(i._stbg,'pos',v), size=lambda i,v: setattr(i._stbg,'size',v))
            stress_btn.bind(on_release=lambda x, data=s: self.run_in_stress(data))
            compare_btn = Button(text='COMPARE', background_color=(0,0,0,0), background_normal='', font_size='11sp', bold=True, color=(1,1,1,1))
            with compare_btn.canvas.before:
                Color(rgba=get_color_from_hex(LIMBO_COLOR))
                compare_btn._cpbg = RoundedRectangle(pos=compare_btn.pos, size=compare_btn.size, radius=[dp(8)])
            compare_btn.bind(pos=lambda i,v: setattr(i._cpbg,'pos',v), size=lambda i,v: setattr(i._cpbg,'size',v))
            compare_btn.bind(on_release=lambda x, data=s: self.select_for_compare(data))
            row_b.add_widget(stress_btn)
            row_b.add_widget(compare_btn)

            actions.add_widget(row_a)
            actions.add_widget(row_b)
            card.add_widget(actions)

            self.strat_list.add_widget(card)



    def show_rename_popup(self, index):
        if not (0 <= index < len(GLOBAL_BANK.strategies)):
            return
        current = normalize_strategy(GLOBAL_BANK.strategies[index])
        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
        content.add_widget(Label(
            text='Rename strategy',
            color=get_color_from_hex(STAKE_TEXT),
            size_hint_y=None,
            height=dp(24)
        ))
        name_input = StyledInput(text=current.get('name', ''))
        content.add_widget(name_input)

        btn_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        save_btn = StyledButton(text='SAVE', bg_color=STAKE_GREEN)
        cancel_btn = StyledButton(text='CANCEL', bg_color=UTILITY_COLOR)
        cancel_btn.color = (1, 1, 1, 1)
        btn_row.add_widget(save_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        popup = Popup(title='Rename Strategy', content=content, size_hint=(0.86, 0.34))

        def do_save(*args):
            new_name = str(name_input.text).strip()
            if new_name:
                strategy = normalize_strategy(GLOBAL_BANK.strategies[index])
                strategy['name'] = new_name
                GLOBAL_BANK.strategies[index] = strategy
                GLOBAL_BANK.save_strategies()
                self.refresh_list()
            popup.dismiss()

        save_btn.bind(on_release=do_save)
        cancel_btn.bind(on_release=lambda *a: popup.dismiss())
        popup.open()

    def run_in_stress(self, data):
        data = normalize_strategy(data)
        stress_screen = App.get_running_app().root.get_screen('stress_lab')
        stress_screen.load_strategy(data)
        App.get_running_app().root.current = 'stress_lab'

    def delete_strat(self, index):
        if 0 <= index < len(GLOBAL_BANK.strategies):
            GLOBAL_BANK.strategies.pop(index)
            GLOBAL_BANK.save_strategies()
            self.refresh_list()

    def export_to_txt(self, *args):
        try:
            filename = "exported_strategies.txt"
            with open(filename, "w") as f:
                f.write("=== STRATEGY SUITE PRO EXPORT ===\n\n")
                for raw in GLOBAL_BANK.strategies:
                    s = normalize_strategy(raw)
                    f.write(f"NAME: {s['name']}\n")
                    f.write(f"Category: {clean_display_label(s['category'])} | Model: {clean_display_label(s['game'])} | Source: {s['source']}\n")
                    f.write(f"Capital: {s['bank']} | Multiplier: {s['multi']}x | Base Entry: {s['base']} | Max Entries: {s['max_bets']}\n")
                    f.write(f"Positive Action: {s['win_action']} | Negative Action: {s['loss_action']}\n")
                    f.write(f"Notes: {s.get('notes', '')}\n")
                    f.write("-" * 40 + "\n")
            Popup(title='Success', content=Label(text=f"Saved to {filename}"), size_hint=(0.6, 0.2)).open()
        except Exception as e:
            Popup(title='Error', content=Label(text=str(e)), size_hint=(0.6, 0.2)).open()

    def run_in_sim(self, data):
        data = normalize_strategy(data)
        sim_screen = App.get_running_app().root.get_screen('dice_sim')
        sim_screen.balance_input.text = str(data['bank'] or '1000')
        sim_screen.change_balance()
        sim_screen.bet_input.text = str(data['base'] or '1')
        try:
            sim_screen.multi_input.text = str(data['multi'] or '2.0')
            sim_screen.on_manual_multi_change()
        except Exception:
            pass
        try:
            val = str(data['loss_action']).split(' ')[1].replace('%', '')
            if hasattr(sim_screen, 'auto_inputs') and 'Negative+%' in sim_screen.auto_inputs:
                sim_screen.auto_inputs['Negative+%'].text = val
        except Exception:
            pass
        App.get_running_app().root.current = 'dice_sim'

    def run_in_calc(self, data):
        data = normalize_strategy(data)
        calc_screen = App.get_running_app().root.get_screen('dice')
        calc_screen.inputs['Balance'].text = str(data['bank'] or '1')
        calc_screen.inputs['Base Entry'].text = str(data['base'] or '0.00015')
        calc_screen.inputs['Multiplier'].text = str(data['multi'] or '2.0')
        try:
            val = str(data['loss_action']).split(' ')[1].replace('%', '')
            calc_screen.inputs['Increase on Negative Result %'].text = val
        except Exception:
            calc_screen.inputs['Increase on Negative Result %'].text = '0'
        calc_screen.calculate()
        App.get_running_app().root.current = 'dice'

    # ── Strategy Comparison ───────────────────────────────────────────────────
    def select_for_compare(self, data):
        data = normalize_strategy(data)
        if self._compare_selected is None:
            # First selection
            self._compare_selected = data
            self._compare_label.height = dp(26)
            self._compare_label.text = f"COMPARE: '{data['name'][:28]}' selected — tap COMPARE on a 2nd strategy"
        else:
            # Second selection — run comparison
            strat_a = self._compare_selected
            strat_b = data
            self._compare_selected = None
            self._compare_label.height = dp(0)
            self._compare_label.text = ""
            self._run_comparison(strat_a, strat_b)

    def _extract_params(self, s):
        """Pull simulation parameters from a normalized strategy dict."""
        bankroll  = safe_float(s.get('bank', '20'), 20)
        base_bet  = safe_float(s.get('base', '0.1'), 0.1)
        multi     = safe_float(s.get('multi', '2.0'), 2.0)
        win_chance = max(0.01, min(99.99, 99.0 / max(1.01, multi)))
        loss_str  = str(s.get('loss_action', ''))
        inc_loss  = 0.0
        try:
            if 'Increase' in loss_str:
                inc_loss = float(loss_str.split('Increase', 1)[1].replace('%', '').strip())
        except Exception:
            inc_loss = 0.0
        max_bets  = safe_int(s.get('max_bets', '12'), 12)
        if max_bets <= 0:
            max_bets = 12
        return bankroll, base_bet, multi, win_chance, inc_loss, max_bets

    def _run_comparison(self, strat_a, strat_b):
        """Run MC for both strategies in a background thread then show results."""
        SESSIONS = 5000

        # Show a loading popup while running
        loading_content = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(10))
        loading_content.add_widget(Label(
            text="Running comparison...\nThis may take a few seconds.",
            color=get_color_from_hex(STAKE_TEXT),
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(60),
        ))
        loading_popup = Popup(
            title='Strategy Comparison',
            content=loading_content,
            size_hint=(0.78, 0.30),
            separator_color=get_color_from_hex(LIMBO_COLOR),
        )
        loading_popup.open()

        def worker():
            try:
                bk_a, bb_a, mu_a, wc_a, il_a, mb_a = self._extract_params(strat_a)
                res_a = MonteCarloEngine.run_sessions(
                    bankroll=bk_a, base_bet=bb_a, multiplier=mu_a,
                    win_chance=wc_a, inc_on_win=0, inc_on_loss=il_a,
                    stop_profit=0, stop_loss=0, max_bets=mb_a, sessions=SESSIONS,
                )
                bk_b, bb_b, mu_b, wc_b, il_b, mb_b = self._extract_params(strat_b)
                res_b = MonteCarloEngine.run_sessions(
                    bankroll=bk_b, base_bet=bb_b, multiplier=mu_b,
                    win_chance=wc_b, inc_on_win=0, inc_on_loss=il_b,
                    stop_profit=0, stop_loss=0, max_bets=mb_b, sessions=SESSIONS,
                )
            except Exception as e:
                _ui_call(loading_popup.dismiss)
                _ui_call(self._show_compare_error, str(e))
                return
            _ui_call(loading_popup.dismiss)
            _ui_call(self._show_comparison_popup, strat_a, strat_b, res_a, res_b, SESSIONS)

        threading.Thread(target=worker, daemon=True).start()

    def _show_compare_error(self, msg):
        Popup(
            title='Comparison Error',
            content=Label(text=msg, color=get_color_from_hex(STAKE_RED)),
            size_hint=(0.78, 0.28),
        ).open()

    def _show_comparison_popup(self, sa, sb, ra, rb, sessions):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        # Header row
        header = GridLayout(cols=3, size_hint_y=None, height=dp(42), spacing=dp(4))
        header.add_widget(Label(text='Metric', color=get_color_from_hex(STAKE_TEXT), font_size='11sp', bold=True))
        header.add_widget(Label(
            text=sa['name'][:20],
            color=get_color_from_hex(LIMBO_COLOR),
            font_size='11sp', bold=True,
            halign='center', valign='middle',
        ))
        header.add_widget(Label(
            text=sb['name'][:20],
            color=get_color_from_hex(MINES_COLOR),
            font_size='11sp', bold=True,
            halign='center', valign='middle',
        ))
        content.add_widget(header)

        # Divider
        div = Widget(size_hint_y=None, height=dp(1))
        with div.canvas.before:
            Color(rgba=get_color_from_hex(DIVIDER_COLOR))
            div._bg = Rectangle(pos=div.pos, size=div.size)
        div.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                 size=lambda i, v: setattr(i._bg, 'size', v))
        content.add_widget(div)

        # Metrics rows
        metrics = [
            ("Avg Net Units",    f"{ra['average_profit']:.4f}",  f"{rb['average_profit']:.4f}",  ra['average_profit'],  rb['average_profit'],  True),
            ("Median Net Units", f"{ra['median_profit']:.4f}",   f"{rb['median_profit']:.4f}",   ra['median_profit'],   rb['median_profit'],   True),
            ("Positive Rate",      f"{ra['win_rate']:.2f}%",       f"{rb['win_rate']:.2f}%",       ra['win_rate'],        rb['win_rate'],        True),
            ("Threshold Rate",     f"{ra['bust_rate']:.2f}%",      f"{rb['bust_rate']:.2f}%",      ra['bust_rate'],       rb['bust_rate'],       False),
            ("Best Session",  f"{ra['best_session']:.4f}",    f"{rb['best_session']:.4f}",    ra['best_session'],    rb['best_session'],    True),
            ("Worst Session", f"{ra['worst_session']:.4f}",   f"{rb['worst_session']:.4f}",   ra['worst_session'],   rb['worst_session'],   True),
            ("Avg Entries",      f"{ra['avg_bets']:.1f}",        f"{rb['avg_bets']:.1f}",        None,                  None,                  True),
        ]

        scroll = ScrollView()
        rows_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(2))
        rows_box.bind(minimum_height=rows_box.setter('height'))

        a_wins = 0
        b_wins = 0

        for metric_name, val_a, val_b, raw_a, raw_b, higher_is_better in metrics:
            row = GridLayout(cols=3, size_hint_y=None, height=dp(28), spacing=dp(4))

            # Determine winner highlight
            col_a = get_color_from_hex(STAKE_TEXT)
            col_b = get_color_from_hex(STAKE_TEXT)
            if raw_a is not None and raw_b is not None and raw_a != raw_b:
                a_better = (raw_a > raw_b) if higher_is_better else (raw_a < raw_b)
                if a_better:
                    col_a = get_color_from_hex(STAKE_GREEN)
                    a_wins += 1
                else:
                    col_b = get_color_from_hex(STAKE_GREEN)
                    b_wins += 1

            row.add_widget(Label(text=metric_name, color=get_color_from_hex(STAKE_TEXT), font_size='11sp'))
            row.add_widget(Label(text=val_a, color=col_a, font_size='11sp', bold=True, halign='center', valign='middle'))
            row.add_widget(Label(text=val_b, color=col_b, font_size='11sp', bold=True, halign='center', valign='middle'))
            rows_box.add_widget(row)

        scroll.add_widget(rows_box)
        content.add_widget(scroll)

        # Verdict
        if a_wins > b_wins:
            verdict = f"WINNER: '{sa['name'][:22]}'  ({a_wins} vs {b_wins})"
            verdict_color = LIMBO_COLOR
        elif b_wins > a_wins:
            verdict = f"WINNER: '{sb['name'][:22]}'  ({b_wins} vs {a_wins})"
            verdict_color = MINES_COLOR
        else:
            verdict = f"DRAW  ({a_wins} vs {b_wins})"
            verdict_color = STAKE_TEXT

        verdict_lbl = Label(
            text=verdict,
            color=get_color_from_hex(verdict_color),
            font_size='12sp',
            bold=True,
            size_hint_y=None,
            height=dp(28),
            halign='center',
            valign='middle',
        )
        verdict_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        content.add_widget(verdict_lbl)

        # Session count note
        note = Label(
            text=f"Based on {sessions:,} Monte Carlo sessions each",
            color=get_color_from_hex(SUBTITLE_TEXT),
            font_size='10sp',
            size_hint_y=None,
            height=dp(20),
            halign='center',
            valign='middle',
        )
        note.bind(size=lambda i, v: setattr(i, 'text_size', v))
        content.add_widget(note)

        # Share + Close buttons
        btn_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        share_btn = StyledButton(text='SHARE', bg_color=UTILITY_COLOR)
        share_btn.color = (1, 1, 1, 1)
        close_btn = StyledButton(text='CLOSE', bg_color=STAKE_GREEN)

        def do_share(*args):
            lines = [
                f"{'Metric':<18} {'A':>12} {'B':>12}",
                f"{'─'*18} {'─'*12} {'─'*12}",
                f"{'Strategy A':<18} {sa['name'][:28]}",
                f"{'Strategy B':<18} {sb['name'][:28]}",
                f"{'─'*18} {'─'*12} {'─'*12}",
                f"{'Avg Net Units':<18} {ra['average_profit']:>12.4f} {rb['average_profit']:>12.4f}",
                f"{'Median Net Units':<18} {ra['median_profit']:>12.4f} {rb['median_profit']:>12.4f}",
                f"{'Positive Rate':<18} {ra['win_rate']:>11.2f}% {rb['win_rate']:>11.2f}%",
                f"{'Threshold Rate':<18} {ra['bust_rate']:>11.2f}% {rb['bust_rate']:>11.2f}%",
                f"{'Best Session':<18} {ra['best_session']:>12.4f} {rb['best_session']:>12.4f}",
                f"{'Worst Session':<18} {ra['worst_session']:>12.4f} {rb['worst_session']:>12.4f}",
                f"{'─'*18} {'─'*12} {'─'*12}",
                verdict,
                f"Sessions: {sessions:,} each",
            ]
            share_result("Strategy Comparison", lines)

        share_btn.bind(on_release=do_share)

        popup = Popup(
            title='Strategy Comparison',
            content=content,
            size_hint=(0.96, 0.86),
            separator_color=get_color_from_hex(LIMBO_COLOR),
        )
        close_btn.bind(on_release=lambda *a: popup.dismiss())
        btn_row.add_widget(share_btn)
        btn_row.add_widget(close_btn)
        content.add_widget(btn_row)
        popup.open()
    # ─────────────────────────────────────────────────────────────────────────

    def show_add_popup(self, *args):
        app = App.get_running_app()
        if app and app.get_tier() == DEMO and DEMO_USAGE.remaining('strats_save') <= 0:
            show_upgrade_popup('Strategies Library', PRO, 'Demo save limit reached.')
            return
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        inputs = {}
        fields = [
            ('Name', 'Manual Strategy'), ('Category', 'Manual Custom'), ('Model', 'general'), ('Source', 'manual'),
            ('Capital', '1000'), ('Base Entry', '1'), ('Multiplier', '2.0'), ('On Positive Result', 'Reset'),
            ('On Negative Result', 'Increase 100%'), ('Max Entries', ''), ('Notes', '')
        ]
        for f, d in fields:
            content.add_widget(Label(text=f, font_size='11sp', size_hint_y=None, height=dp(15)))
            ti = StyledInput(text=d)
            inputs[f] = ti
            content.add_widget(ti)
        save_btn = StyledButton(text='SAVE STRATEGY')
        content.add_widget(save_btn)
        popup = Popup(title='New Strategy', content=content, size_hint=(0.9, 0.95))

        def save_strat(*a):
            app = App.get_running_app()
            if app and app.get_tier() == DEMO:
                if not DEMO_USAGE.consume('strats_save', 1):
                    show_upgrade_popup('Strategies Library', PRO, 'Demo save limit reached.')
                    popup.dismiss()
                    return
            new_s = normalize_strategy({
                'name': inputs['Name'].text, 'category': inputs['Category'].text or 'Manual Custom',
                'game': inputs['Model'].text or 'general', 'source': inputs['Source'].text or 'manual',
                'bank': inputs['Capital'].text, 'base': inputs['Base Entry'].text, 'multi': inputs['Multiplier'].text,
                'win_action': inputs['On Positive Result'].text, 'loss_action': inputs['On Negative Result'].text,
                'max_bets': inputs['Max Entries'].text, 'notes': inputs['Notes'].text
            })
            GLOBAL_BANK.strategies.append(new_s)
            GLOBAL_BANK.save_strategies()
            self.refresh_list()
            popup.dismiss()

        save_btn.bind(on_release=save_strat)
        popup.open()

class ProfitGraph(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history = [0]
        self.bind(pos=self.redraw, size=self.redraw)

    def add_point(self, profit):
        self.history.append(profit)
        if len(self.history) > 60:
            self.history.pop(0)
        self.redraw()

    def redraw(self, *args):
        self.canvas.clear()
        if len(self.history) < 2:
            return

        with self.canvas:
            Color(0.1, 0.12, 0.15, 1)
            Rectangle(pos=self.pos, size=self.size)

            Color(0, 0.7, 1, 1)
            points = []
            x_step = self.width / max(1, (len(self.history) - 1))
            min_h = min(self.history)
            max_h = max(self.history)
            h_range = max(1.0, max_h - min_h)

            for i, val in enumerate(self.history):
                px = self.x + (i * x_step)
                py = self.y + ((val - min_h) / h_range) * self.height
                points.extend([px, py])

            Line(points=points, width=dp(1.5))



"""
Strategy Suite Pro — RNG Variance Engine v2
Standalone module. Drop-in replacement for the DiceSimScreen in main.py.
All widget classes (DiceUiCard, DiceStatCard, DiceRollGraphic, DiceHistoryGraph,
DiceSessionState) are self-contained here.

To integrate into main.py:
  1. Remove the old DiceUiCard, DiceStatCard, DiceRollGraphic, DiceHistoryGraph,
     DiceSessionState, and DiceSimScreen blocks.
  2. Paste this entire file's content in their place (after imports).
  3. The screen name stays 'dice_sim' — no other changes needed.
"""

import math
import random
import threading
from dataclasses import dataclass

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (
    Color, Line, Rectangle, RoundedRectangle
)
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex

# ── Colour palette (matches main app) ────────────────────────────────────────
_BG         = '#000000'
_CARD       = '#0b0b0b'
_CARD2      = '#111317'
_BORDER     = '#232833'
_GREEN      = '#00e701'
_RED        = '#ff4e4e'
_TEXT       = '#b1bad3'
_SUBTEXT    = '#9a9a9a'
_BLUE       = '#3BA3FF'
_YELLOW     = '#F2C94C'
_PURPLE     = '#9B6BFF'
_TEAL       = '#1abc9c'
_UTILITY    = '#2c3e50'
_SOFT_RED   = '#7a0c0c'
_DIVIDER    = '#1C2027'
_TRACK_BG   = '#1C2027'
_ROLL_BG    = '#0B0D10'


def _hex(h):
    return get_color_from_hex(h)


def _safe_float(text, default=0.0):
    try:
        return float(str(text).strip())
    except Exception:
        return default


def _safe_int(text, default=0):
    try:
        return int(float(str(text).strip()))
    except Exception:
        return default


# ── Shared UI primitives ──────────────────────────────────────────────────────

class _RoundedButton(Button):
    """Button with a proper rounded rectangle background."""
    def __init__(self, bg=_UTILITY, radius=dp(10), **kwargs):
        super().__init__(**kwargs)
        self._bg_hex = bg
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.bold = True
        self.color = (0, 0, 0, 1) if bg == _GREEN else (1, 1, 1, 1)
        with self.canvas.before:
            Color(rgba=_hex(bg))
            self._rr = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._rr.pos = self.pos
        self._rr.size = self.size

    def set_color(self, hex_color):
        self._bg_hex = hex_color
        self._rr_color.rgba = _hex(hex_color)

    def set_active(self, active, active_hex=_GREEN, inactive_hex=_UTILITY):
        from kivy.graphics import Color as GColor
        self.canvas.before.clear()
        chosen = active_hex if active else inactive_hex
        with self.canvas.before:
            Color(rgba=_hex(chosen))
            self._rr = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.color = (0, 0, 0, 1) if chosen == _GREEN else (1, 1, 1, 1)
        self.bind(pos=self._upd, size=self._upd)


class _StyledInput(TextInput):
    def __init__(self, **kwargs):
        kwargs.setdefault('multiline', False)
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(40)
        self.background_color = _hex(_CARD)
        self.foreground_color = (1, 1, 1, 1)
        self.padding = [dp(12), dp(10)]
        self.cursor_color = _hex(_GREEN)
        self.font_size = '13sp'


class DiceUiCard(BoxLayout):
    """Dark rounded card — matches existing app style."""
    def __init__(self, radius=dp(16), fill=_CARD2, border=_BORDER, **kwargs):
        super().__init__(**kwargs)
        self._radius = radius
        with self.canvas.before:
            Color(rgba=_hex(fill))
            self._fill = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            Color(rgba=_hex(border))
            self._bdr = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, radius), width=1.0)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._fill.pos = self.pos
        self._fill.size = self.size
        self._bdr.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)


class DiceStatCard(DiceUiCard):
    """Single stat card with title + large value."""
    def __init__(
        self, title, value='--', accent=_BLUE,
        title_font='11sp', value_font='18sp',
        title_height=None, card_padding=None, **kwargs
    ):
        title_height = dp(16) if title_height is None else title_height
        card_padding = dp(12) if card_padding is None else card_padding
        super().__init__(orientation='vertical', padding=card_padding, spacing=dp(2), **kwargs)
        self._title_lbl = Label(
            text=title, color=_hex(_SUBTEXT), font_size=title_font,
            size_hint_y=None, height=title_height, halign='left', valign='middle'
        )
        self._title_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self._val_lbl = Label(
            text=value, color=_hex(accent), bold=True,
            font_size=value_font, halign='left', valign='middle'
        )
        self._val_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self.add_widget(self._title_lbl)
        self.add_widget(self._val_lbl)

    def set_value(self, val, color=None):
        self._val_lbl.text = str(val)
        if color:
            self._val_lbl.color = _hex(color)


# ── RNG Threshold Graphic (neutral teal/slate slider bar) ───────────────────────

class DiceRollGraphic(Widget):
    """
    Visual slider bar showing:
    - Dark track background
    - Coloured win zone (blue=primary zone, slate=secondary zone, red=deficit zone)
    - Yellow threshold line
    - White roll marker (where the ball landed)
    - 0–100 tick marks below the track
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_roll = None
        self.chance = 49.5
        self.is_over = False
        self.win = None

        with self.canvas:
            # background
            Color(rgba=_hex(_ROLL_BG))
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
            # track
            Color(rgba=_hex(_TRACK_BG))
            self._track = RoundedRectangle(pos=(0, 0), size=(0, 0), radius=[dp(12)])
            # win zone
            self._zone_col = Color(rgba=_hex(_BLUE))
            self._zone = RoundedRectangle(pos=(0, 0), size=(0, 0), radius=[dp(12)])
            # threshold line (yellow)
            Color(rgba=_hex(_YELLOW))
            self._thresh = Line(points=[], width=dp(2))
            # roll marker (white)
            Color(rgba=(1, 1, 1, 0.9))
            self._marker = Line(points=[], width=dp(3))
            # tick grid (subtle)
            Color(1, 1, 1, 0.06)
            self._ticks = [Line(points=[], width=dp(1)) for _ in range(11)]
            # tick labels drawn via separate Label widgets added in __init__ after canvas
        self.bind(pos=self.redraw, size=self.redraw)

        # Tick number labels (0, 10, 20 … 100)
        self._tick_labels = []
        for i in range(11):
            lbl = Label(
                text=str(i * 10),
                font_size='9sp',
                color=_hex(_SUBTEXT),
                size_hint=(None, None),
                size=(dp(28), dp(14))
            )
            self.add_widget(lbl)
            self._tick_labels.append(lbl)

        # Roll result big number
        self._roll_lbl = Label(
            text='', font_size='36sp', bold=True,
            color=(1, 1, 1, 0.9),
            size_hint=(None, None), size=(dp(120), dp(50)),
            halign='center', valign='middle'
        )
        self._roll_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self.add_widget(self._roll_lbl)

    def set_state(self, chance, is_over, last_roll=None, win=None):
        self.chance = chance
        self.is_over = is_over
        self.last_roll = last_roll
        self.win = win
        self.redraw()

    def redraw(self, *_):
        pad_x = dp(16)
        pad_y = dp(12)
        x = self.x + pad_x
        y = self.y + pad_y
        w = max(10, self.width - pad_x * 2)
        h = max(10, self.height - pad_y * 2)

        self._bg.pos = self.pos
        self._bg.size = self.size

        # Track sits in the vertical centre
        track_h = min(dp(40), h * 0.32)
        track_y = y + h * 0.46 - track_h / 2
        self._track.pos = (x, track_y)
        self._track.size = (w, track_h)

        # Win zone
        chance = max(0.5, min(98.5, self.chance))
        if self.is_over:
            zone_x = x + w * ((100.0 - chance) / 100.0)
            zone_w = w - (zone_x - x)
        else:
            zone_x = x
            zone_w = w * (chance / 100.0)

        if self.win is True:
            zone_hex = PRESENTATION_ACCENT_ALT
        elif self.win is False:
            zone_hex = '#183247'
        else:
            zone_hex = PRESENTATION_ACCENT

        self._zone_col.rgba = _hex(zone_hex)
        self._zone.pos = (zone_x, track_y)
        self._zone.size = (max(0, zone_w), track_h)

        # Threshold line
        thresh_x = x + w * ((100.0 - chance) / 100.0) if self.is_over else x + w * (chance / 100.0)
        self._thresh.points = [thresh_x, track_y - dp(6), thresh_x, track_y + track_h + dp(6)]

        # Tick marks
        for i, tick in enumerate(self._ticks):
            tx = x + (w / 10.0) * i
            tick.points = [tx, track_y - dp(4), tx, track_y + track_h + dp(4)]

        # Tick labels
        tick_label_y = track_y - dp(18)
        for i, lbl in enumerate(self._tick_labels):
            lbl_x = x + (w / 10.0) * i - dp(14)
            lbl.pos = (lbl_x, tick_label_y)

        # Roll marker
        if self.last_roll is not None:
            mx = x + w * (max(0, min(100, self.last_roll)) / 100.0)
            self._marker.points = [mx, y + dp(2), mx, y + h - dp(2)]
            self._roll_lbl.text = f'{self.last_roll:.2f}'
            roll_col = PRESENTATION_ACCENT if self.win is not False else '#8fb7d8'
            self._roll_lbl.color = _hex(roll_col)
            # Centre the label horizontally near the marker
            lbl_x = max(x, min(mx - dp(60), x + w - dp(120)))
            self._roll_lbl.pos = (lbl_x, y + h * 0.72)
        else:
            self._marker.points = []
            self._roll_lbl.text = ''


# ── Live Balance Graph ────────────────────────────────────────────────────────

class DiceHistoryGraph(Widget):
    """
    Live capital path graph with neutral teal/slate styling:
    - Dark background
    - Subtle horizontal grid lines
    - Gradient-style line (purple/blue)
    - Min/max labels on Y axis
    - Fills area under the line
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history = [0.0]

        with self.canvas:
            # BG
            Color(rgba=_hex(_ROLL_BG))
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            # Grid lines
            Color(1, 1, 1, 0.04)
            self._grid = [Line(points=[], width=dp(1)) for _ in range(5)]
            # Fill under curve (semi-transparent)
            Color(rgba=(0.38, 0.26, 1.0, 0.12))
            self._fill = Line(points=[], width=dp(1), close=False)
            # Main line
            Color(rgba=_hex(_PURPLE))
            self._line = Line(points=[], width=dp(2))

        # Y-axis labels
        self._y_hi = Label(text='', font_size='9sp', color=_hex(_SUBTEXT),
                           size_hint=(None, None), size=(dp(60), dp(14)))
        self._y_lo = Label(text='', font_size='9sp', color=_hex(_SUBTEXT),
                           size_hint=(None, None), size=(dp(60), dp(14)))
        self.add_widget(self._y_hi)
        self.add_widget(self._y_lo)

        self.bind(pos=self.redraw, size=self.redraw)

    def set_history(self, history):
        self.history = list(history[-200:]) if history else [0.0]
        self.redraw()

    def redraw(self, *_):
        pad_x = dp(14)
        pad_y = dp(10)
        x = self.x + pad_x
        y = self.y + pad_y
        w = max(10, self.width - pad_x * 2)
        h = max(10, self.height - pad_y * 2)

        self._bg.pos = self.pos
        self._bg.size = self.size

        # Grid lines
        for i, gl in enumerate(self._grid):
            gy = y + h * (i / 4.0)
            gl.points = [x, gy, x + w, gy]

        values = self.history if len(self.history) >= 2 else [0.0, 0.0]
        lo = min(values)
        hi = max(values)
        if abs(hi - lo) < 1e-9:
            lo -= 1.0
            hi += 1.0

        count = len(values) - 1
        pts = []
        for i, val in enumerate(values):
            px = x + (w * i / count)
            py = y + ((val - lo) / (hi - lo)) * h
            pts.extend([px, py])

        self._line.points = pts

        # Fill: close the polygon by going down to baseline
        if pts:
            fill_pts = list(pts)
            fill_pts.extend([pts[-2], y])   # bottom-right
            fill_pts.extend([pts[0], y])    # bottom-left
            self._fill.points = fill_pts

        # Y labels
        self._y_hi.text = f'{hi:.4f}'
        self._y_hi.pos = (self.x + dp(2), self.y + self.height - dp(16))
        self._y_lo.text = f'{lo:.4f}'
        self._y_lo.pos = (self.x + dp(2), self.y + dp(2))


# ── Session state ─────────────────────────────────────────────────────────────

@dataclass
class DiceSessionState:
    balance: float = 1000.0
    start_balance: float = 1000.0
    current_bet: float = 1.0
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    profit: float = 0.0
    max_balance: float = 1000.0
    min_balance: float = 1000.0
    wagered: float = 0.0
    streak: int = 0          # + for win streak, - for loss streak
    max_win_streak: int = 0
    max_loss_streak: int = 0


# ── Main Screen ───────────────────────────────────────────────────────────────

class DiceSimScreen(Screen):
    MIN_MULT = 1.0101
    MAX_MULT = 200.0

    def __init__(self, **kw):
        super().__init__(**kw)
        self.state = DiceSessionState()
        self.history = [1000.0]
        self.log_lines = []
        self.is_auto_running = False
        self._auto_event = None
        self.base_bet = 1.0
        self._mode = 'manual'   # 'manual' or 'auto'

        self._build_ui()
        self.reset_session()

    def on_pre_enter(self, *args):
        refresh_dynamic_presentation_titles(self)
        try:
            if is_presentation_mode_active():
                self.title_lbl.text = 'RNG Variance Engine  [size=11][color=#9dc7ea]up to 200x[/color][/size]'
                self.title_lbl.color = _hex('#7ec8ff')
            else:
                self.title_lbl.text = 'RNG Variance Engine  [size=11][color=#9dc7ea]up to 200x[/color][/size]'
                self.title_lbl.color = _hex(_GREEN)
        except Exception:
            pass

    # ── Compatibility shims (called by strategy library) ──────────────────────
    @property
    def balance_input(self):
        return self.capital_in

    @property
    def bet_input(self):
        return self.base_bet_in

    def change_balance(self, *_):
        self.reset_session()

    def on_manual_multi_change(self, *_):
        self._sync_mult(from_slider=False)

    # ── UI Build — single screen, no scroll ──────────────────────────────────
    def _build_ui(self):
        # Outer: full screen vertical, tight padding
        root = BoxLayout(
            orientation='vertical',
            padding=[dp(6), dp(6), dp(6), dp(4)],
            spacing=dp(4)
        )

        # ── Row 0: Header bar ────────────────────────────────────────────────
        header = DiceUiCard(
            orientation='horizontal',
            size_hint_y=None, height=dp(38),
            padding=[dp(10), dp(4)], spacing=dp(8)
        )
        self.title_lbl = title_lbl = Label(
            text='RNG Variance Engine  [size=11][color=#9dc7ea]up to 200x[/color][/size]',
            markup=True, font_size='18sp', bold=True,
            color=_hex(_GREEN), halign='left', valign='middle'
        )
        title_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        title_lbl._dynamic_title_sid = 'dice_sim'
        header.add_widget(title_lbl)

        mode_box = BoxLayout(size_hint_x=None, width=dp(130), spacing=dp(5))
        self._manual_btn = _RoundedButton(text='MANUAL', bg=_GREEN, size_hint_x=0.5)
        self._manual_btn.font_size = '11sp'
        self._auto_btn = _RoundedButton(text='AUTO', bg=_UTILITY, size_hint_x=0.5)
        self._auto_btn.font_size = '11sp'
        self._manual_btn.bind(on_release=lambda *_: self._set_mode('manual'))
        self._auto_btn.bind(on_release=lambda *_: self._set_mode('auto'))
        mode_box.add_widget(self._manual_btn)
        mode_box.add_widget(self._auto_btn)
        header.add_widget(mode_box)

        back_btn = _RoundedButton(text='HOME', bg=_UTILITY, size_hint_x=None, width=dp(54))
        back_btn.font_size = '11sp'
        back_btn.bind(on_release=lambda *_: setattr(
            App.get_running_app().root, 'current', 'menu'))
        header.add_widget(back_btn)
        root.add_widget(header)

        # ── Row 1: top stat cards (balance/bet wider) ───────────────────────
        stats_grid = BoxLayout(spacing=dp(4), size_hint_y=None, height=dp(66))
        self._bal_card = DiceStatCard('Capital', accent=_GREEN, value_font='17sp', title_font='10sp', title_height=dp(14), card_padding=dp(10), size_hint_x=1.15)
        self._bet_card = DiceStatCard('Entry', accent=_BLUE, value_font='17sp', title_font='10sp', title_height=dp(14), card_padding=dp(10), size_hint_x=1.15)
        self._pnl_card = DiceStatCard('Net Units', accent=_YELLOW, value_font='15sp', title_font='10sp', title_height=dp(14), card_padding=dp(10), size_hint_x=0.9)
        self._wr_card  = DiceStatCard('Positive %', accent=_PURPLE, value_font='15sp', title_font='10sp', title_height=dp(14), card_padding=dp(10), size_hint_x=0.9)
        for c in [self._bal_card, self._bet_card, self._pnl_card, self._wr_card]:
            stats_grid.add_widget(c)
        root.add_widget(stats_grid)

        # ── Row 2: Roll graphic ──────────────────────────────────────────────
        self._roll_graphic = DiceRollGraphic(size_hint_y=None, height=dp(118))
        root.add_widget(self._roll_graphic)

        # ── Row 3: Main two-column body (LEFT controls | RIGHT graph+log) ────
        body = BoxLayout(orientation='horizontal', spacing=dp(6))

        # ── LEFT COLUMN ──────────────────────────────────────────────────────
        left = BoxLayout(orientation='vertical', spacing=dp(4), size_hint_x=0.54)

        # Capital + Base Bet
        inputs_row = GridLayout(cols=2, spacing=dp(4), size_hint_y=None, height=dp(52))
        self.capital_in  = _StyledInput(text='1000')
        self.capital_in.hint_text = 'Capital'
        self.capital_in.height = dp(34)
        self.base_bet_in = _StyledInput(text='10')
        self.base_bet_in.hint_text = 'Base Entry'
        self.base_bet_in.height = dp(34)
        inputs_row.add_widget(self._labelled('Capital',  self.capital_in))
        inputs_row.add_widget(self._labelled('Base Entry', self.base_bet_in))
        left.add_widget(inputs_row)

        # Multiplier row: [-] [input] [+]
        mult_row = GridLayout(cols=3, spacing=dp(4), size_hint_y=None, height=dp(34))
        self._mult_minus = _RoundedButton(text='-', bg=_UTILITY, size_hint_x=None, width=dp(34))
        self._mult_minus.font_size = '16sp'
        self.mult_input  = _StyledInput(text='2.1000')
        self.mult_input.height = dp(34)
        self.mult_input.bind(text=lambda *_: self._sync_mult(from_slider=False))
        self._mult_plus  = _RoundedButton(text='+', bg=_UTILITY, size_hint_x=None, width=dp(34))
        self._mult_plus.font_size = '16sp'
        self._mult_minus.bind(on_release=lambda *_: self._bump_mult(-1))
        self._mult_plus.bind(on_release=lambda *_:  self._bump_mult(1))
        mult_row.add_widget(self._mult_minus)
        mult_row.add_widget(self.mult_input)
        mult_row.add_widget(self._mult_plus)
        left.add_widget(mult_row)

        # Multiplier slider
        self._mult_slider = Slider(min=0, max=1000, value=0, size_hint_y=None, height=dp(28))
        self._mult_slider.cursor_size = (dp(22), dp(22))
        self._mult_slider.value_track = True
        self._mult_slider.value_track_color = _hex(_PURPLE)
        self._mult_slider.bind(value=lambda *_: self._sync_mult(from_slider=True))
        left.add_widget(self._mult_slider)

        # Chance / mult info row
        info_row = GridLayout(cols=3, size_hint_y=None, height=dp(16), spacing=dp(2))
        self._target_lbl = Label(text='LOW ZONE', color=_hex(_TEXT),    font_size='10sp', halign='left')
        self._chance_lbl = Label(text='49.50%',     color=_hex(_SUBTEXT), font_size='10sp', halign='center')
        self._mult_lbl   = Label(text='2.0000x',    color=_hex(_SUBTEXT), font_size='10sp', halign='right')
        for l in [self._target_lbl, self._chance_lbl, self._mult_lbl]:
            l.bind(size=lambda i, v: setattr(i, 'text_size', v))
            info_row.add_widget(l)
        left.add_widget(info_row)

        # Over / Under
        ou_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(4))
        self._under_btn = _RoundedButton(text='LOW', bg=_GREEN)
        self._under_btn.font_size = '12sp'
        self._over_btn  = _RoundedButton(text='HIGH',  bg=_UTILITY)
        self._over_btn.font_size = '12sp'
        self._under_btn.bind(on_release=lambda *_: self._set_over_under(False))
        self._over_btn.bind(on_release=lambda *_:  self._set_over_under(True))
        ou_row.add_widget(self._under_btn)
        ou_row.add_widget(self._over_btn)
        left.add_widget(ou_row)

        # On Win / On Loss progression (compact 2-row)
        self._win_action  = 'reset'
        self._loss_action = 'increase'

        win_row = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(4))
        win_lbl = Label(text='Pos:', color=_hex(_SUBTEXT), font_size='10sp',
                        size_hint_x=None, width=dp(28), halign='left', valign='middle')
        win_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self._win_action_btn = _RoundedButton(text='RESET', bg='#1a3a1a')
        self._win_action_btn.font_size = '11sp'
        self._win_action_btn.bind(on_release=lambda *_: self._cycle_win_action())
        self._win_pct_in = _StyledInput(text='0', size_hint_x=None, width=dp(52))
        self._win_pct_in.hint_text = '%'
        self._win_pct_in.height = dp(32)
        win_row.add_widget(win_lbl)
        win_row.add_widget(self._win_action_btn)
        win_row.add_widget(self._win_pct_in)
        left.add_widget(win_row)

        loss_row = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(4))
        loss_lbl = Label(text='Neg:', color=_hex(_SUBTEXT), font_size='10sp',
                         size_hint_x=None, width=dp(28), halign='left', valign='middle')
        loss_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self._loss_action_btn = _RoundedButton(text='INC %', bg='#3a1a1a')
        self._loss_action_btn.font_size = '11sp'
        self._loss_action_btn.bind(on_release=lambda *_: self._cycle_loss_action())
        self._loss_pct_in = _StyledInput(text='35', size_hint_x=None, width=dp(52))
        self._loss_pct_in.hint_text = '%'
        self._loss_pct_in.height = dp(32)
        loss_row.add_widget(loss_lbl)
        loss_row.add_widget(self._loss_action_btn)
        loss_row.add_widget(self._loss_pct_in)
        left.add_widget(loss_row)

        # Stop conditions (2x2 compact grid)
        stop_grid = GridLayout(cols=2, spacing=dp(4), size_hint_y=None, height=dp(52))
        self._stop_profit_in = _StyledInput(text='150')
        self._stop_profit_in.hint_text = 'Target Gain'
        self._stop_profit_in.height = dp(34)
        self._stop_loss_in = _StyledInput(text='200')
        self._stop_loss_in.hint_text = 'Max Drawdown'
        self._stop_loss_in.height = dp(34)
        self._max_bets_in = _StyledInput(text='20')
        self._max_bets_in.hint_text = 'Run Limit'
        self._max_bets_in.height = dp(34)
        self._min_bal_in = _StyledInput(text='700')
        self._min_bal_in.hint_text = 'Min Capital'
        self._min_bal_in.height = dp(34)
        stop_grid.add_widget(self._labelled('Target Gain', self._stop_profit_in))
        stop_grid.add_widget(self._labelled('Max Drawdown',   self._stop_loss_in))
        left.add_widget(stop_grid)

        stop_grid2 = GridLayout(cols=2, spacing=dp(4), size_hint_y=None, height=dp(52))
        stop_grid2.add_widget(self._labelled('Run Limit', self._max_bets_in))
        stop_grid2.add_widget(self._labelled('Min Capital',  self._min_bal_in))
        left.add_widget(stop_grid2)

        # Auto speed slider (compact)
        self._speed_lbl = Label(
            text='Speed: Balanced',
            color=_hex(_SUBTEXT), font_size='10sp',
            size_hint_y=None, height=dp(14), halign='left', valign='middle'
        )
        self._speed_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        left.add_widget(self._speed_lbl)
        self._speed_slider = Slider(min=0, max=100, value=40, size_hint_y=None, height=dp(26))
        self._speed_slider.cursor_size = (dp(20), dp(20))
        self._speed_slider.value_track = True
        self._speed_slider.value_track_color = _hex(_TEAL)
        self._speed_slider.bind(value=lambda *_: self._update_speed_label())
        left.add_widget(self._speed_slider)

        # Action buttons are placed below the whole body so they sit at true screen center
        self._roll_btn = _RoundedButton(text='RUN SIMULATION', bg=_GREEN)
        self._roll_btn.font_size = '14sp'
        self._roll_btn.bind(on_release=self._manual_roll)
        self._start_auto_btn = _RoundedButton(text='START AUTO', bg=_UTILITY)
        self._start_auto_btn.font_size = '12sp'
        self._start_auto_btn.bind(on_release=self._start_auto)
        self._stop_auto_btn = _RoundedButton(text='STOP', bg=_SOFT_RED)
        self._stop_auto_btn.font_size = '11sp'
        self._reset_btn = _RoundedButton(text='RESET', bg=_UTILITY)
        self._reset_btn.font_size = '11sp'
        self._clear_values_btn = _RoundedButton(text='CLEAR VALUES', bg='#5a2a2a')
        self._clear_values_btn.font_size = '11sp'
        self._stop_auto_btn.bind(on_release=self._stop_auto)
        self._reset_btn.bind(on_release=lambda *_: self.reset_session())
        self._clear_values_btn.bind(on_release=self.clear_values)

        # Filler
        left.add_widget(Widget())
        body.add_widget(left)

        # ── RIGHT COLUMN ─────────────────────────────────────────────────────
        right = BoxLayout(orientation='vertical', spacing=dp(4), size_hint_x=0.46)

        # Secondary stats: 2x2
        stats2_grid = GridLayout(cols=2, spacing=dp(4), size_hint_y=None, height=dp(104))
        self._wag_card   = DiceStatCard('Exposure', accent=_TEAL, value_font='15sp', title_font='10sp', title_height=dp(13), card_padding=dp(8))
        self._bets_card  = DiceStatCard('Runs', accent=_SUBTEXT, value_font='15sp', title_font='10sp', title_height=dp(13), card_padding=dp(8))
        self._wstrk_card = DiceStatCard('Pos.Run', accent=_GREEN, value_font='15sp', title_font='10sp', title_height=dp(13), card_padding=dp(8))
        self._lstrk_card = DiceStatCard('Neg.Run', accent=_RED, value_font='15sp', title_font='10sp', title_height=dp(13), card_padding=dp(8))
        for c in [self._wag_card, self._bets_card, self._wstrk_card, self._lstrk_card]:
            stats2_grid.add_widget(c)
        right.add_widget(stats2_grid)

        # Balance graph — compact so right-side stats sit higher
        graph_card = DiceUiCard(
            orientation='vertical', size_hint_y=None, height=dp(198),
            padding=[dp(6), dp(6)], spacing=dp(4)
        )
        graph_hdr = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(4))
        graph_lbl = Label(
            text='Capital Path', color=_hex(_TEXT), font_size='11sp', bold=True,
            halign='left', valign='middle'
        )
        graph_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        self._graph_info = Label(
            text='', color=_hex(_SUBTEXT), font_size='9sp',
            halign='right', valign='middle'
        )
        self._graph_info.bind(size=lambda i, v: setattr(i, 'text_size', v))
        graph_hdr.add_widget(graph_lbl)
        graph_hdr.add_widget(self._graph_info)
        graph_card.add_widget(graph_hdr)
        self.balance_graph = DiceHistoryGraph()
        graph_card.add_widget(self.balance_graph)
        right.add_widget(graph_card)

        # Roll log — compact height, keeps both columns visually aligned
        log_card = DiceUiCard(
            orientation='vertical', size_hint_y=None, height=dp(94),
            padding=[dp(6), dp(6)], spacing=dp(4)
        )
        log_hdr = Label(
            text='Recent Samples', color=_hex(_TEXT), font_size='11sp', bold=True,
            size_hint_y=None, height=dp(16), halign='left', valign='middle'
        )
        log_hdr.bind(size=lambda i, v: setattr(i, 'text_size', v))
        log_card.add_widget(log_hdr)
        self.log_input = TextInput(
            text='', readonly=True, multiline=True,
            background_normal='', background_active='',
            background_color=_hex(_ROLL_BG),
            foreground_color=_hex(_TEXT),
            cursor_color=_hex(_GREEN),
            padding=(dp(6), dp(6)),
            font_size='11sp'
        )
        log_card.add_widget(self.log_input)
        right.add_widget(log_card)
        right.add_widget(Widget())

        body.add_widget(right)
        root.add_widget(body)

        # Bottom action buttons centered across the full screen width
        self._roll_btn.height = dp(46)
        self._start_auto_btn.height = dp(46)
        self._stop_auto_btn.height = dp(36)
        self._reset_btn.height = dp(36)
        self._clear_values_btn.height = dp(36)
        self._roll_btn.font_size = '15sp'
        self._start_auto_btn.font_size = '13sp'
        self._stop_auto_btn.font_size = '12sp'
        self._reset_btn.font_size = '12sp'
        self._clear_values_btn.font_size = '12sp'

        action_outer = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(116), spacing=dp(5))

        action_row1 = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(0))
        action_row1.add_widget(Widget(size_hint_x=0.18))
        action_row1_inner = BoxLayout(size_hint_x=0.64, spacing=dp(6))
        action_row1_inner.add_widget(self._roll_btn)
        action_row1_inner.add_widget(self._start_auto_btn)
        action_row1.add_widget(action_row1_inner)
        action_row1.add_widget(Widget(size_hint_x=0.18))

        action_row2 = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(0))
        action_row2.add_widget(Widget(size_hint_x=0.16))
        action_row2_inner = BoxLayout(size_hint_x=0.68, spacing=dp(6))
        action_row2_inner.add_widget(self._stop_auto_btn)
        action_row2_inner.add_widget(self._reset_btn)
        action_row2_inner.add_widget(self._clear_values_btn)
        action_row2.add_widget(action_row2_inner)
        action_row2.add_widget(Widget(size_hint_x=0.16))

        action_row3 = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(0))
        action_row3.add_widget(Widget(size_hint_x=0.25))
        home_bottom_btn = _RoundedButton(text='BACK TO HOME SCREEN', bg=_UTILITY, size_hint_x=0.50)
        home_bottom_btn.height = dp(30)
        home_bottom_btn.font_size = '11sp'
        home_bottom_btn.bind(on_release=lambda *_: setattr(App.get_running_app().root, 'current', 'menu'))
        action_row3.add_widget(home_bottom_btn)
        action_row3.add_widget(Widget(size_hint_x=0.25))

        action_outer.add_widget(action_row1)
        action_outer.add_widget(action_row2)
        action_outer.add_widget(action_row3)
        root.add_widget(action_outer)
        self.add_widget(root)

    # ── Helper: labelled input block ──────────────────────────────────────────
    def _labelled(self, label_text, widget):
        box = BoxLayout(orientation='vertical', spacing=dp(2))
        lbl = Label(
            text=label_text, color=_hex(_SUBTEXT), font_size='10sp',
            size_hint_y=None, height=dp(14), halign='left', valign='middle'
        )
        lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        box.add_widget(lbl)
        box.add_widget(widget)
        return box

    # ── Mode toggle ───────────────────────────────────────────────────────────
    def _set_mode(self, mode):
        self._mode = mode
        if mode == 'manual':
            self._manual_btn.set_active(True)
            self._auto_btn.set_active(False)
        else:
            self._manual_btn.set_active(False)
            self._auto_btn.set_active(True, active_hex=_BLUE)

    # ── Multiplier logic ──────────────────────────────────────────────────────
    def _slider_to_mult(self, v):
        ratio = max(0.0, min(1.0, v / 1000.0))
        return self.MIN_MULT * ((self.MAX_MULT / self.MIN_MULT) ** ratio)

    def _mult_to_slider(self, m):
        m = max(self.MIN_MULT, min(self.MAX_MULT, m))
        return 1000.0 * math.log(m / self.MIN_MULT, self.MAX_MULT / self.MIN_MULT)

    def _bump_mult(self, direction):
        m = self._current_mult()
        step = 0.05 if m < 5 else (0.25 if m < 20 else (1.0 if m < 100 else 2.5))
        m = max(self.MIN_MULT, min(self.MAX_MULT, m + direction * step))
        self.mult_input.text = f'{m:.4f}'
        self._sync_mult(from_slider=False)

    def _sync_mult(self, from_slider=False):
        if from_slider:
            m = self._slider_to_mult(self._mult_slider.value)
            self.mult_input.text = f'{m:.4f}'
        else:
            m = self._current_mult()
            self._mult_slider.value = self._mult_to_slider(m)
        chance = self._current_chance()
        self._mult_lbl.text   = f'{m:.4f}x'
        self._chance_lbl.text = f'{chance:.4f}%'
        is_over = self._is_over()
        mode_txt = f'High Zone {100.0 - chance:.2f}' if is_over else f'Low Zone {chance:.2f}'
        self._target_lbl.text = mode_txt
        self._roll_graphic.set_state(chance, is_over, self._roll_graphic.last_roll, self._roll_graphic.win)

    def _current_mult(self):
        return max(self.MIN_MULT, min(self.MAX_MULT, _safe_float(self.mult_input.text, 2.0)))

    def _current_chance(self):
        return max(0.5, min(98.5, 99.0 / self._current_mult()))

    def _is_over(self):
        return self._over_btn.background_color != _hex(_UTILITY) if hasattr(self, '_over_btn') else False

    # ── Over / Under ──────────────────────────────────────────────────────────
    def _set_over_under(self, is_over):
        self._is_over_mode = is_over
        if is_over:
            self._over_btn.set_active(True)
            self._under_btn.set_active(False)
        else:
            self._under_btn.set_active(True)
            self._over_btn.set_active(False)
        self._sync_mult(from_slider=False)

    def _get_is_over(self):
        return getattr(self, '_is_over_mode', False)

    # ── Win/Loss action cycling ───────────────────────────────────────────────
    _WIN_ACTIONS  = ['reset', 'increase', 'decrease']
    _LOSS_ACTIONS = ['reset', 'increase', 'decrease']
    _WIN_LABELS   = {'reset': 'RESET BASE', 'increase': 'INCREASE', 'decrease': 'DECREASE'}
    _LOSS_LABELS  = {'reset': 'RESET BASE', 'increase': 'INCREASE', 'decrease': 'DECREASE'}
    _WIN_COLORS   = {'reset': '#1a3a1a', 'increase': '#1a2a3a', 'decrease': '#2a1a3a'}
    _LOSS_COLORS  = {'reset': '#1a3a1a', 'increase': '#3a1a1a', 'decrease': '#3a2a1a'}

    def _cycle_win_action(self):
        idx = self._WIN_ACTIONS.index(self._win_action)
        self._win_action = self._WIN_ACTIONS[(idx + 1) % len(self._WIN_ACTIONS)]
        self._win_action_btn.canvas.before.clear()
        col = self._WIN_COLORS[self._win_action]
        with self._win_action_btn.canvas.before:
            Color(rgba=_hex(col))
            self._win_action_btn._rr = RoundedRectangle(
                pos=self._win_action_btn.pos,
                size=self._win_action_btn.size,
                radius=[dp(10)]
            )
        self._win_action_btn.bind(
            pos=lambda i, v: setattr(i._rr, 'pos', v),
            size=lambda i, v: setattr(i._rr, 'size', v)
        )
        self._win_action_btn.text = self._WIN_LABELS[self._win_action]

    def _cycle_loss_action(self):
        idx = self._LOSS_ACTIONS.index(self._loss_action)
        self._loss_action = self._LOSS_ACTIONS[(idx + 1) % len(self._LOSS_ACTIONS)]
        self._loss_action_btn.canvas.before.clear()
        col = self._LOSS_COLORS[self._loss_action]
        with self._loss_action_btn.canvas.before:
            Color(rgba=_hex(col))
            self._loss_action_btn._rr = RoundedRectangle(
                pos=self._loss_action_btn.pos,
                size=self._loss_action_btn.size,
                radius=[dp(10)]
            )
        self._loss_action_btn.bind(
            pos=lambda i, v: setattr(i._rr, 'pos', v),
            size=lambda i, v: setattr(i._rr, 'size', v)
        )
        self._loss_action_btn.text = self._LOSS_LABELS[self._loss_action]

    # ── Speed label ───────────────────────────────────────────────────────────
    def _auto_delay(self):
        v = max(0.0, min(100.0, self._speed_slider.value))
        return 0.55 - (v / 100.0) * 0.52

    def _update_speed_label(self):
        delay = self._auto_delay()
        if delay >= 0.40:   mode = 'Slow'
        elif delay >= 0.24: mode = 'Balanced'
        elif delay >= 0.10: mode = 'Fast'
        else:               mode = 'Turbo'
        self._speed_lbl.text = f'Auto Speed: {mode} | {delay:.2f}s delay'

    def clear_values(self, *_):
        self._stop_auto()
        clear_input_widgets([
            self.capital_in, self.base_bet_in, self.mult_input, self._win_pct_in,
            self._loss_pct_in, self._stop_profit_in, self._stop_loss_in,
            self._max_bets_in, self._min_bal_in
        ])
        self.state = DiceSessionState(balance=0.0, start_balance=0.0, current_bet=0.0, max_balance=0.0, min_balance=0.0)
        self.base_bet = 0.0
        self.history = [0.0]
        self.log_lines = []
        self.log_input.text = ''
        self._refresh_stats()
        self._write_log('Input values cleared.')

    # ── Session reset ─────────────────────────────────────────────────────────
    def reset_session(self, *_):
        cap = max(0.00000001, _safe_float(self.capital_in.text, 1000))
        bet = max(0.00000001, _safe_float(self.base_bet_in.text, 1))
        self.base_bet = bet
        self.state = DiceSessionState(
            balance=cap, start_balance=cap,
            current_bet=bet,
            max_balance=cap, min_balance=cap
        )
        self.history = [cap]
        self.log_lines = []
        self.log_input.text = ''
        self._set_over_under(False)
        self._sync_mult(from_slider=False)
        self._update_speed_label()
        self._refresh_stats()
        self._write_log('Analysis session reset.')

    # ── Core roll execution ───────────────────────────────────────────────────
    def execute_roll(self):
        s = self.state
        chance  = self._current_chance()
        mult    = self._current_mult()
        bet     = s.current_bet
        is_over = self._get_is_over()

        if bet <= 0:
            self._write_log('Entry must be > 0.')
            return 'stop'
        if bet > s.balance:
            self._write_log('Stopped: insufficient capital.')
            return 'stop'

        roll  = round(random.random() * 100.0, 4)
        win   = (roll > (100.0 - chance)) if is_over else (roll < chance)
        delta = (bet * (mult - 1.0)) if win else -bet

        s.balance  += delta
        s.profit    = s.balance - s.start_balance
        s.wagered  += bet
        s.total_bets += 1

        if win:
            s.wins += 1
            s.streak = max(1, s.streak + 1) if s.streak >= 0 else 1
            s.max_win_streak = max(s.max_win_streak, s.streak)
        else:
            s.losses += 1
            s.streak = min(-1, s.streak - 1) if s.streak <= 0 else -1
            s.max_loss_streak = max(s.max_loss_streak, abs(s.streak))

        s.max_balance = max(s.max_balance, s.balance)
        s.min_balance = min(s.min_balance, s.balance)
        self.history.append(s.balance)

        self._roll_graphic.set_state(chance, is_over, roll, win)
        result_word = 'POSITIVE' if win else 'NEGATIVE'
        mode_word   = 'HIGH ZONE' if is_over else 'LOW ZONE'
        self._write_log(
            f'#{s.total_bets} | {roll:.4f} | {mode_word} | {result_word} | '
            f'Entry {bet:.6f} | Cap {s.balance:.6f}'
        )
        self._apply_progression(win)
        self._refresh_stats()

        return 'continue' if self._check_stops() else 'stop'

    # ── Progression ───────────────────────────────────────────────────────────
    def _apply_progression(self, win):
        s    = self.state
        base = max(0.00000001, _safe_float(self.base_bet_in.text, 1))
        pct_win  = max(0.0, _safe_float(self._win_pct_in.text,  0))
        pct_loss = max(0.0, _safe_float(self._loss_pct_in.text, 50))

        if win:
            action = self._win_action
            pct    = pct_win
        else:
            action = self._loss_action
            pct    = pct_loss

        if action == 'reset':
            s.current_bet = base
        elif action == 'increase':
            s.current_bet = max(0.00000001, s.current_bet * (1.0 + pct / 100.0))
        elif action == 'decrease':
            s.current_bet = max(0.00000001, s.current_bet * max(0.0, 1.0 - pct / 100.0))
            if s.current_bet < 0.00000001:
                s.current_bet = base

    # ── Stop conditions ───────────────────────────────────────────────────────
    def _check_stops(self):
        s          = self.state
        stop_prof  = _safe_float(self._stop_profit_in.text, 0)
        stop_loss  = _safe_float(self._stop_loss_in.text,  0)
        max_bets   = _safe_int(self._max_bets_in.text,    0)
        min_bal    = _safe_float(self._min_bal_in.text,   0)

        if stop_prof > 0 and s.profit >= stop_prof:
            self._write_log(f'Stopped: target gain {stop_prof} reached.')
            return False
        if stop_loss > 0 and s.profit <= -stop_loss:
            self._write_log(f'Stopped: max drawdown {stop_loss} reached.')
            return False
        if max_bets > 0 and s.total_bets >= max_bets:
            self._write_log(f'Stopped: run limit {max_bets} reached.')
            return False
        if min_bal > 0 and s.balance <= min_bal:
            self._write_log(f'Stopped: capital fell below {min_bal}.')
            return False
        if s.balance <= 0:
            self._write_log('Stopped: capital exhausted.')
            return False
        return True

    # ── Manual roll ───────────────────────────────────────────────────────────
    def _manual_roll(self, *_):
        if not self.is_auto_running:
            self.execute_roll()

    # ── Auto bet ──────────────────────────────────────────────────────────────
    def _start_auto(self, *_):
        if self.is_auto_running:
            return
        self.base_bet = max(0.00000001, _safe_float(self.base_bet_in.text, 1))
        self.state.current_bet = self.base_bet
        self.is_auto_running = True
        self._set_mode('auto')
        self._write_log('Auto analysis started.')
        self._auto_step()

    def _stop_auto(self, *_):
        if self.is_auto_running:
            self._write_log('Auto analysis stopped.')
        self.is_auto_running = False
        if self._auto_event:
            try:
                self._auto_event.cancel()
            except Exception:
                pass
            self._auto_event = None

    def _auto_step(self, *_):
        if not self.is_auto_running:
            return
        status = self.execute_roll()
        if status == 'stop':
            self.is_auto_running = False
            self._auto_event = None
            return
        self._auto_event = Clock.schedule_once(self._auto_step, self._auto_delay())

    # ── Stats refresh ─────────────────────────────────────────────────────────
    def _refresh_stats(self):
        s  = self.state
        wr = (s.wins / s.total_bets * 100.0) if s.total_bets else 0.0
        sign = '+' if s.profit >= 0 else ''

        self._bal_card.set_value(f'{s.balance:.4f}',
                                 _GREEN if s.balance >= s.start_balance else _RED)
        self._bet_card.set_value(f'{s.current_bet:.6f}', _BLUE)
        self._pnl_card.set_value(f'{sign}{s.profit:.4f}',
                                  _GREEN if s.profit >= 0 else _RED)
        self._wr_card.set_value(f'{wr:.2f}%', _PURPLE)
        self._wag_card.set_value(f'{s.wagered:.4f}', _TEAL)
        self._bets_card.set_value(str(s.total_bets), _SUBTEXT)
        self._wstrk_card.set_value(str(s.max_win_streak), _GREEN)
        self._lstrk_card.set_value(str(s.max_loss_streak), _RED)

        self.balance_graph.set_history(self.history)
        self._graph_info.text = (
            f'High {s.max_balance:.4f}  '
            f'Low {s.min_balance:.4f}  '
            f'Pos/Neg {s.wins}/{s.losses}'
        )

    # ── Log ───────────────────────────────────────────────────────────────────
    def _write_log(self, text):
        self.log_lines.insert(0, text)
        self.log_lines = self.log_lines[:100]
        self.log_input.text = '\n'.join(self.log_lines)

    # ── Popup warning ─────────────────────────────────────────────────────────
    def _warn(self, msg):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout as BL
        content = BL(orientation='vertical', padding=dp(12), spacing=dp(10))
        content.add_widget(Label(text=msg, color=_hex(_TEXT)))
        btn = _RoundedButton(text='OK', bg=_GREEN, size_hint_y=None, height=dp(42))
        content.add_widget(btn)
        popup = Popup(title='Notice', content=content, size_hint=(0.82, 0.28))
        btn.bind(on_release=popup.dismiss)
        popup.open()





class DiceScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        layout.add_widget(build_info_header("THRESHOLD MULTIPLIER"))

        subtitle = Label(
            text="Neutral threshold workspace for sequence depth, event chance and recovery planning.",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(26)
        )
        layout.add_widget(subtitle)

        preview = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(78), padding=[dp(10), dp(8)], spacing=dp(4))
        with preview.canvas.before:
            Color(rgba=get_color_from_hex(STAKE_INPUT))
            preview._bg = RoundedRectangle(pos=preview.pos, size=preview.size, radius=[dp(12)])
            Color(rgba=get_color_from_hex(PRESENTATION_ACCENT_ALT))
            preview._line = Line(points=[], width=dp(2))
            Color(rgba=get_color_from_hex(PRESENTATION_ACCENT))
            preview._threshold = Line(points=[], width=dp(2))
        def _upd_preview(inst, *_):
            inst._bg.pos = inst.pos
            inst._bg.size = inst.size
            x1 = inst.x + dp(12)
            y1 = inst.y + dp(18)
            x2 = inst.right - dp(12)
            y2 = inst.top - dp(18)
            inst._line.points = [x1, y1, x1 + (x2 - x1) * 0.38, y1 + dp(8), x1 + (x2 - x1) * 0.70, y2 - dp(6), x2, y2]
            tx = x1 + (x2 - x1) * 0.68
            inst._threshold.points = [tx, inst.y + dp(10), tx, inst.top - dp(10)]
        preview.bind(pos=_upd_preview, size=_upd_preview)
        self.preview_lbl = Label(
            text="Threshold: --  |  Event Chance: --  |  Recovery: --",
            color=get_color_from_hex(PRESENTATION_ACCENT),
            font_size='12sp',
            bold=True,
            halign='center',
            valign='middle'
        )
        self.preview_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        preview.add_widget(Widget(size_hint_y=None, height=dp(34)))
        preview.add_widget(self.preview_lbl)
        layout.add_widget(preview)

        self.inputs = {}
        fields = [
            ('Capital', '1000'),
            ('Base Entry', '10'),
            ('Threshold', '2.10'),
            ('Event Chance %', '47.14'),
            ('Increase on Negative Result %', '35')
        ]

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for label, default in fields:
            grid.add_widget(Label(text=label, color=get_color_from_hex(STAKE_TEXT), font_size='12sp'))
            self.inputs[label] = StyledInput(text=default)
            if label == 'Threshold':
                self.inputs[label].bind(text=self.update_event_chance)
            grid.add_widget(self.inputs[label])

        layout.add_widget(grid)

        self.stats_lbl = Label(
            text="Sequence Window: --",
            color=get_color_from_hex(STAKE_GREEN),
            size_hint_y=None,
            height=dp(30)
        )
        layout.add_widget(self.stats_lbl)

        btn_box = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(5))
        calc_btn = StyledButton(text="Analyze Threshold")
        calc_btn.bind(on_release=self.calculate)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_box.add_widget(calc_btn)
        btn_box.add_widget(clear_btn)
        layout.add_widget(btn_box)

        self.res_grid = GridLayout(cols=3, spacing=2, size_hint_y=None)
        self.res_grid.bind(minimum_height=self.res_grid.setter('height'))
        scroll = ScrollView()
        scroll.add_widget(self.res_grid)
        layout.add_widget(scroll)

        layout.add_widget(SimpleNav())
        self.add_widget(layout)
        self.update_event_chance(None, self.inputs['Threshold'].text)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.res_grid.clear_widgets()
        self.stats_lbl.text = "Sequence Window: --"
        self.stats_lbl.color = get_color_from_hex(STAKE_GREEN)
        self.preview_lbl.text = "Threshold: --  |  Event Chance: --  |  Recovery: --"

    def update_event_chance(self, instance, value):
        try:
            m = float(value)
            if m > 1:
                chance = (99 / m)
                self.inputs['Event Chance %'].text = f"{chance:.2f}"
                self.preview_lbl.text = f"Threshold: {m:.2f}x  |  Event Chance: {chance:.2f}%  |  Recovery: updating"
        except Exception:
            pass

    def calculate(self, *args):
        self.res_grid.clear_widgets()

        try:
            bal = float(self.inputs['Capital'].text)
            base = float(self.inputs['Base Entry'].text)
            inc_raw = float(self.inputs['Increase on Negative Result %'].text)
            inc = inc_raw / 100
            m_val = float(self.inputs['Threshold'].text)

            min_inc_needed = (100 / (m_val - 1)) if m_val > 1 else 0
            t_bet = 0
            c_bet = base
            s = 0

            while (t_bet + c_bet) <= bal:
                s += 1
                t_bet += c_bet
                for v in [str(s), f"{c_bet:.8f}", f"{t_bet:.8f}"]:
                    self.res_grid.add_widget(Label(text=v, height=dp(25), size_hint_y=None, font_size='11sp'))
                c_bet += (c_bet * inc)

            prob_streak = ((1 - (99 / (m_val * 100))) ** s) * 100
            self.stats_lbl.color = get_color_from_hex(STAKE_GREEN) if inc_raw >= min_inc_needed else get_color_from_hex(STAKE_RED)
            self.stats_lbl.text = f"Max Negative Run: {s} | Min Recovery Buffer: {min_inc_needed:.2f}% | Event Rate: {prob_streak:.6f}%"
            self.preview_lbl.text = f"Threshold: {m_val:.2f}x  |  Event Chance: {99/m_val:.2f}%  |  Recovery: {min_inc_needed:.2f}%"
        except Exception:
            pass



# --- Monte Carlo Engine + Screen ---

class MonteCarloEngine:
    @staticmethod
    def run_sessions(bankroll, base_bet, multiplier, win_chance,
                     inc_on_win, inc_on_loss, stop_profit, stop_loss,
                     max_bets, sessions):
        session_profits = []
        busts = 0
        wins = 0
        total_bets = 0
        longest_loss_streak_overall = 0

        bankroll = max(0.01, float(bankroll))
        base_bet = max(0.00000001, float(base_bet))
        multiplier = max(1.01, float(multiplier))
        win_chance = max(0.0001, min(99.9999, float(win_chance)))
        inc_on_win = float(inc_on_win)
        inc_on_loss = float(inc_on_loss)
        stop_profit = float(stop_profit)
        stop_loss = float(stop_loss)
        max_bets = max(1, int(max_bets))
        sessions = max(1, int(sessions))

        for _ in range(sessions):
            bal = bankroll
            bet = base_bet
            session_start = bankroll
            bets_used = 0
            current_loss_streak = 0
            longest_loss_streak = 0
            session_won = False

            for _bet_index in range(max_bets):
                bets_used += 1

                if bet > bal:
                    busts += 1
                    break

                roll = random.uniform(0, 100)
                is_win = roll <= win_chance

                if is_win:
                    profit = bet * (multiplier - 1.0)
                    bal += profit
                    wins += 1
                    session_won = True
                    current_loss_streak = 0

                    if inc_on_win == 0:
                        bet = base_bet
                    else:
                        bet = max(base_bet, bet * (1.0 + inc_on_win / 100.0))
                else:
                    bal -= bet
                    current_loss_streak += 1
                    longest_loss_streak = max(longest_loss_streak, current_loss_streak)

                    if bal <= 0:
                        busts += 1
                        bal = 0
                        break

                    if inc_on_loss == 0:
                        bet = base_bet
                    else:
                        bet = max(base_bet, bet * (1.0 + inc_on_loss / 100.0))

                profit_now = bal - session_start

                if stop_profit > 0 and profit_now >= stop_profit:
                    break
                if stop_loss > 0 and -profit_now >= stop_loss:
                    break

            total_bets += bets_used
            longest_loss_streak_overall = max(longest_loss_streak_overall, longest_loss_streak)
            session_profits.append(bal - bankroll)

        average_profit = statistics.mean(session_profits) if session_profits else 0.0
        median_profit = statistics.median(session_profits) if session_profits else 0.0
        best_session = max(session_profits) if session_profits else 0.0
        worst_session = min(session_profits) if session_profits else 0.0

        return {
            "sessions": sessions,
            "average_profit": average_profit,
            "median_profit": median_profit,
            "best_session": best_session,
            "worst_session": worst_session,
            "win_rate": (wins / max(1, total_bets)) * 100.0,
            "bust_rate": (busts / max(1, sessions)) * 100.0,
            "avg_bets": total_bets / max(1, sessions),
            "longest_loss_streak": longest_loss_streak_overall,
        }

class MonteCarloScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        outer.add_widget(build_info_header("MONTE CARLO SIMULATOR", MONTE_CARLO_HELP))

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))

        self.mc_inputs = {}

        fields = [
            ("Capital", "1000"),
            ("Base Entry", "10"),
            ("Threshold", "2.10"),
            ("Event Chance %", "47.14"),
            ("Increase on Positive Result %", "0"),
            ("Increase on Negative Result %", "35"),
            ("Stop Net Units", "150"),
            ("Stop Deficit", "200"),
            ("Max Entries / Session", "20"),
            ("Number of Sessions", "1500"),
        ]

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for label_text, default in fields:
            lbl = Label(
                text=label_text,
                color=get_color_from_hex(STAKE_TEXT),
                font_size='12sp',
                size_hint_y=None,
                height=dp(36)
            )
            ti = StyledInput(text=default)
            self.mc_inputs[label_text] = ti
            grid.add_widget(lbl)
            grid.add_widget(ti)

        inner.add_widget(grid)

        self._mc_sync_guard = False
        self.mc_inputs["Threshold"].bind(text=self.on_multiplier_change)

        btn_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
        self.run_btn = StyledButton(text="RUN MONTE\nCARLO", height=dp(52))
        self.run_btn.font_size = '11sp'
        self.run_btn.halign = 'center'
        self.run_btn.valign = 'middle'
        self.run_btn.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        self.run_btn.bind(on_release=self.run_monte_carlo)

        fill_btn = StyledButton(text="LOAD FROM\nTHRESHOLD CALC", bg_color="#2c3e50", height=dp(52))
        fill_btn.font_size = '11sp'
        fill_btn.halign = 'center'
        fill_btn.valign = 'middle'
        fill_btn.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        fill_btn.color = (1, 1, 1, 1)
        fill_btn.bind(on_release=self.load_from_dice_calc)

        clear_btn = StyledButton(text="CLEAR\nVALUES", bg_color=SOFT_RED, height=dp(52))
        clear_btn.font_size = '11sp'
        clear_btn.halign = 'center'
        clear_btn.valign = 'middle'
        clear_btn.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)

        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(fill_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp', size_hint_y=None, height=dp(22))
        inner.add_widget(self.status_lbl)
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.progress_bar)

        self.summary = Label(
            text="Results will appear here",
            color=get_color_from_hex(STAKE_GREEN),
            font_size='14sp',
            size_hint_y=None,
            height=dp(80)
        )
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=2, spacing=dp(4), size_hint_y=None, padding=[dp(10), dp(8)])
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        apply_result_card_style(self.results_grid)
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)
        self.on_multiplier_change(None, self.mc_inputs["Threshold"].text)

    def clear_values(self, *args):
        clear_input_widgets(self.mc_inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Results will appear here"
        self._mc_last_result = None

    def on_multiplier_change(self, instance, value):
        if self._mc_sync_guard:
            return
        try:
            multi = max(1.01, float(value))
            chance = max(0.01, min(99.99, 99 / multi))
            self._mc_sync_guard = True
            self.mc_inputs["Event Chance %"].text = f"{chance:.2f}"
        except Exception:
            pass
        finally:
            self._mc_sync_guard = False

    def load_from_dice_calc(self, *args):
        try:
            dice_screen = App.get_running_app().root.get_screen('dice')
            self.mc_inputs["Capital"].text = dice_screen.inputs["Balance"].text
            self.mc_inputs["Base Entry"].text = dice_screen.inputs["Base Entry"].text
            self.mc_inputs["Threshold"].text = dice_screen.inputs["Threshold"].text
            self.mc_inputs["Event Chance %"].text = dice_screen.inputs["Event Chance %"].text
            self.mc_inputs["Increase on Negative Result %"].text = dice_screen.inputs["Increase on Negative Result %"].text
            self.summary.text = "Loaded values from Threshold Multiplier"
        except Exception as e:
            self.summary.text = f"Load failed: {e}"

    def add_result_row(self, label, value, good=None):
        color = get_color_from_hex(STAKE_TEXT)
        if good is True:
            color = get_color_from_hex(STAKE_GREEN)
        elif good is False:
            color = get_color_from_hex(STAKE_RED)

        self.results_grid.add_widget(
            Label(
                text=label,
                color=get_color_from_hex(STAKE_TEXT),
                size_hint_y=None,
                height=dp(28),
                font_size='12sp'
            )
        )
        self.results_grid.add_widget(
            Label(
                text=value,
                color=color,
                size_hint_y=None,
                height=dp(28),
                font_size='12sp'
            )
        )

    def _set_progress(self, value, text):
        self.progress_bar.value = value
        self.status_lbl.text = text

    def _finish_monte_carlo(self, result):
        self.run_btn.disabled = False
        self.progress_bar.value = self.progress_bar.max
        self.status_lbl.text = "Status: Complete"
        self.summary.text = f"Completed {result['sessions']:,} sessions"
        self.results_grid.clear_widgets()
        self.add_result_row("Average Net Units", f"{result['average_profit']:.4f}", result['average_profit'] >= 0)
        self.add_result_row("Median Net Units", f"{result['median_profit']:.4f}", result['median_profit'] >= 0)
        self.add_result_row("Best Session", f"{result['best_session']:.4f}", True)
        self.add_result_row("Worst Session", f"{result['worst_session']:.4f}", False)
        self.add_result_row("Positive Rate", f"{result['win_rate']:.2f}%")
        self.add_result_row("Threshold Rate", f"{result['bust_rate']:.2f}%", False if result['bust_rate'] > 50 else None)
        self.add_result_row("Avg Entries / Session", f"{result['avg_bets']:.2f}")
        self.add_result_row("Longest Negative Streak", str(result['longest_loss_streak']))
        # Share button
        self._mc_last_result = result
        share_btn = StyledButton(text="SHARE RESULT", bg_color=UTILITY_COLOR)
        share_btn.color = (1, 1, 1, 1)
        share_btn.size_hint_y = None
        share_btn.height = dp(42)
        share_btn.bind(on_release=self._share_mc_result)
        self.results_grid.add_widget(share_btn)
        self.results_grid.add_widget(Label(size_hint_y=None, height=dp(42)))

    def _share_mc_result(self, *args):
        r = getattr(self, '_mc_last_result', None)
        if not r:
            return
        share_result("Monte Carlo Simulator", [
            f"Sessions:              {r['sessions']:,}",
            f"Average Net Units:        {r['average_profit']:.4f}",
            f"Median Net Units:         {r['median_profit']:.4f}",
            f"Best Session:          {r['best_session']:.4f}",
            f"Worst Session:         {r['worst_session']:.4f}",
            f"Positive Rate:              {r['win_rate']:.2f}%",
            f"Threshold Rate:             {r['bust_rate']:.2f}%",
            f"Avg Bets / Session:    {r['avg_bets']:.2f}",
            f"Longest Negative Streak:   {r['longest_loss_streak']}",
        ])

    def run_monte_carlo(self, *args):
        self.results_grid.clear_widgets()
        bankroll = safe_float(self.mc_inputs["Capital"].text, 20)
        base_bet = safe_float(self.mc_inputs["Base Entry"].text, 0.1)
        multiplier = safe_float(self.mc_inputs["Threshold"].text, 2.0)
        win_chance = safe_float(self.mc_inputs["Event Chance %"].text, 49.5)
        inc_on_win = safe_float(self.mc_inputs["Increase on Positive Result %"].text, 0)
        inc_on_loss = safe_float(self.mc_inputs["Increase on Negative Result %"].text, 100)
        stop_profit = safe_float(self.mc_inputs["Stop Net Units"].text, 0)
        stop_loss = safe_float(self.mc_inputs["Stop Deficit"].text, 0)
        max_bets = safe_int(self.mc_inputs["Max Entries / Session"].text, 20)
        sessions = safe_int(self.mc_inputs["Number of Sessions"].text, 5000)
        if bankroll <= 0 or base_bet <= 0:
            self.summary.text = "Capital and Base Entry must be greater than 0"
            return
        if base_bet > bankroll:
            self.summary.text = "Base Entry cannot be greater than Capital"
            return
        self.run_btn.disabled = True
        self.progress_bar.max = max(1, sessions)
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Running Monte Carlo..."
        def worker():
            batch = max(10, sessions // 100)
            all_results=[]; busts=0; wins=0; total_bets=0; longest=0
            done=0
            while done < sessions:
                cur=min(batch, sessions-done)
                result = MonteCarloEngine.run_sessions(bankroll, base_bet, multiplier, win_chance, inc_on_win, inc_on_loss, stop_profit, stop_loss, max_bets, cur)
                # approximate aggregation by expanding session metrics
                all_results.extend([result['average_profit']]*cur)
                busts += result['bust_rate'] * cur / 100.0
                wins += result['win_rate'] * cur / 100.0
                total_bets += result['avg_bets'] * cur
                longest = max(longest, result['longest_loss_streak'])
                done += cur
                _ui_call(self._set_progress, done, f"Status: Running {done}/{sessions} sessions")
            final = {
                'sessions': sessions,
                'average_profit': statistics.mean(all_results) if all_results else 0.0,
                'median_profit': statistics.median(all_results) if all_results else 0.0,
                'best_session': max(all_results) if all_results else 0.0,
                'worst_session': min(all_results) if all_results else 0.0,
                'win_rate': (wins / sessions) * 100 if sessions else 0.0,
                'bust_rate': (busts / sessions) * 100 if sessions else 0.0,
                'avg_bets': total_bets / sessions if sessions else 0.0,
                'longest_loss_streak': longest,
            }
            _ui_call(self._finish_monte_carlo, final)
        threading.Thread(target=worker, daemon=True).start()


class KenoMonteCarloScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))
        outer.add_widget(build_info_header("SPATIAL DISTRIBUTION LAB"))

        preview = GridLayout(cols=5, spacing=dp(4), size_hint_y=None, height=dp(114))
        for i in range(25):
            node = Label(
                text='•',
                color=get_color_from_hex(PRESENTATION_ACCENT if i % 4 else PRESENTATION_ACCENT_ALT),
                font_size='18sp',
                bold=True,
            )
            with node.canvas.before:
                Color(rgba=get_color_from_hex(STAKE_INPUT))
                node._bg = RoundedRectangle(pos=node.pos, size=node.size, radius=[dp(8)])
            node.bind(pos=lambda inst, val: setattr(inst._bg, 'pos', val), size=lambda inst, val: setattr(inst._bg, 'size', val))
            preview.add_widget(node)
        outer.add_widget(preview)

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))

        self.inputs = {}
        fields = [
            ("Capital", "1000"),
            ("Base Entry", "10"),
            ("Data Points", "10"),
            ("Positive Event %", "28.0"),
            ("Tier A Multiplier", "3.5"),
            ("Tier B Multiplier", "8"),
            ("Tier C Multiplier", "13"),
            ("Peak Multiplier", "63"),
            ("Increase on Negative Result %", "35"),
            ("Max Runs / Session", "12"),
            ("Number of Sessions", "1200"),
        ]

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for label_text, default in fields:
            lbl = Label(text=label_text, color=get_color_from_hex(STAKE_TEXT), font_size='12sp', size_hint_y=None, height=dp(36))
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(lbl)
            grid.add_widget(ti)
        inner.add_widget(grid)

        info = Label(
            text="Node model: clear / tier A / tier B / tier C / peak weighted outcome model",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(30)
        )
        inner.add_widget(info)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        self.run_btn = StyledButton(text="RUN SPATIAL MODEL")
        self.run_btn.bind(on_release=self.run_keno_mc)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp', size_hint_y=None, height=dp(22))
        inner.add_widget(self.status_lbl)
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.progress_bar)

        self.summary = Label(text="Results will appear here", color=get_color_from_hex(STAKE_GREEN), font_size='14sp', size_hint_y=None, height=dp(80))
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=2, spacing=dp(4), size_hint_y=None, padding=[dp(10), dp(8)])
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        apply_result_card_style(self.results_grid)
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Results will appear here"

    def add_result_row(self, label, value, good=None):
        color = get_color_from_hex(STAKE_TEXT)
        if good is True:
            color = get_color_from_hex(STAKE_GREEN)
        elif good is False:
            color = get_color_from_hex(STAKE_RED)
        self.results_grid.add_widget(Label(text=label, color=get_color_from_hex(STAKE_TEXT), size_hint_y=None, height=dp(28), font_size='12sp'))
        self.results_grid.add_widget(Label(text=value, color=color, size_hint_y=None, height=dp(28), font_size='12sp'))

    def weighted_keno_outcome(self, hit_chance):
        hit_chance = max(0.0, min(100.0, hit_chance))
        pay_prob = hit_chance / 100.0
        miss_prob = 1.0 - pay_prob
        r = random.random()
        if r < miss_prob:
            return "clear"
        pay_roll = random.random()
        if pay_roll < 0.70:
            return "tier_a"
        elif pay_roll < 0.90:
            return "tier_b"
        elif pay_roll < 0.98:
            return "tier_c"
        else:
            return "peak"

    def _set_progress(self, value, text):
        self.progress_bar.value = value
        self.status_lbl.text = text

    def _finish_keno_mc(self, payload):
        self.run_btn.disabled = False
        self.progress_bar.value = self.progress_bar.max
        self.status_lbl.text = "Status: Complete"
        self.summary.text = f"Completed {payload['sessions']:,} analysis sessions"
        self.results_grid.clear_widgets()
        self.add_result_row("Data Points", str(payload['picks']))
        self.add_result_row("Average Net Units", f"{payload['avg_profit']:.4f}", payload['avg_profit'] >= 0)
        self.add_result_row("Median Net Units", f"{payload['median_profit']:.4f}", payload['median_profit'] >= 0)
        self.add_result_row("Best Session", f"{payload['best_session']:.4f}", True)
        self.add_result_row("Worst Session", f"{payload['worst_session']:.4f}", False)
        self.add_result_row("Session Deficit Rate", f"{payload['bust_rate']:.2f}%", False if payload['bust_rate'] > 50 else None)
        self.add_result_row("Positive Sessions", f"{payload['profitable_rate']:.2f}%", True if payload['profitable_rate'] >= 50 else None)
        self.add_result_row("Avg Runs / Session", f"{payload['avg_bets']:.2f}")
        self.add_result_row("Longest Negative Run", str(payload['longest_loss_streak_seen']))
        self.add_result_row("Total Positive Events", str(payload['total_hits']))
        self.add_result_row("Tier A Events", str(payload['small_hits']))
        self.add_result_row("Tier B Events", str(payload['medium_hits']))
        self.add_result_row("Tier C Events", str(payload['big_hits']))
        self.add_result_row("Peak Events", str(payload['jackpot_hits']))

    def run_keno_mc(self, *args):
        self.results_grid.clear_widgets()
        bankroll = safe_float(self.inputs["Capital"].text, 20)
        base_bet = safe_float(self.inputs["Base Entry"].text, 0.1)
        picks = safe_int(self.inputs["Data Points"].text, 10)
        hit_chance = safe_float(self.inputs["Positive Event %"].text, 28.0)
        small_mult = safe_float(self.inputs["Tier A Multiplier"].text, 3.5)
        medium_mult = safe_float(self.inputs["Tier B Multiplier"].text, 8)
        big_mult = safe_float(self.inputs["Tier C Multiplier"].text, 13)
        jackpot_mult = safe_float(self.inputs["Peak Multiplier"].text, 63)
        inc_loss = safe_float(self.inputs["Increase on Negative Result %"].text, 50)
        max_bets = safe_int(self.inputs["Max Runs / Session"].text, 11)
        sessions = safe_int(self.inputs["Number of Sessions"].text, 5000)
        if bankroll <= 0 or base_bet <= 0:
            self.summary.text = "Capital and Base Entry must be greater than 0"; return
        if base_bet > bankroll:
            self.summary.text = "Base Entry cannot be greater than Capital"; return
        self.run_btn.disabled = True
        self.progress_bar.max = max(1, sessions)
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Running Spatial Distribution Lab..."
        def worker():
            session_results=[]; busts=small_hits=medium_hits=big_hits=jackpot_hits=profitable_sessions=0; longest=0; total_bets=0
            for i in range(max(1, sessions)):
                balance=bankroll; bet=base_bet; session_profit=0.0; loss_streak=0; bets_used=0
                for _roll in range(max(1, max_bets)):
                    if bet <= 0 or bet > balance:
                        busts += 1; break
                    balance -= bet; bets_used += 1
                    outcome = self.weighted_keno_outcome(hit_chance)
                    if outcome == 'clear':
                        session_profit -= bet; loss_streak += 1; longest = max(longest, loss_streak); bet = bet * (1 + inc_loss / 100.0)
                    else:
                        loss_streak = 0
                        if outcome == 'tier_a': payout = bet * small_mult; small_hits += 1
                        elif outcome == 'tier_b': payout = bet * medium_mult; medium_hits += 1
                        elif outcome == 'tier_c': payout = bet * big_mult; big_hits += 1
                        else: payout = bet * jackpot_mult; jackpot_hits += 1
                        profit = payout - bet; balance += payout; session_profit += profit; break
                total_bets += bets_used; session_results.append(session_profit)
                if session_profit > 0: profitable_sessions += 1
                if (i+1) % max(1, sessions//100) == 0 or i == sessions-1:
                    _ui_call(self._set_progress, i+1, f"Status: Running {i+1}/{sessions} sessions")
            payload={
                'sessions': sessions, 'picks': picks,
                'avg_profit': statistics.mean(session_results) if session_results else 0.0,
                'median_profit': statistics.median(session_results) if session_results else 0.0,
                'best_session': max(session_results) if session_results else 0.0,
                'worst_session': min(session_results) if session_results else 0.0,
                'bust_rate': (busts/sessions)*100 if sessions else 0.0,
                'profitable_rate': (profitable_sessions/sessions)*100 if sessions else 0.0,
                'avg_bets': total_bets/sessions if sessions else 0.0,
                'longest_loss_streak_seen': longest,
                'total_hits': small_hits+medium_hits+big_hits+jackpot_hits,
                'small_hits': small_hits, 'medium_hits': medium_hits, 'big_hits': big_hits, 'jackpot_hits': jackpot_hits,
            }
            _ui_call(self._finish_keno_mc, payload)
        threading.Thread(target=worker, daemon=True).start()



class DiceOptimizerScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        outer.add_widget(build_info_header(get_tool_display_title('dice_opt').upper()))

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))

        self.inputs = {}

        fields = [
            ("Capital", "1000"),
            ("Event Chance %", "47.14"),
            ("Base Entry Start", "5"),
            ("Base Entry End", "20"),
            ("Base Entry Step", "5"),
            ("Multiplier Start", "1.80"),
            ("Multiplier End", "2.40"),
            ("Multiplier Step", "0.20"),
            ("Negative % Start", "15"),
            ("Negative % End", "45"),
            ("Negative % Step", "10"),
            ("Max Entries / Session", "12"),
            ("Sessions / Test", "300"),
            ("Top Results", "6"),
        ]

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for label_text, default in fields:
            lbl = Label(
                text=label_text,
                color=get_color_from_hex(STAKE_TEXT),
                font_size='12sp',
                size_hint_y=None,
                height=dp(36)
            )
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(lbl)
            grid.add_widget(ti)

        inner.add_widget(grid)

        # Simulation Quality
        quality_row = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(40))
        quality_row.add_widget(Label(
            text="Simulation Quality",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='12sp'
        ))
        self.quality_spinner = Spinner(
            text='Fast',
            values=('Fast', 'Balanced', 'Accurate', 'Extreme'),
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex(STAKE_INPUT),
            color=(1, 1, 1, 1)
        )
        quality_row.add_widget(self.quality_spinner)
        inner.add_widget(quality_row)

        # Optimize For
        goal_row = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(40))
        goal_row.add_widget(Label(
            text="Optimize For",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='12sp'
        ))
        self.goal_spinner = Spinner(
            text='Net Units/Risk',
            values=('Net Units', 'Safety', 'Net Units/Risk'),
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex(STAKE_INPUT),
            color=(1, 1, 1, 1)
        )
        goal_row.add_widget(self.goal_spinner)
        inner.add_widget(goal_row)

        info = Label(
            text="Tests multiple analytical progression combinations and ranks the best results",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(30)
        )
        inner.add_widget(info)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        self.run_btn = StyledButton(text="RUN OPTIMIZER")
        self.run_btn.bind(on_release=self.run_optimizer)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp', size_hint_y=None, height=dp(22))
        inner.add_widget(self.status_lbl)
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.progress_bar)

        self.summary = Label(
            text="Optimizer results will appear here",
            color=get_color_from_hex(STAKE_GREEN),
            font_size='14sp',
            size_hint_y=None,
            height=dp(80)
        )
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Optimizer results will appear here"

    def frange(self, start, end, step):
        vals = []
        if step <= 0:
            return [start]
        x = start
        while x <= end + 1e-9:
            vals.append(round(x, 8))
            x += step
        return vals

    def get_sessions_for_quality(self):
        quality = self.quality_spinner.text
        if quality == "Fast":
            return 1000
        elif quality == "Balanced":
            return 5000
        elif quality == "Accurate":
            return 20000
        else:
            return 50000

    def compute_score(self, avg_profit, bust_rate, win_rate):
        goal = self.goal_spinner.text

        if goal == "Net Units":
            return avg_profit

        elif goal == "Safety":
            # reward low bust + decent win rate
            return (win_rate * 0.2) - (bust_rate * 3.0)

        else:  # Profit/Risk
            # reward profit but penalize bust strongly
            return avg_profit - (bust_rate * 0.25)

    def add_result_card(self, rank, item):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(118),
            padding=dp(8),
            spacing=dp(3)
        )

        def update_rect(instance, value):
            if hasattr(instance, '_bg_rect'):
                instance._bg_rect.pos = instance.pos
                instance._bg_rect.size = instance.size

        with card.canvas.before:
            Color(rgba=get_color_from_hex(STAKE_INPUT))
            card._bg_rect = Rectangle(pos=card.pos, size=card.size)

        card.bind(pos=update_rect, size=update_rect)

        title = Label(
            text=f"#{rank} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}%",
            color=get_color_from_hex(STAKE_GREEN),
            bold=True,
            font_size='12sp',
            size_hint_y=None,
            height=dp(24)
        )

        row1 = Label(
            text=f"Base: {item['base_bet']} | Multi: {item['multiplier']} | Negative+ {item['loss_pct']}%",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row2 = Label(
            text=f"Positive Rate: {item['win_rate']:.2f}% | Max Entries: {item['max_bets']} | Longest NS: {item['longest_ls']}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row3 = Label(
            text=f"Median: {item['median_profit']:.4f} | Best: {item['best_session']:.4f} | Worst: {item['worst_session']:.4f}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row4 = Label(
            text=f"Score: {item['score']:.4f} | Quality: {self.quality_spinner.text} | Goal: {self.goal_spinner.text}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='10sp',
            size_hint_y=None,
            height=dp(18)
        )

        card.add_widget(title)
        card.add_widget(row1)
        card.add_widget(row2)
        card.add_widget(row3)
        card.add_widget(row4)

        self.results_grid.add_widget(card)

    def _set_progress(self, value, text):
        self.progress_bar.value = value
        self.status_lbl.text = text

    def _finish_optimizer(self, combos, top_results):
        self.run_btn.disabled = False
        self.progress_bar.value = self.progress_bar.max
        self.status_lbl.text = "Status: Complete"
        self.results_grid.clear_widgets()
        combos.sort(key=lambda x: x["score"], reverse=True)
        show_n = max(1, min(top_results, len(combos)))
        self.summary.text = (
            f"Tested {len(combos)} combinations | "
            f"Showing top {show_n} | "
            f"Quality: {self.quality_spinner.text} | "
            f"Goal: {self.goal_spinner.text}"
        )
        for i, item in enumerate(combos[:show_n], start=1):
            self.add_result_card(i, item)

    def run_optimizer(self, *args):
        self.results_grid.clear_widgets()
        bankroll = safe_float(self.inputs["Capital"].text, 20)
        win_chance = safe_float(self.inputs["Event Chance %"].text, 49.5)
        base_start = safe_float(self.inputs["Base Entry Start"].text, 0.05)
        base_end = safe_float(self.inputs["Base Entry End"].text, 0.20)
        base_step = safe_float(self.inputs["Base Entry Step"].text, 0.05)
        multi_start = safe_float(self.inputs["Multiplier Start"].text, 2.0)
        multi_end = safe_float(self.inputs["Multiplier End"].text, 3.5)
        multi_step = safe_float(self.inputs["Multiplier Step"].text, 0.5)
        loss_start = safe_float(self.inputs["Negative % Start"].text, 20)
        loss_end = safe_float(self.inputs["Negative % End"].text, 60)
        loss_step = safe_float(self.inputs["Negative % Step"].text, 10)
        max_bets = safe_int(self.inputs["Max Entries / Session"].text, 12)
        manual_sessions = safe_int(self.inputs["Sessions / Test"].text, 1000)
        top_results = safe_int(self.inputs["Top Results"].text, 10)
        if bankroll <= 0:
            self.summary.text = "Capital must be greater than 0"
            return
        sessions_per_test = self.get_sessions_for_quality()
        if manual_sessions > 0:
            sessions_per_test = manual_sessions if self.quality_spinner.text == "Fast" else sessions_per_test
        combos_to_test=[]
        for base_bet in self.frange(base_start, base_end, base_step):
            for multiplier in self.frange(multi_start, multi_end, multi_step):
                for loss_pct in self.frange(loss_start, loss_end, loss_step):
                    if base_bet <= bankroll:
                        combos_to_test.append((base_bet, multiplier, loss_pct))
        self.run_btn.disabled = True
        self.progress_bar.max = max(1, len(combos_to_test))
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Running optimizer..."
        def worker():
            combos=[]
            total=len(combos_to_test)
            for idx,(base_bet,multiplier,loss_pct) in enumerate(combos_to_test, start=1):
                result = MonteCarloEngine.run_sessions(
                    bankroll=bankroll, base_bet=base_bet, multiplier=multiplier, win_chance=win_chance,
                    inc_on_win=0, inc_on_loss=loss_pct, stop_profit=0, stop_loss=0,
                    max_bets=max_bets, sessions=sessions_per_test)
                score = self.compute_score(result['average_profit'], result['bust_rate'], result['win_rate'])
                combos.append({
                    'base_bet': base_bet, 'multiplier': multiplier, 'loss_pct': loss_pct, 'max_bets': max_bets,
                    'avg_profit': result['average_profit'], 'median_profit': result['median_profit'],
                    'best_session': result['best_session'], 'worst_session': result['worst_session'],
                    'win_rate': result['win_rate'], 'bust_rate': result['bust_rate'],
                    'longest_ls': result['longest_loss_streak'], 'score': score,
                })
                if idx % max(1, total//100) == 0 or idx == total:
                    _ui_call(self._set_progress, idx, f"Status: Testing {idx}/{total} combos")
            _ui_call(self._finish_optimizer, combos, top_results)
        threading.Thread(target=worker, daemon=True).start()

class DiceAutoGeneratorScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        outer.add_widget(build_info_header("SEQUENCE AUTOMATOR"))

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))

        self.inputs = {}

        fields = [
            ("Capital", "1000"),
            ("Event Chance %", "47.14"),
            ("Strategies To Generate", "40"),
            ("Sessions / Strategy", "500"),
            ("Max Entries / Session", "12"),
            ("Top Results", "6"),
        ]

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for label_text, default in fields:
            lbl = Label(
                text=label_text,
                color=get_color_from_hex(STAKE_TEXT),
                font_size='12sp',
                size_hint_y=None,
                height=dp(36)
            )
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(lbl)
            grid.add_widget(ti)

        inner.add_widget(grid)

        goal_row = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(40))
        goal_row.add_widget(Label(
            text="Optimize For",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='12sp'
        ))
        self.goal_spinner = Spinner(
            text='Net Units/Risk',
            values=('Net Units', 'Safety', 'Net Units/Risk'),
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex(STAKE_INPUT),
            color=(1, 1, 1, 1)
        )
        goal_row.add_widget(self.goal_spinner)
        inner.add_widget(goal_row)

        info = Label(
            text="Generates random sequence structures and keeps the strongest results",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(30)
        )
        inner.add_widget(info)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        self.run_btn = StyledButton(text="RUN AUTO GENERATOR")
        self.run_btn.bind(on_release=self.run_generator)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp', size_hint_y=None, height=dp(22))
        inner.add_widget(self.status_lbl)
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.progress_bar)

        self.summary = Label(
            text="Generated strategy results will appear here",
            color=get_color_from_hex(STAKE_GREEN),
            font_size='14sp',
            size_hint_y=None,
            height=dp(80)
        )
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Generated strategy results will appear here"

    def compute_score(self, avg_profit, bust_rate, win_rate):
        goal = self.goal_spinner.text

        if goal == "Net Units":
            return avg_profit
        elif goal == "Safety":
            return (win_rate * 0.2) - (bust_rate * 3.0)
        else:
            return avg_profit - (bust_rate * 0.25)

    def random_strategy(self, bankroll):
        base_bet = round(random.uniform(0.01, min(0.25, bankroll * 0.02)), 4)
        multiplier = round(random.uniform(1.8, 5.0), 2)
        loss_pct = round(random.uniform(10, 80), 2)
        return {
            "base_bet": base_bet,
            "multiplier": multiplier,
            "loss_pct": loss_pct,
        }

    def save_generated_strategy(self, item, rank):
        strategy = normalize_strategy({
            "name": f"DICE GEN | B{item['base_bet']} M{item['multiplier']} L{item['loss_pct']}",
            "category": "Sequence Automator",
            "game": "dice",
            "source": "auto_generator",
            "bank": str(self.inputs["Capital"].text),
            "base": str(item["base_bet"]),
            "multi": str(item["multiplier"]),
            "win_action": "Reset",
            "loss_action": f"Increase {item['loss_pct']}%",
            "max_bets": str(item["max_bets"]),
            "notes": (
                f"Saved from Auto Generator | Rank #{rank} | "
                f"Avg {item['avg_profit']:.4f} | "
                f"Threshold {item['bust_rate']:.2f}% | "
                f"Score {item['score']:.4f} | "
                f"Goal {self.goal_spinner.text}"
            )
        })

        GLOBAL_BANK.strategies.append(strategy)
        GLOBAL_BANK.save_strategies()

        Popup(
            title="Saved",
            content=Label(text=f"Saved:\n{strategy['name']}"),
            size_hint=(0.75, 0.25)
        ).open()

    def add_result_card(self, rank, item):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(156),
            padding=dp(8),
            spacing=dp(3)
        )

        def update_rect(instance, value):
            if hasattr(instance, '_bg_rect'):
                instance._bg_rect.pos = instance.pos
                instance._bg_rect.size = instance.size

        with card.canvas.before:
            Color(rgba=get_color_from_hex(STAKE_INPUT))
            card._bg_rect = Rectangle(pos=card.pos, size=card.size)

        card.bind(pos=update_rect, size=update_rect)

        title = Label(
            text=f"#{rank} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}%",
            color=get_color_from_hex(STAKE_GREEN),
            bold=True,
            font_size='12sp',
            size_hint_y=None,
            height=dp(24)
        )

        row1 = Label(
            text=f"Base: {item['base_bet']} | Multi: {item['multiplier']} | Negative+ {item['loss_pct']}%",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row2 = Label(
            text=f"Positive Rate: {item['win_rate']:.2f}% | Max Entries: {item['max_bets']} | Longest NS: {item['longest_ls']}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row3 = Label(
            text=f"Median: {item['median_profit']:.4f} | Best: {item['best_session']:.4f} | Worst: {item['worst_session']:.4f}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row4 = Label(
            text=f"Score: {item['score']:.4f} | Goal: {self.goal_spinner.text}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='10sp',
            size_hint_y=None,
            height=dp(18)
        )

        save_btn = StyledButton(
            text="SAVE TO LIBRARY",
            bg_color="#2c3e50",
            height=dp(34)
        )
        save_btn.color = (1, 1, 1, 1)
        save_btn.bind(on_release=lambda x: self.save_generated_strategy(item, rank))

        card.add_widget(title)
        card.add_widget(row1)
        card.add_widget(row2)
        card.add_widget(row3)
        card.add_widget(row4)
        card.add_widget(save_btn)

        self.results_grid.add_widget(card)

    def _set_progress(self, value, text):
        self.progress_bar.value = value
        self.status_lbl.text = text

    def _finish_generator(self, results, top_results):
        self.run_btn.disabled = False
        self.progress_bar.value = self.progress_bar.max
        self.status_lbl.text = "Status: Complete"
        results.sort(key=lambda x: x["score"], reverse=True)
        show_n = max(1, min(top_results, len(results)))
        self.summary.text = (
            f"Generated {len(results)} random strategies | "
            f"Showing top {show_n} | "
            f"Goal: {self.goal_spinner.text}"
        )
        self.results_grid.clear_widgets()
        for i, item in enumerate(results[:show_n], start=1):
            self.add_result_card(i, item)

    def run_generator(self, *args):
        self.results_grid.clear_widgets()
        bankroll = safe_float(self.inputs["Capital"].text, 20)
        win_chance = safe_float(self.inputs["Event Chance %"].text, 49.5)
        strategies_to_generate = safe_int(self.inputs["Strategies To Generate"].text, 100)
        sessions_per_strategy = safe_int(self.inputs["Sessions / Strategy"].text, 2000)
        max_bets = safe_int(self.inputs["Max Entries / Session"].text, 12)
        top_results = safe_int(self.inputs["Top Results"].text, 10)
        if bankroll <= 0:
            self.summary.text = "Capital must be greater than 0"; return
        self.run_btn.disabled = True
        self.progress_bar.max = max(1, strategies_to_generate)
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Generating strategies..."
        def worker():
            results=[]
            total=max(1, strategies_to_generate)
            for idx in range(total):
                strat=self.random_strategy(bankroll)
                result = MonteCarloEngine.run_sessions(bankroll, strat['base_bet'], strat['multiplier'], win_chance, 0, strat['loss_pct'], 0, 0, max_bets, sessions_per_strategy)
                score=self.compute_score(result['average_profit'], result['bust_rate'], result['win_rate'])
                results.append({
                    'base_bet': strat['base_bet'], 'multiplier': strat['multiplier'], 'loss_pct': strat['loss_pct'], 'max_bets': max_bets,
                    'avg_profit': result['average_profit'], 'median_profit': result['median_profit'], 'best_session': result['best_session'],
                    'worst_session': result['worst_session'], 'win_rate': result['win_rate'], 'bust_rate': result['bust_rate'], 'longest_ls': result['longest_loss_streak'], 'score': score,
                })
                if (idx+1) % max(1, total//100) == 0 or idx+1 == total:
                    _ui_call(self._set_progress, idx+1, f"Status: Generated {idx+1}/{total}")
            _ui_call(self._finish_generator, results, top_results)
        threading.Thread(target=worker, daemon=True).start()

class DiceEvolutionScreen(Screen):                                                                                 
    def __init__(self, **kw):
        super().__init__(**kw)

        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        outer.add_widget(build_info_header("PROBABILITY EVOLUTION", DICE_EVO_HELP))

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))

        self.inputs = {}

        fields = [
            ("Capital", "1000"),
            ("Event Chance %", "47.14"),
            ("Population Size", "18"),
            ("Generations", "3"),
            ("Elite Keep", "4"),
            ("Children Per Generation", "18"),
            ("Sessions / Strategy", "400"),
            ("Max Entries / Session", "12"),
            ("Top Results", "6"),
        ]

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for label_text, default in fields:
            lbl = Label(
                text=label_text,
                color=get_color_from_hex(STAKE_TEXT),
                font_size='12sp',
                size_hint_y=None,
                height=dp(36)
            )
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(lbl)
            grid.add_widget(ti)

        inner.add_widget(grid)

        goal_row = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(40))
        goal_row.add_widget(Label(
            text="Optimize For",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='12sp'
        ))
        self.goal_spinner = Spinner(
            text='Net Units/Risk',
            values=('Net Units', 'Safety', 'Net Units/Risk'),
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex(STAKE_INPUT),
            color=(1, 1, 1, 1)
        )
        goal_row.add_widget(self.goal_spinner)
        inner.add_widget(goal_row)

        info = Label(
            text="Evolves RNG structures across generations using mutation and elite selection",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(30)
        )
        inner.add_widget(info)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        self.run_btn = StyledButton(text="RUN EVOLUTION")
        self.run_btn.bind(on_release=self.run_evolution)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp', size_hint_y=None, height=dp(22))
        inner.add_widget(self.status_lbl)
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.progress_bar)

        self.summary = Label(
            text="Evolution results will appear here",
            color=get_color_from_hex(STAKE_GREEN),
            font_size='14sp',
            size_hint_y=None,
            height=dp(80)
        )
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Evolution results will appear here"

    def compute_score(self, avg_profit, bust_rate, win_rate):
        goal = self.goal_spinner.text
        if goal == "Net Units":
            return avg_profit
        elif goal == "Safety":
            return (win_rate * 0.2) - (bust_rate * 3.0)
        else:
            return avg_profit - (bust_rate * 0.25)

    def random_strategy(self, bankroll):
        base_bet = round(random.uniform(0.01, min(0.25, bankroll * 0.02)), 4)
        multiplier = round(random.uniform(1.8, 5.0), 2)
        loss_pct = round(random.uniform(10, 80), 2)
        return {
            "base_bet": base_bet,
            "multiplier": multiplier,
            "loss_pct": loss_pct,
        }

    def mutate_strategy(self, parent, bankroll):
        new_base = round(parent["base_bet"] * random.uniform(0.85, 1.15), 4)
        new_multi = round(parent["multiplier"] * random.uniform(0.90, 1.10), 2)
        new_loss = round(parent["loss_pct"] * random.uniform(0.85, 1.15), 2)

        new_base = max(0.01, min(new_base, min(0.25, bankroll * 0.02)))
        new_multi = max(1.5, min(new_multi, 6.0))
        new_loss = max(5.0, min(new_loss, 100.0))

        return {
            "base_bet": new_base,
            "multiplier": new_multi,
            "loss_pct": new_loss,
        }

    def evaluate_strategy(self, strat, bankroll, win_chance, max_bets, sessions_per_strategy):
        result = MonteCarloEngine.run_sessions(
            bankroll=bankroll,
            base_bet=strat["base_bet"],
            multiplier=strat["multiplier"],
            win_chance=win_chance,
            inc_on_win=0,
            inc_on_loss=strat["loss_pct"],
            stop_profit=0,
            stop_loss=0,
            max_bets=max_bets,
            sessions=sessions_per_strategy,
        )

        score = self.compute_score(
            avg_profit=result["average_profit"],
            bust_rate=result["bust_rate"],
            win_rate=result["win_rate"]
        )

        return {
            "base_bet": strat["base_bet"],
            "multiplier": strat["multiplier"],
            "loss_pct": strat["loss_pct"],
            "max_bets": max_bets,
            "avg_profit": result["average_profit"],
            "median_profit": result["median_profit"],
            "best_session": result["best_session"],
            "worst_session": result["worst_session"],
            "win_rate": result["win_rate"],
            "bust_rate": result["bust_rate"],
            "longest_ls": result["longest_loss_streak"],
            "score": score,
        }

    def save_evolved_strategy(self, item, rank):
        strategy = normalize_strategy({
            "name": f"DICE EVO | B{item['base_bet']} M{item['multiplier']} L{item['loss_pct']}",
            "category": "Experimental",
            "game": "dice",
            "source": "evolution_engine",
            "bank": str(self.inputs["Capital"].text),
            "base": str(item["base_bet"]),
            "multi": str(item["multiplier"]),
            "win_action": "Reset",
            "loss_action": f"Increase {item['loss_pct']}%",
            "max_bets": str(item["max_bets"]),
            "notes": (
                f"Saved from Evolution Engine | Rank #{rank} | "
                f"Avg {item['avg_profit']:.4f} | "
                f"Threshold {item['bust_rate']:.2f}% | "
                f"Score {item['score']:.4f} | "
                f"Goal {self.goal_spinner.text}"
            )
        })

        GLOBAL_BANK.strategies.append(strategy)
        GLOBAL_BANK.save_strategies()

        Popup(
            title="Saved",
            content=Label(text=f"Saved:\n{strategy['name']}"),
            size_hint=(0.75, 0.25)
        ).open()

    def add_result_card(self, rank, item):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(156),
            padding=dp(8),
            spacing=dp(3)
        )

        def update_rect(instance, value):
            if hasattr(instance, '_bg_rect'):
                instance._bg_rect.pos = instance.pos
                instance._bg_rect.size = instance.size

        with card.canvas.before:
            Color(rgba=get_color_from_hex(STAKE_INPUT))
            card._bg_rect = Rectangle(pos=card.pos, size=card.size)

        card.bind(pos=update_rect, size=update_rect)

        title = Label(
            text=f"#{rank} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}%",
            color=get_color_from_hex(STAKE_GREEN),
            bold=True,
            font_size='12sp',
            size_hint_y=None,
            height=dp(24)
        )

        row1 = Label(
            text=f"Base: {item['base_bet']} | Multi: {item['multiplier']} | Negative+ {item['loss_pct']}%",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row2 = Label(
            text=f"Positive Rate: {item['win_rate']:.2f}% | Max Entries: {item['max_bets']} | Longest NS: {item['longest_ls']}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row3 = Label(
            text=f"Median: {item['median_profit']:.4f} | Best: {item['best_session']:.4f} | Worst: {item['worst_session']:.4f}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row4 = Label(
            text=f"Score: {item['score']:.4f} | Goal: {self.goal_spinner.text}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='10sp',
            size_hint_y=None,
            height=dp(18)
        )

        save_btn = StyledButton(
            text="SAVE TO LIBRARY",
            bg_color="#2c3e50",
            height=dp(34)
        )
        save_btn.color = (1, 1, 1, 1)
        save_btn.bind(on_release=lambda x: self.save_evolved_strategy(item, rank))

        card.add_widget(title)
        card.add_widget(row1)
        card.add_widget(row2)
        card.add_widget(row3)
        card.add_widget(row4)
        card.add_widget(save_btn)

        self.results_grid.add_widget(card)

    def _set_progress(self, value, text):
        self.progress_bar.value = value
        self.status_lbl.text = text

    def _finish_evolution(self, unique_results, generations, top_results):
        self.run_btn.disabled = False
        self.progress_bar.value = self.progress_bar.max
        self.status_lbl.text = "Status: Complete"
        show_n = max(1, min(top_results, len(unique_results)))
        self.summary.text = f"Evolved across {generations} generations | Showing top {show_n} | Goal: {self.goal_spinner.text}"
        self.results_grid.clear_widgets()
        for i, item in enumerate(unique_results[:show_n], start=1):
            self.add_result_card(i, item)

    def run_evolution(self, *args):
        self.results_grid.clear_widgets()
        bankroll = safe_float(self.inputs["Capital"].text, 20)
        win_chance = safe_float(self.inputs["Event Chance %"].text, 49.5)
        population_size = safe_int(self.inputs["Population Size"].text, 40)
        generations = safe_int(self.inputs["Generations"].text, 5)
        elite_keep = safe_int(self.inputs["Elite Keep"].text, 8)
        children_per_generation = safe_int(self.inputs["Children Per Generation"].text, 40)
        sessions_per_strategy = safe_int(self.inputs["Sessions / Strategy"].text, 2000)
        max_bets = safe_int(self.inputs["Max Entries / Session"].text, 12)
        top_results = safe_int(self.inputs["Top Results"].text, 10)
        if bankroll <= 0: self.summary.text = "Capital must be greater than 0"; return
        self.run_btn.disabled = True
        self.progress_bar.max = max(1, generations * max(2, population_size))
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Running evolution..."
        def worker():
            population=[self.random_strategy(bankroll) for _ in range(max(2,population_size))]
            best_overall=[]; progress=0
            for gen in range(max(1, generations)):
                evaluated=[]
                for s in population:
                    evaluated.append(self.evaluate_strategy(s, bankroll, win_chance, max_bets, sessions_per_strategy))
                    progress += 1
                    if progress % max(1, self.progress_bar.max//100) == 0 or progress == self.progress_bar.max:
                        _ui_call(self._set_progress, progress, f"Status: Generation {gen+1}/{generations}")
                evaluated.sort(key=lambda x: x['score'], reverse=True)
                elites=evaluated[:max(1, elite_keep)]
                best_overall.extend(elites)
                elite_strats=[{'base_bet':e['base_bet'],'multiplier':e['multiplier'],'loss_pct':e['loss_pct']} for e in elites]
                population=[]
                while len(population) < max(2, children_per_generation):
                    population.append(self.mutate_strategy(random.choice(elite_strats), bankroll))
            best_overall.sort(key=lambda x: x['score'], reverse=True)
            seen=set(); unique_results=[]
            for item in best_overall:
                key=(round(item['base_bet'],4), round(item['multiplier'],2), round(item['loss_pct'],2))
                if key not in seen:
                    seen.add(key); unique_results.append(item)
            _ui_call(self._finish_evolution, unique_results, generations, top_results)
        threading.Thread(target=worker, daemon=True).start()
class LimboEvolutionScreen(Screen):                                                                                              
    def __init__(self, **kw):
        super().__init__(**kw)

        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        outer.add_widget(build_info_header("EXPONENTIAL GROWTH LAB", LIMBO_EVO_HELP))

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))

        self.inputs = {}

        fields = [
            ("Capital", "1000"),
            ("Population Size", "18"),
            ("Generations", "3"),
            ("Elite Keep", "4"),
            ("Children Per Generation", "18"),
            ("Sessions / Strategy", "400"),
            ("Max Entries / Session", "12"),
            ("Top Results", "6"),
        ]

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for label_text, default in fields:
            lbl = Label(
                text=label_text,
                color=get_color_from_hex(STAKE_TEXT),
                font_size='12sp',
                size_hint_y=None,
                height=dp(36)
            )
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(lbl)
            grid.add_widget(ti)

        inner.add_widget(grid)

        goal_row = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(40))
        goal_row.add_widget(Label(
            text="Optimize For",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='12sp'
        ))
        self.goal_spinner = Spinner(
            text='Net Units/Risk',
            values=('Net Units', 'Safety', 'Net Units/Risk'),
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex(STAKE_INPUT),
            color=(1, 1, 1, 1)
        )
        goal_row.add_widget(self.goal_spinner)
        inner.add_widget(goal_row)

        info = Label(
            text="Evolves threshold structures across generations using mutation and elite selection",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(30)
        )
        inner.add_widget(info)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        self.run_btn = StyledButton(text="RUN EXPONENTIAL\n GROWTH LAB")
        self.run_btn.bind(on_release=self.run_evolution)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp', size_hint_y=None, height=dp(22))
        inner.add_widget(self.status_lbl)
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.progress_bar)

        self.summary = Label(
            text="Exponential Growth Lab results will appear here",
            color=get_color_from_hex(STAKE_GREEN),
            font_size='14sp',
            size_hint_y=None,
            height=dp(80)
        )
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Exponential Growth Lab results will appear here"

    def compute_score(self, avg_profit, bust_rate, win_rate):
        goal = self.goal_spinner.text
        if goal == "Net Units":
            return avg_profit
        elif goal == "Safety":
            return (win_rate * 0.2) - (bust_rate * 3.0)
        else:
            return avg_profit - (bust_rate * 0.25)

    def random_strategy(self, bankroll):
        base_bet = round(random.uniform(0.01, min(0.25, bankroll * 0.02)), 4)
        target_multiplier = round(random.uniform(1.5, 15.0), 2)
        loss_pct = round(random.uniform(5, 80), 2)
        return {
            "base_bet": base_bet,
            "target_multiplier": target_multiplier,
            "loss_pct": loss_pct,
        }

    def mutate_strategy(self, parent, bankroll):
        new_base = round(parent["base_bet"] * random.uniform(0.85, 1.15), 4)
        new_multi = round(parent["target_multiplier"] * random.uniform(0.90, 1.10), 2)
        new_loss = round(parent["loss_pct"] * random.uniform(0.85, 1.15), 2)

        new_base = max(0.01, min(new_base, min(0.25, bankroll * 0.02)))
        new_multi = max(1.2, min(new_multi, 25.0))
        new_loss = max(1.0, min(new_loss, 100.0))

        return {
            "base_bet": new_base,
            "target_multiplier": new_multi,
            "loss_pct": new_loss,
        }

    def run_limbo_sessions(self, bankroll, base_bet, target_multiplier, inc_on_loss, max_bets, sessions):
        results = []
        busts = 0
        winning_sessions = 0
        total_bets_all = 0
        longest_loss_streak_seen = 0

        bankroll = max(0.00000001, bankroll)
        base_bet = max(0.00000001, base_bet)
        target_multiplier = max(1.01, target_multiplier)
        inc_on_loss = max(-100.0, inc_on_loss)
        max_bets = max(1, max_bets)
        sessions = max(1, sessions)

        win_chance = min(99.0, max(0.01, 99.0 / target_multiplier))

        for _ in range(sessions):
            balance = bankroll
            current_bet = base_bet
            session_profit = 0.0
            bets_used = 0
            loss_streak = 0
            busted = False

            for _roll in range(max_bets):
                if current_bet <= 0 or current_bet > balance:
                    busted = True
                    busts += 1
                    break

                bets_used += 1
                balance -= current_bet

                roll = random.uniform(0, 100.0)
                is_win = roll < win_chance

                if is_win:
                    payout = current_bet * target_multiplier
                    net_profit = payout - current_bet
                    balance += payout
                    session_profit += net_profit
                    loss_streak = 0
                    current_bet = base_bet
                else:
                    session_profit -= current_bet
                    loss_streak += 1
                    longest_loss_streak_seen = max(longest_loss_streak_seen, loss_streak)
                    current_bet = current_bet * (1 + inc_on_loss / 100.0)

            total_bets_all += bets_used
            results.append(session_profit)

            if session_profit > 0:
                winning_sessions += 1

        avg_profit = statistics.mean(results) if results else 0.0
        median_profit = statistics.median(results) if results else 0.0
        best_session = max(results) if results else 0.0
        worst_session = min(results) if results else 0.0
        win_rate = (winning_sessions / sessions) * 100 if sessions else 0.0
        bust_rate = (busts / sessions) * 100 if sessions else 0.0

        return {
            "average_profit": avg_profit,
            "median_profit": median_profit,
            "best_session": best_session,
            "worst_session": worst_session,
            "win_rate": win_rate,
            "bust_rate": bust_rate,
            "longest_loss_streak": longest_loss_streak_seen,
        }

    def evaluate_strategy(self, strat, bankroll, max_bets, sessions_per_strategy):
        result = self.run_limbo_sessions(
            bankroll=bankroll,
            base_bet=strat["base_bet"],
            target_multiplier=strat["target_multiplier"],
            inc_on_loss=strat["loss_pct"],
            max_bets=max_bets,
            sessions=sessions_per_strategy,
        )

        score = self.compute_score(
            avg_profit=result["average_profit"],
            bust_rate=result["bust_rate"],
            win_rate=result["win_rate"]
        )

        return {
            "base_bet": strat["base_bet"],
            "target_multiplier": strat["target_multiplier"],
            "loss_pct": strat["loss_pct"],
            "max_bets": max_bets,
            "avg_profit": result["average_profit"],
            "median_profit": result["median_profit"],
            "best_session": result["best_session"],
            "worst_session": result["worst_session"],
            "win_rate": result["win_rate"],
            "bust_rate": result["bust_rate"],
            "longest_ls": result["longest_loss_streak"],
            "score": score,
        }

    def save_evolved_strategy(self, item, rank):
        strategy = normalize_strategy({
            "name": f"EXP GRW | E{item['base_bet']} T{item['target_multiplier']} N{item['loss_pct']}",
            "category": "Experimental",
            "game": "limbo",
            "source": "evolution_engine",
            "bank": str(self.inputs["Capital"].text),
            "base": str(item["base_bet"]),
            "multi": str(item["target_multiplier"]),
            "win_action": "Reset",
            "loss_action": f"Increase {item['loss_pct']}%",
            "max_bets": str(item["max_bets"]),
            "notes": (
                f"Saved from Exponential Growth Lab | Rank #{rank} | "
                f"Avg {item['avg_profit']:.4f} | "
                f"Threshold {item['bust_rate']:.2f}% | "
                f"Score {item['score']:.4f} | "
                f"Goal {self.goal_spinner.text}"
            )
        })

        GLOBAL_BANK.strategies.append(strategy)
        GLOBAL_BANK.save_strategies()

        Popup(
            title="Saved",
            content=Label(text=f"Saved:\n{strategy['name']}"),
            size_hint=(0.75, 0.25)
        ).open()

    def add_result_card(self, rank, item):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(156),
            padding=dp(8),
            spacing=dp(3)
        )

        def update_rect(instance, value):
            if hasattr(instance, '_bg_rect'):
                instance._bg_rect.pos = instance.pos
                instance._bg_rect.size = instance.size

        with card.canvas.before:
            Color(rgba=get_color_from_hex(STAKE_INPUT))
            card._bg_rect = Rectangle(pos=card.pos, size=card.size)

        card.bind(pos=update_rect, size=update_rect)

        title = Label(
            text=f"#{rank} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}%",
            color=get_color_from_hex(STAKE_GREEN),
            bold=True,
            font_size='12sp',
            size_hint_y=None,
            height=dp(24)
        )

        row1 = Label(
            text=f"Base: {item['base_bet']} | Target: {item['target_multiplier']}x | Negative+ {item['loss_pct']}%",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row2 = Label(
            text=f"Positive Rate: {item['win_rate']:.2f}% | Max Entries: {item['max_bets']} | Longest NS: {item['longest_ls']}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row3 = Label(
            text=f"Median: {item['median_profit']:.4f} | Best: {item['best_session']:.4f} | Worst: {item['worst_session']:.4f}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row4 = Label(
            text=f"Score: {item['score']:.4f} | Goal: {self.goal_spinner.text}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='10sp',
            size_hint_y=None,
            height=dp(18)
        )

        save_btn = StyledButton(
            text="SAVE TO LIBRARY",
            bg_color="#2c3e50",
            height=dp(34)
        )
        save_btn.color = (1, 1, 1, 1)
        save_btn.bind(on_release=lambda x: self.save_evolved_strategy(item, rank))

        card.add_widget(title)
        card.add_widget(row1)
        card.add_widget(row2)
        card.add_widget(row3)
        card.add_widget(row4)
        card.add_widget(save_btn)

        self.results_grid.add_widget(card)

    def _set_progress(self, value, text):
        self.progress_bar.value = value
        self.status_lbl.text = text

    def _finish_evolution(self, unique_results, generations, top_results):
        self.run_btn.disabled = False
        self.progress_bar.value = self.progress_bar.max
        self.status_lbl.text = "Status: Complete"
        show_n = max(1, min(top_results, len(unique_results)))
        self.summary.text = f"Evolved Exponential Growth Lab across {generations} generations | Showing top {show_n} | Goal: {self.goal_spinner.text}"
        self.results_grid.clear_widgets()
        for i, item in enumerate(unique_results[:show_n], start=1):
            self.add_result_card(i, item)

    def run_evolution(self, *args):
        self.results_grid.clear_widgets()
        bankroll=safe_float(self.inputs['Capital'].text,20); population_size=safe_int(self.inputs['Population Size'].text,40); generations=safe_int(self.inputs['Generations'].text,5); elite_keep=safe_int(self.inputs['Elite Keep'].text,8); children_per_generation=safe_int(self.inputs['Children Per Generation'].text,40); sessions_per_strategy=safe_int(self.inputs['Sessions / Strategy'].text,2000); max_bets=safe_int(self.inputs['Max Entries / Session'].text,12); top_results=safe_int(self.inputs['Top Results'].text,10)
        if bankroll<=0: self.summary.text='Capital must be greater than 0'; return
        self.run_btn.disabled=True; self.progress_bar.max=max(1, generations*max(2,population_size)); self.progress_bar.value=0; self.status_lbl.text='Status: Running evolution...'
        def worker():
            population=[self.random_strategy(bankroll) for _ in range(max(2,population_size))]; best_overall=[]; progress=0
            for gen in range(max(1,generations)):
                evaluated=[]
                for s in population:
                    evaluated.append(self.evaluate_strategy(s, bankroll, max_bets, sessions_per_strategy)); progress += 1
                    if progress % max(1,self.progress_bar.max//100) == 0 or progress == self.progress_bar.max:
                        _ui_call(self._set_progress, progress, f'Status: Generation {gen+1}/{generations}')
                evaluated.sort(key=lambda x:x['score'], reverse=True); elites=evaluated[:max(1,elite_keep)]; best_overall.extend(elites)
                elite_strats=[{'base_bet':e['base_bet'],'target_multiplier':e['target_multiplier'],'loss_pct':e['loss_pct']} for e in elites]
                population=[]
                while len(population)<max(2,children_per_generation): population.append(self.mutate_strategy(random.choice(elite_strats), bankroll))
            best_overall.sort(key=lambda x:x['score'], reverse=True)
            seen=set(); unique_results=[]
            for item in best_overall:
                key=(round(item['base_bet'],4), round(item['target_multiplier'],2), round(item['loss_pct'],2))
                if key not in seen: seen.add(key); unique_results.append(item)
            _ui_call(self._finish_evolution, unique_results, generations, top_results)
        threading.Thread(target=worker, daemon=True).start()
class KenoEvolutionScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        outer.add_widget(build_info_header("PATTERN EVOLUTION", KENO_EVO_HELP))

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))

        self.inputs = {}

        fields = [
            ("Capital", "1000"),
            ("Population Size", "16"),
            ("Generations", "3"),
            ("Elite Keep", "4"),
            ("Children Per Generation", "16"),
            ("Sessions / Strategy", "300"),
            ("Max Entries / Session", "10"),
            ("Top Results", "6"),
        ]

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for label_text, default in fields:
            lbl = Label(
                text=label_text,
                color=get_color_from_hex(STAKE_TEXT),
                font_size='12sp',
                size_hint_y=None,
                height=dp(36)
            )
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(lbl)
            grid.add_widget(ti)

        inner.add_widget(grid)

        goal_row = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(40))
        goal_row.add_widget(Label(
            text="Optimize For",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='12sp'
        ))
        self.goal_spinner = Spinner(
            text='Net Units/Risk',
            values=('Net Units', 'Safety', 'Net Units/Risk'),
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex(STAKE_INPUT),
            color=(1, 1, 1, 1)
        )
        goal_row.add_widget(self.goal_spinner)
        inner.add_widget(goal_row)

        info = Label(
            text="Evolves advanced grid-distribution structures using tiles, target samples, progression and elite selection",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(30)
        )
        inner.add_widget(info)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        self.run_btn = StyledButton(text="RUN PATTERN EVOLUTION")
        self.run_btn.bind(on_release=self.run_evolution)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp', size_hint_y=None, height=dp(22))
        inner.add_widget(self.status_lbl)
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.progress_bar)

        self.summary = Label(
            text="Pattern Evolution results will appear here",
            color=get_color_from_hex(STAKE_GREEN),
            font_size='14sp',
            size_hint_y=None,
            height=dp(80)
        )
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Pattern Evolution results will appear here"

    def compute_score(self, avg_profit, bust_rate, win_rate):
        goal = self.goal_spinner.text
        if goal == "Net Units":
            return avg_profit
        elif goal == "Safety":
            return (win_rate * 0.2) - (bust_rate * 3.0)
        else:
            return avg_profit - (bust_rate * 0.25)

    def comb(self, n, r):
        if r < 0 or r > n:
            return 0
        r = min(r, n - r)
        if r == 0:
            return 1
        numer = 1
        denom = 1
        for i in range(1, r + 1):
            numer *= (n - r + i)
            denom *= i
        return numer // denom

    def hypergeom_prob(self, tiles, hits):
        # 40-number board, 10 numbers drawn
        # Player picks `tiles`, probability of exactly `hits`
        if hits < 0 or hits > tiles or hits > 10:
            return 0.0
        total = self.comb(40, 10)
        ways = self.comb(tiles, hits) * self.comb(40 - tiles, 10 - hits)
        return ways / total if total else 0.0

    def keno_win_prob(self, tiles, target_hits):
        prob = 0.0
        for h in range(target_hits, min(tiles, 10) + 1):
            prob += self.hypergeom_prob(tiles, h)
        return prob

    def keno_payout_multiplier(self, tiles, target_hits):
        # Synthetic payout curve for evolution:
        # rarer events pay more, slight house edge built in
        win_prob = max(0.000001, self.keno_win_prob(tiles, target_hits))
        fair_mult = 1.0 / win_prob
        return fair_mult * 0.94

    def random_strategy(self, bankroll):
        tiles = random.randint(1, 10)
        target_hits = random.randint(1, min(tiles, 6))
        base_bet = round(random.uniform(0.01, min(0.25, bankroll * 0.02)), 4)
        loss_pct = round(random.uniform(5, 80), 2)

        return {
            "tiles": tiles,
            "target_hits": target_hits,
            "base_bet": base_bet,
            "loss_pct": loss_pct,
        }

    def mutate_strategy(self, parent, bankroll):
        tiles = parent["tiles"] + random.choice([-1, 0, 1])
        tiles = max(1, min(10, tiles))

        target_hits = parent["target_hits"] + random.choice([-1, 0, 1])
        target_hits = max(1, min(tiles, target_hits))

        new_base = round(parent["base_bet"] * random.uniform(0.85, 1.15), 4)
        new_loss = round(parent["loss_pct"] * random.uniform(0.85, 1.15), 2)

        new_base = max(0.01, min(new_base, min(0.25, bankroll * 0.02)))
        new_loss = max(1.0, min(new_loss, 100.0))

        return {
            "tiles": tiles,
            "target_hits": target_hits,
            "base_bet": new_base,
            "loss_pct": new_loss,
        }

    def simulate_keno_hits(self, tiles):
        # 40-number board, 10 draws, `tiles` picks
        population = list(range(40))
        picked = set(random.sample(population, tiles))
        drawn = set(random.sample(population, 10))
        return len(picked & drawn)

    def run_keno_sessions(self, bankroll, tiles, target_hits, base_bet, inc_on_loss, max_bets, sessions):
        results = []
        busts = 0
        winning_sessions = 0
        longest_loss_streak_seen = 0

        bankroll = max(0.00000001, bankroll)
        base_bet = max(0.00000001, base_bet)
        inc_on_loss = max(-100.0, inc_on_loss)
        max_bets = max(1, max_bets)
        sessions = max(1, sessions)

        payout_multiplier = self.keno_payout_multiplier(tiles, target_hits)

        for _ in range(sessions):
            balance = bankroll
            current_bet = base_bet
            session_profit = 0.0
            loss_streak = 0

            for _round in range(max_bets):
                if current_bet <= 0 or current_bet > balance:
                    busts += 1
                    break

                balance -= current_bet
                hits = self.simulate_keno_hits(tiles)

                if hits >= target_hits:
                    payout = current_bet * payout_multiplier
                    net_profit = payout - current_bet
                    balance += payout
                    session_profit += net_profit
                    loss_streak = 0
                    current_bet = base_bet
                else:
                    session_profit -= current_bet
                    loss_streak += 1
                    longest_loss_streak_seen = max(longest_loss_streak_seen, loss_streak)
                    current_bet = current_bet * (1 + inc_on_loss / 100.0)

            results.append(session_profit)
            if session_profit > 0:
                winning_sessions += 1

        avg_profit = statistics.mean(results) if results else 0.0
        median_profit = statistics.median(results) if results else 0.0
        best_session = max(results) if results else 0.0
        worst_session = min(results) if results else 0.0
        win_rate = (winning_sessions / sessions) * 100 if sessions else 0.0
        bust_rate = (busts / sessions) * 100 if sessions else 0.0

        return {
            "average_profit": avg_profit,
            "median_profit": median_profit,
            "best_session": best_session,
            "worst_session": worst_session,
            "win_rate": win_rate,
            "bust_rate": bust_rate,
            "longest_loss_streak": longest_loss_streak_seen,
            "payout_multiplier": payout_multiplier,
        }

    def evaluate_strategy(self, strat, bankroll, max_bets, sessions_per_strategy):
        result = self.run_keno_sessions(
            bankroll=bankroll,
            tiles=strat["tiles"],
            target_hits=strat["target_hits"],
            base_bet=strat["base_bet"],
            inc_on_loss=strat["loss_pct"],
            max_bets=max_bets,
            sessions=sessions_per_strategy,
        )

        score = self.compute_score(
            avg_profit=result["average_profit"],
            bust_rate=result["bust_rate"],
            win_rate=result["win_rate"]
        )

        return {
            "tiles": strat["tiles"],
            "target_hits": strat["target_hits"],
            "base_bet": strat["base_bet"],
            "loss_pct": strat["loss_pct"],
            "max_bets": max_bets,
            "avg_profit": result["average_profit"],
            "median_profit": result["median_profit"],
            "best_session": result["best_session"],
            "worst_session": result["worst_session"],
            "win_rate": result["win_rate"],
            "bust_rate": result["bust_rate"],
            "longest_ls": result["longest_loss_streak"],
            "payout_multiplier": result["payout_multiplier"],
            "score": score,
        }

    def save_evolved_strategy(self, item, rank):
        strategy = normalize_strategy({
            "name": f"PAT EVO | {item['tiles']}T {item['target_hits']}S E{item['base_bet']} N{item['loss_pct']}",
            "category": "Experimental",
            "game": "keno",
            "source": "evolution_engine",
            "bank": str(self.inputs["Capital"].text),
            "base": str(item["base_bet"]),
            "multi": str(round(item["payout_multiplier"], 2)),
            "win_action": "Reset",
            "loss_action": f"Increase {item['loss_pct']}%",
            "max_bets": str(item["max_bets"]),
            "notes": (
                f"Saved from Pattern Evolution | Rank #{rank} | "
                f"Grid {item['tiles']} | Target Samples {item['target_hits']} | "
                f"Avg {item['avg_profit']:.4f} | "
                f"Threshold {item['bust_rate']:.2f}% | "
                f"Score {item['score']:.4f} | "
                f"Goal {self.goal_spinner.text}"
            )
        })

        GLOBAL_BANK.strategies.append(strategy)
        GLOBAL_BANK.save_strategies()

        Popup(
            title="Saved",
            content=Label(text=f"Saved:\n{strategy['name']}"),
            size_hint=(0.75, 0.25)
        ).open()

    def add_result_card(self, rank, item):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(174),
            padding=dp(8),
            spacing=dp(3)
        )

        def update_rect(instance, value):
            if hasattr(instance, '_bg_rect'):
                instance._bg_rect.pos = instance.pos
                instance._bg_rect.size = instance.size

        with card.canvas.before:
            Color(rgba=get_color_from_hex(STAKE_INPUT))
            card._bg_rect = Rectangle(pos=card.pos, size=card.size)

        card.bind(pos=update_rect, size=update_rect)

        title = Label(
            text=f"#{rank} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}%",
            color=get_color_from_hex(STAKE_GREEN),
            bold=True,
            font_size='12sp',
            size_hint_y=None,
            height=dp(24)
        )

        row1 = Label(
            text=f"Grid: {item['tiles']} | Target Samples: {item['target_hits']} | Return Multiplier: {item['payout_multiplier']:.2f}x",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row2 = Label(
            text=f"Base Entry: {item['base_bet']} | Negative+ {item['loss_pct']}% | Max Entries: {item['max_bets']}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row3 = Label(
            text=f"Positive Rate: {item['win_rate']:.2f}% | Longest NS: {item['longest_ls']}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row4 = Label(
            text=f"Median: {item['median_profit']:.4f} | Best: {item['best_session']:.4f} | Worst: {item['worst_session']:.4f}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row5 = Label(
            text=f"Score: {item['score']:.4f} | Goal: {self.goal_spinner.text}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='10sp',
            size_hint_y=None,
            height=dp(18)
        )

        save_btn = StyledButton(
            text="SAVE TO LIBRARY",
            bg_color="#2c3e50",
            height=dp(34)
        )
        save_btn.color = (1, 1, 1, 1)
        save_btn.bind(on_release=lambda x: self.save_evolved_strategy(item, rank))

        card.add_widget(title)
        card.add_widget(row1)
        card.add_widget(row2)
        card.add_widget(row3)
        card.add_widget(row4)
        card.add_widget(row5)
        card.add_widget(save_btn)

        self.results_grid.add_widget(card)

    def _set_progress(self, value, text):
        self.progress_bar.value = value
        self.status_lbl.text = text

    def _finish_evolution(self, unique_results, generations, top_results):
        self.run_btn.disabled = False
        self.progress_bar.value = self.progress_bar.max
        self.status_lbl.text = "Status: Complete"
        show_n = max(1, min(top_results, len(unique_results)))
        self.summary.text = f"Evolved Pattern Evolution across {generations} generations | Showing top {show_n} | Goal: {self.goal_spinner.text}"
        self.results_grid.clear_widgets()
        for i, item in enumerate(unique_results[:show_n], start=1):
            self.add_result_card(i, item)

    def run_evolution(self, *args):
        self.results_grid.clear_widgets(); bankroll=safe_float(self.inputs['Capital'].text,20); population_size=safe_int(self.inputs['Population Size'].text,40); generations=safe_int(self.inputs['Generations'].text,5); elite_keep=safe_int(self.inputs['Elite Keep'].text,8); children_per_generation=safe_int(self.inputs['Children Per Generation'].text,40); sessions_per_strategy=safe_int(self.inputs['Sessions / Strategy'].text,2000); max_bets=safe_int(self.inputs['Max Entries / Session'].text,12); top_results=safe_int(self.inputs['Top Results'].text,10)
        if bankroll<=0: self.summary.text='Capital must be greater than 0'; return
        self.run_btn.disabled=True; self.progress_bar.max=max(1, generations*max(2,population_size)); self.progress_bar.value=0; self.status_lbl.text='Status: Running evolution...'
        def worker():
            population=[self.random_strategy(bankroll) for _ in range(max(2,population_size))]; best_overall=[]; progress=0
            for gen in range(max(1,generations)):
                evaluated=[]
                for s in population:
                    evaluated.append(self.evaluate_strategy(s, bankroll, max_bets, sessions_per_strategy)); progress += 1
                    if progress % max(1,self.progress_bar.max//100) == 0 or progress == self.progress_bar.max:
                        _ui_call(self._set_progress, progress, f'Status: Generation {gen+1}/{generations}')
                evaluated.sort(key=lambda x:x['score'], reverse=True); elites=evaluated[:max(1,elite_keep)]; best_overall.extend(elites)
                elite_strats=[{'tiles':e['tiles'],'target_hits':e['target_hits'],'base_bet':e['base_bet'],'loss_pct':e['loss_pct']} for e in elites]
                population=[]
                while len(population)<max(2,children_per_generation): population.append(self.mutate_strategy(random.choice(elite_strats), bankroll))
            best_overall.sort(key=lambda x:x['score'], reverse=True)
            seen=set(); unique_results=[]
            for item in best_overall:
                key=(item['tiles'], item['target_hits'], round(item['base_bet'],4), round(item['loss_pct'],2))
                if key not in seen: seen.add(key); unique_results.append(item)
            _ui_call(self._finish_evolution, unique_results, generations, top_results)
        threading.Thread(target=worker, daemon=True).start()
class MinesEvolutionScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        outer.add_widget(build_info_header("GRID-RISK EVOLUTION", MINES_EVO_HELP))

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))

        self.inputs = {}

        fields = [
            ("Capital", "1000"),
            ("Population Size", "16"),
            ("Generations", "3"),
            ("Elite Keep", "4"),
            ("Children Per Generation", "16"),
            ("Sessions / Strategy", "300"),
            ("Max Entries / Session", "10"),
            ("Top Results", "6"),
        ]

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for label_text, default in fields:
            lbl = Label(
                text=label_text,
                color=get_color_from_hex(STAKE_TEXT),
                font_size='12sp',
                size_hint_y=None,
                height=dp(36)
            )
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(lbl)
            grid.add_widget(ti)

        inner.add_widget(grid)

        goal_row = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(40))
        goal_row.add_widget(Label(
            text="Optimize For",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='12sp'
        ))
        self.goal_spinner = Spinner(
            text='Net Units/Risk',
            values=('Net Units', 'Safety', 'Net Units/Risk'),
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=get_color_from_hex(STAKE_INPUT),
            color=(1, 1, 1, 1)
        )
        goal_row.add_widget(self.goal_spinner)
        inner.add_widget(goal_row)

        info = Label(
            text="Evolves grid-risk structures using risk-node count, clear picks and progression",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(30)
        )
        inner.add_widget(info)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        self.run_btn = StyledButton(text="RUN GRID-RISK EVOLUTION")
        self.run_btn.bind(on_release=self.run_evolution)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp', size_hint_y=None, height=dp(22))
        inner.add_widget(self.status_lbl)
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.progress_bar)

        self.summary = Label(
            text="Grid-Risk Evolution results will appear here",
            color=get_color_from_hex(STAKE_GREEN),
            font_size='14sp',
            size_hint_y=None,
            height=dp(80)
        )
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Grid-Risk Evolution results will appear here"

    def compute_score(self, avg_profit, bust_rate, win_rate):
        goal = self.goal_spinner.text
        if goal == "Net Units":
            return avg_profit
        elif goal == "Safety":
            return (win_rate * 0.2) - (bust_rate * 3.0)
        else:
            return avg_profit - (bust_rate * 0.25)

    def comb(self, n, r):
        if r < 0 or r > n:
            return 0
        r = min(r, n - r)
        if r == 0:
            return 1
        numer = 1
        denom = 1
        for i in range(1, r + 1):
            numer *= (n - r + i)
            denom *= i
        return numer // denom

    def mines_win_prob(self, mines_count, safe_picks):
        # Probability of surviving `safe_picks` picks on 25-tile board
        if safe_picks < 0 or mines_count < 1 or mines_count >= 25:
            return 0.0
        safe_tiles = 25 - mines_count
        if safe_picks > safe_tiles:
            return 0.0

        prob = 1.0
        for i in range(safe_picks):
            prob *= (safe_tiles - i) / (25 - i)
        return prob

    def mines_payout_multiplier(self, mines_count, safe_picks):
        win_prob = max(0.000001, self.mines_win_prob(mines_count, safe_picks))
        fair_mult = 1.0 / win_prob
        return fair_mult * 0.94

    def random_strategy(self, bankroll):
        mines_count = random.randint(1, 10)
        max_safe_possible = 24 - mines_count
        safe_picks = random.randint(1, max(1, min(10, max_safe_possible)))
        base_bet = round(random.uniform(0.01, min(0.25, bankroll * 0.02)), 4)
        loss_pct = round(random.uniform(5, 80), 2)

        return {
            "mines_count": mines_count,
            "safe_picks": safe_picks,
            "base_bet": base_bet,
            "loss_pct": loss_pct,
        }

    def mutate_strategy(self, parent, bankroll):
        mines_count = parent["mines_count"] + random.choice([-1, 0, 1])
        mines_count = max(1, min(10, mines_count))

        max_safe_possible = 24 - mines_count
        safe_picks = parent["safe_picks"] + random.choice([-1, 0, 1])
        safe_picks = max(1, min(max_safe_possible, safe_picks))

        new_base = round(parent["base_bet"] * random.uniform(0.85, 1.15), 4)
        new_loss = round(parent["loss_pct"] * random.uniform(0.85, 1.15), 2)

        new_base = max(0.01, min(new_base, min(0.25, bankroll * 0.02)))
        new_loss = max(1.0, min(new_loss, 100.0))

        return {
            "mines_count": mines_count,
            "safe_picks": safe_picks,
            "base_bet": new_base,
            "loss_pct": new_loss,
        }

    def simulate_single_mines_round(self, mines_count, safe_picks):
        tiles = list(range(25))
        mine_set = set(random.sample(tiles, mines_count))
        remaining = tiles[:]

        for _ in range(safe_picks):
            pick = random.choice(remaining)
            remaining.remove(pick)
            if pick in mine_set:
                return False
        return True

    def run_mines_sessions(self, bankroll, mines_count, safe_picks, base_bet, inc_on_loss, max_bets, sessions):
        results = []
        busts = 0
        winning_sessions = 0
        longest_loss_streak_seen = 0

        bankroll = max(0.00000001, bankroll)
        base_bet = max(0.00000001, base_bet)
        inc_on_loss = max(-100.0, inc_on_loss)
        max_bets = max(1, max_bets)
        sessions = max(1, sessions)

        payout_multiplier = self.mines_payout_multiplier(mines_count, safe_picks)

        for _ in range(sessions):
            balance = bankroll
            current_bet = base_bet
            session_profit = 0.0
            loss_streak = 0

            for _round in range(max_bets):
                if current_bet <= 0 or current_bet > balance:
                    busts += 1
                    break

                balance -= current_bet
                is_win = self.simulate_single_mines_round(mines_count, safe_picks)

                if is_win:
                    payout = current_bet * payout_multiplier
                    net_profit = payout - current_bet
                    balance += payout
                    session_profit += net_profit
                    loss_streak = 0
                    current_bet = base_bet
                else:
                    session_profit -= current_bet
                    loss_streak += 1
                    longest_loss_streak_seen = max(longest_loss_streak_seen, loss_streak)
                    current_bet = current_bet * (1 + inc_on_loss / 100.0)

            results.append(session_profit)
            if session_profit > 0:
                winning_sessions += 1

        avg_profit = statistics.mean(results) if results else 0.0
        median_profit = statistics.median(results) if results else 0.0
        best_session = max(results) if results else 0.0
        worst_session = min(results) if results else 0.0
        win_rate = (winning_sessions / sessions) * 100 if sessions else 0.0
        bust_rate = (busts / sessions) * 100 if sessions else 0.0

        return {
            "average_profit": avg_profit,
            "median_profit": median_profit,
            "best_session": best_session,
            "worst_session": worst_session,
            "win_rate": win_rate,
            "bust_rate": bust_rate,
            "longest_loss_streak": longest_loss_streak_seen,
            "payout_multiplier": payout_multiplier,
        }

    def evaluate_strategy(self, strat, bankroll, max_bets, sessions_per_strategy):
        result = self.run_mines_sessions(
            bankroll=bankroll,
            mines_count=strat["mines_count"],
            safe_picks=strat["safe_picks"],
            base_bet=strat["base_bet"],
            inc_on_loss=strat["loss_pct"],
            max_bets=max_bets,
            sessions=sessions_per_strategy,
        )

        score = self.compute_score(
            avg_profit=result["average_profit"],
            bust_rate=result["bust_rate"],
            win_rate=result["win_rate"]
        )

        return {
            "mines_count": strat["mines_count"],
            "safe_picks": strat["safe_picks"],
            "base_bet": strat["base_bet"],
            "loss_pct": strat["loss_pct"],
            "max_bets": max_bets,
            "avg_profit": result["average_profit"],
            "median_profit": result["median_profit"],
            "best_session": result["best_session"],
            "worst_session": result["worst_session"],
            "win_rate": result["win_rate"],
            "bust_rate": result["bust_rate"],
            "longest_ls": result["longest_loss_streak"],
            "payout_multiplier": result["payout_multiplier"],
            "score": score,
        }

    def save_evolved_strategy(self, item, rank):
        strategy = normalize_strategy({
            "name": f"GRID EVO | {item['mines_count']}R {item['safe_picks']}C E{item['base_bet']} N{item['loss_pct']}",
            "category": "Experimental",
            "game": "mines",
            "source": "evolution_engine",
            "bank": str(self.inputs["Capital"].text),
            "base": str(item["base_bet"]),
            "multi": str(round(item["payout_multiplier"], 2)),
            "win_action": "Reset",
            "loss_action": f"Increase {item['loss_pct']}%",
            "max_bets": str(item["max_bets"]),
            "notes": (
                f"Saved from Grid-Risk Evolution | Rank #{rank} | "
                f"Risk Nodes {item['mines_count']} | Clear Nodes {item['safe_picks']} | "
                f"Avg {item['avg_profit']:.4f} | "
                f"Threshold {item['bust_rate']:.2f}% | "
                f"Score {item['score']:.4f} | "
                f"Goal {self.goal_spinner.text}"
            )
        })

        GLOBAL_BANK.strategies.append(strategy)
        GLOBAL_BANK.save_strategies()

        Popup(
            title="Saved",
            content=Label(text=f"Saved:\n{strategy['name']}"),
            size_hint=(0.75, 0.25)
        ).open()

    def add_result_card(self, rank, item):
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(174),
            padding=dp(8),
            spacing=dp(3)
        )

        def update_rect(instance, value):
            if hasattr(instance, '_bg_rect'):
                instance._bg_rect.pos = instance.pos
                instance._bg_rect.size = instance.size

        with card.canvas.before:
            Color(rgba=get_color_from_hex(STAKE_INPUT))
            card._bg_rect = Rectangle(pos=card.pos, size=card.size)

        card.bind(pos=update_rect, size=update_rect)

        title = Label(
            text=f"#{rank} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}%",
            color=get_color_from_hex(STAKE_GREEN),
            bold=True,
            font_size='12sp',
            size_hint_y=None,
            height=dp(24)
        )

        row1 = Label(
            text=f"Risk Nodes: {item['mines_count']} | Clear Nodes: {item['safe_picks']} | Return Multiplier: {item['payout_multiplier']:.2f}x",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row2 = Label(
            text=f"Base Entry: {item['base_bet']} | Negative+ {item['loss_pct']}% | Max Entries: {item['max_bets']}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row3 = Label(
            text=f"Positive Rate: {item['win_rate']:.2f}% | Longest NS: {item['longest_ls']}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row4 = Label(
            text=f"Median: {item['median_profit']:.4f} | Best: {item['best_session']:.4f} | Worst: {item['worst_session']:.4f}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(22)
        )

        row5 = Label(
            text=f"Score: {item['score']:.4f} | Goal: {self.goal_spinner.text}",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='10sp',
            size_hint_y=None,
            height=dp(18)
        )

        save_btn = StyledButton(
            text="SAVE TO LIBRARY",
            bg_color="#2c3e50",
            height=dp(34)
        )
        save_btn.color = (1, 1, 1, 1)
        save_btn.bind(on_release=lambda x: self.save_evolved_strategy(item, rank))

        card.add_widget(title)
        card.add_widget(row1)
        card.add_widget(row2)
        card.add_widget(row3)
        card.add_widget(row4)
        card.add_widget(row5)
        card.add_widget(save_btn)

        self.results_grid.add_widget(card)

    def _set_progress(self, value, text):
        self.progress_bar.value = value
        self.status_lbl.text = text

    def _finish_evolution(self, unique_results, generations, top_results):
        self.run_btn.disabled = False
        self.progress_bar.value = self.progress_bar.max
        self.status_lbl.text = "Status: Complete"
        show_n = max(1, min(top_results, len(unique_results)))
        self.summary.text = f"Evolved Grid-Risk Evolution across {generations} generations | Showing top {show_n} | Goal: {self.goal_spinner.text}"
        self.results_grid.clear_widgets()
        for i, item in enumerate(unique_results[:show_n], start=1):
            self.add_result_card(i, item)

    def run_evolution(self, *args):
        self.results_grid.clear_widgets(); bankroll=safe_float(self.inputs['Capital'].text,20); population_size=safe_int(self.inputs['Population Size'].text,40); generations=safe_int(self.inputs['Generations'].text,5); elite_keep=safe_int(self.inputs['Elite Keep'].text,8); children_per_generation=safe_int(self.inputs['Children Per Generation'].text,40); sessions_per_strategy=safe_int(self.inputs['Sessions / Strategy'].text,2000); max_bets=safe_int(self.inputs['Max Entries / Session'].text,12); top_results=safe_int(self.inputs['Top Results'].text,10)
        if bankroll<=0: self.summary.text='Capital must be greater than 0'; return
        self.run_btn.disabled=True; self.progress_bar.max=max(1, generations*max(2,population_size)); self.progress_bar.value=0; self.status_lbl.text='Status: Running evolution...'
        def worker():
            population=[self.random_strategy(bankroll) for _ in range(max(2,population_size))]; best_overall=[]; progress=0
            for gen in range(max(1,generations)):
                evaluated=[]
                for s in population:
                    evaluated.append(self.evaluate_strategy(s, bankroll, max_bets, sessions_per_strategy)); progress += 1
                    if progress % max(1,self.progress_bar.max//100) == 0 or progress == self.progress_bar.max:
                        _ui_call(self._set_progress, progress, f'Status: Generation {gen+1}/{generations}')
                evaluated.sort(key=lambda x:x['score'], reverse=True); elites=evaluated[:max(1,elite_keep)]; best_overall.extend(elites)
                elite_strats=[{'mines_count':e['mines_count'],'safe_picks':e['safe_picks'],'base_bet':e['base_bet'],'loss_pct':e['loss_pct']} for e in elites]
                population=[]
                while len(population)<max(2,children_per_generation): population.append(self.mutate_strategy(random.choice(elite_strats), bankroll))
            best_overall.sort(key=lambda x:x['score'], reverse=True)
            seen=set(); unique_results=[]
            for item in best_overall:
                key=(item['mines_count'], item['safe_picks'], round(item['base_bet'],4), round(item['loss_pct'],2))
                if key not in seen: seen.add(key); unique_results.append(item)
            _ui_call(self._finish_evolution, unique_results, generations, top_results)
        threading.Thread(target=worker, daemon=True).start()
class SportsLabScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        outer = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        outer.add_widget(build_info_header("ATHLETIC DATA LAB"))

        info = Label(
            text="Neutral market-model workspace using probability ratios, position sizing and compound-return analysis.",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(34)
        )
        outer.add_widget(info)

        preview = GridLayout(cols=3, spacing=dp(6), size_hint_y=None, height=dp(72))
        for title, value, accent in [
            ("Ratios", "2.10  |  1.95", PRESENTATION_ACCENT),
            ("Position", "Capital split", PRESENTATION_ACCENT_ALT),
            ("Return", "Compound view", STAKE_GREEN),
        ]:
            card = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))
            with card.canvas.before:
                Color(rgba=get_color_from_hex(STAKE_INPUT))
                card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])
            card.bind(pos=lambda inst, val: setattr(inst._bg, 'pos', val), size=lambda inst, val: setattr(inst._bg, 'size', val))
            card.add_widget(Label(text=title, color=get_color_from_hex(STAKE_TEXT), font_size='11sp'))
            card.add_widget(Label(text=value, color=get_color_from_hex(accent), font_size='12sp', bold=True))
            preview.add_widget(card)
        outer.add_widget(preview)

        tools_layout = GridLayout(cols=1, spacing=dp(8), size_hint_y=None)
        tools_layout.bind(minimum_height=tools_layout.setter('height'))

        tools = [
            ("Kelly Criterion Tool", "Probability-ratio sizing model", 'sports_kelly'),
            ("Compounded Risk Analyst", "Stage-chain probability and compound return", 'sports_parlay'),
            ("Edge Discovery Tool", "Fair-ratio and EV comparison", 'sports_value'),
            ("Market Convergence Calc", "Two-outcome allocation model", 'sports_arb'),
        ]

        for name, desc, sid in tools:
            row = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4), size_hint_y=None, height=dp(72))
            with row.canvas.before:
                Color(rgba=get_color_from_hex(STAKE_INPUT))
                row._bg = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(10)])
            row.bind(pos=lambda inst, val: setattr(inst._bg, 'pos', val), size=lambda inst, val: setattr(inst._bg, 'size', val))
            btn = StyledButton(text=name, bg_color=STAKE_INPUT, height=dp(36))
            btn.color = (1, 1, 1, 1)
            btn.bind(on_release=lambda x, s=sid: App.get_running_app().open_feature(s))
            desc_lbl = Label(text=desc, color=get_color_from_hex(STAKE_TEXT), font_size='10sp', size_hint_y=None, height=dp(16), halign='left', valign='middle')
            desc_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
            row.add_widget(btn)
            row.add_widget(desc_lbl)
            tools_layout.add_widget(row)

        scroll = ScrollView()
        scroll.add_widget(tools_layout)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)



class SportsKellyScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(6))
        self.inputs = {}

        layout.add_widget(build_info_header("KELLY CRITERION TOOL"))
        layout.add_widget(Label(
            text="Use capital, probability ratio and estimated event probability to size a clean position.",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(28)
        ))

        fields = [
            ("Capital", "1000"),
            ("Probability Ratio", "2.30"),
            ("Estimated Event %", "48"),
        ]

        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for label_text, default in fields:
            grid.add_widget(Label(text=label_text, color=get_color_from_hex(STAKE_TEXT), font_size='12sp', size_hint_y=None, height=dp(36)))
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(ti)
        layout.add_widget(grid)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        calc_btn = StyledButton(text="CALCULATE POSITION SIZE")
        calc_btn.bind(on_release=self.calculate)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(calc_btn)
        btn_row.add_widget(clear_btn)
        layout.add_widget(btn_row)

        self.result_box = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=[dp(10), dp(8)])
        self.result_box.bind(minimum_height=self.result_box.setter('height'))
        apply_result_card_style(self.result_box)

        scroll = ScrollView()
        scroll.add_widget(self.result_box)
        layout.add_widget(scroll)

        layout.add_widget(SimpleNav())
        self.add_widget(layout)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.result_box.clear_widgets()
        self._kelly_last = None

    def calculate(self, *args):
        self.result_box.clear_widgets()
        try:
            capital = float(self.inputs["Capital"].text)
            ratio = float(self.inputs["Probability Ratio"].text)
            est_event_pct = float(self.inputs["Estimated Event %"].text)
            if capital <= 0 or ratio <= 1.0 or est_event_pct <= 0 or est_event_pct >= 100:
                raise ValueError("Invalid input values")

            p = est_event_pct / 100.0
            q = 1 - p
            b = ratio - 1.0
            implied_prob = 100.0 / ratio
            edge_pct = est_event_pct - implied_prob
            position_fraction = max(0.0, ((b * p) - q) / b)
            full_position = capital * position_fraction
            half_position = full_position / 2.0
            quarter_position = full_position / 4.0
            expected_value_per_unit = (p * b) - q
            expected_net_units = full_position * expected_value_per_unit

            lines = [
                f"Implied Probability: {implied_prob:.2f}%",
                f"Your Edge: {edge_pct:.2f}%",
                f"Full Position Fraction: {position_fraction * 100:.2f}% of capital",
                f"Full Position Size: {full_position:.4f}",
                f"Half Position Size: {half_position:.4f}",
                f"Quarter Position Size: {quarter_position:.4f}",
                f"Expected Value / Unit: {expected_value_per_unit:.4f}",
                f"Expected Net Units at Full Position: {expected_net_units:.4f}",
            ]
            for line in lines:
                color = get_color_from_hex(STAKE_GREEN) if ("Edge" in line or "Position" in line) else get_color_from_hex(STAKE_TEXT)
                self.result_box.add_widget(Label(text=line, color=color, font_size='12sp', size_hint_y=None, height=dp(28)))

            self._kelly_last = {
                'capital': capital, 'ratio': ratio, 'est_event_pct': est_event_pct,
                'implied_prob': implied_prob, 'edge_pct': edge_pct,
                'position_fraction': position_fraction, 'full_position': full_position,
                'half_position': half_position, 'quarter_position': quarter_position,
                'expected_value_per_unit': expected_value_per_unit,
                'expected_net_units': expected_net_units,
            }
            share_btn = StyledButton(text="SHARE RESULT", bg_color=UTILITY_COLOR)
            share_btn.color = (1, 1, 1, 1)
            share_btn.size_hint_y = None
            share_btn.height = dp(42)
            share_btn.bind(on_release=self._share_kelly_result)
            self.result_box.add_widget(share_btn)
        except Exception as e:
            self.result_box.add_widget(Label(text=f"Error: {e}", color=get_color_from_hex(STAKE_RED), font_size='12sp', size_hint_y=None, height=dp(28)))

    def _share_kelly_result(self, *args):
        r = getattr(self, '_kelly_last', None)
        if not r:
            return
        share_result("Kelly Criterion Tool", [
            f"Capital:                    {r['capital']:.2f}",
            f"Probability Ratio:          {r['ratio']:.2f}",
            f"Estimated Event:            {r['est_event_pct']:.2f}%",
            f"Implied Probability:        {r['implied_prob']:.2f}%",
            f"Your Edge:                  {r['edge_pct']:.2f}%",
            f"Full Position Fraction:     {r['position_fraction']*100:.2f}% of capital",
            f"Full Position Size:         {r['full_position']:.4f}",
            f"Half Position Size:         {r['half_position']:.4f}",
            f"Quarter Position Size:      {r['quarter_position']:.4f}",
            f"Expected Value / Unit:      {r['expected_value_per_unit']:.4f}",
            f"Expected Net Units:         {r['expected_net_units']:.4f}",
        ])



class SportsParlayScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(6))
        self.inputs = {}

        layout.add_widget(build_info_header("COMPOUNDED RISK ANALYST"))
        info = Label(
            text="Enter probability ratios and estimated event percentages for each stage.",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(28)
        )
        layout.add_widget(info)

        fields = [
            ("Unit Size", "100"),
            ("Stage 1 Ratio", "1.80"),
            ("Stage 1 Event %", "61"),
            ("Stage 2 Ratio", "1.95"),
            ("Stage 2 Event %", "57"),
            ("Stage 3 Ratio", "2.20"),
            ("Stage 3 Event %", "49"),
        ]
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for label_text, default in fields:
            grid.add_widget(Label(text=label_text, color=get_color_from_hex(STAKE_TEXT), font_size='12sp', size_hint_y=None, height=dp(36)))
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(ti)
        layout.add_widget(grid)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        calc_btn = StyledButton(text="ANALYZE COMPOUND STRUCTURE")
        calc_btn.bind(on_release=self.calculate)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(calc_btn)
        btn_row.add_widget(clear_btn)
        layout.add_widget(btn_row)

        self.result_box = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=[dp(10), dp(8)])
        self.result_box.bind(minimum_height=self.result_box.setter('height'))
        apply_result_card_style(self.result_box)
        scroll = ScrollView()
        scroll.add_widget(self.result_box)
        layout.add_widget(scroll)

        layout.add_widget(SimpleNav())
        self.add_widget(layout)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.result_box.clear_widgets()
        self._compound_last = None

    def calculate(self, *args):
        self.result_box.clear_widgets()
        try:
            unit_size = float(self.inputs["Unit Size"].text)
            ratios = [float(self.inputs[f"Stage {i} Ratio"].text) for i in (1,2,3)]
            event_pcts = [float(self.inputs[f"Stage {i} Event %"].text) for i in (1,2,3)]
            if unit_size <= 0:
                raise ValueError("Unit Size must be greater than 0")
            for ratio in ratios:
                if ratio <= 1.0:
                    raise ValueError("All probability ratios must be greater than 1.0")
            for pct in event_pcts:
                if pct <= 0 or pct >= 100:
                    raise ValueError("All event percentages must be between 0 and 100")

            probs = [pct / 100.0 for pct in event_pcts]
            combined_ratio = 1.0
            for ratio in ratios:
                combined_ratio *= ratio
            true_chain_prob = 1.0
            for prob in probs:
                true_chain_prob *= prob
            implied_chain_prob = 1.0 / combined_ratio
            edge_pct = (true_chain_prob - implied_chain_prob) * 100.0
            compound_return = unit_size * combined_ratio
            net_units_complete = compound_return - unit_size
            expected_net_units = (true_chain_prob * net_units_complete) - ((1 - true_chain_prob) * unit_size)
            expected_return_rate = (expected_net_units / unit_size) * 100.0
            failure_prob = (1 - true_chain_prob) * 100.0

            lines = [
                f"Combined Ratio: {combined_ratio:.4f}",
                f"True Stage-Chain Probability: {true_chain_prob * 100:.2f}%",
                f"Implied Stage-Chain Probability: {implied_chain_prob * 100:.2f}%",
                f"Edge: {edge_pct:.2f}%",
                f"Compound Return: {compound_return:.4f}",
                f"Net Units if Complete: {net_units_complete:.4f}",
                f"Expected Net Units: {expected_net_units:.4f}",
                f"Expected Return Rate: {expected_return_rate:.2f}%",
                f"Stage Chain Failure Probability: {failure_prob:.2f}%",
            ]
            for line in lines:
                color = get_color_from_hex(STAKE_GREEN) if ("Edge" in line or "Expected" in line) else get_color_from_hex(STAKE_TEXT)
                self.result_box.add_widget(Label(text=line, color=color, font_size='12sp', size_hint_y=None, height=dp(28)))

            self._compound_last = {
                'unit_size': unit_size, 'combined_ratio': combined_ratio,
                'true_chain_prob': true_chain_prob, 'implied_chain_prob': implied_chain_prob,
                'edge_pct': edge_pct, 'compound_return': compound_return,
                'net_units_complete': net_units_complete,
                'expected_net_units': expected_net_units,
                'expected_return_rate': expected_return_rate,
                'failure_prob': failure_prob,
            }
            share_btn = StyledButton(text="SHARE RESULT", bg_color=UTILITY_COLOR)
            share_btn.color = (1, 1, 1, 1)
            share_btn.size_hint_y = None
            share_btn.height = dp(42)
            share_btn.bind(on_release=self._share_compound_result)
            self.result_box.add_widget(share_btn)
        except Exception as e:
            self.result_box.add_widget(Label(text=f"Error: {e}", color=get_color_from_hex(STAKE_RED), font_size='12sp', size_hint_y=None, height=dp(28)))

    def _share_compound_result(self, *args):
        r = getattr(self, '_compound_last', None)
        if not r:
            return
        share_result("Compounded Risk Analyst", [
            f"Unit Size:                  {r['unit_size']:.2f}",
            f"Combined Ratio:             {r['combined_ratio']:.4f}",
            f"True Chain Probability:     {r['true_chain_prob']*100:.2f}%",
            f"Implied Chain Probability:  {r['implied_chain_prob']*100:.2f}%",
            f"Edge:                       {r['edge_pct']:.2f}%",
            f"Compound Return:            {r['compound_return']:.4f}",
            f"Net Units if Complete:      {r['net_units_complete']:.4f}",
            f"Expected Net Units:         {r['expected_net_units']:.4f}",
            f"Expected Return Rate:       {r['expected_return_rate']:.2f}%",
            f"Stage Chain Failure Prob.:  {r['failure_prob']:.2f}%",
        ])



class SportsValueBetScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(6))
        self.inputs = {}

        layout.add_widget(build_info_header("EDGE DISCOVERY TOOL"))
        info = Label(
            text="Compare a probability ratio against your estimated event probability to find clean edge.",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(28)
        )
        layout.add_widget(info)

        fields = [
            ("Unit Size", "100"),
            ("Probability Ratio", "2.20"),
            ("Estimated Event %", "50"),
        ]
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for label_text, default in fields:
            grid.add_widget(Label(text=label_text, color=get_color_from_hex(STAKE_TEXT), font_size='12sp', size_hint_y=None, height=dp(36)))
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(ti)
        layout.add_widget(grid)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        calc_btn = StyledButton(text="CALCULATE EDGE")
        calc_btn.bind(on_release=self.calculate)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(calc_btn)
        btn_row.add_widget(clear_btn)
        layout.add_widget(btn_row)

        self.result_box = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=[dp(10), dp(8)])
        self.result_box.bind(minimum_height=self.result_box.setter('height'))
        apply_result_card_style(self.result_box)
        scroll = ScrollView()
        scroll.add_widget(self.result_box)
        layout.add_widget(scroll)

        layout.add_widget(SimpleNav())
        self.add_widget(layout)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.result_box.clear_widgets()
        self._value_last = None

    def calculate(self, *args):
        self.result_box.clear_widgets()
        try:
            unit_size = float(self.inputs["Unit Size"].text)
            ratio = float(self.inputs["Probability Ratio"].text)
            est_event_pct = float(self.inputs["Estimated Event %"].text)
            if unit_size <= 0:
                raise ValueError("Unit Size must be greater than 0")
            if ratio <= 1.0:
                raise ValueError("Probability ratio must be greater than 1.0")
            if est_event_pct <= 0 or est_event_pct >= 100:
                raise ValueError("Estimated Event % must be between 0 and 100")

            p = est_event_pct / 100.0
            implied_prob = 1.0 / ratio
            implied_pct = implied_prob * 100.0
            edge_pct = est_event_pct - implied_pct
            event_return = unit_size * ratio
            net_units_event = event_return - unit_size
            expected_value = (p * net_units_event) - ((1 - p) * unit_size)
            expected_return_rate = (expected_value / unit_size) * 100.0
            fair_ratio = 1.0 / p
            verdict = "POSITIVE EV" if expected_value > 0 else "NEGATIVE EV"
            verdict_color = get_color_from_hex(STAKE_GREEN if expected_value > 0 else STAKE_RED)

            lines = [
                (f"Implied Probability: {implied_pct:.2f}%", get_color_from_hex(STAKE_TEXT)),
                (f"Your Estimated Probability: {est_event_pct:.2f}%", get_color_from_hex(STAKE_TEXT)),
                (f"Fair Ratio: {fair_ratio:.4f}", get_color_from_hex(STAKE_TEXT)),
                (f"Edge: {edge_pct:.2f}%", get_color_from_hex(STAKE_GREEN if edge_pct > 0 else STAKE_RED)),
                (f"Event Return: {event_return:.4f}", get_color_from_hex(STAKE_TEXT)),
                (f"Net Units if Event Occurs: {net_units_event:.4f}", get_color_from_hex(STAKE_TEXT)),
                (f"Expected Value: {expected_value:.4f}", get_color_from_hex(STAKE_GREEN if expected_value > 0 else STAKE_RED)),
                (f"Expected Return Rate: {expected_return_rate:.2f}%", get_color_from_hex(STAKE_GREEN if expected_return_rate > 0 else STAKE_RED)),
                (f"Verdict: {verdict}", verdict_color),
            ]
            for line, color in lines:
                self.result_box.add_widget(Label(text=line, color=color, font_size='12sp', size_hint_y=None, height=dp(28)))

            self._value_last = {
                'unit_size': unit_size, 'ratio': ratio, 'est_event_pct': est_event_pct,
                'implied_pct': implied_pct, 'fair_ratio': fair_ratio,
                'edge_pct': edge_pct, 'event_return': event_return,
                'net_units_event': net_units_event, 'expected_value': expected_value,
                'expected_return_rate': expected_return_rate, 'verdict': verdict,
            }
            share_btn = StyledButton(text="SHARE RESULT", bg_color=UTILITY_COLOR)
            share_btn.color = (1, 1, 1, 1)
            share_btn.size_hint_y = None
            share_btn.height = dp(42)
            share_btn.bind(on_release=self._share_value_result)
            self.result_box.add_widget(share_btn)
        except Exception as e:
            self.result_box.add_widget(Label(text=f"Error: {e}", color=get_color_from_hex(STAKE_RED), font_size='12sp', size_hint_y=None, height=dp(28)))

    def _share_value_result(self, *args):
        r = getattr(self, '_value_last', None)
        if not r:
            return
        share_result("Edge Discovery Tool", [
            f"Unit Size:                 {r['unit_size']:.2f}",
            f"Probability Ratio:         {r['ratio']:.2f}",
            f"Estimated Event:           {r['est_event_pct']:.2f}%",
            f"Implied Probability:       {r['implied_pct']:.2f}%",
            f"Fair Ratio:                {r['fair_ratio']:.4f}",
            f"Edge:                      {r['edge_pct']:.2f}%",
            f"Event Return:              {r['event_return']:.4f}",
            f"Net Units if Event:        {r['net_units_event']:.4f}",
            f"Expected Value:            {r['expected_value']:.4f}",
            f"Expected Return Rate:      {r['expected_return_rate']:.2f}%",
            f"Verdict:                   {r['verdict']}",
        ])



class SportsArbitrageScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(6))
        self.inputs = {}

        layout.add_widget(build_info_header("MARKET CONVERGENCE CALC"))
        info = Label(
            text="Use two opposing probability ratios to check for locked positive return across both outcomes.",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(28)
        )
        layout.add_widget(info)

        fields = [
            ("Total Units", "1000"),
            ("Outcome A Ratio", "2.10"),
            ("Outcome B Ratio", "2.05"),
        ]
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for label_text, default in fields:
            grid.add_widget(Label(text=label_text, color=get_color_from_hex(STAKE_TEXT), font_size='12sp', size_hint_y=None, height=dp(36)))
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(ti)
        layout.add_widget(grid)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        calc_btn = StyledButton(text="CHECK CONVERGENCE")
        calc_btn.bind(on_release=self.calculate)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(calc_btn)
        btn_row.add_widget(clear_btn)
        layout.add_widget(btn_row)

        self.result_box = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=[dp(10), dp(8)])
        self.result_box.bind(minimum_height=self.result_box.setter('height'))
        apply_result_card_style(self.result_box)
        scroll = ScrollView()
        scroll.add_widget(self.result_box)
        layout.add_widget(scroll)

        layout.add_widget(SimpleNav())
        self.add_widget(layout)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.result_box.clear_widgets()
        self._arb_last = None

    def calculate(self, *args):
        self.result_box.clear_widgets()
        try:
            total_units = float(self.inputs["Total Units"].text)
            ratio_a = float(self.inputs["Outcome A Ratio"].text)
            ratio_b = float(self.inputs["Outcome B Ratio"].text)
            if total_units <= 0:
                raise ValueError("Total Units must be greater than 0")
            if ratio_a <= 1.0 or ratio_b <= 1.0:
                raise ValueError("All probability ratios must be greater than 1.0")

            inv_sum = (1.0 / ratio_a) + (1.0 / ratio_b)
            convergence_found = inv_sum < 1.0
            alloc_a = total_units * ((1.0 / ratio_a) / inv_sum)
            alloc_b = total_units * ((1.0 / ratio_b) / inv_sum)
            return_a = alloc_a * ratio_a
            return_b = alloc_b * ratio_b
            locked_return = min(return_a, return_b)
            locked_net_units = locked_return - total_units
            locked_roi = (locked_net_units / total_units) * 100.0
            verdict = "CONVERGENCE FOUND" if convergence_found else "NO CONVERGENCE"
            verdict_color = get_color_from_hex(STAKE_GREEN if convergence_found else STAKE_RED)

            lines = [
                (f"Inverse Sum: {inv_sum:.6f}", get_color_from_hex(STAKE_TEXT)),
                (f"Outcome A Allocation: {alloc_a:.4f}", get_color_from_hex(STAKE_TEXT)),
                (f"Outcome B Allocation: {alloc_b:.4f}", get_color_from_hex(STAKE_TEXT)),
                (f"Outcome A Return: {return_a:.4f}", get_color_from_hex(STAKE_TEXT)),
                (f"Outcome B Return: {return_b:.4f}", get_color_from_hex(STAKE_TEXT)),
                (f"Locked Return: {locked_return:.4f}", get_color_from_hex(STAKE_TEXT)),
                (f"Locked Net Units: {locked_net_units:.4f}", get_color_from_hex(STAKE_GREEN if locked_net_units > 0 else STAKE_RED)),
                (f"Locked Return Rate: {locked_roi:.2f}%", get_color_from_hex(STAKE_GREEN if locked_roi > 0 else STAKE_RED)),
                (f"Verdict: {verdict}", verdict_color),
            ]
            for line, color in lines:
                self.result_box.add_widget(Label(text=line, color=color, font_size='12sp', size_hint_y=None, height=dp(28)))

            self._arb_last = {
                'total_units': total_units, 'ratio_a': ratio_a, 'ratio_b': ratio_b,
                'inv_sum': inv_sum, 'alloc_a': alloc_a, 'alloc_b': alloc_b,
                'return_a': return_a, 'return_b': return_b,
                'locked_return': locked_return, 'locked_net_units': locked_net_units,
                'locked_roi': locked_roi, 'verdict': verdict,
            }
            share_btn = StyledButton(text="SHARE RESULT", bg_color=UTILITY_COLOR)
            share_btn.color = (1, 1, 1, 1)
            share_btn.size_hint_y = None
            share_btn.height = dp(42)
            share_btn.bind(on_release=self._share_arb_result)
            self.result_box.add_widget(share_btn)
        except Exception as e:
            self.result_box.add_widget(Label(text=f"Error: {e}", color=get_color_from_hex(STAKE_RED), font_size='12sp', size_hint_y=None, height=dp(28)))

    def _share_arb_result(self, *args):
        r = getattr(self, '_arb_last', None)
        if not r:
            return
        share_result("Market Convergence Calc", [
            f"Total Units:              {r['total_units']:.2f}",
            f"Outcome A Ratio:          {r['ratio_a']:.2f}",
            f"Outcome B Ratio:          {r['ratio_b']:.2f}",
            f"Inverse Sum:              {r['inv_sum']:.6f}",
            f"Outcome A Allocation:     {r['alloc_a']:.4f}",
            f"Outcome B Allocation:     {r['alloc_b']:.4f}",
            f"Outcome A Return:         {r['return_a']:.4f}",
            f"Outcome B Return:         {r['return_b']:.4f}",
            f"Locked Return:            {r['locked_return']:.4f}",
            f"Locked Net Units:         {r['locked_net_units']:.4f}",
            f"Locked Return Rate:       {r['locked_roi']:.2f}%",
            f"Verdict:                  {r['verdict']}",
        ])



class MinesScreen(Screen):      
    def __init__(self, **kw):
        super().__init__(**kw)

        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        layout.add_widget(build_info_header("GRID-RISK ANALYST"))

        info = Label(
            text="Use risk nodes and clear nodes to estimate clear-rate and return multiplier.",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(28)
        )
        layout.add_widget(info)

        preview = GridLayout(cols=5, spacing=dp(4), size_hint_y=None, height=dp(116))
        for i in range(25):
            cell = Label(
                text='•' if i % 6 else '×',
                color=get_color_from_hex(PRESENTATION_ACCENT if i % 6 else PRESENTATION_ACCENT_ALT),
                font_size='20sp',
                bold=True,
            )
            with cell.canvas.before:
                Color(rgba=get_color_from_hex(STAKE_INPUT))
                cell._bg = RoundedRectangle(pos=cell.pos, size=cell.size, radius=[dp(8)])
            cell.bind(pos=lambda inst, val: setattr(inst._bg, 'pos', val), size=lambda inst, val: setattr(inst._bg, 'size', val))
            preview.add_widget(cell)
        layout.add_widget(preview)

        field_grid = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(90))
        self.m_in = StyledInput(text='5')
        self.p_in = StyledInput(text='3')
        field_grid.add_widget(Label(text="Risk Nodes", color=get_color_from_hex(STAKE_TEXT), font_size='12sp'))
        field_grid.add_widget(self.m_in)
        field_grid.add_widget(Label(text="Clear Nodes", color=get_color_from_hex(STAKE_TEXT), font_size='12sp'))
        field_grid.add_widget(self.p_in)
        layout.add_widget(field_grid)

        self.res = Label(text="Return Multiplier: --", font_size='18sp', color=get_color_from_hex(PRESENTATION_ACCENT), size_hint_y=None, height=dp(32))
        layout.add_widget(self.res)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        btn = StyledButton(text="ANALYZE GRID", bg_color=PRESENTATION_ACCENT_ALT)
        btn.color = (1, 1, 1, 1)
        btn.bind(on_release=self.calc)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(btn)
        btn_row.add_widget(clear_btn)
        layout.add_widget(btn_row)

        layout.add_widget(BoxLayout())
        layout.add_widget(SimpleNav())
        self.add_widget(layout)

    def clear_values(self, *args):
        clear_input_widgets([self.m_in, self.p_in])
        self.res.text = "Return Multiplier: --"

    def calc(self, *args):
        try:
            m = int(self.m_in.text)
            p = int(self.p_in.text)

            prob = Decimal(1)
            for i in range(p):
                prob *= (Decimal(25 - m - i) / Decimal(25 - i))

            self.res.text = f"Clear Rate: {prob * 100:.2f}% | Return Multiplier: {(Decimal(1) / prob):.2f}x"
        except Exception:
            pass


class CompoundScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(5))
        self.p_in = StyledInput(text="1000")
        self.r_in = StyledInput(text="12")
        self.t_in = StyledInput(text="10")
        self.target = StyledInput(text="2000")

        for l, w in [("Capital:", self.p_in), ("Rate %:", self.r_in), ("Days:", self.t_in), ("Target:", self.target)]:
            layout.add_widget(Label(text=l, height=dp(20), size_hint_y=None))
            layout.add_widget(w)

        self.res_label = Label(text="Final: --", bold=True, height=dp(30), size_hint_y=None)
        layout.add_widget(self.res_label)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        c_btn = StyledButton(text="Calc Growth")
        c_btn.bind(on_release=self.calc)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(c_btn)
        btn_row.add_widget(clear_btn)
        layout.add_widget(btn_row)

        self.breakdown = GridLayout(cols=1, spacing=2, size_hint_y=None)
        self.breakdown.bind(minimum_height=self.breakdown.setter('height'))

        scroll = ScrollView()
        scroll.add_widget(self.breakdown)
        layout.add_widget(scroll)

        layout.add_widget(SimpleNav())
        self.add_widget(layout)

    def clear_values(self, *args):
        clear_input_widgets([self.p_in, self.r_in, self.t_in, self.target])
        self.breakdown.clear_widgets()
        self.res_label.text = "Final: --"

    def calc(self, *args):
        self.breakdown.clear_widgets()

        try:
            p = float(self.p_in.text)
            r = float(self.r_in.text) / 100
            t = int(self.t_in.text)
            target = float(self.target.text)

            self.res_label.text = f"Final: {p * ((1 + r) ** t):,.2f}"

            for d in range(1, t + 1):
                val = p * ((1 + r) ** d)
                color = STAKE_GREEN if val >= target else STAKE_TEXT
                self.breakdown.add_widget(
                    Label(
                        text=f"Day {d}: {val:,.2f}",
                        height=dp(25),
                        size_hint_y=None,
                        color=get_color_from_hex(color)
                    )
                )
        except Exception:
            pass


class ConverterScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        self.last_edited = "crypto"
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))

        self.amt_crypto = StyledInput(text='1')
        self.amt_fiat = StyledInput(text='2500')

        self.amt_crypto.bind(text=lambda *a: self.set_last_edited("crypto"))
        self.amt_fiat.bind(text=lambda *a: self.set_last_edited("fiat"))

        self.c_spin = Spinner(
            text='bitcoin',
            values=('bitcoin', 'ethereum', 'litecoin', 'tether'),
            height=dp(40)
        )
        self.f_spin = Spinner(
            text='usd',
            values=('usd', 'inr', 'lkr'),
            height=dp(40)
        )

        layout.add_widget(Label(text="Crypto:"))
        layout.add_widget(self.amt_crypto)
        layout.add_widget(self.c_spin)
        layout.add_widget(Label(text="Fiat:"))
        layout.add_widget(self.amt_fiat)
        layout.add_widget(self.f_spin)

        self.res = Label(text="Price: --", color=get_color_from_hex(STAKE_GREEN))
        layout.add_widget(self.res)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        btn = StyledButton(text="Convert Now")
        btn.bind(on_release=self.convert)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(btn)
        btn_row.add_widget(clear_btn)
        layout.add_widget(btn_row)

        layout.add_widget(SimpleNav())
        self.add_widget(layout)

    def clear_values(self, *args):
        clear_input_widgets([self.amt_crypto, self.amt_fiat])
        self.res.text = "Price: --"
        self.last_edited = "crypto"

    def set_last_edited(self, source):
        if self.amt_crypto.focus or self.amt_fiat.focus:
            self.last_edited = source

    def convert(self, *args):
        try:
            url = (
                "https://api.coingecko.com/api/v3/simple/price"
                f"?ids={self.c_spin.text}&vs_currencies={self.f_spin.text}"
            )
            r = requests.get(url, timeout=10, verify=certifi.where()).json()
            price = float(r[self.c_spin.text][self.f_spin.text])

            if self.last_edited == "crypto":
                self.amt_fiat.text = f"{(float(self.amt_crypto.text) * price):.2f}"
            else:
                self.amt_crypto.text = f"{(float(self.amt_fiat.text) / price):.8f}"

            self.res.text = f"1 {self.c_spin.text.upper()} = {price} {self.f_spin.text.upper()}"
        except Exception:
            self.res.text = "Error fetching price"


class BlackjackScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        self.player_cards = []
        self.dealer_cards = []

        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))
        layout.add_widget(build_info_header("STATISTICAL DECK ENGINE"))
        layout.add_widget(Label(
            text="Abstract sample-input model on top, baseline input below. Outputs use neutral action labels only.",
            color=get_color_from_hex(STAKE_TEXT),
            font_size='11sp',
            size_hint_y=None,
            height=dp(24)
        ))

        score_row = BoxLayout(size_hint_y=None, height=dp(62), spacing=dp(6))
        self.sample_score = DiceStatCard('Sample Score', accent=PRESENTATION_ACCENT, value='--', value_font='20sp', title_font='10sp')
        self.baseline_score = DiceStatCard('Baseline Score', accent=PRESENTATION_ACCENT_ALT, value='--', value_font='20sp', title_font='10sp')
        score_row.add_widget(self.sample_score)
        score_row.add_widget(self.baseline_score)
        layout.add_widget(score_row)

        self.p_cards_lbl = Label(text="Sample Set: []", color=get_color_from_hex(PRESENTATION_ACCENT), font_size='18sp', bold=True, size_hint_y=None, height=dp(32))
        self.d_cards_lbl = Label(text="Baseline Set: []", color=get_color_from_hex(STAKE_TEXT), font_size='18sp', bold=True, size_hint_y=None, height=dp(32))
        layout.add_widget(self.p_cards_lbl)
        layout.add_widget(self.d_cards_lbl)

        self.advice_lbl = Label(text="ADD DATA", font_size='30sp', bold=True, color=get_color_from_hex(PRESENTATION_ACCENT), size_hint_y=None, height=dp(56))
        layout.add_widget(self.advice_lbl)

        layout.add_widget(Label(text="Sample Input", color=get_color_from_hex(STAKE_TEXT), font_size='11sp', size_hint_y=None, height=dp(16)))
        grid = GridLayout(cols=5, spacing=dp(4), size_hint_y=None, height=dp(104))
        for c in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'A']:
            btn = Button(text=c, background_color=get_color_from_hex(STAKE_INPUT), background_normal='')
            btn.bind(on_release=self.add_p)
            grid.add_widget(btn)
        layout.add_widget(grid)

        layout.add_widget(Label(text="Baseline Input", color=get_color_from_hex(STAKE_TEXT), font_size='11sp', size_hint_y=None, height=dp(16)))
        d_grid = GridLayout(cols=5, spacing=dp(4), size_hint_y=None, height=dp(104))
        for c in ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'A']:
            btn = Button(text=c, background_color=get_color_from_hex('#203446'), background_normal='')
            btn.bind(on_release=self.add_d)
            d_grid.add_widget(btn)
        layout.add_widget(d_grid)

        reset = StyledButton(text="CLEAR DATA", bg_color='#440000')
        reset.bind(on_release=self.clear_bj)
        layout.add_widget(reset)

        layout.add_widget(SimpleNav())
        self.add_widget(layout)

    def add_p(self, b):
        self.player_cards.append(b.text)
        self.update()

    def add_d(self, b):
        self.dealer_cards.append(b.text)
        self.update()

    def clear_bj(self, *args):
        self.player_cards = []
        self.dealer_cards = []
        self.update()

    def get_info(self, cards):
        val = 0
        aces = 0
        for c in cards:
            if c == 'A':
                aces += 1
                val += 11
            elif c in ['10', 'J', 'Q', 'K']:
                val += 10
            else:
                val += int(c)
        while val > 21 and aces:
            val -= 10
            aces -= 1
        return val, (aces > 0 and val <= 21)

    def update(self):
        p_val, p_soft = self.get_info(self.player_cards)
        d_val, _ = self.get_info(self.dealer_cards)
        self.p_cards_lbl.text = f"Sample Set: {', '.join(self.player_cards)}" if self.player_cards else "Sample Set: []"
        self.d_cards_lbl.text = f"Baseline Set: {', '.join(self.dealer_cards)}" if self.dealer_cards else "Baseline Set: []"
        self.sample_score.set_value('--' if not self.player_cards else str(p_val), PRESENTATION_ACCENT)
        self.baseline_score.set_value('--' if not self.dealer_cards else str(d_val), PRESENTATION_ACCENT_ALT)
        if p_val > 21:
            self.advice_lbl.text = "THRESHOLD BREACH"
        elif not self.player_cards or not self.dealer_cards:
            self.advice_lbl.text = "WAITING"
        else:
            self.advice_lbl.text = self.analyze(p_val, p_soft, d_val)

    def analyze(self, p, soft, d):
        if len(self.player_cards) == 2 and self.player_cards[0] == self.player_cards[1]:
            if self.player_cards[0] in ['A', '8']:
                return "BRANCH"
        if soft:
            if p >= 19:
                return "HOLD"
            return "HOLD" if p == 18 and d <= 8 else "ADD"
        if p >= 17:
            return "HOLD"
        if p >= 13 and d <= 6:
            return "HOLD"
        if p == 12 and 4 <= d <= 6:
            return "HOLD"
        if p == 11:
            return "SCALE"
        if p == 10 and d <= 9:
            return "SCALE"
        return "SCALE" if p == 9 and 3 <= d <= 6 else "ADD"



class PatternScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(5))
        self.base = StyledInput(text="5")
        self.grp = StyledInput(text="4")
        self.mult = StyledInput(text="25")
        self.cnt = StyledInput(text="24")

        grid = GridLayout(cols=2, spacing=dp(5), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        for l, w in [("Base:", self.base), ("Grp:", self.grp), ("%:", self.mult), ("Qty:", self.cnt)]:
            grid.add_widget(Label(text=l))
            grid.add_widget(w)

        layout.add_widget(grid)

        self.total_lbl = Label(text="Total: --", height=dp(30))
        layout.add_widget(self.total_lbl)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        g_btn = StyledButton(text="Generate Pattern")
        g_btn.bind(on_release=self.generate)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(g_btn)
        btn_row.add_widget(clear_btn)
        layout.add_widget(btn_row)

        self.res_grid = GridLayout(cols=3, spacing=2, size_hint_y=None)
        self.res_grid.bind(minimum_height=self.res_grid.setter('height'))

        scroll = ScrollView()
        scroll.add_widget(self.res_grid)
        layout.add_widget(scroll)

        layout.add_widget(SimpleNav())
        self.add_widget(layout)

    def clear_values(self, *args):
        clear_input_widgets([self.base, self.grp, self.mult, self.cnt])
        self.res_grid.clear_widgets()
        self.total_lbl.text = "Total: --"

    def generate(self, *args):
        self.res_grid.clear_widgets()

        try:
            b = float(self.base.text)
            g = int(self.grp.text)
            m = float(self.mult.text) / 100
            c = int(self.cnt.text)
            total = 0

            for i in range(1, c + 1):
                val = b * ((1 + m) ** ((i - 1) // g))
                total += val
                for txt in [str(i), f"{val:.6f}", str(int(val * 1000000))]:
                    self.res_grid.add_widget(
                        Label(text=txt, size_hint_y=None, height=dp(25), font_size='11sp')
                    )

            self.total_lbl.text = f"Total Sum: {total:.6f}"
        except Exception:
            pass





class StrategyStressTestScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        outer.add_widget(build_info_header("STRATEGY STRESS TEST"))

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))

        self.inputs = {}
        self.input_labels = {}
        fields = [
            ("Capital", "1000"),
            ("Base Entry", "10"),
            ("Multiplier / Target", "2.10"),
            ("Event Chance %", "47.14"),
            ("Tiles", "6"),
            ("Target Samples", "2"),
            ("Risk Node Count", "3"),
            ("Clear Nodes", "2"),
            ("Increase on Negative Result %", "35"),
            ("Max Entries / Session", "12"),
            ("Sessions", "1200"),
        ]
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for label_text, default in fields:
            lbl = Label(text=label_text, color=get_color_from_hex(STAKE_TEXT), font_size='12sp',
                        size_hint_y=None, height=dp(36))
            self.input_labels[label_text] = lbl
            grid.add_widget(lbl)
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(ti)
        inner.add_widget(grid)

        game_row = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(40))
        game_row.add_widget(Label(text="Game", color=get_color_from_hex(STAKE_TEXT), font_size='12sp'))
        self.game_spinner = Spinner(
            text='dice', values=('dice', 'limbo', 'keno', 'mines'),
            size_hint_y=None, height=dp(38), background_normal='',
            background_color=get_color_from_hex(STAKE_INPUT), color=(1, 1, 1, 1)
        )
        game_row.add_widget(self.game_spinner)
        inner.add_widget(game_row)

        btn_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        self.run_btn = StyledButton(text="RUN STRESS TEST")
        self.run_btn.bind(on_release=self.start_test)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp',
                                size_hint_y=None, height=dp(22))
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.status_lbl)
        inner.add_widget(self.progress_bar)

        self.summary = Label(text="Results will appear here", color=get_color_from_hex(STAKE_GREEN),
                             font_size='14sp', size_hint_y=None, height=dp(80))
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=2, spacing=dp(4), size_hint_y=None, padding=[dp(10), dp(8)])
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        apply_result_card_style(self.results_grid)
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)

        self._running = False
        self._stress_sync_guard = False
        self.game_spinner.bind(text=self._on_game_change)
        self.inputs["Multiplier / Target"].bind(text=self._on_multiplier_target_change)
        self._on_game_change(self.game_spinner, self.game_spinner.text)

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Results will appear here"

    def _set_field_enabled(self, field_name, enabled, disabled_value="0"):
        ti = self.inputs[field_name]
        lbl = self.input_labels.get(field_name)
        ti.disabled = not enabled
        ti.opacity = 1.0 if enabled else 0.55
        ti.background_color = get_color_from_hex(STAKE_INPUT if enabled else "#050505")
        if lbl is not None:
            lbl.color = get_color_from_hex(STAKE_TEXT if enabled else SUBTITLE_TEXT)
        if not enabled:
            ti.text = str(disabled_value)

    def _on_multiplier_target_change(self, instance, value):
        if self._stress_sync_guard:
            return
        if self.game_spinner.text not in ('dice', 'limbo'):
            return
        try:
            multi = max(1.01, float(value))
            chance = max(0.01, min(99.99, 99 / multi))
            self._stress_sync_guard = True
            self.inputs["Event Chance %"].text = f"{chance:.2f}"
        except Exception:
            pass
        finally:
            self._stress_sync_guard = False

    def _on_game_change(self, instance, value):
        game = str(value).strip().lower()
        is_dice_like = game in ('dice', 'limbo')
        is_keno = game == 'keno'
        is_mines = game == 'mines'

        self._set_field_enabled("Tiles", is_keno)
        self._set_field_enabled("Target Samples", is_keno)
        self._set_field_enabled("Risk Node Count", is_mines)
        self._set_field_enabled("Clear Nodes", is_mines)
        if is_dice_like:
            for field_name in ("Multiplier / Target", "Event Chance %"):
                self.inputs[field_name].disabled = False
                self.inputs[field_name].opacity = 1.0
                self.inputs[field_name].background_color = get_color_from_hex(STAKE_INPUT)
                lbl = self.input_labels.get(field_name)
                if lbl is not None:
                    lbl.color = get_color_from_hex(STAKE_TEXT)
            self._on_multiplier_target_change(None, self.inputs["Multiplier / Target"].text)
        else:
            for field_name in ("Multiplier / Target", "Event Chance %"):
                self.inputs[field_name].disabled = True
                self.inputs[field_name].opacity = 0.55
                self.inputs[field_name].background_color = get_color_from_hex("#050505")
                lbl = self.input_labels.get(field_name)
                if lbl is not None:
                    lbl.color = get_color_from_hex(SUBTITLE_TEXT)
                self.inputs[field_name].text = "0"

    def load_strategy(self, data):
        data = normalize_strategy(data)
        game = str(data.get("game", "dice")).lower().strip()
        if game not in ("dice", "limbo", "keno", "mines"):
            game = "dice"
        self.game_spinner.text = game
        self.inputs["Capital"].text = str(data.get("bank", "20") or "20")
        self.inputs["Base Entry"].text = str(data.get("base", "0.1") or "0.1")
        self.inputs["Multiplier / Target"].text = str(data.get("multi", "3.5") or "3.5")
        self.inputs["Increase on Negative Result %"].text = "50"
        try:
            loss = str(data.get("loss_action", ""))
            if "Increase" in loss:
                self.inputs["Increase on Negative Result %"].text = loss.split("Increase", 1)[1].replace("%", "").strip()
        except Exception:
            pass
        self.inputs["Max Entries / Session"].text = str(data.get("max_bets", "12") or "12")

        notes = str(data.get("notes", ""))
        if "Tiles " in notes:
            try:
                self.inputs["Tiles"].text = notes.split("Tiles ", 1)[1].split(" |", 1)[0].strip()
            except Exception:
                pass
        if "Target " in notes:
            try:
                self.inputs["Target Samples"].text = notes.split("Target ", 1)[1].split(" |", 1)[0].strip()
            except Exception:
                pass
        if "Risk Nodes " in notes:
            try:
                self.inputs["Risk Node Count"].text = notes.split("Risk Nodes ", 1)[1].split(" |", 1)[0].strip()
            except Exception:
                pass
        if "Picks " in notes:
            try:
                self.inputs["Clear Nodes"].text = notes.split("Picks ", 1)[1].split(" |", 1)[0].strip()
            except Exception:
                pass

        self._on_game_change(self.game_spinner, self.game_spinner.text)
        self._on_multiplier_target_change(None, self.inputs["Multiplier / Target"].text)

    def _reset_results(self):
        self.results_grid.clear_widgets()
        self._profits = []
        self._busts = 0
        self._wins = 0
        self._worst = None
        self._best = None
        self._longest_ls = 0
        self._done = 0

    def start_test(self, *args):
        if self._running:
            return
        self._running = True
        self.run_btn.disabled = True
        self.status_lbl.text = "Status: Initializing..."
        self._reset_results()

        self._game = self.game_spinner.text
        self._bankroll = safe_float(self.inputs["Capital"].text, 20)
        self._base = safe_float(self.inputs["Base Entry"].text, 0.1)
        self._multi = safe_float(self.inputs["Multiplier / Target"].text, 3.5)
        self._chance = safe_float(self.inputs["Event Chance %"].text, 28.29)
        self._tiles = safe_int(self.inputs["Tiles"].text, 6)
        self._target_hits = safe_int(self.inputs["Target Samples"].text, 2)
        self._mines = safe_int(self.inputs["Risk Node Count"].text, 3)
        self._safe_picks = safe_int(self.inputs["Clear Nodes"].text, 2)
        self._loss_inc = safe_float(self.inputs["Increase on Negative Result %"].text, 50)
        self._max_bets = safe_int(self.inputs["Max Entries / Session"].text, 12)
        self._sessions = max(1, safe_int(self.inputs["Sessions"].text, 5000))
        self.progress_bar.max = self._sessions
        self.progress_bar.value = 0
        self.summary.text = "Running stress test..."
        Clock.schedule_interval(self._process_batch, 0)

    def _dice_session(self):
        balance = max(1e-8, self._bankroll)
        bet = max(1e-8, self._base)
        profit = 0.0
        ls = 0
        longest = 0
        busted = False
        for _ in range(max(1, self._max_bets)):
            if bet > balance or bet <= 0:
                busted = True
                break
            balance -= bet
            if random.uniform(0, 100) < self._chance:
                payout = bet * self._multi
                balance += payout
                profit += payout - bet
                bet = self._base
                ls = 0
            else:
                profit -= bet
                ls += 1
                longest = max(longest, ls)
                bet = bet * (1 + self._loss_inc / 100.0)
        return profit, busted, longest

    def _limbo_session(self):
        chance = max(0.01, min(99.0, 99.0 / max(1.01, self._multi)))
        balance = max(1e-8, self._bankroll)
        bet = max(1e-8, self._base)
        profit = 0.0
        ls = 0
        longest = 0
        busted = False
        for _ in range(max(1, self._max_bets)):
            if bet > balance or bet <= 0:
                busted = True
                break
            balance -= bet
            if random.uniform(0, 100) < chance:
                payout = bet * self._multi
                balance += payout
                profit += payout - bet
                bet = self._base
                ls = 0
            else:
                profit -= bet
                ls += 1
                longest = max(longest, ls)
                bet = bet * (1 + self._loss_inc / 100.0)
        return profit, busted, longest

    def _comb(self, n, r):
        if r < 0 or r > n:
            return 0
        return math.comb(n, r)

    def _keno_exact_prob(self, tiles, hits):
        total = self._comb(40, 10)
        ways = self._comb(tiles, hits) * self._comb(40 - tiles, 10 - hits)
        return ways / total if total else 0.0

    def _keno_win_prob(self, tiles, target_hits):
        p = 0.0
        for h in range(target_hits, min(tiles, 10) + 1):
            p += self._keno_exact_prob(tiles, h)
        return p

    def _keno_session(self):
        payout_mult = (1.0 / max(1e-6, self._keno_win_prob(self._tiles, self._target_hits))) * 0.94
        balance = max(1e-8, self._bankroll)
        bet = max(1e-8, self._base)
        profit = 0.0
        ls = 0
        longest = 0
        busted = False
        for _ in range(max(1, self._max_bets)):
            if bet > balance or bet <= 0:
                busted = True
                break
            balance -= bet
            hits = len(set(random.sample(range(40), self._tiles)) & set(random.sample(range(40), 10)))
            if hits >= self._target_hits:
                payout = bet * payout_mult
                balance += payout
                profit += payout - bet
                bet = self._base
                ls = 0
            else:
                profit -= bet
                ls += 1
                longest = max(longest, ls)
                bet = bet * (1 + self._loss_inc / 100.0)
        return profit, busted, longest

    def _mines_win_prob(self, mines_count, safe_picks):
        safe_tiles = 25 - mines_count
        prob = 1.0
        for i in range(safe_picks):
            prob *= (safe_tiles - i) / (25 - i)
        return prob

    def _mines_session(self):
        payout_mult = (1.0 / max(1e-6, self._mines_win_prob(self._mines, self._safe_picks))) * 0.94
        balance = max(1e-8, self._bankroll)
        bet = max(1e-8, self._base)
        profit = 0.0
        ls = 0
        longest = 0
        busted = False
        for _ in range(max(1, self._max_bets)):
            if bet > balance or bet <= 0:
                busted = True
                break
            balance -= bet
            tiles = list(range(25))
            mine_set = set(random.sample(tiles, self._mines))
            remaining = tiles[:]
            won = True
            for _p in range(self._safe_picks):
                pick = random.choice(remaining)
                remaining.remove(pick)
                if pick in mine_set:
                    won = False
                    break
            if won:
                payout = bet * payout_mult
                balance += payout
                profit += payout - bet
                bet = self._base
                ls = 0
            else:
                profit -= bet
                ls += 1
                longest = max(longest, ls)
                bet = bet * (1 + self._loss_inc / 100.0)
        return profit, busted, longest

    def _run_one(self):
        if self._game == 'dice':
            return self._dice_session()
        if self._game == 'limbo':
            return self._limbo_session()
        if self._game == 'keno':
            return self._keno_session()
        return self._mines_session()

    def _process_batch(self, dt):
        batch = min(50, self._sessions - self._done)
        for _ in range(batch):
            p, busted, longest = self._run_one()
            self._profits.append(p)
            if busted:
                self._busts += 1
            if p > 0:
                self._wins += 1
            self._best = p if self._best is None else max(self._best, p)
            self._worst = p if self._worst is None else min(self._worst, p)
            self._longest_ls = max(self._longest_ls, longest)
            self._done += 1

        self.progress_bar.value = self._done
        self.status_lbl.text = f"Status: Testing {self._done} / {self._sessions}"

        if self._done >= self._sessions:
            avg_profit = statistics.mean(self._profits) if self._profits else 0.0
            median_profit = statistics.median(self._profits) if self._profits else 0.0
            win_rate = (self._wins / self._sessions) * 100.0
            bust_rate = (self._busts / self._sessions) * 100.0

            self.results_grid.clear_widgets()
            lines = [
                ("Average Net Units", f"{avg_profit:.4f}"),
                ("Median Net Units", f"{median_profit:.4f}"),
                ("Best Session", f"{self._best:.4f}"),
                ("Worst Session", f"{self._worst:.4f}"),
                ("Net Unitsable Sessions", f"{win_rate:.2f}%"),
                ("Threshold Rate", f"{bust_rate:.2f}%"),
                ("Longest Negative Streak", str(self._longest_ls)),
                ("Game", self._game.upper()),
            ]
            for k, v in lines:
                self.results_grid.add_widget(Label(text=k, color=get_color_from_hex(STAKE_TEXT), size_hint_y=None, height=dp(24)))
                self.results_grid.add_widget(Label(text=v, color=get_color_from_hex(STAKE_GREEN), size_hint_y=None, height=dp(24)))

            self.summary.text = "Stress test complete."
            self.status_lbl.text = "Status: Complete"
            self.run_btn.disabled = False
            self._running = False
            # Share button
            self._stress_last = dict(avg=avg_profit, med=median_profit, best=self._best,
                                     worst=self._worst, wr=win_rate, br=bust_rate,
                                     ls=self._longest_ls, game=self._game)
            share_btn = StyledButton(text="SHARE RESULT", bg_color=UTILITY_COLOR)
            share_btn.color = (1, 1, 1, 1)
            share_btn.size_hint_y = None
            share_btn.height = dp(42)
            share_btn.bind(on_release=self._share_stress_result)
            self.results_grid.add_widget(share_btn)
            self.results_grid.add_widget(Label(size_hint_y=None, height=dp(42)))
            return False
        return True


    def _share_stress_result(self, *args):
        r = getattr(self, '_stress_last', None)
        if not r:
            return
        share_result(f"Strategy Stress Test ({r['game'].upper()})", [
            f"Average Net Units:        {r['avg']:.4f}",
            f"Median Net Units:         {r['med']:.4f}",
            f"Best Session:          {r['best']:.4f}",
            f"Worst Session:         {r['worst']:.4f}",
            f"Positive Sessions:   {r['wr']:.2f}%",
            f"Threshold Rate:             {r['br']:.2f}%",
            f"Longest Negative Streak:   {r['ls']}",
        ])


class BankrollSurvivalScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))
        outer.add_widget(build_info_header("CAPITAL SUSTAINABILITY"))

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))
        self.inputs = {}
        fields = [
            ("Capital", "1000"),
            ("Base Entry", "10"),
            ("Event Chance %", "47.14"),
            ("Threshold", "2.10"),
            ("Increase on Negative Result %", "35"),
            ("Max Entries / Session", "12"),
            ("Sessions", "1200"),
        ]
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for label_text, default in fields:
            grid.add_widget(Label(text=label_text, color=get_color_from_hex(STAKE_TEXT), font_size='12sp',
                                  size_hint_y=None, height=dp(36)))
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(ti)
        inner.add_widget(grid)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        self.run_btn = StyledButton(text="RUN SURVIVAL TEST")
        self.run_btn.bind(on_release=self.start_test)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp',
                                size_hint_y=None, height=dp(22))
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.status_lbl)
        inner.add_widget(self.progress_bar)

        self.summary = Label(text="Results will appear here", color=get_color_from_hex(STAKE_GREEN),
                             font_size='14sp', size_hint_y=None, height=dp(80))
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=2, spacing=dp(4), size_hint_y=None, padding=[dp(10), dp(8)])
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        apply_result_card_style(self.results_grid)
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)
        self._running = False

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Results will appear here"

    def start_test(self, *args):
        if self._running:
            return
        self._running = True
        self.run_btn.disabled = True
        self.results_grid.clear_widgets()
        self._bankroll = safe_float(self.inputs["Capital"].text, 20)
        self._base = safe_float(self.inputs["Base Entry"].text, 0.1)
        self._chance = safe_float(self.inputs["Event Chance %"].text, 49.5)
        self._multi = safe_float(self.inputs["Threshold"].text, 2.0)
        self._loss_inc = safe_float(self.inputs["Increase on Negative Result %"].text, 50)
        self._max_bets = safe_int(self.inputs["Max Entries / Session"].text, 12)
        self._sessions = max(1, safe_int(self.inputs["Sessions"].text, 5000))
        self._done = 0
        self._survived = 0
        self._profits = []
        self._worst = None
        self._best = None
        self.progress_bar.max = self._sessions
        self.progress_bar.value = 0
        self.summary.text = "Running survival simulation..."
        Clock.schedule_interval(self._process_batch, 0)

    def _process_batch(self, dt):
        batch = min(50, self._sessions - self._done)
        for _ in range(batch):
            result = MonteCarloEngine.run_sessions(
                bankroll=self._bankroll,
                base_bet=self._base,
                multiplier=self._multi,
                win_chance=self._chance,
                inc_on_win=0,
                inc_on_loss=self._loss_inc,
                stop_profit=0,
                stop_loss=0,
                max_bets=self._max_bets,
                sessions=1,
            )
            p = result["average_profit"]
            busted = result["bust_rate"] > 0
            if not busted:
                self._survived += 1
            self._profits.append(p)
            self._best = p if self._best is None else max(self._best, p)
            self._worst = p if self._worst is None else min(self._worst, p)
            self._done += 1

        self.progress_bar.value = self._done
        self.status_lbl.text = f"Status: Simulating {self._done} / {self._sessions}"

        if self._done >= self._sessions:
            survival = (self._survived / self._sessions) * 100.0
            bust = 100.0 - survival
            avg_profit = statistics.mean(self._profits) if self._profits else 0.0
            roi = (avg_profit / max(1e-8, self._bankroll)) * 100.0
            lines = [
                ("Survival Chance", f"{survival:.2f}%"),
                ("Threshold Chance", f"{bust:.2f}%"),
                ("Average Net Units", f"{avg_profit:.4f}"),
                ("Expected ROI", f"{roi:.2f}%"),
                ("Best Session", f"{self._best:.4f}"),
                ("Worst Session", f"{self._worst:.4f}"),
            ]
            for k, v in lines:
                self.results_grid.add_widget(Label(text=k, color=get_color_from_hex(STAKE_TEXT), size_hint_y=None, height=dp(24)))
                self.results_grid.add_widget(Label(text=v, color=get_color_from_hex(STAKE_GREEN), size_hint_y=None, height=dp(24)))

            self.summary.text = "Capital survival simulation complete."
            self.status_lbl.text = "Status: Complete"
            self.run_btn.disabled = False
            self._running = False
            # Share button
            self._survival_last = dict(survival=survival, bust=bust, avg=avg_profit,
                                       roi=roi, best=self._best, worst=self._worst)
            share_btn = StyledButton(text="SHARE RESULT", bg_color=UTILITY_COLOR)
            share_btn.color = (1, 1, 1, 1)
            share_btn.size_hint_y = None
            share_btn.height = dp(42)
            share_btn.bind(on_release=self._share_survival_result)
            self.results_grid.add_widget(share_btn)
            self.results_grid.add_widget(Label(size_hint_y=None, height=dp(42)))
            return False
        return True


    def _share_survival_result(self, *args):
        r = getattr(self, '_survival_last', None)
        if not r:
            return
        share_result("Capital Sustainability", [
            f"Survival Chance:       {r['survival']:.2f}%",
            f"Threshold Probability:           {r['bust']:.2f}%",
            f"Average Net Units:        {r['avg']:.4f}",
            f"Expected ROI:          {r['roi']:.2f}%",
            f"Best Session:          {r['best']:.4f}",
            f"Worst Session:         {r['worst']:.4f}",
        ])


class StrategyForgeScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        outer = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))
        outer.add_widget(build_info_header("STRATEGY FORGE", STRATEGY_FORGE_HELP))

        scroll = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        inner.bind(minimum_height=inner.setter('height'))
        self.inputs = {}
        fields = [
            ("Capital", "1000"),
            ("Population Size", "18"),
            ("Generations", "4"),
            ("Elite Keep", "4"),
            ("Children Per Generation", "18"),
            ("Sessions / Strategy", "250"),
            ("Max Entries / Session", "10"),
            ("Top Results", "6"),
        ]
        grid = GridLayout(cols=2, spacing=dp(10), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        for label_text, default in fields:
            grid.add_widget(Label(text=label_text, color=get_color_from_hex(STAKE_TEXT), font_size='12sp',
                                  size_hint_y=None, height=dp(36)))
            ti = StyledInput(text=default)
            self.inputs[label_text] = ti
            grid.add_widget(ti)
        inner.add_widget(grid)

        row1 = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(40))
        row1.add_widget(Label(text="Game", color=get_color_from_hex(STAKE_TEXT), font_size='12sp'))
        self.game_spinner = Spinner(text='dice', values=('dice', 'limbo', 'keno', 'mines'),
                                    size_hint_y=None, height=dp(38), background_normal='',
                                    background_color=get_color_from_hex(STAKE_INPUT), color=(1,1,1,1))
        row1.add_widget(self.game_spinner)
        inner.add_widget(row1)

        row2 = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(40))
        row2.add_widget(Label(text="Optimize For", color=get_color_from_hex(STAKE_TEXT), font_size='12sp'))
        self.goal_spinner = Spinner(text='Net Units/Risk', values=('Net Units', 'Safety', 'Net Units/Risk'),
                                    size_hint_y=None, height=dp(38), background_normal='',
                                    background_color=get_color_from_hex(STAKE_INPUT), color=(1,1,1,1))
        row2.add_widget(self.goal_spinner)
        inner.add_widget(row2)

        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        self.run_btn = StyledButton(text="DISCOVER STRATEGY")
        self.run_btn.bind(on_release=self.start_forge)
        clear_btn = StyledButton(text="CLEAR VALUES", bg_color=SOFT_RED)
        clear_btn.color = (1, 1, 1, 1)
        clear_btn.bind(on_release=self.clear_values)
        btn_row.add_widget(self.run_btn)
        btn_row.add_widget(clear_btn)
        inner.add_widget(btn_row)

        self.status_lbl = Label(text="Status: Idle", color=get_color_from_hex(STAKE_TEXT), font_size='11sp',
                                size_hint_y=None, height=dp(22))
        self.progress_bar = ProgressBar(max=1, value=0, size_hint_y=None, height=dp(10))
        inner.add_widget(self.status_lbl)
        inner.add_widget(self.progress_bar)

        self.summary = Label(text="Best discovered strategies will appear here", color=get_color_from_hex(STAKE_GREEN),
                             font_size='14sp', size_hint_y=None, height=dp(80))
        inner.add_widget(self.summary)

        self.results_grid = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.results_grid.bind(minimum_height=self.results_grid.setter('height'))
        inner.add_widget(self.results_grid)

        scroll.add_widget(inner)
        outer.add_widget(scroll)
        outer.add_widget(SimpleNav())
        self.add_widget(outer)
        self._running = False

    def clear_values(self, *args):
        clear_input_widgets(self.inputs)
        self.results_grid.clear_widgets()
        self.progress_bar.value = 0
        self.status_lbl.text = "Status: Idle"
        self.summary.text = "Best discovered strategies will appear here"

    def compute_score(self, avg_profit, bust_rate, win_rate):
        goal = self.goal_spinner.text
        if goal == "Net Units":
            return avg_profit
        elif goal == "Safety":
            return (win_rate * 0.2) - (bust_rate * 3.0)
        return avg_profit - (bust_rate * 0.25)

    def _comb(self, n, r):
        return math.comb(n, r) if 0 <= r <= n else 0

    def _keno_prob(self, tiles, target):
        total = self._comb(40, 10)
        p = 0.0
        for h in range(target, min(tiles, 10)+1):
            ways = self._comb(tiles, h) * self._comb(40-tiles, 10-h)
            p += ways / total if total else 0
        return p

    def _mines_prob(self, mines_count, safe_picks):
        safe_tiles = 25 - mines_count
        prob = 1.0
        for i in range(safe_picks):
            prob *= (safe_tiles - i) / (25 - i)
        return prob

    def random_strategy(self, bankroll):
        g = self.game_spinner.text
        if g == 'dice':
            return {"base_bet": round(random.uniform(0.01, min(0.25, bankroll*0.02)), 4),
                    "multiplier": round(random.uniform(1.5, 8.0), 2),
                    "loss_pct": round(random.uniform(5, 80), 2)}
        if g == 'limbo':
            return {"base_bet": round(random.uniform(0.01, min(0.25, bankroll*0.02)), 4),
                    "target_multiplier": round(random.uniform(1.5, 15.0), 2),
                    "loss_pct": round(random.uniform(5, 80), 2)}
        if g == 'keno':
            tiles = random.randint(1, 10)
            return {"tiles": tiles, "target_hits": random.randint(1, min(tiles, 6)),
                    "base_bet": round(random.uniform(0.01, min(0.25, bankroll*0.02)), 4),
                    "loss_pct": round(random.uniform(5, 80), 2)}
        mines = random.randint(1, 10)
        safe_picks = random.randint(1, max(1, min(10, 24-mines)))
        return {"mines_count": mines, "safe_picks": safe_picks,
                "base_bet": round(random.uniform(0.01, min(0.25, bankroll*0.02)), 4),
                "loss_pct": round(random.uniform(5, 80), 2)}

    def mutate_strategy(self, parent, bankroll):
        g = self.game_spinner.text
        if g == 'dice':
            return {
                "base_bet": max(0.01, min(round(parent["base_bet"] * random.uniform(0.85, 1.15), 4), min(0.25, bankroll*0.02))),
                "multiplier": max(1.2, min(round(parent["multiplier"] * random.uniform(0.9, 1.1), 2), 15.0)),
                "loss_pct": max(1.0, min(round(parent["loss_pct"] * random.uniform(0.85, 1.15), 2), 100.0)),
            }
        if g == 'limbo':
            return {
                "base_bet": max(0.01, min(round(parent["base_bet"] * random.uniform(0.85, 1.15), 4), min(0.25, bankroll*0.02))),
                "target_multiplier": max(1.2, min(round(parent["target_multiplier"] * random.uniform(0.9, 1.1), 2), 25.0)),
                "loss_pct": max(1.0, min(round(parent["loss_pct"] * random.uniform(0.85, 1.15), 2), 100.0)),
            }
        if g == 'keno':
            tiles = max(1, min(10, parent["tiles"] + random.choice([-1,0,1])))
            target = max(1, min(tiles, parent["target_hits"] + random.choice([-1,0,1])))
            return {
                "tiles": tiles,
                "target_hits": target,
                "base_bet": max(0.01, min(round(parent["base_bet"] * random.uniform(0.85, 1.15), 4), min(0.25, bankroll*0.02))),
                "loss_pct": max(1.0, min(round(parent["loss_pct"] * random.uniform(0.85, 1.15), 2), 100.0)),
            }
        mines = max(1, min(10, parent["mines_count"] + random.choice([-1,0,1])))
        safe_picks = max(1, min(24-mines, parent["safe_picks"] + random.choice([-1,0,1])))
        return {
            "mines_count": mines,
            "safe_picks": safe_picks,
            "base_bet": max(0.01, min(round(parent["base_bet"] * random.uniform(0.85, 1.15), 4), min(0.25, bankroll*0.02))),
            "loss_pct": max(1.0, min(round(parent["loss_pct"] * random.uniform(0.85, 1.15), 2), 100.0)),
        }

    def _eval(self, strat, bankroll, max_bets, sessions_per_strategy):
        g = self.game_spinner.text
        if g == 'dice':
            result = MonteCarloEngine.run_sessions(bankroll, strat["base_bet"], strat["multiplier"], 99/max(1.01,strat["multiplier"]), 0, strat["loss_pct"], 0, 0, max_bets, sessions_per_strategy)
            return {**strat, "label": f"B{strat['base_bet']} M{strat['multiplier']} L{strat['loss_pct']}",
                    "avg_profit": result["average_profit"], "median_profit": result["median_profit"], "best_session": result["best_session"], "worst_session": result["worst_session"],
                    "win_rate": result["win_rate"], "bust_rate": result["bust_rate"], "longest_ls": result["longest_loss_streak"],
                    "score": self.compute_score(result["average_profit"], result["bust_rate"], result["win_rate"])}
        if g == 'limbo':
            chance = 99.0 / max(1.01, strat["target_multiplier"])
            result = MonteCarloEngine.run_sessions(bankroll, strat["base_bet"], strat["target_multiplier"], chance, 0, strat["loss_pct"], 0, 0, max_bets, sessions_per_strategy)
            return {**strat, "label": f"B{strat['base_bet']} T{strat['target_multiplier']} L{strat['loss_pct']}",
                    "avg_profit": result["average_profit"], "median_profit": result["median_profit"], "best_session": result["best_session"], "worst_session": result["worst_session"],
                    "win_rate": result["win_rate"], "bust_rate": result["bust_rate"], "longest_ls": result["longest_loss_streak"],
                    "score": self.compute_score(result["average_profit"], result["bust_rate"], result["win_rate"])}
        if g == 'keno':
            p = self._keno_prob(strat["tiles"], strat["target_hits"])
            result = MonteCarloEngine.run_sessions(bankroll, strat["base_bet"], (1/max(1e-6,p))*0.94, p*100, 0, strat["loss_pct"], 0, 0, max_bets, sessions_per_strategy)
            return {**strat, "label": f"{strat['tiles']}T {strat['target_hits']}H B{strat['base_bet']} L{strat['loss_pct']}",
                    "avg_profit": result["average_profit"], "median_profit": result["median_profit"], "best_session": result["best_session"], "worst_session": result["worst_session"],
                    "win_rate": result["win_rate"], "bust_rate": result["bust_rate"], "longest_ls": result["longest_loss_streak"],
                    "score": self.compute_score(result["average_profit"], result["bust_rate"], result["win_rate"])}
        p = self._mines_prob(strat["mines_count"], strat["safe_picks"])
        result = MonteCarloEngine.run_sessions(bankroll, strat["base_bet"], (1/max(1e-6,p))*0.94, p*100, 0, strat["loss_pct"], 0, 0, max_bets, sessions_per_strategy)
        return {**strat, "label": f"{strat['mines_count']}M {strat['safe_picks']}P B{strat['base_bet']} L{strat['loss_pct']}",
                "avg_profit": result["average_profit"], "median_profit": result["median_profit"], "best_session": result["best_session"], "worst_session": result["worst_session"],
                "win_rate": result["win_rate"], "bust_rate": result["bust_rate"], "longest_ls": result["longest_loss_streak"],
                "score": self.compute_score(result["average_profit"], result["bust_rate"], result["win_rate"])}

    def start_forge(self, *args):
        if self._running:
            return
        self._running = True
        self.run_btn.disabled = True
        self.results_grid.clear_widgets()
        self._bankroll = safe_float(self.inputs["Capital"].text, 20)
        self._population_size = max(2, safe_int(self.inputs["Population Size"].text, 24))
        self._generations = max(1, safe_int(self.inputs["Generations"].text, 6))
        self._elite_keep = max(1, safe_int(self.inputs["Elite Keep"].text, 6))
        self._children_per_generation = max(2, safe_int(self.inputs["Children Per Generation"].text, 24))
        self._sessions_per_strategy = max(1, safe_int(self.inputs["Sessions / Strategy"].text, 400))
        self._max_bets = max(1, safe_int(self.inputs["Max Entries / Session"].text, 12))
        self._top_results = max(1, safe_int(self.inputs["Top Results"].text, 8))
        self._population = [self.random_strategy(self._bankroll) for _ in range(self._population_size)]
        self._generation = 0
        self._best_overall = []
        self.progress_bar.max = self._generations
        self.progress_bar.value = 0
        self.summary.text = "Searching for strong strategies..."
        Clock.schedule_interval(self._forge_step, 0)

    def _forge_step(self, dt):
        if self._generation >= self._generations:
            unique_results = []
            seen = set()
            for item in sorted(self._best_overall, key=lambda x: x["score"], reverse=True):
                key = item["label"]
                if key not in seen:
                    seen.add(key)
                    unique_results.append(item)
            self.results_grid.clear_widgets()
            for i, item in enumerate(unique_results[:self._top_results], start=1):
                card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(148), padding=dp(8), spacing=dp(3))
                def _upd(inst, val):
                    if hasattr(inst, "_bg_rect"):
                        inst._bg_rect.pos = inst.pos
                        inst._bg_rect.size = inst.size
                with card.canvas.before:
                    Color(rgba=get_color_from_hex(STAKE_INPUT))
                    card._bg_rect = Rectangle(pos=card.pos, size=card.size)
                card.bind(pos=_upd, size=_upd)
                card.add_widget(Label(text=f"#{i} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}%",
                                      color=get_color_from_hex(STAKE_GREEN), bold=True, size_hint_y=None, height=dp(22), font_size='12sp'))
                card.add_widget(Label(text=item["label"], color=get_color_from_hex(STAKE_TEXT), size_hint_y=None, height=dp(20), font_size='11sp'))
                card.add_widget(Label(text=f"Positive Rate: {item['win_rate']:.2f}% | Longest NS: {item['longest_ls']} | Score: {item['score']:.4f}",
                                      color=get_color_from_hex(STAKE_TEXT), size_hint_y=None, height=dp(20), font_size='11sp'))
                note = "Simulation result only. Real-world environments may differ."
                card.add_widget(Label(text=note, color=get_color_from_hex(SUBTITLE_TEXT), size_hint_y=None, height=dp(34), font_size='10sp'))
                save_btn = StyledButton(text="SAVE TO LIBRARY", bg_color=UTILITY_COLOR, height=dp(32))
                save_btn.bind(on_release=lambda x, data=item, rank=i: self.save_result(data, rank))
                card.add_widget(save_btn)
                self.results_grid.add_widget(card)
            self.status_lbl.text = "Status: Complete"
            self.summary.text = "Strategy discovery complete."
            self.run_btn.disabled = False
            self._running = False
            return False

        evaluated = [self._eval(s, self._bankroll, self._max_bets, self._sessions_per_strategy) for s in self._population]
        evaluated.sort(key=lambda x: x["score"], reverse=True)
        elites = evaluated[:self._elite_keep]
        self._best_overall.extend(elites)
        elite_strats = []
        for e in elites:
            e = dict(e)
            # strip derived keys
            for k in list(e.keys()):
                if k in ("label","avg_profit","median_profit","best_session","worst_session","win_rate","bust_rate","longest_ls","score"):
                    e.pop(k,None)
            elite_strats.append(e)
        new_population = []
        while len(new_population) < self._children_per_generation:
            parent = random.choice(elite_strats)
            new_population.append(self.mutate_strategy(parent, self._bankroll))
        self._population = new_population
        self._generation += 1
        self.progress_bar.value = self._generation
        top_score = elites[0]["score"] if elites else 0.0
        self.status_lbl.text = f"Status: Generation {self._generation} / {self._generations}"
        self.summary.text = f"Best score so far: {top_score:.4f}"
        return True

    def save_result(self, item, rank):
        game = self.game_spinner.text
        if game == 'dice':
            strategy = normalize_strategy({
                "name": f"FORGE RNG | {item['label']}",
                "category": "Experimental",
                "game": "dice",
                "source": "strategy_forge",
                "bank": str(self.inputs["Capital"].text),
                "base": str(item["base_bet"]),
                "multi": str(item["multiplier"]),
                "win_action": "Reset",
                "loss_action": f"Increase {item['loss_pct']}%",
                "max_bets": str(self.inputs["Max Entries / Session"].text),
                "notes": f"Saved from Strategy Forge | Rank #{rank} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}% | Score {item['score']:.4f}"
            })
        elif game == 'limbo':
            strategy = normalize_strategy({
                "name": f"FORGE THR | {item['label']}",
                "category": "Experimental",
                "game": "limbo",
                "source": "strategy_forge",
                "bank": str(self.inputs["Capital"].text),
                "base": str(item["base_bet"]),
                "multi": str(item["target_multiplier"]),
                "win_action": "Reset",
                "loss_action": f"Increase {item['loss_pct']}%",
                "max_bets": str(self.inputs["Max Entries / Session"].text),
                "notes": f"Saved from Strategy Forge | Rank #{rank} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}% | Score {item['score']:.4f}"
            })
        elif game == 'keno':
            p = self._keno_prob(item["tiles"], item["target_hits"])
            strategy = normalize_strategy({
                "name": f"FORGE GRID | {item['label']}",
                "category": "Experimental",
                "game": "keno",
                "source": "strategy_forge",
                "bank": str(self.inputs["Capital"].text),
                "base": str(item["base_bet"]),
                "multi": str(round((1/max(1e-6,p))*0.94,2)),
                "win_action": "Reset",
                "loss_action": f"Increase {item['loss_pct']}%",
                "max_bets": str(self.inputs["Max Entries / Session"].text),
                "notes": f"Saved from Strategy Forge | Rank #{rank} | Samples {item['tiles']} | Target {item['target_hits']} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}% | Score {item['score']:.4f}"
            })
        else:
            p = self._mines_prob(item["mines_count"], item["safe_picks"])
            strategy = normalize_strategy({
                "name": f"FORGE RISK | {item['label']}",
                "category": "Experimental",
                "game": "mines",
                "source": "strategy_forge",
                "bank": str(self.inputs["Capital"].text),
                "base": str(item["base_bet"]),
                "multi": str(round((1/max(1e-6,p))*0.94,2)),
                "win_action": "Reset",
                "loss_action": f"Increase {item['loss_pct']}%",
                "max_bets": str(self.inputs["Max Entries / Session"].text),
                "notes": f"Saved from Strategy Forge | Rank #{rank} | Risk Nodes {item['mines_count']} | Clear Nodes {item['safe_picks']} | Avg {item['avg_profit']:.4f} | Threshold {item['bust_rate']:.2f}% | Score {item['score']:.4f}"
            })
        GLOBAL_BANK.strategies.append(strategy)
        GLOBAL_BANK.save_strategies()
        Popup(title="Saved", content=Label(text=f"Saved:\n{strategy['name']}"), size_hint=(0.75,0.25)).open()



class MainMenu(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        self.tile_buttons = {}
        self.section_header_labels = {}
        self.section_header_dividers = {}
        self.tile_defs = {}
        self.presentation_toggle_btn = None
        self.presentation_row = None
        self.mode_badge_lbl = None

        outer = BoxLayout(orientation='vertical', padding=[dp(12), dp(18), dp(12), dp(8)], spacing=dp(6))

        self.hero = hero = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(166), padding=dp(8), spacing=dp(3))

        def _hero_update(instance, value):
            if hasattr(instance, "_bg_rect"):
                instance._bg_rect.pos = instance.pos
                instance._bg_rect.size = instance.size
            if hasattr(instance, "_strip_left"):
                w = instance.width / 3.0
                instance._strip_left.pos = instance.pos
                instance._strip_left.size = (w, dp(4))
                instance._strip_mid.pos = (instance.x + w, instance.y)
                instance._strip_mid.size = (w, dp(4))
                instance._strip_right.pos = (instance.x + (2 * w), instance.y)
                instance._strip_right.size = (w, dp(4))

        with hero.canvas.before:
            hero._bg_color = Color(rgba=get_color_from_hex(STAKE_INPUT))
            hero._bg_rect = Rectangle(pos=hero.pos, size=hero.size)
            hero._strip_left_color = Color(rgba=get_color_from_hex(DICE_COLOR))
            hero._strip_left = Rectangle(pos=hero.pos, size=(0, 0))
            hero._strip_mid_color = Color(rgba=get_color_from_hex(KENO_COLOR))
            hero._strip_mid = Rectangle(pos=hero.pos, size=(0, 0))
            hero._strip_right_color = Color(rgba=get_color_from_hex(SPORTS_COLOR))
            hero._strip_right = Rectangle(pos=hero.pos, size=(0, 0))
        hero.bind(pos=_hero_update, size=_hero_update)

        self.bank_lbl = Label(text="UNITS: U0.00 | SESSION: 00:00", size_hint_y=None, height=dp(22), color=get_color_from_hex(STAKE_GREEN), bold=True)
        Clock.schedule_interval(self.update_header, 1)
        self.title_lbl = Label(text="Strategy Suite Pro  [size=18]v1.0[/size]", markup=True, font_size='32sp', bold=True, size_hint_y=None, height=dp(40), color=get_color_from_hex(STAKE_GREEN), halign='center', valign='middle')
        self.subtitle_lbl = Label(text="Advanced risk analytics toolkit", color=get_color_from_hex(SUBTITLE_TEXT), font_size='11sp', size_hint_y=None, height=dp(14))
        self.demo_lbl = Label(text="", color=get_color_from_hex(STAKE_TEXT), font_size='10sp', size_hint_y=None, height=dp(16))

        self.profile_lbl = Label(
            text=get_profile_badge_text(),
            color=get_color_from_hex(DICE_COLOR),
            font_size='10sp',
            bold=True,
            size_hint_y=None,
            height=dp(14),
            halign='center',
            valign='middle',
        )
        self.profile_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))

        self.mode_badge_lbl = Label(
            text='',
            color=get_color_from_hex(PRESENTATION_ACCENT),
            font_size='10sp',
            bold=True,
            size_hint_y=None,
            height=dp(0),
            halign='center',
            valign='middle',
        )
        self.mode_badge_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))

        self.presentation_row = BoxLayout(size_hint_y=None, height=dp(0), spacing=dp(0), opacity=0)
        self.presentation_toggle_btn = StyledButton(text='', bg_color=PRESENTATION_ACCENT_ALT, height=dp(34))
        self.presentation_toggle_btn.color = (1, 1, 1, 1)
        self.presentation_toggle_btn.bind(on_release=self.toggle_presentation_mode)
        self.presentation_row.add_widget(self.presentation_toggle_btn)

        p_box = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(5))
        self.p_in = StyledInput(hint_text="Enter Result (+/-)")
        self.p_in.height = dp(32)
        p_box.add_widget(self.p_in)
        u_btn = StyledButton(text="UPDATE", size_hint_x=0.32, bg_color=UTILITY_COLOR, height=dp(32))
        u_btn.bind(on_release=self.update_profit)
        p_box.add_widget(u_btn)

        hero.add_widget(self.bank_lbl)
        hero.add_widget(self.title_lbl)
        hero.add_widget(self.subtitle_lbl)
        hero.add_widget(self.profile_lbl)
        hero.add_widget(self.demo_lbl)
        hero.add_widget(self.mode_badge_lbl)
        hero.add_widget(p_box)
        outer.add_widget(hero)

        scroll = ScrollView(do_scroll_x=False, bar_width=0)
        self.body = body = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[0, 0, 0, dp(6)])
        body.bind(minimum_height=body.setter('height'))

        self.featured_grid = GridLayout(cols=3, spacing=dp(6), size_hint_y=None, height=dp(106))
        self.featured_defs = [
            ('strats', LIBRARY_COLOR, True),
            ('dice_sim', DICE_COLOR, True),
            ('dice', DICE_COLOR, True),
            ('mc', DICE_COLOR, True),
            ('dice_opt', DICE_COLOR, True),
            ('dice_gen', DICE_COLOR, True),
        ]
        for sid, color, tall in self.featured_defs:
            tile = self.make_tile(
                MENU_TILE_LABELS.get(sid, TOOL_TITLES.get(sid, sid)),
                sid,
                color,
                tall=tall,
                height_override=dp(50),
                font_size_override='12sp'
            )
            self.tile_buttons[sid] = tile
            self.tile_defs[sid] = {'color': color, 'tall': tall, 'compact': False}
            self.featured_grid.add_widget(tile)
        body.add_widget(self.featured_grid)

        self.section_configs = [
            ('evolution', [('forge', DICE_COLOR), ('dice_evo', DICE_COLOR), ('limbo_evo', LIMBO_COLOR), ('keno_evo', KENO_COLOR), ('mines_evo', MINES_COLOR)]),
            ('research', [('stress_lab', UTILITY_COLOR), ('survival_lab', UTILITY_COLOR)]),
            ('analytics', [('keno_mc', KENO_COLOR), ('mines', MINES_COLOR), ('bj', UTILITY_COLOR)]),
            ('sports', [('sports_lab', SPORTS_COLOR), ('sports_kelly', SPORTS_COLOR), ('sports_parlay', SPORTS_COLOR), ('sports_value', SPORTS_COLOR), ('sports_arb', SPORTS_COLOR)]),
            ('utilities', [('compound', UTILITY_COLOR), ('pattern', UTILITY_COLOR), ('converter', UTILITY_COLOR)]),
        ]

        section_tile_heights = {
            'research': dp(44),
            'analytics': dp(42),
            'utilities': dp(44),
        }

        for section_key, items in self.section_configs:
            header = self.make_section_header(section_key)
            body.add_widget(header)
            cols = 5 if len(items) >= 5 else len(items)
            rows = math.ceil(len(items) / cols)
            tile_h = section_tile_heights.get(section_key, dp(50))
            grid = GridLayout(cols=cols, spacing=dp(6), size_hint_y=None,
                              height=max(tile_h, rows * tile_h + (rows - 1) * dp(6)))
            for sid, color in items:
                tile = self.make_tile(
                    MENU_TILE_LABELS.get(sid, TOOL_TITLES.get(sid, sid)),
                    sid,
                    color,
                    compact=True,
                    height_override=tile_h,
                    font_size_override='11sp' if section_key == 'analytics' else None
                )
                self.tile_buttons[sid] = tile
                self.tile_defs[sid] = {'color': color, 'tall': False, 'compact': True}
                grid.add_widget(tile)
            while len(grid.children) < rows * cols:
                grid.add_widget(Widget())
            body.add_widget(grid)

        scroll.add_widget(body)
        outer.add_widget(scroll)
        outer.add_widget(self.presentation_row)

        license_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        license_btn = StyledButton(text='LICENSE / UPGRADE', bg_color=STAKE_GREEN, height=dp(40))
        license_btn.bind(on_release=lambda *a: App.get_running_app().show_license_popup())
        license_row.add_widget(license_btn)
        outer.add_widget(license_row)

        action_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        about_btn = StyledButton(text='ABOUT', bg_color=UTILITY_COLOR, size_hint_x=0.22, height=dp(40))
        about_btn.color = (1, 1, 1, 1)
        about_btn.bind(on_release=self.show_about)
        history_btn = StyledButton(text='SESSION\n LOG', bg_color=UTILITY_COLOR, size_hint_x=0.22, height=dp(40))
        history_btn.color = (1, 1, 1, 1)
        history_btn.bind(on_release=self.show_history)
        profile_btn = StyledButton(text='PROFILE', bg_color=UTILITY_COLOR, size_hint_x=0.22, height=dp(40))
        profile_btn.color = (1, 1, 1, 1)
        profile_btn.bind(on_release=self.show_profile_menu)
        reset_tracker_btn = StyledButton(text='RESET', bg_color=UTILITY_COLOR, size_hint_x=0.16, height=dp(40))
        reset_tracker_btn.color = (1, 1, 1, 1)
        reset_tracker_btn.bind(on_release=self.reset_tracker)
        exit_btn = StyledButton(text='EXIT', bg_color=SOFT_RED, size_hint_x=0.18, height=dp(40))
        exit_btn.bind(on_release=lambda *args: sys.exit())
        action_row.add_widget(about_btn)
        action_row.add_widget(history_btn)
        action_row.add_widget(profile_btn)
        action_row.add_widget(reset_tracker_btn)
        action_row.add_widget(exit_btn)
        outer.add_widget(action_row)

        self.add_widget(outer)
        Clock.schedule_once(lambda dt: self.refresh_presentation_mode_ui(), 0)

    def make_section_header(self, section_key):
        box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(22), spacing=dp(3), padding=[0, dp(2), 0, 0])
        title_text = MENU_SECTION_LABELS.get(section_key, str(section_key).upper())
        lbl = Label(text=title_text, color=get_color_from_hex(STAKE_TEXT), font_size='12sp', bold=True, size_hint_y=None, height=dp(14))
        divider = Widget(size_hint_y=None, height=dp(1))
        with divider.canvas.before:
            divider._bg_color = Color(rgba=get_color_from_hex(DIVIDER_COLOR))
            divider._bg_rect = Rectangle(pos=divider.pos, size=divider.size)
        def _update_divider(instance, value):
            divider._bg_rect.pos = instance.pos
            divider._bg_rect.size = instance.size
        divider.bind(pos=_update_divider, size=_update_divider)
        box.add_widget(lbl)
        box.add_widget(divider)
        self.section_header_labels[section_key] = lbl
        self.section_header_dividers[section_key] = divider
        return box

    def make_tile(self, title_text, sid, color, tall=False, compact=False, height_override=None, font_size_override=None):
        tile_h = height_override if height_override is not None else (dp(54) if tall else (dp(50) if compact else dp(56)))
        font_size = font_size_override if font_size_override is not None else ('13sp' if tall else '12sp')
        tile = Button(text=title_text, background_normal='', background_down='', background_color=(0, 0, 0, 0), color=(0, 0, 0, 1), bold=True, font_size=font_size, halign='center', valign='middle', size_hint_y=None, height=tile_h)
        tile._default_accent_hex = color
        tile._is_tall = tall
        tile._is_compact = compact
        with tile.canvas.before:
            tile._bg_color = Color(1, 1, 1, 1)
            tile._bg_rect = RoundedRectangle(pos=tile.pos, size=tile.size, radius=[dp(12)])
            tile._accent_color = Color(rgba=get_color_from_hex(color))
            tile._accent_rect = Rectangle(pos=(tile.x, tile.top - dp(4)), size=(tile.width, dp(4)))
            Color(0, 0, 0, 0.10)
            tile._shadow = Line(rounded_rectangle=(tile.x, tile.y, tile.width, tile.height, dp(12)), width=1.0)
        def _update_tile(instance, value):
            instance._bg_rect.pos = instance.pos
            instance._bg_rect.size = instance.size
            instance._accent_rect.pos = (instance.x, instance.top - dp(4))
            instance._accent_rect.size = (instance.width, dp(4))
            instance._shadow.rounded_rectangle = (instance.x, instance.y, instance.width, instance.height, dp(12))
            instance.text_size = (instance.width - dp(8), None)
        tile.bind(pos=_update_tile, size=_update_tile)
        tile.bind(on_release=lambda x, s=sid: App.get_running_app().open_feature(s))
        return tile

    def get_menu_tile_text(self, sid):
        return PRESENTATION_MENU_TILE_LABELS.get(sid, PRESENTATION_TOOL_TITLES.get(sid, sid))

    def refresh_presentation_mode_ui(self):
        app = App.get_running_app()
        active = True
        available = False

        self.presentation_row.height = dp(0)
        self.presentation_row.opacity = 0
        self.presentation_toggle_btn.disabled = True
        self.presentation_toggle_btn.text = ''

        self.title_lbl.text = f"{get_display_app_name()}  [size=18]v{APP_VERSION_LABEL}[/size]"
        self.subtitle_lbl.text = get_display_subtitle()
        self.title_lbl.color = get_color_from_hex(PRESENTATION_ACCENT if active else STAKE_GREEN)
        self.subtitle_lbl.color = get_color_from_hex(PRESENTATION_SECTION_TEXT if active else SUBTITLE_TEXT)
        self.bank_lbl.color = get_color_from_hex(PRESENTATION_ACCENT if active else STAKE_GREEN)
        self.demo_lbl.color = get_color_from_hex(PRESENTATION_SECTION_TEXT if active else STAKE_TEXT)
        self.p_in.hint_text = 'Enter Result (+/-)'

        self.mode_badge_lbl.height = dp(0)
        self.mode_badge_lbl.text = ''

        self.hero._bg_color.rgba = get_color_from_hex(PRESENTATION_PANEL if active else STAKE_INPUT)
        self.hero._strip_left_color.rgba = get_color_from_hex(PRESENTATION_ACCENT_ALT if active else DICE_COLOR)
        self.hero._strip_mid_color.rgba = get_color_from_hex(PRESENTATION_ACCENT if active else KENO_COLOR)
        self.hero._strip_right_color.rgba = get_color_from_hex('#2d5d89' if active else SPORTS_COLOR)

        for section_key, lbl in self.section_header_labels.items():
            title_map = PRESENTATION_SECTION_LABELS if active else MENU_SECTION_LABELS
            lbl.text = title_map.get(section_key, lbl.text)
            lbl.color = get_color_from_hex(PRESENTATION_SECTION_TEXT if active else STAKE_TEXT)
            divider = self.section_header_dividers.get(section_key)
            if divider and hasattr(divider, '_bg_color'):
                divider._bg_color.rgba = get_color_from_hex(PRESENTATION_ACCENT_ALT if active else DIVIDER_COLOR)

        for sid, tile in self.tile_buttons.items():
            tile.text = self.get_menu_tile_text(sid)
            if active:
                tile.font_size = '12sp' if tile._is_tall else '11sp'
            else:
                tile.font_size = '13sp' if tile._is_tall else '12sp'
            tile.color = (0.02, 0.06, 0.12, 1) if active else (0, 0, 0, 1)
            tile._bg_color.rgba = get_color_from_hex('#eef6ff' if active else '#ffffff')
            tile._accent_color.rgba = get_color_from_hex(PRESENTATION_ACCENT_ALT if active else tile._default_accent_hex)

        self.update_header(0)

    def toggle_presentation_mode(self, *args):
        app = App.get_running_app()
        if not app or app.get_tier() != PRO_PLUS:
            return
        app.set_presentation_mode(not app.presentation_mode_enabled)

    def show_about(self, *args):
        popup_title = 'About Strategy Suite Pro'
        msg = (
            'Strategy Suite Pro is a professional risk modeling and simulation toolkit built for structured analysis, '
            'variance review, probability research, and scenario testing.\n\n'
            'Important Disclaimer\n'
            '• This software is for simulation, educational review, and analytical use only.\n'
            '• It does not guarantee income or provide financial advice.\n'
            '• All outputs shown by the app are mathematical simulations, estimates, or modeled scenarios.\n'
            '• Users remain fully responsible for how they interpret and apply any analysis.\n\n'
            'Created by SH Vertex Technologies'
        )
        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        scroll = ScrollView()
        body = Label(
            text=msg,
            color=get_color_from_hex(STAKE_TEXT),
            halign='left',
            valign='top',
            size_hint_y=None,
            font_size='13sp',
        )

        def _refresh_about(*_args):
            width = max(dp(220), scroll.width - dp(20))
            body.text_size = (width, None)
            body.texture_update()
            body.height = max(dp(220), body.texture_size[1] + dp(16))

        scroll.bind(size=lambda *_: _refresh_about())
        body.bind(texture_size=lambda *_: _refresh_about())
        Clock.schedule_once(lambda dt: _refresh_about(), 0)
        scroll.add_widget(body)

        close_btn = StyledButton(text='CLOSE', bg_color=STAKE_GREEN, height=dp(38))
        popup = Popup(title=popup_title, content=content, size_hint=(0.90, 0.72))
        close_btn.bind(on_release=lambda *a: popup.dismiss())
        content.add_widget(scroll)
        content.add_widget(close_btn)
        popup.open()

    def show_profile_menu(self, *args):
        p = load_risk_profile()
        content = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))

        if p and p.get('completed') and not p.get('skipped'):
            bankroll = p.get('bankroll', '')
            risk = p.get('risk', '')
            game = p.get('game', '')
            created = p.get('created_at', '')
            risk_colors = {'Conservative': STAKE_GREEN, 'Balanced': DICE_COLOR,
                           'Aggressive': MINES_COLOR, 'Degen': STAKE_RED}
            rc = risk_colors.get(risk, STAKE_GREEN)

            profile_lbl = Label(
                text=f"Capital:   {bankroll}\nRisk:          {risk}\nModel:      {clean_display_label(game)}",
                color=get_color_from_hex(STAKE_TEXT), font_size='14sp',
                size_hint_y=None, height=dp(72), halign='center', valign='middle',
            )
            profile_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
            content.add_widget(profile_lbl)

            badge_lbl = Label(
                text=get_profile_badge_text(),
                color=get_color_from_hex(rc), font_size='12sp', bold=True,
                size_hint_y=None, height=dp(26), halign='center', valign='middle',
            )
            badge_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
            content.add_widget(badge_lbl)

            if created:
                content.add_widget(Label(
                    text=f"Created: {created}",
                    color=get_color_from_hex(SUBTITLE_TEXT), font_size='10sp',
                    size_hint_y=None, height=dp(20), halign='center',
                ))
        else:
            content.add_widget(Label(
                text="No profile set yet.",
                color=get_color_from_hex(STAKE_TEXT), font_size='13sp',
                size_hint_y=None, height=dp(40), halign='center',
            ))

        btn_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        redo_btn = StyledButton(text='REDO\n PROFILE', bg_color=DICE_COLOR)
        redo_btn.color = (1, 1, 1, 1)
        reset_btn = StyledButton(text='CLEAR\n PROFILE', bg_color=SOFT_RED)
        close_btn = StyledButton(text='CLOSE', bg_color=UTILITY_COLOR)
        close_btn.color = (1, 1, 1, 1)

        popup = Popup(title='Risk Profile', content=content,
                      size_hint=(0.88, 0.58),
                      separator_color=get_color_from_hex(DICE_COLOR))

        def do_redo(*a):
            popup.dismiss()
            clear_risk_profile()
            Clock.schedule_once(lambda dt: show_onboarding_wizard(
                on_complete=lambda: self.update_header(0)
            ), 0.2)

        def do_clear(*a):
            popup.dismiss()
            clear_risk_profile()
            self.update_header(0)

        redo_btn.bind(on_release=do_redo)
        reset_btn.bind(on_release=do_clear)
        close_btn.bind(on_release=lambda *a: popup.dismiss())
        btn_row.add_widget(redo_btn)
        btn_row.add_widget(reset_btn)
        btn_row.add_widget(close_btn)
        content.add_widget(btn_row)
        popup.open()

    def show_history(self, *args):
        entries = load_session_history()
        unit = get_display_unit_prefix()
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))

        total = sum(e.get('amount', 0) for e in entries)
        wins = [e for e in entries if e.get('amount', 0) > 0]
        losses = [e for e in entries if e.get('amount', 0) < 0]
        summary_color = STAKE_GREEN if total >= 0 else STAKE_RED
        summary = Label(
            text=f"Net Units: {unit}{total:.2f}  |  Updates: {len(entries)}  |  Positive: {len(wins)}  Negative: {len(losses)}",
            color=get_color_from_hex(summary_color),
            font_size='13sp',
            bold=True,
            size_hint_y=None,
            height=dp(28),
            halign='center',
            valign='middle',
        )
        summary.bind(size=lambda inst, val: setattr(inst, 'text_size', val))
        content.add_widget(summary)

        scroll = ScrollView()
        entry_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
        entry_list.bind(minimum_height=entry_list.setter('height'))

        if not entries:
            entry_list.add_widget(Label(
                text="No session entries yet.\nUse the UPDATE button on the main screen to log result entries.",
                color=get_color_from_hex(STAKE_TEXT),
                halign='center',
                valign='middle',
                size_hint_y=None,
                height=dp(80),
            ))
        else:
            for e in reversed(entries):
                amount = e.get('amount', 0)
                ts = e.get('timestamp', '')
                color = STAKE_GREEN if amount >= 0 else STAKE_RED
                sign = '+' if amount >= 0 else ''
                row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
                row.add_widget(Label(
                    text=ts,
                    color=get_color_from_hex(STAKE_TEXT),
                    font_size='11sp',
                    size_hint_x=0.55,
                ))
                row.add_widget(Label(
                    text=f"{unit}{sign}{amount:.2f}",
                    color=get_color_from_hex(color),
                    font_size='12sp',
                    bold=True,
                    size_hint_x=0.25,
                ))
                entry_list.add_widget(row)

        scroll.add_widget(entry_list)
        content.add_widget(scroll)

        close_btn = StyledButton(text='CLOSE', bg_color=STAKE_GREEN, size_hint_y=None, height=dp(42))
        content.add_widget(close_btn)

        popup = Popup(
            title='Session Log',
            content=content,
            size_hint=(0.94, 0.82),
            separator_color=get_color_from_hex(STAKE_GREEN),
        )
        close_btn.bind(on_release=lambda *a: popup.dismiss())
        popup.open()

    def update_profit(self, *args):
        try:
            amount = float(self.p_in.text)
            GLOBAL_BANK.session_profit += amount
            GLOBAL_BANK.save_tracker_state()
            log_history_entry(amount)
            self.p_in.text = ""
            self.update_header(0)
        except Exception:
            pass

    def reset_tracker(self, *args):
        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        content.add_widget(Label(text='Reset total net units and elapsed session tracker?', color=get_color_from_hex(STAKE_TEXT), size_hint_y=None, height=dp(40)))
        row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        yes_btn = StyledButton(text='RESET', bg_color=SOFT_RED)
        no_btn = StyledButton(text='CANCEL', bg_color=UTILITY_COLOR)
        no_btn.color = (1, 1, 1, 1)
        row.add_widget(yes_btn)
        row.add_widget(no_btn)
        content.add_widget(row)
        popup = Popup(title='Reset Tracker', content=content, size_hint=(0.82, 0.28))
        def do_reset(*args):
            GLOBAL_BANK.reset_tracker_state()
            clear_session_history()
            self.update_header(0)
            popup.dismiss()
        yes_btn.bind(on_release=do_reset)
        no_btn.bind(on_release=lambda *a: popup.dismiss())
        popup.open()

    def update_header(self, dt):
        unit = get_display_unit_prefix()
        label = 'UNITS'
        self.bank_lbl.text = f"{label}: {unit}{GLOBAL_BANK.session_profit:.2f} | SESSION: {GLOBAL_BANK.get_duration()}"
        try:
            self.demo_lbl.text = App.get_running_app().get_demo_status_line()
        except Exception:
            self.demo_lbl.text = ''
        self.profile_lbl.text = get_profile_badge_text()


def _wrap_demo_method(cls, method_name, usage_key, title, amount=1):
    original = getattr(cls, method_name)
    @wraps(original)
    def demo_guard(self, *args, **kwargs):
        app = App.get_running_app()
        if app and app.get_tier() == DEMO:
            if not DEMO_USAGE.can_use(usage_key, amount):
                show_upgrade_popup(title, PRO, 'Demo limit reached.')
                return
            DEMO_USAGE.consume(usage_key, amount)
        return original(self, *args, **kwargs)
    demo_guard.__name__ = method_name
    demo_guard.__qualname__ = f"{cls.__name__}.{method_name}"
    setattr(cls, method_name, demo_guard)

def _wrap_dice_sim_execute_roll():
    original = DiceSimScreen.execute_roll
    @wraps(original)
    def demo_guard(self, *args, **kwargs):
        app = App.get_running_app()
        if app and app.get_tier() == DEMO:
            if DEMO_USAGE.remaining('dice_sim_rolls') <= 0:
                self.is_auto_running = False
                try:
                    self.auto_btn.text = 'START AUTO'
                except Exception:
                    pass
                show_upgrade_popup('RNG Variance Engine', PRO, 'Demo roll limit reached.')
                return 'stop'
            DEMO_USAGE.consume('dice_sim_rolls', 1)
        return original(self, *args, **kwargs)
    demo_guard.__name__ = 'execute_roll'
    demo_guard.__qualname__ = f"{DiceSimScreen.__name__}.execute_roll"
    DiceSimScreen.execute_roll = demo_guard

_wrap_dice_sim_execute_roll()
_wrap_demo_method(DiceScreen, 'calculate', 'dice', 'Threshold Multiplier')
_wrap_demo_method(MonteCarloScreen, 'run_monte_carlo', 'mc', 'Monte Carlo Simulator')
_wrap_demo_method(StrategyStressTestScreen, 'start_test', 'stress_lab', 'Strategy Stress Test')
_wrap_demo_method(MinesScreen, 'calc', 'mines', 'Grid-Risk Analyst')
_wrap_demo_method(SportsKellyScreen, 'calculate', 'sports_kelly', 'Kelly Criterion Tool')
_wrap_demo_method(SportsParlayScreen, 'calculate', 'sports_parlay', 'Compounded Risk Analyst')
_wrap_demo_method(SportsValueBetScreen, 'calculate', 'sports_value', 'Edge Discovery Tool')
_wrap_demo_method(SportsArbitrageScreen, 'calculate', 'sports_arb', 'Market Convergence Calc')
_wrap_demo_method(CompoundScreen, 'calc', 'compound', 'Compound Growth Pro')
_wrap_demo_method(PatternScreen, 'generate', 'pattern', 'Pattern Sequence Master')

_original_bj_analyze = BlackjackScreen.analyze
@wraps(_original_bj_analyze)
def _bj_demo_guard(self, p, soft, d):
    app = App.get_running_app()
    if app and app.get_tier() == DEMO:
        if DEMO_USAGE.remaining('bj') <= 0:
            show_upgrade_popup('Statistical Deck Engine', PRO, 'Demo limit reached.')
            return 'UPGRADE'
        DEMO_USAGE.consume('bj', 1)
    return _original_bj_analyze(self, p, soft, d)
_bj_demo_guard.__name__ = 'analyze'
_bj_demo_guard.__qualname__ = f"{BlackjackScreen.__name__}.analyze"
BlackjackScreen.analyze = _bj_demo_guard

class CasinoApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.presentation_mode_enabled = True

    def get_tier(self):
        return LICENSE_STATE.effective_tier()

    def run_revocation_check(self, force=True, on_complete=None):
        if not LICENSE_STATE.license_id or not REVOCATION_URL or get_public_key() is None:
            if on_complete:
                _ui_call(on_complete, False, 'No activated license to check')
            return
        if not force and not LICENSE_STATE.needs_revocation_check():
            if on_complete:
                _ui_call(on_complete, True, 'Recent revocation check already completed')
            return

        def worker():
            ok = False
            message = 'License status check failed'
            try:
                resp = requests.get(REVOCATION_URL, timeout=12, verify=certifi.where())
                resp.raise_for_status()
                data = resp.json()
                ok, state = LICENSE_STATE.apply_revocation_bundle(data)
                if ok and state == 'revoked':
                    message = 'License revoked'
                    _ui_call(show_revoked_popup)
                elif ok:
                    message = LICENSE_STATE.revoked_or_expired_message() or 'License active'
                else:
                    message = 'Invalid revocation bundle'
            except Exception as e:
                LICENSE_STATE.last_revocation_check = time.time()
                LICENSE_STATE.last_revocation_error = str(e)
                LICENSE_STATE.save()
                message = f'Check failed: {e}'
            _ui_call(self.refresh_status_labels)
            if on_complete:
                _ui_call(on_complete, ok, message)

        threading.Thread(target=worker, daemon=True).start()

    def maybe_check_revocations(self):
        self.run_revocation_check(force=False)

    def on_start(self):
        self.run_revocation_check(force=True)
        # Show onboarding wizard on first launch only
        if load_risk_profile() is None:
            Clock.schedule_once(lambda dt: show_onboarding_wizard(
                on_complete=lambda: self.refresh_status_labels()
            ), 0.8)

    def refresh_status_labels(self):
        try:
            menu = self.root.get_screen('menu')
            menu.refresh_presentation_mode_ui()
            menu.update_header(0)
        except Exception:
            pass

    def get_demo_status_line(self):
        tier = self.get_tier()
        if tier == PRO:
            return f"PRO ACTIVE{'  |  ' + LICENSE_STATE.license_id if LICENSE_STATE.license_id else ''}"
        if tier == PRO_PLUS:
            return f"PRO+ ACTIVE{'  |  ' + LICENSE_STATE.license_id if LICENSE_STATE.license_id else ''}"
        msg = LICENSE_STATE.revoked_or_expired_message()
        if msg:
            msg = f"  |  {msg}"
        return (
            f"DEMO  |  RNG {DEMO_USAGE.remaining('dice_sim_rolls')}  |  Threshold {DEMO_USAGE.remaining('dice')}  |  "
            f"MC {DEMO_USAGE.remaining('mc')}  |  Deck {DEMO_USAGE.remaining('bj')}  |  Saves {DEMO_USAGE.remaining('strats_save')}{msg}"
        )


    def is_presentation_mode_active(self):
        return True

    def set_presentation_mode(self, enabled):
        self.presentation_mode_enabled = True
        save_presentation_mode_state(True)
        try:
            for screen in getattr(self.root, 'screens', []):
                refresh_dynamic_presentation_titles(screen)
        except Exception:
            pass
        self.refresh_status_labels()

    def open_support_whatsapp(self):
        device = get_device_code()
        msg = quote(f"Hello, I want {get_display_app_name()}. Device Code: {device}. Please send payment instructions for Pro / Pro+.")
        try:
            webbrowser.open(f"{SUPPORT_WHATSAPP_LINK}?text={msg}")
            return True
        except Exception:
            return False

    def share_device_code_to_whatsapp(self):
        try:
            device = quote(get_device_code())
            webbrowser.open(f"{SUPPORT_WHATSAPP_LINK}?text={device}")
            return True
        except Exception:
            return False

    def open_support_email(self):
        device = get_device_code()
        subject = quote(f"{get_display_app_name()} Activation Request")
        body = quote(f"Hello,\n\nI would like to purchase {get_display_app_name()}.\n\nDevice Code: {device}\nPlan: Pro / Pro+\n\nPlease send payment instructions.\n")
        try:
            webbrowser.open(f"mailto:{SUPPORT_EMAIL_ADDRESS}?subject={subject}&body={body}")
            return True
        except Exception:
            return False

    def show_license_popup(self):
        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
        tier_text = 'DEMO' if self.get_tier() == DEMO else ('PRO' if self.get_tier() == PRO else 'PRO+')
        details = [f"Current Tier: {tier_text}", f"Device Code:\n{get_device_code()}"]
        if LICENSE_STATE.license_id:
            details.append(f"License ID: {LICENSE_STATE.license_id}")
        if LICENSE_STATE.source:
            details.append(f"Source: {LICENSE_STATE.source}")
        if LICENSE_STATE.expires_at:
            details.append(f"Expiry: {LICENSE_STATE.expires_at}")
        msg = LICENSE_STATE.revoked_or_expired_message()
        if msg:
            details.append(msg)

        info = Label(
            text='\n'.join(details),
            color=get_color_from_hex(STAKE_TEXT),
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(128)
        )
        info.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        pricing = Label(
            text=f"Pro: {PRO_PRICE_TEXT}   |   Pro+: {PRO_PLUS_PRICE_TEXT}\nCopy your Device Code, contact support, complete payment, then paste your activation code below.",
            color=get_color_from_hex(SUBTITLE_TEXT),
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(56)
        )
        pricing.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        contact = Label(
            text=f"WhatsApp: {SUPPORT_WHATSAPP_NUMBER}\nEmail: {SUPPORT_EMAIL_ADDRESS}",
            color=get_color_from_hex(STAKE_TEXT),
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(46)
        )
        contact.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        key_input = StyledInput(hint_text='Paste activation key here')

        status = Label(
            text='',
            color=get_color_from_hex(STAKE_GREEN),
            size_hint_y=None,
            height=dp(42),
            halign='center',
            valign='middle'
        )
        status.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

        row1 = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        activate_btn = StyledButton(text='ACTIVATE', bg_color=STAKE_GREEN)
        row1.add_widget(activate_btn)

        row_paste = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        paste_license_btn = StyledButton(text='PASTE LICENSE', bg_color='#2980b9')
        paste_license_btn.color = (1, 1, 1, 1)
        row_paste.add_widget(paste_license_btn)

        row2 = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        check_btn = StyledButton(text='CHECK LICENSE\nSTATUS', bg_color=UTILITY_COLOR)
        check_btn.color = (1, 1, 1, 1)
        clear_btn = StyledButton(text='CLEAR LICENSE', bg_color=SOFT_RED)
        row2.add_widget(check_btn)
        row2.add_widget(clear_btn)

        row3 = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        copy_btn = StyledButton(text='COPY DEVICE\nCODE', bg_color=UTILITY_COLOR)
        copy_btn.color = (1, 1, 1, 1)
        share_code_btn = StyledButton(text='SHARE DEVICE\nCODE', bg_color=UTILITY_COLOR)
        share_code_btn.color = (1, 1, 1, 1)
        row3.add_widget(copy_btn)
        row3.add_widget(share_code_btn)

        row4 = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        wa_btn = StyledButton(text='WHATSAPP', bg_color=UTILITY_COLOR)
        wa_btn.color = (1, 1, 1, 1)
        email_btn = StyledButton(text='EMAIL', bg_color=UTILITY_COLOR)
        email_btn.color = (1, 1, 1, 1)
        row4.add_widget(wa_btn)
        row4.add_widget(email_btn)

        row5 = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        close_btn = StyledButton(text='CLOSE', bg_color=UTILITY_COLOR)
        close_btn.color = (1, 1, 1, 1)
        row5.add_widget(close_btn)

        content.add_widget(info)
        content.add_widget(pricing)
        content.add_widget(contact)
        content.add_widget(key_input)
        content.add_widget(status)
        content.add_widget(row1)
        content.add_widget(row_paste)
        content.add_widget(row2)
        content.add_widget(row3)
        content.add_widget(row4)
        content.add_widget(row5)

        popup = Popup(title='License Center', content=content, size_hint=(0.94, 0.78))

        def do_activate(*args):
            ok, tier, message = LICENSE_STATE.activate(key_input.text)
            status.color = get_color_from_hex(STAKE_GREEN if ok else STAKE_RED)
            status.text = message
            if ok:
                self.refresh_status_labels()
                Clock.schedule_once(lambda dt: popup.dismiss(), 0.8)

        def do_clear(*args):
            LICENSE_STATE.clear()
            self.refresh_status_labels()
            status.color = get_color_from_hex(STAKE_TEXT)
            status.text = 'License cleared. Demo mode active.'

        def do_copy(*args):
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(get_device_code())
                status.color = get_color_from_hex(STAKE_GREEN)
                status.text = 'Device code copied'
            except Exception:
                status.color = get_color_from_hex(STAKE_RED)
                status.text = 'Clipboard copy failed'

        def do_paste_license(*args):
            try:
                from kivy.core.clipboard import Clipboard
                pasted = str(Clipboard.paste() or '').strip()
                if pasted:
                    key_input.text = pasted
                    status.color = get_color_from_hex(STAKE_GREEN)
                    status.text = 'License pasted from clipboard'
                else:
                    status.color = get_color_from_hex(STAKE_RED)
                    status.text = 'Clipboard is empty'
            except Exception:
                status.color = get_color_from_hex(STAKE_RED)
                status.text = 'Clipboard paste failed'

        def do_share_device_code(*args):
            if self.share_device_code_to_whatsapp():
                status.color = get_color_from_hex(STAKE_GREEN)
                status.text = 'Sharing device code via WhatsApp...'
            else:
                status.color = get_color_from_hex(STAKE_RED)
                status.text = 'Could not share device code'

        def do_whatsapp(*args):
            if self.open_support_whatsapp():
                status.color = get_color_from_hex(STAKE_GREEN)
                status.text = 'Opening WhatsApp...'
            else:
                status.color = get_color_from_hex(STAKE_RED)
                status.text = 'Could not open WhatsApp'

        def do_email(*args):
            if self.open_support_email():
                status.color = get_color_from_hex(STAKE_GREEN)
                status.text = 'Opening email app...'
            else:
                status.color = get_color_from_hex(STAKE_RED)
                status.text = 'Could not open email app'

        def do_check(*args):
            status.color = get_color_from_hex(STAKE_TEXT)
            status.text = 'Checking license status...'

            def after_check(ok, message):
                lowered = str(message).lower()
                if 'revoked' in lowered or 'failed' in lowered or 'invalid' in lowered or 'no activated license' in lowered:
                    status.color = get_color_from_hex(STAKE_RED if 'active' not in lowered else STAKE_GREEN)
                else:
                    status.color = get_color_from_hex(STAKE_GREEN)
                status.text = message

            self.run_revocation_check(force=True, on_complete=after_check)

        activate_btn.bind(on_release=do_activate)
        paste_license_btn.bind(on_release=do_paste_license)
        check_btn.bind(on_release=do_check)
        clear_btn.bind(on_release=do_clear)
        copy_btn.bind(on_release=do_copy)
        share_code_btn.bind(on_release=do_share_device_code)
        wa_btn.bind(on_release=do_whatsapp)
        email_btn.bind(on_release=do_email)
        close_btn.bind(on_release=lambda *a: popup.dismiss())

        popup.open()

    def open_feature(self, sid):
        sid = str(sid)
        required = FEATURE_TIERS.get(sid, DEMO)
        title = get_tool_display_title(sid)
        tier = self.get_tier()

        if required == PRO_PLUS and tier != PRO_PLUS:
            show_upgrade_popup(title, PRO_PLUS, 'This is a Pro+ feature.')
            return

        usage_key = None
        if sid == 'dice_sim':
            usage_key = 'dice_sim_rolls'
        elif sid in DEMO_LIMITS:
            usage_key = sid

        if tier == DEMO and usage_key and DEMO_USAGE.remaining(usage_key) <= 0:
            show_upgrade_popup(title, PRO, 'Demo limit reached.')
            return

        if sid in self.root.screen_names:
            try:
                refresh_dynamic_presentation_titles(self.root.get_screen(sid))
            except Exception:
                pass
            self.root.current = sid
        else:
            show_upgrade_popup(title, required, 'Preview mode only.')

    def build(self):
        sm = ScreenManager(transition=FadeTransition())

        screens = [
            (MainMenu, 'menu'),
            (StrategyLibraryScreen, 'strats'),
            (DiceScreen, 'dice'),
            (MonteCarloScreen, 'mc'),
            (KenoMonteCarloScreen, 'keno_mc'),
            (DiceOptimizerScreen, 'dice_opt'),
            (DiceAutoGeneratorScreen, 'dice_gen'),
            (DiceEvolutionScreen, 'dice_evo'),
            (LimboEvolutionScreen, 'limbo_evo'),
            (KenoEvolutionScreen, 'keno_evo'),
            (MinesEvolutionScreen, 'mines_evo'),
            (MinesScreen, 'mines'),
            (CompoundScreen, 'compound'),
            (PatternScreen, 'pattern'),
            (ConverterScreen, 'converter'),
            (BlackjackScreen, 'bj'),
            (SportsLabScreen, 'sports_lab'),
            (SportsKellyScreen, 'sports_kelly'),
            (SportsParlayScreen, 'sports_parlay'),
            (SportsValueBetScreen, 'sports_value'),
            (SportsArbitrageScreen, 'sports_arb'),
            (StrategyStressTestScreen, 'stress_lab'),
            (BankrollSurvivalScreen, 'survival_lab'),
            (StrategyForgeScreen, 'forge'),
            (DiceSimScreen, 'dice_sim')
        ]

        for cls, name in screens:
            sm.add_widget(cls(name=name))

        Clock.schedule_once(lambda dt: self.refresh_status_labels(), 0)
        return sm


if __name__ == '__main__':
    CasinoApp().run()
