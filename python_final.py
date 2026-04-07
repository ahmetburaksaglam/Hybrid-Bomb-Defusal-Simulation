"""
=============================================================================
PROJECT      : Hybrid Bomb Defusal Simulation (Hardware-Software Interface)
COURSE       : CSE 101 - Introduction to Computer Engineering
TERM         : Fall 2025
INSTITUTION  : Gebze Technical University
DATE         : January 14, 2026

DESCRIPTION:
This is the main control software (Master Node) for the Bomb Defusal Project.
It utilizes a multi-threaded architecture to manage serial communication with
two separate Arduino units (Main Control Unit & Tilt Sensor Unit) simultaneously.

FEATURES:
- Real-time Serial synchronization with Arduino Hardware (9600 & 115200 Baud).
- GUI Management using Tkinter for level selection and status monitoring.
- Physics-based rendering engine using Pygame for minigames.
- Computer Vision integration (OpenCV) for motion detection modules.
- Dynamic stress management logic integrated with hardware feedback.

DEPENDENCIES:
- Python 3.x
- Libraries: pygame, pyserial, opencv-python, numpy, tkinter
=============================================================================
"""

import tkinter as tk
from tkinter import messagebox
import serial
import time
import random
import pygame
import threading
import math
import sys

# Initialize Sound System (Windows specific)
try:
    import winsound
except ImportError:
    winsound = None

# Initialize Computer Vision Library
try:
    import cv2
    import numpy as np
except ImportError:
    pass # Handler will manage absence during runtime

# --- SYSTEM CONFIGURATION ---
PORT_MAIN = 'COM5'      # Main Control Unit (Arduino Uno 1)
BAUD_MAIN = 9600 

PORT_TILT = 'COM6'     # Tilt Sensor Unit (Arduino Uno 2)
BAUD_TILT = 115200      

# ==========================================
# PHYSICS & UTILITY CLASSES
# ==========================================

class PhysicsEngine:
    """Handles vector calculations and collision detection for physics-based minigames."""
    @staticmethod
    def normalize_vector(vx, vy):
        magnitude = math.sqrt(vx*vx + vy*vy)
        if magnitude < 0.001: return 0, 0
        return vx/magnitude, vy/magnitude
    
    @staticmethod
    def dot_product(v1x, v1y, v2x, v2y):
        return v1x*v2x + v1y*v2y
    
    @staticmethod
    def reflect_velocity(vx, vy, nx, ny, damping=0.7):
        dot = 2 * PhysicsEngine.dot_product(vx, vy, nx, ny)
        return (vx - dot * nx) * damping, (vy - dot * ny) * damping
    
    @staticmethod
    def advanced_circle_rect_collision(cx, cy, r, vx, vy, rect):
        closest_x = max(rect.left, min(cx, rect.right))
        closest_y = max(rect.top, min(cy, rect.bottom))
        dx = cx - closest_x
        dy = cy - closest_y
        distance_sq = dx*dx + dy*dy
        
        if distance_sq >= r*r: return False, 0, 0, 0, 0
        
        distance = math.sqrt(distance_sq)
        if distance < 0.001:
            # Handle deep penetration/overlap
            left_dist = cx - rect.left
            right_dist = rect.right - cx
            top_dist = cy - rect.top
            bottom_dist = rect.bottom - cy
            min_dist = min(left_dist, right_dist, top_dist, bottom_dist)
            if min_dist == left_dist: nx, ny, penetration = -1, 0, r - left_dist
            elif min_dist == right_dist: nx, ny, penetration = 1, 0, r - right_dist
            elif min_dist == top_dist: nx, ny, penetration = 0, -1, r - top_dist
            else: nx, ny, penetration = 0, 1, r - bottom_dist
        else:
            nx, ny = dx / distance, dy / distance
            penetration = r - distance
        return True, nx, ny, penetration, distance

class Bullet:
    def __init__(self, x, y, vx, vy, w, h):
        self.x, self.y = x, y
        self.W, self.H = w, h
        mag = math.sqrt(vx**2 + vy**2)
        speed = 12
        if mag > 0.1: self.dx, self.dy = (vx / mag) * speed, (vy / mag) * speed
        else: self.dx, self.dy = speed, 0
        self.alive = True
        self.trail = []

    def update(self):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 8: self.trail.pop(0)
        self.x += self.dx
        self.y += self.dy
        if self.x < 0 or self.x > self.W or self.y < 0 or self.y > self.H: self.alive = False

    def draw(self, screen):
        for i, pos in enumerate(self.trail):
            alpha = (i + 1) / len(self.trail)
            color = (255, int(230 * alpha), int(50 * alpha))
            pygame.draw.circle(screen, color, (int(pos[0]), int(pos[1])), int(2 + 3 * alpha))
        pygame.draw.circle(screen, (255, 255, 100), (int(self.x), int(self.y)), 6)
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), 3)

class RotConfetti:
    """Visual particle effects for successful actions."""
    def __init__(self, x, y, color=None):
        self.x, self.y = x, y
        self.vx, self.vy = random.uniform(-6, 6), random.uniform(-8, -3)
        self.life = random.randint(40, 80)
        self.max_life = self.life
        self.col = color if color else random.choice([(255,100,100), (100,255,150), (100,180,255)])
        self.rotation = random.uniform(0, math.pi * 2)
        self.rot_speed = random.uniform(-0.3, 0.3)
        
    def update(self):
        self.life -= 1
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.3
        self.vx *= 0.98
        self.rotation += self.rot_speed
        
    def draw(self, screen):
        if self.life > 0:
            alpha = self.life / self.max_life
            size = int(3 + 4 * alpha)
            color = tuple(int(c * alpha) for c in self.col)
            points = []
            for i in range(4):
                angle = self.rotation + i * math.pi / 2
                px = self.x + math.cos(angle) * size
                py = self.y + math.sin(angle) * size
                points.append((px, py))
            pygame.draw.polygon(screen, color, points)

