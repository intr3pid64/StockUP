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
from openai import OpenAI
from sqlalchemy import *

# OpenAi API
client = OpenAI(
    # this is where the api_key will go
)


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


#Flask Set Up
flaskapp = Flask(__name__)
flaskapp.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///contract.db'
db = SQLAlchemy(flaskapp)

flask_thread = threading.Thread(target=flaskapp.run, args=[False])
flask_thread.start()

#IBApi Threading StartUp
tradeapp = TradingApp()
tradeapp.connect("127.0.0.1", 7497, 0)
trading_thread = threading.Thread(target=tradeapp.run)
trading_thread.start()

#IB_insync setup
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
                                                                                           float(request.form['lmtprice']),
                                                                                           int(request.form['quantity']))
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
        dates, closings, gptfeed = [], [], []
        stock_symbol = ContractDetails.query.order_by(desc(ContractDetails.date_created_)).first().symboll
        with open('History.csv', mode='r') as file:
            raw_data = DictReader(file)
            for line in raw_data:
                dates.append(line.get('date'))
                closings.append(line.get('close'))

                gptfeed.append(line.get('date'))
                gptfeed.append(line.get('close'))

        personalized_dates = []
        personalized_data = []
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
            personalized_dates = dates
            personalized_data = closings

        else:
            return render_template("predictions.html")

        gpt_dates = dates[-20:]
        first_half_closing = closings[-20:]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user",
                       "content": f"""
                       Use the python list of closing prices for {stock_symbol}, with the format [date, price], and to 
                       your capabilities and the current events of the world applicable to the stock,
                       return 1 python string back of the stock price predictions for the next 7 days. The string should 
                       have the dates first and the other half of the string has the corresponding closing price. Format:
                       
                       date1,date2,date3,date4,date5,date6,date7,price1,price2,price3,price4,price5,price6,price7.
                       
                       Only return 1 string in this format without any extra words, symbols, parentheses, quotes or spaces.
                       Make sure to have any spikes in price or dips if applicable.
                       {str(gptfeed)}
                       """ }],
            stream=False
        )
        gpt_content = response.choices[0].message.content.split(',')
        gpt_dates += gpt_content[:7]
        second_half = [first_half_closing[-1]]
        second_half += gpt_content[7:]

        projected = {gpt_dates[19]: second_half[0], gpt_dates[20]: second_half[1], gpt_dates[21]: second_half[2],
                     gpt_dates[22]: second_half[3], gpt_dates[23]: second_half[4], gpt_dates[24]: second_half[5],
                     gpt_dates[25]: second_half[6], gpt_dates[26]: second_half[7]}

        return render_template('predictions_completion.html',
                               symbol=stock_symbol, personaldates=personalized_dates, personaldata=personalized_data,
                               gptdates=gpt_dates, halfclose=first_half_closing, projected=projected)

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
        while true:
            current_id = ContractDetails.query.order_by(desc(ContractDetails.date_created_)).first().id_
            while true:
                if current_id != ContractDetails.query.order_by(desc(ContractDetails.date_created_)).first().id_:
                    con = ContractDetails.query.order_by(desc(ContractDetails.date_created_)).first()
                    main_contract = Stock(con.symboll, con.pexchangee, con.currencyy)
                    ib_app.qualifyContracts(main_contract)
                    hist = ib_app.reqHistoricalData(main_contract, '',
                                                    barSizeSetting='1 day', durationStr='2 Y',
                                                    whatToShow='TRADES', useRTH=True)
                    time.sleep(4)
                    break
                time.sleep(5)
            data = []
            for row in hist:
                data.append({'date': str(row.date), 'close': row.close})
            with open('History.csv', 'w', newline='') as csvfile:
                fieldnames = ['date', 'close']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            time.sleep(20)

