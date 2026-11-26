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

# Leaderboard settings
RECORDS_FILE = "paintball-records.json"
MAX_PLAYER_NAME_LENGTH = 12
MAX_LEADERBOARD_ENTRIES = 10


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
            magazine_size=24,
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
        self.speed = 245
        self.weapon = AutomaticGun()
        self.weapons = [self.weapon, Shotgun(), RPG()]
        self.weapon_index = 0
        self.score = 0
        self.kills = 0

    def move(self, dx, dy, dt):
        length = math.hypot(dx, dy)

        if length:
            dx, dy = dx / length, dy / length
            self.x += dx * self.speed * dt
            self.y += dy * self.speed * dt

        self.x = clamp(self.x, 24, WIDTH - 24)
        self.y = clamp(self.y, 76, HEIGHT - 24)

    def switch_weapon(self):
        self.weapon_index = (self.weapon_index + 1) % len(self.weapons)
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

    def chase(self, player, dt):
        angle = math.atan2(player.y - self.y, player.x - self.x)
        self.x += math.cos(angle) * self.speed * dt
        self.y += math.sin(angle) * self.speed * dt


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

class Equipment:
    color = WHITE

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.active = True

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
    def __init__(self):
        self.wave = 1
        self.spawned = 0
        self.total_to_spawn = 5
        self.spawn_timer = 0
        self.banner_until = time.time() + 2.2

    @property
    def complete(self):
        return self.spawned >= self.total_to_spawn

    def begin_next_wave(self):
        self.wave += 1
        self.spawned = 0
        self.total_to_spawn = 5 + self.wave * 2
        self.spawn_timer = 0
        self.banner_until = time.time() + 2.0


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

        self.last_time = time.perf_counter()
        self.message = ""
        self.message_until = 0
        self.shake = 0

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

    def close_game(self):
        """Save an unfinished run before closing the application."""

        if self.state in ("playing", "paused"):
            self.save_score()

        self.root.destroy()

    # -----------------------------------------------------------------------
    # Game controls
    # -----------------------------------------------------------------------

    def start_game(self, _event=None):
        if self.state not in ("menu", "gameover"):
            return

        player_name = self.enter_player_name()

        if player_name is None:
            return

        self.player_name = player_name

        self.player = Player()
        self.level = Level()

        self.enemies.clear()
        self.bullets.clear()
        self.explosions.clear()
        self.enemy_bullets.clear()
        self.pickups.clear()
        self.particles.clear()

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

    def shoot(self):
        player = self.player

        shots = player.weapon.attack(
            player.x,
            player.y,
            self.mouse_x,
            self.mouse_y
        )

        if shots:
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

        self.enemies.append(Enemy(x, y, self.level.wave))
        self.level.spawned += 1

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

                            if random.random() < 0.16:
                                kind = (
                                    Medkit
                                    if player.health < 65 and random.random() < 0.6
                                    else AmmoCrate
                                )
                                self.pickups.append(kind(enemy.x, enemy.y))

        # Enemies pursue the player.
        for enemy in self.enemies:
            if enemy.alive:
                enemy.chase(player, dt)

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
            text=f"WAVE  {self.level.wave:02}",
            fill=WHITE,
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

        weapon = self.player.weapon

        c.create_text(
            WIDTH - 22, 17,
            text=weapon.name,
            fill=weapon.bullet_color,
            anchor="e",
            font=("Segoe UI", 9, "bold")
        )

        ammo_text = (
            "RELOADING"
            if weapon.is_reloading
            else f"{weapon.ammo:02} / {weapon.magazine_size:02}"
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

            for enemy in self.enemies:
                r = enemy.radius

                c.create_oval(
                    enemy.x - r,
                    enemy.y - r,
                    enemy.x + r,
                    enemy.y + r,
                    fill="#48243c",
                    outline=PINK,
                    width=2
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
