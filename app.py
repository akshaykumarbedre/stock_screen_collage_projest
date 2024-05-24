from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import requests
from sklearn.ensemble import RandomForestRegressor
from apscheduler.schedulers.background import BackgroundScheduler
import bcrypt
import datetime as dt
import ta 
import pandas as pd
import yfinance as yf

app = Flask(__name__)
app.secret_key = "your_secret_key"

# User Authentication
# Load users from CSV using Pandas
def load_users():
    try:
        users_df = pd.read_csv('users.csv', index_col='username')
    except FileNotFoundError:
        # If the file does not exist, create an empty DataFrame
        users_df = pd.DataFrame(columns=['username', 'password', 'name', 'phone'])
        users_df.set_index('username', inplace=True)
    return users_df

users = load_users()



@app.route("/")
def index():
    if "user" in session:
        return render_template("index.html", user=session["user"])
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"].encode('utf-8')
        
        # Check if the username exists in the DataFrame
        if username in users.index:
            # Retrieve the hashed password from the DataFrame
            hashed_password = users.loc[username, 'password'].encode('utf-8')
            
            # Use bcrypt to check if the provided password matches the hashed password
            if bcrypt.checkpw(password, hashed_password):
                session["user"] = username
                return redirect(url_for("index"))
        
        # If authentication fails, return an error
        return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"].encode('utf-8')
        name = request.form["name"]
        phone = request.form["phone"]
        
        if username in users.index:
            return render_template("register.html", error="Username already taken")
        
        # Hash the password
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
        
        # Store the new user details in the DataFrame
        users.loc[username] = [hashed_password.decode('utf-8'), name, phone]
        
        # Save the DataFrame to CSV
        users.to_csv('users.csv')
        
        session["user"] = username
        return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    # Remove the user from the session
    session.pop("user", None)
    # Redirect to the login page
    return redirect(url_for("login"))

# Stock Screening
@app.route("/screen", methods=["GET", "POST"])
def screen():
	pass

def screen_stocks(filters):
    # Fetch stock data from financial APIs and apply filters
    # Return filtered stock data as a pandas DataFrame
    pass

# Stock Recommendations
@app.route("/recommend", methods=["GET", "POST"])
def recommend():
    df=pd.read_csv("Nifty_Result.csv")
    html_table = df.to_html()
    return render_template("recommend.html", table=html_table)

def indicater(df):
        df['MACD hist']=ta.trend.macd_diff(df['Close'])
        df['ADX']=ta.trend.adx(df["High"], df["Low"], df["Close"], window=14)
        df['ATR']=ta.volatility.average_true_range(df["High"], df["Low"], df["Close"], window=14)
        df["EMA 200"] = ta.trend.EMAIndicator(df['Close'], window=200, fillna=False).ema_indicator()
        df['RSI']= ta.momentum.rsi(df["Close"], window=14)
        df['Stochastic Oscillator']=ta.momentum.stoch(df["High"], df["Low"], df["Close"], window=14, smooth_window=3)
        df['MACD hist sloap*']=df['MACD hist'].diff()
        df["EMA 200 Sloap"]=df["EMA 200"].diff()/df['Close']
        return df

def run():
    df=pd.read_csv("nifty_data.csv")
    tickers=df['Symbol']

    ohlc_data={}
    start = dt.datetime.today()-dt.timedelta(365)
    end = dt.datetime.today()

    for ticker in tickers:
        ohlc_data[ticker]=yf.download(ticker, interval="1d",start=start, end=end)

        ohlc_data[ticker]=indicater(ohlc_data[ticker])
        ohlc_data[ticker].drop(["Open","High","Low","Adj Close"],axis=1, inplace=True)
        ohlc_data[ticker].rename(columns = {'Close':'Price'}, inplace = True)
        ohlc_data[ticker]["Company Name"]=df[df['Symbol']==ticker]['Company Name'].iloc[0]

    final_data = [ohlc_data[ticker].iloc[-1] for ticker in tickers]

    df=pd.DataFrame(final_data).set_index("Company Name")
    df.to_csv("Nifty_Result.csv")

scheduler = BackgroundScheduler()
scheduler.add_job(run, 'interval', minutes=1440)
scheduler.start()
#run()

def recommend_stocks(risk_appetite, portfolio):
    pass



if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True)