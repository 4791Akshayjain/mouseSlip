# level13.py
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

# -- Gameplay constants --
STARTING_HEALTH = 6
TELEPORT_CHARGES = 4
SPIDER_SPEED = 0.7
SPIDER_PATH_INTERVAL_MS = 220

# -- Maze generator (same algorithm as other files) --
def generate_perfect_maze(cols=COLS, rows=ROWS, seed=None):
    if seed is not None:
        random.seed(seed)
    maze = [[WALL for _ in range(cols)] for _ in range(rows)]
    def in_bounds(x, y): return 0 <= x < cols and 0 <= y < rows
    sx, sy = 1, 1
    maze[sy][sx] = PATH
    stack = [(sx, sy)]
    dirs = [(2,0),(-2,0),(0,2),(0,-2)]
    while stack:
        x,y = stack[-1]
        neighbors = []
        for dx,dy in dirs:
            nx, ny = x+dx, y+dy
            if in_bounds(nx, ny) and maze[ny][nx] == WALL:
                neighbors.append((nx, ny, dx, dy))
        if neighbors:
            nx, ny, dx, dy = random.choice(neighbors)
            wx, wy = x + dx//2, y + dy//2
            maze[wy][wx] = PATH
            maze[ny][nx] = PATH
            stack.append((nx, ny))
        else:
            stack.pop()
    # borders
    for x in range(cols):
        maze[0][x] = WALL
        maze[rows-1][x] = WALL
    for y in range(rows):
        maze[y][0] = WALL
        maze[y][cols-1] = WALL
    return maze

def maze_to_wall_rects(maze, cell_size=CELL_SIZE, screen_size=(1024,768)):
    rows = len(maze)
    cols = len(maze[0])
    maze_px_w = cols * cell_size
    maze_px_h = rows * cell_size
    sw, sh = screen_size
    ox = (sw - maze_px_w) // 2
    oy = (sh - maze_px_h) // 2
    wall_rects = []
    for y,row in enumerate(maze):
        for x,val in enumerate(row):
            if val == WALL:
                wall_rects.append(pg.Rect(ox + x*cell_size, oy + y*cell_size, cell_size, cell_size))
    return wall_rects, ox, oy

# BFS used by spiders (ignores the purple teleport marker by design)
def bfs_next_step(start, goal, maze, blocked_rects, ox, oy):
    sx, sy = start
    gx, gy = goal
    if not (0 <= sx < COLS and 0 <= sy < ROWS): return start
    if not (0 <= gx < COLS and 0 <= gy < ROWS): return start
    q = deque([start])
    came = {start: None}
    dirs = [(1,0),(-1,0),(0,1),(0,-1)]
    while q:
        x,y = q.popleft()
        if (x,y) == (gx,gy): break
        for dx,dy in dirs:
            nx, ny = x+dx, y+dy
            if not (0 <= nx < COLS and 0 <= ny < ROWS): continue
            if maze[ny][nx] == WALL: continue
            cell_rect = pg.Rect(ox + nx*CELL_SIZE, oy + ny*CELL_SIZE, CELL_SIZE, CELL_SIZE)
            if any(cell_rect.colliderect(r) for r in blocked_rects):
                continue
            if (nx,ny) not in came:
                came[(nx,ny)] = (x,y)
                q.append((nx,ny))
    if (gx,gy) not in came: return start
    cur = (gx,gy)
    while came[cur] != start and came[cur] is not None:
        cur = came[cur]
    return cur

# load helper for images (fallback if missing)
def load_image_safe(path, scale=None, fallback_size=(20,20), fallback_color=(255,255,255)):
    try:
        img = pg.image.load(path).convert_alpha()
        if scale is not None:
            img = pg.transform.scale(img, scale)
        return img
    except Exception:
        surf = pg.Surface(fallback_size, pg.SRCALPHA)
        surf.fill(fallback_color)
        return surf

# make the maze
_maze = generate_perfect_maze()
_start_cell = (1,1)
_goal_cell = (COLS - 2, ROWS - 2)

