import pygame as pg
import random
from collections import deque
from save_utils import load_save, save_progress

CELL_SIZE = 35
REQUESTED_COLS = 16
REQUESTED_ROWS = 16
COLS = REQUESTED_COLS if REQUESTED_COLS % 2 == 1 else REQUESTED_COLS - 1
ROWS = REQUESTED_ROWS if REQUESTED_ROWS % 2 == 1 else REQUESTED_ROWS - 1

WALL, PATH = 1, 0

CURSOR_SIZE = 22
HITBOX_SIZE = 19
INVINCIBILITY_MS = 200
STARTING_HEALTH = 4
GOAL_RADIUS = 12

NUM_TELE_BLOCKS = 4
TELEPORT_INTERVAL_MS = 3000  # 3s

SPIDER_SPEED = 1.7
SPIDER_PATH_INTERVAL_MS = 250
SPIDER_RETREAT_MS = 5400

WEAPON_MAX = 200
WEAPON_DEPL_RATE_PER_FRAME = 5


def generate_perfect_maze(cols=COLS, rows=ROWS, seed=None):
    if seed is not None:
        random.seed(seed)
    maze = [[WALL for _ in range(cols)] for _ in range(rows)]

    def in_bounds(x, y): return 0 <= x < cols and 0 <= y < rows

    sx, sy = 1, 1
    maze[sy][sx] = PATH
    stack = [(sx, sy)]
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
            wx, wy = x + dx // 2, y + dy // 2
            maze[wy][wx] = PATH
            maze[ny][nx] = PATH
            stack.append((nx, ny))
        else:
            stack.pop()
    # border walls
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
    sw, sh = screen_size
    ox = (sw - maze_px_w) // 2
    oy = (sh - maze_px_h) // 2
    wall_rects = []
    for y, row in enumerate(maze):
        for x, val in enumerate(row):
            if val == WALL:
                wall_rects.append(pg.Rect(ox + x * cell_size, oy + y * cell_size, cell_size, cell_size))
    return wall_rects, ox, oy


def solution_path_cells(maze, start_cell, goal_cell):
    sx, sy = start_cell
    gx, gy = goal_cell
    q = deque([(sx, sy)])
    came = {(sx, sy): None}
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    while q:
        x, y = q.popleft()
        if (x, y) == (gx, gy):
            break
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 0 <= nx < COLS and 0 <= ny < ROWS and maze[ny][nx] == PATH and (nx, ny) not in came:
                came[(nx, ny)] = (x, y)
                q.append((nx, ny))
    if (gx, gy) not in came:
        return []
    path = []
    cur = (gx, gy)
    while cur is not None:
        path.append(cur)
        cur = came[cur]
    path.reverse()
    return path


