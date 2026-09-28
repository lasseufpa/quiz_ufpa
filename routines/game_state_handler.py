from routines import  constants
import json

def clear_game_state():
    game_state = {
        'host_sid': None,
        'players': {},
        'current_question': -1,
        'answers': {},
        'scores': {},
        'competition_scores': {},      # NEW
        'state': constants.STATE_LOBBY,
        'question_start_time': None,   # NEW
        'answers_time': {},             # NEW
        'PLAYER_SESSIONS' : {}
    }
    return game_state

def save_full_state(game_state, QUIZ_DATA):
    """Save current game state and player sessions to a JSON file."""
    state = {
        'game_state': {
            'host_sid': game_state['host_sid'],
            'players': game_state['players'],
            'current_question': game_state['current_question'],
            'answers': game_state['answers'],
            'scores': game_state['scores'],
            'competition_scores': game_state['competition_scores'],   # NEW
            'state': game_state['state'],
            'question_start_time': game_state['question_start_time'], # NEW
            'answers_time': game_state['answers_time'],               # NEW
            'PLAYER_SESSIONS' : game_state['PLAYER_SESSIONS']
        },
        'quiz_data': QUIZ_DATA  # current quiz being played
    }
    try:
        with open(constants.GAME_SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        print("✅ Game state saved to file.")
    except Exception as e:
        print(f"❌ Failed to save game state: {e}")