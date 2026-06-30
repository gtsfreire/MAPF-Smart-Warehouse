from pathlib import Path

#------------------------------------------------------------------
# ALGORITHM

PLANNER = "prioritized"  # "astar", "prioritized", "qlearning"

#------------------------------------------------------------------
# Configurações do ambiente

MAP_PATH = Path("scenarios/warehouse-10-20-10-2-1.map")
NUM_ROBOTS = 100
DYNAMIC_OBSTACLES = 50
MOVE_DELAY = 50       # ms entre passos
MAX_WIDTH = 1500
MAX_HEIGHT = 1000
# ----------------------------------------------------------------
# EXPERIMENTOS
ROBOT_COUNTS = [10, 20, 30, 40, 45, 50]  # Números de robôs a testar
MAX_TICKS = 1000                 # Duração máxima da simulação
RUNS_PER_SEED = 30               # Repetições por configuração
TRAIN_EPISODES = 900             # Episódios para treinar o Q-Learning
TRAIN_ROBOTS = [30, 40, 45, 50]  # Currículo de robôs usado no treino
TRAIN_OBSTACLES = 10             # Deve bater com o baseline principal
Q_TABLE_PATH = Path("results/q_table_safe.json")

COLOUR_OBSTACLE  = (40,  40,  40)
COLOUR_FREE      = (240, 240, 240)
COLOUR_GRID      = (180, 180, 180)
COLOUR_START     = (0,   200,  80)
COLOUR_GOAL      = (220,  50,  50)
COLOUR_DYNAMIC   = (180, 100,  20)
COLOUR_COLLISION = (255,   0,   0)
COLOUR_COMPLETED = (255, 220,   0)
COLOUR_TEXT      = (10,   10,  10)
COLOUR_HUD_BG    = (255, 255, 255)

ROBOT_COLOURS = [
    (0,   100, 255),
    (255, 100,   0),
    (0,   180, 120),
    (180,   0, 200),
    (0,   200, 220),
]

PLANNER_LABELS = {
    "astar": "A*",
    "prioritized": "A* + Resolução de Conflitos",
    "qlearning": "Q-Learning",
}