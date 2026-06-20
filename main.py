import pygame as pg
import sys
import os
import json
import time


#levels
import level1, level2, level3, level4, level5, level6, level7, level8, level9, level10, level11,level12, endscreen, level13


# resources / paths

def get_resource_path(*path_parts):
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base, *path_parts)

def get_user_data_dir(app_name="Mouse Slip"):
    local = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
    appdir = os.path.join(local, app_name)
    try:
        os.makedirs(appdir, exist_ok=True)
    except Exception:
        import tempfile
        appdir = tempfile.gettempdir()
    return appdir

#pygame setup
pg.init()
SCREEN_WIDTH, SCREEN_HEIGHT = 1080, 708
screen = pg.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pg.display.set_caption("Mouse Slip")
clock = pg.time.Clock()

try:
    icon_path = get_resource_path("icon.ico")
    if os.path.exists(icon_path):
        icon = pg.image.load(icon_path).convert_alpha()
        pg.display.set_icon(icon)
except Exception:
    pass

#  load cursor image 
try:
    cursor_img_path = get_resource_path("mrunner.png")
    if os.path.exists(cursor_img_path):
        cursor_img = pg.image.load(cursor_img_path).convert_alpha()
        cursor_img = pg.transform.smoothscale(cursor_img, (22, 22))
    else:
        raise FileNotFoundError
except Exception:
    cursor_img = pg.Surface((22, 22), pg.SRCALPHA)
    pg.draw.circle(cursor_img, (255, 255, 255), (12, 12), 10)




LEVEL_ORDER = [1,2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, endscreen]

LEVELS = {
    1: level1, 2: level2, 3: level3, 4: level4, 5: level5,
    6: level13, 7: level6, 8: level7, 9: level8, 10: level9, 11: level10, 12: level11, 13: level12, endscreen: endscreen
}

# save system
SAVE_PATH = os.path.join(get_user_data_dir("Mouse Slip"), "progress.txt")
DEFAULT_HARD_HEARTS = 9

def default_save():
    
    return {
        "highest_completed_seq_index": -1,
        "best_times": {},
        "hearts": "default",
        "difficulty": None
    }

def load_save():
    parent = os.path.dirname(SAVE_PATH)
    try:
        os.makedirs(parent, exist_ok=True)
    except Exception:
        pass

    if not os.path.exists(SAVE_PATH):
        return default_save()
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "hearts" not in data:
                data["hearts"] = "default"
            if "difficulty" not in data:
                data["difficulty"] = None
            if "best_times" not in data:
                data["best_times"] = {}
            if "highest_completed_seq_index" not in data:
                data["highest_completed_seq_index"] = -1
            return data
    except Exception:
        return default_save()