def run_level(screen, cursor_img, clock):
    paused = False
    pause_font = pg.font.SysFont(None, 60)
    pause_small_font = pg.font.SysFont(None, 40)

    screen_w, screen_h = screen.get_size()
    wall_rects, ox, oy = maze_to_wall_rects(_maze, CELL_SIZE, (screen_w, screen_h))

    # pixel positions
    start_px = (ox + _start_cell[0]*CELL_SIZE + CELL_SIZE//2, oy + _start_cell[1]*CELL_SIZE + CELL_SIZE//2)
    goal_px = (ox + _goal_cell[0]*CELL_SIZE + CELL_SIZE//2, oy + _goal_cell[1]*CELL_SIZE + CELL_SIZE//2)
    goal_px_list = [*goal_px]
    return_trip = False

    # player state
    x, y = start_px
    dragging = False
    drag_lockout = False

    # read save / difficulty / hearts (we'll default to per-level 5 hearts unless global integer set)
    data = load_save()
    hearts_setting = data.get("hearts", "default")
    if isinstance(hearts_setting, int):
        health = int(hearts_setting)
    else:
        health = STARTING_HEALTH

    last_hit_time = -INVINCIBILITY_MS

    maze_rect = pg.Rect(ox, oy, COLS*CELL_SIZE, ROWS*CELL_SIZE)

    # heart image
    heart_img = load_image_safe("hart.png", scale=(32,32), fallback_size=(32,32), fallback_color=(220,50,50))

    # spider setup: spawn in two corners (top-right, bottom-left) to avoid player's start
    spider_img = load_image_safe("spider.png", scale=(20,20), fallback_size=(20,20), fallback_color=(150,0,0))
    corners = [
        (ox + (COLS-2)*CELL_SIZE + CELL_SIZE//2, oy + 1*CELL_SIZE + CELL_SIZE//2),         # top-right
        (ox + 1*CELL_SIZE + CELL_SIZE//2, oy + (ROWS-2)*CELL_SIZE + CELL_SIZE//2)          # bottom-left
    ]
    spiders = []
    for (sx,sy) in corners:
        spiders.append({
            "x": float(sx),
            "y": float(sy),
            "state": 0,            # 0 = hunt, 1 = retreat
            "path_timer": 0,
            "next_target": (sx,sy),
            "retreat_until": 0
        })
    SPIDER_HUNT, SPIDER_RETREAT = 0, 1

    # teleport marker (purple block) state
    tele_marker_active = False
    tele_marker_cell = None          # (cell_x, cell_y)
    tele_from_pos = None             # (x,y) pixel pos the player teleported from
    teleport_charges = TELEPORT_CHARGES
    tele_just_teleported = False     # to avoid double-charge while holding

    # drawing helper: convert cell -> rect
    def cell_to_rect(cell):
        cx, cy = cell
        return pg.Rect(ox + cx*CELL_SIZE, oy + cy*CELL_SIZE, CELL_SIZE, CELL_SIZE)

    def world_to_cell(px, py):
        return (int((px - ox)//CELL_SIZE), int((py - oy)//CELL_SIZE))

    def cell_center(cx, cy):
        return (ox + cx*CELL_SIZE + CELL_SIZE//2, oy + cy*CELL_SIZE + CELL_SIZE//2)

    # blocked rects for player-finding (we'll *not* include tele_marker in blocked rects for spiders)
    def find_nearest_safe_cell(from_x, from_y, blocked_rects):
        candidates = []
        for r in range(ROWS):
            for c in range(COLS):
                if _maze[r][c] == PATH:
                    cx = ox + c*CELL_SIZE + CELL_SIZE//2
                    cy = oy + r*CELL_SIZE + CELL_SIZE//2
                    dist = (cx - from_x)**2 + (cy - from_y)**2
                    candidates.append((dist, cx, cy))
        candidates.sort(key=lambda t: t[0])
        for _, cx, cy in candidates:
            cr = pg.Rect(cx - CURSOR_SIZE//2, cy - CURSOR_SIZE//2, CURSOR_SIZE, CURSOR_SIZE)
            if not maze_rect.contains(cr):
                continue
            collide_wall = any(w.colliderect(cr) for w in wall_rects)
            collide_block = any(br.colliderect(cr) for br in blocked_rects)
            if not collide_wall and not collide_block:
                return cx, cy
        return start_px

    # initial safety snap
    char_rect = pg.Rect(x - HITBOX_SIZE // 2, y - HITBOX_SIZE // 2, HITBOX_SIZE, HITBOX_SIZE)
    if not maze_rect.contains(char_rect):
        x,y = start_px

    # MAIN LOOP
    while True:
        screen.fill((30,30,30))
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
        mx, my = pg.mouse.get_pos()  # system mouse pos

        # --- NEW: while teleport marker active, freeze player position at start and disable dragging
        if tele_marker_active:
            # ensure player stays at start_px while holding
            x, y = start_px
            dragging = False
            # keep system mouse on the tele_from_pos visually (we set once when tele activated)
            # do NOT use mx,my to update player while tele is active
        else:
            # normal behaviour: handle left-dragging when not teleported
            mouse_rect = pg.Rect(mx-1, my-1, 2,2)
            char_rect = pg.Rect(x - HITBOX_SIZE // 2, y - HITBOX_SIZE // 2, HITBOX_SIZE, HITBOX_SIZE)
            if buttons[0]:
                if not dragging and not drag_lockout and char_rect.colliderect(mouse_rect):
                    dragging = True
            else:
                dragging = False
                drag_lockout = False
            if dragging:
                x, y = mx, my

        # build blocked rects for player-finding: walls + (if tele marker exists it should block player movement collisions)
        blocked_for_player = list(wall_rects)
        if tele_marker_active and tele_marker_cell:
            blocked_for_player.append(cell_to_rect(tele_marker_cell))

        # Handle RMB teleport mechanic:
        # - On RMB down: if charges left and not already teleported, consume one charge, remember tele_from_pos,
        #   set marker at the cell teleported-from, teleport player to start_px, AND move the system mouse cursor
        #   to the teleported-from spot so the system cursor appears to remain there while holding.
        # - While holding: player stays at start_px (we freeze x,y above). Spiders still move.
        # - On RMB release: if tele_marker_active, teleport player back to tele_from_pos and clear marker.
        if buttons[2]:
            # pressed
            if (not tele_marker_active) and teleport_charges > 0 and not tele_just_teleported:
                teleport_charges -= 1
                tele_from_pos = (int(x), int(y))
                tele_cell = world_to_cell(*tele_from_pos)
                tele_marker_cell = tele_cell
                tele_marker_active = True
                # teleport player to start immediately
                x, y = start_px
                # force the system mouse cursor once to the teleported-from spot so it visually remains there
                try:
                    pg.mouse.set_pos((int(tele_from_pos[0]), int(tele_from_pos[1])))
                except Exception:
                    pass
                tele_just_teleported = True
            else:
                # if already tele_marker_active, ensure we keep player at start (handled above)
                pass
        else:
            # released
            if tele_marker_active:
                # teleport back
                if tele_from_pos is not None:
                    x, y = tele_from_pos
                    # also ensure system cursor matches the player's return spot
                    try:
                        pg.mouse.set_pos((int(tele_from_pos[0]), int(tele_from_pos[1])))
                    except Exception:
                        pass
                tele_marker_active = False
                tele_marker_cell = None
                tele_from_pos = None
            tele_just_teleported = False

        # Recompute char_rect for collisions after any movement/locking
        char_rect = pg.Rect(x - HITBOX_SIZE // 2, y - HITBOX_SIZE // 2, HITBOX_SIZE, HITBOX_SIZE)

        # outside maze instant death / hearts consumption
        if not maze_rect.contains(char_rect):
            if now - last_hit_time >= INVINCIBILITY_MS:
                if isinstance(data.get("hearts", "default"), int):
                    data["hearts"] = int(data["hearts"]) - 1
                    save_progress(data)
                    health = data["hearts"]
                    last_hit_time = now
                    if data["hearts"] <= 0:
                        if data.get("difficulty") == "hard":
                            return "BACK_TO_MENU_HARD_FAIL"
                        else:
                            return "RETRY"
                    sx, sy = find_nearest_safe_cell(x, y, blocked_for_player)
                    x, y = sx, sy
                    try: pg.mouse.set_pos((int(x), int(y)))
                    except Exception: pass
                else:
                    health -= 1
                    last_hit_time = now
                    if health <= 0:
                        return "RETRY"
                    sx, sy = find_nearest_safe_cell(x, y, blocked_for_player)
                    x, y = sx, sy
                    try: pg.mouse.set_pos((int(x), int(y)))
                    except Exception: pass
                dragging = False
                drag_lockout = True

        # draw walls
        for w in wall_rects:
            pg.draw.rect(screen, (200,0,20), w)

        # draw tele marker if active (purple with white border)
        if tele_marker_active and tele_marker_cell:
            mr = cell_to_rect(tele_marker_cell)
            pg.draw.rect(screen, (255,255,255), mr, 2)  # white border
            inner = mr.inflate(-4, -4)
            pg.draw.rect(screen, (160, 0, 160), inner)

        # collisions: wall + marker (marker should hurt player if colliding)
        if now - last_hit_time >= INVINCIBILITY_MS:
            hit_handled = False
            # wall collisions
            for w in wall_rects:
                if w.colliderect(char_rect):
                    last_hit_time = now
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
                    sx, sy = find_nearest_safe_cell(x, y, blocked_for_player)
                    x, y = sx, sy
                    try: pg.mouse.set_pos((int(x), int(y)))
                    except Exception: pass
                    dragging = False
                    drag_lockout = True
                    hit_handled = True
                    break
            # tele-marker collision (hurts player) - only if active
            if (not hit_handled) and tele_marker_active and tele_marker_cell:
                mr = cell_to_rect(tele_marker_cell)
                if mr.colliderect(char_rect):
                    last_hit_time = now
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
                    sx, sy = find_nearest_safe_cell(x, y, blocked_for_player)
                    x, y = sx, sy
                    try: pg.mouse.set_pos((int(x), int(y)))
                    except Exception: pass
                    dragging = False
                    drag_lockout = True

        # SPIDERS: update each spider's target & move them.
        blocked_for_spiders = []   # intentionally empty so they can pass over tele marker
        for sp in spiders:
            spider_rect = pg.Rect(int(sp["x"]) - 10, int(sp["y"]) - 10, 20, 20)

            # Pathfinding update
            if sp["state"] == SPIDER_HUNT:
                if now - sp["path_timer"] > SPIDER_PATH_INTERVAL_MS:
                    scx, scy = world_to_cell(sp["x"], sp["y"])
                    pcx, pcy = world_to_cell(x, y)
                    nx, ny = bfs_next_step((scx, scy), (pcx, pcy), _maze, blocked_for_spiders, ox, oy)
                    tgt = cell_center(nx, ny)
                    sp["next_target"] = tgt
                    sp["path_timer"] = now
            else:
                if now >= sp["retreat_until"]:
                    sp["state"] = SPIDER_HUNT
                elif now - sp["path_timer"] > SPIDER_PATH_INTERVAL_MS:
                    scx, scy = world_to_cell(sp["x"], sp["y"])
                    pcx, pcy = world_to_cell(x, y)
                    best = (scx, scy)
                    best_d2 = -1
                    for dx_, dy_ in [(1,0),(-1,0),(0,1),(0,-1)]:
                        nx_, ny_ = scx + dx_, scy + dy_
                        if 0 <= nx_ < COLS and 0 <= ny_ < ROWS and _maze[ny_][nx_] == PATH:
                            d2 = (nx_ - pcx)**2 + (ny_ - pcy)**2
                            if d2 > best_d2:
                                best_d2 = d2
                                best = (nx_, ny_)
                    sp["next_target"] = cell_center(best[0], best[1])
                    sp["path_timer"] = now

            # movement toward next_target
            dx = sp["next_target"][0] - sp["x"]
            dy = sp["next_target"][1] - sp["y"]
            dist = max(1.0, (dx*dx + dy*dy)**0.5)
            sp["x"] += (dx / dist) * SPIDER_SPEED
            sp["y"] += (dy / dist) * SPIDER_SPEED

            # draw spider
            spider_draw_rect = pg.Rect(int(sp["x"]) - 10, int(sp["y"]) - 10, 20, 20)
            screen.blit(spider_img, (spider_draw_rect.x, spider_draw_rect.y))

            # spider collides with player (and can pass through purple marker): damage if overlapping and not invincible
            if spider_draw_rect.colliderect(char_rect) and now - last_hit_time >= INVINCIBILITY_MS:
                last_hit_time = now
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
                sx, sy = find_nearest_safe_cell(x, y, blocked_for_player)
                x, y = sx, sy
                try: pg.mouse.set_pos((int(x), int(y)))
                except Exception: pass
                dragging = False
                drag_lockout = True

        # draw goal (return-trip behavior preserved)
        goal_color = (50, 150, 255) if not return_trip else (255, 215, 0)
        pg.draw.circle(screen, goal_color, goal_px_list, 12)
        if (x - goal_px_list[0])**2 + (y - goal_px_list[1])**2 <= 12**2:
            if not return_trip:
                goal_px_list[0], goal_px_list[1] = start_px
                return_trip = True
            else:
                return "NEXT"

        # HUD: hearts
        hearts_to_draw = int(data["hearts"]) if isinstance(data.get("hearts","default"), int) else health
        for i in range(max(0, hearts_to_draw)):
            screen.blit(heart_img, (10 + i*40, 10))

        # HUD: teleport charges shown as purple blocks below hearts
        tp_x = 10
        tp_y = 10 + 40 + 6
        for i in range(TELEPORT_CHARGES):
            rect = pg.Rect(tp_x + i*28, tp_y, 22, 14)
            if i < teleport_charges:
                pg.draw.rect(screen, (160,0,160), rect)
            else:
                pg.draw.rect(screen, (80,30,80), rect)
            pg.draw.rect(screen, (255,255,255), rect, 1)

        # draw player (flash when invulnerable)
        if now - last_hit_time < INVINCIBILITY_MS:
            if (now // 100) % 2 == 0:
                screen.blit(cursor_img, (int(x) - CURSOR_SIZE//2, int(y) - CURSOR_SIZE//2))
        else:
            screen.blit(cursor_img, (int(x) - CURSOR_SIZE//2, int(y) - CURSOR_SIZE//2))

        pg.display.flip()
        clock.tick(60)
