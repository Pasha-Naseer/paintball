import math
import random
import time
import json
import os
import datetime
import tempfile
import tkinter as tk
from tkinter import simpledialog, messagebox

WIDTH = 960  # 960
HEIGHT = 640  # 640
BG = "#0b1020"
GRID = "#151e35"
CYAN = "#54e6dc"
BLUE = "#5c8dff"
PINK = "#ff5d8f"
GOLD = "#ffd166"
WHITE = "#edf4ff"
MUTED = "#8492ad"
GREEN = "#8be28b"
YELLOW = "#FED049"

# Leaderboard settings
RECORDS_FILE = "paintball-records.json"
MAX_PLAYER_NAME_LENGTH = 12
MAX_LEADERBOARD_ENTRIES = 10
CHECKPOINT_FILE = "paintball-checkpoint.json"
MAX_MINES = 3
MINE_ARM_TIME = 0.9
MINE_TRIGGER_RADIUS = 72
MINE_BLAST_RADIUS = 145
MINE_DAMAGE = 125
MINE_UNLOCK_WAVE = 40

# Absolute Power settings (activates once wave 100 has been cleared)
ABSOLUTE_POWER_WAVE = 101
POWER_MAX_HEALTH = 250
POWER_REGEN = 6              # health per second
POWER_DAMAGE_MULT = 2.5      # player bullet / mine damage multiplier
POWER_DAMAGE_TAKEN = 0.5     # incoming damage multiplier
POWER_SPEED_MULT = 1.3
POWER_MAX_MINES = 10


def clamp(value, low, high):
    return max(low, min(high, value))


def distance(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

def load_records(filename=RECORDS_FILE):
    """Load records, normalize player names, and keep only each player's best score."""

    if not os.path.exists(filename):
        return {}

    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)

    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        backup_name = (
            f"{filename}.corrupt-"
            f"{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )

        try:
            os.replace(filename, backup_name)
            print(
                f"Invalid leaderboard backed up as '{backup_name}': {error}"
            )
        except OSError as backup_error:
            print(
                f"Invalid leaderboard ({error}); "
                f"could not create backup ({backup_error})."
            )

        return {}

    except OSError as error:
        print(f"Could not read leaderboard: {error}")
        return {}

    if not isinstance(data, dict):
        print("Invalid leaderboard format. Expected a JSON object.")
        return {}

    # Store one entry per normalized player name.
    best_players = {}

    for timestamp, player_data in data.items():
        if not isinstance(timestamp, str) or not isinstance(player_data, dict):
            continue

        for player_name, score in player_data.items():
            if not (
                    isinstance(player_name, str)
                    and player_name.strip()
                    and isinstance(score, int)
                    and not isinstance(score, bool)
                    and score >= 0
            ):
                continue

            normalized_name = player_name.strip().lower()
            previous = best_players.get(normalized_name)

            if previous is None or score > previous[1]:
                best_players[normalized_name] = (timestamp, score)

    # Preserve the timestamp of each player's highest-scoring record.
    cleaned_records = {}

    for player_name, (timestamp, score) in best_players.items():
        cleaned_records.setdefault(timestamp, {})[player_name] = score

    # Persist cleanup so old duplicate/capitalized records are removed from JSON.
    if cleaned_records != data:
        if not save_records(cleaned_records, filename):
            print("Leaderboard cleanup could not be saved.")

    return cleaned_records


def save_records(data, filename=RECORDS_FILE):
    """Save records atomically to reduce the risk of a partial write."""

    directory = os.path.dirname(os.path.abspath(filename))
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=directory,
                delete=False,
                suffix=".tmp"
        ) as temp_file:
            temp_path = temp_file.name
            json.dump(data, temp_file, indent=4, ensure_ascii=False)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, filename)
        return True

    except (OSError, TypeError, ValueError) as error:
        print(f"Could not save leaderboard: {error}")

        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

        return False


def build_leaderboard(records):
    """Return each player's best score, sorted from highest to lowest."""

    best_scores = {}

    for player_data in records.values():
        for player_name, score in player_data.items():
            normalized_name = player_name.strip().lower()

            if not normalized_name:
                continue

            previous = best_scores.get(normalized_name)

            if previous is None or score > previous[1]:
                best_scores[normalized_name] = (player_name, score)

    leaderboard = list(best_scores.values())

    return sorted(
        leaderboard,
        key=lambda item: (-item[1], item[0].lower())
    )


def save_player_score(player_name, score):
    """Save a player's score, keeping only their highest score."""

    if not isinstance(player_name, str) or not player_name.strip():
        return False

    if not isinstance(score, int) or isinstance(score, bool) or score < 0:
        return False

    normalized_name = player_name.strip().lower()
    records = load_records()

    # Find this player's existing best score.
    existing_best = max(
        (
            player_data[normalized_name]
            for player_data in records.values()
            if normalized_name in player_data
        ),
        default=None
    )

    # Do not replace a higher score with a lower or equal score.
    if existing_best is not None and score <= existing_best:
        return True

    # Remove any previous entry for this player.
    for timestamp in list(records):
        records[timestamp].pop(normalized_name, None)

        if not records[timestamp]:
            del records[timestamp]

    # Save the new best score using a lowercase player name.
    timestamp = datetime.datetime.now().isoformat(timespec="microseconds")

    while timestamp in records:
        timestamp = (
                datetime.datetime.now().isoformat(timespec="microseconds")
                + f"-{time.time_ns()}"
        )

    records[timestamp] = {normalized_name: score}
    return save_records(records)


# ---------------------------------------------------------------------------
# Checkpoint persistence
# ---------------------------------------------------------------------------

def save_checkpoint(data):
    temp_path = CHECKPOINT_FILE + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, CHECKPOINT_FILE)
        return True
    except (OSError, TypeError, ValueError) as error:
        print(f"Checkpoint save failed: {error}")
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        return False


def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return None
        wave = data.get("wave")
        if not isinstance(wave, int) or isinstance(wave, bool) or wave < 1:
            return None
        return data
    except (OSError, json.JSONDecodeError):
        return None


def delete_checkpoint():
    try:
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
    except OSError as error:
        print(f"Could not delete checkpoint: {error}")


# ---------------------------------------------------------------------------
# Weapons
# ---------------------------------------------------------------------------

class Weapon:
    def __init__(
            self,
            name,
            damage,
            magazine_size,
            fire_delay,
            reload_time,
            bullet_speed,
            bullet_color=CYAN
    ):
        self.name = name
        self.damage = damage
        self.magazine_size = magazine_size
        self.ammo = magazine_size
        self.fire_delay = fire_delay
        self.reload_time = reload_time
        self.bullet_speed = bullet_speed
        self.bullet_color = bullet_color
        self.last_shot = 0
        self.reloading_until = 0

    @property
    def is_reloading(self):
        return time.time() < self.reloading_until

    def reload(self):
        if self.ammo < self.magazine_size and not self.is_reloading:
            self.reloading_until = time.time() + self.reload_time
            return True
        return False

    def update(self):
        if self.reloading_until and time.time() >= self.reloading_until:
            self.ammo = self.magazine_size
            self.reloading_until = 0

    def attack(self, x, y, target_x, target_y):
        now = time.time()
        self.update()

        if self.is_reloading or self.ammo <= 0:
            return None

        if now - self.last_shot < self.fire_delay:
            return None

        self.last_shot = now
        self.ammo -= 1

        angle = math.atan2(target_y - y, target_x - x)

        return [{
            "x": x + math.cos(angle) * 22,
            "y": y + math.sin(angle) * 22,
            "vx": math.cos(angle) * self.bullet_speed,
            "vy": math.sin(angle) * self.bullet_speed,
            "damage": self.damage,
            "color": self.bullet_color,
            "radius": 4,
        }]


class AutomaticGun(Weapon):
    def __init__(self):
        super().__init__(
            name="PULSE RIFLE",
            damage=25,
            magazine_size=34,
            fire_delay=0.14,
            reload_time=1.15,
            bullet_speed=650,
            bullet_color=CYAN
        )


class Shotgun(Weapon):
    def __init__(self):
        super().__init__(
            name="NOVA SHOTGUN",
            damage=17,
            magazine_size=7,
            fire_delay=0.58,
            reload_time=1.45,
            bullet_speed=520,
            bullet_color=GOLD
        )

    def attack(self, x, y, target_x, target_y):
        now = time.time()
        self.update()

        if self.is_reloading or self.ammo <= 0:
            return None

        if now - self.last_shot < self.fire_delay:
            return None

        self.last_shot = now
        self.ammo -= 1

        base_angle = math.atan2(target_y - y, target_x - x)
        pellets = []

        for offset in (-0.22, -0.11, 0, 0.11, 0.22):
            angle = base_angle + offset
            pellets.append({
                "x": x + math.cos(angle) * 22,
                "y": y + math.sin(angle) * 22,
                "vx": math.cos(angle) * self.bullet_speed,
                "vy": math.sin(angle) * self.bullet_speed,
                "damage": self.damage,
                "color": self.bullet_color,
                "radius": 3,
            })

        return pellets


class RPG(Weapon):
    """Slow rocket launcher with a powerful area-of-effect explosion."""

    def __init__(self):
        super().__init__(
            name="RPG-7 LAUNCHER",
            damage=135,
            magazine_size=1,
            fire_delay=1.15,
            reload_time=2.8,
            bullet_speed=360,
            bullet_color="#ff8c42",
        )

    def attack(self, x, y, target_x, target_y):
        rockets = super().attack(x, y, target_x, target_y)
        if rockets:
            rocket = rockets[0]
            rocket["radius"] = 7
            rocket["splash_radius"] = 105
            rocket["explosive"] = True
        return rockets


