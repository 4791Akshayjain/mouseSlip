# level1.py
from cmath import rect
from pydoc import text
from turtle import color
import pygame as pg
import sys
import os
import json

walls = [
    pg.Rect(100, 100, 600, 20),
    pg.Rect(100, 100, 20, 500),
    pg.Rect(100, 580, 600, 20),
    pg.Rect(680, 100, 20, 500),
]

# Goal position
goal_pos = (640, 440)
goal_radius = 10
HITBOX_SIZE = 19

# Spawn position
start_pos = (454, 276)

#Save/load 
def get_user_data_dir(app_name="Mouse Slip"):
    local = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
    appdir = os.path.join(local, app_name)
    try:
        os.makedirs(appdir, exist_ok=True)
    except Exception:
        import tempfile
        appdir = tempfile.gettempdir()
    return appdir

SAVE_PATH = os.path.join(get_user_data_dir("Mouse Slip"), "progress.txt")

def default_save():
    return {"highest_completed_seq_index": -1, "best_times": {}, "difficulty": None, "hearts": "default"}

def load_save():
    try:
        if not os.path.exists(SAVE_PATH):
            return default_save()
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "difficulty" not in data:
            data["difficulty"] = None
        if "hearts" not in data:
            data["hearts"] = "default"
        return data
    except Exception:
        return default_save()

def save_progress(data):
    try:
        parent = os.path.dirname(SAVE_PATH)
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


def run_level(screen, cursor_img, clock):
    paused = False
    LEVEL_DEFAULT_HEALTH = 1

    cursor_size = 22
    x, y = start_pos  # Character position
    dragging = False

   
    data = load_save()
    hearts_setting = data.get("hearts", "default")
    difficulty = data.get("difficulty", None)

    if isinstance(hearts_setting, int):
        health = int(hearts_setting)
    else:
        health = LEVEL_DEFAULT_HEALTH


    try:
        heart_img = pg.image.load("hart.png").convert_alpha()
        heart_img = pg.transform.scale(heart_img, (32, 32))
    except Exception:
        heart_img = pg.Surface((32, 32), pg.SRCALPHA)
        pg.draw.polygon(heart_img, (200, 20, 20), [(16,0),(32,12),(16,32),(0,12)])

    paused = False
    pause_font = pg.font.SysFont(None, 48)
    pause_small_font = pg.font.SysFont(None, 36)

    while True:
        screen.fill((30, 30, 30))

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


        # Get mouse state
        buttons = pg.mouse.get_pressed()
        if buttons[2]:  # print mouse position
            px, py = pg.mouse.get_pos()
            print(f"Mouse Position: {px}, {py}")
        mx, my = pg.mouse.get_pos()
        mouse_rect = pg.Rect(mx - 1, my - 1, 2, 2)

        # Character rectangle
        char_rect = pg.Rect(x - cursor_size // 2, y - cursor_size // 2, cursor_size, cursor_size)

        # Dragging logic
        if buttons[0]:
            if not dragging and char_rect.colliderect(mouse_rect):
                dragging = True
        else:
            dragging = False

        if dragging:
            x, y = mx, my

        # Draw walls & check collision
        hit = False
        for wall in walls:
            pg.draw.rect(screen, (255, 0, 2), wall)
            if wall.colliderect(char_rect):
                hit = True
                break

        if hit:
            print("Hit a wall!")
            # Apply damage logic depending on whether hearts are managed globally
            if isinstance(data.get("hearts", "default"), int):
                # apply global hearts decrement and persist
                data["hearts"] = int(data["hearts"]) - 1
                save_progress(data)
                health = data["hearts"]
                print(f"Global hearts decreased -> {data['hearts']}")

                # If hearts <= 0 and difficulty is hard: reset progress & hearts and return special code
                if data["hearts"] <= 0 and data.get("difficulty") == "hard":
                    print("Hard-mode global hearts reached 0 -> resetting to level 1 and hearts to 9")
                    data["highest_completed_seq_index"] = -1
                    data["hearts"] = 9
                    save_progress(data)
                    return "BACK_TO_MENU_HARD_FAIL"

                # If hearts <= 0 in non-hard (or other cases), behave like a normal retry
                if data["hearts"] <= 0:
                    print("No health left!")
                    return "RETRY"
            else:
                # local health behavior
                health -= 1
                if health <= 0:
                    print("No health left!")
                    return "RETRY"

            # Reset position after hit
            x, y = start_pos

        # Draw goal
        pg.draw.circle(screen, (50, 150, 255), goal_pos, goal_radius)
        if (x - goal_pos[0])**2 + (y - goal_pos[1])**2 <= goal_radius**2:
            print("Level Complete!")
            return "NEXT"

        # Draw hearts (show global if integer else local)
        hearts_to_draw = data["hearts"] if isinstance(data.get("hearts", "default"), int) else health
        try:
            hearts_to_draw = int(hearts_to_draw)
        except Exception:
            hearts_to_draw = max(0, health)

        for i in range(max(0, hearts_to_draw)):
            screen.blit(heart_img, (10 + i * 40, 10))  # Space hearts

        # Draw character
        screen.blit(cursor_img, (x - cursor_size // 2, y - cursor_size // 2))

        pg.display.flip()
        clock.tick(60)