def save_progress(data):
    parent = os.path.dirname(SAVE_PATH)
    try:
        os.makedirs(parent, exist_ok=True)
    except Exception:
        pass
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        try:
            import tempfile
            fallback = os.path.join(tempfile.gettempdir(), "progress.txt")
            with open(fallback, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            print("Failed to save progress:", e)

def reset_progress():
    data = default_save()
    save_progress(data)
    return data

def get_next_unfinished_index(data):
    idx = data["highest_completed_seq_index"] + 1
    if idx >= len(LEVEL_ORDER):
        return None
    return idx

def record_completion_time(data, level_number, elapsed_seconds):
    # IMPORTANT: expects 'data' to be a fresh save dict
    key = str(level_number)
    prev = data["best_times"].get(key)
    if prev is None or elapsed_seconds < prev:
        data["best_times"][key] = round(float(elapsed_seconds), 3)
    save_progress(data)

def update_sequential_completion(data, finished_level_number):
    try:
        finished_idx = LEVEL_ORDER.index(finished_level_number)
    except ValueError:
        return
    if finished_idx == data["highest_completed_seq_index"] + 1:
        data["highest_completed_seq_index"] = finished_idx
        save_progress(data)

# fonts & colors
FONT_TITLE = pg.font.SysFont(None, 72)
FONT_BIG   = pg.font.SysFont(None, 48)
FONT_MED   = pg.font.SysFont(None, 36)
FONT_SMALL = pg.font.SysFont(None, 28)

COLOR_BG = (30, 30, 30)      
COLOR_BTN = (200, 30, 30)   
COLOR_BTN_HOVER = (255, 60, 60)
COLOR_TEXT = (255, 255, 255)
COLOR_LOCK = (120, 120, 120)
ROW_OUTLINE = (10, 10, 10)


def draw_text(surface, text, font, color, center=None, topleft=None):
    s = font.render(text, True, color)
    rect = s.get_rect()
    if center:
        rect.center = center
    elif topleft:
        rect.topleft = topleft
    surface.blit(s, rect)
    return rect

def make_button(rect, text, enabled=True):
    mx, my = pg.mouse.get_pos()
    hovered = rect.collidepoint(mx, my)
    color = COLOR_BTN_HOVER if (hovered and enabled) else COLOR_BTN
    if not enabled:
        color = COLOR_LOCK
    pg.draw.rect(screen, color, rect, border_radius=6)
    draw_text(screen, text, FONT_MED, COLOR_TEXT, center=rect.center)
    return hovered and enabled

def process_events():
    quit_game = False
    clicked = False
    esc = False
    wheel = 0
    for e in pg.event.get():
        if e.type == pg.QUIT:
            quit_game = True
        elif e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
            esc = True
        elif e.type == pg.MOUSEBUTTONDOWN:
            if e.button == 1:
                clicked = True
            elif e.button == 4:  # -ve for up 
                wheel -= 1
            elif e.button == 5:  # +ve for down 
                wheel += 1
        elif e.type == pg.MOUSEWHEEL: 
            wheel -= e.y
    return quit_game, clicked, esc, wheel


def save_is_empty(data):
    
   
    if data is None:
        return True
    
    norm = {
        "highest_completed_seq_index": data.get("highest_completed_seq_index", -1),
        "best_times": data.get("best_times") or {},
        "difficulty": data.get("difficulty", None),
        "hearts": data.get("hearts", "default"),
    }
    return norm == {
        "highest_completed_seq_index": -1,
        "best_times": {},
        "difficulty": None,
        "hearts": "default",
    }


# difficulty selection (only appear if save data not found)
def difficulty_selection_modal():
    clock_local = pg.time.Clock()
    btn_w, btn_h = 360, 64
    x = SCREEN_WIDTH//2 - btn_w//2
    y = SCREEN_HEIGHT//2 - 80

    while True:
        quit_game, clicked, esc, _ = process_events()
        if quit_game:
            pg.quit()
            sys.exit()
        if esc:
            pass

        mx,my = pg.mouse.get_pos()
        mb = pg.mouse.get_pressed()[0]

        
        overlay = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pg.SRCALPHA)
        overlay.fill((0,0,0,140))
        screen.blit(overlay, (0,0))

        # panel
        panel_rect = pg.Rect(SCREEN_WIDTH//2 - 420//2, SCREEN_HEIGHT//2 - 220//2, 420, 220)
        pg.draw.rect(screen, (42,42,46), panel_rect, border_radius=8)
        draw_text(screen, "Pick difficulty for this new game", FONT_SMALL, (200,200,200), center=(panel_rect.centerx, panel_rect.y + 80))

        easy_rect = pg.Rect(x, y, btn_w, btn_h)
        hard_rect = pg.Rect(x, y+90, btn_w, btn_h)

        hovered_easy = make_button(easy_rect, "Normal", enabled=True)
        hovered_hard = make_button(hard_rect, "Hard", enabled=True)

        if mb and clicked:
            if hovered_easy:
                data = load_save()
                data["difficulty"] = "normal"
                data["hearts"] = "default"
             
                save_progress(data)
                return "normal"
            if hovered_hard:
                data = load_save()
                data["difficulty"] = "hard"
                data["hearts"] = DEFAULT_HARD_HEARTS
                data["highest_completed_seq_index"] = -1
                save_progress(data)
                return "hard"

        pg.display.flip()
        clock_local.tick(60)

def run_level_by_number(level_number):
    module = LEVELS[level_number]
    # run_level(screen, cursor, clock)
    while True:
        start = time.perf_counter()
        result = module.run_level(screen, cursor_img, clock)
        if result == "QUIT":
            pg.quit()
            sys.exit()
        elif result == "RETRY":
            continue
        elif result == "NEXT":
            elapsed = time.perf_counter() - start
            return elapsed
        elif result == "BACK_TO_MENU":
            return "BACK_TO_MENU"
        elif result == "BACK_TO_MENU_HARD_FAIL":
            return "BACK_TO_MENU_HARD_FAIL"
        else:
            continue

def run_campaign_from_index(data, start_index):
    # iterate from start_index to end of LEVEL_ORDER
    for idx in range(start_index, len(LEVEL_ORDER)):
        level_num = LEVEL_ORDER[idx]
        res = run_level_by_number(level_num)
        if res == "BACK_TO_MENU":
            return
        

        # If hard fail signaled, central reset and return
        if res == "BACK_TO_MENU_HARD_FAIL":
            data = load_save()
            data["highest_completed_seq_index"] = -1
            data["hearts"] = DEFAULT_HARD_HEARTS
            save_progress(data)
            return

        # reload saved data here to avoid overwriting changes level made to save
        data = load_save()

        # res is elapsed time now; record & update using fresh data
        elapsed = res
        if elapsed is not None:
            record_completion_time(data, level_num, elapsed)
        update_sequential_completion(data, level_num)


def menu_loop():
    while True:
        quit_game, clicked, _, _ = process_events()
        if quit_game:
            pg.quit()
            sys.exit()

        screen.fill(COLOR_BG)
        draw_text(screen, "Mouse Slip", FONT_TITLE, COLOR_TEXT, center=(SCREEN_WIDTH//2, 150))
        draw_text(screen, "by Akshay Jain", FONT_SMALL, COLOR_TEXT, center=(SCREEN_WIDTH//2, 200))

        # buttons 
        btn_w, btn_h, gap = 300, 60, 20
        x = SCREEN_WIDTH//2 - btn_w//2
        y = 260
        rect_play = pg.Rect(x, y, btn_w, btn_h); y += btn_h + gap
        rect_levels = pg.Rect(x, y, btn_w, btn_h); y += btn_h + gap
        rect_reset = pg.Rect(x, y, btn_w, btn_h); y += btn_h + gap
        rect_quit = pg.Rect(x, y, btn_w, btn_h)

        hovered_play = make_button(rect_play, "Play")
        hovered_levels = make_button(rect_levels, "Level Select")
        hovered_reset = make_button(rect_reset, "Reset Progress")
        hovered_quit = make_button(rect_quit, "Quit")

        data = load_save()
        # HUD: show hearts/difficulty top-left
        if isinstance(data.get("hearts"), int):
            draw_text(screen, f"Hearts: {data['hearts']}", FONT_SMALL, COLOR_TEXT, topleft=(18,18))
        else:
            draw_text(screen, "Hearts: default", FONT_SMALL, COLOR_TEXT, topleft=(18,18))
        draw_text(screen, f"Difficulty: {data.get('difficulty')}", FONT_SMALL, COLOR_TEXT, topleft=(18,46))

        if clicked:
            if hovered_play:
                # If save is empty force difficulty selection modal before starting first run
                data = load_save()
                if save_is_empty(data):
                    difficulty_selection_modal()
                    data = load_save()  # reload after choosing difficulty
                # Now start campaign from next unfinished
                data = load_save()
                next_idx = get_next_unfinished_index(data)
                if next_idx is None:
                    next_idx = 0
                run_campaign_from_index(data, next_idx)
                data = load_save()

            elif hovered_levels:
                level_select_loop()
                data = load_save()

            elif hovered_reset:
                reset_progress()
                data = load_save()

            elif hovered_quit:
                pg.quit()
                sys.exit()

        pg.mouse.set_visible(True)
        pg.display.flip()
        clock.tick(60)

def level_select_loop():
    data = load_save()
    padding_x = 60
    start_y = 140
    row_h = 66
    gap = 12
    left_col = padding_x
    row_width = SCREEN_WIDTH - padding_x*2
    scroll_y = 0

    while True:
        quit_game, clicked, esc, wheel = process_events()
        if quit_game:
            pg.quit()
            sys.exit()
        if esc:
            return

        # update scrolling using wheel (-ve -> scroll up)
        scroll_y -= wheel * 30
        total_height = len(LEVEL_ORDER) * (row_h + gap) - gap
        visible_height = SCREEN_HEIGHT - start_y - 120
        max_scroll = max(0, total_height - visible_height)
        if scroll_y > 0:
            scroll_y = 0
        if scroll_y < -max_scroll:
            scroll_y = -max_scroll

        screen.fill(COLOR_BG)
        draw_text(screen, "Level Select", FONT_BIG, COLOR_TEXT, center=(SCREEN_WIDTH//2, 80))

        mx, my = pg.mouse.get_pos()
        data = load_save()  # always use fresh data here
        next_idx = get_next_unfinished_index(data)
        completed_levels = set(int(k) for k in data["best_times"].keys())

        hover_level_number = None

        # draw rows
        for i, lvl in enumerate(LEVEL_ORDER):
            y = start_y + i * (row_h + gap) + scroll_y
            rect = pg.Rect(left_col, y, row_width, row_h)

            # cull
            if rect.bottom < 0 or rect.top > SCREEN_HEIGHT:
                continue

            enabled = False
            if lvl in completed_levels:
                enabled = True
            elif next_idx is not None and LEVEL_ORDER[next_idx] == lvl:
                enabled = True

            hovered = rect.collidepoint(mx, my)
            if hovered and enabled:
                hover_level_number = lvl

            # choose color
            if not enabled:
                color = COLOR_LOCK
            elif hovered:
                color = COLOR_BTN_HOVER
            else:
                color = COLOR_BTN

            pg.draw.rect(screen, color, rect, border_radius=8)
            pg.draw.rect(screen, ROW_OUTLINE, rect, width=2, border_radius=8)
            draw_text(screen, f"Level {lvl}", FONT_MED, COLOR_TEXT, topleft=(rect.x + 16, rect.y + (row_h//2 - 18)))

            t = data["best_times"].get(str(lvl))
            if t is not None:
                time_text = f"{t:.2f}s"
                tsurf = FONT_MED.render(time_text, True, COLOR_TEXT)
                tsr = tsurf.get_rect()
                tsr.top = rect.y + (row_h//2 - tsr.height//2)
                tsr.right = rect.right - 16
                screen.blit(tsurf, tsr)
            else:
                status = "Unlocked" if enabled else "Locked"
                st_surf = FONT_SMALL.render(status, True, (220, 220, 220))
                st_rect = st_surf.get_rect()
                st_rect.top = rect.y + (row_h//2 - st_rect.height//2)
                st_rect.right = rect.right - 16
                screen.blit(st_surf, st_rect)

        # back button
        back_rect = pg.Rect(SCREEN_WIDTH//2-100, SCREEN_HEIGHT-80, 200, 50)
        hovered_back = make_button(back_rect, "Back")

        if clicked:
            if hovered_back:
                return
            if hover_level_number is not None:
                res = run_level_by_number(hover_level_number)
                if res == "BACK_TO_MENU_HARD_FAIL":
                    data = load_save()
                    data["highest_completed_seq_index"] = -1
                    data["hearts"] = DEFAULT_HARD_HEARTS
                    save_progress(data)
                    return
                # reload save before recording to avoid overwriting level-updated hearts
                data = load_save()
                if isinstance(res, (int, float)):
                    record_completion_time(data, hover_level_number, res)
                    update_sequential_completion(data, hover_level_number)

                update_sequential_completion(data, hover_level_number)
                data = load_save()

        pg.mouse.set_visible(True)
        pg.display.flip()
        clock.tick(60)


menu_loop()
