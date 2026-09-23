import re
import json
#!/usr/bin/env python3

import os
import sys
import time
import subprocess
import getpass
import requests
from pathlib import Path

from sva_engine.ai_client import SVAAIClient
from sva_engine.planner import AIPlanner
from sva_engine.task_store import TaskStore
from sva_engine.controller import SVAController
from sva_engine.action_executor import ActionExecutor
from sva_engine.agent import PersistentAgent
from sva_engine.background_tasks import BackgroundTaskManager

background_manager = BackgroundTaskManager()


# ============================================================
# SVA MATRIX SQUAD
# AI Command-Line Assistant for Termux & Linux
# Code by SVA Matrix Squad • SVA Matrix Squad
# ============================================================

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"

YOUTUBE_URL = "https://www.youtube.com/@TechKhojHQ"


# ============================================================
# APPLY AI FIX ENGINE
# ============================================================

def apply_ai_fix(project_path, patch_data):
    """Safely apply exact AI-generated file patches."""
    project = Path(project_path).expanduser().resolve()

    if not project.is_dir():
        return {
            "success": False,
            "error": f"Project directory does not exist: {project}",
        }

    if not isinstance(patch_data, dict):
        return {
            "success": False,
            "error": "Invalid patch data.",
        }

    patches = patch_data.get("files")

    if not isinstance(patches, list) or not patches:
        return {
            "success": False,
            "error": "No safe file patches were provided by AI.",
        }

    prepared = []

    for patch in patches:
        if not isinstance(patch, dict):
            return {
                "success": False,
                "error": "Invalid patch entry.",
            }

        relative_path = patch.get("path")
        old_text = patch.get("old")
        new_text = patch.get("new")

        if not all(
            isinstance(value, str)
            for value in (relative_path, old_text, new_text)
        ):
            return {
                "success": False,
                "error": "Patch requires path, old and new text.",
            }

        target = (project / relative_path).resolve()

        try:
            target.relative_to(project)
        except ValueError:
            return {
                "success": False,
                "error": f"Blocked path outside project: {relative_path}",
            }

        if not target.is_file():
            return {
                "success": False,
                "error": f"Target file does not exist: {relative_path}",
            }

        content = target.read_text(encoding="utf-8")

        if content.count(old_text) != 1:
            return {
                "success": False,
                "error": (
                    f"Exact old text must occur exactly once in "
                    f"{relative_path}."
                ),
            }

        prepared.append((target, old_text, new_text))

    backups = []

    try:
        for target, _, _ in prepared:
            backup = target.with_name(
                target.name + ".sva-ai-backup"
            )
            backup.write_text(
                target.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            backups.append((target, backup))

        for target, old_text, new_text in prepared:
            content = target.read_text(encoding="utf-8")
            target.write_text(
                content.replace(old_text, new_text, 1),
                encoding="utf-8",
            )

        return {
            "success": True,
            "files_changed": [
                str(target.relative_to(project))
                for target, _, _ in prepared
            ],
            "backups": [
                str(backup.relative_to(project))
                for _, backup in backups
            ],
        }

    except Exception as error:
        for target, backup in backups:
            try:
                target.write_text(
                    backup.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            except Exception:
                pass

        return {
            "success": False,
            "error": f"AI fix failed and rollback was attempted: {error}",
        }


# ============================================================
# COLORS
# ============================================================

RESET = "\033[0m"
BOLD = "\033[1m"

RED = "\033[1;31m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[1;34m"
MAGENTA = "\033[1;35m"
CYAN = "\033[1;36m"
WHITE = "\033[1;37m"


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = (
    "You are SVA Matrix Squad, a helpful command-line AI assistant. "
    "Give clear, practical and concise answers. "
    "Always use the current date and time provided by the application "
    "when answering questions about today, yesterday, tomorrow, dates, "
    "or current time. Never invent a date. "
    "For cybersecurity questions, focus on legal, authorized, "
    "defensive, and educational use."
)


# ============================================================
# CLEAR SCREEN
# ============================================================

def clear():
    os.system("clear")


# ============================================================
# REAL TERMUX / LINUX COMMAND RUNNER
# ============================================================

READ_ONLY_COMMANDS = {
    "pwd",
    "ls",
    "whoami",
    "id",
    "uname",
    "date",
    "which",
    "whereis",
    "env",
    "printenv",
    "df",
    "free",
    "uptime",
    "ps",
}


def run_real_termux_command(command: str):
    command = command.strip()

    if not command:
        return None

    parts = command.split()

    if parts[0] not in READ_ONLY_COMMANDS:
        return None

    try:
        result = subprocess.run(
            ["bash", "-lc", command],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            timeout=30,
        )

        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "success": result.returncode == 0,
        }

    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "returncode": -1,
            "stdout": "",
            "stderr": "Command timed out.",
            "success": False,
        }

    except Exception as error:
        return {
            "command": command,
            "returncode": -1,
            "stdout": "",
            "stderr": str(error),
            "success": False,
        }


# ============================================================
# SVA MATRIX SQUAD LOGO
# ============================================================

def sva_logo():

    print(f"{CYAN}{BOLD}")

    print("███████╗██╗   ██╗ █████╗ ")
    print("██╔════╝██║   ██║██╔══██╗")
    print("███████╗██║   ██║███████║")
    print("╚════██║╚██╗ ██╔╝██╔══██║")
    print("███████║ ╚████╔╝ ██║  ██║")
    print("╚══════╝  ╚═══╝  ╚═╝  ╚═╝")

    print()

    print(f"{YELLOW}{BOLD}")
    print("          M A T R I X")
    print(f"{RESET}")

    print(
        f"{MAGENTA}{BOLD}"
        "      Code by SVA Matrix Squad"
        f"{RESET}"
    )

    print(
        f"{GREEN}{BOLD}"
        "             [ SVA Matrix Squad ]"
        f"{RESET}"
    )

    print()


# ============================================================
# MAIN BANNER
# ============================================================

def banner():

    print(f"{CYAN}{BOLD}")

    print("╔══════════════════════════════════════════════════════════╗")
    print("║                       SVA MATRIX SQUAD                         ║")
    print("║             AI Command-Line Assistant by SVA Matrix Squad                  ║")
    print("╚══════════════════════════════════════════════════════════╝")

    print(f"{RESET}")


# ============================================================
# OPEN YOUTUBE
# ============================================================

def open_youtube():

    commands = [

        # Termux
        [
            "termux-open-url",
            YOUTUBE_URL
        ],

        # Android
        [
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            YOUTUBE_URL
        ],

        # Linux desktop
        [
            "xdg-open",
            YOUTUBE_URL
        ]

    ]

    for command in commands:

        try:

            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            if result.returncode == 0:
                return True

        except FileNotFoundError:
            continue

        except Exception:
            continue

    return False


# ============================================================
# TOOL LOCK SCREEN
# ============================================================

def startup_screen():

    clear()

    print(f"{RED}{BOLD}")

    print("╔══════════════════════════════════════════════════════════╗")
    print("║                                                          ║")
    print("║                  🔒 TOOL LOCKED 🔒                      ║")
    print("║                                                          ║")
    print("╚══════════════════════════════════════════════════════════╝")

    print(f"{RESET}")
    print()

    print(f"{YELLOW}{BOLD}Hello Mr. Hacker 👋{RESET}")
    print()

    print(f"{WHITE}This tool is locked 🔒{RESET}")
    print()

    print(
        f"{WHITE}"
        "To unlock 🔓 this tool, you will be redirected to our\n"
        "YouTube Channel: SVA Matrix Squad."
        f"{RESET}"
    )

    print()

    print(
        f"{GREEN}{BOLD}"
        "Please Like 👍, Subscribe 🔔 and click on the Bell 🔔 icon."
        f"{RESET}"
    )

    print()

    print(
        f"{WHITE}"
        "Then come back to this terminal and your tool will be\n"
        "unlocked 🔓."
        f"{RESET}"
    )

    print()

    print(f"{CYAN}{BOLD}")
    print("────────────────────────────────────────────────────────────")
    print(f"{RESET}")

    print()
    print(f"{MAGENTA}{BOLD}📺 SVA Matrix Squad{RESET}")
    print()

    print(f"{BLUE}{BOLD}Redirecting to YouTube app in{RESET}")
    print()

    for number in range(8, -1, -1):
        print(
            f"{YELLOW}{BOLD}"
            f"                    {number}"
            f"{RESET}"
        )
        time.sleep(1)

    print()

    print(
        f"{GREEN}{BOLD}"
        "📱 Opening SVA Matrix Squad..."
        f"{RESET}"
    )

    time.sleep(1)

    opened = open_youtube()

    if not opened:
        print()
        print(
            f"{RED}{BOLD}"
            "⚠️ Could not open YouTube automatically."
            f"{RESET}"
        )
        print()
        print(f"{WHITE}Please open this channel manually:{RESET}")
        print()
        print(YOUTUBE_URL)

    print()

    print(
        f"{CYAN}{BOLD}"
        "↩️ Come back here and press ENTER to unlock SVA Matrix Squad..."
        f"{RESET}"
    )

    input()



# ============================================================
# MULTI API KEY MANAGER
# ============================================================


LANGUAGE_FILE = Path.home() / ".sva_matrix_squad_language.json"

LANGUAGES = {
    "1": {
        "name": "Hindi",
        "flag": "🇮🇳",
        "instruction": "Respond in Hindi."
    },
    "2": {
        "name": "English (UK)",
        "flag": "🇬🇧",
        "instruction": "Respond in English (UK)."
    },
    "3": {
        "name": "English (US)",
        "flag": "🇺🇸",
        "instruction": "Respond in English (US)."
    },
    "4": {
        "name": "Hinglish",
        "flag": "🗣️",
        "instruction": "Respond in simple Hinglish using natural Hindi-English mixed language."
    },
}


def load_language():
    import json

    if LANGUAGE_FILE.exists():
        try:
            data = json.loads(LANGUAGE_FILE.read_text())

            if data.get("language") in LANGUAGES:
                return data["language"]

        except Exception:
            pass

    return "1"


def save_language(language):
    import json

    LANGUAGE_FILE.write_text(
        json.dumps({"language": language}, indent=2)
    )
    LANGUAGE_FILE.chmod(0o600)


def get_language_instruction():
    language = load_language()
    return LANGUAGES[language]["instruction"]


def get_language_name():
    language = load_language()
    data = LANGUAGES[language]
    return f'{data["flag"]} {data["name"]}'


def language_menu():
    while True:
        clear()

        current = load_language()
        current_data = LANGUAGES[current]

        print(f"{CYAN}{BOLD}")
        print("╭────────────────────────────────────────────────────────╮")
        print("│                    🌐 LANGUAGE                         │")
        print("╰────────────────────────────────────────────────────────╯")
        print(f"{RESET}")

        print(
            f"{GREEN}Current Language:{RESET} "
            f"{current_data['flag']} {current_data['name']}"
        )
        print()

        for number, data in LANGUAGES.items():
            active = " ⭐ ACTIVE" if number == current else ""
            print(
                f"{GREEN if number == current else BLUE}"
                f"[{number}]{RESET} "
                f"{data['flag']} {data['name']}{GREEN if number == current else ''}"
                f"{active}{RESET}"
            )

        print(f"{RED}[0]{RESET} ↩️ Back")
        print()

        choice = input(
            f"{MAGENTA}{BOLD}Language > {RESET}"
        ).strip()

        if choice == "0":
            break

        if choice in LANGUAGES:
            save_language(choice)

            print()
            print(
                f"{GREEN}✅ Active Language: "
                f"{LANGUAGES[choice]['flag']} "
                f"{LANGUAGES[choice]['name']}{RESET}"
            )
            input("\nPress ENTER...")
            continue

        input(
            f"\n{RED}❌ Invalid option. Press ENTER...{RESET}"
        )


API_KEYS_FILE = Path.home() / ".sva_matrix_squad_api_keys.json"
LEGACY_API_KEY_FILE = Path.home() / ".sva_matrix_squad_api_key"