def choose_block_pairs_from_path(maze, start_cell, goal_cell, num_pairs):
    path = solution_path_cells(maze, start_cell, goal_cell)
    candidates = [p for p in path if p not in (start_cell, goal_cell)]
    if len(candidates) < 4:
        candidates = [(x, y) for y, row in enumerate(maze) for x, val in enumerate(row)
                      if val == PATH and (x, y) not in (start_cell, goal_cell)]
    if not candidates:
        candidates = [start_cell, goal_cell]
    pairs = []
    if len(candidates) >= 2 * num_pairs:
        samp = random.sample(candidates, 2 * num_pairs)
        for i in range(num_pairs):
            a = samp[i]
            b = samp[i + num_pairs]
            if a == b:
                b = samp[(i + num_pairs + 1) % (2 * num_pairs)]
            pairs.append((a, b))
    elif len(candidates) >= num_pairs:
        A = random.sample(candidates, num_pairs)
        B = random.sample(candidates, num_pairs)
        for i in range(num_pairs):
            a = A[i]
            b = B[i]
            if a == b:
                found = False
                for c in candidates:
                    if c != a and c not in B:
                        b = c
                        found = True
                        break
                if not found:
                    for c in candidates:
                        if c != a:
                            b = c
                            break
            pairs.append((a, b))
    else:
        L = len(candidates)
        for i in range(num_pairs):
            a = candidates[i % L]
            b = candidates[(i + max(1, L // 2)) % L]
            if a == b:
                b = candidates[(i + 1) % L]
            pairs.append((a, b))

    uniq = []
    seen = set()
    for a, b in pairs:
        key = tuple(sorted((a, b)))
        if key in seen:
            for c in candidates:
                for d in candidates:
                    if c == d:
                        continue
                    k2 = tuple(sorted((c, d)))
                    if k2 not in seen:
                        a, b = c, d
                        key = k2
                        break
                if key not in seen:
                    break
        if key not in seen:
            uniq.append((a, b))
            seen.add(key)

    attempts = 0
    while len(uniq) < num_pairs and attempts < 1000:
        attempts += 1
        a = random.choice(candidates)
        b = random.choice(candidates)
        if a == b:
            continue
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        uniq.append((a, b))
        seen.add(key)
    while len(uniq) < num_pairs:
        uniq.append(uniq[-1])
    return uniq[:num_pairs]


def bfs_next_step(start, goal, maze, blocked_rects, ox, oy):
    sx, sy = start
    gx, gy = goal
    if not (0 <= sx < COLS and 0 <= sy < ROWS):
        return start
    if not (0 <= gx < COLS and 0 <= gy < ROWS):
        return start
    q = deque([start])
    came = {start: None}
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    while q:
        x, y = q.popleft()
        if (x, y) == (gx, gy):
            break
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < COLS and 0 <= ny < ROWS):
                continue
            if maze[ny][nx] == WALL:
                continue
            cell_rect = pg.Rect(ox + nx * CELL_SIZE, oy + ny * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            if any(cell_rect.colliderect(r) for r in blocked_rects):
                continue
            if (nx, ny) not in came:
                came[(nx, ny)] = (x, y)
                q.append((nx, ny))
    if (gx, gy) not in came:
        return start
    cur = (gx, gy)
    while came[cur] != start and came[cur] is not None:
        cur = came[cur]
    return cur


def load_image_safe(path, scale=None, fallback_size=(20, 20), fallback_color=(255, 255, 255)):
    try:
        img = pg.image.load(path).convert_alpha()
        if scale is not None:
            img = pg.transform.scale(img, scale)
        return img
    except Exception:
        surf = pg.Surface(fallback_size, pg.SRCALPHA)
        surf.fill(fallback_color)
        return surf


_maze = generate_perfect_maze()
_start_cell = (1, 1)
_goal_cell = (COLS - 2, ROWS - 2)


def run_level(screen, cursor_img, clock):
    paused = False
    pause_font = pg.font.SysFont(None, 60)
    pause_small_font = pg.font.SysFont(None, 40)
    screen_w, screen_h = screen.get_size()
    ox, oy = 0, 0
    maze = _maze
    wall_rects, ox, oy = maze_to_wall_rects(maze, CELL_SIZE, (screen_w, screen_h))

    start_px = (ox + _start_cell[0] * CELL_SIZE + CELL_SIZE // 2,
                oy + _start_cell[1] * CELL_SIZE + CELL_SIZE // 2)
    end_px = (ox + _goal_cell[0] * CELL_SIZE + CELL_SIZE // 2,
              oy + _goal_cell[1] * CELL_SIZE + CELL_SIZE // 2)
    goal_px = [*end_px]
    return_trip = False

    x, y = start_px
    dragging = False
    drag_lockout = False

    # Load save and difficulty/hearts
    data = load_save()
    hearts_setting = data.get("hearts", "default")
    difficulty = data.get("difficulty", None)
    if isinstance(hearts_setting, int):
        health = int(hearts_setting)
    else:
        health = STARTING_HEALTH

    heart_img = load_image_safe("hart.png", scale=(32, 32), fallback_size=(32, 32), fallback_color=(220, 50, 50))
    last_hit_time = -INVINCIBILITY_MS

    maze_rect = pg.Rect(ox, oy, COLS * CELL_SIZE, ROWS * CELL_SIZE)

    weapon_energy = WEAPON_MAX

    # spider
    spider_img = load_image_safe("spider.png", scale=(20, 20), fallback_size=(20, 20), fallback_color=(50, 220, 50))
    spider_x, spider_y = float(end_px[0]), float(end_px[1])
    SPIDER_HUNT, SPIDER_RETREAT = 0, 1
    spider_state = SPIDER_HUNT
    path_timer = 0
    next_target = (spider_x, spider_y)
    retreat_until = 0

    # Teleporting block pairs
    block_pairs = choose_block_pairs_from_path(maze, _start_cell, _goal_cell, NUM_TELE_BLOCKS)
    blocks_current_cells = [a for (a, b) in block_pairs]  # grid coords
    toggle_state = [False] * len(block_pairs)
    next_teleport_time = pg.time.get_ticks() + TELEPORT_INTERVAL_MS

    def block_rects_from_cells(cells):
        return [pg.Rect(ox + bx * CELL_SIZE, oy + by * CELL_SIZE, CELL_SIZE, CELL_SIZE) for (bx, by) in cells]

    block_rects = block_rects_from_cells(blocks_current_cells)

    def is_safe_at(cx, cy, block_rects_local):
        cr = pg.Rect(cx - CURSOR_SIZE // 2, cy - CURSOR_SIZE // 2, CURSOR_SIZE, CURSOR_SIZE)
        if not maze_rect.contains(cr):
            return False
        if any(wr.colliderect(cr) for wr in wall_rects):
            return False
        if any(br.colliderect(cr) for br in block_rects_local):
            return False
        return True

    def find_nearest_safe_cell(from_x, from_y, block_rects_local):
        candidates = []
        for r in range(ROWS):
            for c in range(COLS):
                if maze[r][c] == PATH:
                    cx = ox + c * CELL_SIZE + CELL_SIZE // 2
                    cy = oy + r * CELL_SIZE + CELL_SIZE // 2
                    dist = (cx - from_x) ** 2 + (cy - from_y) ** 2
                    candidates.append((dist, cx, cy))
        candidates.sort(key=lambda t: t[0])
        for _, cx, cy in candidates:
            if is_safe_at(cx, cy, block_rects_local):
                return cx, cy
        return start_px

    def handle_hit(block_rects_local):
        nonlocal health, x, y, last_hit_time, dragging, drag_lockout, data
        last_hit_time = pg.time.get_ticks()
        dragging = False
        drag_lockout = True

        # global hearts mode
        if isinstance(data.get("hearts", "default"), int):
            data["hearts"] = int(data["hearts"]) - 1
            save_progress(data)
            health = data["hearts"]
            if data["hearts"] <= 0:
                if data.get("difficulty") == "hard":
                    return "BACK_TO_MENU_HARD_FAIL"
                else:
                    return "RETRY"
        else:
            health -= 1
            if health <= 0:
                return "RETRY"

        sx, sy = find_nearest_safe_cell(x, y, block_rects_local)
        x, y = sx, sy
        try:
            pg.mouse.set_pos((int(x), int(y)))
        except Exception:
            pass
        return None

    # ensure starting position safe
    if not is_safe_at(x, y, block_rects):
        x, y = find_nearest_safe_cell(x, y, block_rects)
        try:
            pg.mouse.set_pos((int(x), int(y)))
        except Exception:
            pass

    def world_to_cell(px, py):
        return (int((px - ox) // CELL_SIZE), int((py - oy) // CELL_SIZE))

    def cell_center(cx, cy):
        return (ox + cx * CELL_SIZE + CELL_SIZE // 2, oy + cy * CELL_SIZE + CELL_SIZE // 2)

    def pick_away_neighbor(sx, sy, px, py):
        best = (sx, sy)
        best_d2 = -1
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = sx + dx, sy + dy
            if 0 <= nx < COLS and 0 <= ny < ROWS and maze[ny][nx] == PATH:
                d2 = (nx - px) ** 2 + (ny - py) ** 2
                if d2 > best_d2:
                    best_d2 = d2
                    best = (nx, ny)
        return best

    # main loop
    while True:
        screen.fill((30, 30, 30))
        now = pg.time.get_ticks()

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

        # dragging logic
        if buttons[0]:
            if not dragging and not drag_lockout and char_rect.colliderect(mouse_rect):
                dragging = True
        else:
            dragging = False
            drag_lockout = False
        if dragging:
            x, y = mx, my

        # outside maze instant death (respect global hearts if present)
        if not maze_rect.collidepoint(char_rect.center):
            if isinstance(data.get("hearts", "default"), int):
                if now - last_hit_time >= INVINCIBILITY_MS:
                    res = handle_hit(block_rects)
                    if res:
                        return res
            else:
                return "RETRY"

        # teleport blocks toggle on interval
        if now >= next_teleport_time and block_pairs:
            new_cells = list(blocks_current_cells)
            for i, (a, b) in enumerate(block_pairs):
                target = b if not toggle_state[i] else a
                target_rect = pg.Rect(ox + target[0] * CELL_SIZE, oy + target[1] * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                if target_rect.colliderect(char_rect):
                    continue
                new_cells[i] = target
                toggle_state[i] = not toggle_state[i]
            blocks_current_cells = new_cells
            block_rects = block_rects_from_cells(blocks_current_cells)
            next_teleport_time = now + TELEPORT_INTERVAL_MS

        # draw maze walls
        for w in wall_rects:
            pg.draw.rect(screen, (200, 0, 20), w)

        # draw teleport blocks
        for br in block_rects:
            pg.draw.rect(screen, (180, 0, 180), br)

        # shield weapon (RMB)
        weapon_active = False
        shield_rects = []
        if buttons[2] and weapon_energy > 0:
            weapon_active = True
            weapon_energy = max(0, weapon_energy - WEAPON_DEPL_RATE_PER_FRAME)
            pcx, pcy = world_to_cell(x, y)
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                cx, cy = pcx + dx, pcy + dy
                if 0 <= cx < COLS and 0 <= cy < ROWS and maze[cy][cx] == PATH:
                    r = pg.Rect(ox + cx * CELL_SIZE, oy + cy * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                    shield_rects.append(r)
                    pg.draw.rect(screen, (0, 200, 200), r)

        # collisions: walls
        if now - last_hit_time >= INVINCIBILITY_MS:
            for w in wall_rects:
                if w.colliderect(char_rect):
                    res = handle_hit(block_rects)
                    if res:
                        return res
                    break

        # collisions: teleport blocks
        if now - last_hit_time >= INVINCIBILITY_MS:
            for br in block_rects:
                if br.colliderect(char_rect):
                    res = handle_hit(block_rects)
                    if res:
                        return res
                    break

        # SPIDER logic
        spider_rect = pg.Rect(int(spider_x) - 10, int(spider_y) - 10, 20, 20)
        if shield_rects and any(spider_rect.colliderect(s) for s in shield_rects):
            spider_state = SPIDER_RETREAT
            retreat_until = now + SPIDER_RETREAT_MS

        if spider_state == SPIDER_HUNT:
            if now - path_timer > SPIDER_PATH_INTERVAL_MS:
                scx, scy = world_to_cell(spider_x, spider_y)
                pcx, pcy = world_to_cell(x, y)
                blocked = block_rects if not return_trip else []
                nx, ny = bfs_next_step((scx, scy), (pcx, pcy), maze, blocked, ox, oy)
                next_target = (ox + nx * CELL_SIZE + CELL_SIZE // 2,
                               oy + ny * CELL_SIZE + CELL_SIZE // 2)
                path_timer = now
        else:
            if now >= retreat_until:
                spider_state = SPIDER_HUNT
            elif now - path_timer > SPIDER_PATH_INTERVAL_MS:
                scx, scy = world_to_cell(spider_x, spider_y)
                pcx, pcy = world_to_cell(x, y)
                nx, ny = pick_away_neighbor(scx, scy, pcx, pcy)
                next_target = (ox + nx * CELL_SIZE + CELL_SIZE // 2, oy + ny * CELL_SIZE + CELL_SIZE // 2)
                path_timer = now

        # move spider toward target
        dx_s = next_target[0] - spider_x
        dy_s = next_target[1] - spider_y
        dist_s = max(1.0, (dx_s * dx_s + dy_s * dy_s) ** 0.5)
        spider_x += (dx_s / dist_s) * SPIDER_SPEED
        spider_y += (dy_s / dist_s) * SPIDER_SPEED

        spider_rect = pg.Rect(int(spider_x) - 10, int(spider_y) - 10, 20, 20)
        screen.blit(spider_img, (spider_rect.x, spider_rect.y))

        # spider damages player (unless weapon active)
        if spider_rect.colliderect(char_rect) and not weapon_active and now - last_hit_time >= INVINCIBILITY_MS:
            res = handle_hit(block_rects)
            if res:
                return res

        # GOAL
        goal_color = (50, 150, 255) if not return_trip else (255, 215, 0)
        pg.draw.circle(screen, goal_color, goal_px, GOAL_RADIUS)
        if (x - goal_px[0]) ** 2 + (y - goal_px[1]) ** 2 <= GOAL_RADIUS ** 2:
            if not return_trip:
                goal_px[0], goal_px[1] = start_px
                return_trip = True
            else:
                return "NEXT"

        # HUD: hearts + weapon bar
        hearts_to_draw = int(data["hearts"]) if isinstance(data.get("hearts", "default"), int) else health
        for i in range(hearts_to_draw):
            screen.blit(heart_img, (10 + i * 40, 10))
        bar_w, bar_h = 200, 20
        pg.draw.rect(screen, (100, 0, 0), (10, 50, bar_w, bar_h))
        fill_w = int((weapon_energy / WEAPON_MAX) * bar_w)
        pg.draw.rect(screen, (0, 200, 200), (10, 50, fill_w, bar_h))

        # draw player (flash when invulnerable)
        if now - last_hit_time < INVINCIBILITY_MS:
            if (now // 100) % 2 == 0:
                screen.blit(cursor_img, (x - CURSOR_SIZE // 2, y - CURSOR_SIZE // 2))
        else:
            screen.blit(cursor_img, (x - CURSOR_SIZE // 2, y - CURSOR_SIZE // 2))

        pg.display.flip()
        clock.tick(60)