class AdvBall:
    def __init__(self, x, y, r, w, h):
        self.x, self.y = x, y
        self.radius = r
        self.W, self.H = w, h
        self.vx = 0.0
        self.vy = 0.0
        self.trail = []
        self.rotation = 0
        self.MAX_SPEED = 8.0
        self.FRICTION = 0.985
        self.GRAVITY = 0.08
        self.TILT_GAIN = 0.12
        
    def update(self, roll, pitch):
        gravity_x = roll * self.GRAVITY
        gravity_y = pitch * self.GRAVITY
        self.vx += gravity_x * self.TILT_GAIN
        self.vy += gravity_y * self.TILT_GAIN
        
        speed = math.sqrt(self.vx**2 + self.vy**2)
        if speed > self.MAX_SPEED:
            self.vx = (self.vx / speed) * self.MAX_SPEED
            self.vy = (self.vy / speed) * self.MAX_SPEED
        
        self.vx *= self.FRICTION
        self.vy *= self.FRICTION
        self.x += self.vx
        self.y += self.vy
        self.rotation += speed * 0.1
        
        self.trail.append((self.x, self.y))
        if len(self.trail) > 25: self.trail.pop(0)
    
    def handle_collision(self, walls, moving_walls):
        active_walls = walls + [mw["rect"] for mw in moving_walls if not mw["hit"]]
        for wall in active_walls:
            hit, nx, ny, penetration, _ = PhysicsEngine.advanced_circle_rect_collision(
                self.x, self.y, self.radius, self.vx, self.vy, wall
            )
            if hit:
                self.x += nx * penetration * 1.1
                self.y += ny * penetration * 1.1
                self.vx, self.vy = PhysicsEngine.reflect_velocity(self.vx, self.vy, nx, ny)
                bounce_speed = math.sqrt(self.vx**2 + self.vy**2)
                if bounce_speed < 0.5:
                    self.vx += nx * 0.15; self.vy += ny * 0.15
    
    def clamp_position(self):
        self.x = max(self.radius, min(self.W - self.radius, self.x))
        self.y = max(self.radius, min(self.H - self.radius, self.y))
    
    def draw(self, screen, game_finished=False):
        for i, pos in enumerate(self.trail):
            if i < len(self.trail) - 1:
                alpha = i / len(self.trail)
                radius = self.radius * (0.2 + 0.8 * alpha)
                color = (int(50*alpha), int(150*alpha), int(255*alpha))
                pygame.draw.circle(screen, color, (int(pos[0]), int(pos[1])), int(radius))
        
        if not game_finished:
            pygame.draw.circle(screen, (50, 50, 50), (int(self.x+2), int(self.y+2)), self.radius)
            pygame.draw.circle(screen, (200, 220, 255), (int(self.x), int(self.y)), self.radius)
            pygame.draw.circle(screen, (255, 255, 255), (int(self.x-3), int(self.y-3)), self.radius//3)

# ==========================================
# MODULE 1: LASER OPTICS PUZZLE
# ==========================================

class LaserMirrorGame:
    def __init__(self):
        self.WIDTH, self.HEIGHT = 1050, 700
        self.GRID_SIZE = 50
        self.GRID_WIDTH = 14
        self.GRID_HEIGHT = 12
        self.MAX_MIRRORS = 6
        
        # Color Palette
        self.C_BG = (20, 20, 30)
        self.C_WALL = (70, 70, 80)
        self.C_GRID = (40, 40, 50)
        self.C_LASER = (220, 50, 50)
        self.C_TARGET = (0, 255, 255)
        self.C_SOURCE = (255, 220, 50)
        self.C_MIRROR = (255, 255, 255)
        self.C_SELECT = (255, 100, 255)

        self.walls = self.create_walls()

    def create_walls(self):
        walls = []
        # Boundaries
        walls.extend([(i, 0) for i in range(self.GRID_WIDTH)])
        walls.extend([(i, self.GRID_HEIGHT-1) for i in range(self.GRID_WIDTH)])
        walls.extend([(0, i) for i in range(self.GRID_HEIGHT)])
        walls.extend([(self.GRID_WIDTH-1, i) for i in range(self.GRID_HEIGHT)])
        # Internal Obstacles
        custom_walls = [
            (11, 2), (12, 1), (13, 2), 
            (4, 2), (4, 5),(4, 6), (4, 7), (4, 9), (4, 10),
            (5, 7), (6, 7), (7, 7), (8, 7),
            (8, 1), (8, 4), (8, 6), (8, 8),  
            (10, 5), (10, 10), (11, 1)
        ]
        walls.extend(custom_walls)
        walls.extend([(i, 3) for i in range(3, 10)])
        return walls

    def calculate_laser_path(self, mirrors, source, target_pos):
        path = []
        x, y = source['x'], source['y']
        direction = source['dir']
        visited = set()
        target_hit = False
        
        for _ in range(200): # Infinite loop protection
            if (x, y, direction) in visited: break
            visited.add((x, y, direction))
            
            dx = [1, 0, -1, 0][direction]
            dy = [0, 1, 0, -1][direction]
            nx, ny = x + dx, y + dy
            
            if nx < 0 or nx >= self.GRID_WIDTH or ny < 0 or ny >= self.GRID_HEIGHT or (nx, ny) in self.walls:
                break
            
            path.append(((x, y), (nx, ny)))
            
            if nx == target_pos['x'] and ny == target_pos['y']:
                target_hit = True
                break
            
            for m in mirrors:
                if m['x'] == nx and m['y'] == ny:
                    # Reflection logic based on mirror angle
                    if m['angle'] == 0:
                        direction = {0: 3, 1: 2, 2: 1, 3: 0}[direction]
                    else:
                        direction = {0: 1, 1: 0, 2: 3, 3: 2}[direction]
                    break
            
            x, y = nx, ny
            
        return path, target_hit

    def start(self):
        pygame.init()
        screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Module 1: Laser Optics System")
        clock = pygame.time.Clock()

        mirrors = []
        selected_mirror = None
        laser_source = {'x': 1, 'y': 2, 'dir': 0}
        target_pos = {'x': 12, 'y': 2}
        
        running = True
        game_result = False
        win_timer = 0

        while running:
            path, target_active = self.calculate_laser_path(mirrors, laser_source, target_pos)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    game_result = False
                
                if event.type == pygame.MOUSEBUTTONDOWN and not target_active:
                    gx, gy = event.pos[0] // self.GRID_SIZE, event.pos[1] // self.GRID_SIZE
                    
                    if event.button == 1: # Left Click
                        if 0 < gx < self.GRID_WIDTH-1 and 0 < gy < self.GRID_HEIGHT-1:
                            if (gx, gy) not in self.walls and (gx, gy) != (laser_source['x'], laser_source['y']) and (gx, gy) != (target_pos['x'], target_pos['y']):
                                found = False
                                for m in mirrors:
                                    if m['x'] == gx and m['y'] == gy:
                                        selected_mirror = m
                                        found = True
                                        break
                                if not found and len(mirrors) < self.MAX_MIRRORS:
                                    mirrors.append({'x': gx, 'y': gy, 'angle': 0})
                                    selected_mirror = mirrors[-1]
                    elif event.button == 3: # Right Click
                        mirrors = [m for m in mirrors if not (m['x'] == gx and m['y'] == gy)]
                        selected_mirror = None
                
                if event.type == pygame.KEYDOWN and not target_active:
                    if event.key == pygame.K_r and selected_mirror:
                        selected_mirror['angle'] = 1 - selected_mirror['angle']
                    elif event.key == pygame.K_c:
                        mirrors.clear()
                        selected_mirror = None
                    # Developer Debug Key (Win)
                    elif event.key == pygame.K_w:
                        running = False
                        game_result = True

            # Rendering
            screen.fill(self.C_BG)
            
            for x in range(self.GRID_WIDTH):
                for y in range(self.GRID_HEIGHT):
                    pygame.draw.rect(screen, self.C_GRID, (x * self.GRID_SIZE, y * self.GRID_SIZE, self.GRID_SIZE, self.GRID_SIZE), 1)
            
            for wx, wy in self.walls:
                pygame.draw.rect(screen, self.C_WALL, (wx * self.GRID_SIZE, wy * self.GRID_SIZE, self.GRID_SIZE, self.GRID_SIZE))
            
            lc = (laser_source['x'] * self.GRID_SIZE + 25, laser_source['y'] * self.GRID_SIZE + 25)
            pygame.draw.circle(screen, self.C_SOURCE, lc, 15)
            pygame.draw.circle(screen, self.C_LASER, lc, 12)
            
            tc = (target_pos['x'] * self.GRID_SIZE + 25, target_pos['y'] * self.GRID_SIZE + 25)
            if target_active:
                pygame.draw.circle(screen, self.C_TARGET, tc, 18)
                win_timer += 1
                if win_timer > 100: 
                    running = False
                    game_result = True
            else:
                pygame.draw.circle(screen, self.C_WALL, tc, 15)
                win_timer = 0
            
            for seg in path:
                p1 = (seg[0][0] * self.GRID_SIZE + 25, seg[0][1] * self.GRID_SIZE + 25)
                p2 = (seg[1][0] * self.GRID_SIZE + 25, seg[1][1] * self.GRID_SIZE + 25)
                pygame.draw.line(screen, self.C_LASER, p1, p2, 3)
            
            for m in mirrors:
                cx, cy = m['x'] * self.GRID_SIZE + 25, m['y'] * self.GRID_SIZE + 25
                if m == selected_mirror:
                    pygame.draw.rect(screen, self.C_SELECT, (m['x'] * self.GRID_SIZE + 5, m['y'] * self.GRID_SIZE + 5, 40, 40), 2)
                offset = 15
                if m['angle'] == 0:
                    pygame.draw.line(screen, self.C_MIRROR, (cx - offset, cy + offset), (cx + offset, cy - offset), 4)
                else:
                    pygame.draw.line(screen, self.C_MIRROR, (cx - offset, cy - offset), (cx + offset, cy + offset), 4)

            font = pygame.font.Font(None, 36)
            font_s = pygame.font.Font(None, 28)
            px = self.GRID_WIDTH * self.GRID_SIZE + 10
            screen.blit(font.render("Laser Optics System", True, self.C_MIRROR), (px, 30))
            screen.blit(font_s.render("L-Click: Add/Select", True, self.C_MIRROR), (px, 100))
            screen.blit(font_s.render("R: Rotate Mirror", True, self.C_MIRROR), (px, 140))
            screen.blit(font_s.render("R-Click: Remove", True, self.C_MIRROR), (px, 180))
            screen.blit(font_s.render(f"Mirrors Left: {self.MAX_MIRRORS - len(mirrors)}", True, self.C_MIRROR), (px, 280))

            if target_active:
                 screen.blit(font.render("SIGNAL LOCKED", True, (0,255,0)), (px, 350))

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()
        return game_result

# ==========================================
# MODULE 2: MPU6050 TILT ARENA
# ==========================================

class AdvancedMPUGame:
    def __init__(self, ser_main, ser_tilt):
        self.ser_main = ser_main 
        self.ser_tilt = ser_tilt 
        self.W, self.H = 1024, 768
        self.FPS = 60
        self.BALL_R = 12
        
        self.GAME_MAP = {
            "name": "THE OPEN ARENA",
            "start": (80, 80),
            "goal": pygame.Rect(self.W-120, self.H-120, 80, 80), 
            "walls": [
                pygame.Rect(0, 0, self.W, 30), pygame.Rect(0, self.H-30, self.W, 30),
                pygame.Rect(0, 0, 30, self.H), pygame.Rect(self.W-30, 0, 30, self.H),
                pygame.Rect(30, 200, 250, 20), pygame.Rect(400, 100, 20, 200),
                pygame.Rect(300, 400, 400, 20), pygame.Rect(150, 550, 20, 150),
                pygame.Rect(800, 250, 20, 250), pygame.Rect(550, 650, 250, 20),
            ],
            "moving_walls": [
                {"rect": pygame.Rect(450, 330, 60, 20), "origin": (450, 330), "dir": (1, 0), "speed": 0.005, "range": 150, "hit": False},
                {"rect": pygame.Rect(850, 400, 20, 60), "origin": (850, 400), "dir": (0, 1), "speed": 0.004, "range": 80, "hit": False},
                {"rect": pygame.Rect(200, 600, 80, 20), "origin": (200, 600), "dir": (1, 0), "speed": 0.006, "range": 100, "hit": False},
            ],
            "targets": [
                {"rect": pygame.Rect(300, 100, 40, 40), "hit": False},
                {"rect": pygame.Rect(900, 120, 40, 40), "hit": False},
                {"rect": pygame.Rect(80, 650, 40, 40), "hit": False},
                {"rect": pygame.Rect(600, 500, 40, 40), "hit": False}
            ]
        }
    
    def start(self):
        pygame.init()
        screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("Module 2: MPU6050 Arena")
        clock = pygame.time.Clock()
        font = pygame.font.SysFont("Consolas", 20)
        big_font = pygame.font.SysFont("Consolas", 60, bold=True)
        
        # Flush serial buffers
        if self.ser_tilt: self.ser_tilt.reset_input_buffer()
        if self.ser_main: self.ser_main.reset_input_buffer()

        ball = AdvBall(*self.GAME_MAP["start"], self.BALL_R, self.W, self.H)
        bullets = []
        confetti = []
        
        f_roll = f_pitch = 0.0
        shot_delay = 300
        last_shot_time = 0
        game_finished = False
        finish_timer = 0
        running = True
        game_result = False

        while running:
            t_ms = pygame.time.get_ticks()
            
            for e in pygame.event.get():
                if e.type == pygame.QUIT: running = False
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_r and not game_finished:
                         ball = AdvBall(*self.GAME_MAP["start"], self.BALL_R, self.W, self.H)
                         bullets.clear()
                         for t in self.GAME_MAP["targets"]: t["hit"] = False
                         for mw in self.GAME_MAP["moving_walls"]: mw["hit"] = False
                    # Developer Debug Key
                    if e.key == pygame.K_w:
                         running = False; game_result = True
                    if e.key == pygame.K_SPACE:
                        if t_ms - last_shot_time > shot_delay:
                            bullets.append(Bullet(ball.x, ball.y, ball.vx, ball.vy, self.W, self.H))
                            last_shot_time = t_ms

            # Check for BOOM signal from Main Arduino
            if self.ser_main and self.ser_main.in_waiting > 0:
                try: 
                    if "BOOM" in self.ser_main.read_all().decode('utf-8', errors='ignore'):
                        running = False; game_result = False
                except: pass

            # Read MPU6050 Sensor Data
            fired = False
            if self.ser_tilt and self.ser_tilt.is_open:
                try:
                    while self.ser_tilt.in_waiting > 0:
                        line = self.ser_tilt.readline().decode("utf-8", errors="ignore").strip()
                        parts = line.split(",")
                        if len(parts) >= 2:
                            f_roll = 0.8 * f_roll + 0.2 * float(parts[0])
                            f_pitch = 0.8 * f_pitch + 0.2 * float(parts[1])
                            if len(parts) > 2 and int(parts[2]) == 1: fired = True
                except: pass
            else:
                # Keyboard Fallback
                keys = pygame.key.get_pressed()
                if keys[pygame.K_RIGHT]: f_roll = 8
                elif keys[pygame.K_LEFT]: f_roll = -8
                else: f_roll = 0
                if keys[pygame.K_DOWN]: f_pitch = 8
                elif keys[pygame.K_UP]: f_pitch = -8
                else: f_pitch = 0

            if fired and (t_ms - last_shot_time > shot_delay):
                bullets.append(Bullet(ball.x, ball.y, ball.vx, ball.vy, self.W, self.H))
                last_shot_time = t_ms

            if not game_finished:
                roll = f_roll if abs(f_roll) > 1 else 0
                pitch = f_pitch if abs(f_pitch) > 1 else 0
                ball.update(roll, pitch)
                ball.handle_collision(self.GAME_MAP["walls"], self.GAME_MAP["moving_walls"])
                ball.clamp_position()

                for b in bullets[:]:
                    b.update()
                    if not b.alive: bullets.remove(b)
                    else:
                        # --- DÜZELTME BAŞLANGICI ---
                        # Merminin statik duvarlara çarpıp çarpmadığı kontrolü
                        wall_hit = False
                        for w in self.GAME_MAP["walls"]:
                            if w.collidepoint(b.x, b.y):
                                wall_hit = True
                                b.alive = False
                                # Duvara çarpma efekti (gri kıvılcım)
                                for _ in range(8): confetti.append(RotConfetti(b.x, b.y, (150, 150, 150)))
                                break
                        
                        if wall_hit:
                            bullets.remove(b)
                            continue # Mermi duvara çarptıysa diğer kontrolleri atla
                        # --- DÜZELTME BİTİŞİ ---

                        for t in self.GAME_MAP["targets"]:
                            if not t["hit"] and t["rect"].collidepoint(b.x, b.y):
                                t["hit"] = True; b.alive = False
                                for _ in range(30): confetti.append(RotConfetti(b.x, b.y, (255, 255, 0)))
                        
                        for mw in self.GAME_MAP["moving_walls"]:
                            if not mw["hit"] and mw["rect"].collidepoint(b.x, b.y):
                                mw["hit"] = True; b.alive = False
                                for _ in range(30): confetti.append(RotConfetti(b.x, b.y, (255, 50, 50)))

                for mw in self.GAME_MAP["moving_walls"]:
                    if not mw["hit"]:
                        offset = math.sin(t_ms * mw["speed"]) * mw["range"]
                        mw["rect"].x = mw["origin"][0] + mw["dir"][0] * offset
                        mw["rect"].y = mw["origin"][1] + mw["dir"][1] * offset
                        hit, _, _, _, _ = PhysicsEngine.advanced_circle_rect_collision(ball.x, ball.y, self.BALL_R, ball.vx, ball.vy, mw["rect"])
                        if hit:
                            ball = AdvBall(*self.GAME_MAP["start"], self.BALL_R, self.W, self.H)
                            for _ in range(30): confetti.append(RotConfetti(ball.x, ball.y, (255, 0, 0)))

                active_targets = [t["rect"] for t in self.GAME_MAP["targets"] if not t["hit"]]
                ball.handle_collision(active_targets, [])

                targets_left = any(not t["hit"] for t in self.GAME_MAP["targets"])
                if not targets_left and self.GAME_MAP["goal"].collidepoint(ball.x, ball.y):
                    game_finished = True
                    for _ in range(150): confetti.append(RotConfetti(ball.x, ball.y))

            # Rendering
            screen.fill((20, 20, 35))
            grid_color = (25, 25, 40)
            for i in range(0, self.W, 80): pygame.draw.line(screen, grid_color, (i,0), (i,self.H))
            for i in range(0, self.H, 80): pygame.draw.line(screen, grid_color, (0,i), (self.W,i))

            ball.draw(screen, game_finished)

            if not game_finished:
                targets_count = sum(1 for t in self.GAME_MAP["targets"] if not t["hit"])
                
                goal_color = (0, 255, 100) if targets_count == 0 else (120, 60, 60)
                pygame.draw.rect(screen, goal_color, self.GAME_MAP["goal"], 4 if targets_count == 0 else 0, border_radius=8)

                for w in self.GAME_MAP["walls"]: 
                    pygame.draw.rect(screen, (100, 100, 120), w.move(2,2), border_radius=6)
                    pygame.draw.rect(screen, (140, 140, 160), w, border_radius=6)
                    pygame.draw.rect(screen, (180, 180, 200), w, 2, border_radius=6)

                for t in self.GAME_MAP["targets"]:
                    if not t["hit"]: 
                        pygame.draw.rect(screen, (255, 255, 100), t["rect"], 3, border_radius=8)
                        pygame.draw.rect(screen, (255, 200, 0), t["rect"], border_radius=6)

                for mw in self.GAME_MAP["moving_walls"]:
                    if not mw["hit"]: 
                        pygame.draw.rect(screen, (255, 50, 50), mw["rect"], 2, border_radius=4)
                        pygame.draw.rect(screen, (200, 30, 30), mw["rect"], border_radius=4)
                
                for b in bullets: b.draw(screen)

            for c in confetti[:]:
                c.update()
                c.draw(screen)
                if c.life <= 0: confetti.remove(c)

            if not game_finished:
                targets_count = sum(1 for t in self.GAME_MAP["targets"] if not t["hit"])
                info = font.render(f"TARGETS: {len(self.GAME_MAP['targets']) - targets_count} / {len(self.GAME_MAP['targets'])}", True, (255, 255, 255))
                screen.blit(info, (20, 20))
                status = "SENSOR: ACTIVE" if (self.ser_tilt and self.ser_tilt.is_open) else "SENSOR: N/A (KEYBOARD)"
                screen.blit(font.render(status, True, (150, 150, 150)), (20, 50))

            if game_finished:
                finish_timer += 1
                msg1 = big_font.render("MISSION ACCOMPLISHED!", True, (100, 255, 100))
                screen.blit(msg1, (self.W//2 - msg1.get_width()//2, self.H//2 - 30))
                if finish_timer > 180:
                    running = False
                    game_result = True

            pygame.display.flip()
            clock.tick(self.FPS)
        
        pygame.quit()
        return game_result

# ==========================================
# MODULE 3: ENERGY STABILIZER
# ==========================================

class EnergyStabilizerGame:
    def __init__(self, ser_main):
        self.ser_main = ser_main
        self.WIDTH, self.HEIGHT = 800, 600
        # Initialize random parameters
        self.cpu = random.uniform(20, 80)
        self.cooling = random.uniform(20, 80)
        self.battery = random.uniform(20, 80)
        
        self.cpu_v = 0.0
        self.cooling_v = 0.0
        self.battery_v = 0.0
        
        self.TARGET_MIN = 40
        self.TARGET_MAX = 50
        
        self.player_interacted = False
        self.system_locked = False
        self.color_revealed = False

    def clamp(self, v):
        return max(0, min(100, v))

    def stable(self):
        return (self.TARGET_MIN <= self.cpu <= self.TARGET_MAX and 
                self.TARGET_MIN <= self.cooling <= self.TARGET_MAX and 
                self.TARGET_MIN <= self.battery <= self.TARGET_MAX)

    def drift(self):
        self.cpu_v     += random.uniform(-0.10, 0.11)
        self.cooling_v += random.uniform(-0.11, 0.10)
        self.battery_v += random.uniform(-0.10, 0.11)

    def coupling(self):
        self.cpu_v     += (self.battery - 50) * 0.005
        self.cooling_v -= (self.cpu - 50) * 0.006
        self.battery_v -= abs(self.cpu_v) * 0.014

    def physics(self):
        self.cpu     += self.cpu_v
        self.cooling += self.cooling_v
        self.battery += self.battery_v

        self.cpu_v     *= 0.88
        self.cooling_v *= 0.88
        self.battery_v *= 0.88

    def act_cpu(self, delta):
        self.player_interacted = True
        self.cpu_v     += delta
        self.cooling_v -= delta * 0.42
        self.battery_v -= abs(delta) * 0.26

    def act_cooling(self, delta):
        self.player_interacted = True
        self.cooling_v += delta
        self.cpu_v     -= delta * 0.46
        self.battery_v -= abs(delta) * 0.23

    def act_battery(self, delta):
        self.player_interacted = True
        self.battery_v += delta
        self.cpu_v     += delta * 0.22
        self.cooling_v += delta * 0.18

    def draw_bar(self, screen, font, x, y, value, label):
        color = (0, 200, 0) if self.TARGET_MIN <= value <= self.TARGET_MAX else (220, 60, 60)
        pygame.draw.rect(screen, (60, 60, 60), (x, y, 300, 26))
        pygame.draw.rect(screen, color, (x, y, value * 3, 26))
        txt = font.render(f"{label}: {value:.1f}", True, (230, 230, 230))
        screen.blit(txt, (x, y - 22))

    def start(self):
        pygame.init()
        screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Module 3: Energy Stabilizer")
        
        font = pygame.font.SysFont("consolas", 20)
        big_font = pygame.font.SysFont("consolas", 36)
        clock = pygame.time.Clock()
        
        DRIFT_EVENT = pygame.USEREVENT + 1
        pygame.time.set_timer(DRIFT_EVENT, 1400)
        
        running = True
        game_result = False
        
        win_timer = 0
        
        if self.ser_main: self.ser_main.reset_input_buffer()

        while running:
            screen.fill((18, 18, 18))
            
            # Check for Boom signal
            if self.ser_main and self.ser_main.in_waiting > 0:
                try:
                    lines = self.ser_main.read_all().decode('utf-8', errors='ignore')
                    if "BOOM" in lines:
                        running = False
                        game_result = False
                except: pass

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    game_result = False
                
                if event.type == DRIFT_EVENT and not self.system_locked:
                    self.drift()
                    self.coupling()
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                        game_result = False
                    
                    # Developer Debug Key (F1)
                    if event.key == pygame.K_F1: 
                        self.color_revealed = True
                        self.system_locked = True
                        win_timer = 110 
                    
                    if not self.system_locked:
                        if event.key == pygame.K_q: self.act_cpu(+1.9)
                        if event.key == pygame.K_a: self.act_cpu(-1.9)
                        if event.key == pygame.K_w: self.act_cooling(+1.7)
                        if event.key == pygame.K_s: self.act_cooling(-1.7)
                        if event.key == pygame.K_e: self.act_battery(+2.3)
                        if event.key == pygame.K_d: self.act_battery(-2.3)
                        
                        if event.key == pygame.K_SPACE and self.stable() and self.player_interacted:
                            self.color_revealed = True
                            self.system_locked = True

            if not self.system_locked:
                self.physics()

            self.cpu = self.clamp(self.cpu)
            self.cooling = self.clamp(self.cooling)
            self.battery = self.clamp(self.battery)

            self.draw_bar(screen, font, 80, 150, self.cpu, "CPU LOAD (Q/A)")
            self.draw_bar(screen, font, 80, 210, self.cooling, "COOLING (W/S)")
            self.draw_bar(screen, font, 80, 270, self.battery, "BATTERY (E/D)")

            screen.blit(font.render("Target Range: 40 - 50", True, (170,170,170)), (80, 90))
            
            if self.stable() and self.player_interacted and not self.color_revealed:
                screen.blit(font.render("SYSTEM STABLE - PRESS SPACE", True, (0,220,0)), (450, 220))

            if self.color_revealed:
                screen.blit(big_font.render("SYSTEM UNLOCKED", True, (0,255,140)), (410, 220))
                screen.blit(font.render("SYSTEM LOCKED", True, (120,120,120)), (470, 260))
                
                win_timer += 1
                if win_timer > 120: 
                    running = False
                    game_result = True

            pygame.display.flip()
            clock.tick(60)
        
        pygame.quit()
        return game_result

# ==========================================
# MODULE 4: MOTION DETECTION (RED LIGHT GREEN LIGHT)
# ==========================================

class SquidGame:
    def __init__(self):
        self.TOTAL_ROUNDS = 3
        self.MOTION_THRESHOLD = 1_800_000
        self.GREEN_TIMES = [5, 4.5, 4, 3.5, 3, 2.8]
        self.RED_TIMES   = [3.5, 4.5, 5.5, 6.5, 7.5, 8.5]
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def beep_win(self, freq, duration_sec):
        if winsound:
            winsound.Beep(freq, int(duration_sec * 1000))
        else:
            time.sleep(duration_sec)

    def flash(self, frame, color):
        overlay = frame.copy()
        cv2.rectangle(overlay, (0,0), frame.shape[1:], color, -1)
        return cv2.addWeighted(overlay, 0.18, frame, 0.82, 0)

    def add_noise(self, frame, intensity=18):
        noise = np.random.randint(0, intensity, frame.shape, dtype='uint8')
        return cv2.add(frame, noise)

    def start(self):
        # Attempt to access main camera (0), then external (1)
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            cap = cv2.VideoCapture(1)
            if not cap.isOpened():
                # Safe fallback if no camera is detected
                answer = messagebox.askyesno("Camera Error", "Optical Sensor Not Found. Bypass level verification?")
                return answer

        win_game = False

        for current_round in range(1, self.TOTAL_ROUNDS + 1):
            # --- GREEN LIGHT ---
            self.beep_win(600, 0.3)
            green_start = time.time()
            prev_gray = None

            while time.time() - green_start < self.GREEN_TIMES[current_round - 1]:
                ret, frame = cap.read()
                if not ret: break
                frame = cv2.flip(frame, 1)

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (31, 31), 0)
                prev_gray = gray.copy()

                frame = self.flash(frame, (0, 80, 0))
                cv2.rectangle(frame, (20,20), (620,460), (0,255,0), 6)
                cv2.putText(frame, f"ROUND {current_round} - GREEN (Move)", (30,45), self.font, 0.8, (0,255,0), 2)
                
                # Debug Info
                cv2.putText(frame, "[q] BYPASS [ESC] EXIT", (30, 450), self.font, 0.6, (255,255,255), 1)
                
                cv2.imshow("Red Light Green Light", frame)
                key = cv2.waitKey(1)
                if key == 27: # ESC
                    cap.release(); cv2.destroyAllWindows(); return False
                elif key == ord('q'): # Debug Bypass
                    cap.release(); cv2.destroyAllWindows(); return True

            # --- RED LIGHT ---
            self.beep_win(1200, 0.4)
            red_start = time.time()

            while time.time() - red_start < self.RED_TIMES[current_round - 1]:
                ret, frame = cap.read()
                if not ret: break
                frame = cv2.flip(frame, 1)

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (31, 31), 0)

                if prev_gray is not None:
                    diff = cv2.absdiff(prev_gray, gray)
                    _, thresh = cv2.threshold(diff, 35, 255, cv2.THRESH_BINARY)
                    motion = np.sum(thresh)
                else: motion = 0

                frame = self.add_noise(frame)
                frame = self.flash(frame, (80, 0, 0))
                cv2.rectangle(frame, (20,20), (620,460), (0,0,255), 8)
                cv2.putText(frame, f"ROUND {current_round} - RED (Stop)", (30,45), self.font, 0.8, (0,0,255), 2)

                if motion > self.MOTION_THRESHOLD:
                    self.beep_win(300, 1.4)
                    cv2.putText(frame, "MOTION DETECTED! ELIMINATED", (100,260), self.font, 1.0, (0,0,255), 4)
                    cv2.imshow("Red Light Green Light", frame)
                    cv2.waitKey(2000)
                    cap.release(); cv2.destroyAllWindows()
                    return False 

                cv2.imshow("Red Light Green Light", frame)
                key = cv2.waitKey(1)
                if key == 27:
                    cap.release(); cv2.destroyAllWindows(); return False
                elif key == ord('q'):
                    cap.release(); cv2.destroyAllWindows(); return True

        # Victory Sequence
        self.beep_win(500, 0.3)
        frame = np.zeros((480,640,3), dtype=np.uint8)
        cv2.putText(frame, "SURVIVED!", (50,240), self.font, 1.0, (0,255,255), 3)
        cv2.imshow("Red Light Green Light", frame)
        cv2.waitKey(3000)

        cap.release()
        cv2.destroyAllWindows()
        return True

# ==========================================
# MAIN LAUNCHER SYSTEM
# ==========================================

class GameLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Defuse the Bomb (Hybrid System)")
        self.root.geometry("480x650")

        self.ser_main = None
        self.ser_tilt = None
        
        self.game_running = False
        self.waiting_for_wire_cut = False 
        self.stop_thread = False
        
        # Wire Mapping for Randomization (0:Red, 1:Blue, 2:Green, 3:Yellow)
        self.wire_map = [0, 1, 2, 3] 

        self.connect_systems()
        
        if self.ser_main:
            self.thread = threading.Thread(target=self.serial_listener_main, daemon=True)
            self.thread.start()

        self.current_level = 0
        self.butonlar = []
        self.create_interface()

    def connect_systems(self):
        try:
            self.ser_main = serial.Serial(PORT_MAIN, BAUD_MAIN, timeout=1)
            print(f"SYSTEM: Main Control Unit ({PORT_MAIN}) CONNECTED.")
        except Exception as e: print(f"ERROR: Main Unit ({PORT_MAIN}) not found! -> {e}")

        try:
            self.ser_tilt = serial.Serial(PORT_TILT, BAUD_TILT, timeout=1)
            print(f"SYSTEM: Sensor Unit ({PORT_TILT}) CONNECTED.")
        except Exception as e: print(f"ERROR: Sensor Unit ({PORT_TILT}) not found! Keyboard fallback active.")

    def serial_listener_main(self):
        """Listens for critical signals from the Main Arduino Unit."""
        while not self.stop_thread and self.ser_main and self.ser_main.is_open:
            try:
                if self.ser_main.in_waiting > 0:
                    line = self.ser_main.readline().decode('utf-8', errors='ignore').strip()
                    if len(line) > 0:
                        print(f"[ARDUINO]: {line}") 
                        
                        if "BOOM" in line:
                            self.root.after(0, lambda: messagebox.showerror("GAME OVER", "BOOM! Explosion detected."))
                            self.root.after(0, self.reset_game_gui)
                        
                        elif "YOU WON" in line:
                            self.root.after(0, lambda: messagebox.showinfo("VICTORY", "Bomb Successfully Defused!"))
                            self.root.after(0, self.reset_game_gui)
                        
                        elif "WIRE_CORRECT" in line:
                            self.waiting_for_wire_cut = False
                            
                            # If final wire (Squid Game level) is cut, start Simon
                            if self.current_level == 3:
                                self.arduino_veri_gonder('W') # Start Simon Sequence
                                self.root.after(0, lambda: messagebox.showinfo("SIMON SAYS", "Wire Cut! WARNING: Simon Says Mode Activated on Device."))
                            else:
                                self.root.after(0, lambda: messagebox.showinfo("SYSTEM", "Correct wire cut! Unlocking next stage..."))
                                self.root.after(0, self.next_level_unlock)

                        elif "TIME:" in line:
                            parts = line.split(":")
                            if len(parts) > 1:
                                self.root.after(0, lambda t=parts[1].strip(): self.lbl_timer.config(text=f"BOMB TIMER: {t}"))
            except Exception as e: print(f"Serial Read Error: {e}")
            time.sleep(0.1)

    def create_interface(self):
        tk.Label(self.root, text="Defuse the Bomb", font=("Arial", 20, "bold")).pack(pady=10)
        self.lbl_timer = tk.Label(self.root, text="WAITING FOR START...", font=("Courier New", 16, "bold"), fg="red")
        self.lbl_timer.pack(pady=5)
        self.btn_start = tk.Button(self.root, text="START MISSION ('S')", font=("Arial", 12, "bold"), bg="red", fg="white", command=self.mission_start)
        self.btn_start.pack(pady=10)

        self.game_names = [
            "1. Laser Mirrors", 
            "2. MPU6050 Arena", 
            "3. Energy Stabilizer", 
            "4. Red Light Green Light" 
        ]

        for i, name in enumerate(self.game_names):
            btn = tk.Button(self.root, text=name, font=("Arial", 12), width=35, height=2, command=lambda idx=i: self.oyunu_baslat(idx))
            btn.pack(pady=5)
            self.butonlar.append(btn)
        
        for btn in self.butonlar: btn.config(state="disabled")

    def mission_start(self):
        # Randomize wire sequence at start
        self.wire_map = [0, 1, 2, 3]
        random.shuffle(self.wire_map)
        print(f"DEBUG: Wire Sequence (0:R, 1:B, 2:G, 3:Y) -> {self.wire_map}")
        
        self.arduino_veri_gonder('S')
        self.game_running = True
        self.current_level = 0
        self.btn_start.config(state="disabled")
        self.butonlari_guncelle()

    def reset_game_gui(self):
        self.game_running = False
        self.btn_start.config(state="normal")
        self.lbl_timer.config(text="GAME OVER / RESET")
        for btn in self.butonlar: btn.config(state="disabled", bg="#f0f0f0")

    def next_level_unlock(self):
        self.current_level += 1
        self.butonlari_guncelle()

    def butonlari_guncelle(self):
        if not self.game_running: return
        if self.waiting_for_wire_cut:
            for btn in self.butonlar: btn.config(state="disabled", bg="orange", text="WAITING FOR WIRE CUT...")
            return

        for i, btn in enumerate(self.butonlar):
            btn.config(text=self.game_names[i]) 
            if i < self.current_level: btn.config(state="disabled", bg="#4CAF50", fg="white") 
            elif i == self.current_level: btn.config(state="normal", bg="#2196F3", fg="white")   
            else: btn.config(state="disabled", bg="#9E9E9E", fg="black") 

    def arduino_veri_gonder(self, data):
        if self.ser_main and self.ser_main.is_open:
            try: self.ser_main.write(data.encode())
            except Exception as e: print(f"Transmission Error: {e}")

    def oyunu_baslat(self, game_index):
        if self.waiting_for_wire_cut:
            messagebox.showwarning("Wait", "Wait! Cut the correct wire on the device first!")
            return

        self.root.withdraw()
        result = False

        if game_index == 0:
            game = LaserMirrorGame()
            result = game.start()
        
        elif game_index == 1:
            game = AdvancedMPUGame(self.ser_main, self.ser_tilt)
            result = game.start()

        elif game_index == 2:
            game = EnergyStabilizerGame(self.ser_main)
            result = game.start()
        
        elif game_index == 3:
            game = SquidGame()
            result = game.start()

        self.root.deiconify()
        self.process_game_result(game_index, result)

    def process_game_result(self, game_index, success):
        if success:
            print(f"Level {game_index} Complete.")
            
            # Select target wire from randomized map
            target_wire = self.wire_map[game_index]
            
            # Send target to Arduino
            self.arduino_veri_gonder(str(target_wire)) 
            
            color_names = ["RED", "BLUE", "GREEN", "YELLOW"]
            cut_color = color_names[target_wire]
            
            msg = f"PC Lock Disengaged!\nCut the {cut_color} wire on the device now!"
            messagebox.showinfo("ALERT", msg)
            
            self.waiting_for_wire_cut = True
            self.butonlari_guncelle()
            
        else:
            print("Mission Failed -> PANIC")
            self.arduino_veri_gonder('P') 
            messagebox.showerror("CRITICAL ERROR", "Mistake made! Penalty applied or explosion triggered.")

if __name__ == "__main__":
    root = tk.Tk()
    app = GameLauncher(root)
    root.mainloop()