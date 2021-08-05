import time
import pyupbit
import datetime
import requests
import numpy as np
import schedule
from fbprophet import Prophet

schedule.clear()
# upbit key
access_key = "key"
secret_key = "key"

access = access_key
secret = secret_key

# slack token
myToken = "key"
slack_roomname = "#crypto"

# 7일간 데이터를 넣어서 최고의 성과를 낸 ｋ취득
def get_ror(k=0.5):
	df = pyupbit.get_ohlcv("KRW-BTC", count =7)
	df['range'] = (df['high'] - df['low']) * k
	df['target'] = df['open'] + df['range'].shift(1)

	df['ror'] = np.where(df['high'] > df['target'], df['close'] / df['target'], 1)

	ror = df['ror'].cumprod()[-2]
	
	return ror

def best_kvalue():
	tmp_ror = 0
	tmp_k   = 0
	for k in np.arange(0.15, 1.0, 0.01):
		k = round(k,2)
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

def get_loss_cut_price(day_max_price = 0):
	"""손절 기준가"""
	return day_max_price/100*90

def loss_cut():
	"""손절 처리"""
	btc = get_balance("BTC")
	sell_result = upbit.sell_market_order("KRW-BTC", btc*0.9995)
	post_message(myToken,slack_roomname, "BTC sell : " +str(sell_result))
	return

predicted_close_price = 0
def predict_price(ticker):
	"""Prophet으로 당일 종가 가격 예측"""
	global predicted_close_price
	# 학습데이터는 3일로 최근 트렌드만 반영되도록 
	df = pyupbit.get_ohlcv(ticker, count = 144, interval="minute30")
	df = df.reset_index()
	df['ds'] = df['index']
	df['y'] = df['close']
	data = df[['ds','y']]
	model = Prophet()
	model.fit(data)
	future = model.make_future_dataframe(periods=24, freq='H')
	forecast = model.predict(future)
	closeDf = forecast[forecast['ds'] == forecast.iloc[-1]['ds'].replace(hour=9)]
	if len(closeDf) == 0:
		closeDf = forecast[forecast['ds'] == data.iloc[-1]['ds'].replace(hour=9)]
	closeValue = closeDf['yhat'].values[0]
	predicted_close_price = closeValue
	post_message(myToken,slack_roomname, "predict_val : " +str(predicted_close_price))
	post_message(myToken,slack_roomname, "day_max_price : " +str(day_max_price))
	print(schedule.jobs)

    
# 일봉 최고가 취득
day_max_price = 0
# 로그인
upbit = pyupbit.Upbit(access, secret)
print("autotrade start")
# 시작 메세지 슬랙 전송
post_message(myToken,slack_roomname, "autotrade start")

predict_price("KRW-BTC")
# 1시간에 한번씩 실행
# schedule.every().hour.do(lambda: predict_price("KRW-BTC"))
# 30분에 한번씩 실행
schedule.every(30).minutes.do(lambda: predict_price("KRW-BTC"))

kvalue = best_kvalue()
tmp_target_price = 0


while True:
	try:
		now = datetime.datetime.now()
		start_time = get_start_time("KRW-BTC")
		end_time = start_time + datetime.timedelta(days=1)
		schedule.run_pending()

		if start_time < now < end_time - datetime.timedelta(seconds=10):
			target_price = get_target_price("KRW-BTC", kvalue)
			
			if target_price != tmp_target_price:
				tmp_target_price = target_price
				post_message(myToken,slack_roomname, "Today Kvalue : " +str(kvalue))
				post_message(myToken,slack_roomname, "new T.P : " +str(tmp_target_price))
			ma5 = get_ma5("KRW-BTC")
			current_price = get_current_price("KRW-BTC")
			# 일 최고가 취득
			if day_max_price < current_price:
				day_max_price = current_price

			# 비트코인 보유중 고점에서 10% 빠졌다면 일단 손절
			#if(get_balance("BTC") > 0.00008 and get_loss_cut_price(day_max_price) > current_price):
			#loss_cut()

			if target_price < current_price and ma5 < current_price and current_price < predicted_close_price:
				krw = get_balance("KRW")
				if krw > 5000:
					buy_result = upbit.buy_market_order("KRW-BTC", krw*0.9995)
					post_message(myToken,slack_roomname, "BTC buy : " +str(buy_result))
		else:
			# 일봉마감시간에 비트코인을 보유중이라면 매도
			day_max_price = 0
			btc = get_balance("BTC")
			if btc > 0.00008:
				sell_result = upbit.sell_market_order("KRW-BTC", btc*0.9995)
				post_message(myToken,slack_roomname, "BTC sell : " +str(sell_result))
				post_message(myToken,slack_roomname, "Balance : " +str(get_balance("KRW")))
			kvalue = best_kvalue()
		time.sleep(1)
	except Exception as e:
		print(e)
		post_message(myToken,slack_roomname, "error_log : " + str(e))
		time.sleep(1)