import time
import pyupbit
import datetime
import requests
import numpy as np

# upbit key
access_key = "key"
secret_key = "key"

access = access_key
secret = secret_key

# slack token
myToken = "key"

# 7일간 ｋ값을 넣어서 최고의 성과를 낸 ｋ취득
def get_ror(k=0.5):
    df = pyupbit.get_ohlcv("KRW-BTC", count = 7)
    df['range'] = (df['high'] - df['low']) * k
    df['target'] = df['open'] + df['range'].shift(1)

    df['ror'] = np.where(df['high'] > df['target'], df['close'] / df['target'], 1)

    ror = df['ror'].cumprod()[-2]
    
    return ror

def best_kvalue():
    tmp_ror = 0
    tmp_k   = 0
    for k in np.arange(0.1, 1.0, 0.1):
        ror = get_ror(k)
        if(tmp_ror < ror):
            tmp_ror = ror
            tmp_k   = k
    return tmp_k


def post_message(token, channel, text):
    response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer "+token},
        data={"channel": channel,"text": text}
    )

def get_target_price(ticker, k):
    """변동성 돌파 전략으로 매수 목표가 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
    target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    return target_price

def get_start_time(ticker):
    """시작 시간 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
    start_time = df.index[0]
    return start_time

def get_ma5(ticker):
    """5일 이동 평균선 조회"""
    df = pyupbit.get_ohlcv(ticker, interval="day", count=5)
    ma5 = df['close'].rolling(5).mean().iloc[-1]
    return ma5

def get_balance(ticker):
    """잔고 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0

def get_current_price(ticker):
    """현재가 조회"""
    return pyupbit.get_orderbook(tickers=ticker)[0]["orderbook_units"][0]["ask_price"]


# 로그인
upbit = pyupbit.Upbit(access, secret)
print("autotrade start")
# 시작 메세지 슬랙 전송
post_message(myToken,"#crypto", "autotrade start")

kvalue = best_kvalue()
tmp_target_price = 0
while True:
    try:
        now = datetime.datetime.now()
        start_time = get_start_time("KRW-BTC")
        end_time = start_time + datetime.timedelta(days=1)

        if start_time < now < end_time - datetime.timedelta(seconds=10):
            target_price = get_target_price("KRW-BTC", kvalue)
            if target_price != tmp_target_price:
                tmp_target_price = target_price
                post_message(myToken,"#crypto", "Today Kvalue : " +str(kvalue))
                post_message(myToken,"#crypto", "new T.P : " +str(tmp_target_price))
            ma5 = get_ma5("KRW-BTC")
            current_price = get_current_price("KRW-BTC")
            if target_price < current_price and ma5 < current_price:
                krw = get_balance("KRW")
                if krw > 5000:
                    buy_result = upbit.buy_market_order("KRW-BTC", krw*0.9995)
                    post_message(myToken,"#crypto", "BTC buy : " +str(buy_result))
        else:
            btc = get_balance("BTC")
            if btc > 0.00008:
                sell_result = upbit.sell_market_order("KRW-BTC", btc*0.9995)
                post_message(myToken,"#crypto", "BTC buy : " +str(sell_result))
            kvalue = best_kvalue()
        time.sleep(1)
    except Exception as e:
        print(e)
        post_message(myToken,"#crypto", e)
        time.sleep(1)