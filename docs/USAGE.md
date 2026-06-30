# Guia de utilização

Este documento descreve como executar o projeto **MAPF Smart Warehouse** em modo gráfico, em modo headless, em campanhas repetidas e em treino/avaliação Q-learning.

Todos os comandos devem ser executados na raiz do projeto.

---

## 1. Requisitos

- Python 3.10 ou superior.
- `pygame` para o visualizador gráfico.
- `pytest` para correr os testes.

Instalação recomendada:

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

Instalar dependências:

```bash
python -m pip install --upgrade pip
python -m pip install pygame pytest
```

---

## 2. Configuração global

O ficheiro `config/settings.py` contém valores usados por defeito, especialmente pelo viewer.

Parâmetros principais:

| Definição | Descrição |
|---|---|
| `PLANNER` | Planner usado pelo viewer: `astar`, `prioritized` ou `qlearning`. |
| `MAP_PATH` | Caminho do mapa MovingAI. |
| `NUM_ROBOTS` | Número de robôs criados no viewer. |
| `DYNAMIC_OBSTACLES` | Número de obstáculos dinâmicos iniciais. |
| `MAX_TICKS` | Limite máximo de ticks nas experiências. |
| `ROBOT_COUNTS` | Lista de quantidades de robôs usadas nas campanhas. |
| `RUNS_PER_SEED` | Número de runs por configuração. |
| `TRAIN_EPISODES` | Número predefinido de episódios de treino. |
| `Q_TABLE_PATH` | Caminho predefinido da Q-table. |

> Os argumentos de linha de comandos substituem estes defaults na maioria dos scripts. Para experiências finais, prefira usar CLI em vez de alterar o ficheiro manualmente.

---

## 3. Viewer gráfico

```bash
python viewer.py
```

O viewer cria o mapa, os obstáculos dinâmicos, os robôs e executa a simulação tick a tick com Pygame.

Controlos:

| Tecla | Ação |
|---|---|
| `SPACE` | Pausar ou retomar. |
| `R` | Reiniciar o cenário. |
| `ESC` | Sair. |

### Usar Q-learning no viewer

No ficheiro `config/settings.py`:

```python
PLANNER = "qlearning"
Q_TABLE_PATH = Path("results/final_q_table_safe.json")
```

Se a tabela final tiver outro nome, atualize `Q_TABLE_PATH` ou copie o ficheiro:

Windows PowerShell:

```powershell
Copy-Item results\final_q_table_safe.json results\q_table_safe.json
```

Linux/macOS:

```bash
cp results/final_q_table_safe.json results/q_table_safe.json
```

---

## 4. Execução headless

O script `run_headless.py` executa uma única simulação sem interface gráfica.

Formato geral:

```bash
python run_headless.py [opções]
```

Argumentos principais:

| Argumento | Descrição |
|---|---|
| `--map PATH` | Caminho para o mapa. |
| `--planner {astar,prioritized,qlearning}` | Planner usado. |
| `--robots N` | Número de robôs solicitado. |
| `--obstacles N` | Obstáculos dinâmicos iniciais. |
| `--ticks N` | Limite máximo de ticks. |
| `--seed N` | Seed usada na criação dos robôs e no QAgent. |
| `--output PATH` | CSV de saída. |
| `--q-table PATH` | Q-table usada no modo `qlearning`. |
| `--no-csv` | Não grava CSV. |
| `--no-early-stop` | Continua até `max_ticks`, mesmo que todos concluam. |
| `--allow-online-qlearning` | Permite treino online; apenas para debug, não para resultados finais. |

### Exemplos

A* simples:

```bash
python run_headless.py --planner astar --robots 20 --obstacles 10 --ticks 1000 --seed 42
```

Prioritized A*:

```bash
python run_headless.py --planner prioritized --robots 30 --obstacles 10 --ticks 1000 --seed 42
```

Q-learning em avaliação greedy:

```bash
python run_headless.py \
  --planner qlearning \
  --q-table results/final_q_table_safe.json \
  --robots 30 \
  --obstacles 10 \
  --ticks 1000 \
  --seed 42
```

> Não use `--allow-online-qlearning` para resultados finais, porque isso mistura treino e avaliação.

---

## 5. Campanhas repetidas

O script `multiple_runs.py` executa várias simulações e grava um CSV agregável.

Formato geral:

```bash
python multiple_runs.py [opções]
```

Argumentos principais:

| Argumento | Descrição |
|---|---|
| `--planner` | Planner a avaliar. |
| `--robots 10,20,30` | Lista de quantidades de robôs. |
| `--obstacles N` | Obstáculos dinâmicos iniciais. |
| `--ticks N` | Limite de ticks por run. |
| `--runs N` | Número de seeds por configuração. |
| `--initial-seed N` | Primeira seed. |
| `--output PATH` | CSV final. |
| `--q-table PATH` | Q-table no modo `qlearning`. |
| `--overwrite` | Substitui CSV existente. |

### Campanhas finais recomendadas

A* simples:

```bash
python multiple_runs.py \
  --planner astar \
  --robots 10,20,30,40,45,50 \
  --obstacles 10 \
  --ticks 1000 \
  --runs 30 \
  --initial-seed 33 \
  --output results/final_astar_naive.csv \
  --overwrite
```

Prioritized A*:

```bash
python multiple_runs.py \
  --planner prioritized \
  --robots 10,20,30,40,45,50 \
  --obstacles 10 \
  --ticks 1000 \
  --runs 30 \
  --initial-seed 33 \
  --output results/final_prioritized_baseline.csv \
  --overwrite
```

Q-learning:

```bash
python multiple_runs.py \
  --planner qlearning \
  --q-table results/final_q_table_safe.json \
  --robots 10,20,30,40,45,50 \
  --obstacles 10 \
  --ticks 1000 \
  --runs 30 \
  --initial-seed 33 \
  --output results/final_qlearning_safe_eval.csv \
  --overwrite
```

---

## 6. Treino do Q-learning

O script `train_q_learning.py` treina a política tabular `WAIT/YIELD`.

Formato geral:

```bash
python train_q_learning.py [opções]
```

Argumentos principais:

| Argumento | Descrição |
|---|---|
| `--episodes` | Número de episódios de treino. |
| `--robots` | Lista curricular de quantidades de robôs. |
| `--obstacles` | Obstáculos dinâmicos iniciais. |
| `--ticks` | Limite máximo por episódio. |
| `--seed` | Seed base do treino. |
| `--out` | Ficheiro JSON da Q-table. |
| `--log` | CSV com log por episódio. |
| `--alpha` | Taxa de aprendizagem. |
| `--gamma` | Fator de desconto. |
| `--epsilon` | Exploração inicial. |
| `--epsilon-min` | Exploração mínima. |
| `--epsilon-decay` | Decaimento da exploração. |

Treino final recomendado:

```bash
python train_q_learning.py \
  --episodes 900 \
  --robots 10,20,30,40,45,50 \
  --obstacles 10 \
  --ticks 1000 \
  --seed 33 \
  --out results/final_q_table_safe.json \
  --log results/final_qlearning_training_log.csv
```

---

## 7. Mapas

O loader aceita mapas no formato MovingAI:

```text
type octile
height 4
width 6
map
..@@..
......
.T..O.
..##..
```

Caracteres tratados como obstáculos:

```text
@ O T #
```

Os restantes caracteres são tratados como células livres.

Convenção interna:

```text
posição = (x, y) = (coluna, linha)
grid[y][x]
```

---

## 8. CSV e Excel em português

Os CSVs são gravados com vírgula `,` como separador.

Em Excel configurado para português, o ficheiro pode aparecer todo numa só coluna. Para abrir corretamente:

```text
Excel → Dados → De Texto/CSV → escolher ficheiro → Delimitador: Vírgula
```

Alternativas:

- abrir no Google Sheets;
- importar com Pandas;
- converter o separador para `;` se for necessário entregar a alguém que use Excel PT.

---

## 9. Resolução de problemas

### `ModuleNotFoundError: No module named 'pygame'`

```bash
python -m pip install pygame
```

### Q-table não encontrada

Passe explicitamente:

```bash
--q-table results/final_q_table_safe.json
```

ou ajuste `Q_TABLE_PATH` em `config/settings.py`.

### CSV já existe

Use outro caminho ou adicione:

```bash
--overwrite
```

### Poucos robôs são criados

O sistema só aceita robôs com origem, destino e caminho válidos. Reduza o número de robôs, reduza obstáculos ou use um mapa com mais células livres nas zonas laterais.

### Viewer lento

Reduza `NUM_ROBOTS`, reduza `DYNAMIC_OBSTACLES` ou aumente `MOVE_DELAY` em `config/settings.py`.
