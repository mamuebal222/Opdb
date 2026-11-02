import hashlib
import json
import os
import re
import threading
import urllib.request
import urllib.error
from datetime import datetime

import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

TIMEOUT = 8

USERNAME_SITES = {
    "GitHub": "https://github.com/{u}",
    "GitLab": "https://gitlab.com/{u}",
    "Reddit": "https://www.reddit.com/user/{u}",
    "Habr": "https://habr.com/ru/users/{u}/",
    "Pikabu": "https://pikabu.ru/@{u}",
    "VK": "https://vk.com/{u}",
    "OK": "https://ok.ru/{u}",
    "Twitch": "https://www.twitch.tv/{u}",
    "Steam": "https://steamcommunity.com/id/{u}",
    "YouTube": "https://www.youtube.com/@{u}",
    "TikTok": "https://www.tiktok.com/@{u}",
    "Medium": "https://medium.com/@{u}",
    "Dev.to": "https://dev.to/{u}",
    "Behance": "https://www.behance.net/{u}",
    "SoundCloud": "https://soundcloud.com/{u}",
    "Keybase": "https://keybase.io/{u}",
    "Replit": "https://replit.com/@{u}",
    "Codepen": "https://codepen.io/{u}",
    "PyPI": "https://pypi.org/user/{u}/",
    "NPM": "https://www.npmjs.com/~{u}",
}

def _check_site(name, url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Linux; Android 10)'})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            if response.status == 200:
                return {"site": name, "url": url}
    except Exception:
        pass
    return None

def scan_username(username):
    found = []
    for name, url in USERNAME_SITES.items():
        result = _check_site(name, url.format(u=username))
        if result:
            found.append(result)
    return {"username": username, "found": found, "total": len(found)}

def scan_email(email):
    domain = email.split("@")[-1]
    valid_syntax = bool(re.match(r"^[\w\.\-+]+@[\w\-]+\.[\w\.\-]+$", email))
    return {
        "email": email,
        "syntax_valid": valid_syntax,
        "domain": domain,
    }

def scan_phone(number):
    try:
        p = phonenumbers.parse(number, None)
    except phonenumbers.NumberParseException as e:
        return {"error": str(e)}
    if not phonenumbers.is_valid_number(p):
        return {"error": "неверный номер"}
    e164 = phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)
    return {
        "e164": e164,
        "valid": True,
        "region": geocoder.description_for_number(p, "ru") or "неизвестно",
        "carrier": carrier.name_for_number(p, "ru") or "неизвестно",
        "timezones": list(timezone.time_zones_for_number(p)),
        "check_links": {
            "telegram": f"https://t.me/{e164}",
            "whatsapp": f"https://wa.me/{e164.lstrip('+')}",
        },
    }

def detect_kind(target):
    t = target.strip()
    if "@" in t and "." in t.split("@")[-1]:
        return "email"
    cleaned = t.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if cleaned.startswith("+") or cleaned.isdigit():
        return "phone"
    return "username"

class RootWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=12, spacing=10, **kwargs)
        self.add_widget(Label(text="[b]OSINT Local[/b]\nВведи username, email или телефон", markup=True, size_hint_y=0.12))
        self.input = TextInput(hint_text="пример: johndoe | user@mail.com | +79001234567", size_hint_y=0.1, multiline=False)
        self.add_widget(self.input)
        
        btn_row = BoxLayout(size_hint_y=0.1, spacing=10)
        self.btn_scan = Button(text="Сканировать")
        self.btn_scan.bind(on_press=self.run_scan)
        btn_row.add_widget(self.btn_scan)
        self.add_widget(btn_row)
        
        self.status = Label(text="Готов к работе", size_hint_y=0.08)
        self.add_widget(self.status)
        
        self.output = Label(text="Здесь появится результат...", size_hint_y=0.6, halign="left", valign="top", text_size=(None, None))
        scroll = ScrollView()
        scroll.add_widget(self.output)
        self.add_widget(scroll)

    def run_scan(self, _):
        target = self.input.text.strip()
        if not target:
            self.status.text = "Пустой запрос"
            return
        kind = detect_kind(target)
        self.status.text = f"Сканирую ({kind}): {target} ..."
        self.output.text = "Подожди, идёт сканирование..."
        threading.Thread(target=self._worker, args=(target, kind), daemon=True).start()

    def _worker(self, target, kind):
        try:
            if kind == "username":
                data = scan_username(target)
                summary = f"Найдено профилей: {data['total']}\n\n"
                if data["found"]:
                    for f in data["found"]:
                        summary += f"[{f['site']}] {f['url']}\n"
                else:
                    summary += "Ничего не найдено."
            elif kind == "email":
                data = scan_email(target)
                summary = f"Email: {data['email']}\nСинтаксис: {'OK' if data['syntax_valid'] else 'ошибка'}\nДомен: {data['domain']}"
            else:
                data = scan_phone(target)
                if "error" in data:
                    summary = f"Ошибка: {data['error']}"
                else:
                    summary = f"Номер: {data['e164']}\nРегион: {data['region']}\nОператор: {data['carrier']}\nTelegram: {data['check_links']['telegram']}\nWhatsApp: {data['check_links']['whatsapp']}"
            
            Clock.schedule_once(lambda dt: setattr(self.output, "text", summary))
            Clock.schedule_once(lambda dt: setattr(self.status, "text", "Готово"))
        except Exception as e:
            Clock.schedule_once(lambda dt: setattr(self.output, "text", f"Ошибка: {e}"))
            Clock.schedule_once(lambda dt: setattr(self.status, "text", "Ошибка"))

class OSINTApp(App):
    def build(self):
        return RootWidget()

if __name__ == "__main__":
    OSINTApp().run()
