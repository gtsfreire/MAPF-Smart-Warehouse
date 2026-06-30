# Referência curta da API

Este documento resume as classes e funções públicas mais relevantes do projeto. Não é uma documentação linha a linha; o objetivo é ajudar a compreender e utilizar o código sem depender de detalhes privados.

---

## 1. Tipos principais

### `agents/types.py`

| Nome | Significado |
|---|---|
| `Position` | Tuplo `(x, y)`. |
| `State` | Tuplo `((x, y), t)`. |
| `Grid2D` | Matriz 2D de inteiros, onde `0` é livre e `1` é bloqueado. |

---

## 2. Planeamento

### `agents.a_star.a_star(...)`

```python
a_star(
    grid,
    start,
    goal,
    max_time=200,
    vertex_constraints=None,
    edge_constraints=None,
)
```

Executa A* numa grelha expandida no tempo.

Parâmetros principais:

| Parâmetro | Descrição |
|---|---|
| `grid` | Matriz 2D usada no planeamento. |
| `start` | Posição inicial `(x, y)`. |
| `goal` | Posição objetivo `(x, y)`. |
| `max_time` | Limite temporal da pesquisa. |
| `vertex_constraints` | Estados proibidos `((x, y), t)`. |
| `edge_constraints` | Transições proibidas `(from_pos, to_pos, t)`. |

Retorna:

- lista de estados `[((x, y), t), ...]` quando encontra caminho;
- `None` quando não encontra solução.

---

### `agents.prioritized_a_star.plan(...)`

Interface usada pelos modos `prioritized` e `qlearning`. Internamente delega para `a_star()`.

A coordenação prioritizada real é feita no `Engine`, não neste ficheiro.

---

## 3. Robô

### `agents.robot.Robot`

Representa um robô individual.

Campos importantes:

| Campo | Descrição |
|---|---|
| `robot_id` | Identificador do robô. |
| `start` | Posição inicial. |
| `goal` | Objetivo. |
| `current_position` | Posição atual. |
| `path` | Caminho temporal planeado. |
| `steps_taken` | Passos executados. |
| `replan_count` | Número de replans. |
| `reached_goal` | Indica se concluiu. |
| `consecutive_blocked_ticks` | Bloqueio consecutivo. |

Métodos principais:

| Método | Função |
|---|---|
| `plan_path(grid, ...)` | Calcula caminho inicial. |
| `replan(grid, ...)` | Recalcula caminho a partir da posição atual. |
| `peek_next_position()` | Consulta a próxima posição sem mover. |
| `move_one_step()` | Consome o próximo passo do caminho. |
| `stay()` | Mantém o robô parado. |
| `has_reached_goal()` | Indica se chegou ao objetivo. |
| `reset()` | Reposição para estado inicial. |

---

## 4. Ambiente

### `environment.grid.Grid`

Representa uma grelha estática.

Métodos principais:

| Método | Função |
|---|---|
| `in_bounds(x, y)` | Verifica limites. |
| `is_walkable(x, y)` | Indica se a célula pode ser atravessada. |
| `neighbors(x, y)` | Devolve vizinhos ortogonais caminháveis. |
| `set_obstacle(x, y)` | Marca obstáculo estático. |
| `set_free(x, y)` | Remove obstáculo estático. |

---

### `environment.loader.load_map(path)`

Carrega um mapa MovingAI e devolve uma instância de `Grid`.

---

### `environment.obstacles.ObstacleManager`

Gere obstáculos estáticos e dinâmicos.

Métodos principais:

| Método | Função |
|---|---|
| `add_static(x, y)` | Adiciona obstáculo permanente à grelha. |
| `remove_static(x, y)` | Remove obstáculo permanente. |
| `add_dynamic(x, y, duration, kind='generic')` | Cria obstáculo temporário. |
| `remove_dynamic(x, y)` | Remove obstáculo temporário. |
| `is_blocked(x, y)` | Indica se a célula está bloqueada. |
| `tick()` | Atualiza duração dos obstáculos dinâmicos. |
| `spawn_random_dynamic(...)` | Cria obstáculos temporários aleatórios. |
| `get_stats()` | Devolve contagens e informação resumida. |

---

## 5. Engine

### `environment.engine.Engine`

Motor central da simulação.

Criação típica:

```python
engine = Engine(map_path, metrics=metrics, conflict_resolver=resolver)
```

Métodos públicos principais:

| Método | Função |
|---|---|
| `start(num_robots=None)` | Inicia a simulação e emite evento inicial. |
| `end()` | Termina a simulação e fecha o episódio. |
| `add_robot(robot)` | Valida, planeia e adiciona um robô. |
| `remove_robot(robot_id)` | Remove um robô. |
| `get_combined_grid()` | Combina grelha estática e obstáculos dinâmicos. |
| `step()` | Executa um tick completo da simulação. |
| `get_stats()` | Devolve estatísticas finais do motor. |

