# Metodologia experimental e resultados finais

Este documento descreve a metodologia experimental, as métricas usadas e os resultados finais do projeto **MAPF Smart Warehouse**.

---

## 1. Objetivo experimental

O objetivo experimental foi comparar três estratégias de navegação multi-agente:

1. **A* simples**, como baseline ingênuo sem coordenação segura;
2. **Prioritized A***, como baseline determinístico principal;
3. **Q-learning seguro**, como política local adaptativa sobre o baseline A*.

A comparação avalia:

- taxa de conclusão;
- segurança;
- colisões;
- esperas;
- replaneamentos;
- makespan;
- passos médios por robô.

---

## 2. Configuração das campanhas finais

Configuração usada nos CSVs finais:

| Parâmetro | Valor |
|---|---:|
| Mapa | `warehouse-10-20-10-2-1.map` |
| Planners | `astar`, `prioritized`, `qlearning` |
| Quantidades de robôs | 10, 20, 30, 40, 45, 50 |
| Runs por configuração | 30 |
| Seeds | 33-62 |
| Obstáculos dinâmicos solicitados | 10 |
| Limite de ticks | 1000 |
| Política Q-learning | `wait_yield_safe`, versão 3 |
| Ações Q-learning | `WAIT`, `YIELD` |

Cada CSV de avaliação contém:

```text
6 quantidades de robôs × 30 runs = 180 execuções
```

---

## 3. Ficheiros finais

| Ficheiro | Conteúdo |
|---|---|
| `results/final_astar_naive.csv` | Avaliação do A* simples. |
| `results/final_prioritized_baseline.csv` | Avaliação do baseline priorizado. |
| `results/final_qlearning_safe_eval.csv` | Avaliação greedy do Q-learning. |
| `results/final_qlearning_training_log.csv` | Log de treino por episódio. |
| `results/final_q_table_safe.json` | Q-table final treinada. |

---

## 4. Separação entre treino e avaliação

O Q-learning foi treinado antes da avaliação final.

Na avaliação final:

```text
q_training = False
q_updates = 0
q_epsilon = 0
```

Isto significa que a Q-table foi usada em modo congelado, sem aprendizagem online e sem exploração aleatória.

---

## 5. Definições das métricas

### Conclusão

```text
completion_rate = robots_completed / robots_spawned
completion_success = robots_completed == robots_spawned
```

### Segurança

```text
collision_free = total_collisions == 0
safe_success = completion_success and collision_free
safe_success_rate = 1.0 se safe_success, senão 0.0
```

Numa campanha, a média de `safe_success_rate` é a proporção de runs totalmente seguras.

### Tempo

```text
makespan = tick final - tick inicial
average_completion_time = média do tempo até conclusão dos robôs concluídos
throughput = robots_completed / makespan
```

### Passos

```text
total_steps = soma de Robot.steps_taken
average_steps_per_robot = total_steps / robots_spawned
```

`total_steps` inclui movimentos normais e movimentos manuais de cedência (`YIELD`).

### Coordenação

| Métrica | Significado |
|---|---|
| `blocked_intents` | Movimentos pretendidos que foram bloqueados. |
| `actual_waits` | Esperas efetivamente registadas. |
| `total_replans` | Replaneamentos acumulados. |
| `max_consecutive_blocked` | Maior sequência de ticks bloqueado. |

---

## 6. Resultados por planner

### 6.1 A* simples

| Robôs | Completion | Safe success | Colisões médias | Makespan médio |
|---:|---:|---:|---:|---:|
| 10 | 1.000 | 0.400 | 0.87 | 186.3 |
| 20 | 1.000 | 0.000 | 19.93 | 191.3 |
| 30 | 1.000 | 0.000 | 37.67 | 194.8 |
| 40 | 1.000 | 0.000 | 69.33 | 195.5 |
| 45 | 1.000 | 0.000 | 101.87 | 194.0 |
| 50 | 1.000 | 0.000 | 99.27 | 195.6 |

Interpretação: o A* simples tem conclusão total, mas gera muitas colisões. Serve para demonstrar que A* individual não resolve MAPF seguro.

---

### 6.2 Prioritized A*

| Robôs | Completion | Safe success | Colisões | Waits | Replans | Makespan |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 0.993 | 0.967 | 0.00 | 66.8 | 22.5 | 213.9 |
| 20 | 0.990 | 0.800 | 0.13 | 225.4 | 76.0 | 283.7 |
| 30 | 0.987 | 0.600 | 0.27 | 463.3 | 156.7 | 367.9 |
| 40 | 0.985 | 0.300 | 1.13 | 715.5 | 245.0 | 434.5 |
| 45 | 0.988 | 0.233 | 2.67 | 650.9 | 226.4 | 405.1 |
| 50 | 0.975 | 0.033 | 4.50 | 1374.2 | 471.6 | 643.7 |

