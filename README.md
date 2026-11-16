# 🎯 paintball – Python Survival Shooter

**paintball** is a top-down survival shooter built with Python and Tkinter, featuring object-oriented game architecture, enemy AI, multiple weapons, progressive enemy waves, collision detection, and real-time visual effects.

Survive increasingly difficult waves of enemies, manage your ammunition, collect supplies, and see how long you can stay alive.

## ✨ Features

- **Wave-Based Survival:** Face progressively larger waves of enemies.
- **Enemy AI:** Enemies actively pursue the player across the arena.
- **Enemy Collision Resolution:** Enemies detect overlaps and push each other apart instead of stacking on top of one another.
- **Multiple Weapons:** Switch between an automatic rifle and a shotgun, each with different firing characteristics.
- **Ammunition Management:** Reload weapons and manage limited magazine capacity.
- **Health System:** Take damage from enemy contact and monitor your remaining health.
- **Collectible Equipment:** Pick up medkits and ammunition crates dropped by defeated enemies.
- **Dynamic Difficulty:** Enemy health, movement speed, and wave size increase as the game progresses.
- **Visual Effects:** Particle bursts, aiming reticle, health indicators, and animated game feedback.
- **Game States:** Main menu, active gameplay, pause screen, and game-over screen.

## 🕹️ Controls

| Key / Input | Action |
|---|---|
| W / A / S / D | Move |
| Arrow Keys | Move |
| Mouse Movement | Aim |
| Left Mouse Button | Shoot |
| Space | Shoot |
| Q | Switch Weapon |
| R | Reload |
| P | Pause / Resume |
| Esc | Pause / Resume |
| Enter | Start / Restart |
 
## 🔫 Weapons

The game currently features two weapons with different damage, magazine capacity, firing rates, and reload times.

### 1. Pulse Rifle

<details>
<summary>Weapon specifications</summary>

- Damage: 25 per bullet
- Magazine: 24 rounds
- Fire delay: 0.14 seconds
- Reload time: 1.15 seconds
- Bullet speed: 650

</details>

### 2. Nova Shotgun

<details>
<summary>Weapon specifications</summary>

- Damage: 17 per pellet
- Magazine: 7 rounds
- Fire delay: 0.58 seconds
- Reload time: 1.45 seconds
- Bullet speed: 520
- Fires 5 pellets per shot with a spread pattern.

</details>

## 👾 Enemy System

Enemies spawn from the four edges of the arena and continuously pursue the player.

Their characteristics scale with the current wave:

- **Health:** Increases with each wave.
- **Movement Speed:** Randomized for each enemy, with additional scaling as waves progress.
- **Contact Damage:** Enemies deal 13 damage when they reach the player.
- **Attack Cooldown:** Each enemy has an independent 0.75-second contact damage cooldown.

### Enemy Collision System

A collision-resolution algorithm prevents enemies from overlapping.

When two enemies collide:
1. Their distance is calculated.
2. The overlap between their collision circles is determined.
3. Both enemies are pushed away from each other.
4. Multiple resolution passes help handle crowded groups.

This creates more natural enemy movement and prevents enemies from occupying the same space.

## ❤️ Health & Equipment

Enemies have a 16% chance of dropping equipment when defeated.

Two types of equipment are available:

| Equipment | Effect |
|---|---|
| Medkit | Restores up to 30 health |
| Ammo Crate | Refills all weapons |

Medkits are particularly useful when health is low, while ammunition crates restore the magazines of both weapons.

## 🌊 Wave Progression

The game starts with 5 enemies in Wave 1.

Each subsequent wave increases the number of enemies:

- Wave 1: 5 enemies
- Wave 2: 9 enemies
- Wave 3: 11 enemies
- Wave 4: 13 enemies
- And so on.

Enemies also become stronger as the waves progress, making survival increasingly challenging.

## 🛠️ Technologies Used

- **Python** – Core programming language and game logic.
- **Tkinter** – Game window, canvas rendering, and input handling.
- **Math** – Distance calculations, vector movement, angles, and collision detection.
- **Random** – Enemy generation, weapon-independent randomization, and equipment drops.
- **Time** – Game timing, firing intervals, reloads, and cooldowns.

## 🧠 Programming Concepts

This project demonstrates several important programming concepts:

- Object-Oriented Programming (OOP)
- Inheritance and method overriding
- Encapsulation and properties
- Game loops and frame-based updates
- Delta time for frame-rate-independent movement
- Vector mathematics and trigonometry
- Circle-based collision detection
- Collision resolution and separation algorithms
- State management
- Event-driven programming
- Particle systems
- Randomized enemy behavior and procedural spawning

## 🏗️ Architecture

The project is organized around several classes, each responsible for a specific part of the game.

| Class | Responsibility |
|---|---|
| `Weapon` | Base weapon functionality, firing, and reloading |
| `AutomaticGun` | Pulse Rifle implementation |
| `Shotgun` | Multi-pellet shooting mechanics |
| `Character` | Shared character attributes and health management |
| `Player` | Player movement, weapons, score, and eliminations |
| `Enemy` | Enemy health, movement, and pursuit behavior |
| `Equipment` | Base class for collectible items |
| `Medkit` | Health restoration |
| `AmmoCrate` | Ammunition restoration |
| `Level` | Wave progression and enemy spawning |
| `ArenaGame` | Main game loop, event handling, game logic, and rendering |

## ⚙️ Installation & Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd paintball
```

### 2. Run the game

Tkinter is included with most standard Python installations.

```bash
python main.py
```

No external Python packages are required by the current implementation.

## 🎮 Gameplay Objective

Your objective is simple:

**Survive as many waves as possible.**

Eliminate enemies, collect supplies, manage your weapons, and avoid getting surrounded.

Your mission ends when your health reaches zero.

---

**Built with Python 🐍**

*paintball — SURVIVE THE WAVES. KEEP MOVING.*

## 🤝 Contributing

Contributions are welcome!

If you would like to improve this project:

1. Fork the repository.
2. Create a new branch for your changes.
3. Make your changes and test them.
4. Commit your changes with a clear message.
5. Push your branch to your fork.
6. Open a Pull Request describing your improvements.

Please keep your changes clear, focused, and consistent with the existing code style.
