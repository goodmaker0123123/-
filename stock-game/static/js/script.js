const socket = io();

// DOM 요소 참조
const timerDisplay = document.getElementById('timer-display');
const startBtn = document.getElementById('start-btn');
const myCashDisplay = document.getElementById('my-cash');
const myProfitDisplay = document.getElementById('my-profit');
const modal = document.getElementById('end-modal');

// 숫자 포맷 (콤마)
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// 시작 버튼
function startGame() {
    socket.emit('start_game');
}

// 거래 요청
function trade(action, symbol) {
    socket.emit('trade', { action: action, symbol: symbol });
}

function closeModal() {
    modal.classList.add('hidden');
}

// --- 소켓 이벤트 리스너 ---

// 1. 게임 시작됨
socket.on('game_started', () => {
    startBtn.disabled = true;
    startBtn.innerText = "진행 중...";
    modal.classList.add('hidden');
});

// 2. 실시간 데이터 업데이트 (1초마다)
socket.on('update_data', (data) => {
    // 타이머 업데이트
    const min = Math.floor(data.time_left / 60);
    const sec = data.time_left % 60;
    timerDisplay.innerText = `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;

    // 주가 및 등락 업데이트
    for (const [symbol, price] of Object.entries(data.prices)) {
        const change = data.changes[symbol];
        const priceEl = document.getElementById(`price-${symbol}`);
        const changeEl = document.getElementById(`change-${symbol}`);
        
        // 가격 표시
        priceEl.innerText = `${formatNumber(price)} ₩`;
        
        // 등락 표시
        let sign = change > 0 ? "▲" : (change < 0 ? "▼" : "-");
        let colorClass = change > 0 ? "up" : (change < 0 ? "down" : "");
        
        changeEl.innerText = `${sign} ${formatNumber(Math.abs(change))}`;
        changeEl.className = `fluctuation ${colorClass}`;
    }
});

// 3. 개인 자산 업데이트 (거래 시)
socket.on('user_update', (data) => {
    myCashDisplay.innerText = `${formatNumber(data.cash)} ₩`;
    
    // 보유 수량 업데이트
    for (const [symbol, count] of Object.entries(data.holdings)) {
        document.getElementById(`hold-${symbol}`).innerText = `(${count})`;
    }

    // 순손익 업데이트
    const profit = data.profit;
    let profitSign = profit > 0 ? "+" : "";
    myProfitDisplay.innerText = `${profitSign}${formatNumber(profit)}`;
    myProfitDisplay.className = profit > 0 ? "plus" : (profit < 0 ? "minus" : "neutral");
});

// 4. 초기 상태 동기화 (접속 시)
socket.on('init_status', (data) => {
    myCashDisplay.innerText = `${formatNumber(data.cash)} ₩`;
    if(data.is_active) {
        startBtn.disabled = true;
        startBtn.innerText = "진행 중...";
    }
});

// 5. 게임 종료
socket.on('game_over', (data) => {
    startBtn.disabled = false;
    startBtn.innerText = "다시 시작";
    
    // 모달 표시
    document.getElementById('final-balance').innerText = formatNumber(data.final_balance);
    document.getElementById('final-profit').innerText = formatNumber(data.profit);
    modal.classList.remove('hidden');
    
    // UI 리셋
    myCashDisplay.innerText = `${formatNumber(data.final_balance)} ₩`;
    document.querySelectorAll('.btn-sell span').forEach(el => el.innerText = '(0)');
});
