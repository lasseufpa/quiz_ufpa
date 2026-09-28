import matplotlib.pyplot as plt
import os
import matplotlib.patches as patches 

def save_answer_distribution_chart(answer_distribution, question_data, question_index):
    os.makedirs('static/graphs', exist_ok=True)
    labels = ['A', 'B', 'C', 'D'][:len(answer_distribution)]
    values = answer_distribution
    plt.figure(figsize=(5,3))
    plt.bar(labels, values, color=['#007bff', '#28a745', '#ffc107', '#dc3545'][:len(values)])
    plt.title(f"Distribuição das respostas - Pergunta {question_index + 1}")
    plt.xlabel("Alternativas")
    plt.ylabel("Número de respostas")
    plt.tight_layout()
    filename = f"static/graphs/q{question_index + 1}_results.png"
    plt.savefig(filename)
    plt.close()
    return filename


def save_combined_results_chart(answer_distribution, question_data, question_index, top3):
    """Generate a single figure with two subplots:
       - Left: answer distribution bar chart
       - Right: podium (top 3 competition points)
       Returns the file path to the saved image.
    """
    os.makedirs('static/graphs', exist_ok=True)
    filename = f"static/graphs/q{question_index + 1}_results.png"
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3))
    
    # ---- Subplot 1: Answer distribution bar chart ----
    labels = ['A', 'B', 'C', 'D'][:len(answer_distribution)]
    values = answer_distribution
    colors = ['#007bff', '#28a745', '#ffc107', '#dc3545'][:len(values)]
    ax1.bar(labels, values, color=colors)
    ax1.set_title(f"Distribuição das respostas\nPergunta {question_index + 1}")
    ax1.set_xlabel("Alternativas")
    ax1.set_ylabel("Número de respostas")
    
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