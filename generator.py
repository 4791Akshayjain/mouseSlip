# level2.py
import pygame as pg
import random

# Maze / display settings
CELL_SIZE = 24        # pixel size of each cell (fits your 24x24 cursor)
REQUESTED_COLS = 40   # requested maze width in cells
REQUESTED_ROWS = 25   # requested maze height in cells

# Make cols/rows odd so DFS carving with "step 2" works nicely.
COLS = REQUESTED_COLS if REQUESTED_COLS % 2 == 1 else REQUESTED_COLS - 1
ROWS = REQUESTED_ROWS if REQUESTED_ROWS % 2 == 1 else REQUESTED_ROWS - 1

WALL = 1
PATH = 0

def generate_perfect_maze(cols=COLS, rows=ROWS, seed=None):
    """
    Generates a perfect maze (no loops) using iterative DFS (stack).
    Returns a 2D list: maze[y][x] with 0=path, 1=wall.
    """
    if seed is not None:
        random.seed(seed)

    # Start with all walls
    maze = [[WALL for _ in range(cols)] for _ in range(rows)]

    # Helper
    def in_bounds(x, y):
        return 0 <= x < cols and 0 <= y < rows

    # Start carving at (1,1) (an odd coordinate)
    start_x, start_y = 1, 1
    maze[start_y][start_x] = PATH
    stack = [(start_x, start_y)]

    # Directions: move by 2 so we carve rooms and leave walls between them
    dirs = [(2, 0), (-2, 0), (0, 2), (0, -2)]

    while stack:
        x, y = stack[-1]
        neighbors = []
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if in_bounds(nx, ny) and maze[ny][nx] == WALL:
                neighbors.append((nx, ny, dx, dy))
        if neighbors:
            # choose random neighbor and carve through the wall between
            nx, ny, dx, dy = random.choice(neighbors)
            wall_x, wall_y = x + dx // 2, y + dy // 2
            maze[wall_y][wall_x] = PATH
            maze[ny][nx] = PATH
            stack.append((nx, ny))
        else:
            stack.pop()

    # Ensure outer border is walls (in case cols/rows allow)
    for x in range(cols):
        maze[0][x] = WALL
        maze[rows - 1][x] = WALL
    for y in range(rows):
        maze[y][0] = WALL
        maze[y][cols - 1] = WALL

    return maze

def maze_to_wall_rects(maze, cell_size=CELL_SIZE, screen_size=(1024, 768)):
    """
    Convert maze grid to a list of pygame.Rect wall blocks and compute offsets
    so the maze is centered on the screen.
    Returns: wall_rects, offset_x, offset_y
    """
    rows = len(maze)
    cols = len(maze[0])
    maze_px_w = cols * cell_size
    maze_px_h = rows * cell_size
    screen_w, screen_h = screen_size

    # Center maze on screen
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

# Generate maze once when module is imported
_maze = generate_perfect_maze()
# We'll set start at the cell near (1,1) and goal near (cols-2, rows-2)
_start_cell = (1, 1)
_goal_cell = (len(_maze[0]) - 2, len(_maze) - 2)

def run_level(screen, cursor_img, clock):
    cursor_size = 24
    screen_w, screen_h = screen.get_size()

    # Convert maze to wall rects using actual screen size to center it
    wall_rects, offset_x, offset_y = maze_to_wall_rects(_maze, cell_size=CELL_SIZE, screen_size=(screen_w, screen_h))

    # Start and goal pixel positions (center of their cells)
    start_px = (offset_x + _start_cell[0] * CELL_SIZE + CELL_SIZE // 2,
                offset_y + _start_cell[1] * CELL_SIZE + CELL_SIZE // 2)
    goal_px = (offset_x + _goal_cell[0] * CELL_SIZE + CELL_SIZE // 2,
               offset_y + _goal_cell[1] * CELL_SIZE + CELL_SIZE // 2)

    # Player initial position (center of start cell)
    x, y = start_px
    dragging = False

    # Precompute goal rectangle (for a slightly easier hit)
    goal_radius = 20

    while True:
        screen.fill((30, 30, 30))

        for event in pg.event.get():
            if event.type == pg.QUIT:
                return "QUIT"

        buttons = pg.mouse.get_pressed()
        # Debug print on right-click (optional)
        if buttons[2]:
            print("Mouse:", pg.mouse.get_pos())

        mx, my = pg.mouse.get_pos()
        mouse_rect = pg.Rect(mx - 1, my - 1, 2, 2)

        # char rect used for collision and drag detection
        char_rect = pg.Rect(x - cursor_size // 2, y - cursor_size // 2, cursor_size, cursor_size)

        # Start dragging only if left mouse button and hovering sprite
        if buttons[0]:
            if not dragging and char_rect.colliderect(mouse_rect):
                dragging = True
        else:
            dragging = False

        # Move when dragging
        if dragging:
            x, y = mx, my

        # Update char rect after move for collision detection
        char_rect = pg.Rect(x - cursor_size // 2, y - cursor_size // 2, cursor_size, cursor_size)

        # Draw walls and check collisions
        for w in wall_rects:
            pg.draw.rect(screen, (200, 200, 200), w)
            if w.colliderect(char_rect):
                print("Hit a wall!")
                return "RETRY"

        # Draw goal and check reach
        pg.draw.circle(screen, (220, 40, 40), goal_px, goal_radius)
        if (x - goal_px[0]) ** 2 + (y - goal_px[1]) ** 2 <= goal_radius ** 2:
            print("Level Complete!")
            return "NEXT"

        # Draw player sprite
        screen.blit(cursor_img, (x - cursor_size // 2, y - cursor_size // 2))

        pg.display.flip()
        clock.tick(60)

# --- Utility exported for debugging if you want the raw grid/list ---
def get_maze_grid():
    """Return the 2D maze grid (list of lists) where 1=wall, 0=path."""
    return _maze

def get_flattened_list():
    """Return the maze flattened into a single list [row0..., row1..., ...]"""
    return [c for row in _maze for c in row]
