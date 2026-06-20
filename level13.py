import pygame as pg
from save_utils import load_save, save_progress

CELL_SIZE = 35
REQUESTED_COLS = 12
REQUESTED_ROWS = 12

COLS = REQUESTED_COLS if REQUESTED_COLS % 2 == 1 else REQUESTED_COLS - 1
ROWS = REQUESTED_ROWS if REQUESTED_ROWS % 2 == 1 else REQUESTED_ROWS - 1

WALL = 1
PATH = 0

CURSOR_SIZE = 22
HITBOX_SIZE = 19   
INVINCIBILITY_MS = 200
LEVEL_DEFAULT_HEALTH = 4
GOAL_RADIUS = 10




_static_maze = [
    [1,1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,0,1],   # Easy path
    [1,0,1,1,1,1,1,1,1,0,1],
    [1,0,1,0,1,0,0,0,1,0,1],
    [1,0,1,0,1,0,1,0,1,0,1],
    [1,0,0,0,0,0,1,0,1,0,1],
    [1,1,1,1,1,1,1,0,1,0,1],
    [1,0,0,0,0,0,0,0,1,0,1],   # Hard path
    [1,0,1,1,1,1,1,1,1,0,1],
    [1,0,0,0,0,0,0,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,1,1],
]

_start_cell = (1, 1)
_goal_cell = (9, 9)



def maze_to_wall_rects(maze, screen_size):
    maze_px_w = COLS * CELL_SIZE
    maze_px_h = ROWS * CELL_SIZE
    sw, sh = screen_size

    ox = (sw - maze_px_w) // 2
    oy = (sh - maze_px_h) // 2

    wall_rects = []
    for y, row in enumerate(maze):
        for x, val in enumerate(row):
            if val == WALL:
                wall_rects.append(
                    pg.Rect(
                        ox + x * CELL_SIZE,
                        oy + y * CELL_SIZE,
                        CELL_SIZE,
                        CELL_SIZE
                    )
                )

    return wall_rects, ox, oy



