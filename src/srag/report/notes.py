"""Fixed methodology notes shown in every report (summary of docs/METRICS.md)."""

from srag.config import DAILY_CHART_DAYS, MONTHLY_CHART_MONTHS

LIMITATIONS: tuple[str, ...] = (
    "Fonte dos dados: Open DATASUS (SRAG). A data de referência é o último caso com início de "
    "sintomas na base, não a data de hoje, porque a base pública é publicada com atraso.",
    "Atraso de notificação: os casos mais recentes entram no sistema aos poucos. Por isso, os "
    "últimos dias ficam de fora das taxas e aparecem como incompletos no gráfico diário.",
    "Variação de casos: compara a janela atual com a janela anterior de mesmo tamanho. Fica "
    "indefinida quando a janela anterior não teve casos.",
    "Mortalidade: considera só os casos com desfecho já conhecido. Casos ainda em aberto não "
    "entram na conta, e a completude mostra quanto da janela foi usada.",
    "UTI: a base não traz a capacidade de leitos, então não é possível calcular a ocupação real. "
    "A proporção mostrada é uma aproximação (proxy) da pressão sobre a UTI.",
    "Vacinação: a base só tem pessoas notificadas com SRAG, não a população. As proporções "
    "mostradas são o status vacinal entre os casos, e não a cobertura vacinal.",
    "Amostras pequenas: resultados calculados sobre poucos registros são marcados como "
    "instáveis e devem ser lidos com cautela.",
    f"Gráficos: casos por dia nos últimos {DAILY_CHART_DAYS} dias e por mês nos últimos "
    f"{MONTHLY_CHART_MONTHS} meses, sempre até a data de referência.",
    "Os números são calculados por código, e o modelo de linguagem apenas os explica. "
    "Cada número do texto e cada link citado são verificados automaticamente antes da "
    "publicação.",
)