def load_api_keys():
    import json

    if API_KEYS_FILE.exists():
        try:
            data = json.loads(API_KEYS_FILE.read_text())

            if isinstance(data, dict) and isinstance(data.get("keys"), list):
                data.setdefault("active", 0)
                return data

        except Exception:
            pass

    if LEGACY_API_KEY_FILE.exists():
        try:
            key = LEGACY_API_KEY_FILE.read_text().strip()

            if key:
                data = {
                    "active": 0,
                    "keys": [
                        {
                            "name": "API 1",
                            "key": key,
                        }
                    ],
                }

                save_api_keys(data)
                return data

        except OSError:
            pass

    return {
        "active": 0,
        "keys": [],
    }


def save_api_keys(data):
    import json

    API_KEYS_FILE.write_text(
        json.dumps(data, indent=2)
    )
    API_KEYS_FILE.chmod(0o600)


def mask_api_key(key):
    if len(key) <= 8:
        return "••••••••"

    return key[:4] + "••••••••••" + key[-4:]


def get_active_api_key():
    data = load_api_keys()
    keys = data.get("keys", [])
    active = data.get("active", 0)

    if not keys:
        return ""

    if not isinstance(active, int) or not 0 <= active < len(keys):
        active = 0
        data["active"] = active
        save_api_keys(data)

    return keys[active].get("key", "")


def api_keys_menu():
    while True:
        clear()

        data = load_api_keys()
        keys = data.get("keys", [])
        active = data.get("active", 0)

        print(f"{CYAN}{BOLD}")
        print("╭────────────────────────────────────────────────────────╮")
        print("│                     🔑 API KEYS                        │")
        print("╰────────────────────────────────────────────────────────╯")
        print(f"{RESET}")

        if keys and 0 <= active < len(keys):
            print(
                f"{GREEN}⭐ Active API: "
                f"{keys[active].get('name', f'API {active + 1}')}"
                f"{RESET}"
            )
        else:
            print(f"{YELLOW}⚠️ No active API key.{RESET}")

        print()

        if keys:
            for i, item in enumerate(keys, 1):
                name = item.get("name", f"API {i}")
                key = item.get("key", "")

                marker = "⭐" if i - 1 == active else " "
                print(
                    f"{marker} [{i}] {name:<10} "
                    f"{mask_api_key(key)}"
                )
        else:
            print(f"{YELLOW}No API keys saved.{RESET}")

        print()
        print("────────────────────────────────────────────────────────")
        print()
        print(f"{GREEN}[A]{RESET} ➕ Add API")
        print(f"{BLUE}[R]{RESET} 🔄 Replace API")
        print(f"{RED}[D]{RESET} 🗑️ Remove API")
        print(f"{YELLOW}[S]{RESET} ⭐ Select Active API")
        print(f"{RED}[0]{RESET} ↩️ Back")
        print()

        choice = input(
            f"{MAGENTA}{BOLD}API Keys > {RESET}"
        ).strip().lower()

        if choice == "0":
            return

        if choice == "a":
            clear()

            print(f"{CYAN}{BOLD}➕ ADD API KEY{RESET}")
            print()

            try:
                key = getpass.getpass(
                    f"{CYAN}OpenRouter API Key > {RESET}"
                ).strip()
            except (KeyboardInterrupt, EOFError):
                print()
                continue

            if not key:
                print(f"{RED}❌ API key cannot be empty.{RESET}")
                input("\nPress ENTER...")
                continue

            data = load_api_keys()
            keys = data.setdefault("keys", [])

            keys.append({
                "name": f"API {len(keys) + 1}",
                "key": key,
            })

            if len(keys) == 1:
                data["active"] = 0

            save_api_keys(data)

            print()
            print(f"{GREEN}✅ API key added successfully.{RESET}")
            input("\nPress ENTER...")
            continue

        if choice == "r":
            if not keys:
                print(f"{YELLOW}⚠️ No API keys to replace.{RESET}")
                input("\nPress ENTER...")
                continue

            clear()
            print(f"{BLUE}{BOLD}🔄 REPLACE API KEY{RESET}")
            print()

            for i, item in enumerate(keys, 1):
                print(
                    f"[{i}] {item.get('name', f'API {i}')} "
                    f"{mask_api_key(item.get('key', ''))}"
                )

            print("[0] ↩️ Back")
            print()

            try:
                selected = int(
                    input(f"{MAGENTA}Replace API > {RESET}").strip()
                )
            except (ValueError, KeyboardInterrupt, EOFError):
                continue

            if selected == 0:
                continue

            if not 1 <= selected <= len(keys):
                continue

            try:
                new_key = getpass.getpass(
                    f"{CYAN}New OpenRouter API Key > {RESET}"
                ).strip()
            except (KeyboardInterrupt, EOFError):
                print()
                continue

            if not new_key:
                print(f"{RED}❌ API key cannot be empty.{RESET}")
                input("\nPress ENTER...")
                continue

            keys[selected - 1]["key"] = new_key
            save_api_keys(data)

            print()
            print(f"{GREEN}✅ API key replaced.{RESET}")
            input("\nPress ENTER...")
            continue

        if choice == "d":
            if not keys:
                print(f"{YELLOW}⚠️ No API keys to remove.{RESET}")
                input("\nPress ENTER...")
                continue

            clear()
            print(f"{RED}{BOLD}🗑️ REMOVE API KEY{RESET}")
            print()

            for i, item in enumerate(keys, 1):
                print(
                    f"[{i}] {item.get('name', f'API {i}')} "
                    f"{mask_api_key(item.get('key', ''))}"
                )

            print("[0] ↩️ Back")
            print()

            try:
                selected = int(
                    input(f"{MAGENTA}Remove API > {RESET}").strip()
                )
            except (ValueError, KeyboardInterrupt, EOFError):
                continue

            if selected == 0:
                continue

            if not 1 <= selected <= len(keys):
                continue

            confirm = input(
                f"{RED}Delete API {selected}? [y/N] > {RESET}"
            ).strip().lower()

            if confirm != "y":
                continue

            keys.pop(selected - 1)

            if not keys:
                data["active"] = 0
            elif data.get("active", 0) >= len(keys):
                data["active"] = len(keys) - 1
            elif selected - 1 < data.get("active", 0):
                data["active"] -= 1

            for i, item in enumerate(keys, 1):
                item["name"] = f"API {i}"

            save_api_keys(data)

            print()
            print(f"{GREEN}✅ API key removed.{RESET}")
            input("\nPress ENTER...")
            continue

        if choice == "s":
            if not keys:
                print(f"{YELLOW}⚠️ No API keys available.{RESET}")
                input("\nPress ENTER...")
                continue

            clear()
            print(f"{YELLOW}{BOLD}⭐ SELECT ACTIVE API{RESET}")
            print()

            for i, item in enumerate(keys, 1):
                marker = "⭐" if i - 1 == data.get("active", 0) else " "
                print(
                    f"{marker} [{i}] "
                    f"{item.get('name', f'API {i}')} "
                    f"{mask_api_key(item.get('key', ''))}"
                )

            print("[0] ↩️ Back")
            print()

            try:
                selected = int(
                    input(f"{MAGENTA}Active API > {RESET}").strip()
                )
            except (ValueError, KeyboardInterrupt, EOFError):
                continue

            if selected == 0:
                continue

            if not 1 <= selected <= len(keys):
                continue

            data["active"] = selected - 1
            save_api_keys(data)

            print()
            print(
                f"{GREEN}✅ {keys[selected - 1].get('name', f'API {selected}')} "
                f"is now active.{RESET}"
            )
            input("\nPress ENTER...")
            continue


def get_api_key():
    key = get_active_api_key()

    if key:
        return key

    clear()

    print(f"{GREEN}{BOLD}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                  🔐 API KEY SETUP                        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{RESET}")
    print()

    print(
        f"{WHITE}"
        "SVA Matrix Squad uses your own OpenRouter API key.\n"
        "The key is stored locally on this device.\n"
        "It is not written into the source code."
        f"{RESET}"
    )

    print()

    while True:
        try:
            key = getpass.getpass(
                f"{CYAN}{BOLD}"
                "OpenRouter API Key > "
                f"{RESET}"
            ).strip()

        except (KeyboardInterrupt, EOFError):
            print()
            print(f"{RED}❌ Cancelled.{RESET}")
            sys.exit(1)

        if key:
            data = {
                "active": 0,
                "keys": [
                    {
                        "name": "API 1",
                        "key": key,
                    }
                ],
            }

            try:
                save_api_keys(data)

                print()
                print(f"{GREEN}✅ API key saved locally.{RESET}")
                time.sleep(1)

            except OSError as e:
                print()
                print(
                    f"{YELLOW}⚠️ Could not save API key: "
                    f"{e}{RESET}"
                )

            return key

        print()
        print(f"{RED}❌ API key cannot be empty.{RESET}")


    key_file = Path.home() / ".sva_matrix_squad_api_key"

    # Load previously saved API key
    if key_file.exists():

        try:
            key = key_file.read_text().strip()

            if key:
                print(f"{GREEN}🔐 Saved OpenRouter API key loaded.{RESET}")
                time.sleep(1)
                return key

        except OSError:
            pass

    clear()

    print(f"{GREEN}{BOLD}")

    print("╔══════════════════════════════════════════════════════════╗")
    print("║                  🔐 API KEY SETUP                        ║")
    print("╚══════════════════════════════════════════════════════════╝")

    print(f"{RESET}")
    print()

    print(
        f"{WHITE}"
        "SVA Matrix Squad uses your own OpenRouter API key.\n"
        "The key is stored locally on this device.\n"
        "It is not written into the source code."
        f"{RESET}"
    )

    print()

    while True:

        try:
            key = getpass.getpass(
                f"{CYAN}{BOLD}"
                "OpenRouter API Key > "
                f"{RESET}"
            ).strip()

        except (KeyboardInterrupt, EOFError):

            print()
            print(f"{RED}❌ Cancelled.{RESET}")
            sys.exit(1)

        if key:

            try:
                key_file.write_text(key + "\n")
                key_file.chmod(0o600)
                print()
                print(f"{GREEN}✅ API key saved locally.{RESET}")
                time.sleep(1)
            except OSError as e:
                print()
                print(f"{YELLOW}⚠️ Could not save API key: {e}{RESET}")

            return key

        print()
        print(f"{RED}❌ API key cannot be empty.{RESET}")
        print()


# ============================================================
# OPENROUTER REQUEST
# ============================================================

def ask_ai(api_key, messages):
    """Send an AI request using the configured API-key failover chain."""
    client = SVAAIClient(
        api_key,
        API_URL,
        MODEL,
    )

    result = client.ask(
        "\n".join(
            str(message.get("content", ""))
            for message in messages
            if isinstance(message, dict)
        )
    )

    if result.get("success"):
        return result.get("response", "")

    raise RuntimeError(
        result.get("error", "AI request failed.")
    )


# ============================================================
# MENU
# ============================================================

def show_menu():

    print(f"{BLUE}{BOLD}")

    print("╭────────────────────────────────────────────────────────╮")
    print("│                  ⚡ SVA MATRIX SQUAD MENU ⚡                  │")
    print("╰────────────────────────────────────────────────────────╯")

    print(f"{RESET}")

    print(
        f"{CYAN}[1]{RESET} ⚙️ Settings"
    )
    print(
        f"{GREEN}[2]{RESET} 🤖 Ask AI"
    )

    print(
        f"{GREEN}[3]{RESET} 🐧 Explain Linux / Termux Command"
    )

    print(
        f"{MAGENTA}[4]{RESET} 💻 Code Assistant"
    )

    print(
        f"{RED}[5]{RESET} 🛡️  Cybersecurity Learning"
    )

    print(
        f"{YELLOW}[6]{RESET} 💬 General Question"
    )

    print(
        f"{BLUE}[7]{RESET} 🚀 Task Agent"
    )

    print(
        f"{RED}[0]{RESET} 🚪 Exit"
    )

    print()


# ============================================================
# AI ASSISTANT
# ============================================================

CHAT_HISTORY_FILE = Path.home() / ".sva_matrix_squad_chat.json"


def load_chat_history():
    if not CHAT_HISTORY_FILE.exists():
        return []

    try:
        import json
        data = json.loads(CHAT_HISTORY_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_chat_history(messages):
    import json

    try:
        CHAT_HISTORY_FILE.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2)
        )
        try:
            CHAT_HISTORY_FILE.chmod(0o600)
        except OSError:
            pass
    except Exception as error:
        print(f"{RED}⚠ Chat save failed: {error}{RESET}")