Interpretação: o baseline priorizado reduz drasticamente colisões face ao A* simples, mas sofre com esperas e replans em maior densidade.

---

### 6.3 Q-learning seguro

| Robôs | Completion | Safe success | Colisões | Waits | Replans | Makespan |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 1.000 | 1.000 | 0.00 | 1.6 | 0.8 | 186.5 |
| 20 | 1.000 | 0.900 | 0.10 | 8.4 | 4.0 | 194.3 |
| 30 | 0.996 | 0.733 | 0.33 | 148.1 | 53.2 | 256.3 |
| 40 | 1.000 | 0.233 | 1.87 | 61.4 | 31.1 | 207.4 |
| 45 | 1.000 | 0.367 | 1.87 | 68.0 | 36.2 | 209.9 |
| 50 | 0.996 | 0.233 | 2.70 | 265.4 | 102.4 | 288.2 |

Interpretação: o Q-learning seguro melhora o desempenho médio, sobretudo em waits, replans e makespan. A melhoria em segurança não é uniforme em todos os cenários; por exemplo, em 40 robôs o `safe_success` é inferior ao baseline priorizado, mas em 45 e 50 robôs é superior.

---

## 7. Comparação global

| Métrica | A* simples | Prioritized A* | Q-learning seguro |
|---|---:|---:|---:|
| Completion médio | 1.000 | 0.986 | 0.999 |
| Safe success médio | 0.067 | 0.489 | 0.578 |
| Colisões médias | 54.82 | 1.45 | 1.14 |
| Waits médios | 0.0 | 582.7 | 92.1 |
| Replans médios | 0.0 | 199.7 | 38.0 |
| Makespan médio | 192.9 | 391.5 | 223.8 |
| Steps médios/robô | 157.0 | 158.0 | 159.9 |

---

## 8. Conclusões experimentais

Conclusões principais:

1. O A* simples apresenta elevada conclusão, mas falha em segurança devido ao número elevado de colisões.
2. O Prioritized A* reduz drasticamente as colisões, mas aumenta esperas, replaneamentos e makespan.
3. O Q-learning seguro melhora o desempenho médio do sistema, aumentando o `safe_success` médio e reduzindo de forma expressiva waits, replans e makespan.
4. O Q-learning não melhora uniformemente todos os cenários, mas apresenta melhor comportamento médio global.
5. A ligeira subida em `average_steps_per_robot` no Q-learning é aceitável, pois resulta de movimentos de cedência que reduzem bloqueios e tempo total.

Formulação recomendada para o relatório:

> A política Q-learning segura, limitada às ações `WAIT` e `YIELD`, aumentou o `safe_success` médio de 48.9% para 57.8%, reduziu os waits médios de 582.7 para 92.1, os replaneamentos médios de 199.7 para 38.0 e o makespan médio de 391.5 para 223.8, mantendo uma taxa de conclusão praticamente total.

---

## 9. Q-table final

Metadados principais de `final_q_table_safe.json`:

| Campo | Valor |
|---|---:|
| `version` | 3 |
| `policy` | `wait_yield_safe` |
| ações | `wait`, `yield` |
| `alpha` | 0.12 |
| `gamma` | 0.85 |
| `epsilon_min` | 0.01 |
| `epsilon_decay` | 0.997 |
| estados guardados | 514 |
| decisões de treino | 47 764 |
| updates | 47 764 |

Contagem de ações no treino:

```text
WAIT  = 34 975
YIELD = 12 789
```

---

## 10. Limitações metodológicas

### Reprodutibilidade dos obstáculos

A criação dos robôs usa seed controlada. Dependendo da versão do código, a criação dos obstáculos dinâmicos pode usar o gerador global `random`. Se for necessário garantir reprodutibilidade bit-a-bit, recomenda-se fixar também a seed antes de chamar `spawn_random_dynamic()` ou adaptar o `ObstacleManager` para receber um RNG explícito.

### Baseline priorizado

O baseline priorizado é heurístico. Não é equivalente a CBS/ECBS e não garante solução ótima ou completude em todos os cenários MAPF.

### Q-learning tabular

A política é tabular e usa um estado discreto compacto. Isto torna o modelo simples e interpretável, mas limita a capacidade de generalização para mapas muito diferentes.

### Variância entre runs

Como os cenários dependem de posições iniciais, objetivos e obstáculos, uma única execução pode ter resultados muito diferentes da média. Por isso, a análise deve usar campanhas com múltiplas seeds.