class AK_47(Weapon):
    def __init__(self):
        super().__init__(
            name="AK-47 (Kalashnikov)",
            damage=29,
            magazine_size=30,
            fire_delay=0.09,
            reload_time=1.0,
            bullet_speed=690,
            bullet_color=YELLOW
        )


class SMG(Weapon):
    """Very fast submachine gun with a large magazine."""

    def __init__(self):
        super().__init__(
            name="VIPER SMG",
            damage=15,
            magazine_size=45,
            fire_delay=0.055,
            reload_time=1.25,
            bullet_speed=730,
            bullet_color="#72f1b8"
        )


class SniperRifle(Weapon):
    """Slow, accurate rifle that deals heavy single-shot damage."""

    def __init__(self):
        super().__init__(
            name="LONGSHOT SNIPER",
            damage=125,
            magazine_size=5,
            fire_delay=0.85,
            reload_time=2.0,
            bullet_speed=1120,
            bullet_color="#b9a0ff"
        )

    def attack(self, x, y, target_x, target_y):
        shots = super().attack(x, y, target_x, target_y)
        if shots:
            shots[0]["radius"] = 5
        return shots


class Minigun(Weapon):
    """Extremely high fire rate, balanced by modest damage and slow reload."""

    def __init__(self):
        super().__init__(
            name="TITAN MINIGUN",
            damage=12,
            magazine_size=100,
            fire_delay=0.035,
            reload_time=3.4,
            bullet_speed=760,
            bullet_color="#ffcf70"
        )


class BurstRifle(Weapon):
    """Fires a three-projectile burst with a small spread."""

    def __init__(self):
        super().__init__(
            name="TRIDENT BURST RIFLE",
            damage=13,
            magazine_size=27,
            fire_delay=0.32,
            reload_time=1.65,
            bullet_speed=790,
            bullet_color="#70c7ff"
        )

    def attack(self, x, y, target_x, target_y):
        shots = super().attack(x, y, target_x, target_y)
        if not shots:
            return shots

        base = shots[0]
        angle = math.atan2(target_y - y, target_x - x)
        burst = []
        for offset in (-0.075, 0, 0.075):
            shot_angle = angle + offset
            burst.append({
                "x": x + math.cos(shot_angle) * 22,
                "y": y + math.sin(shot_angle) * 22,
                "vx": math.cos(shot_angle) * self.bullet_speed,
                "vy": math.sin(shot_angle) * self.bullet_speed,
                "damage": self.damage,
                "color": self.bullet_color,
                "radius": 3,
            })
        return burst


class Flamethrower(Weapon):
    """Short-range-feeling stream of slow, large flame projectiles."""

    def __init__(self):
        super().__init__(
            name="INFERNO FLAMETHROWER",
            damage=9,
            magazine_size=90,
            fire_delay=0.045,
            reload_time=2.5,
            bullet_speed=390,
            bullet_color="#ff7138"
        )

    def attack(self, x, y, target_x, target_y):
        shots = super().attack(x, y, target_x, target_y)
        if shots:
            shots[0]["radius"] = 7
            shots[0]["damage"] = 11
        return shots


class Railgun(Weapon):
    """Very powerful energy shot with a tiny magazine."""

    def __init__(self):
        super().__init__(
            name="APEX RAILGUN",
            damage=190,
            magazine_size=3,
            fire_delay=1.25,
            reload_time=2.6,
            bullet_speed=1450,
            bullet_color="#ff5de4"
        )

    def attack(self, x, y, target_x, target_y):
        shots = super().attack(x, y, target_x, target_y)
        if shots:
            shots[0]["radius"] = 6
        return shots


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------

class Character:
    def __init__(self, x, y, health):
        self.x = x
        self.y = y
        self.health = health
        self.max_health = health
        self.alive = True

    def take_damage(self, amount):
        self.health -= amount

        if self.health <= 0:
            self.health = 0
            self.alive = False