def chat_stats(messages):
    user_count = sum(
        1 for m in messages if m.get("role") == "user"
    )
    assistant_count = sum(
        1 for m in messages if m.get("role") == "assistant"
    )

    return user_count, assistant_count


def display_chat_history(messages):

    terminal_width = 60

    for message in messages:
        role = message.get("role")
        content = message.get("content", "").strip()

        if role == "user":
            print(
                f"{GREEN}{BOLD}"
                f"{'👤 YOU:':>{terminal_width}}"
                f"{RESET}"
            )

            for line in content.splitlines():
                print(
                    f"{WHITE}"
                    f"{line:>{terminal_width}}"
                    f"{RESET}"
                )

            print()

        elif role == "assistant":
            print(
                f"{CYAN}{BOLD}"
                "🤖 SVA MATRIX:"
                f"{RESET}"
            )

            print(
                f"{WHITE}{content}{RESET}"
            )

            print()

    print(
        f"{CYAN}"
        "──────────────────────────────────────────────────────────"
        f"{RESET}"
    )



def assistant(api_key, initial_choice=None):

    from datetime import datetime

    now = datetime.now().astimezone()
    current_context = (
        f"Current local date and time: {now.strftime('%A, %d %B %Y, %I:%M:%S %p %Z')}. "
        "Use this as the authoritative current date and time for this session."
    )

    saved_messages = load_chat_history()

    if saved_messages:
        messages = saved_messages

        system_message = {
            "role": "system",
            "content": SYSTEM_PROMPT + "\n\n" + current_context
        }

        if messages and messages[0].get("role") == "system":
            messages[0] = system_message
        else:
            messages.insert(0, system_message)

        save_chat_history(messages)

    else:
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT + "\n\n" + current_context
            }
        ]

        save_chat_history(messages)


    while True:

        if initial_choice is not None:
            choice = str(initial_choice).strip()
            initial_choice = None
        else:
            clear()
            show_menu()

            try:
                choice = input(
                    f"{MAGENTA}{BOLD}"
                    "SVA Matrix Squad > "
                    f"{RESET}"
                ).strip()

            except (KeyboardInterrupt, EOFError):
                print()
                print(
                    f"{GREEN}{BOLD}"
                    "👋 Goodbye from SVA Matrix Squad!"
                    f"{RESET}"
                )
                return

        if choice == "0":
            print()
            print(
                f"{GREEN}{BOLD}"
                "👋 Goodbye from SVA Matrix Squad!"
                f"{RESET}"
            )
            return

        # ----------------------------------------------------
        # SETTINGS
        # ----------------------------------------------------

        if choice == "1":
            while True:
                clear()

                print(f"{CYAN}{BOLD}")
                print("╭────────────────────────────────────────────────────────╮")
                print("│                     ⚙️ SETTINGS                        │")
                print("╰────────────────────────────────────────────────────────╯")
                print(f"{RESET}")

                print(f"{GREEN}[1]{RESET} 🌐 Language")
                print(f"{YELLOW}[2]{RESET} 🔑 API Keys")
                print(f"{RED}[0]{RESET} ↩️ Back")
                print()

                setting_choice = input(
                    f"{MAGENTA}{BOLD}Settings > {RESET}"
                ).strip()

                if setting_choice == "0":
                    break

                if setting_choice == "1":
                    language_menu()
                    continue

                if setting_choice == "2":
                    api_keys_menu()
                    continue

                input(
                    f"\n{RED}❌ Invalid option. Press ENTER...{RESET}"
                )

            continue

        # ----------------------------------------------------
        # ASK AI: DIRECT CHAT
        # ----------------------------------------------------


        if choice == "2":
            history_type = "chat"
            history_label = "🤖 Ask AI"

            from sva_engine.history import HistoryManager
            history_manager = HistoryManager()

            # Start directly with a fresh chat.
            # Old chats are available through M / m inside Chat.
            history_id = None

            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT + "\n\n" + current_context,
                }
            ]

            while True:
                clear()

                print(
                    f"{CYAN}{BOLD}"
                    "╭────────────────────────────────────────────────────────╮"
                )
                print(
                    "│                       🤖 ASK AI                         │"
                )
                print(
                    "╰────────────────────────────────────────────────────────╯"
                    f"{RESET}"
                )
                print()

                if history_id:
                    current_record = history_manager.load(history_id)

                    if current_record:
                        print(
                            f"{YELLOW}{BOLD}"
                            f"📚 {current_record.get('title', 'Untitled')}"
                            f"{RESET}"
                        )
                        print()

                display_chat_history(messages)

                print(
                    f"{YELLOW}"
                    "Type your question. Enter 0 to return to menu."
                    f"{RESET}"
                )
                print(
                    f"{BLUE}"
                    "M / m → Chat Manager"
                    f"{RESET}"
                )
                print()

                try:
                    question = input(
                        f"{MAGENTA}{BOLD}"
                        "SVA Matrix Squad > "
                        f"{RESET}"
                    ).strip()
                except (KeyboardInterrupt, EOFError):
                    print()
                    return

                # 0 = Main Menu
                if question == "0":
                    break

                # Only exactly one M/m is accepted.
                if len(question) == 1 and question.lower() == "m":
                    history_id, loaded_messages = universal_chat_manager(
                        history_manager,
                        history_type,
                        history_id,
                        messages,
                        history_label,
                    )

                    if loaded_messages is None:
                        messages = [
                            {
                                "role": "system",
                                "content": (
                                    SYSTEM_PROMPT
                                    + "\n\n"
                                    + current_context
                                ),
                            }
                        ]
                    else:
                        messages = loaded_messages

                    continue

                # MM/mm or any other multi-character command is NOT Manager.
                if question.lower() == "mm":
                    input(
                        f"\n{RED}"
                        "❌ Invalid. Use only M for Chat Manager."
                        f"{RESET}"
                    )
                    continue

                if not question:
                    continue

                # Create history only after first real question.
                if history_id is None:
                    history_record = history_manager.create(
                        history_type="chat",
                        first_text=question,
                        data={"messages": []},
                    )
                    history_id = history_record["history_id"]

                messages.append(
                    {
                        "role": "user",
                        "content": question,
                    }
                )

                history_manager.append_message(
                    history_id,
                    "user",
                    question,
                )

                try:
                    answer = ask_ai(
                        api_key,
                        messages,
                    )
                except Exception as error:
                    print()
                    print(
                        f"{RED}"
                        f"❌ AI error: {error}"
                        f"{RESET}"
                    )
                    input("\nPress ENTER...")
                    continue

                messages.append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

                history_manager.append_message(
                    history_id,
                    "assistant",
                    answer,
                )

                # AI reply is already saved in messages.
                # Let the chat loop redraw the complete conversation
                # so YOU stays on the right and SVA MATRIX stays on the left.
                continue

        # ----------------------------------------------------
        # ASK AI: DIRECT CHAT
        # ----------------------------------------------------

        if choice == "3":
            from sva_engine.history import HistoryManager

            history_type = "linux"
            history_label = "🐧 Linux / Termux"
            history_manager = HistoryManager()
            history_id = None

            linux_prompt = (
                SYSTEM_PROMPT
                + "\\n\\n"
                + current_context
                + "\\n\\n"
                + "You are a Linux and Termux command expert. "
                + "Explain Linux/Termux commands clearly and safely. "
                + "When useful, give practical examples and explain "
                + "what each command does."
            )

            messages = [
                {
                    "role": "system",
                    "content": linux_prompt,
                }
            ]

            while True:
                clear()

                print(
                    f"{CYAN}{BOLD}"
                    "╭────────────────────────────────────────────────────────╮"
                )
                print(
                    "│              🐧 LINUX / TERMUX ASSISTANT               │"
                )
                print(
                    "╰────────────────────────────────────────────────────────╯"
                    f"{RESET}"
                )
                print()

                display_chat_history(messages)

                print(
                    f"{YELLOW}"
                    "Type a Linux/Termux command or question."
                    f"{RESET}"
                )
                print(
                    f"{BLUE}"
                    "Enter 0 to return to Main Menu."
                    f"{RESET}"
                )
                print()

                try:
                    question = input(
                        f"{MAGENTA}{BOLD}"
                        "Linux / Termux > "
                        f"{RESET}"
                    ).strip()
                except (KeyboardInterrupt, EOFError):
                    print()
                    break

                if question == "0":
                    break

                if question.lower() == "m":
                    history_id, loaded_messages = universal_chat_manager(
                        history_manager,
                        history_type,
                        history_id,
                        messages,
                        history_label,
                    )

                    if loaded_messages is None:
                        messages = [
                            {
                                "role": "system",
                                "content": linux_prompt,
                            }
                        ]
                    else:
                        messages = loaded_messages

                    continue

                if not question:
                    continue

                real_result = run_real_termux_command(question)

                if real_result is not None:
                    output = real_result["stdout"] or "(no stdout)"
                    error = real_result["stderr"]

                    real_text = (
                        f"REAL TERMUX COMMAND: {question}\n"
                        f"RETURN CODE: {real_result['returncode']}\n"
                        f"STDOUT:\n{output}"
                    )

                    if error:
                        real_text += f"\nSTDERR:\n{error}"

                    messages.append(
                        {
                            "role": "user",
                            "content": question,
                        }
                    )

                    messages.append(
                        {
                            "role": "assistant",
                            "content": real_text,
                        }
                    )

                    if history_id is None:
                        history_record = history_manager.create(
                            history_type=history_type,
                            first_text=question,
                            data={"messages": []},
                        )
                        history_id = history_record["history_id"]

                    history_manager.append_message(
                        history_id,
                        "user",
                        question,
                    )
                    history_manager.append_message(
                        history_id,
                        "assistant",
                        real_text,
                    )

                    try:
                        explanation = ask_ai(
                            api_key,
                            [
                                {
                                    "role": "system",
                                    "content": linux_prompt,
                                },
                                {
                                    "role": "user",
                                    "content": (
                                        "Explain this REAL Termux result. "
                                        "Do not invent or change any output.\\n\\n"
                                        + real_text
                                    ),
                                },
                            ],
                        )
                    except Exception as error:
                        explanation = f"AI explanation error: {error}"

                    explanation_text = (
                        "Explanation:\\n" + explanation
                    )

                    messages.append(
                        {
                            "role": "assistant",
                            "content": explanation_text,
                        }
                    )

                    history_manager.append_message(
                        history_id,
                        "assistant",
                        explanation_text,
                    )

                    continue

                messages.append(
                    {
                        "role": "user",
                        "content": question,
                    }
                )

                try:
                    answer = ask_ai(
                        api_key,
                        messages,
                    )
                except Exception as error:
                    messages.pop()
                    print()
                    print(
                        f"{RED}"
                        f"❌ AI error: {error}"
                        f"{RESET}"
                    )
                    input("\nPress ENTER...")
                    continue

                messages.append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

                if history_id is None:
                    history_record = history_manager.create(
                        history_type=history_type,
                        first_text=question,
                        data={"messages": []},
                    )
                    history_id = history_record["history_id"]

                history_manager.append_message(
                    history_id,
                    "user",
                    question,
                )
                history_manager.append_message(
                    history_id,
                    "assistant",
                    answer,
                )

                continue

        # ----------------------------------------------------
        # ----------------------------------------------------
        # CODE ASSISTANT / REAL DEBUGGER
        # ----------------------------------------------------

        if choice == "4":
            from sva_engine.code_debugger import CodeDebugger

            ai_client = SVAAIClient(
                api_key=api_key,
                api_url=API_URL,
                model=MODEL,
            )

            debugger = CodeDebugger(ai_client=ai_client)

            while True:
                clear()

                print(
                    f"{CYAN}{BOLD}"
                    "╭────────────────────────────────────────────────────────╮"
                )
                print(
                    "│                  💻 CODE ASSISTANT                      │"
                )
                print(
                    "╰────────────────────────────────────────────────────────╯"
                    f"{RESET}"
                )
                print()

                print(
                    f"{YELLOW}"
                    "Select what you want to debug."
                    f"{RESET}"
                )
                print(
                    f"{BLUE}"
                    "Choose a Python file or paste Python code."
                    f"{RESET}"
                )
                print()

                print(
                    f"{CYAN}{BOLD}"
                    "[1] 📂 Select Python File"
                    f"{RESET}"
                )
                print(
                    f"{CYAN}{BOLD}"
                    "[2] 🔎 Search Python File"
                    f"{RESET}"
                )
                print(
                    f"{CYAN}{BOLD}"
                    "[3] 📝 Paste Python Code"
                    f"{RESET}"
                )
                print(
                    f"{CYAN}{BOLD}"
                    "[4] 📦 Select Project"
                    f"{RESET}"
                )
                print(
                    f"{CYAN}{BOLD}"
                    "[5] 📍 Enter Project Path"
                    f"{RESET}"
                )
                print(
                    f"{BLUE}"
                    "[0] ↩️ Back"
                    f"{RESET}"
                )
                print()

                source_choice = input(
                    f"{MAGENTA}{BOLD}"
                    "Select > "
                    f"{RESET}"
                ).strip()

                if source_choice == "0":
                    break

                code = ""
                selected_file = None

                if source_choice == "1":
                    py_files = sorted(
                        path
                        for path in Path(".").rglob("*.py")
                        if ".git" not in path.parts
                        and "__pycache__" not in path.parts
                        and not any(
                            part.startswith("SVA-Matrix.py.before-")
                            for part in path.parts
                        )
                    )

                    print()
                    print(
                        f"{CYAN}{BOLD}"
                        "📂 PYTHON FILES"
                        f"{RESET}"
                    )
                    print()

                    if not py_files:
                        print(
                            f"{YELLOW}"
                            "No Python files found."
                            f"{RESET}"
                        )
                        input("\nPress Enter to continue...")
                        continue

                    for index, path in enumerate(py_files, 1):
                        print(
                            f"{YELLOW}"
                            f"[{index}] "
                            f"{path}"
                            f"{RESET}"
                        )

                    print()
                    file_choice = input(
                        f"{MAGENTA}{BOLD}"
                        "File > "
                        f"{RESET}"
                    ).strip()

                    try:
                        file_index = int(file_choice)
                        if not 1 <= file_index <= len(py_files):
                            raise ValueError
                    except ValueError:
                        print()
                        print(
                            f"{RED}"
                            "Invalid file selection."
                            f"{RESET}"
                        )
                        input("\nPress Enter to continue...")
                        continue

                    selected_file = py_files[file_index - 1]

                    try:
                        code = selected_file.read_text(
                            encoding="utf-8"
                        )
                    except Exception as error:
                        print()
                        print(
                            f"{RED}"
                            f"Could not read file: {error}"
                            f"{RESET}"
                        )
                        input("\nPress Enter to continue...")
                        continue

                    question = (
                        "Find bugs or errors in this Python file "
                        "and give the exact fix."
                    )

                elif source_choice == "2":
                    search_root = Path(".").resolve()

                    print()
                    print(
                        f"{YELLOW}"
                        "🔎 SEARCH PYTHON FILE"
                        f"{RESET}"
                    )
                    print()

                    search_term = input(
                        f"{MAGENTA}{BOLD}"
                        "Search > "
                        f"{RESET}"
                    ).strip()

                    if not search_term:
                        continue

                    py_files = sorted(
                        path
                        for path in search_root.rglob("*.py")
                        if ".git" not in path.parts
                        and "__pycache__" not in path.parts
                        and not any(
                            part.startswith("SVA-Matrix.py.before-")
                            for part in path.parts
                        )
                        and search_term.lower()
                        in path.name.lower()
                    )

                    print()

                    if not py_files:
                        print(
                            f"{YELLOW}"
                            "No matching Python files found."
                            f"{RESET}"
                        )
                        input("\nPress Enter to continue...")
                        continue

                    print(
                        f"{CYAN}{BOLD}"
                        f"Found {len(py_files)} matching file(s):"
                        f"{RESET}"
                    )
                    print()

                    for index, file_path in enumerate(py_files, 1):
                        print(
                            f"{YELLOW}"
                            f"[{index}] "
                            f"{file_path}"
                            f"{RESET}"
                        )

                    print()

                    file_choice = input(
                        f"{MAGENTA}{BOLD}"
                        "File > "
                        f"{RESET}"
                    ).strip()

                    try:
                        file_index = int(file_choice)
                        if not 1 <= file_index <= len(py_files):
                            raise ValueError
                    except ValueError:
                        print()
                        print(
                            f"{RED}"
                            "Invalid file selection."
                            f"{RESET}"
                        )
                        input("\nPress Enter to continue...")
                        continue

                    selected_file = py_files[file_index - 1]

                    try:
                        code = selected_file.read_text(
                            encoding="utf-8"
                        )
                    except Exception as error:
                        print()
                        print(
                            f"{RED}"
                            f"Could not read file: {error}"
                            f"{RESET}"
                        )
                        input("\nPress Enter to continue...")
                        continue

                    question = (
                        "Find bugs or errors in this Python file "
                        "and give the exact fix."
                    )

                elif source_choice == "3":
                    print()
                    print(
                        f"{YELLOW}"
                        "Paste Python code below."
                        f"{RESET}"
                    )
                    print(
                        f"{BLUE}"
                        "Type END_CODE on a new line when finished."
                        f"{RESET}"
                    )
                    print()

                    lines = []

                    while True:
                        line = input()
                        if line.strip().replace(" ", "_").upper() == "END_CODE":
                            break
                        lines.append(line)

                    code = "\n".join(lines)

                    if not code.strip():
                        continue

                    print()
                    question = input(
                        f"{MAGENTA}{BOLD}"
                        "Question > "
                        f"{RESET}"
                    ).strip()

                    if question == "0":
                        break

                    if not question:
                        question = (
                            "Find bugs or errors in this Python code "
                            "and give the exact fix."
                        )

                elif source_choice == "5":
                    from sva_engine.project_checker import ProjectChecker

                    print()
                    print(
                        f"{CYAN}{BOLD}"
                        "📍 ENTER PROJECT PATH"
                        f"{RESET}"
                    )
                    print()
                    print(
                        f"{YELLOW}"
                        "Enter the exact project/folder path to check."
                        f"{RESET}"
                    )
                    print(
                        f"{YELLOW}"
                        "Example: ~/My Project/MASTER-BUILDER/SVA-Matrix-Custom/SVA-Matrix"
                        f"{RESET}"
                    )
                    print()

                    project_path_input = input(
                        f"{MAGENTA}{BOLD}"
                        "Path > "
                        f"{RESET}"
                    )
                    print(f"DEBUG PATH RECEIVED: {project_path_input!r}")
                    project_path_input = project_path_input.strip()

                    if not project_path_input:
                        print()
                        print(
                            f"{RED}"
                            "No project path entered."
                            f"{RESET}"
                        )
                        input("\nPress Enter to continue...")
                        continue

                    project_path_input = os.path.expandvars(
                        project_path_input
                    )
                    selected_project = Path(
                        project_path_input
                    ).expanduser()
                    if not selected_project.is_absolute():
                        selected_project = (
                            Path.cwd() / selected_project
                        )
                    selected_project = selected_project.resolve()

                    if not selected_project.is_dir():
                        print()
                        print(
                            f"{RED}"
                            f"Project directory not found: {selected_project}"
                            f"{RESET}"
                        )
                        input("\nPress Enter to continue...")
                        continue

                    print()
                    print(
                        f"{CYAN}{BOLD}"
                        "🔎 SCANNING PROJECT..."
                        f"{RESET}"
                    )
                    print(
                        f"{YELLOW}"
                        f"Path: {selected_project}"
                        f"{RESET}"
                    )

                    import time as _timing_time
                    _flow_start = _timing_time.perf_counter()

                    checker = ProjectChecker(selected_project)

                    _t = _timing_time.perf_counter()
                    project_report = checker.check()
                    print(f"DEBUG CHECK: {_timing_time.perf_counter() - _t:.3f}s")

                    _t = _timing_time.perf_counter()
                    pytest_report = checker.run_pytest()
                    print(f"DEBUG PYTEST: {_timing_time.perf_counter() - _t:.3f}s")
                    print(f"DEBUG LOCAL BEFORE AI: {_timing_time.perf_counter() - _flow_start:.3f}s")

                    clear()

                    print(
                        f"{CYAN}{BOLD}"
                        "╭────────────────────────────────────────────────────────╮"
                    )
                    print(
                        "│                  📦 PROJECT SCAN                       │"
                    )
                    print(
                        "╰────────────────────────────────────────────────────────╯"
                        f"{RESET}"
                    )
                    print()

                    print(f"📍 Project: {selected_project}")
                    print(
                        f"📄 Files discovered: "
                        f"{project_report['files_discovered']}"
                    )
                    print(
                        f"🐍 Python files: "
                        f"{project_report['python_files']}"
                    )
                    print(
                        f"✓ Syntax passed: "
                        f"{project_report['passed']}"
                    )
                    print(
                        f"✗ Syntax errors: "
                        f"{project_report['failed']}"
                    )

                    print()
                    print(
                        f"{CYAN}{BOLD}"
                        "🧪 REAL TESTS"
                        f"{RESET}"
                    )

                    if pytest_report["available"]:
                        status = (
                            "PASS"
                            if pytest_report["success"]
                            else "FAIL"
                        )
                        print(f"Pytest: {status}")
                        print(
                            f"Return code: "
                            f"{pytest_report['returncode']}"
                        )

                        if pytest_report["stdout"]:
                            print()
                            print(pytest_report["stdout"])

                        if pytest_report["stderr"]:
                            print()
                            print(pytest_report["stderr"])
                    else:
                        print(
                            f"{YELLOW}"
                            "⚠ Real pytest tests are not available."
                            f"{RESET}"
                        )

                    print()
                    print(
                        f"{CYAN}{BOLD}"
                        "🔎 STATIC ANALYSIS"
                        f"{RESET}"
                    )
                    print()

                    static_report = checker.static_analyze()

                    print(
                        f"Python files analyzed: "
                        f"{static_report['python_files']}"
                    )
                    print(
                        f"Files with issues: "
                        f"{static_report['files_with_issues']}"
                    )
                    print(
                        f"Total issues: "
                        f"{static_report['issue_count']}"
                    )

                    for _static_file in static_report["results"]:
                        for _issue in _static_file["issues"]:
                            print(
                                f"{YELLOW}"
                                f"  • {_static_file['path']}:{_issue['line']} "
                                f"[{_issue['code']}] {_issue['message']}"
                                f"{RESET}"
                            )

                    if static_report["success"] and static_report["issue_count"] == 0:
                        print(
                            f"{GREEN}"
                            "✓ Static Analysis: PASS"
                            f"{RESET}"
                        )
                    elif static_report["success"]:
                        print(
                            f"{YELLOW}"
                            "⚠ Static Analysis: WARN"
                            f"{RESET}"
                        )
                    else:
                        print(
                            f"{RED}"
                            "✗ Static Analysis: FAIL"
                            f"{RESET}"
                        )

                    print()
                    print()
                    print(
                        f"{CYAN}{BOLD}"
                        "🤖 AI PROJECT ANALYSIS"
                        f"{RESET}"
                    )
                    print()

                    # AI review runs for both passing and failing projects.
                    if True:
                        _source_parts = []
                        _project_files = (
                            ProjectChecker(selected_project)
                            .summary()["files"]
                        )

                        for _item in _project_files:
                            if _item["language"] != "Python":
                                continue

                            _source_path = (
                                Path(selected_project) / _item["path"]
                            )

                            try:
                                _source_text = _source_path.read_text(
                                    encoding="utf-8"
                                )
                            except (OSError, UnicodeDecodeError):
                                continue

                            if len(_source_text) > 50000:
                                _source_text = _source_text[:50000]

                            _source_parts.append(
                                f"===== {_item['path']} =====\n"
                                f"{_source_text}"
                            )

                        _project_source_text = (
                            "\n\n".join(_source_parts)
                            if _source_parts
                            else "(No readable Python source files found.)"
                        )

                        ai_prompt = (
                            "You are the SVA Matrix Squad AI Code Reviewer and Project Debugger.\n"
                            "Review the actual project whether REAL TESTS pass or fail.\n"
                            "Do not invent errors, files, bugs, or test results.\n"
                            "When tests pass, inspect the supplied source and static-analysis results for concrete functional bugs, correctness risks, and test gaps.\n"
                            "Do not recommend changes merely for style or personal preference.\n"
                            "Use only evidence from the supplied project report, "
                            "REAL PYTEST RESULT, and the supplied source files.\n\n"
                            "The source files below are the ACTUAL current files from "
                            "the selected project. Use their exact text when creating "
                            "PATCH JSON. Do not invent or rewrite unrelated files.\n\n"
                            "Return EXACTLY these sections:\n"
                            "CODE REVIEW\n"
                            "BUG / PROBLEM\n"
                            "WHY\n"
                            "EXACT FIX\n"
                            "FILES TO CHANGE\n"
                            "RETEST COMMAND\n"
                            "EXPECTED VERIFICATION\n"
                            "PATCH JSON\n\n"
                            "PATCH JSON must be valid JSON only and have this exact shape:\n"
                            '{"files":[{"path":"relative/path","old":"exact old text","new":"exact new text"}]}\n'
                            "Use only files that exist inside the supplied project.\n"
                            "The old field must contain the exact text to replace.\n"
                            "The new field must contain the complete replacement text.\n"
                            "If no concrete fix is needed, return an empty files list.\n"
                            "If tests pass and the code review finds no concrete functional issue, PATCH JSON must contain an empty files list.\n"
                            "Do NOT modify files automatically unless a safe exact patch is returned.\n\n"
                            f"Project: {selected_project}\n\n"
                            f"PROJECT REPORT:\n{project_report}\n\n"
                            f"STATIC ANALYSIS RESULT:\n{static_report}\n\n"
                            "ACTUAL PROJECT SOURCE FILES:\n"
                            f"{_project_source_text}\n\n"
                            f"REAL PYTEST RESULT:\n"
                            f"{pytest_report['stdout']}\n\n"
                            f"PYTEST ERRORS:\n"
                            f"{pytest_report['stderr']}\n"
                        )

                        try:
                            ai_result = ai_client.ask(ai_prompt)

                            ai_analysis = ""

                            if isinstance(ai_result, dict):
                                if ai_result.get("success"):
                                    ai_analysis = str(
                                        ai_result.get(
                                            "response",
                                            "AI returned no analysis.",
                                        )
                                    )
                                else:
                                    print(
                                        f"{RED}"
                                        f"AI Error: "
                                        f"{ai_result.get('error', 'Unknown error')}"
                                        f"{RESET}"
                                    )
                            else:
                                ai_analysis = str(
                                    ai_result or ""
                                )

                            if ai_analysis.strip():
                                print(ai_analysis)
                                print()
                                try:
                                        json_start = ai_analysis.find("{")
                                        json_end = ai_analysis.rfind("}")

                                        if (
                                            json_start == -1
                                            or json_end == -1
                                        ):
                                            raise ValueError(
                                                "AI did not return PATCH JSON."
                                            )

                                        patch_data = json.loads(
                                            ai_analysis[
                                                json_start:json_end + 1
                                            ]
                                        )

                                        patch_files = patch_data.get(
                                            "files",
                                            []
                                        )

                                        if not patch_files:
                                            print()
                                            print(
                                                f"{GREEN}{BOLD}"
                                                "✓ No fix required"
                                                f"{RESET}"
                                            )
                                        else:
                                            print()
                                            print(
                                                f"{CYAN}{BOLD}"
                                                "🛠️ APPLYING AI FIX..."
                                                f"{RESET}"
                                            )
                                            print(
                                                f"{YELLOW}"
                                                f"Validated patch files: "
                                                f"{len(patch_files)}"
                                                f"{RESET}"
                                            )

                                            fix_result = apply_ai_fix(
                                                selected_project,
                                                patch_data,
                                            )

                                            if not fix_result["success"]:
                                                print(
                                                    f"{RED}"
                                                    "✗ AI FIX NOT APPLIED"
                                                    f"{RESET}"
                                                )
                                                print(
                                                    fix_result["error"]
                                                )
                                            else:
                                                print(
                                                    f"{GREEN}"
                                                "✓ AI FIX APPLIED"
                                                f"{RESET}"
                                            )

                                            for file_path in fix_result[
                                                "files_changed"
                                            ]:
                                                print(
                                                    f"{GREEN}"
                                                    f"  Changed: {file_path}"
                                                    f"{RESET}"
                                                )

                                            print()
                                            print(
                                                f"{CYAN}{BOLD}"
                                                "🧪 RETESTING PROJECT..."
                                                f"{RESET}"
                                            )

                                            retest_report = ProjectChecker(
                                                selected_project
                                            ).run_pytest()

                                            print()

                                            if (
                                                retest_report["available"]
                                                and retest_report["success"]
                                            ):
                                                print(
                                                    f"{GREEN}{BOLD}"
                                                    "✓ VERIFY: ALL TESTS PASSED"
                                                    f"{RESET}"
                                                )
                                                if retest_report["stdout"]:
                                                    print(
                                                        retest_report["stdout"]
                                                    )
                                            else:
                                                print(
                                                    f"{RED}{BOLD}"
                                                    "✗ VERIFY: TESTS STILL FAIL"
                                                    f"{RESET}"
                                                )
                                                if retest_report["stdout"]:
                                                    print(
                                                        retest_report["stdout"]
                                                    )
                                                if retest_report["stderr"]:
                                                    print(
                                                        retest_report["stderr"]
                                                    )

                                except Exception as error:
                                    print(
                                        f"{RED}"
                                        f"AI FIX ERROR: {error}"
                                        f"{RESET}"
                                    )

                            else:
                                ai_analysis = ""

                        except Exception as error:
                            print(
                                f"{RED}"
                                f"AI analysis error: {error}"
                                f"{RESET}"
                            )

                    elif pytest_report["available"]:
                        print(
                            "✓ Real tests passed. "
                            "No failure requires AI analysis."
                        )
                    else:
                        print(
                            "⚠ Real pytest tests are not available."
                        )

                    input("\nPress Enter to continue...")
                    continue


                elif source_choice == "4":
                    from sva_engine.project_checker import ProjectChecker

                    print()
                    print(
                        f"{CYAN}{BOLD}"
                        "📦 SELECT PROJECT"
                        f"{RESET}"
                    )
                    print()

                    projects_root = Path(".").resolve()
                    project_dirs = sorted(
                        directory
                        for directory in projects_root.iterdir()
                        if directory.is_dir()
                        and directory.name not in {
                            ".git",
                            "__pycache__",
                            ".venv",
                            "venv",
                            "node_modules",
                        }
                        and not directory.name.startswith(
                            "SVA-Matrix.py.before-"
                        )
                    )

                    if not project_dirs:
                        print(
                            f"{YELLOW}"
                            "No project directories found."
                            f"{RESET}"
                        )
                        input("\nPress Enter to continue...")
                        continue

                    for index, directory in enumerate(project_dirs, 1):
                        print(
                            f"{YELLOW}"
                            f"[{index}] 📦 {directory.name}"
                            f"{RESET}"
                        )

                    print()

                    project_choice = input(
                        f"{MAGENTA}{BOLD}"
                        "Project > "
                        f"{RESET}"
                    ).strip()

                    try:
                        project_index = int(project_choice)
                        if not 1 <= project_index <= len(project_dirs):
                            raise ValueError
                    except ValueError:
                        print()
                        print(
                            f"{RED}"
                            "Invalid project selection."
                            f"{RESET}"
                        )
                        input("\nPress Enter to continue...")
                        continue

                    selected_project = project_dirs[project_index - 1]

                    checker = ProjectChecker(selected_project)
                    project_report = checker.check()
                    pytest_report = checker.run_pytest()

                    clear()

                    print(
                        f"{CYAN}{BOLD}"
                        "╭────────────────────────────────────────────────────────╮"
                    )
                    print(
                        "│                  📦 PROJECT SCAN                       │"
                    )
                    print(
                        "╰────────────────────────────────────────────────────────╯"
                        f"{RESET}"
                    )
                    print()

                    print(
                        f"{YELLOW}"
                        f"Project: {selected_project}"
                        f"{RESET}"
                    )
                    print()

                    print(
                        f"{CYAN}{BOLD}"
                        "📊 PROJECT REPORT"
                        f"{RESET}"
                    )
                    print()

                    print(
                        f"Files discovered : "
                        f"{project_report['files_discovered']}"
                    )
                    print(
                        f"Python files     : "
                        f"{project_report['python_files']}"
                    )
                    print(
                        f"Syntax passed    : "
                        f"{project_report['passed']}"
                    )
                    print(
                        f"Syntax errors    : "
                        f"{project_report['failed']}"
                    )

                    print()

                    print(
                        f"{CYAN}{BOLD}"
                        "🧪 REAL TESTS"
                        f"{RESET}"
                    )
                    print()

                    if pytest_report["available"]:
                        print(
                            f"Pytest status    : "
                            f"{'PASS' if pytest_report['success'] else 'FAIL'}"
                        )
                        print(
                            f"Return code      : "
                            f"{pytest_report['returncode']}"
                        )

                        if pytest_report["stdout"]:
                            print()
                            print("Test output:")
                            print(pytest_report["stdout"])

                        if pytest_report["stderr"]:
                            print()
                            print(
                                f"{RED}"
                                "Test errors:"
                                f"{RESET}"
                            )
                            print(pytest_report["stderr"])
                    else:
                        print(
                            f"{YELLOW}"
                            f"{pytest_report['message']}"
                            f"{RESET}"
                        )

                    print()

                    errors = [
                        result
                        for result in project_report["results"]
                        if not result["success"]
                    ]

                    if not errors:
                        print(
                            f"{GREEN}{BOLD}"
                            "✓ No Python syntax errors found."
                            f"{RESET}"
                        )
                    else:
                        print(
                            f"{RED}{BOLD}"
                            "✗ ERRORS FOUND"
                            f"{RESET}"
                        )

                        for result in errors:
                            print()
                            print(
                                f"{RED}"
                                f"File: {result['path']}"
                                f"{RESET}"
                            )
                            print(result["stderr"])

                    print()
                    print(
                        f"{CYAN}{BOLD}"
                        "🤖 AI PROJECT ANALYSIS"
                        f"{RESET}"
                    )
                    print()

                    if pytest_report["available"] and not pytest_report["success"]:
                        ai_prompt = (
                            "You are the SVA Matrix Squad Project Debugger.\n"
                            "Analyze the REAL project test failure below.\n"
                            "Do not invent errors, files, or test results.\n"
                            "Use only evidence from the supplied project report "
                            "and REAL PYTEST RESULT.\n\n"
                            "Return EXACTLY these sections:\n"
                            "BUG / PROBLEM\n"
                            "WHY\n"
                            "EXACT FIX\n"
                            "FILES TO CHANGE\n"
                            "RETEST COMMAND\n"
                            "EXPECTED VERIFICATION\n\n"
                            "Do NOT modify files automatically.\n"
                            f"Project: {selected_project}\n\n"
                            f"Python syntax report: {project_report}\n\n"
                            f"REAL PYTEST RESULT:\n"
                            f"{pytest_report['stdout']}\n\n"
                            f"PYTEST ERRORS:\n"
                            f"{pytest_report['stderr']}\n"
                        )

                        try:
                            ai_result = ai_client.ask(ai_prompt)

                            if isinstance(ai_result, dict):
                                if ai_result.get("success"):
                                    ai_analysis = ai_result.get(
                                        "response",
                                        "AI returned no analysis.",
                                    )
                                else:
                                    ai_analysis = ""
                                    print(
                                        f"{RED}"
                                        f"AI Error: "
                                        f"{ai_result.get('error', 'Unknown error')}"
                                        f"{RESET}"
                                    )
                            else:
                                ai_analysis = str(
                                    ai_result or "No AI analysis available."
                                )

                            if ai_analysis:
                                print(ai_analysis)
                                print()
                                print(
                                    f"{CYAN}{BOLD}"
                                    "🛠️ Apply AI Fix"
                                    f"{RESET}"
                                )
                                print(
                                    f"{YELLOW}"
                                    "Apply the exact fix identified by AI, "
                                    "then automatically retest and verify."
                                    f"{RESET}"
                                )
                                print()
                                print("[1] Apply AI Fix")
                                print("[0] Back")
                                print()

                                fix_choice = input(
                                    f"{MAGENTA}{BOLD}"
                                    "Apply AI Fix > "
                                    f"{RESET}"
                                ).strip()

                                if fix_choice == "1":
                                    print()
                                    print(
                                        f"{CYAN}{BOLD}"
                                        "🛠️ APPLYING AI FIX..."
                                        f"{RESET}"
                                    )

                                    try:
                                        json_start = ai_analysis.find("{")
                                        json_end = ai_analysis.rfind("}")

                                        if json_start == -1 or json_end == -1:
                                            raise ValueError(
                                                "AI did not return valid PATCH JSON."
                                            )

                                        patch_data = json.loads(
                                            ai_analysis[json_start:json_end + 1]
                                        )

                                        fix_result = apply_ai_fix(
                                            selected_project,
                                            patch_data,
                                        )

                                        if not fix_result["success"]:
                                            print(
                                                f"{RED}"
                                                f"✗ AI FIX NOT APPLIED"
                                                f"{RESET}"
                                            )
                                            print(fix_result["error"])
                                        else:
                                            print(
                                                f"{GREEN}"
                                                "✓ AI FIX APPLIED"
                                                f"{RESET}"
                                            )

                                            for file_path in fix_result["files_changed"]:
                                                print(
                                                    f"{GREEN}"
                                                    f"  Changed: {file_path}"
                                                    f"{RESET}"
                                                )

                                            print()
                                            print(
                                                f"{CYAN}{BOLD}"
                                                "🧪 RETESTING PROJECT..."
                                                f"{RESET}"
                                            )

                                            retest_report = ProjectChecker(
                                                selected_project
                                            ).run_pytest()

                                            if (
                                                retest_report["available"]
                                                and retest_report["success"]
                                            ):
                                                print(
                                                    f"{GREEN}"
                                                    "✓ VERIFY: ALL TESTS PASSED"
                                                    f"{RESET}"
                                                )
                                                print(
                                                    retest_report["stdout"]
                                                )
                                            else:
                                                print(
                                                    f"{RED}"
                                                    "✗ VERIFY: TESTS STILL FAIL"
                                                    f"{RESET}"
                                                )
                                                print(
                                                    retest_report["stdout"]
                                                )
                                                print(
                                                    retest_report["stderr"]
                                                )

                                    except Exception as error:
                                        print(
                                            f"{RED}"
                                            f"AI FIX ERROR: {error}"
                                            f"{RESET}"
                                        )

                                    input("\nPress Enter to continue...")
                                    continue

                        except Exception as error:
                            print(
                                f"{RED}"
                                f"AI Error: {error}"
                                f"{RESET}"
                            )
                    elif pytest_report["available"]:
                        print(
                            f"{GREEN}"
                            "✓ Real tests passed. No failure requires AI analysis."
                            f"{RESET}"
                        )
                    else:
                        print(
                            f"{YELLOW}"
                            "⚠ Real pytest tests are not available."
                            f"{RESET}"
                        )

                    print()
                    input("Press Enter to continue...")
                    continue

                else:
                    print()
                    print(
                        f"{RED}"
                        "Invalid selection."
                        f"{RESET}"
                    )
                    input("\nPress Enter to continue...")
                    continue

                # Project/file flows above handle their own results.
                # Keep the legacy debugger flow unreachable from project scans.
                continue

                clear()

                print(
                    f"{CYAN}{BOLD}"
                    "╭────────────────────────────────────────────────────────╮"
                )
                print(
                    "│                  💻 CODE ASSISTANT                      │"
                )
                print(
                    "╰────────────────────────────────────────────────────────╯"
                    f"{RESET}"
                )
                print()

                print(
                    f"{YELLOW}{BOLD}"
                    "👤 YOU:"
                    f"{RESET}"
                )
                print(question)
                print()

                print(
                    f"{YELLOW}{BOLD}"
                    f"{' ' * 45}👤 YOU — CODE:"
                    f"{RESET}"
                )
                print(f"{' ' * 45}```python")
                for code_line in code.splitlines():
                    print(f"{' ' * 45}{code_line}")
                print(f"{' ' * 45}```")
                print()

                if selected_file is not None:
                    print(
                        f"{BLUE}"
                        f"📂 File: {selected_file}"
                        f"{RESET}"
                    )
                    print()

                print(
                    f"{CYAN}{BOLD}"
                    "🤖 SVA MATRIX:"
                    f"{RESET}"
                )
                print()

                test_result = result.get("test_result", {})

                print(
                    f"{YELLOW}{BOLD}"
                    "REAL TEST"
                    f"{RESET}"
                )
                print(
                    f"Return code: "
                    f"{test_result.get('returncode', 'N/A')}"
                )

                if test_result.get("stdout"):
                    print()
                    print("STDOUT:")
                    print(test_result["stdout"])

                if test_result.get("stderr"):
                    print()
                    print("STDERR:")
                    print(test_result["stderr"])

                print()
                print(
                    f"{CYAN}{BOLD}"
                    "🤖 AI ANALYSIS"
                    f"{RESET}"
                )

                analysis = result.get("analysis", "")

                if analysis:
                    print(analysis)

                    print()
                    print(
                        f"{GREEN}{BOLD}"
                        "🛠️ FIXED CODE"
                        f"{RESET}"
                    )
                    print()
                    print(
                        f"{YELLOW}"
                        "The AI explanation above may contain the corrected "
                        "code. Use the Exact Fix section from the analysis."
                        f"{RESET}"
                    )

                elif result.get("ai_error"):
                    print(
                        f"{RED}"
                        f"AI Error: {result['ai_error']}"
                        f"{RESET}"
                    )
                else:
                    print(
                        f"{YELLOW}"
                        "No AI analysis available."
                        f"{RESET}"
                    )

                print()
                input("Press Enter to continue...")

        # ----------------------------------------------------
        # ASK AI: DIRECT CHAT
        # ----------------------------------------------------

        from sva_engine.history import HistoryManager

        history_manager = HistoryManager()

        if choice == "5":
            history_type = "cybersecurity"
            history_label = "🛡️ Cybersecurity Learning"
            history_manager = HistoryManager()
            history_id = None

            messages = [
                {
                    "role": "system",
                    "content": (
                        SYSTEM_PROMPT
                        + "\n\nYou are handling Cybersecurity Learning mode. "
                        + "Explain cybersecurity clearly, practically, and "
                        + "educationally. Keep examples legal, authorized, "
                        + "defensive, and suitable for learning. "
                        + "Prefer safe labs and local test environments."
                    ),
                }
            ]

            while True:
                clear()
                print(
                    f"{CYAN}{BOLD}"
                    "╭────────────────────────────────────────────────────────╮"
                )
                print(
                    "│              🛡️ CYBERSECURITY LEARNING                │"
                )
                print(
                    "╰────────────────────────────────────────────────────────╯"
                    f"{RESET}"
                )
                print()
                print(
                    f"{YELLOW}"
                    "Type your cybersecurity question. "
                    "Enter 0 to return to menu."
                    f"{RESET}"
                )
                print(
                    f"{BLUE}"
                    "M / m → Chat Manager"
                    f"{RESET}"
                )
                print()

                display_chat_history(messages)

                try:
                    question = input(
                        f"{MAGENTA}{BOLD}"
                        "Cybersecurity > "
                        f"{RESET}"
                    ).strip()
                except (KeyboardInterrupt, EOFError):
                    print()
                    break

                if question == "0":
                    break

                if question.lower() == "m":
                    history_id, loaded_messages = universal_chat_manager(
                        history_manager,
                        history_type,
                        history_id,
                        messages,
                        history_label,
                    )

                    if loaded_messages is None:
                        messages = [
                            {
                                "role": "system",
                                "content": (
                                    SYSTEM_PROMPT
                                    + "\n\nYou are handling Cybersecurity Learning mode. "
                                    + "Explain cybersecurity clearly, practically, and "
                                    + "educationally. Keep examples legal, authorized, "
                                    + "defensive, and suitable for learning. "
                                    + "Prefer safe labs and local test environments."
                                ),
                            }
                        ]
                    else:
                        messages = loaded_messages

                    continue

                if not question:
                    continue

                messages.append(
                    {"role": "user", "content": question}
                )

                try:
                    answer = ask_ai(api_key, messages)
                except Exception as error:
                    messages.pop()
                    print(f"\n{RED}❌ AI error: {error}{RESET}")
                    input("\nPress ENTER...")
                    continue

                messages.append(
                    {"role": "assistant", "content": answer}
                )

                if history_id is None:
                    history_record = history_manager.create(
                        history_type=history_type,
                        first_text=question,
                        data={"messages": []},
                    )
                    history_id = history_record["history_id"]

                history_manager.append_message(
                    history_id,
                    "user",
                    question,
                )

                history_manager.append_message(
                    history_id,
                    "assistant",
                    answer,
                )

            continue

        # ----------------------------------------------------
        # GENERAL QUESTION
        # ----------------------------------------------------

        if choice == "6":
            history_type = "general"
            history_label = "💬 General Question"
            history_manager = HistoryManager()
            history_id = None

            messages = [
                {
                    "role": "system",
                    "content": (
                        SYSTEM_PROMPT
                        + "\n\nYou are handling General Question mode. "
                        + "Answer clearly and accurately. "
                        + "Use the user's language when practical. "
                        + "Do not invent facts. Keep answers helpful."
                    ),
                }
            ]

            while True:
                clear()
                print(
                    f"{CYAN}{BOLD}"
                    "╭────────────────────────────────────────────────────────╮"
                )
                print(
                    "│                 💬 GENERAL QUESTION                    │"
                )
                print(
                    "╰────────────────────────────────────────────────────────╯"
                    f"{RESET}"
                )
                print()
                print(
                    f"{YELLOW}"
                    "Type your question. Enter 0 to return to menu."
                    f"{RESET}"
                )
                print(
                    f"{BLUE}"
                    "M / m → Chat Manager"
                    f"{RESET}"
                )
                print()

                display_chat_history(messages)

                try:
                    question = input(
                        f"{MAGENTA}{BOLD}"
                        "General Question > "
                        f"{RESET}"
                    ).strip()
                except (KeyboardInterrupt, EOFError):
                    print()
                    break

                if question == "0":
                    break

                if question.lower() == "m":
                    history_id, loaded_messages = universal_chat_manager(
                        history_manager,
                        history_type,
                        history_id,
                        messages,
                        history_label,
                    )

                    if loaded_messages is None:
                        messages = [
                            {
                                "role": "system",
                                "content": (
                                    SYSTEM_PROMPT
                                    + "\n\nYou are handling General Question mode. "
                                    + "Answer clearly and accurately. "
                                    + "Use the user's language when practical. "
                                    + "Do not invent facts. Keep answers helpful."
                                ),
                            }
                        ]
                    else:
                        messages = loaded_messages

                    continue

                if not question:
                    continue

                messages.append(
                    {"role": "user", "content": question}
                )

                try:
                    answer = ask_ai(api_key, messages)
                except Exception as error:
                    messages.pop()
                    print(f"\n{RED}❌ AI error: {error}{RESET}")
                    input("\nPress ENTER...")
                    continue

                messages.append(
                    {"role": "assistant", "content": answer}
                )

                if history_id is None:
                    history_record = history_manager.create(
                        history_type=history_type,
                        first_text=question,
                        data={"messages": []},
                    )
                    history_id = history_record["history_id"]

                history_manager.append_message(
                    history_id,
                    "user",
                    question,
                )

                history_manager.append_message(
                    history_id,
                    "assistant",
                    answer,
                )

            continue

        # ----------------------------------------------------
        # TASK AGENT
        # ----------------------------------------------------

        if choice == "7":
            task_messages = []

            while True:
                clear()

                print(
                    f"{CYAN}{BOLD}"
                    "╭────────────────────────────────────────────────────────╮"
                )
                print(
                    "│                    🚀 TASK AGENT                       │"
                )
                print(
                    "╰────────────────────────────────────────────────────────╯"
                    f"{RESET}"
                )
                print()

                for message in task_messages:
                    if message["role"] == "user":
                        print(f"{MAGENTA}{BOLD}YOU{RESET}")
                    else:
                        print(f"{GREEN}{BOLD}SVA MATRIX{RESET}")

                    print(message["content"])
                    print()

                print(
                    f"{YELLOW}{BOLD}"
                    "[B] Background Continue    [M] Manage History    [0] Back"
                    f"{RESET}"
                )
                print()

                try:
                    task_prompt = input(
                        f"{MAGENTA}{BOLD}"
                        "SVA Matrix Squad > "
                        f"{RESET}"
                    ).strip()

                except (KeyboardInterrupt, EOFError):
                    print()
                    break
                except (KeyboardInterrupt, EOFError):
                    print()
                    break

                if task_prompt == "0":
                    break

                if task_prompt.lower() == "m":
                    task_agent_manager(
                        TaskStore(),
                        background_manager,
                    )
                    continue

                if task_prompt.lower() == "b":
                    active = background_manager.active()

                    clear()

                    print(
                        f"{CYAN}{BOLD}"
                        "╭────────────────────────────────────────────────────────╮"
                    )
                    print("│              🟢 BACKGROUND CONTINUE                    │")
                    print(
                        "╰────────────────────────────────────────────────────────╯"
                        f"{RESET}"
                    )
                    print()

                    if not active:
                        print(
                            f"{YELLOW}"
                            "No task is currently running in this SVA session."
                            f"{RESET}"
                        )
                    else:
                        store = TaskStore()

                        for item in active:
                            live_task = store.load_task(
                                item["project_id"],
                                item["task_id"],
                            )

                            if not live_task:
                                continue

                            current = int(
                                live_task.get("current_step") or 0
                            )
                            total = int(
                                live_task.get("total_steps") or 0
                            )
                            percent = (
                                int(current * 100 / total)
                                if total > 0
                                else 0
                            )

                            print(
                                f"{GREEN}🟢 {item['task_id']}"
                                f" — {percent}% "
                                f"({current}/{total}){RESET}"
                            )
                            print(
                                f"   Action: "
                                f"{live_task.get('current_action')}"
                            )

                    input("\nPress ENTER...")
                    continue

                if not task_prompt:
                    continue

                task_messages.append(
                    {
                        "role": "user",
                        "content": task_prompt,
                    }
                )

                try:
                    store = TaskStore()

                    ai_client = SVAAIClient(
                        api_key=api_key,
                        api_url=API_URL,
                        model=MODEL,
                    )

                    planner = AIPlanner(ai_client)

                    task_messages.append(
                        {
                            "role": "assistant",
                            "content": "🤖 Understanding task...",
                        }
                    )

                    clear()

                    print(
                        f"{CYAN}{BOLD}"
                        "╭────────────────────────────────────────────────────────╮"
                    )
                    print(
                        "│                    🚀 TASK AGENT                       │"
                    )
                    print(
                        "╰────────────────────────────────────────────────────────╯"
                        f"{RESET}"
                    )
                    print()

                    print(f"{MAGENTA}{BOLD}YOU{RESET}")
                    print(task_prompt)
                    print()

                    print(
                        f"{CYAN}"
                        "🧠 Understanding task..."
                        f"{RESET}"
                    )

                    print(
                        f"{CYAN}"
                        "📋 Creating execution plan..."
                        f"{RESET}"
                    )

                    plan = planner.plan(task_prompt)

                    if not plan.get("success"):
                        reason = (
                            plan.get("reason")
                            or plan.get("error")
                            or "Unknown error"
                        )

                        task_messages[-1]["content"] = (
                            "❌ Planning failed:\n"
                            + str(reason)
                        )
                        continue

                    steps = plan.get("steps", [])

                    if not steps:
                        task_messages[-1]["content"] = (
                            "❌ AI returned no executable steps."
                        )
                        continue

                    project_name = str(
                        plan.get("project_name")
                        or "sva-task"
                    ).strip()

                    project_name = (
                        project_name
                        .replace("/", "-")
                        .replace("\\", "-")
                        .replace(" ", "-")
                    )

                    if (
                        not project_name
                        or project_name in {".", ".."}
                        or project_name.startswith(".")
                    ):
                        project_name = "sva-task"

                    # Detect an existing project path from the user's prompt.
                    # Existing paths are only accepted inside the user's home directory.
                    home = Path.home().resolve()
                    existing_workspace = None

                    for raw_part in task_prompt.split():
                        candidate = raw_part.strip().strip('"\\\'`.,:;()[]{}')

                        if candidate.startswith("$HOME/"):
                            candidate = str(home / candidate[6:])
                        elif candidate.startswith("~/"):
                            candidate = str(home / candidate[2:])

                        try:
                            resolved_candidate = Path(candidate).expanduser().resolve()
                        except (OSError, RuntimeError):
                            continue

                        if (
                            resolved_candidate.is_dir()
                            and (
                                resolved_candidate == home
                                or home in resolved_candidate.parents
                            )
                        ):
                            existing_workspace = resolved_candidate
                            break

                    if existing_workspace is not None:
                        workspace = existing_workspace
                        workspace_name = existing_workspace.name or project_name
                    else:
                        workspace = (
                            Path.home() / project_name
                        ).resolve()
                        workspace_name = project_name

                    project_id = (
                        "task_"
                        + str(int(time.time()))
                    )

                    task_id = (
                        "task_"
                        + str(int(time.time() * 1000))
                    )

                    store.create_project(
                        project_id,
                        name=project_name,
                        description=task_prompt,
                        workspace=workspace,
                    )

                    store.create_task(
                        project_id=project_id,
                        task_id=task_id,
                        description=task_prompt,
                        steps=steps,
                    )

                    controller = SVAController(store)
                    controller.set_project(project_id)

                    executor = ActionExecutor(controller)

                    agent = PersistentAgent(
                        controller,
                        store=store,
                        executor=executor,
                    )

                    task_messages[-1]["content"] = (
                        "📋 Plan created: "
                        f"{len(steps)} steps\\n"
                        f"📁 Project: {project_name}\\n"
                        f"📂 Workspace: {workspace}\\n"
                        f"🆔 Task: {task_id}"
                    )

                    clear()

                    print(
                        f"{CYAN}{BOLD}"
                        "╭────────────────────────────────────────────────────────╮"
                    )
                    print(
                        "│                    🚀 TASK AGENT                       │"
                    )
                    print(
                        "╰────────────────────────────────────────────────────────╯"
                        f"{RESET}"
                    )
                    print()

                    print(
                        f"{GREEN}"
                        "🟢 AGENT STARTED"
                        f"{RESET}"
                    )
                    print()
                    print(f"📁 Project: {project_name}")
                    print(f"📂 Workspace: {workspace}")
                    print(f"📋 Steps: {len(steps)}")
                    print()

                    print(
                        f"{CYAN}"
                        "🤖 Understand → Plan → Execute → Verify"
                        f"{RESET}"
                    )
                    print()

                    # Task execution starts immediately.
                    # The task can be moved to background from the
                    # persistent Task Agent controls shown below.

                    agent.run(
                        project_id,
                        task_id,
                    )

                    task = store.load_task(
                        project_id,
                        task_id,
                    )

                    if not task:
                        task_messages[-1]["content"] += (
                            "\n\n"
                            "❌ Task state could not be loaded."
                        )
                        continue

                    status = task.get("status")

                    if status == "COMPLETE":
                        task_messages[-1]["content"] += (
                            "\n\n"
                            "✅ Task completed successfully."
                            "\n"
                            f"📂 Workspace: {workspace}"
                            "\n"
                            f"💾 Checkpoint: {task.get('checkpoint')}"
                        )

                    elif status == "ERROR":
                        task_messages[-1]["content"] += (
                            "\n\n"
                            "❌ Task stopped with an error."
                            "\n"
                            f"📂 Workspace: {workspace}"
                            "\n"
                            f"💾 Checkpoint: {task.get('checkpoint')}"
                            "\n"
                            f"⚠️ {task.get('last_error')}"
                        )

                    elif status == "STOPPED":
                        task_messages[-1]["content"] += (
                            "\n\n"
                            "⏹️ Task stopped."
                            "\n"
                            f"📂 Workspace: {workspace}"
                            "\n"
                            f"💾 Checkpoint: {task.get('checkpoint')}"
                        )

                    else:
                        task_messages[-1]["content"] += (
                            "\n\n"
                            f"ℹ️ Task status: {status}"
                            "\n"
                            f"📂 Workspace: {workspace}"
                        )

                except Exception as error:
                    task_messages.append(
                        {
                            "role": "assistant",
                            "content": (
                                "❌ Task Agent error:\\n"
                                + str(error)
                            ),
                        }
                    )


