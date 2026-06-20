import pygame as pg
import random
from collections import deque
from save_utils import load_save, save_progress

CELL_SIZE = 35
REQUESTED_COLS = 16
REQUESTED_ROWS = 16

COLS = REQUESTED_COLS if REQUESTED_COLS % 2 == 1 else REQUESTED_COLS - 1
ROWS = REQUESTED_ROWS if REQUESTED_ROWS % 2 == 1 else REQUESTED_ROWS - 1

WALL = 1
PATH = 0


def generate_perfect_maze(cols=COLS, rows=ROWS, seed=None):
    if seed is not None:
        random.seed(seed)

    maze = [[WALL for _ in range(cols)] for _ in range(rows)]

    def in_bounds(x, y):
        return 0 <= x < cols and 0 <= y < rows

    start_x, start_y = 1, 1
    maze[start_y][start_x] = PATH
    stack = [(start_x, start_y)]
    dirs = [(2, 0), (-2, 0), (0, 2), (0, -2)]

    while stack:
        x, y = stack[-1]
        neighbors = []
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if in_bounds(nx, ny) and maze[ny][nx] == WALL:
                neighbors.append((nx, ny, dx, dy))
        if neighbors:
            nx, ny, dx, dy = random.choice(neighbors)
            wall_x, wall_y = x + dx // 2, y + dy // 2
            maze[wall_y][wall_x] = PATH
            maze[ny][nx] = PATH
            stack.append((nx, ny))
        else:
            stack.pop()

    # Border walls
    for x in range(cols):
        maze[0][x] = WALL
        maze[rows - 1][x] = WALL
    for y in range(rows):
        maze[y][0] = WALL
        maze[y][cols - 1] = WALL

    return maze


def maze_to_wall_rects(maze, cell_size=CELL_SIZE, screen_size=(1024, 768)):
    rows = len(maze)
    cols = len(maze[0])
    maze_px_w = cols * cell_size
    maze_px_h = rows * cell_size
    screen_w, screen_h = screen_size

    offset_x = (screen_w - maze_px_w) // 2
    offset_y = (screen_h - maze_px_h) // 2

    wall_rects = []
    for y, row in enumerate(maze):
        for x, val in enumerate(row):
            if val == WALL:
                rect = pg.Rect(offset_x + x * cell_size,
                               offset_y + y * cell_size,
                               cell_size, cell_size)
                wall_rects.append(rect)
    return wall_rects, offset_x, offset_y


def bfs_next_step(start, goal, maze, shield_blocks, offset_x, offset_y):
    sx, sy = start
    gx, gy = goal
    if not (0 <= sx < COLS and 0 <= sy < ROWS):
        return start
    if not (0 <= gx < COLS and 0 <= gy < ROWS):
        return start

    queue = deque([start])
    came_from = {start: None}
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    while queue:
        x, y = queue.popleft()
        if (x, y) == (gx, gy):
            break
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < COLS and 0 <= ny < ROWS):
                continue
            if maze[ny][nx] == WALL:
                continue
            # if shields are "blocking", skip those cells
            if shield_blocks:
                cell_rect = pg.Rect(offset_x + nx * CELL_SIZE,
                                    offset_y + ny * CELL_SIZE,
                                    CELL_SIZE, CELL_SIZE)
                if any(cell_rect.colliderect(s) for s in shield_blocks):
                    continue
            if (nx, ny) not in came_from:
                came_from[(nx, ny)] = (x, y)
                queue.append((nx, ny))

    if (gx, gy) not in came_from:
        return start  # no path
    cur = (gx, gy)
    while came_from[cur] != start and came_from[cur] is not None:
        cur = came_from[cur]
    return cur


# Maze + goal
_maze = generate_perfect_maze()
_goal_cell = (len(_maze[0]) - 2, len(_maze) - 2)


