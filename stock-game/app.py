from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_economy_club_key'
socketio = SocketIO(app, async_mode='eventlet')

# --- 게임 설정값 ---
INITIAL_CASH = 500000
GAME_DURATION = 120  # 2분 (초 단위)
STOCKS_CONFIG = {
    'A': {'start': 50000, 'range': 1000},
    'B': {'start': 50000, 'range': 2000},
    'C': {'start': 50000, 'range': 3000},
    'D': {'start': 50000, 'range': 5000}
}

# --- 서버 메모리 상태 (DB 대신 사용) ---
# users = { 'session_id': { 'cash': 500000, 'holdings': {'A':0...}, 'history': [] } }
users = {}
# game_state = { 'time_left': 120, 'prices': {...}, 'changes': {...}, 'is_active': False }
game_state = {
    'time_left': GAME_DURATION,
    'prices': {k: v['start'] for k, v in STOCKS_CONFIG.items()},
    'changes': {k: 0 for k in STOCKS_CONFIG}, # 전일 대비 등락
    'is_active': False
}

def game_loop():
    """1초마다 가격 변동 및 시간 체크를 하는 백그라운드 스레드"""
    global game_state
    while game_state['is_active']:
        socketio.sleep(1)
        game_state['time_left'] -= 1

        # 1. 가격 변동 로직
        for symbol, config in STOCKS_CONFIG.items():
            # 랜덤 등락폭 결정
            fluctuation = random.randint(-config['range'], config['range'])
            new_price = game_state['prices'][symbol] + fluctuation
            
            # 가격이 0 이하로 떨어지지 않게 방어
            if new_price < 1: new_price = 1
            
            game_state['changes'][symbol] = new_price - game_state['prices'][symbol]
            game_state['prices'][symbol] = new_price

        # 2. 클라이언트에 데이터 전송 (Broadcasting)
        socketio.emit('update_data', {
            'time_left': game_state['time_left'],
            'prices': game_state['prices'],
            'changes': game_state['changes']
        })

        # 3. 게임 종료 처리 (0초 도달)
        if game_state['time_left'] <= 0:
            game_state['is_active'] = False
            finalize_game()
            break

def finalize_game():
    """게임 종료 시 모든 주식 자동 매도 처리"""
    final_prices = game_state['prices']
    
    for sid, user in users.items():
        total_stock_value = 0
        # 보유 주식 전량 매도 계산
        for symbol, count in user['holdings'].items():
            if count > 0:
                earn = count * final_prices[symbol]
                user['cash'] += earn
                total_stock_value += earn
                user['holdings'][symbol] = 0
        
        # 최종 결과 전송
        socketio.emit('game_over', {
            'final_balance': user['cash'],
            'profit': user['cash'] - INITIAL_CASH
        }, room=sid)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    # 유저 접속 시 초기화
    users[request.sid] = {
        'cash': INITIAL_CASH,
        'holdings': {'A': 0, 'B': 0, 'C': 0, 'D': 0}
    }
    # 현재 게임 상태 전송
    emit('init_status', {
        'cash': INITIAL_CASH,
        'holdings': users[request.sid]['holdings'],
        'prices': game_state['prices'],
        'is_active': game_state['is_active']
    })

@socketio.on('start_game')
def handle_start_game():
    global game_state
    # 게임이 이미 실행 중이 아닐 때만 시작
    if not game_state['is_active']:
        game_state['is_active'] = True
        game_state['time_left'] = GAME_DURATION
        game_state['prices'] = {k: v['start'] for k, v in STOCKS_CONFIG.items()}
        game_state['changes'] = {k: 0 for k in STOCKS_CONFIG}
        
        # 모든 유저 자산 초기화
        for uid in users:
            users[uid] = {'cash': INITIAL_CASH, 'holdings': {'A': 0, 'B': 0, 'C': 0, 'D': 0}}
        
        socketio.emit('game_started')
        socketio.start_background_task(game_loop)

@socketio.on('trade')
def handle_trade(data):
    if not game_state['is_active']:
        return

    sid = request.sid
    action = data['action'] # 'buy' or 'sell'
    symbol = data['symbol']
    current_price = game_state['prices'][symbol]
    user = users[sid]

    if action == 'buy':
        if user['cash'] >= current_price:
            user['cash'] -= current_price
            user['holdings'][symbol] += 1
    elif action == 'sell':
        if user['holdings'][symbol] > 0:
            user['cash'] += current_price
            user['holdings'][symbol] -= 1
    
    # 개인 자산 상태 업데이트 전송
    emit('user_update', {
        'cash': user['cash'],
        'holdings': user['holdings'],
        'profit': (user['cash'] + sum(user['holdings'][s] * game_state['prices'][s] for s in STOCKS_CONFIG)) - INITIAL_CASH
    })

if __name__ == '__main__':
    # 0.0.0.0으로 설정하여 같은 와이파이의 다른 기기에서도 접속 가능하게 함
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