Responsabilidades internas do `step()`:

1. replanear robôs afetados por obstáculos;
2. recolher intenções de movimento;
3. resolver conflitos;
4. pedir decisões ao Q-learning, se existir;
5. executar movimentos;
6. atualizar obstáculos;
7. detetar colisões;
8. emitir eventos;
9. atualizar métricas;
10. dar feedback ao resolvedor.

---

## 6. Resolução de conflitos

### `ConflictAction`

Ações possíveis:

| Ação | Significado |
|---|---|
| `WAIT` | Esperar. |
| `YIELD` | Ceder passagem. |
| `REPLAN` | Replanear. |

A política Q-learning final usa apenas `WAIT` e `YIELD`.

---

### `ConflictContext`

Observação fornecida ao resolvedor.

Campos principais:

| Campo | Descrição |
|---|---|
| `tick` | Tick atual. |
| `robot_id` | Robô em decisão. |
| `current_position` | Posição atual. |
| `intended_position` | Posição pretendida. |
| `goal` | Objetivo do robô. |
| `blocked_ticks` | Bloqueio consecutivo. |
| `others` | Posições/intenção dos outros robôs. |
| `extra` | Campo extensível. |

---

### `QLearningResolver`

Implementa Q-learning tabular.

Criação para treino:

```python
agent = QLearningResolver(training=True, seed=33)
```

Carregamento para avaliação:

```python
agent = QLearningResolver.load_json("results/final_q_table_safe.json", training=False, epsilon=0.0)
```

Métodos principais:

| Método | Função |
|---|---|
| `decide(ctx)` | Escolhe `WAIT` ou `YIELD`. |
| `observe(ctx, action, reward)` | Atualiza a Q-table durante treino. |
| `reset()` | Fecha episódio e aplica decaimento de epsilon. |
| `save_json(path)` | Guarda política. |
| `load_json(path, ...)` | Carrega política. |
| `stats()` | Devolve estatísticas do agente. |

---

### `default_reward(...)`

Função de recompensa usada no treino.

Recompensa:

- conclusão do objetivo;
- progresso em direção ao objetivo.

Penaliza:

- colisão;
- espera prolongada;
- afastamento do objetivo;
- bloqueio persistente.

---

## 7. Métricas

### `metrics.events.Event`

Representa um evento da simulação.

Tipos comuns:

- `SIM_START`;
- `SIM_END`;
- `TICK`;
- `ROBOT_SPAWN`;
- `ROBOT_WAIT`;
- `ROBOT_REPLAN`;
- `ROBOT_GOAL`;
- `COLLISION`.

---

### `metrics.simulation_metrics.SimulationMetrics`

Agrega eventos em métricas.

Métodos/propriedades principais:

| Nome | Função |
|---|---|
| `record(event)` | Processa evento. |
| `set_run_metadata(planner, seed)` | Guarda metadata. |
| `add_steps(n)` | Acumula passos. |
| `makespan` | Duração da simulação. |
| `robots_completed` | Número de robôs concluídos. |
| `success_rate` | Fração concluída. |
| `throughput` | Robôs concluídos por tick. |
| `to_dict()` | Serializa métricas. |

---

## 8. Scripts principais

### `run_headless.run(...)`

Executa uma simulação isolada e devolve um dicionário com resultados.

Uso típico via CLI:

```bash
python run_headless.py --planner prioritized --robots 30 --obstacles 10 --ticks 1000 --seed 42
```

---

### `multiple_runs.py`

Executa campanhas repetidas e gera CSVs finais.

Uso típico:

```bash
python multiple_runs.py --planner prioritized --robots 10,20,30,40,45,50 --runs 30 --initial-seed 33 --overwrite
```

---

### `train_q_learning.train(...)`

Treina a política Q-learning e grava Q-table/log.

Uso típico:

```bash
python train_q_learning.py --episodes 900 --robots 10,20,30,40,45,50 --out results/final_q_table_safe.json
```

---

### `viewer.py`

Executa a visualização gráfica com Pygame.

```bash
python viewer.py
```

---

## 9. APIs recomendadas para uso externo

Para scripts ou experiências externas, usar preferencialmente:

```python
from run_headless import run
from environment.engine import Engine
from environment.multi_robot import create_robots
from agents.conflict_resolution.q_agent import QLearningResolver
from metrics.simulation_metrics import SimulationMetrics
```

Evitar depender de métodos privados cujo nome começa por `_`, porque são detalhes internos do motor.