# ============================================================
# TASK AGENT MANAGER
# ============================================================

def task_agent_manager(store, background_manager):
    """Interactive manager for persisted Task Agent history."""
    while True:
        clear()

        print(
            f"{CYAN}{BOLD}"
            "╭────────────────────────────────────────────────────────╮"
        )
        print("│                 📚 TASK MANAGER                        │")
        print(
            "╰────────────────────────────────────────────────────────╯"
            f"{RESET}"
        )
        print()

        projects = store.list_projects()

        if not projects:
            print(f"{YELLOW}No saved Task Agent projects.{RESET}")
        else:
            for index, project in enumerate(projects, start=1):
                project_id = project.get("project_id", "")
                name = project.get("name") or project_id
                workspace = project.get("workspace") or ""

                tasks = store.list_tasks(project_id)
                active = [
                    task for task in tasks
                    if task.get("status") in {
                        "PENDING", "RUNNING", "PAUSED", "ERROR"
                    }
                ]

                print(
                    f"{MAGENTA}{index}.{RESET} "
                    f"{BOLD}{name}{RESET}"
                )
                print(f"   📂 {workspace}")
                print(
                    f"   📋 Tasks: {len(tasks)}"
                    f" | Active: {len(active)}"
                )
                print()

        print(
            f"{YELLOW}"
            "[number] Open project    [0] Back"
            f"{RESET}"
        )
        print()

        choice = input(
            f"{MAGENTA}{BOLD}"
            "Task Manager > "
            f"{RESET}"
        ).strip()

        if choice == "0":
            return

        if not choice.isdigit():
            continue

        index = int(choice)

        if index < 1 or index > len(projects):
            continue

        project = projects[index - 1]
        project_id = project.get("project_id")
        project_name = project.get("name") or project_id

        while True:
            clear()

            print(
                f"{CYAN}{BOLD}"
                f"📁 {project_name}"
                f"{RESET}"
            )
            print()

            tasks = store.list_tasks(project_id)

            if not tasks:
                print(f"{YELLOW}No tasks in this project.{RESET}")
            else:
                for task_index, task in enumerate(tasks, start=1):
                    current = int(task.get("current_step") or 0)
                    total = int(task.get("total_steps") or 0)
                    percent = (
                        int(current * 100 / total)
                        if total > 0
                        else 0
                    )

                    print(
                        f"{MAGENTA}{task_index}.{RESET} "
                        f"{task.get('task_id')} — "
                        f"{task.get('status')} — "
                        f"{percent}% ({current}/{total})"
                    )
                    print(
                        f"   {task.get('description', '')}"
                    )

            print()
            print(
                f"{YELLOW}"
                "[number] Details / Continue    [0] Back"
                f"{RESET}"
            )

            task_choice = input(
                f"{MAGENTA}{BOLD}"
                "Project Manager > "
                f"{RESET}"
            ).strip()

            if task_choice == "0":
                break

            if not task_choice.isdigit():
                continue

            task_index = int(task_choice)

            if task_index < 1 or task_index > len(tasks):
                continue

            task = tasks[task_index - 1]
            task_id = task.get("task_id")

            clear()

            print(
                f"{CYAN}{BOLD}"
                "📋 TASK DETAILS"
                f"{RESET}"
            )
            print()
            print(f"🆔 Task: {task_id}")
            print(f"📌 Status: {task.get('status')}")
            print(f"📊 Progress: {task.get('current_step', 0)}/{task.get('total_steps', 0)}")
            print(f"📂 Workspace: {project.get('workspace')}")
            print(f"⚙️ Current action: {task.get('current_action')}")
            print(f"⚠️ Last error: {task.get('last_error')}")
            print(f"💾 Checkpoint: {task.get('checkpoint')}")
            print()

            status = task.get("status")

            if status in {"PENDING", "PAUSED", "ERROR", "STOPPED"}:
                print(
                    f"{YELLOW}"
                    "[C] Continue    [B] Background Continue    [0] Back"
                    f"{RESET}"
                )

                action = input(
                    f"{MAGENTA}{BOLD}"
                    "Task Action > "
                    f"{RESET}"
                ).strip().lower()

                if action == "0":
                    continue

                if action in {"c", "b"}:
                    controller = SVAController(store)
                    controller.set_project(project_id)
                    executor = ActionExecutor(controller)
                    agent = PersistentAgent(
                        controller,
                        store=store,
                        executor=executor,
                    )

                    if action == "b":
                        result = background_manager.start(
                            agent,
                            project_id,
                            task_id,
                        )
                        print()
                        if result.get("success"):
                            print(
                                f"{GREEN}"
                                "🟢 Task continued in background."
                                f"{RESET}"
                            )
                        else:
                            print(
                                f"{RED}"
                                f"❌ {result.get('reason')}"
                                f"{RESET}"
                            )
                        input("\nPress ENTER...")
                    else:
                        agent.resume(project_id, task_id)
                        input("\nPress ENTER...")

            else:
                input("\nPress ENTER...")

