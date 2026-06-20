import pygame as pg
import random
from save_utils import load_save, save_progress

CELL_SIZE = 34
REQUESTED_COLS = 15
REQUESTED_ROWS = 15
COLS = REQUESTED_COLS if REQUESTED_COLS % 2 == 1 else REQUESTED_COLS - 1
ROWS = REQUESTED_ROWS if REQUESTED_ROWS % 2 == 1 else REQUESTED_ROWS - 1

WALL = 1
PATH = 0

def generate_perfect_maze(cols=COLS, rows=ROWS, seed=None):
    if seed is not None:
        random.seed(seed)
    maze = [[WALL for _ in range(cols)] for _ in range(rows)]
    def in_bounds(x, y): return 0 <= x < cols and 0 <= y < rows
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
            maze[y + dy // 2][x + dx // 2] = PATH
            maze[ny][nx] = PATH
            stack.append((nx, ny))
        else:
            stack.pop()
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

_maze = generate_perfect_maze()
_start_cell = (1, 1)
_goal_cell = (len(_maze[0]) - 2, len(_maze) - 2)

def create_teleporting_blocks(maze, num_blocks=4):
    path_cells = [(x, y) for y, row in enumerate(maze) for x, val in enumerate(row)
                  if val == PATH and (x, y) not in [_start_cell, _goal_cell]]
    random.shuffle(path_cells)
    return path_cells[:num_blocks]

def valid_teleport_targets(maze, block, excluded_blocks):
    ox, oy = block
    path_cells = [(cx, cy) for cy, row in enumerate(maze) for cx, val in enumerate(row)
                  if val == PATH and (cx, cy) not in excluded_blocks and (cx, cy) != _start_cell and (cx, cy) != _goal_cell]
    # require at least a 2-cell gap in either axis
    return [(tx, ty) for (tx, ty) in path_cells if abs(ox - tx) >= 2 or abs(oy - ty) >= 2]

def run_level(screen, cursor_img, clock):
    paused = False
    pause_font = pg.font.SysFont(None, 60)
    pause_small_font = pg.font.SysFont(None, 40)
    cursor_size = 24
    HITBOX_SIZE = 19
    screen_w, screen_h = screen.get_size()
    wall_rects, offset_x, offset_y = maze_to_wall_rects(
        _maze, cell_size=CELL_SIZE, screen_size=(screen_w, screen_h)
    )
    maze_rect = pg.Rect(offset_x, offset_y, COLS * CELL_SIZE, ROWS * CELL_SIZE)

    start_px = (offset_x + _start_cell[0] * CELL_SIZE + CELL_SIZE // 2,
                offset_y + _start_cell[1] * CELL_SIZE + CELL_SIZE // 2)
    goal_px = (offset_x + _goal_cell[0] * CELL_SIZE + CELL_SIZE // 2,
               offset_y + _goal_cell[1] * CELL_SIZE + CELL_SIZE // 2)

    x, y = start_px
    dragging = False
    drag_lockout = False
    goal_radius = 10

    # Teleporting blocks setup with 2-cell gap rule
    blocks_original = create_teleporting_blocks(_maze, num_blocks=4)
    teleport_targets = {}
    for block in blocks_original:
        possible_cells = valid_teleport_targets(_maze, block, blocks_original)
        teleport_targets[block] = random.choice(possible_cells) if possible_cells else block
    blocks_current = list(blocks_original)

    # Teleport limit
    TELEPORT_LIMIT = 5
    teleport_count = TELEPORT_LIMIT
    teleport_active = False

    # Load save and difficulty/hearts
    data = load_save()
    hearts_setting = data.get("hearts", "default")
    difficulty = data.get("difficulty", None)

    # per-level default health if global hearts not used
    LEVEL_DEFAULT_HEARTS = 4
    if isinstance(hearts_setting, int):
        hearts = int(hearts_setting)
    else:
        hearts = LEVEL_DEFAULT_HEARTS

    # images and fonts
    try:
        heart_img = pg.image.load("hart.png").convert_alpha()
        heart_img = pg.transform.smoothscale(heart_img, (28, 28))
    except Exception:
        heart_img = pg.Surface((28, 28), pg.SRCALPHA)
        pg.draw.polygon(heart_img, (200, 20, 20), [(14,0),(28,10),(14,28),(0,10)])

    font = pg.font.SysFont(None, 32)

    # invincibility measured in milliseconds
    invincibility_ms = 200
    last_hit_time = -invincibility_ms

    def is_safe_at(cx, cy, block_rects):
        cr = pg.Rect(cx - cursor_size // 2, cy - cursor_size // 2, cursor_size, cursor_size)
        if not maze_rect.contains(cr):
            return False
        for wr in wall_rects:
            if wr.colliderect(cr):
                return False
        for br in block_rects:
            if br.colliderect(cr):
                return False
        return True

    def find_nearest_safe_cell(from_x, from_y, block_rects):
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
            if is_safe_at(cx, cy, block_rects):
                return cx, cy
        return start_px

    def blocks_to_rects(blocks_list):
        return [
            pg.Rect(offset_x + bx * CELL_SIZE, offset_y + by * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            for (bx, by) in blocks_list
        ]

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

        # Instant death / out of maze: apply hearts logic if used, otherwise retry
        if not maze_rect.contains(char_rect):
            if isinstance(data.get("hearts", "default"), int):
                if current_time - last_hit_time >= invincibility_ms:
                    data["hearts"] = int(data["hearts"]) - 1
                    last_hit_time = current_time
                    save_progress(data)
                    hearts = data["hearts"]
                    if data["hearts"] <= 0:
                        if data.get("difficulty") == "hard":
                            return "BACK_TO_MENU_HARD_FAIL"
                        else:
                            return "RETRY"
                    # recompute block rects (right-click may change them)
                    if buttons[2]:
                        blocks_current = [teleport_targets[orig] for orig in blocks_original]
                    else:
                        blocks_current = list(blocks_original)
                    block_rects = blocks_to_rects(blocks_current)
                    x, y = find_nearest_safe_cell(x, y, block_rects)
                    try: pg.mouse.set_pos((int(x), int(y)))
                    except Exception: pass
                    dragging = False
                    drag_lockout = True
            else:
                return "RETRY"

        # Right click teleport blocks for this frame if available
        if buttons[2] and teleport_count > 0:
            if not teleport_active:
                teleport_active = True
                teleport_count -= 1
            blocks_current = [teleport_targets[orig] for orig in blocks_original]
        else:
            teleport_active = False
            blocks_current = list(blocks_original)

        block_rects = blocks_to_rects(blocks_current)

        # Dragging logic with lockout
        if buttons[0]:
            if not dragging and not drag_lockout and char_rect.colliderect(mouse_rect):
                dragging = True
        else:
            dragging = False
            drag_lockout = False

        if dragging:
            x, y = mx, my

        # Collision handling (respect invincibility)
        if current_time - last_hit_time >= invincibility_ms:
            # walls
            hit = False
            for w in wall_rects:
                if w.colliderect(char_rect):
                    last_hit_time = current_time
                    # hearts-mode
                    if isinstance(data.get("hearts", "default"), int):
                        data["hearts"] = int(data["hearts"]) - 1
                        save_progress(data)
                        hearts = data["hearts"]
                        dragging = False
                        drag_lockout = True
                        if data["hearts"] <= 0:
                            if data.get("difficulty") == "hard":
                                return "BACK_TO_MENU_HARD_FAIL"
                            else:
                                return "RETRY"
                        x, y = find_nearest_safe_cell(x, y, block_rects)
                        try: pg.mouse.set_pos((int(x), int(y)))
                        except Exception: pass
                    else:
                        hearts -= 1
                        dragging = False
                        drag_lockout = True
                        if hearts <= 0:
                            return "RETRY"
                        x, y = find_nearest_safe_cell(x, y, block_rects)
                        try: pg.mouse.set_pos((int(x), int(y)))
                        except Exception: pass
                    hit = True
                    break

            # blocks
            if not hit:
                for br in block_rects:
                    if br.colliderect(char_rect):
                        last_hit_time = current_time
                        if isinstance(data.get("hearts", "default"), int):
                            data["hearts"] = int(data["hearts"]) - 1
                            save_progress(data)
                            hearts = data["hearts"]
                            dragging = False
                            drag_lockout = True
                            if data["hearts"] <= 0:
                                if data.get("difficulty") == "hard":
                                    return "BACK_TO_MENU_HARD_FAIL"
                                else:
                                    return "RETRY"
                            x, y = find_nearest_safe_cell(x, y, block_rects)
                            try: pg.mouse.set_pos((int(x), int(y)))
                            except Exception: pass
                        else:
                            hearts -= 1
                            dragging = False
                            drag_lockout = True
                            if hearts <= 0:
                                return "RETRY"
                            x, y = find_nearest_safe_cell(x, y, block_rects)
                            try: pg.mouse.set_pos((int(x), int(y)))
                            except Exception: pass
                        break

        # Draw walls
        for w in wall_rects:
            pg.draw.rect(screen, (200, 0, 2), w)

        # Draw teleporting blocks
        for br in block_rects:
            pg.draw.rect(screen, (200, 0, 200), br)

        # Draw goal
        pg.draw.circle(screen, (50, 150, 255), goal_px, goal_radius)
        if (x - goal_px[0]) ** 2 + (y - goal_px[1]) ** 2 <= goal_radius ** 2:
            return "NEXT"

        # Draw teleport bar and label
        bar_x = screen_w - 40
        bar_y = 50
        bar_width = 20
        bar_height = 200
        pg.draw.rect(screen, (100, 100, 100), (bar_x, bar_y, bar_width, bar_height))
        unit_height = bar_height / TELEPORT_LIMIT
        for i in range(teleport_count):
            pg.draw.rect(screen, (200, 0, 120),
                         (bar_x, bar_y + (TELEPORT_LIMIT - i - 1) * unit_height,
                          bar_width, unit_height - 2))
        label = font.render("TP", True, (255, 255, 255))
        screen.blit(label, (bar_x - 5, bar_y - 25))

        # Instruction text
        instruction = font.render("Right-click to teleport blocks", True, (255, 255, 255))
        screen.blit(instruction, (screen_w // 2 - instruction.get_width() // 2, 10))

        # Draw hearts HUD (global save hearts if present else per-level)
        hearts_to_draw = int(data["hearts"]) if isinstance(data.get("hearts", "default"), int) else hearts
        for i in range(max(0, min(6, hearts_to_draw))):
            screen.blit(heart_img, (10 + i * 28, 10))

        # Draw cursor (flash while invincible)
        if current_time - last_hit_time < invincibility_ms:
            if (current_time // 100) % 2 == 0:
                screen.blit(cursor_img, (x - cursor_size // 2, y - cursor_size // 2))
        else:
            screen.blit(cursor_img, (x - cursor_size // 2, y - cursor_size // 2))

        pg.display.flip()
        clock.tick(60)