class Player(Character):
    def __init__(self):
        super().__init__(WIDTH / 2, HEIGHT / 2, 100)
        self.base_speed = 245
        self.speed = self.base_speed
        self.absolute_power = False
        self.weapon = AutomaticGun()
        self.weapons = [
            self.weapon,
            Shotgun(),
            RPG(),
            AK_47(),
            SMG(),
            SniperRifle(),
            Minigun(),
            BurstRifle(),
            Flamethrower(),
            Railgun(),
        ]
        self.weapon_index = 0
        self.unlocked_weapon_count = 1
        self.score = 0
        self.kills = 0

    def take_damage(self, amount):
        # Absolute Power halves all incoming damage.
        if self.absolute_power:
            amount *= POWER_DAMAGE_TAKEN
        super().take_damage(amount)

    def unlock_weapons_for_wave(self, wave):
        """Unlock one additional weapon every ten waves."""
        new_count = min(len(self.weapons), 1 + max(0, wave // 10))
        if new_count <= self.unlocked_weapon_count:
            return None

        self.unlocked_weapon_count = new_count
        return self.weapons[new_count - 1].name

    def move(self, dx, dy, dt):
        length = math.hypot(dx, dy)

        if length:
            dx, dy = dx / length, dy / length
            self.x += dx * self.speed * dt
            self.y += dy * self.speed * dt

        self.x = clamp(self.x, 24, WIDTH - 24)
        self.y = clamp(self.y, 76, HEIGHT - 24)

    def switch_weapon(self):
        self.weapon_index = (self.weapon_index + 1) % self.unlocked_weapon_count
        self.weapon = self.weapons[self.weapon_index]


class Enemy(Character):
    def __init__(self, x, y, wave):
        health = 45 + wave * 7
        super().__init__(x, y, health)
        self.speed = random.uniform(100, 150) + min(wave * 40, 35)
        self.radius = random.randint(13, 18)
        self.damage = 13
        self.attack_cooldown = 0
        self._kill_awarded = False
        self.is_checkpoint = False

    def chase(self, player, dt):
        angle = math.atan2(player.y - self.y, player.x - self.x)
        self.x += math.cos(angle) * self.speed * dt
        self.y += math.sin(angle) * self.speed * dt


BOSS_TYPES = [
    {   # 1
        "name": "WARDEN", "color": GOLD, "fill": "#56351d",
        "radius": 0, "hp": 1.0, "spd": 1.0, "bspd": 1.0, "ivl": 1.0,
        "dash_from": 2, "dash_every": 5.0,
        "summon_from": 2, "summon_time": 9.0,
        "patterns": {
            1: ["single", "fan"],
            2: ["fan", "ring", "burst"],
            3: ["ring", "fan", "burst", "ring"],
        },
    },
    {   # 2
        "name": "STRIKER", "color": "#ff6b6b", "fill": "#4a1c1c",
        "radius": -4, "hp": 0.85, "spd": 1.35, "bspd": 1.1, "ivl": 0.85,
        "dash_from": 1, "dash_every": 3.2,
        "patterns": {
            1: ["burst", "single"],
            2: ["burst", "fan", "burst"],
            3: ["burst", "fan", "burst", "ring"],
        },
    },
    {   # 3
        "name": "VORTEX", "color": "#b388ff", "fill": "#2f2250",
        "radius": 0, "hp": 1.0, "spd": 1.0, "bspd": 0.9, "ivl": 0.55,
        "orbit": True,
        "patterns": {
            1: ["spiral"],
            2: ["spiral", "fan"],
            3: ["spiral", "ring", "spiral"],
        },
    },
    {   # 4
        "name": "HIVE QUEEN", "color": GREEN, "fill": "#1f3a24",
        "radius": 2, "hp": 1.15, "spd": 0.95, "bspd": 1.0, "ivl": 1.1,
        "summon_from": 1, "summon_time": 6.5, "summon_cap": 10, "summon_bonus": 1,
        "patterns": {
            1: ["single", "shotgun"],
            2: ["shotgun", "fan", "ring"],
            3: ["shotgun", "ring", "fan", "shotgun"],
        },
    },
    {   # 5
        "name": "PHANTOM", "color": CYAN, "fill": "#143a3c",
        "radius": -2, "hp": 0.95, "spd": 1.15, "bspd": 1.2, "ivl": 0.9,
        "blink_from": 1, "blink_every": 3.2,
        "patterns": {
            1: ["snipe", "fan"],
            2: ["snipe", "burst", "fan"],
            3: ["snipe", "snipe", "ring", "burst"],
        },
    },
    {   # 6
        "name": "TEMPEST", "color": BLUE, "fill": "#1a2650",
        "radius": 0, "hp": 1.1, "spd": 1.0, "bspd": 1.0, "ivl": 0.8,
        "dash_from": 3, "dash_every": 4.5,
        "patterns": {
            1: ["cross", "single"],
            2: ["cross", "ring", "spiral"],
            3: ["cross", "ring", "spiral", "cross"],
        },
    },
    {   # 7
        "name": "JUGGERNAUT", "color": "#ff8c42", "fill": "#4a2a12",
        "radius": 10, "hp": 1.6, "spd": 0.9, "bspd": 1.0, "ivl": 1.0,
        "dash_from": 1, "dash_every": 4.0, "dash_ring": True,
        "patterns": {
            1: ["shotgun", "wall"],
            2: ["shotgun", "wall", "ring"],
            3: ["wall", "shotgun", "ring", "wall"],
        },
    },
    {   # 8
        "name": "ECLIPSE", "color": "#c0c8ff", "fill": "#262a4a",
        "radius": 0, "hp": 1.0, "spd": 1.25, "bspd": 1.15, "ivl": 0.8,
        "dash_from": 2, "dash_every": 4.0, "blink_from": 2, "blink_every": 3.6,
        "patterns": {
            1: ["burst", "snipe"],
            2: ["burst", "cross", "snipe"],
            3: ["cross", "snipe", "burst", "ring"],
        },
    },
    {   # 9
        "name": "NOVA", "color": "#ff5de4", "fill": "#4a1844",
        "radius": 2, "hp": 1.2, "spd": 1.1, "bspd": 1.0, "ivl": 0.75,
        "orbit": True,
        "patterns": {
            1: ["wall", "cross"],
            2: ["wall", "cross", "ring"],
            3: ["wall", "cross", "ring", "spiral"],
        },
    },
    {   # 10
        "name": "OVERLORD", "color": "#ff3b30", "fill": "#3a0d0d",
        "radius": 6, "hp": 1.5, "spd": 1.15, "bspd": 1.1, "ivl": 0.8,
        "dash_from": 1, "dash_every": 3.5, "blink_from": 2, "blink_every": 3.4,
        "summon_from": 1, "summon_time": 7.5,
        "patterns": {
            1: ["fan", "burst", "wall"],
            2: ["ring", "wall", "burst", "cross", "snipe"],
            3: ["cross", "ring", "wall", "burst", "spiral", "snipe"],
        },
    },
]


class BossEnemy(Enemy):
    """
    A massive multi-phase boss. Every ten waves brings a different boss
    (BOSS_TYPES cycles after wave 100, and keeps getting stronger).

    Phase 1 (>66% health), Phase 2 (>33%) and Phase 3 (<=33%) unlock
    progressively nastier attack patterns and faster attack rates.
    """

    def __init__(self, x, y, wave):
        super().__init__(x, y, wave)

        tier = max(1, wave // 10)
        cfg = BOSS_TYPES[(tier - 1) % len(BOSS_TYPES)]
        self.cfg = cfg
        self.tier = tier
        self.wave = wave
        self.cycle = (tier - 1) // len(BOSS_TYPES)

        self.boss_name = cfg["name"] + (f" MK{self.cycle + 1}" if self.cycle else "")
        self.color = cfg["color"]
        self.body_fill = cfg["fill"]

        self.max_health = int((2000 + wave * 130 + tier * tier * 45) * cfg["hp"] * 0.88)
        self.health = self.max_health
        self.radius = 34 + min(tier // 2, 8) + cfg["radius"]
        self.base_speed = (105 + min(wave * 0.7, 70)) * cfg["spd"]
        self.speed = self.base_speed
        self.damage = min(60, 25 + int(tier * 2))
        self.attack_cooldown = 0
        self.is_checkpoint = True
        self.is_boss = True

        # Projectile stats.
        self.bullet_damage = int(min(36, 12 + tier * 1.6))
        self.bullet_speed = (255 + min(135, wave * 1.3)) * cfg["bspd"]

        # Behaviour state.
        self.phase = 1
        self.shot_timer = 0.9
        self.pattern_step = 0
        self.ring_offset = 0.0
        self.spin = random.random() * math.tau
        self.summon_timer = min(6.0, cfg.get("summon_time", 9.0))
        self.dash_timer = min(3.5, cfg.get("dash_every", 5.0))
        self.dash_time_left = 0.0
        self.dash_angle = 0.0
        self.blink_timer = cfg.get("blink_every", 3.2)
        self.orbit_dir = random.choice((-1, 1))
        self.orbit_flip = random.uniform(2.5, 5.0)
        self.blink_flash = False
        self.pending_message = None

    # -- projectile helpers -------------------------------------------------

    def _fire(self, bullets, angle, speed_mult=1.0, radius=7,
              ox=0.0, oy=0.0, dmg_mult=1.0):
        speed = self.bullet_speed * speed_mult
        bullets.append({
            "x": self.x + ox,
            "y": self.y + oy,
            "vx": math.cos(angle) * speed,
            "vy": math.sin(angle) * speed,
            "radius": radius,
            "damage": max(1, int(self.bullet_damage * dmg_mult)),
            "life": 4.0,
            "color": self.color,
        })

    def _fire_fan(self, bullets, angle, count, spread=0.2):
        start = -spread * (count - 1) / 2
        for i in range(count):
            self._fire(bullets, angle + start + i * spread)

    def _fire_ring(self, bullets, count):
        for i in range(count):
            angle = self.ring_offset + math.tau * i / count
            self._fire(bullets, angle, speed_mult=0.75, radius=6)
        self.ring_offset += 0.21

    def _ring_count(self):
        return 10 + 4 * (self.phase - 1) + min(self.tier, 10) + self.cycle * 2

    # -- attack patterns ----------------------------------------------------

    def _pattern(self, name, player, bullets):
        angle = math.atan2(player.y - self.y, player.x - self.x)
        extra = self.cycle * 2
        fan_n = 3 + min(self.tier // 3, 5) + 2 * (self.phase - 1) + extra

        if name == "single":
            self._fire(bullets, angle, 1.15)

        elif name == "fan":
            self._fire_fan(bullets, angle, fan_n)

        elif name == "ring":
            self._fire_ring(bullets, self._ring_count())

        elif name == "burst":
            mults = (1.0, 1.18, 1.36) + ((1.54, 1.72) if self.phase == 3 else ())
            for m in mults:
                self._fire(bullets, angle, m)

        elif name == "spiral":
            arms = 3 + self.phase + self.cycle
            for i in range(arms):
                self._fire(bullets, self.spin + math.tau * i / arms,
                           speed_mult=0.85, radius=6)
            self.spin += 0.33

        elif name == "cross":
            axes = 4 if self.phase < 3 else 8
            for i in range(axes):
                a = self.spin + math.tau * i / axes
                self._fire(bullets, a, 0.8)
                self._fire(bullets, a, 1.1)
            self.spin += 0.4

        elif name == "wall":
            perp = angle + math.pi / 2
            count = 11 + extra
            gap = random.randint(1, count - 4)
            for k in range(count):
                if gap <= k < gap + 3:
                    continue
                off = (k - (count - 1) / 2) * 30
                self._fire(bullets, angle, 0.7, 6,
                           ox=math.cos(perp) * off, oy=math.sin(perp) * off)

        elif name == "snipe":
            self._fire(bullets, angle, 2.0, 6, dmg_mult=1.6)

        elif name == "shotgun":
            for _ in range(7 + self.phase * 2 + extra):
                a = angle + random.uniform(-0.38, 0.38)
                self._fire(bullets, a, random.uniform(0.75, 1.1), 5, dmg_mult=0.65)

    # -- special abilities --------------------------------------------------

    def _summon(self, enemies):
        cfg = self.cfg
        alive_minions = sum(
            1 for e in enemies
            if getattr(e, "is_minion", False) and e.alive
        )
        room = cfg.get("summon_cap", 8) - alive_minions
        count = min(room, 2 + min(self.tier // 5, 2) + cfg.get("summon_bonus", 0))
        if count <= 0:
            return False

        for _ in range(count):
            angle = random.random() * math.tau
            mx = clamp(self.x + math.cos(angle) * (self.radius + 30), 25, WIDTH - 25)
            my = clamp(self.y + math.sin(angle) * (self.radius + 30), 95, HEIGHT - 25)
            minion = Enemy(mx, my, self.wave)
            minion.health = minion.max_health = max(
                40, int(minion.max_health * 0.45)
            )
            minion.is_minion = True
            minion._kill_awarded = True  # minions give no score or drops
            enemies.append(minion)
        return True

    def _blink(self, player):
        lo_x, hi_x = self.radius + 5, WIDTH - self.radius - 5
        lo_y, hi_y = 85 + self.radius, HEIGHT - self.radius - 5
        for _ in range(10):
            angle = random.random() * math.tau
            r = random.uniform(200, 320)
            nx = player.x + math.cos(angle) * r
            ny = player.y + math.sin(angle) * r
            if lo_x <= nx <= hi_x and lo_y <= ny <= hi_y:
                break
        else:
            nx = clamp(nx, lo_x, hi_x)
            ny = clamp(ny, lo_y, hi_y)
        self.blink_flash = True
        self.x, self.y = nx, ny
        self.blink_flash = True
        self.shot_timer = min(self.shot_timer, 0.2)

    # -- main AI ------------------------------------------------------------

    def update_ai(self, player, dt, enemy_bullets, enemies=None):
        cfg = self.cfg

        ratio = self.health / self.max_health
        new_phase = 1 if ratio > 0.66 else (2 if ratio > 0.33 else 3)
        if new_phase != self.phase:
            self.phase = new_phase
            self.pending_message = f"{self.boss_name} ENRAGED - PHASE {new_phase}!"
            self.shot_timer = min(self.shot_timer, 0.4)

        dx = player.x - self.x
        dy = player.y - self.y
        dist = max(1, math.hypot(dx, dy))

        speed = self.base_speed * (1 + 0.2 * (self.phase - 1))
        self.speed = speed

        # Movement.
        if self.dash_time_left > 0:
            self.dash_time_left -= dt
            dash_speed = self.base_speed * 3.2
            self.x += math.cos(self.dash_angle) * dash_speed * dt
            self.y += math.sin(self.dash_angle) * dash_speed * dt
            if self.dash_time_left <= 0 and cfg.get("dash_ring"):
                self._fire_ring(enemy_bullets, self._ring_count())
                self.pending_message = f"{self.boss_name} SHOCKWAVE!"

        elif cfg.get("orbit"):
            self.orbit_flip -= dt
            if self.orbit_flip <= 0:
                self.orbit_dir *= -1
                self.orbit_flip = random.uniform(2.5, 5.0)
            tx = -dy / dist * self.orbit_dir
            ty = dx / dist * self.orbit_dir
            radial = clamp((dist - 230) / 60, -1, 1)
            mx = tx + dx / dist * radial * 0.9
            my = ty + dy / dist * radial * 0.9
            length = max(1, math.hypot(mx, my))
            self.x += mx / length * speed * dt
            self.y += my / length * speed * dt

        else:
            if dist > 175:
                self.x += dx / dist * speed * dt
                self.y += dy / dist * speed * dt
            elif dist < 115:
                self.x -= dx / dist * speed * 0.65 * dt
                self.y -= dy / dist * speed * 0.65 * dt

        # Dash trigger.
        dash_from = cfg.get("dash_from")
        if dash_from and self.phase >= dash_from and self.dash_time_left <= 0:
            self.dash_timer -= dt
            if self.dash_timer <= 0 and dist > 140:
                self.dash_time_left = 0.55
                self.dash_angle = math.atan2(dy, dx)
                self.dash_timer = max(
                    1.6,
                    cfg.get("dash_every", 5.0) - 0.5 * self.phase - self.tier * 0.05
                )

        # Teleport.
        blink_from = cfg.get("blink_from")
        if blink_from and self.phase >= blink_from:
            self.blink_timer -= dt
            if self.blink_timer <= 0:
                self._blink(player)
                self.blink_timer = max(
                    1.4, cfg.get("blink_every", 3.2) - 0.4 * self.phase
                )

        # Keep the boss inside the arena (orbiters reverse direction at walls).
        ux, uy = self.x, self.y
        self.x = clamp(self.x, self.radius + 5, WIDTH - self.radius - 5)
        self.y = clamp(self.y, 85 + self.radius, HEIGHT - self.radius - 5)
        if cfg.get("orbit") and (abs(ux - self.x) > 0.5 or abs(uy - self.y) > 0.5):
            self.orbit_dir *= -1

        # Shooting.
        self.shot_timer -= dt
        if self.shot_timer <= 0:
            patterns = cfg["patterns"][self.phase]
            name = patterns[self.pattern_step % len(patterns)]
            self.pattern_step += 1
            self._pattern(name, player, enemy_bullets)
            base_interval = max(0.42, 1.15 - self.tier * 0.04) * cfg["ivl"]
            self.shot_timer = max(
                0.25, base_interval / (1 + 0.3 * (self.phase - 1))
            )

        # Reinforcements.
        summon_from = cfg.get("summon_from")
        if summon_from and self.phase >= summon_from and enemies is not None:
            self.summon_timer -= dt
            if self.summon_timer <= 0:
                if self._summon(enemies):
                    self.pending_message = f"{self.boss_name} SUMMONS REINFORCEMENTS!"
                self.summon_timer = max(
                    3.5, cfg.get("summon_time", 9.0) - 1.5 * (self.phase - 1)
                )

# ---------------------------------------------------------------------------
# Mines
# ---------------------------------------------------------------------------

class Mine:
    """A proximity mine placed by the player."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.placed_at = time.time()
        self.exploded = False

    @property
    def armed(self):
        return time.time() - self.placed_at >= MINE_ARM_TIME


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

class Equipment:
    color = WHITE

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.active = True
        self.ttl = None  # seconds until the pickup disappears (None = never)

    def pick_up(self, player):
        raise NotImplementedError


class Medkit(Equipment):
    color = GREEN

    def pick_up(self, player):
        before = player.health
        player.health = min(player.max_health, player.health + 30)
        self.active = False
        return player.health - before


class AmmoCrate(Equipment):
    color = GOLD

    def pick_up(self, player):
        for weapon in player.weapons:
            weapon.ammo = weapon.magazine_size
            weapon.reloading_until = 0

        self.active = False
        return 1


# ---------------------------------------------------------------------------
# Waves
# ---------------------------------------------------------------------------

class Level:
    def __init__(self, wave=1, checkpoint_done=False):
        self.wave = wave
        self.spawned = 0
        # Every tenth wave is a dedicated boss fight with no regular enemies.
        self.total_to_spawn = 1 if wave % 10 == 0 else (5 if wave == 1 else 5 + wave * 2)
        self.spawn_timer = 0
        self.banner_until = time.time() + 2.8
        self.checkpoint_spawn_number = 1 if wave % 10 == 0 else None

    @property
    def complete(self):
        return self.spawned >= self.total_to_spawn

    def begin_next_wave(self):
        self.wave += 1
        self.spawned = 0
        self.total_to_spawn = 1 if self.wave % 10 == 0 else 5 + self.wave * 2
        self.spawn_timer = 0
        self.banner_until = time.time() + (3.0 if self.wave % 10 == 0 else 2.0)
        self.checkpoint_spawn_number = 1 if self.wave % 10 == 0 else None


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------

class ArenaGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Paintball  |  Python OOP Game")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root,
            width=WIDTH,
            height=HEIGHT,
            bg=BG,
            highlightthickness=0
        )
        self.canvas.pack()

        self.keys = set()
        self.mouse_x = WIDTH / 2
        self.mouse_y = HEIGHT / 2
        self.mouse_down = False

        self.state = "menu"

        # Player identity and leaderboard state.
        self.player_name = ""
        self.records = load_records()
        self.score_saved = False

        self.player = Player()
        self.level = Level()

        self.enemies = []
        self.bullets = []
        self.explosions = []
        self.enemy_bullets = []
        self.pickups = []
        self.particles = []
        self.mines = []

        self.last_time = time.perf_counter()
        self.message = ""
        self.message_until = 0
        self.shake = 0
        self.boss_pickup_timer = 4.0

        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        self.root.bind("<KeyPress>", self.on_key_down)
        self.root.bind("<KeyRelease>", self.on_key_up)
        self.root.bind("<Return>", self.start_game)
        self.root.bind("<space>", self.on_space)
        self.root.bind("<Escape>", lambda _event: self.toggle_pause())

        self.root.focus_set()

        # Save the current run if the window is closed.
        self.root.protocol("WM_DELETE_WINDOW", self.close_game)

        self.draw()
        self.loop()

    # -----------------------------------------------------------------------
    # Player registration and score saving
    # -----------------------------------------------------------------------

    def enter_player_name(self):
        """Ask for a non-empty player name of at most 12 characters."""

        while True:
            name = simpledialog.askstring(
                "Player Registration",
                f"Enter your player name "
                f"(maximum {MAX_PLAYER_NAME_LENGTH} characters):",
                parent=self.root
            )

            if name is None:
                return None

            name = name.strip()

            if not name:
                messagebox.showwarning(
                    "Invalid Name",
                    "Player name cannot be empty.",
                    parent=self.root
                )
                continue

            if len(name) > MAX_PLAYER_NAME_LENGTH:
                messagebox.showwarning(
                    "Name Too Long",
                    f"Your name must not exceed "
                    f"{MAX_PLAYER_NAME_LENGTH} characters.",
                    parent=self.root
                )
                continue

            return name

    def save_score(self):
        """Save the current game's score no more than once."""

        if self.score_saved or not self.player_name:
            return

        success = save_player_score(
            self.player_name,
            self.player.score
        )

        if success:
            self.score_saved = True
            self.records = load_records()
        else:
            print("Your score could not be saved.")

    def save_checkpoint(self):
        player = self.player
        data = {
            "wave": self.level.wave,
            "player_name": self.player_name,
            "health": player.health,
            "score": player.score,
            "kills": player.kills,
            "weapon_index": player.weapon_index,
            "ammo": [weapon.ammo for weapon in player.weapons],
        }
        if save_checkpoint(data):
            self.level.checkpoint_spawn_number = None
            self.set_message("CHECKPOINT SAVED!")
            return True
        self.set_message("CHECKPOINT SAVE FAILED!")
        return False

    def close_game(self):
        """Save an unfinished run before closing the application."""

        if self.state in ("playing", "paused"):
            self.save_score()

        self.root.destroy()

    # -----------------------------------------------------------------------
    # Absolute Power
    # -----------------------------------------------------------------------

    def activate_absolute_power(self, silent=False):
        """Grant the player every upgrade once wave 100 has been conquered."""

        player = self.player
        if player.absolute_power:
            return

        player.absolute_power = True
        player.max_health = POWER_MAX_HEALTH
        player.health = player.max_health
        player.speed = player.base_speed * POWER_SPEED_MULT
        player.unlocked_weapon_count = len(player.weapons)

        for weapon in player.weapons:
            weapon.ammo = weapon.magazine_size
            weapon.reloading_until = 0

        if not silent:
            self.set_message("ABSOLUTE POWER ACTIVATED!")
            self.message_until = time.time() + 3.5
            self.shake = max(self.shake, 0.4)
            self.add_burst(player.x, player.y, GOLD, 40)
            self.add_burst(player.x, player.y, CYAN, 40)

    # -----------------------------------------------------------------------
    # Game controls
    # -----------------------------------------------------------------------

    def start_game(self, _event=None):
        if self.state not in ("menu", "gameover"):
            return

        checkpoint = load_checkpoint()
        continue_game = False
        if checkpoint:
            continue_game = messagebox.askyesno(
                "Checkpoint Found",
                f"Checkpoint found at Wave {checkpoint['wave']}.\n\nDo you want to continue?",
                parent=self.root
            )

        if continue_game:
            self.player_name = checkpoint.get("player_name", "Player")
        else:
            player_name = self.enter_player_name()
            if player_name is None:
                return
            self.player_name = player_name
            delete_checkpoint()

        self.player = Player()
        if continue_game and checkpoint["wave"] >= ABSOLUTE_POWER_WAVE:
            self.activate_absolute_power(silent=True)
        if continue_game:
            health = checkpoint.get("health", 100)
            if not isinstance(health, (int, float)) or isinstance(health, bool):
                health = 100
            self.player.health = clamp(health, 1, self.player.max_health)
            for field in ("score", "kills"):
                value = checkpoint.get(field, 0)
                setattr(self.player, field, value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0)
            self.player.unlock_weapons_for_wave(checkpoint["wave"])
            weapon_index = checkpoint.get("weapon_index", 0)
            if not isinstance(weapon_index, int) or isinstance(weapon_index, bool):
                weapon_index = 0
            self.player.weapon_index = clamp(
                weapon_index, 0, self.player.unlocked_weapon_count - 1
            )
            self.player.weapon = self.player.weapons[self.player.weapon_index]
            ammo_data = checkpoint.get("ammo", [])
            if isinstance(ammo_data, list):
                for weapon, ammo in zip(self.player.weapons, ammo_data):
                    if isinstance(ammo, int) and not isinstance(ammo, bool):
                        weapon.ammo = clamp(ammo, 0, weapon.magazine_size)
            self.level = Level(wave=checkpoint["wave"], checkpoint_done=True)
        else:
            self.level = Level()

        self.enemies.clear()
        self.bullets.clear()
        self.explosions.clear()
        self.enemy_bullets.clear()
        self.pickups.clear()
        self.particles.clear()
        self.mines.clear()
        self.boss_pickup_timer = 4.0
        self.score_saved = False
        self.state = "playing"
        self.last_time = time.perf_counter()

    def on_key_down(self, event):
        key = event.keysym.lower()
        self.keys.add(key)

        if key == "r" and self.state == "playing":
            if self.player.weapon.reload():
                self.set_message("RELOADING...")

        elif key == "q" and self.state == "playing":
            self.player.switch_weapon()
            self.set_message(self.player.weapon.name)

        elif key == "e" and self.state == "playing":
            self.place_mine()

        elif key == "p":
            self.toggle_pause()

    def on_key_up(self, event):
        self.keys.discard(event.keysym.lower())

    def on_space(self, _event):
        if self.state == "playing":
            self.shoot()

    def on_mouse_move(self, event):
        self.mouse_x, self.mouse_y = event.x, event.y

    def on_mouse_down(self, _event):
        self.mouse_down = True

        if self.state == "playing":
            self.shoot()

    def on_mouse_up(self, _event):
        self.mouse_down = False

    def toggle_pause(self):
        if self.state == "playing":
            self.state = "paused"

        elif self.state == "paused":
            self.state = "playing"
            self.last_time = time.perf_counter()

    def set_message(self, message):
        self.message = message
        self.message_until = time.time() + 1.25

    def place_mine(self):
        if self.level.wave < MINE_UNLOCK_WAVE:
            self.set_message(f"MINES UNLOCK AT WAVE {MINE_UNLOCK_WAVE}")
            return

        max_mines = POWER_MAX_MINES if self.player.absolute_power else MAX_MINES
        if len(self.mines) >= max_mines:
            self.set_message(f"MAX {max_mines} MINES ACTIVE")
            return
        self.mines.append(Mine(self.player.x, self.player.y))
        self.set_message("MINE DEPLOYED - E TO PLACE")

    def shoot(self):
        player = self.player

        shots = player.weapon.attack(
            player.x,
            player.y,
            self.mouse_x,
            self.mouse_y
        )

        if shots:
            if player.absolute_power:
                # Boosted damage, bigger blasts, infinite ammo, faster fire rate.
                for shot in shots:
                    shot["damage"] = int(shot["damage"] * POWER_DAMAGE_MULT)
                    if "splash_radius" in shot:
                        shot["splash_radius"] *= 1.4
                player.weapon.ammo = player.weapon.magazine_size
                player.weapon.reloading_until = 0
                player.weapon.last_shot -= player.weapon.fire_delay * 0.4
            self.bullets.extend(shots)

        elif player.weapon.ammo == 0 and not player.weapon.is_reloading:
            self.set_message("OUT OF AMMO  —  PRESS R")

    # -----------------------------------------------------------------------
    # Enemy spawning and collision resolution
    # -----------------------------------------------------------------------

    def spawn_enemy(self):
        side = random.randrange(4)

        if side == 0:
            x, y = random.randint(30, WIDTH - 30), 82
        elif side == 1:
            x, y = random.randint(30, WIDTH - 30), HEIGHT - 25
        elif side == 2:
            x, y = 25, random.randint(90, HEIGHT - 25)
        else:
            x, y = WIDTH - 25, random.randint(90, HEIGHT - 25)

        self.level.spawned += 1
        if self.level.wave % 10 == 0:
            enemy = BossEnemy(x, y, self.level.wave)
            self.set_message(f"{enemy.boss_name} - BOSS WAVE {self.level.wave}!")
        else:
            enemy = Enemy(x, y, self.level.wave)
            if self.level.spawned == self.level.checkpoint_spawn_number:
                enemy.is_checkpoint = True
        self.enemies.append(enemy)

    def spawn_boss_medkit(self):
        """Drop a temporary health pack somewhere away from the boss."""

        boss = next(
            (e for e in self.enemies if getattr(e, "is_boss", False) and e.alive),
            None
        )
        x, y = WIDTH / 2, HEIGHT / 2

        for _ in range(12):
            x = random.randint(40, WIDTH - 40)
            y = random.randint(100, HEIGHT - 40)
            far_from_boss = boss is None or distance(x, y, boss.x, boss.y) >= 140
            if far_from_boss and distance(x, y, self.player.x, self.player.y) >= 60:
                break

        kit = Medkit(x, y)
        kit.ttl = 15.0
        self.pickups.append(kit)
        self.set_message("HEALTH PACK DROPPED!")

    def resolve_enemy_collisions(self):
        enemies = [enemy for enemy in self.enemies if enemy.alive]

        # Repeat to resolve collisions in crowded groups.
        for _ in range(5):
            for i in range(len(enemies)):
                for j in range(i + 1, len(enemies)):
                    enemy1 = enemies[i]
                    enemy2 = enemies[j]

                    dx = enemy2.x - enemy1.x
                    dy = enemy2.y - enemy1.y

                    dist = math.hypot(dx, dy)
                    min_dist = enemy1.radius + enemy2.radius

                    if dist < min_dist:
                        # Handle enemies at exactly the same position.
                        if dist == 0:
                            angle = (i + j + 1) * 2.399
                            dx = math.cos(angle)
                            dy = math.sin(angle)
                            dist = 1

                        nx = dx / dist
                        ny = dy / dist
                        overlap = min_dist - dist
                        push = overlap / 2

                        enemy1.x -= nx * push
                        enemy1.y -= ny * push
                        enemy2.x += nx * push
                        enemy2.y += ny * push

        # Keep enemies inside the arena.
        for enemy in enemies:
            enemy.x = clamp(enemy.x, enemy.radius, WIDTH - enemy.radius)
            enemy.y = clamp(
                enemy.y,
                76 + enemy.radius,
                HEIGHT - enemy.radius
            )

    # -----------------------------------------------------------------------
    # Effects
    # -----------------------------------------------------------------------

    def add_burst(self, x, y, color, count=8):
        for _ in range(count):
            angle = random.random() * math.tau
            speed = random.uniform(45, 180)

            self.particles.append({
                "x": x,
                "y": y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": random.uniform(0.18, 0.42),
                "max_life": 0.42,
                "color": color,
            })

    # -----------------------------------------------------------------------
    # Game update
    # -----------------------------------------------------------------------

    def update(self, dt):
        if self.state != "playing":
            return

        player = self.player

        dx = int("d" in self.keys or "right" in self.keys) - int(
            "a" in self.keys or "left" in self.keys
        )

        dy = int("s" in self.keys or "down" in self.keys) - int(
            "w" in self.keys or "up" in self.keys
        )

        player.move(dx, dy, dt)

        if self.mouse_down:
            self.shoot()

        player.weapon.update()

        # Absolute Power: health regeneration and endless ammo.
        if player.absolute_power:
            player.health = min(
                player.max_health,
                player.health + POWER_REGEN * dt
            )
            for weapon in player.weapons:
                if weapon.reloading_until or weapon.ammo < weapon.magazine_size:
                    weapon.ammo = weapon.magazine_size
                    weapon.reloading_until = 0

        # During boss fights, supply temporary health packs to keep it fair.
        if any(getattr(e, "is_boss", False) and e.alive for e in self.enemies):
            self.boss_pickup_timer -= dt
            if self.boss_pickup_timer <= 0:
                medkits = sum(1 for i in self.pickups if isinstance(i, Medkit))
                if medkits < 3 and player.health < player.max_health:
                    self.spawn_boss_medkit()
                low_health = player.health < player.max_health * 0.5
                self.boss_pickup_timer = 7.0 if low_health else 13.0
        else:
            self.boss_pickup_timer = 4.0

        # Spawn the current wave gradually.
        if self.level.spawned < self.level.total_to_spawn:
            self.level.spawn_timer -= dt

            if self.level.spawn_timer <= 0:
                self.spawn_enemy()
                self.level.spawn_timer = max(
                    0.38,
                    1.15 - self.level.wave * 0.045
                )

        # Move player bullets and resolve direct hits / rocket splash damage.
        for bullet in self.bullets[:]:
            bullet["x"] += bullet["vx"] * dt
            bullet["y"] += bullet["vy"] * dt

            if not (
                    0 <= bullet["x"] <= WIDTH
                    and 65 <= bullet["y"] <= HEIGHT
            ):
                self.bullets.remove(bullet)
                continue

            hit_enemy = None
            for enemy in self.enemies:
                if enemy.alive and distance(
                        bullet["x"],
                        bullet["y"],
                        enemy.x,
                        enemy.y
                ) < enemy.radius + bullet["radius"]:
                    hit_enemy = enemy
                    break

            if hit_enemy:
                if bullet.get("explosive"):
                    blast_x, blast_y = bullet["x"], bullet["y"]
                    blast_radius = bullet["splash_radius"]
                    self.explosions.append({
                        "x": blast_x,
                        "y": blast_y,
                        "radius": blast_radius,
                        "life": 0.24,
                        "max_life": 0.24,
                    })
                    self.shake = max(self.shake, 0.18)
                    self.add_burst(blast_x, blast_y, bullet["color"], 24)

                    # The impact target receives full damage; nearby enemies
                    # receive distance-scaled splash damage.
                    for enemy in self.enemies:
                        if not enemy.alive:
                            continue
                        blast_distance = distance(
                            blast_x, blast_y, enemy.x, enemy.y
                        )
                        if blast_distance <= blast_radius:
                            if enemy is hit_enemy:
                                damage = bullet["damage"]
                            else:
                                falloff = 1 - blast_distance / blast_radius
                                damage = max(1, int(bullet["damage"] * falloff))
                            enemy.take_damage(damage)
                else:
                    hit_enemy.take_damage(bullet["damage"])
                    self.add_burst(
                        bullet["x"],
                        bullet["y"],
                        bullet["color"],
                        3
                    )

                self.bullets.remove(bullet)

                # Award kills and drops for every enemy eliminated by the hit.
                for enemy in self.enemies:
                    if not enemy.alive:
                        if not getattr(enemy, "_kill_awarded", False):
                            enemy._kill_awarded = True
                            player.score += 100
                            player.kills += 1
                            self.add_burst(enemy.x, enemy.y, PINK, 13)

                            if getattr(enemy, "is_boss", False):
                                self.enemy_bullets.clear()
                                self.set_message("BOSS DEFEATED! HEALTH RESTORED")
                                player.health = player.max_health
                                self.add_burst(player.x, player.y, GREEN, 30)

                            if enemy.is_checkpoint:
                                self.save_checkpoint()

                            if random.random() < 0.16:
                                kind = (
                                    Medkit
                                    if player.health < 65 and random.random() < 0.6
                                    else AmmoCrate
                                )
                                self.pickups.append(kind(enemy.x, enemy.y))

        # Mines arm after a short delay, then detonate when an enemy approaches.
        mine_power = POWER_DAMAGE_MULT if player.absolute_power else 1
        for mine in self.mines[:]:
            if not mine.armed:
                continue
            target = next((enemy for enemy in self.enemies if enemy.alive and distance(mine.x, mine.y, enemy.x, enemy.y) <= MINE_TRIGGER_RADIUS), None)
            if target is None:
                continue
            mine.exploded = True
            self.explosions.append({"x": mine.x, "y": mine.y, "radius": MINE_BLAST_RADIUS, "life": 0.32, "max_life": 0.32})
            self.shake = max(self.shake, 0.22)
            self.add_burst(mine.x, mine.y, YELLOW, 28)
            for enemy in self.enemies:
                if enemy.alive:
                    dist = distance(mine.x, mine.y, enemy.x, enemy.y)
                    if dist <= MINE_BLAST_RADIUS:
                        falloff = 1 - (dist / MINE_BLAST_RADIUS) * 0.35
                        enemy.take_damage(int(MINE_DAMAGE * falloff * mine_power))
            self.mines.remove(mine)
            self.set_message("MINE DETONATED!")

        # Award kills caused by mines as well as other damage sources.
        for enemy in self.enemies:
            if not enemy.alive and not enemy._kill_awarded:
                enemy._kill_awarded = True
                player.score += 100
                player.kills += 1
                self.add_burst(enemy.x, enemy.y, PINK, 13)
                if getattr(enemy, "is_boss", False):
                    self.enemy_bullets.clear()
                    self.set_message("BOSS DEFEATED! HEALTH RESTORED")
                    player.health = player.max_health
                    self.add_burst(player.x, player.y, GREEN, 30)
                if enemy.is_checkpoint:
                    self.save_checkpoint()
                if random.random() < 0.16:
                    kind = Medkit if player.health < 65 and random.random() < 0.6 else AmmoCrate
                    self.pickups.append(kind(enemy.x, enemy.y))

        # Regular enemies chase; bosses keep their distance and fire aimed shots.
        for enemy in self.enemies[:]:
            if not enemy.alive:
                continue
            if getattr(enemy, "is_boss", False):
                enemy.update_ai(player, dt, self.enemy_bullets, self.enemies)
                if enemy.pending_message:
                    self.set_message(enemy.pending_message)
                    enemy.pending_message = None
                    self.shake = max(self.shake, 0.15)
                if enemy.blink_flash:
                    self.add_burst(enemy.x, enemy.y, enemy.color, 18)
                    enemy.blink_flash = False
            else:
                enemy.chase(player, dt)

        # Update boss projectiles and apply damage to the player.
        for bullet in self.enemy_bullets[:]:
            bullet["x"] += bullet["vx"] * dt
            bullet["y"] += bullet["vy"] * dt
            bullet["life"] -= dt
            if (bullet["life"] <= 0 or bullet["x"] < -10 or bullet["x"] > WIDTH + 10
                    or bullet["y"] < 60 or bullet["y"] > HEIGHT + 10):
                self.enemy_bullets.remove(bullet)
                continue
            if distance(player.x, player.y, bullet["x"], bullet["y"]) < 18 + bullet["radius"]:
                player.take_damage(bullet["damage"])
                self.enemy_bullets.remove(bullet)
                self.shake = max(self.shake, 0.10)
                self.add_burst(player.x, player.y, PINK, 7)

        # Push enemies apart when they touch.
        self.resolve_enemy_collisions()

        # Check enemy-player contact damage.
        for enemy in self.enemies:
            if not enemy.alive:
                continue

            if distance(
                    player.x,
                    player.y,
                    enemy.x,
                    enemy.y
            ) < enemy.radius + 17:

                now = time.time()

                if now - enemy.attack_cooldown > 0.75:
                    player.take_damage(enemy.damage)
                    enemy.attack_cooldown = now
                    self.shake = 0.12
                    self.add_burst(player.x, player.y, PINK, 5)

        self.enemies = [
            enemy for enemy in self.enemies if enemy.alive
        ]

        # Pickups.
        for item in self.pickups[:]:
            if item.ttl is not None:
                item.ttl -= dt
                if item.ttl <= 0:
                    item.active = False
            if (
                    item.active
                    and distance(
                player.x,
                player.y,
                item.x,
                item.y
            ) < 27
            ):
                amount = item.pick_up(player)

                if isinstance(item, Medkit):
                    self.set_message(f"+{amount} HEALTH")
                else:
                    self.set_message("AMMO RESTORED")

                self.add_burst(item.x, item.y, item.color, 9)

            if not item.active:
                self.pickups.remove(item)

        # Brief visual rings for rocket explosions.
        for explosion in self.explosions[:]:
            explosion["life"] -= dt
            if explosion["life"] <= 0:
                self.explosions.remove(explosion)

        # Particles.
        for particle in self.particles[:]:
            particle["x"] += particle["vx"] * dt
            particle["y"] += particle["vy"] * dt
            particle["life"] -= dt

            if particle["life"] <= 0:
                self.particles.remove(particle)

        # Game over: save the score once.
        if player.health <= 0:
            self.state = "gameover"
            self.save_score()

        # Start the next wave after all enemies and pickups are cleared.
        if (
                self.level.complete
                and not self.enemies
                and not self.pickups
                and self.level.spawned > 0
        ):
            self.level.begin_next_wave()
            unlocked_name = player.unlock_weapons_for_wave(self.level.wave)
            if unlocked_name and self.level.wave == MINE_UNLOCK_WAVE:
                self.set_message(
                    f"NEW WEAPON: {unlocked_name}  |  MINES UNLOCKED (E)"
                )
            elif unlocked_name:
                self.set_message(f"NEW WEAPON UNLOCKED: {unlocked_name}")
            elif self.level.wave == MINE_UNLOCK_WAVE:
                self.set_message("MINES UNLOCKED! PRESS E TO DEPLOY")

            # Wave 100 conquered: grant absolute power for all later waves.
            if (
                    self.level.wave >= ABSOLUTE_POWER_WAVE
                    and not player.absolute_power
            ):
                self.activate_absolute_power()

        self.shake = max(0, self.shake - dt)

    # -----------------------------------------------------------------------
    # Drawing
    # -----------------------------------------------------------------------

    def draw_background(self):
        self.canvas.create_rectangle(
            0, 0, WIDTH, HEIGHT,
            fill=BG,
            outline=""
        )

        for x in range(0, WIDTH, 40):
            self.canvas.create_line(x, 64, x, HEIGHT, fill=GRID)

        for y in range(80, HEIGHT, 40):
            self.canvas.create_line(0, y, WIDTH, y, fill=GRID)

        # Subtle corner decorations.
        self.canvas.create_oval(
            -100, -180, 260, 180,
            outline="#172744",
            width=2
        )

        self.canvas.create_oval(
            WIDTH - 230,
            HEIGHT - 160,
            WIDTH + 100,
            HEIGHT + 170,
            outline="#172744",
            width=2
        )

    def draw_hud(self):
        c = self.canvas

        c.create_rectangle(
            0, 0, WIDTH, 64,
            fill="#10182b",
            outline=""
        )

        c.create_text(
            22, 19,
            text="ARENA",
            fill=CYAN,
            anchor="w",
            font=("Segoe UI", 17, "bold")
        )

        c.create_text(
            22, 43,
            text="OPS  /  SURVIVAL PROTOCOL",
            fill=MUTED,
            anchor="w",
            font=("Segoe UI", 7, "bold")
        )

        c.create_text(
            250, 18,
            text=(f"BOSS WAVE  {self.level.wave:02}" if self.level.wave % 10 == 0
                  else f"WAVE  {self.level.wave:02}"),
            fill=GOLD if self.level.wave % 10 == 0 else WHITE,
            font=("Segoe UI", 10, "bold")
        )

        c.create_text(
            250, 42,
            text=f"ELIMINATIONS  {self.player.kills}",
            fill=MUTED,
            font=("Segoe UI", 8, "bold")
        )

        c.create_text(
            405, 18,
            text="VITALS",
            fill=MUTED,
            anchor="w",
            font=("Segoe UI", 8, "bold")
        )

        c.create_rectangle(
            405, 29, 585, 43,
            fill="#26314a",
            outline=""
        )

        health_width = 180 * self.player.health / self.player.max_health

        health_color = (
            GREEN if self.player.health > 55
            else GOLD if self.player.health > 25
            else PINK
        )

        c.create_rectangle(
            405, 29, 405 + health_width, 43,
            fill=health_color,
            outline=""
        )

        c.create_text(
            590, 36,
            text=f"{int(self.player.health)}",
            fill=WHITE,
            anchor="w",
            font=("Segoe UI", 9, "bold")
        )

        if self.player.absolute_power:
            c.create_text(
                625, 18,
                text="ABSOLUTE POWER",
                fill=GOLD,
                anchor="w",
                font=("Segoe UI", 8, "bold")
            )

        weapon = self.player.weapon

        c.create_text(
            WIDTH - 22, 17,
            text=weapon.name,
            fill=weapon.bullet_color,
            anchor="e",
            font=("Segoe UI", 9, "bold")
        )

        if self.player.absolute_power:
            ammo_text = "INFINITE"
        else:
            ammo_text = (
                "RELOADING"
                if weapon.is_reloading
                else f"{weapon.ammo:02} / {weapon.magazine_size:02}"
            )

        mine_hint = "E  MINE" if self.level.wave >= MINE_UNLOCK_WAVE else f"E  MINE ({MINE_UNLOCK_WAVE})"
        c.create_text(
            690, 42, text=mine_hint, fill=YELLOW, anchor="w", font=("Segoe UI", 8, "bold")
        )

        c.create_text(
            WIDTH - 22, 41,
            text=ammo_text,
            fill=WHITE,
            anchor="e",
            font=("Segoe UI", 12, "bold")
        )

    def draw_leaderboard(self, x, y, title="ALL-TIME LEADERBOARD"):
        """Draw the top five players on the Tkinter canvas."""

        c = self.canvas
        leaderboard = build_leaderboard(self.records)

        panel_width = 235
        panel_height = 215

        c.create_rectangle(
            x, y,
            x + panel_width, y + panel_height,
            fill="#10182b",
            outline="#285e69",
            width=2
        )

        c.create_text(
            x + 14, y + 18,
            text=title,
            fill=CYAN,
            anchor="w",
            font=("Segoe UI", 10, "bold")
        )

        c.create_line(
            x + 12, y + 38,
            x + panel_width - 12, y + 38,
            fill="#285e69"
        )

        if not leaderboard:
            c.create_text(
                x + panel_width / 2,
                y + 95,
                text="NO RECORDS YET",
                fill=MUTED,
                font=("Segoe UI", 10, "bold")
            )

            c.create_text(
                x + panel_width / 2,
                y + 120,
                text="Be the first champion!",
                fill=WHITE,
                font=("Segoe UI", 8)
            )
            return

        c.create_text(
            x + 18, y + 55,
            text="RANK",
            fill=MUTED,
            anchor="w",
            font=("Segoe UI", 7, "bold")
        )

        c.create_text(
            x + 65, y + 55,
            text="PLAYER",
            fill=MUTED,
            anchor="w",
            font=("Segoe UI", 7, "bold")
        )

        c.create_text(
            x + panel_width - 15, y + 55,
            text="SCORE",
            fill=MUTED,
            anchor="e",
            font=("Segoe UI", 7, "bold")
        )

        for position, (name, score) in enumerate(
                leaderboard[:5],
                start=1
        ):
            row_y = y + 82 + (position - 1) * 25

            if position == 1:
                color = GOLD
            elif position == 2:
                color = WHITE
            elif position == 3:
                color = "#cd8c65"
            else:
                color = MUTED

            c.create_text(
                x + 20, row_y,
                text=f"#{position}",
                fill=color,
                anchor="w",
                font=("Segoe UI", 9, "bold")
            )

            c.create_text(
                x + 65, row_y,
                text=name,
                fill=WHITE,
                anchor="w",
                font=("Segoe UI", 9)
            )

            c.create_text(
                x + panel_width - 15, row_y,
                text=f"{score:,}",
                fill=CYAN,
                anchor="e",
                font=("Segoe UI", 9, "bold")
            )

    def draw_warden(self, enemy):
        """Armored knight design for the WARDEN boss."""

        c = self.canvas
        t = time.time()
        x, y, r = enemy.x, enemy.y, enemy.radius
        spin = t * (0.9 + 0.5 * (enemy.phase - 1))
        aim = math.atan2(self.player.y - y, self.player.x - x)

        # Orbiting armor plates.
        for k in range(8):
            a = spin + math.tau * k / 8
            cx = x + math.cos(a) * (r + 7)
            cy = y + math.sin(a) * (r + 7)
            tx, ty = -math.sin(a), math.cos(a)
            nx, ny = math.cos(a), math.sin(a)
            pts = []
            for st, sn in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                pts += [
                    cx + tx * 9 * st + nx * 3.5 * sn,
                    cy + ty * 9 * st + ny * 3.5 * sn,
                ]
            c.create_polygon(pts, fill=enemy.color, outline="#fff3c4", width=1)

        # Octagonal armored body.
        pts = []
        for k in range(8):
            a = math.pi / 8 + math.tau * k / 8
            pts += [x + math.cos(a) * r, y + math.sin(a) * r]
        c.create_polygon(pts, fill=enemy.body_fill, outline=enemy.color, width=3)

        # Rotating inner hexagon.
        pts = []
        for k in range(6):
            a = -spin * 1.5 + math.tau * k / 6
            pts += [x + math.cos(a) * r * 0.55, y + math.sin(a) * r * 0.55]
        c.create_polygon(pts, fill="", outline=enemy.color, width=2)

        # Glowing visor that tracks the player (turns red when enraged).
        eye_color = PINK if enemy.phase == 1 else "#ff3b30"
        ex = x + math.cos(aim) * r * 0.32
        ey = y + math.sin(aim) * r * 0.32
        c.create_oval(ex - 8, ey - 8, ex + 8, ey + 8, fill=eye_color, outline=WHITE, width=2)
        c.create_oval(ex - 3, ey - 3, ex + 3, ey + 3, fill=WHITE, outline="")

    def draw_player(self):
        c = self.canvas
        p = self.player

        angle = math.atan2(
            self.mouse_y - p.y,
            self.mouse_x - p.x
        )

        c.create_oval(
            p.x - 18, p.y - 18,
            p.x + 18, p.y + 18,
            fill="#183f50",
            outline=CYAN,
            width=2
        )

        c.create_oval(
            p.x - 7, p.y - 7,
            p.x + 7, p.y + 7,
            fill=CYAN,
            outline=""
        )

        c.create_line(
            p.x, p.y,
            p.x + math.cos(angle) * 28,
            p.y + math.sin(angle) * 28,
            fill=WHITE,
            width=5,
            capstyle=tk.ROUND
        )

        c.create_oval(
            p.x - 25, p.y - 25,
            p.x + 25, p.y + 25,
            outline="#285e69",
            width=1
        )

        # Golden aura while Absolute Power is active.
        if p.absolute_power:
            c.create_oval(
                p.x - 32, p.y - 32,
                p.x + 32, p.y + 32,
                outline=GOLD,
                width=2
            )

    def draw_overlay(self):
        self.canvas.create_rectangle(
            0, 0, WIDTH, HEIGHT,
            fill="#070b16",
            stipple="gray50",
            outline=""
        )

    def draw(self):
        c = self.canvas
        c.delete("all")
        self.draw_background()

        if self.state in ("playing", "paused", "gameover"):
            self.draw_hud()

            for item in self.pickups:
                # Expiring packs blink during their last seconds.
                if item.ttl is not None and item.ttl < 4 and int(item.ttl * 6) % 2 == 0:
                    continue
                color = item.color

                c.create_oval(
                    item.x - 10,
                    item.y - 10,
                    item.x + 10,
                    item.y + 10,
                    fill="#182c32",
                    outline=color,
                    width=2
                )

                symbol = "+" if isinstance(item, Medkit) else "A"

                c.create_text(
                    item.x, item.y,
                    text=symbol,
                    fill=color,
                    font=("Segoe UI", 10, "bold")
                )

            for mine in self.mines:
                armed = mine.armed
                pulse = 0.5 + 0.5 * math.sin(time.time() * (10 if armed else 4))
                color = PINK if armed else MUTED

                # Pulsing danger ring once the mine is armed.
                if armed:
                    ring = 20 + 5 * pulse
                    c.create_oval(
                        mine.x - ring, mine.y - ring,
                        mine.x + ring, mine.y + ring,
                        outline="#7a2e4d", width=1, dash=(2, 4)
                    )

                # Spiked naval-mine body.
                for k in range(8):
                    a = math.pi / 8 + math.tau * k / 8
                    x1 = mine.x + math.cos(a) * 9
                    y1 = mine.y + math.sin(a) * 9
                    x2 = mine.x + math.cos(a) * 15
                    y2 = mine.y + math.sin(a) * 15
                    c.create_line(x1, y1, x2, y2, fill=color, width=3)
                    c.create_oval(x2 - 2, y2 - 2, x2 + 2, y2 + 2, fill=color, outline="")

                c.create_oval(
                    mine.x - 10, mine.y - 10, mine.x + 10, mine.y + 10,
                    fill="#2a2f3d", outline=color, width=2
                )

                # Blinking core light.
                core = 2 + 3 * pulse if armed else 3
                c.create_oval(
                    mine.x - core, mine.y - core, mine.x + core, mine.y + core,
                    fill=color if armed else "#4a5368", outline=""
                )

            for bullet in self.bullets:
                r = bullet["radius"]

                c.create_oval(
                    bullet["x"] - r,
                    bullet["y"] - r,
                    bullet["x"] + r,
                    bullet["y"] + r,
                    fill=bullet["color"],
                    outline=""
                )

            for explosion in self.explosions:
                progress = 1 - explosion["life"] / explosion["max_life"]
                ring_radius = explosion["radius"] * progress
                c.create_oval(
                    explosion["x"] - ring_radius,
                    explosion["y"] - ring_radius,
                    explosion["x"] + ring_radius,
                    explosion["y"] + ring_radius,
                    outline="#ff9b45",
                    width=max(1, int(5 * (1 - progress))),
                )

            for bullet in self.enemy_bullets:
                r = bullet["radius"]
                c.create_oval(
                    bullet["x"] - r, bullet["y"] - r,
                    bullet["x"] + r, bullet["y"] + r,
                    fill=bullet.get("color", "#ff9b45"), outline="#ffe0a3", width=2
                )

            for enemy in self.enemies:
                r = enemy.radius

                if getattr(enemy, "is_boss", False):
                    c.create_oval(
                        enemy.x-r-11, enemy.y-r-11,
                        enemy.x+r+11, enemy.y+r+11,
                        outline=enemy.color, width=3
                    )
                    c.create_text(
                        enemy.x, enemy.y-r-29,
                        text=enemy.boss_name, fill=enemy.color,
                        font=("Segoe UI", 10, "bold")
                    )
                    # Large boss health bar.
                    bar_width = 110
                    c.create_rectangle(
                        enemy.x-bar_width/2, enemy.y-r-17,
                        enemy.x+bar_width/2, enemy.y-r-10,
                        fill="#39263b", outline=enemy.color
                    )
                    c.create_rectangle(
                        enemy.x-bar_width/2, enemy.y-r-17,
                        enemy.x-bar_width/2 + bar_width * enemy.health / enemy.max_health,
                        enemy.y-r-10, fill="#ff5d8f", outline=""
                    )
                elif enemy.is_checkpoint:
                    c.create_oval(enemy.x-r-9, enemy.y-r-9, enemy.x+r+9, enemy.y+r+9, outline=GOLD, width=3)
                    c.create_text(enemy.x, enemy.y-r-20, text="CHECKPOINT", fill=GOLD, font=("Segoe UI", 8, "bold"))

                if getattr(enemy, "is_boss", False) and enemy.cfg["name"] == "WARDEN":
                    self.draw_warden(enemy)
                else:
                    c.create_oval(
                        enemy.x - r,
                        enemy.y - r,
                        enemy.x + r,
                        enemy.y + r,
                        fill=enemy.body_fill if getattr(enemy, "is_boss", False) else "#48243c",
                        outline=enemy.color if getattr(enemy, "is_boss", False) else PINK,
                        width=3 if getattr(enemy, "is_boss", False) else 2
                    )

                    c.create_oval(
                        enemy.x - 5,
                        enemy.y - 5,
                        enemy.x + 5,
                        enemy.y + 5,
                        fill=PINK,
                        outline=""
                    )

                # Tiny health strip.
                c.create_rectangle(
                    enemy.x - 17,
                    enemy.y - r - 8,
                    enemy.x + 17,
                    enemy.y - r - 4,
                    fill="#39263b",
                    outline=""
                )

                c.create_rectangle(
                    enemy.x - 17,
                    enemy.y - r - 8,
                    enemy.x - 17 + 34 * enemy.health / enemy.max_health,
                    enemy.y - r - 4,
                    fill=PINK,
                    outline=""
                )

            self.draw_player()

            for particle in self.particles:
                r = max(
                    1,
                    3 * particle["life"] / particle["max_life"]
                )

                c.create_oval(
                    particle["x"] - r,
                    particle["y"] - r,
                    particle["x"] + r,
                    particle["y"] + r,
                    fill=particle["color"],
                    outline=""
                )

            if time.time() < self.message_until:
                c.create_text(
                    WIDTH / 2, 91,
                    text=self.message,
                    fill=GOLD,
                    font=("Segoe UI", 10, "bold")
                )

            if (
                    time.time() < self.level.banner_until
                    and self.state == "playing"
            ):
                c.create_text(
                    WIDTH / 2,
                    HEIGHT / 2 - 100,
                    text=f"WAVE {self.level.wave}",
                    fill=WHITE,
                    font=("Segoe UI", 27, "bold")
                )

                c.create_text(
                    WIDTH / 2,
                    HEIGHT / 2 - 70,
                    text="HOSTILES INBOUND",
                    fill=CYAN,
                    font=("Segoe UI", 9, "bold")
                )

        # Main menu.
        if self.state == "menu":
            self.draw_overlay()

            c.create_text(
                WIDTH / 2.8, 190,
                text="paintball",
                fill=WHITE,
                font=("Segoe UI", 42, "bold")
            )

            c.create_text(
                WIDTH / 2.8, 235,
                text="A PYTHON OOP SURVIVAL GAME",
                fill=CYAN,
                font=("Segoe UI", 11, "bold")
            )

            # Keep menu instructions clear of the leaderboard panel.
            c.create_text(
                350, 320,
                text="SURVIVE THE WAVES. COLLECT SUPPLIES. KEEP MOVING.",
                fill=MUTED,
                font=("Segoe UI", 9)
            )

            c.create_text(
                350, 390,
                text="WASD / ARROWS  MOVE     •     MOUSE  AIM",
                fill=WHITE,
                font=("Segoe UI", 10, "bold")
            )

            c.create_text(
                350, 420,
                text="CLICK / SPACE  FIRE     •     R  RELOAD     •     Q  SWITCH WEAPON",
                fill=WHITE,
                font=("Segoe UI", 8, "bold")
            )

            c.create_text(
                350, 500,
                text="PRESS ENTER TO DEPLOY",
                fill=GOLD,
                font=("Segoe UI", 14, "bold")
            )

            self.records = load_records()
            self.draw_leaderboard(
                700,
                20,
                "TOP OPERATORS"
            )

        # Pause screen.
        elif self.state == "paused":
            self.draw_overlay()

            c.create_text(
                WIDTH / 2,
                HEIGHT / 2 - 15,
                text="PAUSED",
                fill=WHITE,
                font=("Segoe UI", 34, "bold")
            )

            c.create_text(
                WIDTH / 2,
                HEIGHT / 2 + 30,
                text="PRESS P OR ESC TO CONTINUE",
                fill=CYAN,
                font=("Segoe UI", 10, "bold")
            )

        # Game-over screen.
        elif self.state == "gameover":
            self.draw_overlay()

            c.create_text(
                350, 225,
                text="MISSION FAILED",
                fill=PINK,
                font=("Segoe UI", 34, "bold")
            )

            c.create_text(
                350, 300,
                text=f"SCORE  {self.player.score:,}",
                fill=WHITE,
                font=("Segoe UI", 20, "bold")
            )

            c.create_text(
                350, 340,
                text=(
                    f"WAVE REACHED  {self.level.wave}"
                    f"     •     ELIMINATIONS  {self.player.kills}"
                ),
                fill=MUTED,
                font=("Segoe UI", 9, "bold")
            )

            c.create_text(
                350, 430,
                text="PRESS ENTER TO TRY AGAIN",
                fill=GOLD,
                font=("Segoe UI", 12, "bold")
            )

            self.records = load_records()
            self.draw_leaderboard(
                700,
                390,
                "TOP OPERATORS"
            )

        # Custom aiming reticle.
        if self.state == "playing":
            x, y = self.mouse_x, self.mouse_y

            c.create_oval(
                x - 8, y - 8,
                x + 8, y + 8,
                outline=CYAN,
                width=1
            )

            c.create_line(
                x - 13, y, x - 4, y,
                fill=CYAN
            )

            c.create_line(
                x + 4, y, x + 13, y,
                fill=CYAN
            )

            c.create_line(
                x, y - 13, x, y - 4,
                fill=CYAN
            )

            c.create_line(
                x, y + 4, x, y + 13,
                fill=CYAN
            )

    # -----------------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------------

    def loop(self):
        now = time.perf_counter()
        dt = min(now - self.last_time, 0.035)
        self.last_time = now

        self.update(dt)
        self.draw()

        if self.root.winfo_exists():
            self.root.after(16, self.loop)


if __name__ == "__main__":
    window = tk.Tk()
    game = ArenaGame(window)
    window.mainloop()