# ============================================================
# MAIN
# ============================================================


def universal_chat_manager(
    history_manager,
    history_type,
    current_history_id=None,
    current_messages=None,
    mode_label="Chat",
):
    """Mode-specific history manager for chat-based SVA modes."""

    while True:
        clear()

        print(
            f"{CYAN}{BOLD}"
            "╭────────────────────────────────────────────────────────╮"
        )
        print(
            f"│              🗂️ {mode_label.upper()} MANAGER"
            + " " * max(0, 26 - len(mode_label))
            + "│"
        )
        print(
            "╰────────────────────────────────────────────────────────╯"
            f"{RESET}"
        )
        print()

        # IMPORTANT: only this mode's history is shown.
        histories = history_manager.list_history(history_type)

        if histories:
            print(f"{BLUE}📚 {mode_label.upper()} HISTORY{RESET}")
            print()

            for index, record in enumerate(histories, 1):
                title = record.get("title", "Untitled")
                marker = ""

                if record.get("history_id") == current_history_id:
                    marker = f" {GREEN}← CURRENT{RESET}"

                print(
                    f"{YELLOW}[{index}] {RESET}"
                    f"{title}{marker}"
                )
        else:
            print(
                f"{YELLOW}"
                "📭 No saved history."
                f"{RESET}"
            )

        print()
        print(f"{CYAN}[N] 🆕 New Chat{RESET}")
        print(f"{CYAN}[S] 🔄 Switch / Continue Chat{RESET}")
        print(f"{CYAN}[R] ✏️ Rename{RESET}")
        print(f"{CYAN}[E] 📝 Edit Title{RESET}")
        print(f"{RED}[D] 🗑️ Delete Selected{RESET}")
        print(f"{RED}[X] 📦 Delete Range{RESET}")
        print(f"{RED}[A] 💥 Delete All{RESET}")
        print(f"{CYAN}[0] ↩️ Back to {mode_label}{RESET}")
        print()

        try:
            choice = input(
                f"{MAGENTA}{BOLD}"
                f"{mode_label} Manager > "
                f"{RESET}"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return current_history_id, current_messages

        command = choice.lower()

        # ----------------------------------------------------
        # Back
        # ----------------------------------------------------
        if command == "0":
            return current_history_id, current_messages

        # ----------------------------------------------------
        # New Chat
        # ----------------------------------------------------
        if command == "n":
            return None, None

        # ----------------------------------------------------
        # Switch / Continue
        # ----------------------------------------------------
        if command == "s":
            if not histories:
                input(
                    f"\n{YELLOW}"
                    "📭 No saved history. Press ENTER..."
                    f"{RESET}"
                )
                continue

            number = input(
                f"{BLUE}Switch to {mode_label.lower()} number > {RESET}"
            ).strip()

            if not number.isdigit():
                input(
                    f"\n{RED}"
                    "❌ Invalid number. Press ENTER..."
                    f"{RESET}"
                )
                continue

            number = int(number)

            if not 1 <= number <= len(histories):
                input(
                    f"\n{RED}"
                    "❌ Invalid history number. Press ENTER..."
                    f"{RESET}"
                )
                continue

            record = histories[number - 1]
            selected_id = record["history_id"]
            stored = history_manager.load(selected_id) or {}
            stored_messages = stored.get("data", {}).get("messages", [])

            messages = []

            if current_messages:
                system_message = next(
                    (
                        item
                        for item in current_messages
                        if item.get("role") == "system"
                    ),
                    None,
                )

                if system_message:
                    messages.append(system_message)

            for item in stored_messages:
                if item.get("role") in ("user", "assistant"):
                    messages.append(
                        {
                            "role": item.get("role"),
                            "content": item.get("content", ""),
                        }
                    )

            history_manager.touch(selected_id)

            return selected_id, messages

        # ----------------------------------------------------
        # Rename
        # ----------------------------------------------------
        if command in ("r", "e"):
            if not histories:
                input(
                    f"\n{YELLOW}"
                    "📭 No saved history. Press ENTER..."
                    f"{RESET}"
                )
                continue

            number = input(
                f"{BLUE}Edit history number > {RESET}"
            ).strip()

            if not number.isdigit():
                input(
                    f"\n{RED}"
                    "❌ Invalid number. Press ENTER..."
                    f"{RESET}"
                )
                continue

            number = int(number)

            if not 1 <= number <= len(histories):
                input(
                    f"\n{RED}"
                    "❌ Invalid history number. Press ENTER..."
                    f"{RESET}"
                )
                continue

            record = histories[number - 1]

            title = input(
                f"{BLUE}New title > {RESET}"
            ).strip()

            if not title:
                input(
                    f"\n{YELLOW}"
                    "⚠️ Title cannot be empty. Press ENTER..."
                    f"{RESET}"
                )
                continue

            if history_manager.rename(
                record["history_id"],
                title,
            ):
                print(f"{GREEN}✅ Title updated.{RESET}")
            else:
                print(f"{RED}❌ Rename failed.{RESET}")

            input("\nPress ENTER...")
            continue

        # ----------------------------------------------------
        # Delete selected
        # ----------------------------------------------------
        if command == "d":
            if not histories:
                input(
                    f"\n{YELLOW}"
                    "📭 No saved history. Press ENTER..."
                    f"{RESET}"
                )
                continue

            numbers_text = input(
                f"{RED}"
                "Delete number(s) "
                "(example: 1,3,6) > "
                f"{RESET}"
            ).strip()

            try:
                selected_numbers = []

                for part in numbers_text.split(","):
                    part = part.strip()

                    if not part:
                        raise ValueError

                    number = int(part)

                    if number not in selected_numbers:
                        selected_numbers.append(number)

            except ValueError:
                input(
                    f"\n{RED}"
                    "❌ Invalid number list. Use: 1,3,6"
                    f"{RESET}"
                )
                continue

            if any(
                number < 1 or number > len(histories)
                for number in selected_numbers
            ):
                input(
                    f"\n{RED}"
                    "❌ One or more numbers are outside the list."
                    f"{RESET}"
                )
                continue

            selected_records = [
                histories[number - 1]
                for number in selected_numbers
            ]

            print()
            print(f"{RED}Selected for deletion:{RESET}")

            for record in selected_records:
                print(
                    f"  • {record.get('title', 'Untitled')}"
                )

            confirm = input(
                f"{RED}Type DELETE to confirm > {RESET}"
            ).strip()

            if confirm.upper() != "DELETE":
                print(
                    f"{YELLOW}"
                    "Delete cancelled."
                    f"{RESET}"
                )
                input("\nPress ENTER...")
                continue

            deleted_count = 0

            for record in selected_records:
                deleted_id = record["history_id"]

                if history_manager.delete(deleted_id):
                    deleted_count += 1

                    if deleted_id == current_history_id:
                        current_history_id = None
                        current_messages = None

            print(
                f"{GREEN}"
                f"✅ {deleted_count} history item(s) deleted."
                f"{RESET}"
            )
            input("\nPress ENTER...")
            continue

        # ----------------------------------------------------
        # Delete range
        # ----------------------------------------------------
        if command == "x":
            if not histories:
                input(
                    f"\n{YELLOW}"
                    "📭 No saved history. Press ENTER..."
                    f"{RESET}"
                )
                continue

            range_text = input(
                f"{RED}"
                "Delete range (example: 3-7) > "
                f"{RESET}"
            ).strip()

            match = re.fullmatch(
                r"\s*(\d+)\s*-\s*(\d+)\s*",
                range_text,
            )

            if not match:
                input(
                    f"\n{RED}"
                    "❌ Invalid range. Use: 3-7"
                    f"{RESET}"
                )
                continue

            start_number = int(match.group(1))
            end_number = int(match.group(2))

            if start_number > end_number:
                start_number, end_number = end_number, start_number

            if (
                start_number < 1
                or end_number > len(histories)
            ):
                input(
                    f"\n{RED}"
                    "❌ Range is outside the history list."
                    f"{RESET}"
                )
                continue

            selected_records = histories[
                start_number - 1:end_number
            ]

            print()
            print(
                f"{RED}"
                f"Range selected: {start_number}-{end_number}"
                f"{RESET}"
            )

            for record in selected_records:
                print(
                    f"  • {record.get('title', 'Untitled')}"
                )

            confirm = input(
                f"{RED}Type DELETE to confirm > {RESET}"
            ).strip()

            if confirm.upper() != "DELETE":
                print(
                    f"{YELLOW}"
                    "Delete cancelled."
                    f"{RESET}"
                )
                input("\nPress ENTER...")
                continue

            deleted_count = 0

            for record in selected_records:
                deleted_id = record["history_id"]

                if history_manager.delete(deleted_id):
                    deleted_count += 1

                    if deleted_id == current_history_id:
                        current_history_id = None
                        current_messages = None

            print(
                f"{GREEN}"
                f"✅ {deleted_count} history item(s) deleted."
                f"{RESET}"
            )
            input("\nPress ENTER...")
            continue

        # ----------------------------------------------------
        # Delete all
        # ----------------------------------------------------
        if command == "a":
            if not histories:
                input(
                    f"\n{YELLOW}"
                    "📭 No saved history. Press ENTER..."
                    f"{RESET}"
                )
                continue

            print()
            print(
                f"{RED}"
                f"⚠️ This will delete ALL {mode_label.lower()} history."
                f"{RESET}"
            )

            confirm = input(
                f"{RED}Type DELETE ALL to confirm > {RESET}"
            ).strip()

            if confirm.upper() != "DELETE ALL":
                print(
                    f"{YELLOW}"
                    "Delete cancelled."
                    f"{RESET}"
                )
                input("\nPress ENTER...")
                continue

            deleted_count = 0

            for record in histories:
                deleted_id = record["history_id"]

                if history_manager.delete(deleted_id):
                    deleted_count += 1

            current_history_id = None
            current_messages = None

            print(
                f"{GREEN}"
                f"✅ {deleted_count} {mode_label.lower()} "
                f"history item(s) deleted."
                f"{RESET}"
            )
            input("\nPress ENTER...")
            continue

        input(
            f"\n{RED}"
            "❌ Invalid option. Use N, S, R, E, D, X, A or 0."
            f"{RESET}"
        )


def main():

    # --------------------------------------------------------
    # TOOL LOCK SCREEN
    # --------------------------------------------------------

    # --------------------------------------------------------
    # API KEY / FIRST-RUN SCREEN
    # --------------------------------------------------------

    key_file = Path.home() / ".sva_matrix_squad_api_key"

    # Show the YouTube/startup screen only on first run.
    if not key_file.exists() or not key_file.read_text().strip():
        startup_screen()

    api_key = get_api_key()

    # --------------------------------------------------------
    # SVA MATRIX SQUAD STARTUP
    # --------------------------------------------------------

    clear()
    sva_logo()

    print(
        f"{GREEN}{BOLD}"
        "╔══════════════════════════════════════════════════════════╗"
    )
    print(
        "║                                                          ║"
    )
    print(
        "║              🚀 SVA MATRIX SQUAD 🚀                    ║"
    )
    print(
        "║                                                          ║"
    )
    print(
        "║              Starting SVA AI System...                 ║"
    )
    print(
        "║                                                          ║"
    )
    print(
        "╚══════════════════════════════════════════════════════════╝"
        f"{RESET}"
    )

    time.sleep(1)

    # --------------------------------------------------------
    # START ASSISTANT
    # --------------------------------------------------------

    assistant(api_key)



# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
