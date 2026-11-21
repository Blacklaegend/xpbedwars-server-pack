#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BedWars 服务器自助面板 (Windows)
- 下载 Paper 1.21.4 核心并命名为 server.jar
- 开服 / 关服 (优雅 stop，超时强制结束)
- 快速编辑资源生成器 generators.yml (表单)
- 快速编辑商店 shop.yml / 升级 upgrades2.yml (文本编辑器 + 自动备份)
- 查看各竞技场地图配置 (只读)
- 单文件、无第三方依赖，可打包为 exe
"""
# BedWars 服务器面板 v2.2.0
# Copyright (C) 2024-2026 黑色的传说
# Licensed under the GNU General Public License v3.0 (GPL-3.0)
# 项目主页: https://www.minebbs.com/resources/10218/
import http.server
import socketserver
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import random
import urllib.request
import urllib.parse
import webbrowser
import zipfile
import glob
import sqlite3
from collections import deque
from datetime import datetime

APP_VERSION = "2.2.0"
APP_AUTHOR = "黑色的传说"
APP_LICENSE = "GPL-3.0"
APP_COPYRIGHT = "Copyright (C) 2024-2026 黑色的传说"
APP_URL = "https://www.minebbs.com/resources/10218/"

APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
CONFIG_PATH = os.path.join(APP_DIR, "panel_config.json")
LOG_PATH = os.path.join(APP_DIR, "panel.log")

DEFAULT_CONFIG = {
    "server_dir": os.path.dirname(APP_DIR),
    "java_path": "C:\\Program Files\\Java\\jdk-21.0.11\\bin\\java.exe",
    "min_mem": "4G",
    "max_mem": "8G",
    "paper_version": "1.21.4",
    "paper_build": "",
    "panel_port": 8765,
}

BW = os.path.join("plugins", "BedWars1058")
QUICK_FILES = [
    os.path.join(BW, "generators.yml"),
    os.path.join(BW, "shop.yml"),
    os.path.join(BW, "upgrades2.yml"),
]
GENERATOR_FIELDS = [
    ("Default.iron.delay", "铁生成间隔(秒,可小数)"),
    ("Default.iron.amount", "铁每次数量"),
    ("Default.iron.spawn-limit", "铁堆叠上限"),
    ("Default.gold.delay", "金生成间隔(秒)"),
    ("Default.gold.amount", "金每次数量"),
    ("Default.gold.spawn-limit", "金堆叠上限"),
    ("Default.diamond.tierI.delay", "钻石 I 间隔"),
    ("Default.diamond.tierI.amount", "钻石 I 数量"),
    ("Default.diamond.tierII.delay", "钻石 II 间隔"),
    ("Default.diamond.tierII.amount", "钻石 II 数量"),
    ("Default.diamond.tierII.start", "钻石 II 开始(秒)"),
    ("Default.diamond.tierIII.delay", "钻石 III 间隔"),
    ("Default.diamond.tierIII.amount", "钻石 III 数量"),
    ("Default.diamond.tierIII.start", "钻石 III 开始(秒)"),
    ("Default.emerald.tierI.delay", "绿宝石 I 间隔"),
    ("Default.emerald.tierI.amount", "绿宝石 I 数量"),
    ("Default.emerald.tierII.delay", "绿宝石 II 间隔"),
    ("Default.emerald.tierII.amount", "绿宝石 II 数量"),
    ("Default.emerald.tierII.start", "绿宝石 II 开始(秒)"),
    ("Default.emerald.tierIII.delay", "绿宝石 III 间隔"),
    ("Default.emerald.tierIII.amount", "绿宝石 III 数量"),
    ("Default.emerald.tierIII.start", "绿宝石 III 开始(秒)"),
]


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    # 相对目录以面板所在目录为基准解析，保证解压到任意路径都能找到服务器根目录
    server_dir = str(cfg.get("server_dir") or "").strip()
    if not server_dir:
        cfg["server_dir"] = os.path.dirname(APP_DIR)
    elif not os.path.isabs(server_dir):
        cfg["server_dir"] = os.path.abspath(os.path.join(APP_DIR, server_dir))
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_jar_version(path):
    try:
        with zipfile.ZipFile(path) as z:
            if "version.json" in z.namelist():
                return str(json.loads(z.read("version.json").decode("utf-8", "replace")).get("id", ""))
    except Exception:
        pass
    return ""


def safe_join(root, rel):
    root = os.path.abspath(root)
    p = os.path.abspath(os.path.join(root, rel))
    if not p.startswith(root + os.sep) and p != root:
        raise ValueError("path out of server dir")
    return p


# ---------------------------------------------------------------- YAML helpers
KEY_RE = re.compile(r"^(\s*)([A-Za-z0-9_.\-]+):(.*)$")


def yaml_find_path(text, keys):
    """Return (line_index, indent, key, value_part) for a key path, or None."""
    stack = []
    wanted = list(keys)
    for i, line in enumerate(text.splitlines()):
        m = KEY_RE.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        key = m.group(2)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        cur = [k for _, k in stack] + [key]
        stack.append((indent, key))
        if cur == wanted:
            return i, indent, key, m.group(3)
    return None


def yaml_get(text, keys, default=""):
    hit = yaml_find_path(text, keys)
    if not hit:
        return default
    val = hit[3].strip()
    if "#" in val:
        val = val.split("#", 1)[0].strip()
    if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
        val = val[1:-1]
    return val


def yaml_set(text, keys, new_value):
    lines = text.splitlines()
    hit = yaml_find_path(text, keys)
    if not hit:
        raise KeyError("not found")
    i, indent, key, rest = hit
    trailing = ""
    if "#" in rest:
        trailing = "  " + rest[rest.index("#"):].rstrip()
    lines[i] = "%s%s: %s%s" % (" " * indent, key, new_value, trailing)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def parse_mapping_yaml(text):
    """Small indentation parser for mapping-only YAML (no lists)."""
    root = {}
    stack = [(-1, root)]
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([A-Za-z0-9_.\-]+):(.*)$", line)
        if not m:
            continue
        indent = len(m.group(1))
        key = m.group(2)
        rest = m.group(3).strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if rest == "":
            child = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            val = rest.split(" #")[0].strip()
            if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
                val = val[1:-1]
            parent[key] = val
    return root


def parse_shop_model(text):
    root = parse_mapping_yaml(text)
    categories = []
    for name, cat in root.items():
        if not isinstance(cat, dict) or "category-content" not in cat:
            continue
        items = []
        for iname, item in (cat.get("category-content") or {}).items():
            if not isinstance(item, dict):
                continue
            cs = item.get("content-settings") or {}
            tiers = []
            for tname, tier in (item.get("content-tiers") or {}).items():
                if not isinstance(tier, dict):
                    continue
                ts = tier.get("tier-settings") or {}
                ti = tier.get("tier-item") or {}
                tiers.append({
                    "tier": tname,
                    "cost": ts.get("cost", ""),
                    "currency": ts.get("currency", ""),
                    "material": ti.get("material", ""),
                    "amount": ti.get("amount", ""),
                    "data": ti.get("data", ""),
                    "enchanted": ti.get("enchanted", ""),
                })
            items.append({
                "key": iname,
                "slot": cs.get("content-slot", ""),
                "permanent": cs.get("is-permanent", ""),
                "downgradable": cs.get("is-downgradable", ""),
                "weight": cs.get("weight", ""),
                "unbreakable": cs.get("is-unbreakable", ""),
                "tiers": tiers,
            })
        categories.append({
            "key": name,
            "slot": cat.get("category-slot", ""),
            "display": (cat.get("category-item") or {}).get("material", ""),
            "items": items,
        })
    specials = []
    specials_map = root.get("shop-specials")
    if isinstance(specials_map, dict):
        for sname, sp in specials_map.items():
            if isinstance(sp, dict):
                specials.append({
                    "key": sname,
                    "enable": sp.get("enable", ""),
                    "material": sp.get("material", ""),
                    "health": sp.get("health", ""),
                    "damage": sp.get("damage", ""),
                    "speed": sp.get("speed", ""),
                    "despawn": sp.get("despawn", ""),
                })
    return {"categories": categories, "specials": specials}


def read_yaml(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def strip_mc_colors(value):
    if value is None:
        return ""
    s = str(value)
    s = re.sub(r"[&§][0-9a-fk-orx]", "", s, flags=re.I)
    s = s.replace("{color}", "").replace("{team_color}", "").strip()
    return s


def load_shop_lang(server_dir):
    """Read the shop item display names from the Chinese language file."""
    base = os.path.join(server_dir, BW, "Languages")
    for name in ("messages_zh_cn.yml", "messages_en.yml"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            try:
                return parse_mapping_yaml(read_yaml(p))
            except Exception:
                continue
    return {}


def lang_shop_section(lang):
    if not isinstance(lang, dict):
        return {}
    section = lang.get("shop-items-messages")
    return section if isinstance(section, dict) else {}


def find_block_end(lines, start_index, base_indent):
    """Return index of first non-blank/comment line after start with indent <= base_indent."""
    for i in range(start_index + 1, len(lines)):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= base_indent:
            return i
    return len(lines)


def insert_shop_item(text, category, key, slot, material, amount, cost, currency,
                     data=0, enchanted="false", permanent="false", downgradable="false"):
    lines = text.splitlines()
    cat_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^" + re.escape(category) + r":\s*$", line):
            cat_idx = i
            break
    if cat_idx is None:
        raise KeyError("分类不存在")
    content_idx = None
    for i in range(cat_idx + 1, len(lines)):
        if re.match(r"^  category-content:\s*$", lines[i]):
            content_idx = i
            break
        if lines[i] and not lines[i].startswith(" "):
            break
    if content_idx is None:
        raise KeyError("分类里没有 category-content")
    end_idx = find_block_end(lines, content_idx, 2)
    block = [
        "    %s:" % key,
        "      content-settings:",
        "        content-slot: %s" % slot,
        "        is-permanent: %s" % permanent,
        "        is-downgradable: %s" % downgradable,
        "      content-tiers:",
        "        tier1:",
        "          tier-item:",
        "            material: %s" % material,
        "            data: %s" % data,
        "            amount: %s" % amount,
        "            enchanted: %s" % enchanted,
        "          tier-settings:",
        "            cost: %s" % cost,
        "            currency: %s" % currency,
        "          buy-items:",
        "            %s:" % key,
        "              material: %s" % material,
        "              data: %s" % data,
        "              amount: %s" % amount,
    ]
    # keep a blank line before the new block if needed
    out = lines[:end_idx] + block + lines[end_idx:]
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def insert_lang_item(text, category, key, name, lore):
    lines = text.splitlines()
    root_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^shop-items-messages:\s*$", line):
            root_idx = i
            break
    if root_idx is None:
        raise KeyError("找不到 shop-items-messages 段")
    cat_idx = None
    for i in range(root_idx + 1, len(lines)):
        if re.match(r"^  " + re.escape(category) + r":\s*$", lines[i]):
            cat_idx = i
            break
        if lines[i] and not lines[i].startswith("  "):
            break
    if cat_idx is None:
        raise KeyError("语言文件里找不到分类 %s" % category)
    end_idx = find_block_end(lines, cat_idx, 2)

    def q(s):
        return "'" + str(s).replace("'", "''") + "'"

    block = ["    content-item-%s-name: %s" % (key, q(name))]
    if lore:
        block.append("    content-item-%s-lore:" % key)
        for line in lore:
            block.append("    - %s" % q(line))
    else:
        block.append("    content-item-%s-lore: []" % key)
    out = lines[:end_idx] + block + lines[end_idx:]
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def set_lang_item(text, category, key, name, lore, indent="    "):
    """Set content-item-<key>-name/lore inside language file, replacing lore list."""
    lines = text.splitlines()
    name_key = "content-item-%s-name" % key
    lore_key = "content-item-%s-lore" % key
    # replace name if present
    found_name = False
    for i, line in enumerate(lines):
        m = re.match(r"^" + re.escape(indent) + re.escape(name_key) + r":.*$", line)
        if m:
            lines[i] = "%s%s: '%s'" % (indent, name_key, str(name).replace("'", "''"))
            found_name = True
            break
    # replace lore list if present
    found_lore = False
    for i, line in enumerate(lines):
        if re.match(r"^" + re.escape(indent) + re.escape(lore_key) + r":.*$", line):
            end = i + 1
            while end < len(lines) and re.match(r"^" + re.escape(indent) + r"-\s+", lines[end]):
                end += 1
            new_lore = []
            if lore:
                new_lore.append("%s%s:" % (indent, lore_key))
                for l in lore:
                    new_lore.append("%s- '%s'" % (indent, str(l).replace("'", "''")))
            else:
                new_lore.append("%s%s: []" % (indent, lore_key))
            lines[i:end] = new_lore
            found_lore = True
            break
    if not found_name:
        lines.append("%s%s: '%s'" % (indent, name_key, str(name).replace("'", "''")))
    if not found_lore:
        if lore:
            lines.append("%s%s:" % (indent, lore_key))
            for l in lore:
                lines.append("%s- '%s'" % (indent, str(l).replace("'", "''")))
        else:
            lines.append("%s%s: []" % (indent, lore_key))
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def get_lang_lores(text, category, key):
    """Return the lore lines of content-item-<key>-lore inside the given category."""
    lines = text.splitlines()
    cat_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^  " + re.escape(category) + r":\s*$", line):
            cat_idx = i
            break
    if cat_idx is None:
        return []
    end = find_block_end(lines, cat_idx, 2)
    target = "    content-item-%s-lore:" % key
    for i in range(cat_idx, end):
        if lines[i].strip() == target.strip() and lines[i].startswith("    content-item-"):
            lore = []
            j = i + 1
            while j < end and re.match(r"^    -\s+", lines[j]):
                val = lines[j].strip()[1:].strip()
                if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
                    val = val[1:-1]
                lore.append(val.replace("''", "'"))
                j += 1
            return lore
    return []


def backup_file(path):
    bak = path + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copyfile(path, bak)
    return bak


def get_arena_groups(config_text):
    lines = config_text.splitlines()
    groups = []
    in_groups = False
    for line in lines:
        if re.match(r"^arenaGroups:\s*$", line):
            in_groups = True
            continue
        if in_groups:
            m = re.match(r"^\s*-\s*(.+?)\s*$", line)
            if m:
                groups.append(m.group(1).strip().strip("\"'"))
            elif line.strip() == "":
                continue
            else:
                break
    # deduplicate while keeping order
    seen = set()
    unique = []
    for g in groups:
        if g and g not in seen:
            seen.add(g)
            unique.append(g)
    return unique


def set_arena_groups(config_text, groups):
    # dedupe input
    seen = set()
    unique = []
    for g in groups:
        g = str(g).strip()
        if g and g not in seen:
            seen.add(g)
            unique.append(g)
    groups = unique
    lines = config_text.splitlines()
    out = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if re.match(r"^arenaGroups:\s*$", line):
            out.append(line)
            for g in groups:
                out.append("- " + g)
            replaced = True
            i += 1
            # skip old list items and blank lines that belong to the old block
            while i < len(lines):
                if re.match(r"^\s*-\s+", lines[i]):
                    i += 1
                    continue
                if lines[i].strip() == "":
                    j = i + 1
                    while j < len(lines) and lines[j].strip() == "":
                        j += 1
                    if j < len(lines) and re.match(r"^\s*-\s+", lines[j]):
                        i = j
                        continue
                break
            continue
        out.append(line)
        i += 1
    if not replaced:
        out.append("arenaGroups:")
        for g in groups:
            out.append("- " + g)
    return "\n".join(out) + ("\n" if config_text.endswith("\n") else "")


ARENA_FIELDS = [
    ("display-name", "显示名"),
    ("group", "所属分组"),
    ("minPlayers", "最少玩家"),
    ("maxInTeam", "每队最大人数"),
    ("island-radius", "岛屿半径"),
    ("worldBorder", "世界边界"),
    ("y-kill-height", "死亡高度"),
    ("max-build-y", "最高建筑高度"),
    ("allowSpectate", "允许旁观"),
    ("allow-map-break", "允许破坏地图"),
]


def read_arena_model(server_dir):
    arena_dir = os.path.join(server_dir, BW, "Arenas")
    arenas = []
    if not os.path.isdir(arena_dir):
        return arenas
    for name in sorted(os.listdir(arena_dir)):
        if not name.endswith(".yml"):
            continue
        p = os.path.join(arena_dir, name)
        try:
            text = read_yaml(p)
        except Exception:
            text = ""
        fields = {}
        for key, _label in ARENA_FIELDS:
            fields[key] = yaml_get(text, [key], "")
        base = name[:-4]
        arenas.append({
            "name": name,
            "base": base,
            "size": os.path.getsize(p),
            "world_exists": os.path.isdir(os.path.join(server_dir, base)),
            "fields": fields,
        })
    return arenas


# ---------------------------------------------------------------- Server control
class ServerManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self.proc = None
        self.lock = threading.Lock()
        self.lines = deque(maxlen=4000)
        self.reader = None
        self.started_at = 0.0
        self.stopping = False

    # ---- log ----
    def log(self, text):
        for part in str(text).rstrip().splitlines():
            self.lines.append("[%s] %s" % (now_str(), part))
        try:
            with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as f:
                f.write("%s\n" % str(text).rstrip())
        except Exception:
            pass

    def tail(self, n=300):
        return list(self.lines)[-n:]

    # ---- status ----
    def port_open(self):
        try:
            s = socket.create_connection(("127.0.0.1", 25565), timeout=0.4)
            s.close()
            return True
        except Exception:
            return False

    def _run_hidden(self, args, timeout=10):
        flags = 0
        startupinfo = None
        if os.name == "nt":
            flags = subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        try:
            return subprocess.run(args, capture_output=True, text=True, encoding="gbk", errors="replace",
                                  timeout=timeout, creationflags=flags, startupinfo=startupinfo)
        except Exception:
            return None

    def _pid_listening_on_port(self, port=25565):
        """Read the Windows TCP table with ctypes: no console window is ever created."""
        if os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            class MIB_TCPROW_OWNER_PID(ctypes.Structure):
                _fields_ = [("dwState", wintypes.DWORD),
                            ("dwLocalAddr", wintypes.DWORD),
                            ("dwLocalPort", wintypes.DWORD),
                            ("dwRemoteAddr", wintypes.DWORD),
                            ("dwRemotePort", wintypes.DWORD),
                            ("dwOwningPid", wintypes.DWORD)]

            table = ctypes.windll.iphlpapi.GetExtendedTcpTable
            size = wintypes.DWORD(0)
            AF_INET = 2
            TCP_TABLE_OWNER_PID_LISTENER = 3
            table(None, ctypes.byref(size), False, AF_INET, TCP_TABLE_OWNER_PID_LISTENER, 0)
            buf = ctypes.create_string_buffer(size.value)
            ret = table(buf, ctypes.byref(size), False, AF_INET, TCP_TABLE_OWNER_PID_LISTENER, 0)
            if ret != 0:
                return None
            count = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD)).contents.value
            rows = ctypes.cast(ctypes.addressof(buf) + 4,
                               ctypes.POINTER(MIB_TCPROW_OWNER_PID))
            for i in range(count):
                row = rows[i]
                local_port = socket.ntohs(row.dwLocalPort & 0xFFFF)
                if local_port == port:
                    return int(row.dwOwningPid)
        except Exception:
            pass
        return None

    def external_pid(self):
        return self._pid_listening_on_port(25565)

    def managed(self):
        with self.lock:
            p = self.proc
        return p is not None and p.poll() is None

    def status(self):
        running = self.managed() or self.port_open()
        pid = None
        if self.managed():
            pid = self.proc.pid
        elif running:
            pid = self.external_pid()
        server_dir = self.cfg.get("server_dir")
        jar = os.path.join(server_dir, "server.jar")
        eula_path = os.path.join(server_dir, "eula.txt")
        eula_ok = False
        try:
            with open(eula_path, "r", encoding="utf-8", errors="replace") as f:
                eula_ok = "eula=true" in f.read().replace(" ", "").lower()
        except Exception:
            eula_ok = False
        jar_size = os.path.getsize(jar) if os.path.exists(jar) else 0
        uptime = int(time.time() - self.started_at) if self.managed() and self.started_at else 0
        return {
            "running": running,
            "managed": self.managed(),
            "stopping": self.stopping,
            "pid": pid,
            "uptime": uptime,
            "port_open": self.port_open(),
            "eula_ok": eula_ok,
            "server_jar": os.path.exists(jar),
            "server_jar_size": jar_size,
            "server_jar_version": read_jar_version(jar) if os.path.exists(jar) else "",
            "server_dir": server_dir,
            "java_path": self.cfg.get("java_path"),
            "java_ok": os.path.exists(self.cfg.get("java_path", "")),
            "memory": "%s / %s" % (self.cfg.get("min_mem"), self.cfg.get("max_mem")),
            "paper_version": self.cfg.get("paper_version"),
            "paper_build": self.cfg.get("paper_build", ""),
            "panel_version": APP_VERSION,
            "author": APP_AUTHOR,
            "license": APP_LICENSE,
        }

    # ---- start / stop ----
    def start(self):
        if self.stopping:
            return False, "服务器正在关闭中，请稍候再启动"
        if self.status()["running"]:
            return False, "服务器已经在运行中"
        server_dir = self.cfg["server_dir"]
        jar = os.path.join(server_dir, "server.jar")
        if not os.path.exists(jar):
            return False, "server.jar 不存在，请先在“下载核心”里下载 Paper %s" % self.cfg.get("paper_version")
        eula_path = os.path.join(server_dir, "eula.txt")
        eula_ok = False
        if os.path.exists(eula_path):
            try:
                eula_ok = "eula=true" in open(eula_path, "r", encoding="utf-8", errors="replace").read().replace(" ", "").lower()
            except Exception:
                eula_ok = False
        if not eula_ok:
            return False, "尚未同意 EULA，请先在面板里同意 EULA（eula.txt）"
        java = self.cfg["java_path"]
        if not os.path.exists(java):
            return False, "找不到 Java：%s" % java
        cmd = [java, "-Xms%s" % self.cfg.get("min_mem", "4G"), "-Xmx%s" % self.cfg.get("max_mem", "8G"),
               "-jar", "server.jar", "nogui"]
        self.log("启动命令: %s" % " ".join(cmd))
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            proc = subprocess.Popen(
                cmd, cwd=server_dir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="gbk", errors="replace",
                bufsize=1, creationflags=creationflags,
            )
        except Exception as e:
            self.log("启动失败: %r" % e)
            return False, "启动失败: %r" % e
        with self.lock:
            self.proc = proc
            self.started_at = time.time()
        self.reader = threading.Thread(target=self._read_output, args=(proc,), daemon=True)
        self.reader.start()
        return True, "已发送启动指令，等待服务器加载..."

    def _read_output(self, proc):
        try:
            for line in proc.stdout:
                self.log(line.rstrip())
        except Exception as e:
            self.log("读取控制台失败: %r" % e)
        code = proc.poll()
        self.log("服务器进程已退出，退出码: %s" % code)
        with self.lock:
            if self.proc is proc:
                self.proc = None

    def stop(self):
        if self.stopping:
            return False, "服务器正在关闭中，请稍候"
        if self.managed():
            self.stopping = True
            threading.Thread(target=self._stop_worker, daemon=True).start()
            return True, "已发送 stop 指令，服务器正在关闭（请稍候刷新状态）"
        pid = self.external_pid()
        if pid:
            self.log("检测到外部服务器进程 PID=%s，执行 taskkill" % pid)
            self._run_hidden(["taskkill", "/PID", str(pid), "/F", "/T"], timeout=15)
            return True, "已结束外部服务器进程 PID=%s" % pid
        return False, "服务器当前没有运行"

    def _stop_worker(self):
        try:
            self.log("发送 stop 指令...")
            try:
                self.proc.stdin.write("stop\n")
                self.proc.stdin.flush()
            except Exception as e:
                self.log("写入 stop 失败: %r" % e)
            for _ in range(180):
                if self.proc.poll() is not None:
                    self.log("服务器已正常关闭")
                    return
                time.sleep(1)
            self.log("优雅关闭超时，强制结束进程")
            try:
                self.proc.kill()
            except Exception:
                pass
        finally:
            self.stopping = False

    def send_command(self, command):
        command = str(command or "").strip()
        if not command:
            return False, "命令不能为空"
        if not self.managed():
            return False, "服务器不是面板启动的，无法发送命令（请用面板开服后再输入）"
        try:
            self.proc.stdin.write(command + "\n")
            self.proc.stdin.flush()
            self.log("[面板指令] " + command)
            return True, "已发送: " + command
        except Exception as e:
            return False, "发送失败: %r" % e

    def open_vanilla_console(self):
        if self.status()["running"]:
            return False, "服务器正在运行，请先关服再打开原版控制台"
        server_dir = self.cfg["server_dir"]
        bat = os.path.join(server_dir, "start.bat")
        if not os.path.exists(bat):
            return False, "找不到 start.bat"
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "", "start.bat"], cwd=server_dir,
                             creationflags=(subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0))
            self.log("已在新窗口启动原版控制台（start.bat）")
            return True, "已在新窗口启动原版控制台；面板将无法再捕获这个服务器的输出"
        except Exception as e:
            return False, "启动失败: %r" % e

    # ---- EULA ----
    def accept_eula(self):
        path = os.path.join(self.cfg["server_dir"], "eula.txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/MinecraftEULA).\n")
                f.write("eula=true\n")
            return True, "已写入 eula.txt (eula=true)"
        except Exception as e:
            return False, "写入 eula.txt 失败: %r" % e


# ---------------------------------------------------------------- Paper download
class Downloader:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.state = {"active": False, "phase": "", "downloaded": 0, "total": 0, "error": "", "done": False, "url": ""}

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def _set(self, **kw):
        with self.lock:
            self.state.update(kw)

    def start(self, version=None):
        with self.lock:
            if self.state["active"]:
                return False, "已有下载任务在进行"
        version = version or self.cfg.get("paper_version", "1.21.4")
        t = threading.Thread(target=self._run, args=(version,), daemon=True)
        t.start()
        return True, "开始下载 Paper %s 最新稳定版..." % version

    def _run(self, version):
        self._set(active=True, phase="查询 PaperMC 版本信息", downloaded=0, total=0, error="", done=False, url="")
        try:
            api = "https://fill.papermc.io/v3/projects/paper/versions/%s/builds" % version
            req = urllib.request.Request(api, headers={"User-Agent": "BedWarsPanel/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                builds = json.load(r)
            wanted_build = str(self.cfg.get("paper_build") or "").strip()
            if wanted_build.isdigit():
                match = [b for b in builds if int(b.get("id", 0)) == int(wanted_build)]
                if not match:
                    raise ValueError("Paper %s 没有构建号 %s" % (version, wanted_build))
                pick = match[0]
            else:
                stable = [b for b in builds if str(b.get("channel", "")).upper() in ("STABLE", "RECOMMENDED", "DEFAULT")]
                pick = max(stable or builds, key=lambda b: int(b.get("id", 0)))
            downloads = pick.get("downloads") or {}
            entry = downloads.get("server:default") or next(iter(downloads.values()))
            url = entry["url"]
            total = int(entry.get("size") or 0)
            self._set(phase="下载 paper-%s-%s.jar" % (version, pick.get("id")), total=total, url=url)
            tmp = os.path.join(self.cfg["server_dir"], "server.jar.download")
            os.makedirs(self.cfg["server_dir"], exist_ok=True)
            downloaded = 0
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "BedWarsPanel/1.0"}), timeout=60) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    self._set(downloaded=downloaded)
            self._set(phase="校验并替换 server.jar")
            jar = os.path.join(self.cfg["server_dir"], "server.jar")
            if os.path.exists(jar):
                bak = jar + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.move(jar, bak)
                self._set(phase="已备份旧核心 -> %s" % os.path.basename(bak))
            shutil.move(tmp, jar)
            self._set(phase="完成", done=True, downloaded=downloaded, total=downloaded)
        except Exception as e:
            self._set(error="%r" % e, phase="失败")
        finally:
            self._set(active=False)


# ---------------------------------------------------------------- plugin config forms
def props_get(text, key, default=""):
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip()
    return default


def props_set(text, key, value):
    lines = text.splitlines()
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith("#"):
            continue
        if "=" in line and line.split("=", 1)[0].strip() == key:
            lines[i] = key + "=" + str(value)
            found = True
            break
    if not found:
        lines.append(key + "=" + str(value))
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def format_yaml_scalar(value, typ):
    v = str(value).strip()
    if typ == "bool":
        return "true" if v.lower() in ("true", "1", "yes", "on") else "false"
    if typ == "number":
        if not re.fullmatch(r"-?\d+(\.\d+)?", v):
            raise ValueError("必须是数字: " + v)
        return v
    if re.fullmatch(r"-?\d+(\.\d+)?", v):
        return v
    if v.lower() in ("true", "false"):
        return v.lower()
    return "'" + v.replace("'", "''") + "'"


FORMS = [
    {
        "id": "authme",
        "title": "AuthMe 登录注册",
        "file": "plugins/AuthMe/config.yml",
        "kind": "yaml",
        "note": "保存后执行 /authme reload 或重启服务器生效",
        "fields": [
            ("settings.restrictions.loginTimeout", "登录超时（秒）", "number"),
            ("settings.restrictions.registerTimeout", "注册超时（秒）", "number"),
            ("settings.restrictions.allowChat", "未登录允许聊天（true/false）", "bool"),
            ("settings.restrictions.allowMovement", "未登录允许移动（true/false）", "bool"),
            ("settings.restrictions.maxRegPerIp", "单 IP 最多注册数", "number"),
            ("settings.sessions.enabled", "同 IP 自动登录（true/false）", "bool"),
            ("settings.sessions.timeout", "会话时长（分钟）", "number"),
            ("settings.enablePremium", "正版免密（true/false）", "bool"),
            ("settings.messagesLanguage", "提示语言（zhcn/en）", "text"),
            ("Security.captcha.useCaptcha", "验证码（true/false）", "bool"),
            ("Security.captcha.maxLoginTry", "验证码触发次数", "number"),
            ("Security.tempban.enableTempban", "密码错误封 IP（true/false）", "bool"),
            ("Security.tempban.maxLoginTries", "封 IP 前错误次数", "number"),
        ],
    },
    {
        "id": "ocm",
        "title": "OldCombatMechanics（1.8 PVP）",
        "file": "plugins/OldCombatMechanics/config.yml",
        "kind": "yaml",
        "note": "保存后执行 /ocm reload 或重启服务器生效",
        "fields": [
            ("disable-attack-cooldown.generic-attack-speed", "攻击速度（40=无冷却）", "number"),
            ("attack-frequency.playerDelay", "玩家攻击间隔", "number"),
            ("attack-frequency.mobDelay", "怪物攻击间隔", "number"),
            ("old-player-knockback.knockback-horizontal", "击退水平强度", "number"),
            ("old-player-knockback.knockback-vertical", "击退垂直强度", "number"),
            ("old-player-knockback.knockback-extra-horizontal", "额外水平击退", "number"),
            ("old-critical-hits.multiplier", "暴击倍率", "number"),
            ("old-player-regen.interval", "回血间隔", "number"),
            ("old-player-regen.amount", "每次回血量", "number"),
            ("old-golden-apples.enchanted-golden-apple-crafting", "附魔金苹果可合成", "bool"),
            ("mode-permissions.enabled", "模式权限限制", "bool"),
        ],
    },
    {
        "id": "bedwars",
        "title": "BedWars1058 基础",
        "file": "plugins/BedWars1058/config.yml",
        "kind": "yaml",
        "note": "保存后执行 /bw reload 或重启服务器生效",
        "fields": [
            ("chat-settings.global", "全服聊天（true=全服，false=局内）", "bool"),
            ("chat-settings.shout-cmd-cooldown", "公屏喊话冷却（秒）", "number"),
            ("rejoin-time", "重连保留时间（秒）", "number"),
            ("sidebar.enable-lobby-sidebar", "大厅侧边栏", "bool"),
            ("sidebar.enable-game-sidebar", "游戏内侧边栏", "bool"),
        ],
    },
    {
        "id": "geyser",
        "title": "Geyser 基岩版",
        "file": "plugins/Geyser-Spigot/config.yml",
        "kind": "yaml",
        "note": "保存后需重启服务器生效",
        "fields": [
            ("bedrock.port", "基岩版端口（UDP）", "number"),
            ("java.auth-type", "验证方式（floodgate/offline/online）", "text"),
            ("motd.primary-motd", "MOTD 第一行", "text"),
            ("motd.passthrough-motd", "透传 Java MOTD", "bool"),
            ("gameplay.server-name", "服务器名称", "text"),
        ],
    },
    {
        "id": "serverprops",
        "title": "服务器基本配置 server.properties",
        "file": "server.properties",
        "kind": "props",
        "note": "保存后需重启服务器生效（Java 端口改了记得同步端口映射）",
        "fields": [
            ("server-port", "Java 版端口", "number"),
            ("motd", "MOTD", "text"),
            ("max-players", "最大玩家数", "number"),
            ("view-distance", "视距", "number"),
            ("online-mode", "正版验证（离线整合包请勿改）", "bool"),
        ],
    },
    {
        "id": "voicechat",
        "title": "Simple Voice Chat 语音",
        "file": "plugins/voicechat/voicechat-server.properties",
        "kind": "props",
        "note": "保存后需重启服务器生效；语音端口是 UDP",
        "fields": [
            ("port", "语音端口（UDP）", "number"),
            ("max_voice_distance", "最大语音距离", "text"),
            ("bind_address", "绑定地址（留空=跟随 server-ip）", "text"),
        ],
    },
]


def read_form_values(form, server_dir):
    path = safe_join(server_dir, form["file"])
    if not os.path.exists(path):
        raise FileNotFoundError(form["file"])
    text = read_yaml(path)
    values = []
    for field_path, label, typ in form["fields"]:
        if form["kind"] == "props":
            value = props_get(text, field_path, "")
        else:
            value = yaml_get(text, field_path.split("."), "")
        values.append({"path": field_path, "label": label, "type": typ, "value": value})
    return values


def apply_form_values(form, server_dir, values):
    path = safe_join(server_dir, form["file"])
    text = read_yaml(path)
    allowed = {f[0]: f[2] for f in form["fields"]}
    changed = 0
    for key, val in (values or {}).items():
        if key not in allowed:
            continue
        typ = allowed[key]
        if form["kind"] == "props":
            text = props_set(text, key, str(val).strip())
        else:
            text = yaml_set(text, key.split("."), format_yaml_scalar(val, typ))
        changed += 1
    if changed == 0:
        raise ValueError("没有可保存的字段")
    bak = backup_file(path)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return bak


# ---------------------------------------------------------------- home server config
HOME_FIELDS = [
    ("server.properties", "props", "server-port", "Java 版端口"),
    ("server.properties", "props", "motd", "MOTD"),
    ("plugins/BedWars1058/config.yml", "yaml", "server-ip", "服务器地址（{serverIp}）"),
    ("server.properties", "props", "max-players", "最大玩家数"),
    ("server.properties", "props", "view-distance", "视距"),
    ("plugins/Geyser-Spigot/config.yml", "yaml", "bedrock.port", "基岩版端口（UDP）"),
    ("plugins/voicechat/voicechat-server.properties", "props", "port", "语音端口（UDP）"),
]


def _home_key(file, path):
    return file + "::" + path


def read_home_config(server_dir):
    cache = {}
    out = []
    for file, kind, path, label in HOME_FIELDS:
        if file not in cache:
            cache[file] = read_yaml(safe_join(server_dir, file)) if os.path.exists(safe_join(server_dir, file)) else ""
        text = cache[file]
        if kind == "props":
            value = props_get(text, path, "")
        else:
            value = yaml_get(text, path.split("."), "")
        out.append({"key": _home_key(file, path), "file": file, "path": path,
                    "kind": kind, "label": label, "value": value})
    return out


def apply_home_config(server_dir, values):
    by_file = {}
    for file, kind, path, label in HOME_FIELDS:
        key = _home_key(file, path)
        if key in values:
            by_file.setdefault(file, []).append((kind, path, values[key]))
    if not by_file:
        raise ValueError("没有可保存的字段")
    backups = []
    for file, items in by_file.items():
        p = safe_join(server_dir, file)
        text = read_yaml(p)
        for kind, path, value in items:
            value = str(value).strip()
            if kind == "props":
                text = props_set(text, path, value)
            else:
                text = yaml_set(text, path.split("."), format_yaml_scalar(value, "number" if path.endswith("port") else "text"))
        backups.append(backup_file(p))
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return backups


# ---------------------------------------------------------------- java environment
JAVA_DIR = os.path.join(APP_DIR, "java")
JAVA_DOWNLOAD_URL = "https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse"


def java_version(path):
    try:
        p = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=12,
                           creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0))
        out = (p.stderr or "") + (p.stdout or "")
        m = re.search(r'version "([^"]+)"', out)
        return m.group(1) if m else ""
    except Exception:
        return ""


def find_java_candidates(cfg):
    cands = []

    def add(p):
        if p and os.path.isfile(p) and p.lower().endswith("java.exe") and p not in cands:
            cands.append(p)

    add(cfg.get("java_path"))
    add(shutil.which("java"))
    bases = [
        r"C:\Program Files\Java",
        r"C:\Program Files\Eclipse Adoptium",
        r"C:\Program Files\Zulu",
        r"C:\Program Files\Microsoft\jdk",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Eclipse Adoptium"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Java"),
    ]
    for base in bases:
        if not base:
            continue
        for d in glob.glob(os.path.join(base, "*")):
            add(os.path.join(d, "bin", "java.exe"))
    for d in glob.glob(os.path.join(JAVA_DIR, "*")):
        add(os.path.join(d, "bin", "java.exe"))
    return cands[:12]


class JavaDownloader:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"active": False, "phase": "", "downloaded": 0, "total": 0,
                      "error": "", "done": False, "path": ""}

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def _set(self, **kw):
        with self.lock:
            self.state.update(kw)

    def start(self):
        with self.lock:
            if self.state["active"]:
                return False, "Java 下载任务已在进行"
        threading.Thread(target=self._run, daemon=True).start()
        return True, "开始下载 Temurin 21 JDK（约 190MB），请稍候..."

    def _run(self):
        self._set(active=True, phase="下载 Temurin 21 JDK", downloaded=0, total=0, error="", done=False, path="")
        try:
            os.makedirs(JAVA_DIR, exist_ok=True)
            zip_path = os.path.join(JAVA_DIR, "temurin21.zip")
            req = urllib.request.Request(JAVA_DOWNLOAD_URL, headers={"User-Agent": "BedWarsPanel/2.2.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(zip_path, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                self._set(total=total)
                downloaded = 0
                while True:
                    chunk = r.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    self._set(downloaded=downloaded)
            self._set(phase="解压中")
            target = os.path.join(JAVA_DIR, "temurin21")
            if os.path.isdir(target):
                shutil.rmtree(target)
            os.makedirs(target, exist_ok=True)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(target)
            java_exe = None
            for root, dirs, files in os.walk(target):
                if "java.exe" in files and os.path.basename(root).lower() == "bin":
                    java_exe = os.path.join(root, "java.exe")
                    break
            if not java_exe:
                raise RuntimeError("解压后没有找到 bin/java.exe")
            self._set(path=java_exe)
            CFG["java_path"] = java_exe
            save_config(CFG)
            self._set(phase="完成", done=True, downloaded=downloaded, total=downloaded or total)
        except Exception as e:
            self._set(error="%r" % e, phase="失败")
        finally:
            self._set(active=False)


# ---------------------------------------------------------------- plugin updater
PLUGIN_TARGETS = [
    {"id": "geyser", "label": "Geyser-Spigot", "prefix": "Geyser-Spigot", "kind": "geyser",
     "api": "https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest"},
    {"id": "floodgate", "label": "floodgate", "prefix": "floodgate-spigot", "kind": "geyser",
     "project": "floodgate", "filename": "floodgate-spigot.jar",
     "api": "https://download.geysermc.org/v2/projects/floodgate/versions/latest/builds/latest"},
    {"id": "viaversion", "label": "ViaVersion", "prefix": "ViaVersion", "kind": "modrinth", "slug": "viaversion"},
    {"id": "viabackwards", "label": "ViaBackwards", "prefix": "ViaBackwards", "kind": "modrinth", "slug": "viabackwards"},
]


def read_plugin_version(path):
    try:
        with zipfile.ZipFile(path) as z:
            for name in ("plugin.yml", "paper-plugin.yml"):
                if name in z.namelist():
                    text = z.read(name).decode("utf-8", "replace")
                    m = re.search(r"(?m)^version:\s*(.+)$", text)
                    if m:
                        return m.group(1).strip().strip("\"'")
    except Exception:
        pass
    return ""


def find_plugin_jar(plugins_dir, prefix):
    try:
        for f in sorted(os.listdir(plugins_dir)):
            if f.lower().endswith(".jar") and f.startswith(prefix):
                return os.path.join(plugins_dir, f)
    except Exception:
        pass
    return None


def modrinth_latest(slug):
    url = "https://api.modrinth.com/v2/project/%s/version" % slug
    req = urllib.request.Request(url, headers={"User-Agent": "BedWarsPanel/2.2.0"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    releases = [v for v in data if v.get("version_type") == "release"]
    pick = releases[0] if releases else data[0]
    for f in pick.get("files", []):
        if str(f.get("filename", "")).lower().endswith(".jar"):
            return pick.get("version_number", ""), f["url"], f["filename"]
    raise RuntimeError("Modrinth 里没有找到 jar")


def version_key(v):
    m = re.match(r"v?(\d+(?:\.\d+)*)", (v or "").strip().lower())
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def resolve_latest(target):
    if target.get("kind") == "geyser":
        req = urllib.request.Request(target["api"], headers={"User-Agent": "BedWarsPanel/2.2.0"})
        data = json.load(urllib.request.urlopen(req, timeout=30))
        ver = str(data.get("version") or "")
        build = data.get("build")
        if not ver or build is None:
            raise RuntimeError("Geyser API 没有返回版本信息")
        project = target.get("project") or "geyser"
        filename = target.get("filename") or ("Geyser-Spigot.jar" if project == "geyser" else project + "-spigot.jar")
        url = "https://download.geysermc.org/v2/projects/%s/versions/%s/builds/%s/downloads/spigot" % (project, ver, build)
        return ver, url, filename, "GeyserMC"
    slug = target.get("slug") or target.get("modrinth")
    ver, url, name = modrinth_latest(slug)
    return ver, url, name, "Modrinth"


class PluginUpdater:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"active": False, "phase": "", "downloaded": 0, "total": 0,
                      "results": [], "error": "", "done": False}
        self.checked = {}

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def _set(self, **kw):
        with self.lock:
            self.state.update(kw)

    def installed(self):
        plugins_dir = os.path.join(CFG["server_dir"], "plugins")
        out = []
        for t in PLUGIN_TARGETS:
            jar = find_plugin_jar(plugins_dir, t["prefix"])
            out.append({"id": t["id"], "label": t["label"],
                        "version": read_plugin_version(jar) if jar else "",
                        "installed": bool(jar), "path": jar or ""})
        return out

    def check(self):
        plugins_dir = os.path.join(CFG["server_dir"], "plugins")
        results = []
        for t in PLUGIN_TARGETS:
            jar = find_plugin_jar(plugins_dir, t["prefix"])
            cur = read_plugin_version(jar) if jar else ""
            item = {"id": t["id"], "label": t["label"], "installed": cur, "latest": "",
                    "update": False, "source": "", "filename": "", "url": "", "error": ""}
            try:
                latest, url, filename, source = resolve_latest(t)
                item.update({"latest": latest, "url": url, "filename": filename, "source": source})
                if not cur:
                    item["update"] = True
                elif version_key(latest) and version_key(cur):
                    item["update"] = version_key(latest) > version_key(cur)
                else:
                    item["update"] = latest != cur
            except Exception as e:
                item["error"] = str(e)
            results.append(item)
        with self.lock:
            self.checked = {r["id"]: r for r in results if r.get("url")}
        return results

    def start(self, ids):
        with self.lock:
            if self.state["active"]:
                return False, "已有更新任务在进行"
        targets = [t for t in PLUGIN_TARGETS
                   if t["id"] in (ids or []) and self.checked.get(t["id"], {}).get("update")]
        if not targets:
            return False, "请先检查更新，并勾选有新版本的插件"
        if SERVER.status()["running"]:
            return False, "服务器正在运行，请先关服再更新插件（jar 文件被占用）"
        self._set(active=True, phase="准备更新", downloaded=0, total=0, results=[], error="", done=False)
        threading.Thread(target=self._run, args=(targets,), daemon=True).start()
        return True, "开始更新 %d 个插件..." % len(targets)

    def _download(self, url, path):
        last = None
        for _ in range(3):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "BedWarsPanel/2.2.0",
                    "Accept": "application/java-archive,*/*",
                })
                with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
                    total = int(r.headers.get("Content-Length") or 0)
                    self._set(total=total)
                    downloaded = 0
                    while True:
                        chunk = r.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        self._set(downloaded=downloaded)
                if os.path.getsize(path) < 1000:
                    raise RuntimeError("下载内容过小")
                return
            except Exception as e:
                last = e
                try:
                    os.remove(path)
                except Exception:
                    pass
                time.sleep(1.2)
        raise RuntimeError("下载失败: %r" % (last,))

    def _run(self, targets):
        plugins_dir = os.path.join(CFG["server_dir"], "plugins")
        backup_dir = os.path.join(plugins_dir, "_disabled", "plugin-updates")
        os.makedirs(backup_dir, exist_ok=True)
        results = []
        try:
            for target in targets:
                label = target["label"]
                info = self.checked.get(target["id"]) or {}
                old_jar = find_plugin_jar(plugins_dir, target["prefix"])
                old_ver = read_plugin_version(old_jar) if old_jar else ""
                tmp = os.path.join(plugins_dir, ".panel-update-%s.tmp" % target["id"])
                try:
                    if not info.get("url"):
                        raise RuntimeError("请先检查更新")
                    self._set(phase="正在下载 %s（%s）" % (label, info.get("source", "")), downloaded=0, total=0)
                    self._download(info["url"], tmp)
                    if not read_plugin_version(tmp):
                        raise RuntimeError("下载的文件不是有效插件 jar")
                    if old_jar and os.path.exists(old_jar):
                        backup = os.path.join(backup_dir, os.path.basename(old_jar) + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
                        shutil.move(old_jar, backup)
                    for f in list(os.listdir(plugins_dir)):
                        if f.lower().endswith(".jar") and f.startswith(target["prefix"]) and f != info["filename"]:
                            try:
                                os.remove(os.path.join(plugins_dir, f))
                            except Exception:
                                pass
                    final_path = os.path.join(plugins_dir, info["filename"])
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    shutil.move(tmp, final_path)
                    results.append("%s: %s -> %s  OK（%s）" % (label, old_ver or "未安装", info.get("latest") or "?", info.get("source", "")))
                except Exception as e:
                    results.append("%s: 失败 %r" % (label, e))
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                self._set(results=list(results))
            self._set(phase="完成", done=True)
        except Exception as e:
            self._set(error="%r" % e, phase="失败")
        finally:
            self._set(active=False)


# ---------------------------------------------------------------- players
def _sqlite_rows(path, sql):
    # read-only snapshot: works even while the plugin holds a write lock on Windows
    try:
        uri = "file:///" + path.replace("\\", "/").lstrip("/") + "?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True, timeout=2)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()
    except Exception:
        pass
    try:
        conn = sqlite3.connect(path, timeout=2)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()
    except Exception:
        return []


def load_player_overview(server_dir):
    players = {}
    by_uuid = {}

    def ensure(name, uuid=""):
        if not name:
            return None
        key = name.lower()
        p = players.get(key)
        if p is None:
            p = {"name": name, "uuid": (uuid or "").lower(), "level": None, "xp": None,
                 "next_cost": None, "whitelisted": False, "whitelist_ban": False, "ban": None}
            players[key] = p
        if uuid and not p["uuid"]:
            p["uuid"] = uuid.lower()
        if p["uuid"]:
            by_uuid[p["uuid"]] = p
        return p

    try:
        import json as _json
        with open(os.path.join(server_dir, "usercache.json"), "r", encoding="utf-8") as f:
            for e in _json.load(f):
                ensure(e.get("name"), e.get("uuid", ""))
    except Exception:
        pass

    shop_db = os.path.join(server_dir, "plugins", "BedWars1058", "Cache", "shop.db")
    stats = _sqlite_rows(shop_db, "SELECT name, uuid FROM global_stats")
    for name, uuid in stats:
        ensure(name, uuid)
    for uuid, level, xp, cost in _sqlite_rows(
            shop_db, "SELECT uuid, level, xp, next_cost FROM player_levels ORDER BY id DESC"):
        p = by_uuid.get(str(uuid).lower())
        if p is not None and p["level"] is None:
            p["level"] = level
            p["xp"] = xp
            p["next_cost"] = cost

    wl_db = os.path.join(server_dir, "plugins", "IpacWhitelist", "Data.sqlite3")
    for name, uuid, ban in _sqlite_rows(wl_db, "SELECT Name, UUID, Ban FROM player"):
        p = ensure(name, uuid)
        if p is not None:
            p["whitelisted"] = True
            p["whitelist_ban"] = int(ban or 0) != 0

    abz_db = os.path.join(server_dir, "plugins", "AdvancedBanZ", "data", "storage.db")
    now = int(time.time() * 1000)
    for name, uuid, reason, operator, ptype, end in _sqlite_rows(
            abz_db, "SELECT name, uuid, reason, operator, punishmentType, end FROM Punishments"):
        if "BAN" not in str(ptype).upper():
            continue
        try:
            endv = int(end)
        except Exception:
            endv = -1
        if endv > 0 and endv < now:
            continue
        p = ensure(name, uuid)
        if p is not None:
            p["ban"] = {"reason": reason, "operator": operator, "type": ptype, "end": endv}

    return sorted(players.values(), key=lambda x: (-(x["level"] or 0), x["name"].lower()))


def _sqlite_exec(path, sql, params=()):
    for _ in range(4):
        try:
            conn = sqlite3.connect(path, timeout=5)
            try:
                conn.execute(sql, params)
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception:
            time.sleep(0.5)
    return False


def _find_player(server_dir, name):
    key = name.lower()
    for p in load_player_overview(server_dir):
        if p["name"].lower() == key:
            return p
    return None


# ---------------------------------------------------------------- HTTP server
CFG = load_config()
SERVER = ServerManager(CFG)
DOWNLOADER = Downloader(CFG)
JAVA_DOWNLOADER = JavaDownloader()
UPDATER = PluginUpdater()
TOKEN = os.urandom(8).hex()

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BedWars 服务器面板</title>
<link rel="icon" type="image/png" href="/assets/logo.png">
<style>
:root{--bg:#070a14;--card:rgba(16,22,44,.42);--card2:rgba(255,255,255,.05);--line:rgba(150,190,255,.18);--txt:#eaf2ff;--muted:#a9b8d6;--green:#5ef0b0;--red:#ff7a97;--yellow:#ffd479;--blue:#8ec8ff;--accent:#ff9ed2;--accent2:#8ec8ff;--radius:16px}
*{box-sizing:border-box}
html{background:#070a14}
body{margin:0;min-height:100vh;font:14px/1.6 "Microsoft YaHei",system-ui,sans-serif;color:var(--txt);background:transparent;text-shadow:0 1px 2px rgba(0,0,0,.45)}
body::before{content:"";position:fixed;inset:0;z-index:-2;pointer-events:none;background:#070a14 url("data:image/webp;base64,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") center center/cover no-repeat;filter:brightness(1.44) saturate(1.1)}
body::after{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:radial-gradient(1100px 680px at 86% -4%,rgba(255,140,200,.30),transparent 62%),radial-gradient(1000px 640px at 6% 8%,rgba(110,170,255,.28),transparent 64%),linear-gradient(120deg,rgba(96,146,255,.14),rgba(255,140,200,.14)),linear-gradient(180deg,rgba(6,10,22,.14) 0%,rgba(6,10,22,.38) 46%,rgba(6,10,22,.56) 100%),repeating-linear-gradient(0deg,rgba(180,210,255,.028) 0 1px,transparent 1px 46px),repeating-linear-gradient(90deg,rgba(180,210,255,.02) 0 1px,transparent 1px 46px)}
::selection{background:rgba(255,158,210,.35)}
header{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr) minmax(0,1fr);grid-template-areas:"title quote status";align-items:center;padding:14px 22px;background:linear-gradient(180deg,rgba(12,16,34,.56),rgba(8,11,24,.34));border-bottom:1px solid var(--line);position:sticky;top:0;z-index:20;backdrop-filter:blur(24px) saturate(160%);-webkit-backdrop-filter:blur(24px) saturate(160%);box-shadow:0 10px 40px rgba(0,0,0,.28)}
h1{grid-area:title;font-size:19px;margin:0;letter-spacing:.5px;color:#f2f8ff;text-shadow:0 0 26px rgba(142,200,255,.45);min-width:0;white-space:nowrap;display:flex;align-items:center;gap:9px}
.brand-logo{width:36px;height:36px;flex:none;border-radius:10px;object-fit:cover;border:1px solid rgba(165,205,255,.35);box-shadow:0 0 18px rgba(142,200,255,.55),0 4px 14px rgba(0,0,0,.35)}
.hitokoto-head{grid-area:quote;display:flex;align-items:center;justify-content:center;min-width:0;padding:0 24px;cursor:text}
.hitokoto-head:hover #hitokotoText{color:#fff}
#hitokotoText{display:block;box-sizing:border-box;width:100%;text-align:center;min-width:0;max-width:100%;padding:2px 8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:15px;font-weight:400;font-style:italic;color:#eef6ff;letter-spacing:.2px}
@media(max-width:900px){header{grid-template-columns:1fr auto;grid-template-areas:"title status"}.hitokoto-head{display:none}}
h1 .ver{font-size:14px;color:#a9d4ff;font-weight:400;margin-left:10px}
.home-layout{display:flex;gap:16px;align-items:flex-start}
.home-main{flex:1;min-width:0}
.home-side{width:380px;flex:none}
@media(max-width:1100px){.home-layout{flex-wrap:wrap}.home-side{width:100%}}
.about{margin-top:12px;padding:10px 6px 4px;border-top:1px solid var(--line);color:var(--muted);font-size:11.5px;line-height:1.8;text-align:center}
#statusPill{grid-area:status;justify-self:end;display:inline-flex;align-items:center;gap:8px;padding:6px 14px;border-radius:999px;font-size:13px;color:var(--txt);background:rgba(16,22,44,.38);border:1px solid var(--line);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);box-shadow:0 0 24px rgba(142,200,255,.14)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;background:#888;box-shadow:0 0 12px rgba(255,255,255,.35)}
.wrap{display:flex;gap:16px;padding:18px;align-items:flex-start;max-width:1500px;margin:0 auto}
nav{width:196px;flex:none;padding:10px;position:sticky;top:86px;border:1px solid var(--line);border-radius:18px;background:linear-gradient(180deg,rgba(22,30,56,.40),rgba(8,12,26,.36));backdrop-filter:blur(26px) saturate(150%);-webkit-backdrop-filter:blur(26px) saturate(150%);box-shadow:0 14px 44px rgba(0,0,0,.30),inset 0 1px 0 rgba(255,255,255,.08)}
nav button{position:relative;display:block;width:100%;text-align:left;background:transparent;border:0;color:var(--muted);padding:10px 12px;border-radius:10px;cursor:pointer;font-size:13.5px;transition:background .18s,color .18s,box-shadow .18s}
nav button:hover{background:rgba(142,200,255,.10);color:var(--txt)}
nav button.active{background:linear-gradient(90deg,rgba(255,158,210,.22),rgba(142,200,255,.16));color:#fff;font-weight:600;box-shadow:inset 0 0 0 1px rgba(255,158,210,.28),0 0 26px rgba(142,200,255,.20)}
nav button.active::before{content:"";position:absolute;left:0;top:22%;bottom:22%;width:3px;border-radius:3px;background:linear-gradient(180deg,var(--accent),var(--accent2));box-shadow:0 0 10px rgba(255,158,210,.9)}
.power-btns{margin-top:10px;padding-top:10px;border-top:1px solid var(--line);display:flex;flex-direction:column;gap:7px}
.power-btns .btn{width:100%;padding:8px 10px;font-size:12.5px;justify-content:center;display:flex;align-items:center;gap:6px}
#dirtyBar{display:none;position:fixed;left:50%;top:76px;transform:translateX(-50%);z-index:60;padding:9px 18px;border-radius:12px;background:rgba(255,196,90,.14);border:1px solid rgba(255,212,121,.42);color:#ffe6ad;font-size:12.5px;backdrop-filter:blur(16px);box-shadow:0 10px 30px rgba(0,0,0,.28);white-space:nowrap}
main{flex:1;min-width:0}
section{display:none}
section.active{display:block}
.card{position:relative;padding:18px;margin-bottom:16px;border:1px solid rgba(165,205,255,.18);border-radius:var(--radius);background:linear-gradient(180deg,rgba(26,34,64,.20),rgba(8,12,26,.26));backdrop-filter:blur(32px) saturate(155%);-webkit-backdrop-filter:blur(28px) saturate(155%);box-shadow:0 16px 50px rgba(0,0,0,.34),inset 0 1px 0 rgba(255,255,255,.10)}
.card::before{content:"";position:absolute;left:18px;right:18px;top:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,158,210,.75),rgba(142,200,255,.75),transparent)}
.card h2{display:flex;align-items:center;gap:9px;font-size:14.5px;margin:0 0 14px;color:#f0f7ff;font-weight:600;letter-spacing:.3px}
.card h2::before{content:"";width:4px;height:15px;border-radius:3px;background:linear-gradient(180deg,var(--accent),var(--accent2));box-shadow:0 0 12px rgba(255,158,210,.75)}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
button.btn{background:linear-gradient(180deg,rgba(142,200,255,.16),rgba(255,158,210,.07));border:1px solid rgba(165,205,255,.30);color:#eef6ff;padding:8px 16px;border-radius:10px;cursor:pointer;font-size:13px;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);transition:transform .16s,background .16s,box-shadow .16s,border-color .16s;box-shadow:inset 0 1px 0 rgba(255,255,255,.10)}
button.btn:hover{background:linear-gradient(180deg,rgba(142,200,255,.26),rgba(255,158,210,.12));border-color:rgba(190,220,255,.55);box-shadow:0 8px 26px rgba(90,150,255,.22),inset 0 1px 0 rgba(255,255,255,.14);transform:translateY(-1px)}
button.btn:active{transform:translateY(0)}
button.btn.primary{background:linear-gradient(120deg,rgba(255,158,210,.62),rgba(142,200,255,.52));border-color:rgba(205,225,255,.6);color:#fff;box-shadow:0 8px 28px rgba(120,150,255,.30),inset 0 1px 0 rgba(255,255,255,.22)}
button.btn.green{border-color:rgba(142,200,255,.45);color:#cfe9ff}
button.btn.red{border-color:rgba(255,158,210,.45);color:#ffd6ea}
button.btn.yellow{border-color:rgba(180,200,255,.40);color:#e7eeff}
button.btn:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none}
.kv{display:grid;grid-template-columns:150px 1fr;gap:6px 12px;font-size:13px}
.kv .k{color:var(--muted)}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;background:rgba(142,200,255,.14);border:1px solid rgba(142,200,255,.24)}
textarea,input[type=text],input[type=number],select{background:rgba(8,12,26,.38);border:1px solid var(--line);color:var(--txt);border-radius:10px;padding:9px 11px;font:13px/1.5 Consolas,"Microsoft YaHei",monospace;width:100%;backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);transition:border-color .16s,box-shadow .16s}
textarea:focus,input[type=text]:focus,input[type=number]:focus,select:focus{outline:none;border-color:rgba(142,200,255,.62);box-shadow:0 0 0 3px rgba(142,200,255,.16)}
textarea{resize:vertical;min-height:220px;white-space:pre}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
.field label{display:block;font-size:12px;color:var(--muted);margin-bottom:4px}
input.ro{opacity:.6;cursor:not-allowed;background:rgba(6,9,20,.45)}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;align-items:center}
.hint{color:var(--muted);font-size:12px}
#log{background:rgba(4,7,18,.48);border:1px solid var(--line);border-radius:14px;padding:12px;height:calc(100vh - 260px);overflow:auto;font:12px/1.55 Consolas,monospace;white-space:pre-wrap;word-break:break-all;backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);box-shadow:inset 0 0 44px rgba(110,170,255,.07)}
.map-item{display:flex;justify-content:space-between;align-items:center;background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin-bottom:8px;cursor:pointer;transition:.16s;backdrop-filter:blur(12px)}
.map-item:hover{border-color:rgba(255,158,210,.55);background:rgba(255,158,210,.08);box-shadow:0 0 24px rgba(142,200,255,.18)}
.ptable{width:100%;border-collapse:collapse;font-size:13px}
.ptable th,.ptable td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left}
.ptable th{color:var(--muted);font-weight:500}
.ptable tr:hover{background:rgba(142,200,255,.07)}
.log-err{color:#ff9db0}
.log-warn{color:#ffd6a1}
.log-info{color:#a9e6ff}
.log-cmd{color:#ffb8e0}
.toast{position:fixed;right:22px;bottom:22px;background:rgba(10,14,30,.60);border:1px solid var(--line);border-left:4px solid var(--accent);padding:12px 16px;border-radius:12px;max-width:460px;display:none;z-index:99;white-space:pre-wrap;backdrop-filter:blur(22px) saturate(150%);-webkit-backdrop-filter:blur(22px) saturate(150%);box-shadow:0 16px 48px rgba(0,0,0,.42)}
.toast.ok{border-left-color:var(--green)}.toast.err{border-left-color:var(--red)}
progress{width:100%;height:16px;accent-color:var(--accent2)}
.tabs{display:flex;gap:8px;margin-bottom:10px;padding:5px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.03);backdrop-filter:blur(14px)}
.tabs button{flex:1;padding:7px;border-radius:8px;border:1px solid transparent;background:transparent;color:var(--muted);cursor:pointer;transition:.16s}
.tabs button:hover{color:var(--txt);background:rgba(142,200,255,.08)}
.tabs button.active{background:linear-gradient(180deg,rgba(255,158,210,.26),rgba(142,200,255,.16));color:#fff;border-color:rgba(255,158,210,.32);box-shadow:0 0 20px rgba(142,200,255,.18)}
code{background:rgba(142,200,255,.14);border:1px solid rgba(142,200,255,.24);padding:1px 6px;border-radius:6px;font-family:Consolas,monospace;font-size:12.5px;color:#dcecff}
.alert-warn{margin-top:12px;padding:11px 14px;border:1px solid rgba(255,212,121,.32);background:linear-gradient(180deg,rgba(255,212,121,.11),rgba(255,212,121,.04));border-radius:12px;backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(142,200,255,.28);border-radius:8px;border:2px solid transparent;background-clip:content-box}
::-webkit-scrollbar-thumb:hover{background:rgba(142,200,255,.45);background-clip:content-box}
</style>
</head>
<body>
<div id="dirtyBar">⚠ 当前页面有未保存的修改，请点击页面里的「保存」按钮</div>
<header>
  <h1><img class="brand-logo" src="/assets/logo.png" alt="logo">BedWars 服务器面板 <span class="ver">v__VERSION__</span></h1>
  <div class="hitokoto-head" id="hitokotoBox" title="双击换一句（可选中复制）">
    <span id="hitokotoText">加载中...</span>
  </div>
  <div id="statusPill"><span class="dot"></span>检测中...</div>
</header>
<div class="wrap">
<nav>
  <button class="active" data-tab="home">🏠 状态 / 控制</button>
  <button data-tab="console">📜 控制台</button>
  <button data-tab="players">👥 玩家管理</button>
  <button data-tab="plugins">🧩 插件配置</button>
  <button data-tab="gen">⚙ 资源生成器</button>
  <button data-tab="shop">🛒 商店编辑</button>
  <button data-tab="maps">🗺 地图管理</button>
  <button data-tab="settings">🔧 面板设置</button>
  <button data-tab="help">📖 使用说明</button>
  <div class="power-btns">
    <button class="btn" id="btnExitPanel">⏻ 退出面板</button>
    <button class="btn red" id="btnExitStop">⏻ 退出面板并关服</button>
  </div>
  <div class="about">
    v__VERSION__<br>
    © 2024-2026 黑色的传说<br>
    GNU GPL v3 开源
  </div>
</nav>
<main>
  <section id="home" class="active">
    <div class="home-layout">
      <div class="home-main">
    <div class="card">
      <h2>服务器状态</h2>
      <div class="kv" id="statusKv"></div>
      <div class="row" style="margin-top:14px">
        <button class="btn green" id="btnStart">▶ 开服</button>
        <button class="btn red" id="btnStop">■ 关服</button>
        <button class="btn" id="btnEula">同意 EULA</button>
        <button class="btn yellow" id="btnGoDownload">⬇ 下载核心</button>
        <button class="btn" id="btnVanilla">🖥 打开原版控制台</button>
        <button class="btn yellow" id="javaDownloadTop">⬇ 下载 Java</button>
        <button class="btn" id="btnRefresh">刷新</button>
      </div>
      <div id="jarWarn" class="alert-warn" style="display:none">
        ⚠️ 当前没有 <code>server.jar</code>，需要先下载核心才能开服。
        <button class="btn yellow" id="btnJarWarnDownload" style="margin-left:10px">去下载核心</button>
      </div>
    </div>
    <div class="card">
      <h2>最近日志 / 控制台</h2>
      <div class="toolbar">
        <input type="text" id="cmdInputHome" placeholder="输入服务器指令，例如 list / bw reload / authme reload" style="max-width:520px">
        <button class="btn primary" id="cmdSendHome">发送指令</button>
        <button class="btn" id="openLogTab">打开控制台</button>
      </div>
      <div id="homeLog" style="height:220px;overflow:auto;font:12px/1.5 Consolas,monospace;color:#a9b6d6;white-space:pre-wrap"></div>
      <p class="hint" style="margin-top:6px">只有用面板启动的服务器才能输入指令；更多行数请点「打开控制台」。</p>
    </div>
      </div>
      <div class="home-side">
        <div class="card">
          <h2>服务器基本配置</h2>
          <div id="homeConfigFields"></div>
          <div class="row" style="margin-top:12px"><button class="btn primary" id="homeConfigSave">保存配置</button></div>
          <p class="hint">Java / 基岩版 / 语音端口改完需重启服务器；端口映射也要同步修改。</p>
        </div>
        <div class="card">
          <h2>Java 环境</h2>
          <div class="kv" id="javaInfoHome"></div>
          <div class="toolbar" style="margin-top:10px">
            <select id="javaCandsHome" style="max-width:100%"></select>
          </div>
          <div class="row" style="margin-top:8px">
            <button class="btn" id="javaUseHome">使用选中版本</button>
          </div>
          <div class="hint" id="javaProgressHome" style="margin-top:8px"></div>
        </div>
      </div>
    </div>
  </section>

  <section id="gen">
    <div class="card">
      <h2>资源生成器 generators.yml</h2>
      <div class="toolbar">
        <button class="btn" id="genReload">重新读取</button>
        <button class="btn primary" id="genSave">保存</button>
        <span class="hint">直接改数值后保存，自动备份 .bak</span>
      </div>
      <div class="grid" id="genGrid"></div>
      <div style="margin-top:14px">
        <div class="toolbar"><button class="btn" id="genRawToggle">显示/隐藏原始文本</button></div>
        <textarea id="genRaw" style="display:none;min-height:300px"></textarea>
      </div>
    </div>
  </section>

  <section id="shop">
    <div class="card">
      <h2>商店编辑 shop.yml（UI）</h2>
      <div class="toolbar">
        <button class="btn" id="shopReload">重新读取</button>
        <button class="btn green" id="shopAddOpen">＋ 新增物品</button>
        <span class="hint">选分类 → 点物品 → 改价格/物品/中文名 → 保存，自动备份</span>
      </div>
      <div class="tabs" id="shopCats"></div>
      <div class="grid" id="shopItems"></div>
    </div>
    <div class="card" id="shopAddCard" style="display:none">
      <h2>新增物品</h2>
      <div class="grid" id="shopAddFields"></div>
      <div class="row" style="margin-top:12px">
        <button class="btn primary" id="shopAddSave">创建物品</button>
        <button class="btn" id="shopAddCancel">取消</button>
      </div>
      <p class="hint">物品 ID 用英文（如 gold-apple）；中文名/描述会写入 messages_zh_cn.yml。创建后游戏内需 /bw reload。</p>
    </div>
    <div class="card" id="shopEditCard" style="display:none">
      <h2 id="shopEditTitle">编辑物品</h2>
      <div class="grid" id="shopEditFields"></div>
      <div class="row" style="margin-top:12px">
        <button class="btn primary" id="shopSaveItem">保存物品</button>
        <button class="btn" id="shopCancelEdit">取消</button>
      </div>
    </div>
    <div class="card">
      <h2>特殊物品 shop-specials</h2>
      <div class="grid" id="shopSpecials"></div>
    </div>
    <div class="card">
      <h2>高级：原文编辑</h2>
      <div class="toolbar">
        <select id="rawFileSel" style="max-width:260px">
          <option value="plugins/BedWars1058/shop.yml">shop.yml</option>
          <option value="plugins/BedWars1058/upgrades2.yml">upgrades2.yml</option>
        </select>
        <button class="btn" id="rawLoad">读取</button>
        <button class="btn primary" id="rawSave">保存</button>
      </div>
      <textarea id="shopText" style="min-height:420px;display:none"></textarea>
    </div>
  </section>

  <section id="maps">
    <div class="card">
      <h2>地图管理（按分组）</h2>
      <div class="toolbar">
        <button class="btn" id="mapsReload">刷新</button>
        <span class="hint">按竞技场 group 字段分组；点地图编辑基础配置</span>
      </div>
      <div id="mapGroups"></div>
    </div>
    <div class="card" id="mapEditCard" style="display:none">
      <h2 id="mapEditTitle">编辑地图</h2>
      <div class="grid" id="mapEditFields"></div>
      <div class="row" style="margin-top:12px">
        <button class="btn primary" id="mapSave">保存地图配置</button>
        <button class="btn" id="mapCancel">取消</button>
      </div>
    </div>
    <div class="card" id="mapRawCard" style="display:none">
      <h2 id="mapRawTitle">地图原文</h2>
      <textarea id="mapRaw" style="min-height:420px"></textarea>
      <div class="row" style="margin-top:10px">
        <button class="btn primary" id="mapRawSave">保存原文</button>
        <button class="btn" id="mapRawClose">关闭</button>
      </div>
    </div>
    <div class="card">
      <h2>分组管理（config.yml 的 arenaGroups）</h2>
      <div class="toolbar">
        <input type="text" id="newGroup" placeholder="新分组名称" style="max-width:280px">
        <button class="btn primary" id="addGroup">添加分组</button>
      </div>
      <div id="groupList" style="margin-top:10px"></div>
      <p class="hint">删除分组前需要先把该分组下的地图改到别的分组。</p>
    </div>
  </section>

  <section id="players">
    <div class="card">
      <h2>玩家管理</h2>
      <div class="toolbar">
        <input type="text" id="playerSearch" placeholder="搜索玩家名..." style="max-width:220px">
        <button class="btn" id="playersRefresh">刷新</button>
        <input type="text" id="playerAddWl" placeholder="输入玩家名添加白名单" style="max-width:220px">
        <button class="btn" id="playerAddWlBtn">添加白名单</button>
        <span class="hint" id="playersStatus"></span>
      </div>
      <div id="playerTable"></div>
      <p class="hint">BW 等级读取 BedWars <code>Cache/shop.db</code>；白名单来自 IpacWhitelist；封禁来自 AdvancedBanZ。</p>
      <p class="hint">白名单 / 封禁操作需要面板启动的服务器；操作后稍等自动刷新。</p>
    </div>
  </section>

  <section id="plugins">
    <div class="card">
      <h2>插件更新（Geyser / Floodgate / Via 系列）</h2>
      <p class="hint">先点「检查更新」，确认有新版本后再更新。更新前请先关服，旧 jar 会备份到 plugins/_disabled/plugin-updates/。</p>
      <div class="grid" id="updateChecks"><p class="hint">尚未检查更新。</p></div>
      <div class="row" style="margin-top:12px">
        <button class="btn" id="updateCheck">🔍 检查更新</button>
        <button class="btn primary" id="updateRun" disabled>更新选中插件</button>
        <span class="hint" id="updateStatus"></span>
      </div>
    </div>
    <div class="card">
      <h2>插件配置（常用项）</h2>
      <p class="alert-warn" style="margin-bottom:12px">⚠️ 不确定的配置项不要乱改。保存会自动备份，但改错仍可能导致插件报错或无法启动。</p>
      <div class="toolbar">
        <select id="formSel" style="max-width:340px"></select>
        <button class="btn" id="formLoad">重新读取</button>
        <button class="btn primary" id="formSave">保存</button>
        <span class="hint" id="formNote"></span>
      </div>
      <div class="grid" id="formFields"></div>
    </div>
  </section>

  <section id="console">
    <div class="card">
      <h2>控制台</h2>
      <div class="toolbar">
        <button class="btn" id="logRefresh">刷新</button>
        <button class="btn" id="logClear">清空显示</button>
        <label class="hint"><input type="checkbox" id="logAuto" checked> 自动刷新</label>
        <span class="hint">只有用面板启动的服务器才能输入指令</span>
      </div>
      <div id="log"></div>
      <div class="toolbar" style="margin-top:10px">
        <input type="text" id="cmdInput" placeholder="输入服务器指令，例如 list / bw reload / authme reload" style="flex:1;max-width:none">
        <button class="btn primary" id="cmdSend" onclick="sendConsoleCommand('cmdInput')">发送指令</button>
      </div>
    </div>
  </section>

  <section id="settings">
    <div class="card">
      <h2>面板设置</h2>
      <div class="grid">
        <div class="field"><label>服务器目录</label><input type="text" id="cfgDir"></div>
        <div class="field"><label>Java 路径</label><input type="text" id="cfgJava"></div>
        <div class="field"><label>最小内存</label><input type="text" id="cfgMin"></div>
        <div class="field"><label>最大内存</label><input type="text" id="cfgMax"></div>
        <div class="field"><label>Paper 版本（已锁定）</label><input type="text" id="cfgPaper" readonly class="ro"></div>
        <div class="field"><label>Paper 构建号（已锁定）</label><input type="text" id="cfgBuild" readonly class="ro"></div>
      </div>
      <div class="row" style="margin-top:14px"><button class="btn primary" id="cfgSave">保存设置</button></div>
      <p class="hint" style="margin-top:10px">服务器目录必须包含 <code>server.jar</code> 和 <code>plugins/</code>。修改后需重启面板生效。</p>
      <p class="hint">Paper 版本 / 构建号已锁定，不能在这里改（防止填错导致下载失败）。如需更换，请手动编辑 <code>panel\panel_config.json</code> 后重启面板。</p>
      <p class="hint">当前 server.jar 实际版本：<b id="jarVer">-</b></p>
    </div>
    <div class="card">
      <h2>下载 Paper 核心（自动命名为 server.jar）</h2>
      <p class="hint">从 PaperMC 官方 API 下载，不内置核心文件；会先备份旧 server.jar。版本/构建号读取上面的设置。</p>
      <div class="row">
        <span>目标版本：<b id="dlVersion">-</b></span>
        <button class="btn primary" id="btnDownload">下载最新稳定版</button>
      </div>
      <div style="margin-top:14px">
        <progress id="dlProgress" value="0" max="100"></progress>
        <div class="hint" id="dlText" style="margin-top:6px">空闲</div>
      </div>
      <div class="hint" id="jarInfo" style="margin-top:10px"></div>
    </div>
    <div class="card">
      <h2>Java 环境检测 / 下载</h2>
      <div class="kv" id="javaInfo"></div>
      <div class="toolbar" style="margin-top:12px">
        <select id="javaCands" style="max-width:520px"></select>
        <button class="btn" id="javaUse">使用选中版本</button>
        <button class="btn yellow" id="javaDownload">下载 Temurin 21 JDK</button>
      </div>
      <div class="hint" id="javaProgress" style="margin-top:8px"></div>
      <p class="hint">下载约 190MB，解压到 panel\java\temurin21，完成后自动切换 Java 路径；重启面板生效。</p>
    </div>
    <div class="card">
      <h2>关于</h2>
      <div class="kv">
        <div class="k">项目</div><div>BedWars 服务器面板</div>
        <div class="k">版本</div><div>v__VERSION__</div>
        <div class="k">作者</div><div>黑色的传说</div>
        <div class="k">开源协议</div><div>GNU GPL v3（GPL-3.0）</div>
        <div class="k">版权</div><div>Copyright (C) 2024-2026 黑色的传说</div>
        <div class="k">项目主页</div><div><a href="https://www.minebbs.com/resources/10218/" target="_blank" rel="noopener" style="color:#5aa9ff">MineBBS 资源页</a></div>
      </div>
      <p class="hint" style="margin-top:10px">本面板属于整合包原创部分，按 GNU GPL v3 开源；第三方插件版权归各自原作者所有。</p>
    </div>
  </section>
  <section id="help">
    <div class="card">
      <h2>📖 使用说明</h2>
      <div class="kv">
        <div class="k">启动面板</div><div>双击 ServerPanel.exe；面板只监听本机 127.0.0.1。</div>
        <div class="k">首次开服</div><div>先「同意 EULA」→「下载核心」→「▶ 开服」。</div>
        <div class="k">控制台</div><div>面板启动的服务器才能输入指令；start.bat 启动的请用「打开原版控制台」。</div>
        <div class="k">配置修改</div><div>保存会自动生成 .bak-时间戳 备份；端口类修改后必须重启服务器。</div>
        <div class="k">插件更新</div><div>先检查更新，再勾选更新；更新前关服，更新后重启服务器。</div>
        <div class="k">玩家管理</div><div>BW 等级读取 BedWars 统计；白名单/封禁操作需要面板启动的服务器。</div>
      </div>
    </div>
    <div class="card">
      <h2>常见问题</h2>
      <div class="kv">
        <div class="k">端口冲突</div><div>在首页「服务器基本配置」修改 Java / 基岩版 / 语音端口。</div>
        <div class="k">插件没生效</div><div>配置改完执行对应 reload；替换 jar 后必须重启服务器。</div>
        <div class="k">日志乱码</div><div>面板已按 GBK 解码服务器输出。</div>
        <div class="k">备份位置</div><div>配置文件备份在原目录 .bak-时间戳；插件旧版本在 plugins/_disabled/。</div>
      </div>
    </div>
  </section>

</main>
</div>
<div class="toast" id="toast"></div>
<script>
const TOKEN = "__TOKEN__";
const SAVE_POST_PATHS = new Set([
  '/api/settings', '/api/file', '/api/shop', '/api/shop/add', '/api/forms',
  '/api/homeconfig', '/api/generators', '/api/arena', '/api/arena/raw',
  '/api/arena/group', '/api/groups', '/api/maps'
]);
function markDirty(){
  window.__dirty = true;
  const bar = document.getElementById('dirtyBar');
  if(bar) bar.style.display = 'block';
}
function clearDirty(){
  window.__dirty = false;
  const bar = document.getElementById('dirtyBar');
  if(bar) bar.style.display = 'none';
}
async function api(path, opts={}){
  opts.headers = Object.assign({'X-Panel-Token': TOKEN}, opts.headers||{});
  if(opts.body && typeof opts.body === 'object'){ opts.headers['Content-Type']='application/json'; opts.body=JSON.stringify(opts.body); }
  const r = await fetch(path, opts);
  const j = await r.json().catch(()=>({ok:false,error:'bad json'}));
  if(j.ok && opts.method==='POST' && SAVE_POST_PATHS.has(path.split('?')[0])) clearDirty();
  return j;
}
function toast(msg, ok=true){
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast ' + (ok?'ok':'err'); t.style.display='block';
  clearTimeout(window.__toastT); window.__toastT = setTimeout(()=>t.style.display='none', 5000);
}
document.querySelectorAll('nav button[data-tab]').forEach(b=>b.onclick=()=>{
  if(window.__dirty && !confirm('当前页面有未保存的修改，确定放弃并切换？\n\n建议先点击当前页面的「保存」按钮。')) return;
  clearDirty();
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  document.getElementById(b.dataset.tab).classList.add('active');
  if(b.dataset.tab==='gen') loadGenerators();
  if(b.dataset.tab==='shop') loadShop();
  if(b.dataset.tab==='maps') loadMaps();
  if(b.dataset.tab==='settings') { loadSettings(); loadJava(); }
  if(b.dataset.tab==='plugins') { loadForms(); loadUpdates(); }
  if(b.dataset.tab==='home') { loadHomeConfig(); loadJavaHome(); }
  if(b.dataset.tab==='console') loadLog();
  if(b.dataset.tab==='players') loadPlayers();
});
async function refreshStatus(){
  const s = await api('/api/status');
  const pill = document.getElementById('statusPill');
  if(s.stopping){ pill.innerHTML='<span class="dot" style="background:#ffc94d"></span>关闭中...'; }
  else if(s.running){ pill.innerHTML='<span class="dot" style="background:#3ddc84"></span>运行中' + (s.pid?('  PID '+s.pid):''); }
  else { pill.innerHTML='<span class="dot" style="background:#ff5c7a"></span>已停止'; }
  const kv = document.getElementById('statusKv');
  const rows = [
    ['服务器目录', s.server_dir],
    ['运行状态', s.running ? (s.managed?'面板管理':'外部进程') : '已停止'],
    ['PID', s.pid || '-'],
    ['端口 25565', s.port_open ? '监听中' : '未监听'],
    ['EULA', s.eula_ok ? '已同意' : '未同意'],
    ['server.jar', s.server_jar ? ('存在 ('+(s.server_jar_size/1024/1024).toFixed(1)+' MB)') : '不存在'],
    ['内存', s.memory],
    ['Java', s.java_ok ? '正常' : '路径无效'],
    ['运行时长', s.uptime ? (Math.floor(s.uptime/60)+' 分 '+s.uptime%60+' 秒') : '-'],
  ];
  kv.innerHTML = rows.map(r=>`<div class="k">${r[0]}</div><div>${r[1]}</div>`).join('');
  document.getElementById('btnStart').disabled = s.running || s.stopping;
  document.getElementById('btnStop').disabled = !s.running || s.stopping;
  document.getElementById('btnEula').disabled = s.eula_ok;
  document.getElementById('jarInfo').textContent = s.server_jar ? ('当前 server.jar: ' + (s.server_jar_version || '未知版本') + ' ('+(s.server_jar_size/1024/1024).toFixed(1)+' MB)') : '当前没有 server.jar';
  const warn = document.getElementById('jarWarn');
  if(warn) warn.style.display = s.server_jar ? 'none' : 'block';
  refreshHomeLog();
  if(document.getElementById('dlVersion')) document.getElementById('dlVersion').textContent = s.paper_version + (s.paper_build ? (' build ' + s.paper_build) : '');
  return s;
}
async function refreshHomeLog(){
  const r = await api('/api/log?n=20');
  if(!r.ok) return;
  const el = document.getElementById('homeLog');
  if(el) el.innerHTML = renderLogLines((r.lines || []).slice(-20));
}
document.getElementById('btnStart').onclick = async()=>{
  const r = await api('/api/start',{method:'POST',body:{}});
  toast(r.message || r.error, r.ok); setTimeout(refreshStatus,1500);
};
document.getElementById('btnStop').onclick = async()=>{
  if(!confirm('确定要关闭服务器吗？')) return;
  const r = await api('/api/stop',{method:'POST',body:{}});
  toast(r.message || r.error, r.ok); setTimeout(refreshStatus,1500);
};
document.getElementById('btnEula').onclick = async()=>{
  if(!confirm('点击确定表示你已阅读并同意 Minecraft EULA (https://aka.ms/MinecraftEULA)')) return;
  const r = await api('/api/eula',{method:'POST',body:{}});
  toast(r.message || r.error, r.ok); refreshStatus();
};
document.getElementById('btnRefresh').onclick = ()=>refreshStatus();
document.getElementById('btnVanilla').onclick = async()=>{
  if(!confirm('将在新窗口用 start.bat 启动服务器（面板将无法捕获其输出），继续？')) return;
  const r = await api('/api/openconsole',{method:'POST',body:{}});
  toast(r.message||r.error, r.ok);
};
function gotoDownloadTab(){
  const btn = document.querySelector('nav button[data-tab="settings"]');
  if(btn) btn.click();
}
document.getElementById('btnGoDownload').onclick = gotoDownloadTab;
document.getElementById('btnJarWarnDownload').onclick = gotoDownloadTab;

// ---------------- download
async function dlStatus(){
  const d = await api('/api/download/status');
  const pct = d.total ? Math.min(100, Math.round(d.downloaded/d.total*100)) : (d.done?100:0);
  document.getElementById('dlProgress').value = pct;
  let txt = d.phase || '空闲';
  if(d.total) txt += `  ${(d.downloaded/1024/1024).toFixed(1)} / ${(d.total/1024/1024).toFixed(1)} MB`;
  if(d.error) txt += '  |  错误: ' + d.error;
  document.getElementById('dlText').textContent = txt;
}
document.getElementById('btnDownload').onclick = async()=>{
  if(!confirm('将下载 Paper 最新稳定版并覆盖 server.jar（旧文件会备份），继续？')) return;
  const r = await api('/api/download',{method:'POST',body:{}});
  toast(r.message || r.error, r.ok);
};
setInterval(dlStatus, 1000);

// ---------------- generators
const GEN_FIELDS = __GEN_FIELDS__;
let genValues = {};
function renderGenGrid(){
  const grid = document.getElementById('genGrid');
  grid.innerHTML = GEN_FIELDS.map(f=>`<div class="field"><label>${f[1]}<br><span style="color:#56637f">${f[0]}</span></label><input type="text" data-path="${f[0]}" value="${genValues[f[0]]??''}"></div>`).join('');
}
async function loadGenerators(){
  const r = await api('/api/generators');
  if(!r.ok){ toast(r.error,false); return; }
  genValues = r.values;
  renderGenGrid();
  document.getElementById('genRaw').value = r.raw;
}
document.getElementById('genReload').onclick = loadGenerators;
document.getElementById('genRawToggle').onclick = ()=>{ const t=document.getElementById('genRaw'); t.style.display = t.style.display==='none'?'block':'none'; };
document.getElementById('genSave').onclick = async()=>{
  const values = {};
  document.querySelectorAll('#genGrid input').forEach(i=>values[i.dataset.path]=i.value);
  const r = await api('/api/generators',{method:'POST',body:{values}});
  toast(r.message || r.error, r.ok);
  if(r.ok){ loadGenerators(); }
};

// ---------------- shop UI
let shopModel = null;
let shopCat = null;
let editItemKey = null;
async function loadShop(){
  const r = await api('/api/shop');
  if(!r.ok){ toast(r.error,false); return; }
  shopModel = r;
  const cats = document.getElementById('shopCats');
  cats.innerHTML = r.categories.map(c=>`<button data-cat="${c.key}">${c.cn||c.key}</button>`).join('')
    + '<button data-cat="__specials__">特殊物品</button>';
  cats.querySelectorAll('button').forEach(b=>b.onclick=()=>{
    cats.querySelectorAll('button').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    shopCat = b.dataset.cat;
    renderShopItems();
  });
  if(r.categories.length){ shopCat = r.categories[0].key; cats.querySelector('button').classList.add('active'); }
  renderShopItems();
  renderSpecials(r.specials);
  renderAddFields();
}
function renderShopItems(){
  const box = document.getElementById('shopItems');
  document.getElementById('shopEditCard').style.display='none';
  document.getElementById('shopAddCard').style.display='none';
  if(shopCat==='__specials__'){ box.innerHTML='<p class="hint">特殊物品在下方单独编辑</p>'; return; }
  const cat = shopModel.categories.find(c=>c.key===shopCat);
  if(!cat){ box.innerHTML=''; return; }
  box.innerHTML = cat.items.map(it=>{
    const t = it.tiers[0] || {};
    return `<div class="map-item" data-item="${it.key}">
      <div><b>${it.name||it.key}</b> <span class="hint">(${it.key})</span>
      <div class="hint">槽位 ${it.slot} · ${t.material||''} x${t.amount||''} · ${t.cost||''} ${t.currency||''}</div></div>
      <div class="pill">编辑</div></div>`;
  }).join('');
  box.querySelectorAll('.map-item').forEach(el=>el.onclick=()=>openShopItem(cat, el.dataset.item));
}
function openShopItem(cat, itemKey){
  const it = cat.items.find(i=>i.key===itemKey);
  if(!it) return;
  editItemKey = itemKey;
  const root = cat.key + '.category-content.' + it.key;
  const fields = [];
  fields.push(['content-settings.content-slot','槽位', it.slot]);
  if(it.permanent!=='') fields.push(['content-settings.is-permanent','永久(false/true)', it.permanent]);
  if(it.downgradable!=='') fields.push(['content-settings.is-downgradable','可降级(false/true)', it.downgradable]);
  if(it.weight!=='') fields.push(['content-settings.weight','权重', it.weight]);
  if(it.unbreakable!=='') fields.push(['content-settings.is-unbreakable','不毁(false/true)', it.unbreakable]);
  it.tiers.forEach(t=>{
    const base = 'content-tiers.'+t.tier+'.';
    fields.push([base+'tier-settings.cost','价格 ('+t.tier+')', t.cost]);
    fields.push([base+'tier-settings.currency','货币 ('+t.tier+')', t.currency]);
    fields.push([base+'tier-item.material','物品 ('+t.tier+')', t.material]);
    fields.push([base+'tier-item.amount','数量 ('+t.tier+')', t.amount]);
    fields.push([base+'tier-item.data','数据值 ('+t.tier+')', t.data]);
    fields.push([base+'tier-item.enchanted','附魔(true/false) ('+t.tier+')', t.enchanted]);
  });
  const langFields = `
    <div class="field"><label>中文名（支持 &amp; 颜色、{color}）</label><input type="text" id="editLangName" value="${(it.name_raw||'').replace(/"/g,'&quot;')}"></div>
    <div class="field"><label>中文描述（一行一条）</label><textarea id="editLangLore" style="min-height:110px">${(it.lore||[]).join('\n')}</textarea></div>`;
  const box = document.getElementById('shopEditFields');
  box.innerHTML = langFields + fields.map(f=>`<div class="field"><label>${f[1]}<br><span style="color:#56637f">${root}.${f[0]}</span></label><input type="text" data-suffix="${f[0]}" value="${f[2]??''}"></div>`).join('');
  document.getElementById('shopEditTitle').textContent = '编辑：' + (it.name||it.key) + ' ('+it.key+')';
  const card = document.getElementById('shopEditCard');
  card.style.display='block'; card.dataset.root = root; card.dataset.cat = cat.key;
  card.scrollIntoView({behavior:'smooth'});
}
function renderSpecials(specials){
  const box = document.getElementById('shopSpecials');
  box.innerHTML = specials.map(s=>{
    const fields = [['enable','启用'],['material','物品'],['health','血量'],['damage','伤害'],['speed','速度'],['despawn','消失(秒)']];
    return `<div class="field"><b>${s.name||s.key} <span class="hint">(${s.key})</span></b>` + fields.map(f=>`<div style="display:flex;gap:6px;align-items:center;margin-top:4px"><span class="hint" style="width:70px">${f[1]}</span><input type="text" data-special="${s.key}" data-field="${f[0]}" value="${s[f[0]]??''}"></div>`).join('') + '</div>';
  }).join('');
}
function renderAddFields(){
  const box = document.getElementById('shopAddFields');
  if(!box) return;
  const cats = shopModel ? shopModel.categories : [];
  box.innerHTML = `
    <div class="field"><label>分类</label><select id="addCat">${cats.map(c=>`<option value="${c.key}">${c.cn||c.key}</option>`).join('')}</select></div>
    <div class="field"><label>物品 ID（英文）</label><input type="text" id="addKey" placeholder="gold-apple"></div>
    <div class="field"><label>中文名</label><input type="text" id="addName" placeholder="金苹果"></div>
    <div class="field"><label>中文描述（一行一条）</label><textarea id="addLore" style="min-height:90px"></textarea></div>
    <div class="field"><label>槽位</label><input type="text" id="addSlot" value="0"></div>
    <div class="field"><label>物品材质</label><input type="text" id="addMaterial" value="GOLDEN_APPLE"></div>
    <div class="field"><label>数量</label><input type="text" id="addAmount" value="1"></div>
    <div class="field"><label>价格</label><input type="text" id="addCost" value="1"></div>
    <div class="field"><label>货币 (iron/gold/emerald/diamond)</label><input type="text" id="addCurrency" value="iron"></div>
    <div class="field"><label>数据值</label><input type="text" id="addData" value="0"></div>
    <div class="field"><label>永久 (true/false)</label><input type="text" id="addPermanent" value="false"></div>`;
}
document.getElementById('shopReload').onclick = loadShop;
document.getElementById('shopAddOpen').onclick = ()=>{
  if(!shopModel) return;
  renderAddFields();
  document.getElementById('shopAddCard').style.display='block';
  document.getElementById('shopAddCard').scrollIntoView({behavior:'smooth'});
};
document.getElementById('shopAddCancel').onclick = ()=>{ document.getElementById('shopAddCard').style.display='none'; };
document.getElementById('shopAddSave').onclick = async()=>{
  const body = {
    category: document.getElementById('addCat').value,
    key: document.getElementById('addKey').value,
    name: document.getElementById('addName').value,
    lore: document.getElementById('addLore').value.split('\n'),
    slot: document.getElementById('addSlot').value,
    material: document.getElementById('addMaterial').value,
    amount: document.getElementById('addAmount').value,
    cost: document.getElementById('addCost').value,
    currency: document.getElementById('addCurrency').value,
    data: document.getElementById('addData').value,
    permanent: document.getElementById('addPermanent').value,
  };
  const r = await api('/api/shop/add',{method:'POST',body});
  toast(r.message || r.error, r.ok);
  if(r.ok){ loadShop(); }
};
document.getElementById('shopSaveItem').onclick = async()=>{
  const card = document.getElementById('shopEditCard');
  const root = card.dataset.root;
  const updates = [];
  card.querySelectorAll('input[data-suffix]').forEach(i=>updates.push({path: root + '.' + i.dataset.suffix, value:i.value}));
  const lang = {
    category: card.dataset.cat,
    key: editItemKey,
    name: document.getElementById('editLangName').value,
    lore: document.getElementById('editLangLore').value.split('\n'),
  };
  const r = await api('/api/shop',{method:'POST',body:{updates, lang}});
  toast(r.message || r.error, r.ok);
  if(r.ok) loadShop();
};
document.getElementById('shopCancelEdit').onclick = ()=>{ document.getElementById('shopEditCard').style.display='none'; };
document.getElementById('shopSpecials').addEventListener('change', async (e)=>{
  if(!e.target.dataset.special) return;
  const updates = [];
  document.querySelectorAll('#shopSpecials input').forEach(i=>updates.push({path:'shop-specials.'+i.dataset.special+'.'+i.dataset.field, value:i.value}));
  const r = await api('/api/shop',{method:'POST',body:{updates}});
  toast(r.message || r.error, r.ok);
});

// ---------------- raw editor
async function loadRaw(){
  const file = document.getElementById('rawFileSel').value;
  const r = await api('/api/file?path='+encodeURIComponent(file));
  if(!r.ok){ toast(r.error,false); return; }
  document.getElementById('shopText').style.display='block';
  document.getElementById('shopText').value = r.content;
}
document.getElementById('rawLoad').onclick = loadRaw;
document.getElementById('rawSave').onclick = async()=>{
  const file = document.getElementById('rawFileSel').value;
  const r = await api('/api/file',{method:'POST',body:{path:file, content:document.getElementById('shopText').value}});
  toast(r.message || r.error, r.ok);
};

// ---------------- maps
let arenaModel = null;
let editArena = null;
async function loadMaps(){
  const r = await api('/api/arenas');
  if(!r.ok){ toast(r.error,false); return; }
  arenaModel = r;
  renderMapGroups();
  renderGroupList();
}
function renderMapGroups(){
  const box = document.getElementById('mapGroups');
  if(!arenaModel){ box.innerHTML=''; return; }
  box.innerHTML = arenaModel.groups.map(g=>{
    const maps = arenaModel.arenas.filter(a=>a.fields.group===g);
    const cards = maps.map(a=>`<div class="map-item" data-map="${a.name}">
      <div><b>${a.name}</b><div class="hint">${a.fields['display-name']||''} · 人数 ${a.fields.minPlayers||''}/${a.fields.maxInTeam||''} · 世界${a.world_exists?'✅':'❌'}</div></div>
      <div class="pill">编辑</div></div>`).join('') || '<p class="hint">（该分组下暂无地图）</p>';
    return `<div style="margin-bottom:14px"><h3 style="font-size:13px;color:#8fb8ff;margin:6px 0">📁 ${g} (${maps.length})</h3>${cards}</div>`;
  }).join('');
  box.querySelectorAll('.map-item').forEach(el=>el.onclick=()=>openMapEditor(el.dataset.map));
}
function openMapEditor(name){
  const a = arenaModel.arenas.find(x=>x.name===name);
  if(!a) return;
  editArena = name;
  const fields = [['display-name','显示名'],['group','分组'],['minPlayers','最少玩家'],['maxInTeam','每队最大人数'],['island-radius','岛屿半径'],['worldBorder','世界边界'],['y-kill-height','死亡高度'],['max-build-y','最高建筑高度'],['allowSpectate','允许旁观(true/false)'],['allow-map-break','允许破坏地图(true/false)']];
  document.getElementById('mapEditTitle').textContent = '编辑：' + name;
  document.getElementById('mapEditFields').innerHTML = fields.map(f=>`<div class="field"><label>${f[1]}<br><span style="color:#56637f">${f[0]}</span></label><input type="text" data-field="${f[0]}" value="${a.fields[f[0]]??''}"></div>`).join('');
  const card = document.getElementById('mapEditCard');
  card.style.display='block'; card.scrollIntoView({behavior:'smooth'});
}
document.getElementById('mapsReload').onclick = loadMaps;
document.getElementById('mapSave').onclick = async()=>{
  const fields = {};
  document.querySelectorAll('#mapEditFields input').forEach(i=>fields[i.dataset.field]=i.value);
  const r = await api('/api/arena',{method:'POST',body:{name:editArena, fields}});
  toast(r.message || r.error, r.ok);
  if(r.ok) loadMaps();
};
document.getElementById('mapCancel').onclick = ()=>{ document.getElementById('mapEditCard').style.display='none'; };
document.getElementById('mapRawClose').onclick = ()=>{ document.getElementById('mapRawCard').style.display='none'; };
document.getElementById('mapRawSave').onclick = async()=>{
  const r = await api('/api/arena/raw',{method:'POST',body:{name:editArena, content:document.getElementById('mapRaw').value}});
  toast(r.message || r.error, r.ok);
};
function renderGroupList(){
  const box = document.getElementById('groupList');
  box.innerHTML = arenaModel.groups.map(g=>`<div class="map-item" style="cursor:default"><div><b>${g}</b><div class="hint">${arenaModel.arenas.filter(a=>a.fields.group===g).length} 张地图</div></div><div class="pill" data-delgroup="${g}" style="cursor:pointer">删除</div></div>`).join('');
  box.querySelectorAll('[data-delgroup]').forEach(el=>el.onclick=async()=>{
    const g = el.dataset.delgroup;
    if(arenaModel.arenas.some(a=>a.fields.group===g)){ toast('该分组下还有地图，先把地图改到别的分组', false); return; }
    if(!confirm('删除分组 '+g+' ？')) return;
    const groups = arenaModel.groups.filter(x=>x!==g);
    const r = await api('/api/groups',{method:'POST',body:{groups}});
    toast(r.message || r.error, r.ok); if(r.ok) loadMaps();
  });
}
document.getElementById('addGroup').onclick = async()=>{
  const name = document.getElementById('newGroup').value.trim();
  if(!name) return;
  if(arenaModel.groups.includes(name)){ toast('分组已存在',false); return; }
  const r = await api('/api/groups',{method:'POST',body:{groups: arenaModel.groups.concat([name])}});
  toast(r.message || r.error, r.ok); if(r.ok){ document.getElementById('newGroup').value=''; loadMaps(); }
};

// ---------------- log
// ---------------- log
function escapeHtml(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function renderLogLines(lines){
  return (lines||[]).map(l=>{
    let cls='';
    if(/ERROR|SEVERE|Exception|\bError\b/.test(l)) cls='log-err';
    else if(/WARN/.test(l)) cls='log-warn';
    else if(/\[面板指令\]/.test(l)) cls='log-cmd';
    else if(/INFO/.test(l)) cls='log-info';
    return `<div class="${cls}">${escapeHtml(l)}</div>`;
  }).join('');
}
async function loadLog(){
  const r = await api('/api/log?n=400');
  if(!r.ok) return;
  const box = document.getElementById('log');
  const stick = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
  box.innerHTML = renderLogLines(r.lines);
  if(stick) box.scrollTop = box.scrollHeight;
}
document.getElementById('logRefresh').onclick = loadLog;
document.getElementById('logClear').onclick = ()=>{ document.getElementById('log').textContent=''; };
document.getElementById('logAuto').onchange = ()=>{};

// ---------------- settings
async function loadSettings(){
  const s = await api('/api/settings');
  if(!s.ok) return;
  document.getElementById('cfgDir').value = s.config.server_dir;
  document.getElementById('cfgJava').value = s.config.java_path;
  document.getElementById('cfgMin').value = s.config.min_mem;
  document.getElementById('cfgMax').value = s.config.max_mem;
  document.getElementById('cfgPaper').value = s.config.paper_version;
  document.getElementById('cfgBuild').value = s.config.paper_build || '';
  document.getElementById('jarVer').textContent = s.jar_version || '未知';
}
document.getElementById('cfgSave').onclick = async()=>{
  const r = await api('/api/settings',{method:'POST',body:{
    server_dir: document.getElementById('cfgDir').value,
    java_path: document.getElementById('cfgJava').value,
    min_mem: document.getElementById('cfgMin').value,
    max_mem: document.getElementById('cfgMax').value,
  }});
  toast(r.message || r.error, r.ok);
};

// ---------------- plugin forms
let formList = [];
async function loadForms(){
  const r = await api('/api/forms');
  if(!r.ok){ toast(r.error,false); return; }
  formList = r.forms || [];
  const sel = document.getElementById('formSel');
  sel.innerHTML = formList.map(f=>`<option value="${f.id}">${f.title}</option>`).join('');
  if(formList.length) renderForm(formList[0].id);
}
function renderForm(id){
  const f = formList.find(x=>x.id===id);
  if(!f) return;
  document.getElementById('formNote').textContent = f.note || '';
  const box = document.getElementById('formFields');
  if(f.error){ box.innerHTML = '<p class="hint">读取失败: '+f.error+'</p>'; return; }
  box.innerHTML = f.fields.map(x=>`<div class="field"><label>${x.label}<br><span style="color:#56637f">${x.path}</span></label><input type="text" data-path="${x.path}" value="${(x.value+'').replace(/"/g,'&quot;')}"></div>`).join('');
}
document.getElementById('formSel').onchange = ()=>renderForm(document.getElementById('formSel').value);
document.getElementById('formLoad').onclick = ()=>loadForms();
document.getElementById('formSave').onclick = async()=>{
  const values={};
  document.querySelectorAll('#formFields input[data-path]').forEach(i=>values[i.dataset.path]=i.value);
  const r = await api('/api/forms',{method:'POST',body:{id:document.getElementById('formSel').value, values}});
  toast(r.message||r.error, r.ok);
};

// ---------------- console
document.getElementById('cmdInput').addEventListener('keydown', e=>{ if(e.key==='Enter') sendConsoleCommand('cmdInput'); });

// ---------------- java environment
let javaState = null;
async function loadJava(){
  const r = await api('/api/java');
  if(!r.ok) return;
  javaState = r;
  document.getElementById('javaInfo').innerHTML =
    `<div class="k">当前路径</div><div>${r.current.path||'-'}</div>` +
    `<div class="k">当前版本</div><div>${r.current.version||'未检测到'}</div>`;
  const sel = document.getElementById('javaCands');
  sel.innerHTML = r.candidates.map(c=>`<option value="${c.path}">${c.version||'?'} — ${c.path}</option>`).join('');
  updateJavaProgress(r.download||{});
}
function updateJavaProgress(d){
  const el = document.getElementById('javaProgress');
  if(!el) return;
  if(!d.phase){ el.textContent=''; return; }
  let t = d.phase;
  if(d.total) t += '  ' + Math.round(d.downloaded/d.total*100) + '% (' + (d.downloaded/1024/1024).toFixed(1) + '/' + (d.total/1024/1024).toFixed(1) + ' MB)';
  if(d.error) t += '  错误: ' + d.error;
  el.textContent = t;
}
document.getElementById('javaUse').onclick = async()=>{
  const p = document.getElementById('javaCands').value;
  if(!p) return;
  const r = await api('/api/settings',{method:'POST',body:{java_path:p}});
  toast(r.message||r.error, r.ok); loadJava();
};
document.getElementById('javaDownload').onclick = async()=>{
  if(!confirm('下载约 190MB 的 Temurin 21 JDK？')) return;
  const r = await api('/api/java/download',{method:'POST',body:{}});
  toast(r.message||r.error, r.ok);
};
setInterval(async()=>{
  const onSettings = document.getElementById('settings').classList.contains('active');
  const onHome = document.getElementById('home').classList.contains('active');
  if(!onSettings && !onHome) return;
  const d = await api('/api/java/progress');
  if(!d) return;
  if(onSettings) updateJavaProgress(d);
  if(onHome) updateJavaProgressHome(d);
}, 3000);

// ---------------- home server config
async function loadHomeConfig(){
  const r = await api('/api/homeconfig');
  if(!r.ok){ return; }
  const box = document.getElementById('homeConfigFields');
  box.innerHTML = (r.fields||[]).map(f=>`<div class="field" style="margin-bottom:8px"><label>${f.label}<br><span style="color:#56637f">${f.file} · ${f.path}</span></label><input type="text" data-key="${f.key}" value="${(f.value+'').replace(/"/g,'&quot;')}"></div>`).join('');
}
document.getElementById('homeConfigSave').onclick = async()=>{
  const values={};
  document.querySelectorAll('#homeConfigFields input[data-key]').forEach(i=>values[i.dataset.key]=i.value);
  const r = await api('/api/homeconfig',{method:'POST',body:{values}});
  toast(r.message||r.error, r.ok);
};

// ---------------- home java
async function loadJavaHome(){
  const r = await api('/api/java');
  if(!r.ok) return;
  document.getElementById('javaInfoHome').innerHTML =
    `<div class="k">当前版本</div><div>${r.current.version||'未检测到'}</div>` +
    `<div class="k">当前路径</div><div style="word-break:break-all">${r.current.path||'-'}</div>`;
  const sel = document.getElementById('javaCandsHome');
  sel.innerHTML = r.candidates.map(c=>`<option value="${c.path}">${c.version||'?'} — ${c.path}</option>`).join('');
  updateJavaProgressHome(r.download||{});
}
function updateJavaProgressHome(d){
  const el = document.getElementById('javaProgressHome');
  if(!el) return;
  if(!d.phase){ el.textContent=''; return; }
  let t = d.phase;
  if(d.total) t += '  ' + Math.round(d.downloaded/d.total*100) + '%';
  if(d.error) t += '  错误: ' + d.error;
  el.textContent = t;
}
document.getElementById('javaUseHome').onclick = async()=>{
  const p = document.getElementById('javaCandsHome').value;
  if(!p) return;
  const r = await api('/api/settings',{method:'POST',body:{java_path:p}});
  toast(r.message||r.error, r.ok); loadJavaHome();
};
document.getElementById('javaDownloadTop').onclick = async()=>{
  if(!confirm('下载约 190MB 的 Temurin 21 JDK？')) return;
  const r = await api('/api/java/download',{method:'POST',body:{}});
  toast(r.message||r.error, r.ok);
};

// ---------------- console (shared by home + log tab)
window.sendConsoleCommand = async function(inputId){
  const input = document.getElementById(inputId);
  if(!input) return;
  const cmd = input.value.trim();
  if(!cmd) return;
  const r = await api('/api/console',{method:'POST',body:{command:cmd}});
  toast(r.message||r.error, r.ok);
  if(r.ok) input.value = '';
};
document.getElementById('cmdSendHome').onclick = ()=>sendConsoleCommand('cmdInputHome');
document.getElementById('cmdInputHome').addEventListener('keydown', e=>{ if(e.key==='Enter') sendConsoleCommand('cmdInputHome'); });
document.getElementById('openLogTab').onclick = ()=>{
  const btn = document.querySelector('nav button[data-tab="console"]');
  if(btn) btn.click();
};

// ---------------- plugin updater
let updateDoneShown = false, updaterChecked = false, updaterResults = [];
function updateStatusText(st){
  const el = document.getElementById('updateStatus');
  if(!el) return;
  if(!st) { el.textContent=''; return; }
  if(st.active){
    let t = st.phase || '更新中';
    if(st.total) t += '  ' + Math.round(st.downloaded/st.total*100) + '%';
    el.textContent = t;
  } else if(st.results && st.results.length){
    el.textContent = st.results.join('  |  ');
  } else if(st.error){
    el.textContent = '错误: ' + st.error;
  } else {
    el.textContent = '';
  }
}
function renderUpdateResults(results){
  const box = document.getElementById('updateChecks');
  const run = document.getElementById('updateRun');
  if(!results){
    box.innerHTML = '<p class="hint">尚未检查更新。点击下方「🔍 检查更新」获取各插件最新版本。</p>';
    run.disabled = true;
    return;
  }
  box.innerHTML = results.map(r=>{
    const badge = r.error
      ? `<span class="pill" style="border-color:rgba(255,158,210,.5);color:#ffd6ea">检查失败</span>`
      : (r.update ? `<span class="pill">可更新 ${r.latest||'?'}</span>` : `<span class="pill" style="opacity:.7">已是最新</span>`);
    const cb = r.update
      ? `<input type="checkbox" value="${r.id}" checked>`
      : `<input type="checkbox" value="${r.id}" disabled>`;
    return `<label class="hint" style="display:flex;gap:8px;align-items:center;padding:9px 11px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.04);flex-wrap:wrap">${cb}<span style="color:#eaf4ff">${r.label}</span><span style="color:#93a9cf">当前 ${r.installed||'未安装'} → ${r.latest||'?'}</span>${badge}${r.error?`<span class="hint" style="color:#ffb8d2">${r.error}</span>`:''}</label>`;
  }).join('');
  run.disabled = !results.some(r=>r.update);
}
async function checkUpdates(){
  const btn = document.getElementById('updateCheck');
  const st = document.getElementById('updateStatus');
  btn.disabled = true;
  st.textContent = '正在检查更新...';
  try{
    const r = await api('/api/updater/check');
    if(!r.ok){ toast(r.error || '检查更新失败', false); st.textContent = '检查失败'; return; }
    updaterResults = r.results || [];
    updaterChecked = true;
    renderUpdateResults(updaterResults);
    const n = updaterResults.filter(x=>x.update).length;
    st.textContent = n ? ('发现 ' + n + ' 个可更新插件') : '所有插件都已是最新';
  } finally {
    btn.disabled = false;
  }
}
function resetUpdateSelection(){
  updaterChecked = false;
  renderUpdateResults(null);
  document.getElementById('updateStatus').textContent = '';
}
async function loadUpdates(){
  const r = await api('/api/updater/status');
  if(!r.ok) return;
  if(!updaterChecked) renderUpdateResults(null);
  updateStatusText(r.state || {});
}
document.getElementById('updateCheck').onclick = checkUpdates;
document.getElementById('updateRun').onclick = async()=>{
  const targets = Array.from(document.querySelectorAll('#updateChecks input:checked:not(:disabled)')).map(i=>i.value);
  if(!targets.length){ toast('请先检查更新，并勾选有新版本的插件', false); return; }
  if(!confirm('更新所选插件？需要先关服，更新后要重启服务器。')) return;
  const r = await api('/api/updater/run',{method:'POST',body:{targets}});
  toast(r.message||r.error, r.ok);
  if(r.ok) resetUpdateSelection();
};
setInterval(async()=>{
  if(!document.getElementById('plugins').classList.contains('active')) return;
  const r = await api('/api/updater/status');
  if(!r.ok) return;
  updateStatusText(r.state || {});
  if(r.state && r.state.done && !r.state.active && !updateDoneShown){
    updateDoneShown = true;
    resetUpdateSelection();
  }
  if(r.state && r.state.active) updateDoneShown = false;
}, 2500);

// ---------------- hitokoto
async function loadHitokoto(){
  const t = document.getElementById('hitokotoText');
  if(!t) return;
  t.textContent = '加载中...';
  const r = await api('/api/hitokoto');
  if(r && r.ok && r.text){
    t.textContent = '“' + r.text + '”' + (r.from ? ('  —— ' + r.from) : '');
    t.title = r.text;
  } else {
    t.textContent = '“暂时获取不到一言”';
  }
}
document.getElementById('hitokotoBox').ondblclick = loadHitokoto;

// ---------------- player management
let playerData = [];
async function loadPlayers(){
  const r = await api('/api/players');
  if(!r.ok){ toast(r.error,false); return; }
  playerData = r.players || [];
  document.getElementById('playersStatus').textContent = r.running ? '服务器运行中，可操作' : '服务器未运行，只能查看';
  renderPlayers();
}
function renderPlayers(){
  const q = (document.getElementById('playerSearch').value || '').toLowerCase();
  const rows = playerData.filter(p => !q || p.name.toLowerCase().includes(q));
  const box = document.getElementById('playerTable');
  box.innerHTML = '<table class="ptable"><thead><tr><th>玩家</th><th>BW 等级</th><th>白名单</th><th>封禁</th><th>操作</th></tr></thead><tbody>' +
    rows.map(p => {
      const level = p.level != null ? ('Lv ' + p.level + ' <span class="hint">' + (p.xp ?? 0) + '/' + (p.next_cost ?? '?') + '</span>') : '-';
      const wl = p.whitelisted ? (p.whitelist_ban ? '<span style="color:#ff6b81">封禁中</span>' : '<span style="color:#9fe3b0">已加入</span>') : '<span class="hint">无</span>';
      const ban = p.ban ? '<span style="color:#ff6b81">' + (p.ban.reason || '封禁') + '</span>' : '<span class="hint">无</span>';
      const wlBtn = p.whitelisted
        ? `<button class="btn" data-act="wl-del" data-name="${p.name}">移除白名单</button>`
        : `<button class="btn" data-act="wl-add" data-name="${p.name}">加白名单</button>`;
      const banBtn = p.ban
        ? `<button class="btn" data-act="unban" data-name="${p.name}">解封</button>`
        : `<button class="btn red" data-act="ban" data-name="${p.name}">封禁</button>`;
      return `<tr><td>${p.name}${p.uuid ? ' <span class="hint">' + p.uuid.slice(0, 8) + '</span>' : ''}</td><td>${level}</td><td>${wl}</td><td>${ban}</td><td>${wlBtn} ${banBtn}</td></tr>`;
    }).join('') + '</tbody></table>';
  box.querySelectorAll('button[data-act]').forEach(b => b.onclick = () => playerAction(b.dataset.act, b.dataset.name));
}
async function playerAction(act, name){
  let path, body = { name };
  if(act === 'wl-add'){ path = '/api/players/whitelist'; body.action = 'add'; }
  else if(act === 'wl-del'){ path = '/api/players/whitelist'; body.action = 'remove'; }
  else if(act === 'ban'){
    const reason = prompt('封禁原因', '违规');
    if(reason === null) return;
    path = '/api/players/ban'; body.reason = reason;
  }
  else if(act === 'unban'){ path = '/api/players/unban'; }
  else return;
  const r = await api(path, {method:'POST', body});
  toast(r.message || r.error, r.ok);
  if(r.ok) setTimeout(loadPlayers, 1500);
}
document.getElementById('playersRefresh').onclick = loadPlayers;
document.getElementById('playerSearch').oninput = renderPlayers;
document.getElementById('playerAddWlBtn').onclick = async()=>{
  const name = document.getElementById('playerAddWl').value.trim();
  if(!name) return;
  const r = await api('/api/players/whitelist', {method:'POST', body:{name, action:'add'}});
  toast(r.message || r.error, r.ok);
  if(r.ok) setTimeout(loadPlayers, 1500);
};

// ---------------- 面板退出

async function panelExit(stopServer){
  const dirtyTip = window.__dirty ? '\n\n注意：当前页面有未保存的修改，退出后会丢失！' : '';
  const msg = (stopServer
    ? '确定退出面板并关闭服务器吗？\n\n服务器会先关闭，然后面板退出。'
    : '确定退出面板吗？\n\n只退出面板，服务器继续运行，不会关服。') + dirtyTip;
  if(!confirm(msg)) return;
  window.__panelExiting = true;
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;background:rgba(4,8,18,.82);color:#fff;font-size:16px;text-align:center;padding:24px;backdrop-filter:blur(10px)';
  overlay.innerHTML = stopServer
    ? '<div>正在关闭服务器并退出面板...<br><span style="font-size:13px;color:#9fb3d9">关闭完成后可直接关掉此页面</span></div>'
    : '<div>面板已退出，服务器仍在运行。<br><span style="font-size:13px;color:#9fb3d9">可以关闭此页面</span></div>';
  document.body.appendChild(overlay);
  try {
    const r = await api('/api/panel-exit', {method:'POST', body:{stop_server:stopServer}});
    if(!r.ok){
      overlay.remove();
      if(r.error === 'unauthorized'){
        toast('面板已重启，正在刷新页面...', false);
        window.__panelExiting = true;
        setTimeout(()=>location.reload(), 900);
        return;
      }
      window.__panelExiting = false;
      toast(r.error || r.message, false);
    }
  } catch(e) {
    // 面板进程可能已经退出，忽略
  }
}

document.getElementById('btnExitPanel').onclick = () => panelExit(false);
document.getElementById('btnExitStop').onclick = () => panelExit(true);

window.__panelHadInteraction = false;
['pointerdown', 'keydown'].forEach(evt => window.addEventListener(evt, function(){
  window.__panelHadInteraction = true;
}, true));

window.addEventListener('beforeunload', function(e){
  if(window.__panelExiting) return;
  e.preventDefault();
  e.returnValue = window.__dirty
    ? '当前页面有未保存的配置修改，确定关闭面板吗？'
    : '确定退出面板吗？只退出面板，服务器不会关闭。';
  return e.returnValue;
});

window.addEventListener('unload', function(){
  if(window.__panelExiting) return;
  try {
    fetch('/api/panel-exit', {
      method:'POST',
      keepalive:true,
      headers:{'Content-Type':'application/json','X-Panel-Token':TOKEN},
      body:JSON.stringify({stop_server:false})
    });
  } catch(e) {}
});

// ---------------- 未保存提醒

const NO_DIRTY_IDS = new Set([
  'cmdInputHome', 'cmdInput', 'playerSearch', 'playerAddWl',
  'javaCandsHome', 'javaCands', 'rawFileSel', 'formSel', 'logAuto'
]);
['input', 'change'].forEach(evt => document.addEventListener(evt, function(e){
  const el = e.target;
  if(!el || !/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
  if(el.type === 'checkbox' || el.type === 'radio' || el.type === 'button') return;
  if(el.readOnly || el.disabled) return;
  if(NO_DIRTY_IDS.has(el.id)) return;
  markDirty();
}, true));

// ---------------- loops

setInterval(refreshStatus, 3000);
setInterval(()=>{ if(document.getElementById('log').closest('section').classList.contains('active') && document.getElementById('logAuto').checked) loadLog(); }, 3000);
refreshStatus();
loadLog();
loadHitokoto();
loadHomeConfig();
loadJavaHome();
loadUpdates();
loadPlayers();
</script>
</body>
</html>
"""


