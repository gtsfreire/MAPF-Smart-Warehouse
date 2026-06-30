# Notas para o relatório

Este documento contém texto e pontos que podem ser adaptados diretamente para o relatório académico.

---

## 1. Descrição geral do projeto

O projeto **MAPF Smart Warehouse** consiste no desenvolvimento de um simulador de navegação multi-agente em ambientes logísticos, com foco no problema **Multi-Agent Path Finding (MAPF)**. O sistema representa um armazém como uma grelha bidimensional, onde vários robôs devem deslocar-se de uma posição inicial até um objetivo, evitando obstáculos estáticos, obstáculos dinâmicos e conflitos com outros robôs.

A solução permite comparar diferentes estratégias de navegação, desde uma abordagem A* individual sem coordenação até uma abordagem prioritizada com resolução determinística de conflitos e uma política local baseada em Q-learning. O objetivo principal é avaliar de que forma mecanismos de coordenação e aprendizagem podem melhorar a segurança e eficiência da navegação multi-agente.

---

## 2. Problema abordado

O problema tratado enquadra-se no domínio MAPF, em que vários agentes partilham o mesmo ambiente e devem encontrar trajetórias que permitam atingir objetivos individuais sem colisões. Este problema é particularmente relevante em armazéns inteligentes, onde robôs móveis transportam mercadorias, atravessam corredores comuns e podem gerar congestionamento em zonas estreitas.

Uma solução baseada apenas em A* individual não é suficiente, porque cada robô planeia ignorando os restantes agentes. Como consequência, dois robôs podem tentar ocupar a mesma célula no mesmo tick ou trocar de posição simultaneamente, originando colisões. Assim, torna-se necessária uma camada de coordenação multi-agente.

---

## 3. Arquitetura resumida

A arquitetura do sistema foi organizada em módulos independentes. O ambiente é representado por uma grelha carregada a partir de mapas no formato MovingAI, contendo obstáculos estáticos e obstáculos dinâmicos temporários. Cada robô possui uma posição inicial, um objetivo e uma trajetória calculada através de A*. O motor de simulação coordena a execução temporal dos robôs, deteta conflitos, aplica estratégias de espera, cedência de passagem e replaneamento, e emite eventos para o sistema de métricas.

Foram implementados três modos de funcionamento. No modo A* simples, cada robô planeia de forma independente, servindo como baseline ingênuo. No modo Prioritized A*, o motor adiciona uma camada determinística de coordenação para reduzir colisões. No modo Q-learning, o planeamento global continua a ser feito por A*, mas uma política tabular decide localmente entre esperar e ceder passagem quando ocorre um bloqueio.

---

## 4. A* simples

O A* simples foi usado como baseline inicial. Neste modo, cada robô calcula o seu caminho individualmente e executa a trajetória sem considerar os restantes agentes como obstáculos móveis. Por isso, o sistema pode apresentar uma taxa de conclusão elevada, mesmo registando muitas colisões. Esta abordagem é útil para demonstrar que o A* individual, embora eficiente para navegação de um único agente, não garante segurança em cenários multi-agente.

---

## 5. Prioritized A*

O modo Prioritized A* mantém o A* como algoritmo de planeamento, mas adiciona coordenação no motor de simulação. O sistema calcula intenções de movimento, identifica conflitos, estabelece prioridades e decide que robôs podem avançar em cada tick. Robôs bloqueados podem esperar, ceder passagem ou ser replaneados. Esta abordagem reduz significativamente as colisões face ao A* simples, mas pode aumentar o número de waits, replans e o makespan, especialmente em cenários congestionados.

---

## 6. Q-learning seguro

A política Q-learning foi integrada como uma camada local de decisão. O agente não calcula trajetórias completas; essa responsabilidade continua a pertencer ao A*. O Q-learning atua apenas quando um robô fica bloqueado, escolhendo entre duas ações: `WAIT`, que mantém o robô parado, e `YIELD`, que tenta deslocá-lo para uma célula lateral segura.

