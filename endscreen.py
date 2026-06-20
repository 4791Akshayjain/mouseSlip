import pygame as pg
import sys
from save_utils import load_save



FONT_BIG_SIZE = 72
FONT_MED_SIZE = 36
FONT_SMALL_SIZE = 24

BG_COLOR = (18, 18, 18)
ACCENT_COLOR = (102, 204, 255)
TEXT_FILL = (255, 255, 255)
SHADOW_COLOR = (0, 0, 0)

PADDING_TOP = 120


def draw_gta_text(surface, text, font, centerx, y):
   
    # shadow
    offset_range = [(-4, -4), (4, -4), (-4, 4), (4, 4)]
    for ox, oy in offset_range:
        s = font.render(text, True, SHADOW_COLOR)
        r = s.get_rect()
        r.centerx = centerx + ox
        r.y = y + oy
        surface.blit(s, r)
    # colored outline (one pass)
    outline = font.render(text, True, ACCENT_COLOR)
    orc = outline.get_rect()
    orc.centerx = centerx
    orc.y = y - 2
    surface.blit(outline, orc)
    # main fill
    main = font.render(text, True, TEXT_FILL)
    mr = main.get_rect()
    mr.centerx = centerx
    mr.y = y
    surface.blit(main, mr)


def run_level(screen, cursor_img, clock):
    # screen must be already created by main
    screen_w, screen_h = screen.get_size()

    # fonts
    try:
        font_big = pg.font.SysFont(None, FONT_BIG_SIZE)
        font_med = pg.font.SysFont(None, FONT_MED_SIZE)
        font_small = pg.font.SysFont(None, FONT_SMALL_SIZE)
    except Exception:
        pg.font.init()
        font_big = pg.font.SysFont(None, FONT_BIG_SIZE)
        font_med = pg.font.SysFont(None, FONT_MED_SIZE)
        font_small = pg.font.SysFont(None, FONT_SMALL_SIZE)

    data = load_save()
    best_times = data.get("best_times", {}) or {}
    difficulty = data.get("difficulty", None)
    title_text = "MISSION COMPLETED RESPECT ++"
    
    # prepare list of level times sorted by level number
    times_display = []
    for lvl in range(1, 13):
        t = best_times.get(str(lvl))
        if t is None:
            times_display.append((lvl, None))
        else:
            times_display.append((lvl, float(t)))

    # compute total (sum of available best times)
    total = 0.0
    any_time = False
    for _, t in times_display:
        if t is not None:
            total += t
            any_time = True

    if not any_time:
        total = None

    # main loop for the end-screen
    while True:
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                return "QUIT"
            if ev.type == pg.KEYDOWN or (ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1):
                # any key or left-click returns to menu / quit
                return "QUIT"

        screen.fill(BG_COLOR)

        # Title
        draw_gta_text(screen, title_text, font_big, screen_w // 2, PADDING_TOP)

        # Subtitle
        subtitle_y = PADDING_TOP + FONT_BIG_SIZE + 20
        sub = font_med.render(f"Level Completion time ( Difficulty: {difficulty} ) ", True, TEXT_FILL)
        sub_r = sub.get_rect()
        sub_r.centerx = screen_w // 2
        sub_r.y = subtitle_y
        screen.blit(sub, sub_r)

        # Draw times as a two-column list
        list_start_y = subtitle_y + FONT_MED_SIZE + 10
        left_x = screen_w // 2 - 220
        right_x = screen_w // 2 + 40
        row_h = FONT_SMALL_SIZE + 8

        for i, (lvl, t) in enumerate(times_display):
            y = list_start_y + i * row_h
            lvl_text = f"Level {lvl}:"
            if t is None:
                time_text = "--"
            else:
                time_text = f"{t:.2f}s"

            lsurf = font_small.render(lvl_text, True, TEXT_FILL)
            lrect = lsurf.get_rect()
            lrect.topleft = (left_x, y)
            screen.blit(lsurf, lrect)

            tsurf = font_small.render(time_text, True, TEXT_FILL)
            trect = tsurf.get_rect()
            trect.topleft = (right_x, y)
            screen.blit(tsurf, trect)

    
        # instruction
        # footer message
        footer = font_small.render("Thank you for playing my game", True, (180, 180, 180))
        fr = footer.get_rect()
        fr.centerx = screen_w // 2
        fr.y = screen_h - 65
        screen.blit(footer, fr)

        instr = font_small.render("Press any key or click to exit", True, (200, 200, 200))
        ir = instr.get_rect()
        ir.centerx = screen_w // 2
        ir.y = screen_h - 45
        screen.blit(instr, ir)

        # draw cursor image
        try:
            screen.blit(cursor_img, (screen_w - 40, screen_h - 40))
        except Exception:
            pass

        pg.display.flip()
        clock.tick(30)