def html_page():
    page = HTML.replace("__TOKEN__", TOKEN)
    page = page.replace("__GEN_FIELDS__", json.dumps(GENERATOR_FIELDS, ensure_ascii=False))
    page = page.replace("__VERSION__", APP_VERSION)
    return page


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "BedWarsPanel/1.0"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _asset(self, fp, ctype):
        try:
            with open(fp, "rb") as f:
                data = f.read()
        except OSError:
            self._send(404, b"", "text/plain; charset=utf-8")
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        if self.headers.get("X-Panel-Token") == TOKEN:
            return True
        # 退出面板允许同源请求：面板重启后旧标签页的 token 会失效，
        # 但用户关闭旧页面时仍然应该能正常退出面板。
        try:
            if urllib.parse.urlparse(self.path).path == "/api/panel-exit":
                sec = self.headers.get("Sec-Fetch-Site") or ""
                origin = (self.headers.get("Origin") or "").rstrip("/")
                host = self.headers.get("Host") or ""
                referer = self.headers.get("Referer") or ""
                same_referer = False
                if referer and host:
                    try:
                        same_referer = urllib.parse.urlparse(referer).netloc == host
                    except Exception:
                        same_referer = False
                if sec == "same-origin" or (origin and host and origin.endswith(host)) or same_referer:
                    return True
        except Exception:
            pass
        self._json({"ok": False, "error": "unauthorized"}, 403)
        return False

    def _read_json(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        if path == "/":
            self._send(200, html_page(), "text/html; charset=utf-8")
            return
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        if path == "/assets/console_bg.webp":
            self._asset(os.path.join(APP_DIR, "panel_assets", "console_bg.webp"), "image/webp")
            return
        if path == "/assets/logo.png":
            self._asset(os.path.join(APP_DIR, "panel_assets", "logo.png"), "image/png")
            return
        if path == "/api/status":
            self._json(SERVER.status())
            return
        if path == "/api/log":
            n = int(qs.get("n", ["300"])[0])
            self._json({"ok": True, "lines": SERVER.tail(n)})
            return
        if path == "/api/download/status":
            self._json(DOWNLOADER.snapshot())
            return
        if path == "/api/generators":
            try:
                text = open(os.path.join(CFG["server_dir"], BW, "generators.yml"), "r", encoding="utf-8").read()
            except Exception as e:
                self._json({"ok": False, "error": "读取 generators.yml 失败: %r" % e})
                return
            values = {p: yaml_get(text, p.split(".")) for p, _ in GENERATOR_FIELDS}
            self._json({"ok": True, "values": values, "raw": text})
            return
        if path == "/api/maps":
            arena_dir = os.path.join(CFG["server_dir"], BW, "Arenas")
            maps = []
            if os.path.isdir(arena_dir):
                for name in sorted(os.listdir(arena_dir)):
                    if name.endswith(".yml"):
                        p = os.path.join(arena_dir, name)
                        maps.append({"name": name, "path": "Arenas/" + name, "size": os.path.getsize(p)})
            self._json({"ok": True, "maps": maps})
            return
        if path == "/api/map":
            name = qs.get("name", [""])[0]
            if not name or "/" in name or "\\" in name:
                self._json({"ok": False, "error": "invalid name"})
                return
            p = os.path.join(CFG["server_dir"], BW, "Arenas", name)
            if not os.path.isfile(p):
                self._json({"ok": False, "error": "地图不存在"})
                return
            try:
                self._json({"ok": True, "name": name, "content": open(p, "r", encoding="utf-8", errors="replace").read()})
            except Exception as e:
                self._json({"ok": False, "error": repr(e)})
            return
        if path == "/api/settings":
            jar = os.path.join(CFG["server_dir"], "server.jar")
            self._json({"ok": True, "config": CFG, "version": APP_VERSION, "author": APP_AUTHOR,
                        "license": APP_LICENSE, "copyright": APP_COPYRIGHT, "url": APP_URL,
                        "jar_version": read_jar_version(jar) if os.path.exists(jar) else ""})
            return
        if path == "/api/file":
            rel = qs.get("path", [""])[0]
            try:
                p = safe_join(CFG["server_dir"], rel)
                self._json({"ok": True, "content": open(p, "r", encoding="utf-8", errors="replace").read()})
            except Exception as e:
                self._json({"ok": False, "error": "读取失败: %r" % e})
            return
        if path == "/api/shop":
            try:
                text = read_yaml(os.path.join(CFG["server_dir"], BW, "shop.yml"))
                model = parse_shop_model(text)
                lang_path = os.path.join(CFG["server_dir"], BW, "Languages", "messages_zh_cn.yml")
                lang_text = read_yaml(lang_path) if os.path.exists(lang_path) else ""
                lang = parse_mapping_yaml(lang_text)
                section = lang_shop_section(lang)
                for cat in model["categories"]:
                    c = section.get(cat["key"]) if isinstance(section.get(cat["key"]), dict) else {}
                    cat["cn"] = strip_mc_colors(c.get("category-item-name", "")) or cat["key"]
                    for it in cat["items"]:
                        it["name_raw"] = c.get("content-item-%s-name" % it["key"], "")
                        it["name"] = strip_mc_colors(it["name_raw"]) or it["key"]
                        it["lore"] = get_lang_lores(lang_text, cat["key"], it["key"])
                specials_cn = {"silverfish": "蠹虫", "iron-golem": "铁傀儡", "tower": "塔"}
                for sp in model["specials"]:
                    sp["name"] = specials_cn.get(sp["key"]) or sp["key"]
                model["ok"] = True
                self._json(model)
            except Exception as e:
                self._json({"ok": False, "error": "读取 shop.yml 失败: %r" % e})
            return
        if path == "/api/arenas":
            try:
                arenas = read_arena_model(CFG["server_dir"])
                config_text = read_yaml(os.path.join(CFG["server_dir"], BW, "config.yml"))
                groups = get_arena_groups(config_text)
                for a in arenas:
                    if a["fields"].get("group") and a["fields"]["group"] not in groups:
                        groups.append(a["fields"]["group"])
                self._json({"ok": True, "groups": groups, "arenas": arenas})
            except Exception as e:
                self._json({"ok": False, "error": "读取地图失败: %r" % e})
            return
        if path == "/api/arena/raw":
            name = qs.get("name", [""])[0]
            try:
                if "/" in name or "\\" in name or not name.endswith(".yml"):
                    raise ValueError("bad name")
                p = os.path.join(CFG["server_dir"], BW, "Arenas", name)
                self._json({"ok": True, "content": read_yaml(p)})
            except Exception as e:
                self._json({"ok": False, "error": "读取失败: %r" % e})
            return
        if path == "/api/forms":
            out = []
            for form in FORMS:
                entry = {"id": form["id"], "title": form["title"], "note": form["note"], "kind": form["kind"]}
                try:
                    entry["fields"] = read_form_values(form, CFG["server_dir"])
                except Exception as e:
                    entry["fields"] = []
                    entry["error"] = repr(e)
                out.append(entry)
            self._json({"ok": True, "forms": out})
            return
        if path == "/api/java":
            candidates = []
            for p in find_java_candidates(CFG):
                candidates.append({"path": p, "version": java_version(p)})
            cur = CFG.get("java_path", "")
            self._json({
                "ok": True,
                "current": {"path": cur, "version": java_version(cur) if os.path.exists(cur) else "",
                            "exists": os.path.exists(cur)},
                "candidates": candidates,
                "download": JAVA_DOWNLOADER.snapshot(),
            })
            return
        if path == "/api/java/progress":
            self._json(JAVA_DOWNLOADER.snapshot())
            return
        if path == "/api/homeconfig":
            try:
                self._json({"ok": True, "fields": read_home_config(CFG["server_dir"])})
            except Exception as e:
                self._json({"ok": False, "error": "读取失败: %r" % e})
            return
        if path == "/api/players":
            try:
                self._json({"ok": True, "players": load_player_overview(CFG["server_dir"]),
                            "running": SERVER.status()["running"]})
            except Exception as e:
                self._json({"ok": False, "error": "读取玩家数据失败: %r" % e})
            return
        if path == "/api/updater/status":
            self._json({"ok": True, "installed": UPDATER.installed(),
                        "state": UPDATER.snapshot(), "running": SERVER.status()["running"]})
            return
        if path == "/api/updater/check":
            try:
                self._json({"ok": True, "results": UPDATER.check(),
                            "running": SERVER.status()["running"]})
            except Exception as e:
                self._json({"ok": False, "error": "检查更新失败: %r" % e})
            return
        if path == "/api/hitokoto":
            quotes = [
                "愿你出走半生，归来仍是少年。",
                "生活明朗，万物可爱。",
                "人间值得，未来可期。",
                "把烦心事丢掉，腾出地方装鲜花。",
                "慢慢来，谁还没有一个努力的过程。",
                "今天也要好好生活呀。",
                "心之所向，素履以往。",
                "所有热爱的事情都要不遗余力。",
            ]
            try:
                req = urllib.request.Request("https://v1.hitokoto.cn/", headers={"User-Agent": "BedWarsPanel/2.2.0"})
                data = json.load(urllib.request.urlopen(req, timeout=6))
                txt = str(data.get("hitokoto") or "").strip()
                frm = str(data.get("from") or "").strip()
                if txt:
                    self._json({"ok": True, "text": txt, "from": frm})
                    return
            except Exception:
                pass
            self._json({"ok": True, "text": random.choice(quotes), "from": "本地"})
            return
        self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if not self._auth():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        data = self._read_json()
        if path == "/api/start":
            ok, msg = SERVER.start()
            self._json({"ok": ok, "message": msg, "error": msg if not ok else ""})
            return
        if path == "/api/stop":
            ok, msg = SERVER.stop()
            self._json({"ok": ok, "message": msg, "error": msg if not ok else ""})
            return
        if path == "/api/panel-exit":
            stop_server = bool(data.get("stop_server"))
            if stop_server:
                msg = "正在关闭服务器并退出面板..."
            else:
                msg = "面板正在退出，服务器继续运行"
            self._json({"ok": True, "message": msg})

            def _panel_exit_worker():
                time.sleep(0.7)
                try:
                    if stop_server and SERVER.status().get("running"):
                        SERVER.stop()
                        deadline = time.time() + 180
                        while time.time() < deadline:
                            if not SERVER.status().get("running"):
                                break
                            time.sleep(0.5)
                except Exception:
                    pass
                finally:
                    os._exit(0)

            threading.Thread(target=_panel_exit_worker, daemon=True).start()
            return
        if path == "/api/eula":
            ok, msg = SERVER.accept_eula()
            self._json({"ok": ok, "message": msg, "error": msg if not ok else ""})
            return
        if path == "/api/download":
            ok, msg = DOWNLOADER.start(None)
            self._json({"ok": ok, "message": msg, "error": msg if not ok else ""})
            return
        if path == "/api/generators":
            values = data.get("values") or {}
            gen_path = os.path.join(CFG["server_dir"], BW, "generators.yml")
            try:
                text = open(gen_path, "r", encoding="utf-8").read()
                for keypath, val in values.items():
                    if keypath not in [p for p, _ in GENERATOR_FIELDS]:
                        continue
                    val = str(val).strip()
                    if not re.match(r"^-?\d+(\.\d+)?$", val):
                        raise ValueError("非法数值: %s = %s" % (keypath, val))
                    text = yaml_set(text, keypath.split("."), val)
                bak = gen_path + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copyfile(gen_path, bak)
                with open(gen_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                self._json({"ok": True, "message": "已保存 generators.yml（备份: %s）" % os.path.basename(bak)})
            except Exception as e:
                self._json({"ok": False, "error": "保存失败: %r" % e})
            return
        if path == "/api/file":
            rel = data.get("path", "")
            content = data.get("content", "")
            try:
                p = safe_join(CFG["server_dir"], rel)
                bak = p + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copyfile(p, bak)
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
                self._json({"ok": True, "message": "已保存 %s（备份: %s）" % (rel, os.path.basename(bak))})
            except Exception as e:
                self._json({"ok": False, "error": "保存失败: %r" % e})
            return
        if path == "/api/settings":
            try:
                for k in ("server_dir", "java_path", "min_mem", "max_mem"):
                    if k in data:
                        CFG[k] = str(data[k]).strip()
                save_config(CFG)
                SERVER.cfg = CFG
                DOWNLOADER.cfg = CFG
                locked = any(k in data and str(data[k]).strip() != str(CFG.get(k, "")).strip()
                             for k in ("paper_version", "paper_build"))
                msg = "设置已保存（部分设置需重启面板生效）"
                if locked:
                    msg = "设置已保存；Paper 版本/构建号已锁定，未修改"
                self._json({"ok": True, "message": msg})
            except Exception as e:
                self._json({"ok": False, "error": "保存失败: %r" % e})
            return
        if path == "/api/shop":
            updates = data.get("updates") or []
            lang_update = data.get("lang") or None
            try:
                shop_path = os.path.join(CFG["server_dir"], BW, "shop.yml")
                text = read_yaml(shop_path)
                for up in updates:
                    p = (up.get("path") or "").strip()
                    v = str(up.get("value", "")).strip()
                    if not p:
                        continue
                    if any(ch in p for ch in "\n\r"):
                        raise ValueError("非法路径")
                    text = yaml_set(text, p.split("."), v)
                bak = backup_file(shop_path)
                with open(shop_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                msg = "已保存 shop.yml（备份: %s）" % os.path.basename(bak)
                if lang_update:
                    lang_path = os.path.join(CFG["server_dir"], BW, "Languages", "messages_zh_cn.yml")
                    ltext = read_yaml(lang_path)
                    ltext = set_lang_item(ltext, lang_update.get("category", ""),
                                          lang_update.get("key", ""),
                                          lang_update.get("name", ""),
                                          lang_update.get("lore") or [])
                    lbak = backup_file(lang_path)
                    with open(lang_path, "w", encoding="utf-8", newline="\n") as f:
                        f.write(ltext)
                    msg += "；中文名已更新（备份: %s）" % os.path.basename(lbak)
                self._json({"ok": True, "message": msg})
            except Exception as e:
                self._json({"ok": False, "error": "保存失败: %r" % e})
            return
        if path == "/api/shop/add":
            try:
                category = str(data.get("category", "")).strip()
                key = str(data.get("key", "")).strip()
                if not re.match(r"^[A-Za-z0-9_\-]+$", key):
                    raise ValueError("物品 ID 只能包含字母、数字、下划线、短横线")
                shop_path = os.path.join(CFG["server_dir"], BW, "shop.yml")
                text = read_yaml(shop_path)
                model = parse_shop_model(text)
                cat = next((c for c in model["categories"] if c["key"] == category), None)
                if cat is None:
                    raise ValueError("分类不存在")
                if any(i["key"] == key for i in cat["items"]):
                    raise ValueError("该分类下已存在物品 ID: %s" % key)
                name = str(data.get("name", "")).strip() or key
                lore = data.get("lore") or []
                if isinstance(lore, str):
                    lore = [x for x in lore.splitlines()]
                text = insert_shop_item(
                    text, category, key,
                    slot=str(data.get("slot", "0")),
                    material=str(data.get("material", "STONE")).strip().upper(),
                    amount=str(data.get("amount", "1")),
                    cost=str(data.get("cost", "1")),
                    currency=str(data.get("currency", "iron")).strip().lower(),
                    data=str(data.get("data", "0")),
                    enchanted=str(data.get("enchanted", "false")).strip().lower(),
                    permanent=str(data.get("permanent", "false")).strip().lower(),
                    downgradable=str(data.get("downgradable", "false")).strip().lower(),
                )
                bak = backup_file(shop_path)
                with open(shop_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                lang_path = os.path.join(CFG["server_dir"], BW, "Languages", "messages_zh_cn.yml")
                ltext = read_yaml(lang_path)
                ltext = insert_lang_item(ltext, category, key, name, lore)
                lbak = backup_file(lang_path)
                with open(lang_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(ltext)
                self._json({"ok": True, "message": "已新增物品 %s（shop.yml 备份: %s；语言备份: %s）"
                            % (key, os.path.basename(bak), os.path.basename(lbak))})
            except Exception as e:
                self._json({"ok": False, "error": "新增失败: %r" % e})
            return
        if path == "/api/arena":
            name = data.get("name", "")
            fields = data.get("fields") or {}
            try:
                if "/" in name or "\\" in name or not name.endswith(".yml"):
                    raise ValueError("地图名非法")
                arena_path = os.path.join(CFG["server_dir"], BW, "Arenas", name)
                text = read_yaml(arena_path)
                for key, val in fields.items():
                    if key not in [k for k, _ in ARENA_FIELDS]:
                        continue
                    text = yaml_set(text, [key], str(val).strip())
                bak = backup_file(arena_path)
                with open(arena_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
                self._json({"ok": True, "message": "已保存 %s（备份: %s）" % (name, os.path.basename(bak))})
            except Exception as e:
                self._json({"ok": False, "error": "保存失败: %r" % e})
            return
        if path == "/api/arena/raw":
            name = data.get("name", "")
            content = data.get("content", "")
            try:
                if "/" in name or "\\" in name or not name.endswith(".yml"):
                    raise ValueError("地图名非法")
                arena_path = os.path.join(CFG["server_dir"], BW, "Arenas", name)
                bak = backup_file(arena_path)
                with open(arena_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
                self._json({"ok": True, "message": "已保存 %s（备份: %s）" % (name, os.path.basename(bak))})
            except Exception as e:
                self._json({"ok": False, "error": "保存失败: %r" % e})
            return
        if path == "/api/groups":
            groups = data.get("groups") or []
            try:
                cfg_path = os.path.join(CFG["server_dir"], BW, "config.yml")
                text = read_yaml(cfg_path)
                new_text = set_arena_groups(text, [str(g).strip() for g in groups if str(g).strip()])
                bak = backup_file(cfg_path)
                with open(cfg_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(new_text)
                self._json({"ok": True, "message": "已更新 arenaGroups（备份: %s）" % os.path.basename(bak)})
            except Exception as e:
                self._json({"ok": False, "error": "保存失败: %r" % e})
            return
        if path == "/api/console":
            ok, msg = SERVER.send_command(data.get("command", ""))
            self._json({"ok": ok, "message": msg, "error": "" if ok else msg})
            return
        if path == "/api/forms":
            form = next((f for f in FORMS if f["id"] == data.get("id")), None)
            if form is None:
                self._json({"ok": False, "error": "未知配置"})
                return
            try:
                bak = apply_form_values(form, CFG["server_dir"], data.get("values") or {})
                self._json({"ok": True, "message": "已保存 %s（备份: %s）" % (form["title"], os.path.basename(bak))})
            except Exception as e:
                self._json({"ok": False, "error": "保存失败: %r" % e})
            return
        if path == "/api/openconsole":
            ok, msg = SERVER.open_vanilla_console()
            self._json({"ok": ok, "message": msg, "error": "" if ok else msg})
            return
        if path == "/api/java/download":
            ok, msg = JAVA_DOWNLOADER.start()
            self._json({"ok": ok, "message": msg, "error": "" if ok else msg})
            return
        if path == "/api/homeconfig":
            try:
                baks = apply_home_config(CFG["server_dir"], data.get("values") or {})
                self._json({"ok": True, "message": "已保存服务器基本配置（备份 %d 个文件，重启服务器生效）" % len(baks)})
            except Exception as e:
                self._json({"ok": False, "error": "保存失败: %r" % e})
            return
        if path == "/api/players/whitelist":
            name = str(data.get("name", "")).strip()
            action = str(data.get("action", "add")).strip().lower()
            if not name:
                self._json({"ok": False, "error": "玩家名不能为空"})
                return
            if action not in ("add", "remove"):
                self._json({"ok": False, "error": "未知操作"})
                return
            db = os.path.join(CFG["server_dir"], "plugins", "IpacWhitelist", "Data.sqlite3")
            if action == "add":
                cmd = "wl add " + name
                ok, msg = SERVER.send_command(cmd)
                p = _find_player(CFG["server_dir"], name) or {"uuid": ""}
                if p.get("uuid"):
                    _sqlite_exec(db, "UPDATE player SET UUID=? WHERE lower(Name)=lower(?)", (p["uuid"], name))
                SERVER.send_command("wl reload")
                self._json({"ok": ok, "message": "已添加白名单 %s" % name, "error": "" if ok else msg})
            else:
                ok, msg = SERVER.send_command("wl del " + name)
                _sqlite_exec(db, "DELETE FROM player WHERE lower(Name)=lower(?)", (name,))
                SERVER.send_command("wl reload")
                self._json({"ok": True, "message": "已移除白名单 %s" % name})
            return
        if path == "/api/players/ban":
            name = str(data.get("name", "")).strip()
            reason = str(data.get("reason", "") or "由面板封禁").strip()
            if not name:
                self._json({"ok": False, "error": "玩家名不能为空"})
                return
            p = _find_player(CFG["server_dir"], name) or {"uuid": ""}
            db = os.path.join(CFG["server_dir"], "plugins", "AdvancedBanZ", "data", "storage.db")
            now = int(time.time() * 1000)
            ok1 = _sqlite_exec(db, "INSERT INTO Punishments (name,uuid,reason,operator,punishmentType,start,end,calculation) VALUES (?,?,?,?,?,?,?,?)",
                               (name, p.get("uuid", ""), reason, "面板", "BAN", now, -1, ""))
            _sqlite_exec(db, "INSERT INTO PunishmentHistory (name,uuid,reason,operator,punishmentType,start,end,calculation) VALUES (?,?,?,?,?,?,?,?)",
                         (name, p.get("uuid", ""), reason, "面板", "BAN", now, -1, ""))
            SERVER.send_command("advancedbanz:advancedban reload")
            SERVER.send_command("kick %s %s" % (name, reason))
            if ok1:
                self._json({"ok": True, "message": "已封禁 %s（AdvancedBanZ 已重载）" % name})
            else:
                self._json({"ok": False, "error": "写入封禁数据库失败"})
            return
        if path == "/api/players/unban":
            name = str(data.get("name", "")).strip()
            if not name:
                self._json({"ok": False, "error": "玩家名不能为空"})
                return
            db = os.path.join(CFG["server_dir"], "plugins", "AdvancedBanZ", "data", "storage.db")
            ok1 = _sqlite_exec(db, "DELETE FROM Punishments WHERE lower(name)=lower(?) AND upper(punishmentType) LIKE '%BAN%'", (name,))
            SERVER.send_command("advancedbanz:advancedban reload")
            if ok1:
                self._json({"ok": True, "message": "已解封 %s" % name})
            else:
                self._json({"ok": False, "error": "解除封禁失败"})
            return
        if path == "/api/updater/run":
            ok, msg = UPDATER.start(data.get("targets") or [])
            self._json({"ok": ok, "message": msg, "error": "" if ok else msg})
            return
        self._json({"ok": False, "error": "unknown endpoint"}, 404)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def port_free(port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False


def main():
    args = sys.argv[1:]
    no_browser = "--no-browser" in args
    port = int(CFG.get("panel_port", 8765))
    if not port_free(port):
        # 已经有一个面板占用端口时不重复启动，直接打开现有面板
        url = "http://127.0.0.1:%d/" % port
        print("面板已经在运行: %s" % url)
        if not no_browser:
            webbrowser.open(url)
        return
    httpd = ThreadedHTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/" % port
    print("=" * 60)
    print(" BedWars 服务器面板已启动")
    print(" 地址: %s" % url)
    print(" 服务器目录: %s" % CFG.get("server_dir"))
    print(" 按 Ctrl+C 退出面板")
    print("=" * 60)
    if not no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
