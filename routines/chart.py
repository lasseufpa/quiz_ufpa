import matplotlib
matplotlib.use('Agg')  # backend sem display (necessário rodando no servidor)
import matplotlib.pyplot as plt
import os
import matplotlib.patches as patches 


def _draw_team_standings(ax, standings):
    """Desenha o painel do modo time: quem está ganhando e os melhores de cada time."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    ax.set_title("Placar por time")

    blocks = max(len(standings), 1)
    block_height = 1.0 / blocks

    for index, team in enumerate(standings):
        top_y = 1.0 - index * block_height
        color = '#FFD966' if team.get('winning') else '#dfe3e8'

        # Cabeçalho: nome do time e pontuação total
        header = patches.Rectangle(
            (0.02, top_y - 0.15), 0.96, 0.13,
            linewidth=1, edgecolor='black', facecolor=color, alpha=0.9
        )
        ax.add_patch(header)
        ax.text(0.06, top_y - 0.085, team.get('name', '?'),
                fontsize=12, fontweight='bold', va='center')
        ax.text(0.94, top_y - 0.085, f"{team.get('score', 0)} pts",
                fontsize=12, fontweight='bold', va='center', ha='right')

        # Situação do time na disputa
        if team.get('winning'):
            situacao = 'Empate na liderança' if team.get('tied') else 'Na frente'
        else:
            situacao = f"{team.get('position', '?')}º lugar"
        ax.text(0.06, top_y - 0.20, situacao, fontsize=9, style='italic',
                va='center', color='#444')

        # Melhores jogadores do time
        membros = team.get('top') or []
        if not membros:
            ax.text(0.06, top_y - 0.30, 'sem jogadores', fontsize=10,
                    style='italic', color='#666', va='center')
        for pos, member in enumerate(membros, start=1):
            y = top_y - 0.30 - (pos - 1) * 0.105
            ax.text(0.08, y, f"{pos}. {member['nickname']}", fontsize=10, va='center')
            ax.text(0.94, y, str(member['score']), fontsize=10, va='center', ha='right')


def save_combined_results_chart(answer_distribution, question_data, question_index, top3,
                               team_standings=None):
    """Generate a single figure with two subplots:
       - Left: answer distribution bar chart
       - Right: podium (top 3 competition points) or, in team mode, the team
         standings with the best players of each team
       Returns the file path to the saved image.
    """
    os.makedirs('static/graphs', exist_ok=True)
    filename = f"static/graphs/q{question_index + 1}_results.png"

    team_mode = bool(team_standings)
    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(9, 3.6) if team_mode else (8, 3)
    )
    
    # ---- Subplot 1: Answer distribution bar chart ----
    labels = ['A', 'B', 'C', 'D'][:len(answer_distribution)]
    values = answer_distribution
    colors = ['#007bff', '#28a745', '#ffc107', '#dc3545'][:len(values)]
    ax1.bar(labels, values, color=colors)
    ax1.set_title(f"Distribuição das respostas\nPergunta {question_index + 1}")
    ax1.set_xlabel("Alternativas")
    ax1.set_ylabel("Número de respostas")

    if team_mode:
        _draw_team_standings(ax2, team_standings)
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
        return filename

    # ---- Subplot 2: Podium ----
    ax2.set_xlim(0, 3)
    ax2.set_ylim(0, 1)
    ax2.axis('off')
    
    cores_podium = ['#FFD966', '#C0C0C0', '#CD7F32']
    largura = 0.9
    altura = 0.7
    y_base = 0.15
    
    for i, (nome, pontuacao) in enumerate(top3):
        # Handle spaces in names: replace with newline
        nome_display = nome.replace(' ', '\n')
        x = i + 0.05
        rect = patches.Rectangle(
            (x, y_base), largura, altura,
            linewidth=1, edgecolor='black', facecolor=cores_podium[i], alpha=0.8
        )
        ax2.add_patch(rect)
        ax2.text(
            x + largura/2, y_base + altura/2,
            f"{nome_display}\n{pontuacao}",
            ha='center', va='center', fontsize=15, fontweight='bold'
        )
    ax2.set_title("Pódio")
    
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()
    return filename