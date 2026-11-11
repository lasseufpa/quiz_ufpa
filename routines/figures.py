"""Figuras em SVG para os guias de uso.

São desenhadas a partir das constantes reais do jogo (`routines/constants.py`),
então o guia nunca fica desatualizado — se a fórmula de pontuação mudar, o
desenho muda junto. Nada é gravado em disco: o SVG vai embutido no HTML.
"""

import math

from routines import constants

# Mesmo epsilon de `game_logic._sinc`: evita 0/0 no primeiro instante.
_EPS = 1e-5


def _sinc(x):
    """Sinc normalizado — a mesma função usada para pontuar a rapidez."""
    return math.sin(math.pi * x + _EPS) / (math.pi * x + _EPS)


def competition_points(seconds):
    """Bônus de competição (pontos) para um tempo de resposta em segundos."""
    if seconds is None or seconds < 0:
        return 0
    value = _sinc(seconds / constants.COMPETITION_HALF_WINDOW)
    return int(constants.COMPETITION_MAX_POINTS * value ** constants.COMPETITION_EXPONENT)


def scoring_curve_svg(width=620, height=250):
    """Curva do bônus por rapidez (tempo de resposta → pontos).

    Retorna o SVG como string, pronto para ser embutido no template com
    `|safe`. É vetorial: fica nítido em projetor e no celular.
    """
    seconds_max = constants.COMPETITION_HALF_WINDOW
    max_points = constants.COMPETITION_MAX_POINTS

    pad_left, pad_right = 54, 16
    pad_top, pad_bottom = 14, 40
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    def x_of(seconds):
        return pad_left + (seconds / seconds_max) * plot_w

    def y_of(points):
        return pad_top + (1 - points / max_points) * plot_h

    # --- Curva amostrada a cada 0,5 s ---
    samples = []
    step = 0.5
    seconds = 0.0
    while seconds <= seconds_max + 1e-9:
        samples.append((seconds, competition_points(seconds)))
        seconds += step

    curve = " ".join(f"{x_of(s):.1f},{y_of(p):.1f}" for s, p in samples)
    area = (f"M {pad_left:.1f},{y_of(0):.1f} L "
            + " L ".join(f"{x_of(s):.1f},{y_of(p):.1f}" for s, p in samples)
            + f" L {x_of(seconds_max):.1f},{y_of(0):.1f} Z")

    parts = []
    add = parts.append

    add(f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-labelledby="score-curve-title score-curve-desc" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'font-family="system-ui, -apple-system, \'Segoe UI\', sans-serif">')
    add('<title id="score-curve-title">Bônus de competição conforme o tempo de resposta</title>')
    add('<desc id="score-curve-desc">Gráfico de linha: o bônus começa perto de '
        f'{competition_points(0)} pontos para quem responde na hora, cai pela metade por '
        f'volta dos 19 segundos e chega a zero em {seconds_max} segundos.</desc>')

    # --- Grade horizontal + rótulos do eixo Y ---
    for points in range(0, max_points + 1, 50):
        y = y_of(points)
        add(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" '
            f'stroke="#e7eaf1" stroke-width="1"/>')
        add(f'<text x="{pad_left - 10}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#8792a6">{points}</text>')

    # --- Marcações do eixo X ---
    for seconds_tick in range(0, seconds_max + 1, 10):
        x = x_of(seconds_tick)
        add(f'<line x1="{x:.1f}" y1="{y_of(0):.1f}" x2="{x:.1f}" '
            f'y2="{y_of(0) + 4:.1f}" stroke="#c9d0dc" stroke-width="1"/>')
        add(f'<text x="{x:.1f}" y="{y_of(0) + 18:.1f}" text-anchor="middle" '
            f'font-size="11" fill="#8792a6">{seconds_tick}</text>')

    # --- Área + linha da curva ---
    add(f'<path d="{area}" fill="rgba(47,191,113,0.16)" stroke="none"/>')
    add(f'<polyline points="{curve}" fill="none" stroke="#1f9d59" '
        f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')

    # --- Pontos anotados (o valor em t = 0 fica no próprio eixo, "200") ---
    for seconds_mark in (5, 15, 30, 45, seconds_max):
        points_mark = competition_points(seconds_mark)
        x, y = x_of(seconds_mark), y_of(points_mark)
        add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#ffffff" '
            f'stroke="#1f9d59" stroke-width="2"/>')
        # rótulo acima do ponto; nas pontas, deslocado para não sair do gráfico
        anchor, dx = 'middle', 0
        if seconds_mark == seconds_max:
            anchor, dx = 'end', -6
        label_y = max(y - 9, pad_top + 8)
        add(f'<text x="{x + dx:.1f}" y="{label_y:.1f}" text-anchor="{anchor}" '
            f'font-size="11" font-weight="700" fill="#17703a">{points_mark}</text>')

    # --- Tempo que zera o bônus (linha vertical tracejada) ---
    add(f'<line x1="{x_of(seconds_max):.1f}" y1="{pad_top}" '
        f'x2="{x_of(seconds_max):.1f}" y2="{y_of(0):.1f}" '
        f'stroke="#c9d0dc" stroke-width="1" stroke-dasharray="4 4"/>')

    # --- Títulos dos eixos ---
    add(f'<text x="{pad_left + plot_w / 2:.1f}" y="{height - 6}" text-anchor="middle" '
        f'font-size="11.5" fill="#6b7280">segundos para responder</text>')
    add(f'<text transform="translate(14 {pad_top + plot_h / 2:.1f}) rotate(-90)" '
        f'text-anchor="middle" font-size="11.5" fill="#6b7280">pontos de competição</text>')

    add('</svg>')
    return "".join(parts)