def run_level(screen, cursor_img, clock):
    paused = False
    pause_font = pg.font.SysFont(None, 60)
    pause_small_font = pg.font.SysFont(None, 40)
    cursor_size = 22
    HITBOX_SIZE = 19
    screen_w, screen_h = screen.get_size()

    wall_rects, offset_x, offset_y = maze_to_wall_rects(
        _maze, cell_size=CELL_SIZE, screen_size=(screen_w, screen_h)
    )

    # desired spawn; will snap to a PATH cell if needed
    desired_start_px = (402, 200)
    goal_px = (offset_x + _goal_cell[0] * CELL_SIZE + CELL_SIZE // 2,
               offset_y + _goal_cell[1] * CELL_SIZE + CELL_SIZE // 2)

    # Load save and difficulty/hearts
    data = load_save()
    hearts_setting = data.get("hearts", "default")
    difficulty = data.get("difficulty", None)
    # per-level default health
    LEVEL_DEFAULT_HEALTH = 4
    if isinstance(hearts_setting, int):
        health = int(hearts_setting)
    else:
        health = LEVEL_DEFAULT_HEALTH

    # Player setup
    x, y = desired_start_px
    dragging = False
    drag_lockout = False
    goal_radius = 10

    # Heart image fallback
    try:
        heart_img = pg.image.load("hart.png").convert_alpha()
        heart_img = pg.transform.scale(heart_img, (32, 32))
    except Exception:
        heart_img = pg.Surface((32, 32), pg.SRCALPHA)
        pg.draw.polygon(heart_img, (200, 20, 20), [(16, 0), (32, 12), (16, 32), (0, 12)])

    invincibility_time = 200
    last_hit_time = -invincibility_time

    # Bounds rect for instant death
    maze_rect = pg.Rect(offset_x, offset_y, COLS * CELL_SIZE, ROWS * CELL_SIZE)

    # Weapon bar
    weapon_max = 300
    weapon_energy = weapon_max
    weapon_deplete_rate = 3  # per frame

    # Spider setup
    try:
        spider_img = pg.image.load("spider.png").convert_alpha()
        spider_img = pg.transform.scale(spider_img, (20, 20))
    except Exception:
        # fallback: small red square
        spider_img = pg.Surface((20, 20))
        spider_img.fill((150, 0, 0))
    spider_x, spider_y = float(goal_px[0]), float(goal_px[1])
    spider_speed = 1.0
    path_timer = 0
    path_interval = 250  # ms

    # Spider FSM
    SPIDER_HUNT = 0
    SPIDER_RETREAT = 1
    spider_state = SPIDER_HUNT
    # next_target in world coords
    next_target = (spider_x, spider_y)

    # Retreat timing
    RETREAT_BURST_MS = 5400
    retreat_until = 0

    def cell_center(cx, cy):
        return (offset_x + cx * CELL_SIZE + CELL_SIZE // 2,
                offset_y + cy * CELL_SIZE + CELL_SIZE // 2)

    def world_to_cell(px, py):
        return (int((px - offset_x) // CELL_SIZE),
                int((py - offset_y) // CELL_SIZE))

    def pick_away_neighbor(spider_cx, spider_cy, player_cx, player_cy):
        best = (spider_cx, spider_cy)
        best_d2 = -1
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = spider_cx + dx, spider_cy + dy
            if 0 <= nx < COLS and 0 <= ny < ROWS and _maze[ny][nx] == PATH:
                d2 = (nx - player_cx) ** 2 + (ny - player_cy) ** 2
                if d2 > best_d2:
                    best_d2 = d2
                    best = (nx, ny)
        return best

    def is_safe_at(cx, cy):
        cr = pg.Rect(cx - cursor_size // 2, cy - cursor_size // 2, cursor_size, cursor_size)
        if not maze_rect.contains(cr):
            return False
        for wr in wall_rects:
            if wr.colliderect(cr):
                return False
        return True

    def find_nearest_safe_cell(from_x, from_y):
        candidates = []
        for r in range(ROWS):
            for c in range(COLS):
                if _maze[r][c] == PATH:
                    cx = offset_x + c * CELL_SIZE + CELL_SIZE // 2
                    cy = offset_y + r * CELL_SIZE + CELL_SIZE // 2
                    dist = (cx - from_x) ** 2 + (cy - from_y) ** 2
                    candidates.append((dist, cx, cy))
        candidates.sort(key=lambda t: t[0])
        for _, cx, cy in candidates:
            if is_safe_at(cx, cy):
                return cx, cy
        # center fallback
        return (offset_x + CELL_SIZE * (COLS // 2) + CELL_SIZE // 2,
                offset_y + CELL_SIZE * (ROWS // 2) + CELL_SIZE // 2)

    # Snap start to safe path if needed
    start_rect = pg.Rect(x - cursor_size // 2, y - cursor_size // 2, cursor_size, cursor_size)
    if not maze_rect.contains(start_rect) or not is_safe_at(x, y):
        x, y = find_nearest_safe_cell(x, y)
        try:
            pg.mouse.set_pos((int(x), int(y)))
        except Exception:
            pass

    # main loop
    while True:
        screen.fill((30, 30, 30))
        current_time = pg.time.get_ticks()

        for event in pg.event.get():
            if event.type == pg.QUIT:
                return "QUIT"

            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    paused = not paused

        if paused:
            # Dark overlay
            overlay = pg.Surface(screen.get_size(), pg.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))

            screen_w, screen_h = screen.get_size()

            # Title
            title_surf = pause_font.render("Paused", True, (255, 255, 255))
            screen.blit(title_surf, (screen_w//2 - title_surf.get_width()//2, 200))

            # Buttons
            btn_w, btn_h = 300, 60
            btn_x = screen_w//2 - btn_w//2

            resume_rect = pg.Rect(btn_x, 300, btn_w, btn_h)
            restart_rect = pg.Rect(btn_x, 380, btn_w, btn_h)
            menu_rect = pg.Rect(btn_x, 460, btn_w, btn_h)

            mx, my = pg.mouse.get_pos()
            clicked = pg.mouse.get_pressed()[0]

            def draw_button(rect, text):
                color = (255, 60, 60) if rect.collidepoint(mx, my) else (200, 30, 30)
                pg.draw.rect(screen, color, rect, border_radius=8)
                text_surf = pause_small_font.render(text, True, (255,255,255))
                screen.blit(text_surf,
                            (rect.centerx - text_surf.get_width()//2,
                            rect.centery - text_surf.get_height()//2))

            draw_button(resume_rect, "Resume")
            draw_button(restart_rect, "Restart Level")
            draw_button(menu_rect, "Return to Main Menu")

            if clicked:
                if resume_rect.collidepoint(mx, my):
                    paused = False
                elif restart_rect.collidepoint(mx, my):
                    return "RETRY"
                elif menu_rect.collidepoint(mx, my):
                    return "BACK_TO_MENU"

            pg.display.flip()
            clock.tick(60)
            continue

        buttons = pg.mouse.get_pressed()
        mx, my = pg.mouse.get_pos()
        mouse_rect = pg.Rect(mx - 1, my - 1, 2, 2)
        char_rect = pg.Rect(x - HITBOX_SIZE // 2, y - HITBOX_SIZE // 2, HITBOX_SIZE, HITBOX_SIZE)

        # Dragging
        if buttons[0]:
            if not dragging and not drag_lockout and char_rect.colliderect(mouse_rect):
                dragging = True
        else:
            dragging = False
            drag_lockout = False

        if dragging:
            x, y = mx, my

        char_rect = pg.Rect(x - HITBOX_SIZE // 2, y - HITBOX_SIZE // 2, HITBOX_SIZE, HITBOX_SIZE)

        # Instant death if outside -> use global hearts if present
        if not maze_rect.contains(char_rect):
            if isinstance(data.get("hearts", "default"), int):
                if current_time - last_hit_time >= invincibility_time:
                    data["hearts"] = int(data["hearts"]) - 1
                    last_hit_time = current_time
                    save_progress(data)
                    health = data["hearts"]
                    if data["hearts"] <= 0:
                        if data.get("difficulty") == "hard":
                            return "BACK_TO_MENU_HARD_FAIL"
                        else:
                            return "RETRY"
                    x, y = find_nearest_safe_cell(x, y)
                    try:
                        pg.mouse.set_pos((int(x), int(y)))
                    except Exception:
                        pass
                    dragging = False
                    drag_lockout = True
            else:
                return "RETRY"

        # Draw maze
        for w in wall_rects:
            pg.draw.rect(screen, (200, 0, 2), w)

        # Weapon (shield) usage - RMB, per-level resource
        weapon_active = False
        shield_blocks = []
        if buttons[2] and weapon_energy > 0:
            weapon_active = True
            weapon_energy = max(0, weapon_energy - weapon_deplete_rate)
            px = int((x - offset_x) // CELL_SIZE)
            py = int((y - offset_y) // CELL_SIZE)
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                cx, cy = px + dx, py + dy
                if 0 <= cx < COLS and 0 <= cy < ROWS and _maze[cy][cx] == PATH:
                    rect = pg.Rect(offset_x + cx * CELL_SIZE,
                                   offset_y + cy * CELL_SIZE,
                                   CELL_SIZE, CELL_SIZE)
                    shield_blocks.append(rect)
                    pg.draw.rect(screen, (0, 200, 200), rect)

        # Wall collision -> lose health (respect invincibility)
        for w in wall_rects:
            if w.colliderect(char_rect):
                if current_time - last_hit_time >= invincibility_time:
                    # hearts-mode (global)
                    if isinstance(data.get("hearts", "default"), int):
                        data["hearts"] = int(data["hearts"]) - 1
                        last_hit_time = current_time
                        save_progress(data)
                        health = data["hearts"]
                        if data["hearts"] <= 0:
                            if data.get("difficulty") == "hard":
                                return "BACK_TO_MENU_HARD_FAIL"
                            else:
                                return "RETRY"
                    else:
                        health -= 1
                        last_hit_time = current_time
                        if health <= 0:
                            return "RETRY"
                    x, y = find_nearest_safe_cell(x, y)
                    try:
                        pg.mouse.set_pos((int(x), int(y)))
                    except Exception:
                        pass
                    dragging = False
                    drag_lockout = True
                break

        # Spider logic & shield interaction
        spider_rect = pg.Rect(int(spider_x) - 10, int(spider_y) - 10, 20, 20)

        touching_shield = weapon_active and any(spider_rect.colliderect(s) for s in shield_blocks)
        if touching_shield:
            spider_state = SPIDER_RETREAT
            retreat_until = current_time + RETREAT_BURST_MS

        # Update path target per state
        if spider_state == SPIDER_HUNT:
            if current_time - path_timer > path_interval:
                spider_cx, spider_cy = world_to_cell(spider_x, spider_y)
                player_cx, player_cy = world_to_cell(x, y)
                # when hunting ignore shield blocks (we want spider to path to player)
                next_cx, next_cy = bfs_next_step(
                    (spider_cx, spider_cy), (player_cx, player_cy),
                    _maze, [], offset_x, offset_y
                )
                next_target = cell_center(next_cx, next_cy)
                path_timer = current_time

        elif spider_state == SPIDER_RETREAT:
            if current_time >= retreat_until:
                spider_state = SPIDER_HUNT
            else:
                if current_time - path_timer > path_interval:
                    spider_cx, spider_cy = world_to_cell(spider_x, spider_y)
                    player_cx, player_cy = world_to_cell(x, y)
                    away_cx, away_cy = pick_away_neighbor(spider_cx, spider_cy, player_cx, player_cy)
                    next_target = cell_center(away_cx, away_cy)
                    path_timer = current_time

        # Move spider toward its current target
        dx = next_target[0] - spider_x
        dy = next_target[1] - spider_y
        dist = max(1.0, (dx * dx + dy * dy) ** 0.5)
        spider_x += (dx / dist) * spider_speed
        spider_y += (dy / dist) * spider_speed

        # Draw spider
        screen.blit(spider_img, (int(spider_x) - 10, int(spider_y) - 10))

        # Spider damages player (BUT NOT if weapon is active/shield covers spider)
        spider_rect = pg.Rect(int(spider_x) - 10, int(spider_y) - 10, 20, 20)
        shield_blocks_for_collision = shield_blocks if weapon_active else []
        spider_shielded = any(spider_rect.colliderect(s) for s in shield_blocks_for_collision)

        if spider_rect.colliderect(char_rect) and not spider_shielded:
            if current_time - last_hit_time >= invincibility_time:
                if isinstance(data.get("hearts", "default"), int):
                    data["hearts"] = int(data["hearts"]) - 1
                    last_hit_time = current_time
                    save_progress(data)
                    health = data["hearts"]
                    if data["hearts"] <= 0:
                        if data.get("difficulty") == "hard":
                            return "BACK_TO_MENU_HARD_FAIL"
                        else:
                            return "RETRY"
                else:
                    health -= 1
                    last_hit_time = current_time
                    if health <= 0:
                        return "RETRY"
                x, y = find_nearest_safe_cell(x, y)
                try:
                    pg.mouse.set_pos((int(x), int(y)))
                except Exception:
                    pass
                dragging = False
                drag_lockout = True

        # Goal
        pg.draw.circle(screen, (50, 150, 255), goal_px, goal_radius)
        if (x - goal_px[0]) ** 2 + (y - goal_px[1]) ** 2 <= goal_radius ** 2:
            return "NEXT"

        # Hearts HUD (global hearts if present else per-level)
        hearts_to_draw = int(data["hearts"]) if isinstance(data.get("hearts", "default"), int) else health
        for i in range(max(0, hearts_to_draw)):
            screen.blit(heart_img, (10 + i * 40, 10))

        # Weapon bar + label
        bar_w, bar_h = 200, 20
        pg.draw.rect(screen, (100, 0, 0), (10, 50, bar_w, bar_h))
        fill_w = int((weapon_energy / weapon_max) * bar_w)
        pg.draw.rect(screen, (0, 200, 200), (10, 50, fill_w, bar_h))
        font = pg.font.SysFont(None, 28)
        txt = font.render("Shield", True, (255, 255, 255))
        screen.blit(txt, (10, 80))

        # Player (invincibility flash)
        if current_time - last_hit_time < invincibility_time:
            if (current_time // 100) % 2 == 0:
                screen.blit(cursor_img, (x - cursor_size // 2, y - cursor_size // 2))
        else:
            screen.blit(cursor_img, (x - cursor_size // 2, y - cursor_size // 2))

        pg.display.flip()
        clock.tick(60)