def run_level(screen, cursor_img, clock):

    paused = False
    pause_font = pg.font.SysFont(None, 60)
    pause_small_font = pg.font.SysFont(None, 40)

    screen_w, screen_h = screen.get_size()
    wall_rects, ox, oy = maze_to_wall_rects(_static_maze, (screen_w, screen_h))

    start_px = (
        ox + _start_cell[0]*CELL_SIZE + CELL_SIZE//2,
        oy + _start_cell[1]*CELL_SIZE + CELL_SIZE//2
    )

    goal_px = [
        ox + _goal_cell[0]*CELL_SIZE + CELL_SIZE//2,
        oy + _goal_cell[1]*CELL_SIZE + CELL_SIZE//2
    ]

    x, y = start_px
    dragging = False
    drag_lockout = False


    data = load_save()
    hearts_setting = data.get("hearts", "default")

    if isinstance(hearts_setting, int):
        health = int(hearts_setting)
    else:
        health = LEVEL_DEFAULT_HEALTH

    last_hit_time = -INVINCIBILITY_MS
    maze_rect = pg.Rect(ox, oy, COLS*CELL_SIZE, ROWS*CELL_SIZE)

    try:
        heart_img = pg.image.load("hart.png").convert_alpha()
        heart_img = pg.transform.scale(heart_img, (32,32))
    except:
        heart_img = pg.Surface((32,32), pg.SRCALPHA)


    easy_path_chosen = False
    trap_wall = None
    return_trip = False


    def find_nearest_safe_cell(from_x, from_y):

        candidates = []

        for r in range(ROWS):
            for c in range(COLS):
                if _static_maze[r][c] == PATH:
                    cx = ox + c*CELL_SIZE + CELL_SIZE//2
                    cy = oy + r*CELL_SIZE + CELL_SIZE//2
                    dist = (cx - from_x)**2 + (cy - from_y)**2
                    candidates.append((dist, cx, cy))

        candidates.sort(key=lambda t: t[0])

        for _, cx, cy in candidates:
            cr = pg.Rect(cx-CURSOR_SIZE//2, cy-CURSOR_SIZE//2,
                         CURSOR_SIZE, CURSOR_SIZE)

            if not maze_rect.contains(cr):
                continue

            collision = False
            for w in wall_rects:
                if w.colliderect(cr):
                    collision = True
                    break

            if trap_wall and trap_wall.colliderect(cr):
                collision = True

            if not collision:
                return cx, cy

        return start_px



    def handle_damage():
        nonlocal health, x, y, last_hit_time, dragging, drag_lockout

        last_hit_time = pg.time.get_ticks()
        dragging = False
        drag_lockout = True

        # Global hearts mode
        if isinstance(data.get("hearts"), int):
            data["hearts"] -= 1
            save_progress(data)
            health = data["hearts"]

            if health <= 0:
                if data.get("difficulty") == "hard":
                    return "BACK_TO_MENU_HARD_FAIL"
                return "RETRY"

        else:
            health -= 1
            if health <= 0:
                return "RETRY"

        # Reposition safely
        sx, sy = find_nearest_safe_cell(x, y)
        x, y = sx, sy
        try:
            pg.mouse.set_pos((int(x), int(y)))
        except:
            pass

        return None



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

            overlay = pg.Surface(screen.get_size(), pg.SRCALPHA)
            overlay.fill((0,0,0,180))
            screen.blit(overlay,(0,0))

            title = pause_font.render("Paused", True, (255,255,255))
            screen.blit(title, (screen_w//2 - title.get_width()//2, 200))

            btn_w, btn_h = 300, 60
            btn_x = screen_w//2 - btn_w//2

            resume_rect = pg.Rect(btn_x, 300, btn_w, btn_h)
            restart_rect = pg.Rect(btn_x, 380, btn_w, btn_h)
            menu_rect = pg.Rect(btn_x, 460, btn_w, btn_h)

            mx, my = pg.mouse.get_pos()
            clicked = pg.mouse.get_pressed()[0]

            def draw_button(rect, text):
                color = (255,60,60) if rect.collidepoint(mx,my) else (200,30,30)
                pg.draw.rect(screen, color, rect, border_radius=8)
                txt = pause_small_font.render(text, True, (255,255,255))
                screen.blit(txt, (
                    rect.centerx - txt.get_width()//2,
                    rect.centery - txt.get_height()//2
                ))

            draw_button(resume_rect, "Resume")
            draw_button(restart_rect, "Restart Level")
            draw_button(menu_rect, "Return to Main Menu")

            if clicked:
                if resume_rect.collidepoint(mx,my):
                    paused = False
                elif restart_rect.collidepoint(mx,my):
                    return "RETRY"
                elif menu_rect.collidepoint(mx,my):
                    return "BACK_TO_MENU"

            pg.display.flip()
            clock.tick(60)
            continue

      

        buttons = pg.mouse.get_pressed()
        mx, my = pg.mouse.get_pos()

        mouse_rect = pg.Rect(mx-1, my-1, 2,2)
        char_rect = pg.Rect(x-CURSOR_SIZE//2, y-CURSOR_SIZE//2,
                            CURSOR_SIZE, CURSOR_SIZE)

        # Drag logic
        if buttons[0]:
            if not dragging and not drag_lockout and char_rect.colliderect(mouse_rect):
                dragging = True
        else:
            dragging = False
            drag_lockout = False

        if dragging:
            x, y = mx, my

        char_rect = pg.Rect(x-CURSOR_SIZE//2, y-CURSOR_SIZE//2,
                            CURSOR_SIZE, CURSOR_SIZE)

        # Boundary damage (not instant retry)
        if not maze_rect.contains(char_rect):
            if now - last_hit_time >= INVINCIBILITY_MS:
                res = handle_damage()
                if res:
                    return res

        # Detect easy path usage
        cell_x = int((x - ox)//CELL_SIZE)
        cell_y = int((y - oy)//CELL_SIZE)

        if not easy_path_chosen and cell_y == 1 and cell_x > 2:
            easy_path_chosen = True

        if easy_path_chosen and trap_wall is None and cell_x > 3:
            trap_wall = pg.Rect(
                ox + 2*CELL_SIZE,
                oy + 1*CELL_SIZE,
                CELL_SIZE,
                CELL_SIZE
            )

        # Draw walls
        for w in wall_rects:
            pg.draw.rect(screen,(200,0,20),w)

        if trap_wall:
            pg.draw.rect(screen,(200,0,20),trap_wall)

        # Collision damage
        if now - last_hit_time >= INVINCIBILITY_MS:
            for w in wall_rects + ([trap_wall] if trap_wall else []):
                if w and w.colliderect(char_rect):
                    res = handle_damage()
                    if res:
                        return res
                    break

        # Goal
        pg.draw.circle(screen,(50,150,255),goal_px,GOAL_RADIUS)

        if (x-goal_px[0])**2 + (y-goal_px[1])**2 <= GOAL_RADIUS**2:
            if not return_trip:
                return_trip = True
                goal_px[0], goal_px[1] = start_px
            else:
                return "NEXT"

        # Draw cursor
        screen.blit(cursor_img,(x-CURSOR_SIZE//2,y-CURSOR_SIZE//2))

        # Draw hearts
        for i in range(max(0,health)):
            screen.blit(heart_img,(10+i*40,10))

        pg.display.flip()
        clock.tick(60)

