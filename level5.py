import pygame as pg
import random
from save_utils import load_save, save_progress

CELL_SIZE = 35        # pixel size of each cell
REQUESTED_COLS = 12   # requested maze width in cells
REQUESTED_ROWS = 12   # requested maze height in cells

COLS = REQUESTED_COLS if REQUESTED_COLS % 2 == 1 else REQUESTED_COLS - 1
ROWS = REQUESTED_ROWS if REQUESTED_ROWS % 2 == 1 else REQUESTED_ROWS - 1

WALL = 1
PATH = 0

def generate_perfect_maze(cols=COLS, rows=ROWS, seed=None):
    if seed is not None:
        random.seed(seed)

    # Start with all walls
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

    # Make border walls
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

    start_px = (offset_x + _start_cell[0] * CELL_SIZE + CELL_SIZE // 2,
                offset_y + _start_cell[1] * CELL_SIZE + CELL_SIZE // 2)
    goal_px = [offset_x + _goal_cell[0] * CELL_SIZE + CELL_SIZE // 2,
               offset_y + _goal_cell[1] * CELL_SIZE + CELL_SIZE // 2]

    # Load save and difficulty/hearts
    data = load_save()
    hearts_setting = data.get("hearts", "default")
    difficulty = data.get("difficulty", None)

    # Per-level default health when global hearts not used
    LEVEL_DEFAULT_HEALTH = 3
    if isinstance(hearts_setting, int):
        health = int(hearts_setting)
    else:
        health = LEVEL_DEFAULT_HEALTH

    x, y = start_px
    dragging = False
    drag_lockout = False
    goal_radius = max(12, cursor_size // 2)

    return_trip = False

    # Load heart image if available (fallback drawn if not)
    try:
        heart_img = pg.image.load("hart.png").convert_alpha()
        heart_img = pg.transform.scale(heart_img, (32, 32))
    except Exception:
        heart_img = pg.Surface((32, 32), pg.SRCALPHA)
        pg.draw.polygon(heart_img, (200, 20, 20), [(16,0),(32,12),(16,32),(0,12)])

    invincibility_time = 200
    last_hit_time = -invincibility_time

    maze_rect = pg.Rect(offset_x, offset_y, COLS * CELL_SIZE, ROWS * CELL_SIZE)

    def is_safe_at(cx, cy):
        cr = pg.Rect(cx - cursor_size // 2, cy - cursor_size // 2, cursor_size, cursor_size)
        return not any(wr.colliderect(cr) for wr in wall_rects)

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
        return start_px

    def dist2(ax, ay, bx, by):
        return (ax - bx) ** 2 + (ay - by) ** 2

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

        # Out of maze: apply hearts logic if used, otherwise retry
        if not maze_rect.contains(char_rect):
            if isinstance(data.get("hearts", "default"), int):
                if current_time - last_hit_time >= invincibility_time:
                    # decrement global hearts, save immediately
                    data["hearts"] = int(data["hearts"]) - 1
                    last_hit_time = current_time
                    save_progress(data)
                    health = data["hearts"]
                    if data["hearts"] <= 0:
                        if data.get("difficulty") == "hard":
                            return "BACK_TO_MENU_HARD_FAIL"
                        else:
                            return "RETRY"
                    # move to nearest safe cell
                    x, y = find_nearest_safe_cell(x, y)
                    try:
                        pg.mouse.set_pos((int(x), int(y)))
                    except Exception:
                        pass
                    dragging = False
                    drag_lockout = True
            else:
                return "RETRY"

        # Draw walls
        for w in wall_rects:
            pg.draw.rect(screen, (200, 0, 20), w)

        # Wall collisions
        for w in wall_rects:
            if w.colliderect(char_rect):
                if current_time - last_hit_time >= invincibility_time:
                    last_hit_time = current_time

                    # Hearts-mode (global save)
                    if isinstance(data.get("hearts", "default"), int):
                        data["hearts"] = int(data["hearts"]) - 1
                        save_progress(data)  # persist immediately
                        health = data["hearts"]

                        # force stop dragging and lock until release
                        dragging = False
                        drag_lockout = True

                        if data["hearts"] <= 0:
                            if data.get("difficulty") == "hard":
                                return "BACK_TO_MENU_HARD_FAIL"
                            else:
                                return "RETRY"

                        # recenter to nearest safe spot
                        safe_x, safe_y = find_nearest_safe_cell(x, y)
                        x, y = safe_x, safe_y
                        try:
                            pg.mouse.set_pos((int(x), int(y)))
                        except Exception:
                            pass

                    else:
                        # per-level health mode
                        health -= 1
                        dragging = False
                        drag_lockout = True

                        if health <= 0:
                            return "RETRY"

                        safe_x, safe_y = find_nearest_safe_cell(x, y)
                        x, y = safe_x, safe_y
                        try:
                            pg.mouse.set_pos((int(x), int(y)))
                        except Exception:
                            pass
                break

        # Draw goal (changes color on return trip)
        goal_color = (50, 150, 255) if not return_trip else (255, 215, 0)
        pg.draw.circle(screen, goal_color, goal_px, goal_radius)

        if dist2(x, y, goal_px[0], goal_px[1]) <= goal_radius ** 2:
            if not return_trip:
                # first visit: move goal to start and require return trip
                goal_px[0], goal_px[1] = start_px
                return_trip = True
                # subtle message in console for debug
                print("Goal moved! Return to start to finish.")
            else:
                print("Level complete after return trip!")
                return "NEXT"

        # Draw hearts HUD (draw from save if present else per-level)
        hearts_to_draw = int(data["hearts"]) if isinstance(data.get("hearts", "default"), int) else health
        for i in range(max(0, min(6, hearts_to_draw))):
            screen.blit(heart_img, (10 + i * 40, 10))

        # Draw player with invincibility flash
        if current_time - last_hit_time < invincibility_time:
            if (current_time // 100) % 2 == 0:
                screen.blit(cursor_img, (x - cursor_size // 2, y - cursor_size // 2))
        else:
            screen.blit(cursor_img, (x - cursor_size // 2, y - cursor_size // 2))

        pg.display.flip()
        clock.tick(60)

