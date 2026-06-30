# MAPF Smart Warehouse

Simulador de navegação multi-agente para ambientes logísticos, desenvolvido para estudar o problema **Multi-Agent Path Finding (MAPF)** numa grelha 2D com múltiplos robôs, obstáculos estáticos, obstáculos dinâmicos temporários, resolução de conflitos e avaliação experimental.

O projeto compara três modos de navegação:

| Modo | Descrição | Papel experimental |
|---|---|---|
| `astar` | Cada robô executa A* individualmente, ignorando os restantes agentes. | Baseline ingênuo: rápido, mas inseguro. |
| `prioritized` | A* temporal com coordenação determinística no `Engine`. | Baseline principal: mais seguro, mas com esperas e replanning. |
| `qlearning` | A* temporal + política tabular local `WAIT/YIELD`. | Proposta adaptativa: reduzir waits, replans e makespan. |

> O Q-learning **não substitui** o A*. O A* continua a calcular trajetórias globais. O Q-learning apenas atua localmente quando um robô bloqueado precisa escolher entre esperar ou ceder passagem.

---

## Documentos disponíveis

| Ficheiro | Objetivo |
|---|---|
| [`USAGE.md`](USAGE.md) | Como instalar, correr o viewer, executar simulações, treinar e avaliar. |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Explicação da arquitetura, fluxo de simulação e responsabilidades dos módulos. |
| [`EXPERIMENTS.md`](EXPERIMENTS.md) | Metodologia experimental, métricas e resultados finais. |
| [`API_REFERENCE.md`](API_REFERENCE.md) | Referência curta das funções/classes públicas mais relevantes. |
| [`REPORT_NOTES.md`](REPORT_NOTES.md) | Texto e pontos prontos para adaptar ao relatório académico. |

---

## Funcionalidades principais

- Carregamento de mapas no formato MovingAI.
- Representação do ambiente como grelha 2D.
- Criação automática de robôs em fluxos opostos, para provocar cruzamentos no armazém.
- Planeamento A* temporal com ação de espera.
- Restrições de vértice e de aresta para planeamento cooperativo.
- Obstáculos dinâmicos temporários.
- Resolução determinística de conflitos no `Engine`.
- Deteção de colisões, bloqueios, waits, replans e conclusão de objetivos.
- Política Q-learning tabular conservadora com ações `WAIT` e `YIELD`.
- Execução visual com Pygame.
- Execução headless para experiências reprodutíveis.
- Exportação CSV com métricas detalhadas.
- Treino e avaliação separados do Q-learning.
- Testes automatizados de grelha, obstáculos, métricas e regressões do motor.

---

## Início rápido

### 1. Preparar ambiente

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Instalar dependências principais:

```bash
python -m pip install --upgrade pip
python -m pip install pygame pytest
```

### 2. Correr viewer

```bash
python viewer.py
```

### 3. Correr uma simulação headless

```bash
python run_headless.py --planner prioritized --robots 20 --obstacles 10 --ticks 1000 --seed 42
```

### 4. Avaliar Q-learning final

```bash
python run_headless.py \
  --planner qlearning \
  --q-table results/final_q_table_safe.json \
  --robots 30 \
  --obstacles 10 \
  --ticks 1000 \
  --seed 42
```

---

## Estrutura principal

```text
mapf-smart-warehouse/
├── agents/
│   ├── a_star.py
│   ├── prioritized_a_star.py
│   ├── robot.py
│   └── conflict_resolution/
├── config/
│   └── settings.py
├── environment/
│   ├── engine.py
│   ├── grid.py
│   ├── loader.py
│   ├── multi_robot.py
│   └── obstacles.py
├── metrics/
│   ├── events.py
│   └── simulation_metrics.py
├── scenarios/
├── results/
├── tests/
├── run_headless.py
├── multiple_runs.py
├── train_q_learning.py
└── viewer.py
```

---

## Métricas mais importantes

| Métrica | Significado |
|---|---|
| `completion_rate` | Percentagem de robôs que chegaram ao objetivo. |
| `completion_success` | Indica se todos os robôs chegaram ao objetivo. |
| `collision_free` | Indica se a execução terminou sem colisões. |
| `safe_success` | Verdadeiro apenas se todos chegaram e não houve colisões. |
| `total_collisions` | Número de colisões registadas. |
| `actual_waits` | Número de esperas efetivas por bloqueio. |
| `total_replans` | Número de replaneamentos efetuados. |
| `makespan` | Número de ticks da execução. |
| `average_steps_per_robot` | Média de passos por robô. |

A métrica mais importante para segurança MAPF é `safe_success`, não apenas `completion_rate`.

---

## Resultados finais resumidos

Médias globais das campanhas finais com 10 obstáculos dinâmicos, 30 runs por configuração e seeds 33-62:

| Planner | Completion médio | Safe success médio | Colisões médias | Waits médios | Replans médios | Makespan médio |
|---|---:|---:|---:|---:|---:|---:|
| A* simples | 1.000 | 0.067 | 54.82 | 0.0 | 0.0 | 192.9 |
| Prioritized A* | 0.986 | 0.489 | 1.45 | 582.7 | 199.7 | 391.5 |
| Q-learning seguro | 0.999 | 0.578 | 1.14 | 92.1 | 38.0 | 223.8 |

Interpretação resumida:

- O A* simples chega rapidamente aos objetivos, mas colide muito.
- O Prioritized A* reduz drasticamente as colisões, mas aumenta waits, replans e makespan.
- O Q-learning seguro melhora o desempenho médio, sobretudo reduzindo waits, replans e makespan.

---

## Testes

```bash
pytest -q
```

Na versão final limpa, a suíte de testes deve passar sem erros.
