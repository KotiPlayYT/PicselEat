import pyglet
from pyglet.window import key
import json
import os
import math
import random
from datetime import datetime

# ========== НАСТРОЙКИ ==========
WINDOW_WIDTH = 2020
WINDOW_HEIGHT = 1180
SAVE_FILE = "savegame.json"
ENEMY_COUNT = 50
WALL_COUNT = 15

window = pyglet.window.Window(WINDOW_WIDTH, WINDOW_HEIGHT, "GAME FOR YOU")
batch = pyglet.graphics.Batch()
ui_batch = pyglet.graphics.Batch()

# ========== МУЗЫКА ==========
boss_music = None
music_player = None
music_playing = False


def load_music():
    global boss_music
    try:
        boss_music = pyglet.media.load("./resources/amam.mp3", streaming=True)
        return True
    except:
        print("Файл amam.mp3 не найден!")
        return False


def play_boss_music():
    global music_player, music_playing
    if boss_music and not music_playing:
        music_player = pyglet.media.Player()
        music_player.queue(boss_music)
        music_player.loop = True
        music_player.play()
        music_playing = True


def stop_boss_music():
    global music_player, music_playing
    if music_player:
        music_player.pause()
        music_player.delete()
        music_player = None
    music_playing = False


# ========== ФУНКЦИЯ ЦЕНТРИРОВАНИЯ ОКНА ==========
def center_window():
    try:
        display = pyglet.canvas.get_display()
        screen = display.get_default_screen()
        screen_width = screen.width
        screen_height = screen.height
        win_width, win_height = window.get_size()
        if win_width > screen_width:
            win_width = int(screen_width * 0.9)
        if win_height > screen_height:
            win_height = int(screen_height * 0.9)
        if win_width != window.get_size()[0] or win_height != window.get_size()[1]:
            window.set_size(win_width, win_height)
        x = (screen_width - win_width) // 2
        y = (screen_height - win_height) // 2
        if x < 0:
            x = 0
        if y < 0:
            y = 0
        window.set_location(x, y)
    except:
        window.set_location(100, 100)


# ========== СОСТОЯНИЯ ИГРЫ ==========
class GameState:
    MENU = 0
    PLAYING = 1
    PAUSED = 2
    GAME_OVER = 3
    VICTORY = 4
    SHOP = 5
    TROLL = 6


current_state = GameState.MENU
current_level = 1
max_level = 5

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ДРОЖАНИЯ ==========
shake_timer = 0
shake_intensity = 15


def trigger_shake(duration=3.0, intensity=15):
    global shake_timer, shake_intensity
    shake_timer = duration
    shake_intensity = intensity


# ========== ТРОЛЛЬ-ЭКРАН ==========
troll_image = None
troll_sprite = None