Esta restrição foi uma decisão arquitetural importante. Versões anteriores em que o agente podia escolher `REPLAN` revelaram-se instáveis, originando excesso de replaneamentos. A versão final mantém o replanning como mecanismo determinístico do motor e usa Q-learning apenas para decisões locais de espera ou cedência.

---

## 7. Metodologia experimental

A avaliação experimental comparou três abordagens: A* simples, Prioritized A* e Q-learning seguro. Foram testados cenários com 10, 20, 30, 40, 45 e 50 robôs, 10 obstáculos dinâmicos e um limite de 1000 ticks por execução. Para cada configuração foram realizadas 30 execuções com seeds controlados entre 33 e 62.

As principais métricas analisadas foram `completion_rate`, `safe_success`, colisões, waits, replans, makespan e passos médios por robô. A métrica `safe_success` foi definida como verdadeira apenas quando todos os robôs chegam ao objetivo e não ocorre qualquer colisão, sendo por isso mais rigorosa do que a simples taxa de conclusão.

---

## 8. Resultados finais resumidos

A comparação global mostrou que o A* simples apresenta conclusão praticamente total, mas falha em segurança devido ao elevado número de colisões. O Prioritized A* reduz drasticamente as colisões, mas introduz custos significativos de espera e replaneamento. O Q-learning seguro melhorou o desempenho médio do sistema, aumentando o `safe_success` médio e reduzindo significativamente waits, replans e makespan.

Valores globais médios:

| Planner | Completion médio | Safe success médio | Colisões médias | Waits médios | Replans médios | Makespan médio |
|---|---:|---:|---:|---:|---:|---:|
| A* simples | 1.000 | 0.067 | 54.82 | 0.0 | 0.0 | 192.9 |
| Prioritized A* | 0.986 | 0.489 | 1.45 | 582.7 | 199.7 | 391.5 |
| Q-learning seguro | 0.999 | 0.578 | 1.14 | 92.1 | 38.0 | 223.8 |

---

## 9. Conclusão para o relatório

Os resultados demonstram que A* individual não é adequado como solução MAPF segura, apesar de apresentar elevada taxa de conclusão. O baseline Prioritized A* melhora fortemente a segurança, mas degrada o desempenho temporal em cenários densos devido ao aumento de waits e replaneamentos. A política Q-learning segura, limitada às ações `WAIT` e `YIELD`, melhora o desempenho médio do sistema, reduzindo waits, replans e makespan, mantendo uma taxa de conclusão praticamente total.

A contribuição principal do projeto não está em substituir o planeamento A*, mas em demonstrar que uma camada local de aprendizagem por reforço pode complementar uma estratégia determinística de coordenação, tornando a navegação multi-agente mais eficiente em ambientes logísticos congestionados.

---

## 10. Limitações

Limitações a mencionar:

- O baseline priorizado é heurístico e não garante otimalidade global.
- O Q-learning é tabular e depende de uma representação discreta do estado.
- A política foi treinada e avaliada num mapa específico.
- A melhoria do Q-learning não é uniforme em todas as densidades.
- Cenários mais realistas poderiam incluir tarefas pickup/dropoff, múltiplos mapas e obstáculos dinâmicos persistentes.

---

## 11. Trabalho futuro

Possíveis melhorias:

- Implementar CBS ou ECBS como baseline MAPF mais avançado.
- Treinar Q-learning em múltiplos mapas.
- Enriquecer o estado do agente com informação sobre corredores, densidade local e histórico de replans.
- Avaliar Deep Q-learning ou outras políticas de aprendizagem por reforço.
- Introduzir tarefas logísticas completas, como recolha e entrega de mercadorias.
- Melhorar a reprodutibilidade da geração de obstáculos dinâmicos com RNG explícito.
- Criar cenários com diferentes layouts de armazém.
