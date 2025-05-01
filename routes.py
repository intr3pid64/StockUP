"""
V2.0.1
This piece of code was used in StockUp to control the web application framework and direct information to different
website pages. Flask was used as the application framework, and the user data, historical data were brought through to
the pages that displayed it to the user.
"""

import csv
import threading
import time
from csv import DictReader
from datetime import datetime

from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from ib_insync import *
from ibapi.client import *
from ibapi.wrapper import *
from sqlalchemy import *
import pandas as pd

# Machine learning imports
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score



class TradingApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)

    # Order Id
    def nextValidId(self, orderId: int):
        self.orderId = orderId

    def nextId(self):
        self.orderId += 1
        return self.orderId

    def error(self, reqId: int, errorCode: int, errorString: str):
        """
        Prints any errors to the terminal in regard to the API
        """
        print(f"reqId: {reqId}, errorCode: {errorCode}, errorString: {errorString}")

    # Historical Data
    def reqHistoricalData(self, reqId: TickerId, contract: Contract, endDateTime: str,
                          durationStr: str, barSizeSetting: str, whatToShow: str,
                          useRTH: int, formatDate: int, keepUpToDate: bool, chartOptions: TagValueList):
        self.logRequest(current_fn_name(), vars())

        if not self.isConnected():
            self.wrapper.error(reqId, NOT_CONNECTED.code(),
                               NOT_CONNECTED.msg())
            return

        if self.serverVersion() < MIN_SERVER_VER_TRADING_CLASS:
            if contract.tradingClass or contract.conId > 0:
                self.wrapper.error(reqId, UPDATE_TWS.code(),
                                   UPDATE_TWS.msg() + "  It does not support conId and tradingClass parameters in reqHistoricalData.")
                return

        try:

            VERSION = 6

            # send req mkt data msg
            flds = []
            flds += [make_field(OUT.REQ_HISTORICAL_DATA), ]

            if self.serverVersion() < MIN_SERVER_VER_SYNT_REALTIME_BARS:
                flds += [make_field(VERSION), ]

            flds += [make_field(reqId), ]

            # send contract fields
            if self.serverVersion() >= MIN_SERVER_VER_TRADING_CLASS:
                flds += [make_field(contract.conId), ]
            flds += [make_field(contract.symbol),
                     make_field(contract.secType),
                     make_field(contract.lastTradeDateOrContractMonth),
                     make_field(contract.strike),
                     make_field(contract.right),
                     make_field(contract.multiplier),
                     make_field(contract.exchange),
                     make_field(contract.primaryExchange),
                     make_field(contract.currency),
                     make_field(contract.localSymbol)]
            if self.serverVersion() >= MIN_SERVER_VER_TRADING_CLASS:
                flds += [make_field(contract.tradingClass), ]
            flds += [make_field(contract.includeExpired),  # srv v31 and above
                     make_field(endDateTime),  # srv v20 and above
                     make_field(barSizeSetting),  # srv v20 and above
                     make_field(durationStr),
                     make_field(useRTH),
                     make_field(whatToShow),
                     make_field(formatDate)]  # srv v16 and above

            # Send combo legs for BAG requests
            if contract.secType == "BAG":
                flds += [make_field(len(contract.comboLegs)), ]
                for comboLeg in contract.comboLegs:
                    flds += [make_field(comboLeg.conId),
                             make_field(comboLeg.ratio),
                             make_field(comboLeg.action),
                             make_field(comboLeg.exchange)]

            if self.serverVersion() >= MIN_SERVER_VER_SYNT_REALTIME_BARS:
                flds += [make_field(keepUpToDate), ]

            # send chartOptions parameter
            if self.serverVersion() >= MIN_SERVER_VER_LINKING:
                chartOptionsStr = ""
                if chartOptions:
                    for tagValue in chartOptions:
                        chartOptionsStr += str(tagValue)
                flds += [make_field(chartOptionsStr), ]

            msg = "".join(flds)

        except ClientException as ex:
            self.wrapper.error(reqId, ex.code, ex.msg + ex.text)
            return

        self.histData = msg
        self.sendMsg(msg)

    # Placing an order
    def openOrder(self, orderId: OrderId, contract: Contract, order: Order,
                  orderState: OrderState):
        print(f"openOrder. orderId: {OrderId}, contract: {contract}, order: {order}")

    def orderStatus(self, orderId: OrderId, status: str, filled: float,
                    remaining: float, avgFillPrice: float, permId: int,
                    parentId: int, lastFillPrice: float, clientId: int,
                    whyHeld: str, mktCapPrice: float):
        print(f"orderId: {orderId}, filled: {filled}, remaining: {remaining}, avgFillPrice: {avgFillPrice}, \
        permId: {permId}, parentId: {parentId}, lastFillPrice: {lastFillPrice}, clientId: {clientId}, \
        whyHeld: {whyHeld}, mktPriceCap: {mktCapPrice}")

    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        print(f"reqId: {reqId}, contract: {contract}, execution: {execution}")

    def contractDetailsEnd(self, reqId: int):
        print("End of contract details")

    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float,
                  attrib: TickAttrib):
        print(f"reqId: {reqId}, tickType: {TickTypeEnum.to_str(tickType)}, price: {price}, attrib: {attrib}")

    def tickSize(self, reqId: TickerId, tickType: TickType, size: int):
        print(f"reqId: {reqId}, tickType: {TickTypeEnum.to_str(tickType)}, size: {size}")

    def headTimestamp(self, reqId: int, headTimestamp: str):
        """
        Uses API to get the furthest date that the contract can get historical data
        """
        print(headTimestamp)
        self.cancelHeadTimeStamp(reqId)

    def historicalData(self, reqId: int, bar: BarData):
        """
        API function to assist in printing historical data of current contract
        """
        print(reqId, bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        print(f"Historical Data Ended for {reqId}. Started at {start}, ending at {end}.")
        self.cancelHistoricalData(reqId)


# Flask Set Up
flaskapp = Flask(__name__)
flaskapp.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///contract.db'
db = SQLAlchemy(flaskapp)

flask_thread = threading.Thread(target=flaskapp.run, args=[False])
flask_thread.start()

# IBApi Threading StartUp
tradeapp = TradingApp()
tradeapp.connect("127.0.0.1", 7497, 0)
trading_thread = threading.Thread(target=tradeapp.run)
trading_thread.start()

# IB_insync setup
ib_app = IB()
ib_app.connect(host='127.0.0.1', port=7497, clientId=1)


class ContractDetails(db.Model):
    """
    Database model to store incoming contract information from users
    symboll:str - the symbol of the stock wanting to be stored
    currencyy:str - the currency of the stock
    pexchangee:str - the primary exchange of the stock
    """
    id_ = Column(Integer, primary_key=True)
    symboll = Column(String(200), nullable=False)
    currencyy = Column(String(200), nullable=False)
    pexchangee = Column(String(200), nullable=False)
    date_created_ = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<Contract %r>' % self.sym


def predict(train, test, predictors, model):
    """
    Train the model on 'train' subset of DataFrame,
    then predict classification for 'test'.
    """
    model.fit(train[predictors], train["Target"])
    # Probability that Target=1
    preds = model.predict_proba(test[predictors])[:, 1]
    # threshold at 0.6, as in your example
    preds[preds >= 0.6] = 1
    preds[preds < 0.6] = 0
    preds = pd.Series(preds, index=test.index, name="Predictions")
    combined = pd.concat([test["Target"], preds], axis=1)
    return combined


def backtest(data, model, predictors, start=2500, step=250):
    """
    Walk-forward backtest: train on [0:i], predict i:(i+step).
    """
    all_predictions = []
    for i in range(start, data.shape[0], step):
        train = data.iloc[0:i].copy()
        test = data.iloc[i:(i + step)].copy()
        predictions = predict(train, test, predictors, model)
        all_predictions.append(predictions)
    return pd.concat(all_predictions)


@flaskapp.route('/', methods=['post', 'get'])
def login():
    filename = 'History.csv'
    f = open(filename, "w")
    f.truncate()
    f.close()
    if request.method == 'POST':
        web_sym, web_curr, web_pex = (request.form['symbol'], request.form['currency'], request.form['pexchange'])
        new_contract = ContractDetails(symboll=web_sym, currencyy=web_curr, pexchangee=web_pex)
        try:
            db.session.add(new_contract)
            db.session.commit()
            return redirect('/home')
        except:
            return 'There was an issue confirming your contract'
    return render_template("login.html")


@flaskapp.route('/home')
def home():
    return render_template("home.html")


@flaskapp.route('/ordering', methods=['post', 'get'])
def ordering():
    if request.method == 'POST':
        try:
            contract_details = ContractDetails.query.order_by(desc(ContractDetails.date_created_)).first()
            contract = Contract()
            contract.symbol = contract_details.symboll
            contract.secType = "STK"
            contract.currency = contract_details.currencyy
            contract.exchange = 'SMART'
            contract.primaryExchange = contract_details.pexchangee
            print(contract.symbol + " " + contract.currency)
        except:
            return "Error with contract creation"
        try:
            myorder = Order()
            myorder.orderId = tradeapp.orderId
            if request.form['orderType'] == 'MKT':
                myorder.action, myorder.orderType, myorder.totalQuantity = (request.form['actions'],
                                                                            request.form['orderType'],
                                                                            int(request.form['quantity']))
            else:
                myorder.action = request.form['actions']
                myorder.tif, myorder.orderType, myorder.lmtPrice, myorder.totalQuantity = (request.form['tif'],
                                                                                           request.form['orderType'],
                                                                                           float(request.form[
                                                                                                     'lmtprice']),
                                                                                           int(request.form[
                                                                                                   'quantity']))
            # helps with setting orders
            myorder.eTradeOnly = ''
            myorder.firmQuoteOnly = ''
            # Place Order Method
            tradeapp.placeOrder(tradeapp.orderId, contract, myorder)
            tradeapp.nextId()
            return redirect('/order_complete')
        except:
            return "Error with order delivery"
    else:
        return render_template("ordering.html")


@flaskapp.route('/order_complete')
def order_complete():
    return render_template("order_completion.html")


@flaskapp.route('/predictions', methods=['POST', 'GET'])
def predictions():
    if request.method == 'POST':
        dates, opens, highs, lows, closings, volumes = [], [], [], [], [], []
        stock_symbol = ContractDetails.query.order_by(desc(ContractDetails.date_created_)).first().symboll
        with open('History.csv', mode='r') as file:
            raw_data = DictReader(file)
            for line in raw_data:
                dates.append(line['date'])
                opens.append(float(line['open']))
                highs.append(float(line['high']))
                lows.append(float(line['low']))
                closings.append(float(line['close']))
                volumes.append(float(line['volume']))

        # Build DataFrame
        df = pd.DataFrame({
            'Date': pd.to_datetime(dates),
            'Open': opens,
            'High': highs,
            'Low': lows,
            'Close': closings,
            'Volume': volumes
        })
        df.sort_values('Date', inplace=True)
        df.set_index('Date', inplace=True)
        # Step 2) Prepare ML features
        df['Tomorrow'] = df['Close'].shift(-1)
        df['Target'] = (df['Tomorrow'] > df['Close']).astype(int)
        print('here')

        # Rolling features
        horizons = [2, 5, 60, 250, 1000]
        new_predictors = ['Open', 'High', 'Low', 'Close', 'Volume']
        for horizon in horizons:
            rolling_averages = df[['Open', 'High', 'Low', 'Close', 'Volume']].rolling(horizon).mean()

            ratio_column = f"Close_Ratio_{horizon}"
            df[ratio_column] = df['Close'] / rolling_averages['Close']

            trend_column = f"Trend_{horizon}"
            df[trend_column] = df['Target'].shift(1).rolling(horizon).sum()

            new_predictors += [ratio_column, trend_column]

        df.dropna(inplace=True)

        # 4) Split into Train (80%), Validation (19%), Test (last row)
        split_index = int(0.8 * len(df))  # 80% of the data
        train = df.iloc[:split_index]
        val = df.iloc[split_index:-1]
        test = df.iloc[-1:]  # single row = "tomorrow"

        # 5) Fit on training set only
        model = RandomForestClassifier(n_estimators=200,
                                       min_samples_split=50,
                                       random_state=1)
        model.fit(train[new_predictors], train["Target"])

        # 6) Evaluate on the validation set
        val_preds = model.predict(val[new_predictors])
        val_precision = precision_score(val["Target"], val_preds)
        print(f"Precision on validation set: {val_precision}")

        # 7) Predict the final day's outcome => "tomorrow"
        prob_up = model.predict_proba(test[new_predictors])[:, 1][0]
        next_day_prediction = "Up" if prob_up >= 0.5 else "Down"
        print(f"Next-day prediction (final row) = {next_day_prediction}")

        if request.form['length'] == '1W':
            personalized_dates = dates[-7:]
            personalized_data = closings[-7:]

        elif request.form['length'] == '1M':
            personalized_dates = dates[-30:]
            personalized_data = closings[-30:]

        elif request.form['length'] == '6M':
            personalized_dates = dates[-180:]
            personalized_data = closings[-180:]

        elif request.form['length'] == '1Y':
            personalized_dates = dates[-365:]
            personalized_data = closings[-365:]

        elif request.form['length'] == '2Y':
            personalized_dates = dates[-750:]
            personalized_data = closings[-750:]

        else:
            return render_template("predictions.html")

        return render_template('predictions_completion.html',
                               symbol=stock_symbol, personaldates=personalized_dates, personaldata=personalized_data,
                               next_day_prediction=next_day_prediction)

    return render_template("predictions.html")


@flaskapp.route('/predictions_completion', methods=['POST', 'GET'])
def predictions_completion():
    return render_template('predictions_completion.html')


if __name__ == "__main__":
    with flaskapp.app_context():
        # creates the database
        db.create_all()

        # Writing Data To File Loop
        # When first creating the database, comment out all lines lower and then after creation rerun with bottom lines
        print('here')
        while True:
            print('here2')
            current_id = ContractDetails.query.order_by(desc(ContractDetails.date_created_)).first().id_
            while True:
                print('here3')
                if current_id != ContractDetails.query.order_by(desc(ContractDetails.date_created_)).first().id_:
                    con = ContractDetails.query.order_by(desc(ContractDetails.date_created_)).first()
                    print('jere')
                    main_contract = Stock(con.symboll, con.pexchangee, con.currencyy)
                    ib_app.qualifyContracts(main_contract)
                    hist = ib_app.reqHistoricalData(main_contract, '',
                                                    barSizeSetting='1 day', durationStr='10 Y',
                                                    whatToShow='TRADES', useRTH=True)
                    print('here')
                    time.sleep(4)
                    break
                time.sleep(5)
            data = []
            for row in hist:
                data.append({'date': str(row.date),'open': row.open, 'high': row.high, 'low': row.low,
                             'close': row.close, 'volume': row.volume})
            with open('History.csv', 'w', newline='') as csvfile:
                fieldnames = ['date', 'open', 'high', 'low', 'close', 'volume']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            time.sleep(10)