def load_troll_image():
    global troll_image, troll_sprite
    try:
        troll_image = pyglet.image.load("./resources/troll.png")
        troll_sprite = pyglet.sprite.Sprite(troll_image,
                                            x=WINDOW_WIDTH // 2 - 200,
                                            y=WINDOW_HEIGHT // 2 - 200)
        return True
    except:
        print("Файл troll.png не найден!")
        return False


def show_troll_screen():
    global current_state
    current_state = GameState.TROLL
    stop_boss_music()


# ========== КЛАСС ПУЛИ ==========
class Bullet:
    def __init__(self, x, y, target_x, target_y, damage=20, speed=300, owner="player"):
        self.x = x
        self.y = y
        self.damage = damage
        self.speed = speed
        self.owner = owner
        self.lifetime = 3.0
        self.active = True

        dx = target_x - x
        dy = target_y - y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0:
            self.vx = (dx / dist) * speed
            self.vy = (dy / dist) * speed
        else:
            self.vx = random.uniform(-1, 1) * speed
            self.vy = random.uniform(-1, 1) * speed

        color = (0, 255, 255, 255) if owner == "player" else (255, 255, 0, 255)
        img = create_rect(color, 8, 8)
        self.sprite = pyglet.sprite.Sprite(img, x, y, batch=batch)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.sprite.x = self.x
        self.sprite.y = self.y
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.active = False
            self.sprite.visible = False

    def check_hit(self, boss):
        if not self.active or not boss:
            return False
        dist = math.sqrt((self.x - boss.x) ** 2 + (self.y - boss.y) ** 2)
        if dist < 40:
            boss.take_damage(self.damage)
            self.active = False
            self.sprite.visible = False
            return True
        return False

    def check_hit_mini(self, mini_enemies):
        if not self.active or not mini_enemies:
            return False
        for mini in mini_enemies[:]:
            dist = math.sqrt((self.x - mini.x) ** 2 + (self.y - mini.y) ** 2)
            if dist < 25:
                if mini.take_damage(self.damage):
                    mini_enemies.remove(mini)
                    mini.sprite.visible = False
                self.active = False
                self.sprite.visible = False
                return True
        return False


# ========== МАГАЗИН ==========
class Shop:
    def __init__(self):
        self.items = {
            "health_potion": {"name": "Зелье здоровья", "cost": 50, "effect": "heal", "value": 30},
            "damage_up": {"name": "Улучшение урона", "cost": 100, "effect": "damage", "value": 10},
            "max_health": {"name": "Увеличение HP", "cost": 150, "effect": "max_health", "value": 25},
        }
        self.selected = 0

    def buy(self, item_id, player):
        if item_id in self.items:
            item = self.items[item_id]
            if player.score >= item["cost"]:
                player.score -= item["cost"]

                if item["effect"] == "heal":
                    player.health = min(player.max_health, player.health + item["value"])
                    player.message = f"Куплено: {item['name']}! +{item['value']} HP!"

                elif item["effect"] == "damage":
                    player.damage_bonus += item["value"]
                    player.message = f"Куплено: {item['name']}! Урон +{item['value']}!"

                elif item["effect"] == "max_health":
                    player.max_health += item["value"]
                    player.health = player.max_health
                    player.message = f"Макс. HP +{item['value']}!"

                player.message_time = 2
                return True
            else:
                player.message = f"Не хватает очков! Нужно: {item['cost']}"
                player.message_time = 1.5
                return False
        return False


shop = Shop()


# ========== ДОСТИЖЕНИЯ ==========
class Achievements:
    def __init__(self):
        self.achievements = {
            "first_kill": {"name": "ПЕРВАЯ КРОВЬ", "completed": False, "progress": 0, "target": 1},
            "killer_10": {"name": "НАЧИНАЮЩИЙ УБИЙЦА", "completed": False, "progress": 0, "target": 10},
            "killer_50": {"name": "МАССОВЫЙ УБИЙЦА", "completed": False, "progress": 0, "target": 50},
            "killer_100": {"name": "ВЛАСТЕЛИН ВОЙНЫ", "completed": False, "progress": 0, "target": 100},
            "rich_100": {"name": "НАЧИНАЮЩИЙ БОГАЧ", "completed": False, "progress": 0, "target": 100},
            "rich_500": {"name": "МАГНАТ", "completed": False, "progress": 0, "target": 500},
            "boss_slayer": {"name": "УБИЙЦА БОССОВ", "completed": False, "progress": 0, "target": 1},
            "ultra_usage": {"name": "УЛЬТРА-МАСТЕР", "completed": False, "progress": 0, "target": 1},
            "secret_finder": {"name": "ИССЛЕДОВАТЕЛЬ СЕКРЕТОВ", "completed": False, "progress": 0, "target": 1},
        }
        self.notification_time = 0
        self.notification_text = ""

    def update_progress(self, achievement_id, amount=1):
        if achievement_id in self.achievements and not self.achievements[achievement_id]["completed"]:
            self.achievements[achievement_id]["progress"] += amount
            if self.achievements[achievement_id]["progress"] >= self.achievements[achievement_id]["target"]:
                self.achievements[achievement_id]["completed"] = True
                self.notification_text = f"{self.achievements[achievement_id]['name']}"
                self.notification_time = 3
                return True
        return False

    def check_kills(self, kills):
        self.update_progress("first_kill", 1 if kills >= 1 else 0)
        self.update_progress("killer_10", 1 if kills >= 10 else 0)
        self.update_progress("killer_50", 1 if kills >= 50 else 0)
        self.update_progress("killer_100", 1 if kills >= 100 else 0)

    def check_score(self, score):
        self.update_progress("rich_100", 1 if score >= 100 else 0)
        self.update_progress("rich_500", 1 if score >= 500 else 0)

    def check_boss(self):
        self.update_progress("boss_slayer")

    def check_ultra(self):
        self.update_progress("ultra_usage")

    def check_secret(self):
        self.update_progress("secret_finder")

    def update(self, dt):
        if self.notification_time > 0:
            self.notification_time -= dt


# ========== УЛЬТРА-РЕЖИМ ==========
class UltraMode:
    def __init__(self):
        self.active = False
        self.duration = 0
        self.cooldown = 0
        self.radius = 200
        self.from_secret = False
        self.auto_ultra_timer = 0
        self.auto_ultra_interval = 25.0

    def activate(self, player, enemies, boss, from_secret=False):
        if not from_secret:
            return False

        if self.cooldown <= 0 and not self.active:
            self.active = True
            self.from_secret = True
            self.duration = 5.0
            player.message = "УЛЬТРА-РЕЖИМ ИЗ СЕКРЕТНОГО СУНДУКА! 5 СЕКУНД!"
            player.message_time = 2
            self.explode(player, enemies, boss)
            return True
        elif self.cooldown > 0:
            player.message = f"Ультра перезаряжается: {int(self.cooldown)} сек"
            player.message_time = 1
        return False

    def auto_activate(self, player, enemies, boss, mini_enemies=None):
        if boss and not self.active and self.cooldown <= 0:
            self.active = True
            self.from_secret = False
            self.duration = 5.0
            player.message = "АВТО-УЛЬТРА РЕЖИМ АКТИВИРОВАН! 5 СЕКУНД!"
            player.message_time = 2
            self.explode(player, enemies, boss, mini_enemies)
            return True
        return False

    def explode(self, player, enemies, boss, mini_enemies=None):
        killed_count = 0

        for enemy in enemies[:]:
            dist = math.sqrt((player.x - enemy.x) ** 2 + (player.y - enemy.y) ** 2)
            if dist < self.radius:
                enemies.remove(enemy)
                killed_count += 1
                player.kill_count += 1
                player.score += 10

        if mini_enemies:
            for mini in mini_enemies[:]:
                dist = math.sqrt((player.x - mini.x) ** 2 + (player.y - mini.y) ** 2)
                if dist < self.radius:
                    mini_enemies.remove(mini)
                    mini.sprite.visible = False
                    killed_count += 1
                    player.kill_count += 1
                    player.score += 5

        if boss:
            dist = math.sqrt((player.x - boss.x) ** 2 + (player.y - boss.y) ** 2)
            if dist < self.radius:
                boss.health -= 50
                trigger_shake(3.0, 20)
                player.message = f"УЛЬТРА: боссу нанесено 50 урона! Осталось: {boss.health}"
                player.message_time = 2

        if killed_count > 0:
            player.message = f"УНИЧТОЖЕНО {killed_count} ВРАГОВ И МИНИ-ВРАГОВ!"
            player.message_time = 1.5
            player.score += killed_count * 10

        return killed_count

    def update(self, dt, player, enemies, boss, mini_enemies=None):
        if boss is not None and not self.active:
            self.auto_ultra_timer += dt
            if self.auto_ultra_timer >= self.auto_ultra_interval:
                self.auto_ultra_timer = 0
                self.auto_activate(player, enemies, boss, mini_enemies)

        if self.active:
            self.duration -= dt
            if int(self.duration * 2) != int((self.duration + dt) * 2):
                self.explode(player, enemies, boss, mini_enemies)
            if self.duration <= 0:
                self.active = False
                self.cooldown = 0
                if self.from_secret:
                    player.message = "УЛЬТРА-РЕЖИМ ИЗ СЕКРЕТНОГО СУНДУКА ЗАКОНЧИЛСЯ!"
                else:
                    player.message = "АВТО-УЛЬТРА РЕЖИМ ЗАКОНЧИЛСЯ!"
                player.message_time = 2
        if self.cooldown > 0:
            self.cooldown -= dt

    def draw_radius(self, player):
        if self.active and player:
            if self.from_secret:
                color = (255, 215, 0, 80)
                outline_color = (255, 215, 0, 200)
            else:
                color = (0, 255, 255, 80)
                outline_color = (0, 255, 255, 200)
            circle = pyglet.shapes.Circle(player.x + 20, player.y + 20, self.radius,
                                          color=color, batch=ui_batch)
            circle.draw()
            outline = pyglet.shapes.Circle(player.x + 20, player.y + 20, self.radius,
                                           color=outline_color, batch=ui_batch)
            outline.draw()


# ========== ОГНЕННЫЙ ВРАГ ==========
class FireEnemy:
    def __init__(self, x, y):
        self.sprite = pyglet.sprite.Sprite(create_rect((255, 50, 50, 255), 35, 35), x, y, batch=batch)
        self.x = x
        self.y = y
        self.health = 40
        self.speed = 120
        self.patrol_target = (random.randint(50, WINDOW_WIDTH - 50), random.randint(50, WINDOW_HEIGHT - 50))
        self.explosion_radius = 100

    def update(self, player, dt):
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist > 0 and dist < 350:
            self.x += (dx / dist) * self.speed * dt
            self.y += (dy / dist) * self.speed * dt
        else:
            tx, ty = self.patrol_target
            dx2 = tx - self.x
            dy2 = ty - self.y
            dist2 = math.sqrt(dx2 * dx2 + dy2 * dy2)
            if dist2 > 10:
                self.x += (dx2 / dist2) * self.speed * dt * 0.5
                self.y += (dy2 / dist2) * self.speed * dt * 0.5
            else:
                self.patrol_target = (random.randint(50, WINDOW_WIDTH - 50), random.randint(50, WINDOW_HEIGHT - 50))

        self.x = max(10, min(self.x, WINDOW_WIDTH - 45))
        self.y = max(10, min(self.y, WINDOW_HEIGHT - 45))
        self.sprite.x = self.x
        self.sprite.y = self.y

        if dist < 50:
            return player.take_damage(25 * dt)
        return False

    def explode(self, player, enemies):
        for enemy in enemies[:]:
            if enemy != self:
                dist = math.sqrt((self.x - enemy.x) ** 2 + (self.y - enemy.y) ** 2)
                if dist < self.explosion_radius:
                    enemies.remove(enemy)

        dist_to_player = math.sqrt((self.x - player.x) ** 2 + (self.y - player.y) ** 2)
        if dist_to_player < self.explosion_radius:
            player.take_damage(15)
            player.message = "ОГНЕННЫЙ ВРАГ ВЗОРВАЛСЯ! -15 HP!"
            player.message_time = 1

        return True


# ========== МИНИ-ВРАГ (УМЕНЬШЕН УРОН) ==========
class MiniEnemy:
    def __init__(self, x, y):
        self.sprite = pyglet.sprite.Sprite(create_rect((255, 100, 100, 255), 25, 25), x, y, batch=batch)
        self.x = x
        self.y = y
        self.health = 20
        self.max_health = 20
        self.speed = 150
        self.damage = 3  # Уменьшено с 10 до 3!

    def update(self, player, dt):
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist > 0:
            self.x += (dx / dist) * self.speed * dt
            self.y += (dy / dist) * self.speed * dt

        self.x = max(10, min(self.x, WINDOW_WIDTH - 35))
        self.y = max(10, min(self.y, WINDOW_HEIGHT - 35))
        self.sprite.x = self.x
        self.sprite.y = self.y

        if dist < 40:
            return player.take_damage(self.damage * dt * 30)  # Делим на 30 для плавности
        return False

    def take_damage(self, damage):
        self.health -= damage
        return self.health <= 0


# ========== СОЗДАНИЕ ГРАФИКИ ==========
def create_rect(color, width=32, height=32):
    pattern = pyglet.image.SolidColorImagePattern(color)
    return pattern.create_image(width, height)


PLAYER_COLOR = (50, 200, 50, 255)
ENEMY_COLOR = (200, 50, 50, 255)
BOSS_COLOR = (255, 0, 100, 255)
CHEST_COLOR = (255, 200, 0, 255)
WALL_COLOR = (100, 100, 100, 255)
PET_COLOR = (100, 200, 255, 255)
SECRET_CHEST_COLOR = (255, 100, 255, 255)

player_img = create_rect(PLAYER_COLOR, 40, 40)
enemy_img = create_rect(ENEMY_COLOR, 35, 35)
boss_img = create_rect(BOSS_COLOR, 60, 60)
chest_img = create_rect(CHEST_COLOR, 30, 30)
wall_img = create_rect(WALL_COLOR, 50, 50)
pet_img = create_rect(PET_COLOR, 25, 25)
secret_chest_img = create_rect(SECRET_CHEST_COLOR, 35, 35)


# ========== КЛАСС ПИТОМЦА ==========
class Pet:
    def __init__(self, x, y):
        self.sprite = pyglet.sprite.Sprite(pet_img, x, y, batch=batch)
        self.x = x
        self.y = y
        self.speed = 200
        self.collect_radius = 60
        self.attack_cooldown = 0
        self.level = 1
        self.health = 100
        self.shoot_cooldown = 0
        self.damage = 20

    def update(self, player, dt, drops, enemies, boss, bullets):
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist > 100:
            self.x += (dx / dist) * self.speed * dt
            self.y += (dy / dist) * self.speed * dt
        elif dist < 60:
            self.x -= (dx / dist) * self.speed * dt * 0.5
            self.y -= (dy / dist) * self.speed * dt * 0.5

        self.x = max(10, min(self.x, WINDOW_WIDTH - 35))
        self.y = max(10, min(self.y, WINDOW_HEIGHT - 35))
        self.sprite.x = self.x
        self.sprite.y = self.y

        for drop in drops[:]:
            if abs(self.x - drop.x) < self.collect_radius and abs(self.y - drop.y) < self.collect_radius:
                healed = drop.collect(player)
                if drop in drops:
                    drops.remove(drop)
                drop.sprite.visible = False
                player.score += 15
                player.message = f"Питомец собрал {drop.drop_type}! +15 очков"
                player.message_time = 1
                return healed

        if boss and self.shoot_cooldown <= 0:
            dx = boss.x - self.x
            dy = boss.y - self.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > 0:
                dir_x = dx / dist
                dir_y = dy / dist

                start_x = self.x + 10 + dir_x * 20
                start_y = self.y + 10 + dir_y * 20

                bullet = Bullet(start_x, start_y, boss.x, boss.y, damage=self.damage, speed=350, owner="pet")
                bullets.append(bullet)
                self.shoot_cooldown = 1.0

        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= dt

        if self.attack_cooldown <= 0:
            for enemy in enemies[:]:
                if abs(self.x - enemy.x) < 50 and abs(self.y - enemy.y) < 50:
                    enemies.remove(enemy)
                    self.attack_cooldown = 2.0
                    player.kill_count += 1
                    player.score += 10
                    player.achievements.check_kills(player.kill_count)
                    player.message = "Питомец убил врага! +10 очков"
                    player.message_time = 0.8
                    return True

        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        return None


# ========== СЕКРЕТНЫЙ СУНДУК ==========
class SecretChest:
    def __init__(self, x, y):
        self.sprite = pyglet.sprite.Sprite(secret_chest_img, x, y, batch=batch)
        self.x = x
        self.y = y
        self.opened = False

    def interact(self, player, enemies, boss):
        if not self.opened:
            self.opened = True
            self.sprite.visible = False

            rewards = [
                "500 золота",
                "Полное исцеление",
                "Питомец +1 уровень",
                "Ультра-режим (5 сек)"
            ]
            reward = random.choice(rewards)

            if "золота" in reward:
                player.score += 500
                player.achievements.check_score(player.score)
                player.message = f"СЕКРЕТНЫЙ СУНДУК: 500 золота!"

            elif "исцеление" in reward:
                player.health = player.max_health
                player.max_health += 50
                player.message = f"СЕКРЕТНЫЙ СУНДУК: Полное исцеление! +50 HP!"

            elif "Питомец" in reward and player.pet:
                player.pet.level += 1
                player.pet.speed += 30
                player.pet.damage += 50
                player.message = f"СЕКРЕТНЫЙ СУНДУК: Питомец +1 уровень! Урон +50!"

            elif "Ультра" in reward:
                player.ultra_mode.activate(player, enemies, boss, from_secret=True)
                player.message = f"СЕКРЕТНЫЙ СУНДУК: Ультра-режим (5 сек)!"

            player.achievements.check_secret()
            player.inventory.append(reward)
            player.message_time = 3
            return reward, True
        return None, False


# ========== КЛАСС БОССА ==========
class Boss:
    def __init__(self, x, y, level):
        self.sprite = pyglet.sprite.Sprite(boss_img, x, y, batch=batch)
        self.x = x
        self.y = y
        self.level = level
        self.health = 3000
        self.max_health = 3000
        self.damage = 20 + level * 3
        self.speed = 100
        self.attack_cooldown = 0
        self.phase = 1
        self.spawn_timer = 0
        self.minion_spawn_rate = 0.04

    def update(self, player, dt, mini_enemies):
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist > 0 and dist < 400:
            self.x += (dx / dist) * self.speed * dt
            self.y += (dy / dist) * self.speed * dt

        self.x = max(20, min(self.x, WINDOW_WIDTH - 80))
        self.y = max(20, min(self.y, WINDOW_HEIGHT - 80))
        self.sprite.x = self.x
        self.sprite.y = self.y

        if dist < 70 and self.attack_cooldown <= 0:
            player.take_damage(self.damage)
            self.attack_cooldown = 1.0

        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt

        self.spawn_timer += dt
        while self.spawn_timer >= self.minion_spawn_rate:
            self.spawn_timer -= self.minion_spawn_rate
            if len(mini_enemies) < 100:
                angle = random.uniform(0, 2 * math.pi)
                distance = random.randint(100, 250)
                spawn_x = self.x + distance * math.cos(angle)
                spawn_y = self.y + distance * math.sin(angle)
                spawn_x = max(20, min(spawn_x, WINDOW_WIDTH - 45))
                spawn_y = max(20, min(spawn_y, WINDOW_HEIGHT - 45))
                mini_enemies.append(MiniEnemy(spawn_x, spawn_y))

        if self.health <= self.max_health // 2 and self.phase == 1:
            self.phase = 2
            self.speed = 160
            self.damage += 10
            self.minion_spawn_rate = 0.02
            trigger_shake(3.0, 20)
            return "phase_change"

        return None

    def take_damage(self, damage):
        if damage > 0:
            self.health -= damage
            trigger_shake(3.0, 15)
            return self.health <= 0
        return False

    def draw_health_bar(self):
        bar_width = 300
        bar_height = 20
        health_percent = self.health / self.max_health
        bar_x = self.x + 30 - bar_width // 2
        bar_y = self.y - 40

        pyglet.shapes.Rectangle(bar_x, bar_y, bar_width, bar_height, color=(50, 50, 50, 255), batch=ui_batch).draw()
        color = (255, 0, 0, 255) if health_percent > 0.5 else (255, 100, 0, 255)
        pyglet.shapes.Rectangle(bar_x, bar_y, bar_width * health_percent, bar_height, color=color,
                                batch=ui_batch).draw()
        pyglet.text.Label(f"БОСС {int(self.health)}/{int(self.max_health)} HP",
                          x=self.x + 30, y=self.y - 35, font_size=12, anchor_x='center', color=(255, 0, 0, 255)).draw()


# ========== КЛАСС ДРОПА ==========
class Drop:
    def __init__(self, x, y, drop_type):
        self.x = x
        self.y = y
        self.drop_type = drop_type
        self.lifetime = 10.0
        self.max_lifetime = 10.0

        if drop_type == "зелье":
            img = create_rect((0, 255, 0, 255), 20, 20)
            self.heal_amount = 20
        elif drop_type == "кристалл":
            img = create_rect((255, 0, 255, 255), 20, 20)
            self.heal_amount = 15
        else:
            img = create_rect((255, 215, 0, 255), 20, 20)
            self.heal_amount = 10

        self.sprite = pyglet.sprite.Sprite(img, x, y, batch=batch)

    def update(self, dt):
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.sprite.visible = False
            return False

        if self.lifetime < 2:
            if int(self.lifetime * 10) % 2 == 0:
                self.sprite.opacity = 128
            else:
                self.sprite.opacity = 255
            scale = max(0.3, self.lifetime / 2)
            self.sprite.scale = scale
        else:
            self.sprite.opacity = 255
            self.sprite.scale = 1
        return True

    def draw_timer(self):
        if self.lifetime > 0 and self.lifetime < self.max_lifetime:
            percent = self.lifetime / self.max_lifetime
            bar_x = self.x + 10 - 15
            bar_y = self.y + 25

            if percent > 0.5:
                color = (50, 200, 50, 255)
            elif percent > 0.2:
                color = (200, 200, 50, 255)
            else:
                color = (200, 50, 50, 255)

            pyglet.shapes.Rectangle(bar_x, bar_y, 30, 4, color=(50, 50, 50, 255), batch=ui_batch).draw()
            pyglet.shapes.Rectangle(bar_x, bar_y, 30 * percent, 4, color=color, batch=ui_batch).draw()

    def collect(self, player):
        return player.heal(self.heal_amount)


# ========== ДЕКОРАЦИИ ==========
class Decoration:
    def __init__(self, x, y, deco_type):
        color = (random.randint(50, 200), random.randint(50, 150), random.randint(50, 100), 255)
        self.sprite = pyglet.sprite.Sprite(create_rect(color, 15, 15), x, y, batch=batch)


# ========== ОБЫЧНЫЙ ВРАГ ==========
class Enemy:
    def __init__(self, x, y):
        self.sprite = pyglet.sprite.Sprite(enemy_img, x, y, batch=batch)
        self.x = x
        self.y = y
        self.health = 50
        self.speed = 100
        self.patrol_target = (random.randint(50, WINDOW_WIDTH - 50), random.randint(50, WINDOW_HEIGHT - 50))

    def update(self, player, dt):
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist > 0 and dist < 350:
            self.x += (dx / dist) * self.speed * dt
            self.y += (dy / dist) * self.speed * dt
        else:
            tx, ty = self.patrol_target
            dx2 = tx - self.x
            dy2 = ty - self.y
            dist2 = math.sqrt(dx2 * dx2 + dy2 * dy2)
            if dist2 > 10:
                self.x += (dx2 / dist2) * self.speed * dt * 0.5
                self.y += (dy2 / dist2) * self.speed * dt * 0.5
            else:
                self.patrol_target = (random.randint(50, WINDOW_WIDTH - 50), random.randint(50, WINDOW_HEIGHT - 50))

        self.x = max(10, min(self.x, WINDOW_WIDTH - 45))
        self.y = max(10, min(self.y, WINDOW_HEIGHT - 45))
        self.sprite.x = self.x
        self.sprite.y = self.y

        if dist < 50:
            return player.take_damage(20 * dt)
        return False


# ========== КЛАСС ИГРОКА ==========
class Player:
    def __init__(self, x, y):
        self.sprite = pyglet.sprite.Sprite(player_img, x, y, batch=batch)
        self.x = x
        self.y = y
        self.health = 100
        self.max_health = 100
        self.speed = 400
        self.inventory = []
        self.attack_cooldown = 0
        self.kill_count = 0
        self.level = 1
        self.score = 0
        self.damage_bonus = 0
        self.message = ""
        self.message_time = 0
        self.ultra_mode = UltraMode()
        self.achievements = Achievements()
        self.pet = None
        self.shoot_cooldown = 0
        self.lives = 10

    def move(self, dx, dy, dt, walls):
        new_x = self.x + dx * self.speed * dt
        new_y = self.y + dy * self.speed * dt
        new_x = max(10, min(new_x, WINDOW_WIDTH - 50))
        new_y = max(10, min(new_y, WINDOW_HEIGHT - 50))

        for wall in walls:
            if (new_x < wall.x + wall.width and new_x + 40 > wall.x and
                    new_y < wall.y + wall.height and new_y + 40 > wall.y):
                return
        self.x = new_x
        self.y = new_y
        self.sprite.x = self.x
        self.sprite.y = self.y

    def shoot(self, boss, bullets):
        if boss and self.shoot_cooldown <= 0:
            dx = boss.x - self.x
            dy = boss.y - self.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > 0:
                dir_x = dx / dist
                dir_y = dy / dist

                start_x = self.x + 20 + dir_x * 25
                start_y = self.y + 20 + dir_y * 25

                bullet = Bullet(start_x, start_y, boss.x, boss.y, damage=20, speed=500, owner="player")
                bullets.append(bullet)
                self.shoot_cooldown = 0.3
                return True
        return False

    def attack(self, enemies, boss=None, mini_enemies=None):
        if self.attack_cooldown > 0:
            return False, None
        damage = 25 + self.level * 5 + self.damage_bonus

        if boss and abs(self.x - boss.x) < 80 and abs(self.y - boss.y) < 80:
            if boss.take_damage(damage):
                self.achievements.check_boss()
                return True, "boss_killed"
            self.attack_cooldown = 0.5
            return True, "boss_hit"

        for enemy in enemies[:]:
            if abs(self.x - enemy.x) < 60 and abs(self.y - enemy.y) < 60:
                is_fire = isinstance(enemy, FireEnemy)
                enemies.remove(enemy)
                self.attack_cooldown = 0.3
                self.kill_count += 1
                self.achievements.check_kills(self.kill_count)

                if is_fire:
                    enemy.explode(self, enemies)
                    self.message = "ОГНЕННЫЙ ВРАГ ВЗОРВАЛСЯ!"
                    self.message_time = 1

                return True, enemy

        if mini_enemies:
            for mini in mini_enemies[:]:
                if abs(self.x - mini.x) < 60 and abs(self.y - mini.y) < 60:
                    if mini.take_damage(damage):
                        mini_enemies.remove(mini)
                        mini.sprite.visible = False
                        self.kill_count += 1
                        self.score += 5
                        self.message = "МИНИ-ВРАГ УНИЧТОЖЕН! +5 очков"
                        self.message_time = 0.8
                    self.attack_cooldown = 0.3
                    return True, "mini_killed"

        return False, None

    def take_damage(self, damage):
        if boss is not None and current_level == max_level:
            self.lives -= 1
            if self.lives <= 0:
                self.health = 0
                return True
            self.health = 100
            self.message = f"Осталось жизней: {self.lives}"
            self.message_time = 2
            return False
        else:
            self.health -= damage
            return self.health <= 0

    def heal(self, amount):
        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        return self.health - old_health

    def update(self, dt):
        if self.attack_cooldown > 0:
            self.attack_cooldown -= dt
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= dt
        self.achievements.update(dt)


class Chest:
    def __init__(self, x, y):
        self.sprite = pyglet.sprite.Sprite(chest_img, x, y, batch=batch)
        self.x = x
        self.y = y
        self.opened = False

    def interact(self, player):
        if not self.opened:
            self.opened = True
            self.sprite.visible = False
            rewards = ["Золото", "Золото", "Зелье здоровья", "Кристалл"]
            reward = random.choice(rewards)
            player.inventory.append(reward)

            if reward == "Зелье здоровья":
                healed = player.heal(30)
                return reward, healed, 30
            else:
                healed = player.heal(10)
                player.achievements.check_score(player.score)
                return reward, healed, 10


class Wall:
    def __init__(self, x, y, width=50, height=50):
        self.sprite = pyglet.sprite.Sprite(wall_img, x, y, batch=batch)
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.sprite.scale_x = width / 50
        self.sprite.scale_y = height / 50


# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
player = None
enemies = []
mini_enemies = []
chests = []
secret_chests = []
walls = []
decorations = []
boss = None
drops = []
bullets = []
key_handler = None


# ========== ГЕНЕРАЦИЯ МИРА ==========
def generate_walls(count):
    walls = []
    player_start_x = WINDOW_WIDTH // 2
    player_start_y = WINDOW_HEIGHT // 2

    for _ in range(count):
        while True:
            width = random.choice([40, 60, 80, 100])
            height = random.choice([20, 30, 40])
            x = random.randint(50, WINDOW_WIDTH - width - 50)
            y = random.randint(50, WINDOW_HEIGHT - height - 50)

            if abs(x - player_start_x) > 150 and abs(y - player_start_y) > 150:
                overlap = False
                for w in walls:
                    if (x < w.x + w.width + 20 and x + width + 20 > w.x and
                            y < w.y + w.height + 20 and y + height + 20 > w.y):
                        overlap = True
                        break
                if not overlap:
                    walls.append(Wall(x, y, width, height))
                    break
    return walls


def generate_decorations():
    decorations = []
    for i in range(80):
        x = random.randint(20, WINDOW_WIDTH - 20)
        y = random.randint(20, WINDOW_HEIGHT - 20)
        decorations.append(Decoration(x, y, "deco"))
    return decorations


def init_level(level):
    global player, enemies, mini_enemies, chests, secret_chests, walls, decorations, boss, drops, bullets, current_level

    current_level = level

    old_score = player.score if player else 0
    old_kill_count = player.kill_count if player else 0
    old_achievements = player.achievements if player else Achievements()
    old_damage_bonus = player.damage_bonus if player else 0
    old_max_health = player.max_health if player else 100
    old_speed = player.speed if player else 400
    old_pet = player.pet if player and hasattr(player, 'pet') else None
    old_lives = player.lives if player else 10

    player = Player(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
    player.level = level
    player.health = min(player.max_health, player.health + 20)

    player.score = old_score
    player.kill_count = old_kill_count
    player.achievements = old_achievements
    player.damage_bonus = old_damage_bonus
    player.max_health = old_max_health
    player.speed = old_speed
    player.health = min(player.max_health, player.health)
    player.lives = old_lives

    if old_pet:
        player.pet = old_pet
        player.pet.x = player.x - 50
        player.pet.y = player.y
        player.pet.damage = 20 + (level - 1) * 50
    else:
        player.pet = Pet(player.x - 50, player.y)
        player.pet.damage = 20 + (level - 1) * 50

    walls = generate_walls(WALL_COUNT)
    decorations = generate_decorations()

    enemies = []
    mini_enemies = []
    enemy_cnt = max(20, ENEMY_COUNT - (level - 1) * 5)
    for i in range(enemy_cnt):
        while True:
            x = random.randint(50, WINDOW_WIDTH - 50)
            y = random.randint(50, WINDOW_HEIGHT - 50)
            on_wall = False
            for wall in walls:
                if (x > wall.x - 30 and x < wall.x + wall.width + 30 and
                        y > wall.y - 30 and y < wall.y + wall.height + 30):
                    on_wall = True
                    break
            if not on_wall and abs(x - player.x) > 100:
                if random.random() < 0.3:
                    enemies.append(FireEnemy(x, y))
                else:
                    enemies.append(Enemy(x, y))
                break

    chests = []
    for i in range(8 + level):
        while True:
            x = random.randint(50, WINDOW_WIDTH - 50)
            y = random.randint(50, WINDOW_HEIGHT - 50)
            on_wall = False
            for wall in walls:
                if (x > wall.x - 40 and x < wall.x + wall.width + 40 and
                        y > wall.y - 40 and y < wall.y + wall.height + 40):
                    on_wall = True
                    break
            if not on_wall and abs(x - player.x) > 100:
                chests.append(Chest(x, y))
                break

    secret_chests = []
    for i in range(3):
        while True:
            x = random.randint(50, WINDOW_WIDTH - 50)
            y = random.randint(50, WINDOW_HEIGHT - 50)
            on_wall = False
            for wall in walls:
                if (x > wall.x - 50 and x < wall.x + wall.width + 50 and
                        y > wall.y - 50 and y < wall.y + wall.height + 50):
                    on_wall = True
                    break
            if not on_wall and abs(x - player.x) > 150:
                secret_chests.append(SecretChest(x, y))
                break

    if level == max_level:
        boss = None
        player.lives = 10
        player.message = f"УРОВЕНЬ {level}! Уничтожьте всех врагов, чтобы вызвать БОССА! У вас {player.lives} жизней!"
        player.message_time = 4
    else:
        boss = None
        player.message = f"УРОВЕНЬ {level}! Нажми B - МАГАЗИН!"
        player.message_time = 3

    drops = []
    bullets = []


def check_level_complete():
    global current_level, current_state, boss, enemies, mini_enemies

    if current_level == max_level and boss is None and len(enemies) == 0:
        boss_x = random.randint(100, WINDOW_WIDTH - 100)
        boss_y = random.randint(100, WINDOW_HEIGHT - 100)
        boss = Boss(boss_x, boss_y, current_level)
        if player:
            player.message = "БОСС ПОЯВИЛСЯ! ОН СПАВНИТ 25 МИНИ-ВРАГОВ В СЕКУНДУ! У вас 10 жизней!"
            player.message_time = 3
        play_boss_music()
        return

    if boss is not None and boss.health <= 0 and len(enemies) == 0 and len(mini_enemies) == 0:
        stop_boss_music()
        if current_level < max_level:
            current_level += 1
            init_level(current_level)
            if player:
                player.message = f"УРОВЕНЬ {current_level}!"
                player.message_time = 3
        else:
            show_troll_screen()
        return

    if boss is None and len(enemies) == 0:
        if current_level < max_level:
            current_level += 1
            init_level(current_level)
            if player:
                player.message = f"УРОВЕНЬ {current_level}!"
                player.message_time = 3
        else:
            pass


def create_drop(x, y):
    global drops
    if len(drops) >= 25:
        drops.pop(0).sprite.visible = False
    drop_type = random.choice(["золото", "золото", "золото", "зелье", "кристалл"])
    drops.append(Drop(x, y, drop_type))


# ========== UI ==========
health_bg = pyglet.shapes.Rectangle(20, WINDOW_HEIGHT - 45, 250, 25, color=(100, 100, 100, 255), batch=ui_batch)
health_fill = pyglet.shapes.Rectangle(20, WINDOW_HEIGHT - 45, 250, 25, color=(255, 0, 0, 255), batch=ui_batch)


def update_ui():
    if player:
        health_percent = max(0, player.health / player.max_health)
        health_fill.width = 250 * health_percent


# ========== ОТРИСОВКА МАГАЗИНА ==========
def draw_shop():
    window.clear()
    pyglet.shapes.Rectangle(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, color=(0, 0, 0, 200), batch=ui_batch).draw()

    pyglet.text.Label("МАГАЗИН", x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 100,
                      font_size=48, anchor_x='center', color=(255, 215, 0, 255)).draw()
    pyglet.text.Label(f"Очков: {player.score}", x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 150,
                      font_size=24, anchor_x='center', color=(255, 215, 0, 255)).draw()

    items = list(shop.items.values())
    start_y = WINDOW_HEIGHT - 250

    for i, item in enumerate(items):
        y = start_y - i * 80
        color = (255, 215, 0, 255) if shop.selected == i else (255, 255, 255, 255)
        pyglet.text.Label(f"{i + 1}. {item['name']} - {item['cost']} очков",
                          x=WINDOW_WIDTH // 2, y=y, font_size=24,
                          anchor_x='center', color=color).draw()

    pyglet.text.Label("Нажмите цифру (1-3) для покупки | B - выйти",
                      x=WINDOW_WIDTH // 2, y=50, font_size=16,
                      anchor_x='center', color=(150, 150, 150, 255)).draw()


# ========== ОТРИСОВКА ==========
@window.event
def on_draw():
    global current_state, shake_timer, shake_intensity

    if current_state == GameState.MENU:
        draw_menu()
        return

    if current_state == GameState.SHOP:
        draw_shop()
        return

    if current_state == GameState.TROLL:
        window.clear()
        pyglet.shapes.Rectangle(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, color=(0, 0, 0, 255), batch=ui_batch).draw()
        if troll_sprite:
            troll_sprite.draw()

        # БИНАРНЫЙ КОД ПРИ ПОБЕДЕ!
        binary_code = "01100010 01111001 00100000 01101001 01101111 01101110 01110101 01111000"
        pyglet.text.Label(binary_code,
                          x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 250,
                          font_size=28, anchor_x='center', color=(0, 255, 0, 255)).draw()

        pyglet.text.Label("ТЫ ПОБЕДИЛ БОССА!",
                          x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 100,
                          font_size=48, anchor_x='center', color=(255, 0, 0, 255)).draw()
        pyglet.text.Label("ТЕБЯ ric roooooooooool",
                          x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 170,
                          font_size=36, anchor_x='center', color=(255, 200, 0, 255)).draw()
        pyglet.text.Label("уф пипа клутой",
                          x=WINDOW_WIDTH // 2, y=100,
                          font_size=24, anchor_x='center', color=(150, 150, 150, 255)).draw()
        return

    if current_state == GameState.PLAYING and shake_timer > 0:
        offset_x = random.randint(-shake_intensity, shake_intensity)
        offset_y = random.randint(-shake_intensity, shake_intensity)
        win_x, win_y = window.get_location()
        window.set_location(win_x + offset_x, win_y + offset_y)
    else:
        win_x, win_y = window.get_location()
        if win_x != 0 or win_y != 0:
            window.set_location(0, 0)

    window.clear()

    batch.draw()

    if player:
        player.ultra_mode.draw_radius(player)

    if boss:
        boss.draw_health_bar()

    for drop in drops:
        drop.draw_timer()

    ui_batch.draw()

    if player:
        pyglet.text.Label(f"HP: {int(player.health)}/{player.max_health}", x=25, y=WINDOW_HEIGHT - 42,
                          font_size=14).draw()
        if current_level == max_level:
            pyglet.text.Label(f"Жизней: {player.lives}", x=25, y=WINDOW_HEIGHT - 62, font_size=14,
                              color=(255, 215, 0, 255)).draw()
    pyglet.text.Label(f"Уровень: {current_level}/{max_level}", x=25, y=WINDOW_HEIGHT - 82, font_size=16,
                      color=(255, 215, 0, 255)).draw()

    if player:
        pyglet.text.Label(f"Убито: {player.kill_count}", x=25, y=WINDOW_HEIGHT - 107, font_size=14,
                          color=(200, 200, 255, 255)).draw()
        pyglet.text.Label(f"Очки: {player.score}", x=25, y=WINDOW_HEIGHT - 132, font_size=14,
                          color=(255, 215, 0, 255)).draw()
    pyglet.text.Label(f"Врагов: {len(enemies)}", x=25, y=WINDOW_HEIGHT - 157, font_size=14,
                      color=(200, 200, 255, 255)).draw()
    pyglet.text.Label(f"Дропов: {len(drops)}/25", x=25, y=WINDOW_HEIGHT - 182, font_size=14,
                      color=(0, 255, 255, 255)).draw()

    fire_count = sum(1 for e in enemies if isinstance(e, FireEnemy))
    if fire_count > 0:
        pyglet.text.Label(f"Огненных врагов: {fire_count} (взрываются!)", x=25, y=WINDOW_HEIGHT - 207, font_size=14,
                          color=(255, 100, 100, 255)).draw()

    if player and player.pet:
        pyglet.text.Label(f"Питомец ур. {player.pet.level} (урон: {player.pet.damage})", x=25, y=WINDOW_HEIGHT - 232,
                          font_size=14, color=(100, 200, 255, 255)).draw()

    if len(mini_enemies) > 0:
        pyglet.text.Label(f"Мини-врагов: {len(mini_enemies)} (спавн 25/сек!)", x=25, y=WINDOW_HEIGHT - 257,
                          font_size=14, color=(255, 150, 150, 255)).draw()

    if player and player.ultra_mode.active and player.ultra_mode.from_secret:
        pyglet.text.Label(f"УЛЬТРА-РЕЖИМ ИЗ СУНДУКА: {int(player.ultra_mode.duration)} сек",
                          x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 60, font_size=20,
                          anchor_x='center', color=(255, 215, 0, 255)).draw()
    elif player and player.ultra_mode.active and not player.ultra_mode.from_secret:
        pyglet.text.Label(f"АВТО-УЛЬТРА РЕЖИМ: {int(player.ultra_mode.duration)} сек",
                          x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 60, font_size=20,
                          anchor_x='center', color=(0, 255, 255, 255)).draw()

    if boss and boss.health > 0:
        pyglet.text.Label(f"БОСС - HP: {int(boss.health)}/{int(boss.max_health)}",
                          x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 30, font_size=18,
                          anchor_x='center', color=(255, 100, 100, 255)).draw()
        spawn_rate = 25 if boss.phase == 1 else 50
        pyglet.text.Label(f"СПАВН МИНИ-ВРАГОВ: {spawn_rate}/сек",
                          x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 55, font_size=14,
                          anchor_x='center', color=(255, 200, 100, 255)).draw()

        if player and player.ultra_mode:
            time_left = player.ultra_mode.auto_ultra_interval - player.ultra_mode.auto_ultra_timer
            pyglet.text.Label(f"АВТО-УЛЬТРА ЧЕРЕЗ: {int(time_left)} сек",
                              x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 80, font_size=14,
                              anchor_x='center', color=(0, 255, 255, 255)).draw()

    pyglet.text.Label("B - МАГАЗИН | Пробел - ближняя атака | Авто-стрельба", x=WINDOW_WIDTH // 2, y=15,
                      font_size=12, anchor_x='center', color=(150, 150, 150, 255)).draw()

    if player and player.achievements.notification_time > 0:
        pyglet.text.Label(player.achievements.notification_text, x=WINDOW_WIDTH // 2, y=120,
                          font_size=16, anchor_x='center', color=(255, 215, 0, 255)).draw()

    if player and player.message_time > 0:
        pyglet.text.Label(player.message, x=WINDOW_WIDTH // 2, y=180, font_size=18,
                          anchor_x='center', color=(255, 255, 100, 255)).draw()
        player.message_time -= 1 / 60

    if current_state == GameState.PAUSED:
        pyglet.text.Label("ПАУЗА", x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT // 2 + 30,
                          font_size=48, anchor_x='center', color=(255, 255, 0, 255)).draw()
        pyglet.text.Label("Нажми P для продолжения", x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT // 2 - 30,
                          font_size=24, anchor_x='center', color=(255, 255, 255, 255)).draw()

    elif current_state == GameState.GAME_OVER:
        pyglet.text.Label("ПОРАЖЕНИЕ", x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT // 2 + 30,
                          font_size=48, anchor_x='center', color=(255, 0, 0, 255)).draw()
        pyglet.text.Label("Нажми R для рестарта", x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT // 2 - 30,
                          font_size=24, anchor_x='center', color=(255, 255, 255, 255)).draw()


# ========== МЕНЮ ==========
def draw_menu():
    window.clear()

    pyglet.text.Label("skibidi чёто - там!!!", x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 150,
                      font_size=64, anchor_x='center', color=(255, 215, 0, 255)).draw()
    pyglet.text.Label("byionux",
                      x=WINDOW_WIDTH // 2, y=WINDOW_HEIGHT - 220, font_size=24,
                      anchor_x='center', color=(200, 200, 255, 255)).draw()

    mouse_x, mouse_y = window._mouse_x, window._mouse_y

    btn_y = 300
    if mouse_y > btn_y - 25 and mouse_y < btn_y + 25:
        pyglet.text.Label("НАЧАТЬ ИГРУ", x=WINDOW_WIDTH // 2, y=btn_y, font_size=32,
                          anchor_x='center', color=(255, 215, 0, 255)).draw()
    else:
        pyglet.text.Label("НЕ ВЫХОДИТЬ", x=WINDOW_WIDTH // 2, y=btn_y, font_size=32,
                          anchor_x='center', color=(255, 255, 255, 255)).draw()

    btn_y = 400
    if mouse_y > btn_y - 25 and mouse_y < btn_y + 25:
        pyglet.text.Label("ВЫХОД", x=WINDOW_WIDTH // 2, y=btn_y, font_size=32,
                          anchor_x='center', color=(255, 215, 0, 255)).draw()
    else:
        pyglet.text.Label("НЕ НАЧИНАТЬ ИГРУ", x=WINDOW_WIDTH // 2, y=btn_y, font_size=32,
                          anchor_x='center', color=(255, 255, 255, 255)).draw()

    pyglet.text.Label("Управление: WASD - движение | Пробел - ближняя атака | B - МАГАЗИН | Авто-стрельба",
                      x=WINDOW_WIDTH // 2, y=80, font_size=14, anchor_x='center', color=(255, 200, 100, 255)).draw()
    pyglet.text.Label("F5 - сохранить | F9 - загрузить | ESC - выход",
                      x=WINDOW_WIDTH // 2, y=50, font_size=14, anchor_x='center', color=(150, 150, 150, 255)).draw()


# ========== СОБЫТИЯ ==========
@window.event
def on_mouse_press(x, y, button, modifiers):
    global current_state
    if current_state == GameState.MENU:
        if y > 275 and y < 325:
            current_state = GameState.PLAYING
            center_window()
            init_level(1)
        elif y > 375 and y < 425:
            pyglet.app.exit()


@window.event
def on_mouse_motion(x, y, dx, dy):
    window._mouse_x = x
    window._mouse_y = y


@window.event
def on_key_press(symbol, modifiers):
    global current_state, current_level, player, enemies, mini_enemies, boss, walls, chests, secret_chests, drops, shop, bullets

    if current_state == GameState.TROLL:
        if symbol == key.ESCAPE:
            pyglet.app.exit()
        return

    if current_state == GameState.MENU:
        if symbol == key.ENTER:
            current_state = GameState.PLAYING
            center_window()
            init_level(1)
        return

    if current_state == GameState.VICTORY or current_state == GameState.GAME_OVER:
        if symbol == key.R:
            current_state = GameState.PLAYING
            current_level = 1
            center_window()
            init_level(1)
        return

    if current_state == GameState.SHOP:
        if symbol == key._1:
            shop.buy("health_potion", player)
        elif symbol == key._2:
            shop.buy("damage_up", player)
        elif symbol == key._3:
            shop.buy("max_health", player)
        elif symbol == key.B:
            current_state = GameState.PLAYING
        return

    if current_state == GameState.PLAYING and player:
        if symbol == key.P:
            current_state = GameState.PAUSED
            return

        if symbol == key.B:
            current_state = GameState.SHOP
            return

        if symbol == key.SPACE:
            killed, result = player.attack(enemies, boss, mini_enemies)
            if killed:
                if result == "boss_killed":
                    player.message = "БОСС ПОВЕРЖЕН!"
                    player.message_time = 2
                    boss = None
                    player.score += 200
                    player.achievements.check_score(player.score)
                    player.achievements.check_boss()
                    check_level_complete()
                elif result == "boss_hit":
                    player.message = "Удар по боссу! +30 очков"
                    player.message_time = 0.5
                    player.score += 30
                    player.achievements.check_score(player.score)
                elif result == "mini_killed":
                    pass
                else:
                    player.score += 10
                    player.message = f"Враг повержен! +10 (осталось: {len(enemies)})"
                    player.message_time = 0.8
                    player.achievements.check_kills(player.kill_count)
                    player.achievements.check_score(player.score)
                    if result and not isinstance(result, str):
                        create_drop(result.x, result.y)
            update_ui()
            check_level_complete()

    if current_state == GameState.PAUSED and symbol == key.P:
        current_state = GameState.PLAYING

    if symbol == key.F5 and current_state == GameState.PLAYING and player:
        data = {
            "timestamp": datetime.now().isoformat(),
            "score": player.score,
            "level": current_level,
            "kill_count": player.kill_count,
            "damage_bonus": player.damage_bonus,
            "max_health": player.max_health,
            "speed": player.speed,
            "lives": player.lives,
            "player": {"x": player.x, "y": player.y, "health": player.health},
            "enemies": [{"x": e.x, "y": e.y, "type": "fire" if isinstance(e, FireEnemy) else "normal"} for e in
                        enemies],
            "chests": [{"x": c.x, "y": c.y, "opened": c.opened} for c in chests],
            "secret_chests": [{"x": sc.x, "y": sc.y, "opened": sc.opened} for sc in secret_chests],
            "walls": [{"x": w.x, "y": w.y, "width": w.width, "height": w.height} for w in walls],
            "boss": {"x": boss.x, "y": boss.y, "health": boss.health, "level": boss.level} if boss else None,
            "pet_damage": player.pet.damage if player.pet else 20
        }
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        player.message = "Сохранено!"
        player.message_time = 1.5

    if symbol == key.F9 and current_state == GameState.PLAYING and player:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data:
                player.x = data["player"]["x"]
                player.y = data["player"]["y"]
                player.sprite.x = player.x
                player.sprite.y = player.y
                player.health = data["player"]["health"]
                player.score = data["score"]
                player.kill_count = data.get("kill_count", 0)
                player.damage_bonus = data.get("damage_bonus", 0)
                player.max_health = data.get("max_health", 100)
                player.speed = data.get("speed", 400)
                player.lives = data.get("lives", 10)
                current_level = data["level"]

                player.achievements.check_kills(player.kill_count)
                player.achievements.check_score(player.score)

                enemies.clear()
                for e in data["enemies"]:
                    if e.get("type") == "fire":
                        enemies.append(FireEnemy(e["x"], e["y"]))
                    else:
                        enemies.append(Enemy(e["x"], e["y"]))

                chests.clear()
                for c in data["chests"]:
                    chest = Chest(c["x"], c["y"])
                    chest.opened = c["opened"]
                    chest.sprite.visible = not c["opened"]
                    chests.append(chest)

                secret_chests.clear()
                for sc in data.get("secret_chests", []):
                    s_chest = SecretChest(sc["x"], sc["y"])
                    s_chest.opened = sc["opened"]
                    s_chest.sprite.visible = not sc["opened"]
                    secret_chests.append(s_chest)

                walls.clear()
                for w in data["walls"]:
                    walls.append(Wall(w["x"], w["y"], w["width"], w["height"]))

                if data["boss"]:
                    b = data["boss"]
                    boss = Boss(b["x"], b["y"], b["level"])
                    boss.health = b["health"]

                if not player.pet:
                    player.pet = Pet(player.x - 50, player.y)

                pet_damage = data.get("pet_damage", 20)
                player.pet.damage = pet_damage

                update_ui()
                player.message = "Загружено!"
                player.message_time = 1.5

    if symbol == key.ESCAPE:
        pyglet.app.exit()


# ========== ОСНОВНОЙ ЦИКЛ ==========
def update(dt):
    global current_state, drops, secret_chests, boss, bullets, mini_enemies, enemies, shake_timer

    if current_state == GameState.TROLL:
        return

    if current_state != GameState.PLAYING or player is None:
        return

    if shake_timer > 0:
        shake_timer -= dt

    dx = dy = 0
    if key_handler[key.UP] or key_handler[key.W]: dy = 1
    if key_handler[key.DOWN] or key_handler[key.S]: dy = -1
    if key_handler[key.LEFT] or key_handler[key.A]: dx = -1
    if key_handler[key.RIGHT] or key_handler[key.D]: dx = 1

    player.move(dx, dy, dt, walls)
    player.update(dt)

    if boss:
        player.shoot(boss, bullets)

    player.ultra_mode.update(dt, player, enemies, boss, mini_enemies)

    for bullet in bullets[:]:
        bullet.update(dt)
        if not bullet.active:
            bullets.remove(bullet)
            bullet.sprite.visible = False
        else:
            if boss and bullet.owner in ["player", "pet"]:
                if bullet.check_hit(boss):
                    if boss.health <= 0:
                        if current_level == max_level:
                            show_troll_screen()
                            boss = None
                            shake_timer = 0
                            win_x, win_y = window.get_location()
                            if win_x != 0 or win_y != 0:
                                window.set_location(0, 0)
                            update_ui()
                            return
                        else:
                            boss = None
                            shake_timer = 0
                            win_x, win_y = window.get_location()
                            if win_x != 0 or win_y != 0:
                                window.set_location(0, 0)
                            stop_boss_music()
                            check_level_complete()
                            update_ui()
                            return

            if bullet.owner in ["player", "pet"] and len(mini_enemies) > 0:
                bullet.check_hit_mini(mini_enemies)

    if player.pet:
        player.pet.update(player, dt, drops, enemies, boss, bullets)

    if boss:
        result = boss.update(player, dt, mini_enemies)
        if result == "phase_change":
            player.message = "БОСС ВЗБЕШЁН! ТЕПЕРЬ СПАВНИТ 50 МИНИ-ВРАГОВ В СЕКУНДУ!"
            player.message_time = 2

        if boss.health <= 0:
            if current_level == max_level:
                show_troll_screen()
                boss = None
                shake_timer = 0
                win_x, win_y = window.get_location()
                if win_x != 0 or win_y != 0:
                    window.set_location(0, 0)
                update_ui()
                return
            else:
                boss = None
                shake_timer = 0
                win_x, win_y = window.get_location()
                if win_x != 0 or win_y != 0:
                    window.set_location(0, 0)
                stop_boss_music()
                check_level_complete()
                update_ui()
                return

    for enemy in enemies[:]:
        if enemy.update(player, dt):
            current_state = GameState.GAME_OVER
            shake_timer = 0
            win_x, win_y = window.get_location()
            if win_x != 0 or win_y != 0:
                window.set_location(0, 0)
            stop_boss_music()
            update_ui()

    for mini in mini_enemies[:]:
        if mini.update(player, dt):
            current_state = GameState.GAME_OVER
            shake_timer = 0
            win_x, win_y = window.get_location()
            if win_x != 0 or win_y != 0:
                window.set_location(0, 0)
            stop_boss_music()
            update_ui()
        if mini.health <= 0:
            mini_enemies.remove(mini)
            mini.sprite.visible = False

    for drop in drops[:]:
        if not drop.update(dt):
            if drop in drops:
                drops.remove(drop)
            drop.sprite.visible = False

    for drop in drops[:]:
        if abs(player.x - drop.x) < 35 and abs(player.y - drop.y) < 35:
            healed = drop.collect(player)
            if drop in drops:
                drops.remove(drop)
            drop.sprite.visible = False
            player.score += 15
            player.achievements.check_score(player.score)
            player.message = f"СОБРАН {drop.drop_type}! +15 очков, +{healed} HP!"
            player.message_time = 1
            update_ui()

    for chest in chests:
        if not chest.opened and abs(player.x - chest.x) < 50 and abs(player.y - chest.y) < 50:
            reward, healed, amount = chest.interact(player)
            player.score += 50
            player.achievements.check_score(player.score)
            player.message = f"{reward}! +{amount} HP! (+50 очков)"
            player.message_time = 1.5
            update_ui()

    for secret_chest in secret_chests[:]:
        if not secret_chest.opened and abs(player.x - secret_chest.x) < 55 and abs(player.y - secret_chest.y) < 55:
            reward, is_secret = secret_chest.interact(player, enemies, boss)
            if is_secret:
                player.score += 100
                player.achievements.check_score(player.score)
                update_ui()
                check_level_complete()
                if secret_chest in secret_chests:
                    secret_chests.remove(secret_chest)

    if boss is None and len(enemies) == 0 and len(mini_enemies) == 0:
        check_level_complete()


# ========== ЗАПУСК ==========
if __name__ == "__main__":
    center_window()

    load_music()
    load_troll_image()

    init_level(1)
    key_handler = key.KeyStateHandler()
    window.push_handlers(key_handler)
    window._mouse_x = 0
    window._mouse_y = 0

    pyglet.clock.schedule_interval(update, 1 / 60)
    pyglet.app.run()