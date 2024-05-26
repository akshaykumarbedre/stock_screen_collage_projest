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
import seaborn as sns
import pickle
import io,os
import base64
import matplotlib.pyplot as plt

plt.style.use('ggplot')

app = Flask(__name__)
app.secret_key = "your_secret_key"

df=pd.read_csv("nifty_data.csv")
df.set_index('index',inplace=True)

# User Authentication
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
@app.route("/visualization", methods=["GET", "POST"])
def visualization():
    # Compare stock function calls
    print(compare_stock(20))
    print(compare_stock(240))
    print(compare_stock(20, order=False))
    print(compare_stock(240, order=False))

    # Generate plots
    plot_url_20 = generate_plot(pd.read_csv(os.path.join('data',"data20True.csv")), 'Top Performers of the Past Month')
    plot_url_240 = generate_plot(pd.read_csv(os.path.join('data',"data240True.csv")), 'Top Performers of the Year')
    plot_url_20n = generate_plot(pd.read_csv(os.path.join('data',"data20False.csv")), 'Top Loser of the Past Month')
    plot_url_240n = generate_plot(pd.read_csv(os.path.join('data',"data240False.csv")), 'Top Loser of the Past Year')

    # Render template with plot URLs
    return render_template('visualization.html', plot_url_20=plot_url_20, plot_url_240=plot_url_240, plot_url_20N=plot_url_20n, plot_url_240N=plot_url_240n)

    # Function to generate plots
def generate_plot(dataframe, title):
    fig, ax = plt.subplots()
    for i in range(1, 6):
        ax.plot(dataframe.iloc[:, i], label=df.loc[dataframe.columns[i]]['Company Name'])
    ax.yaxis.set_major_formatter(plt.matplotlib.ticker.PercentFormatter(xmax=1))
    ax.legend()
    fig.set_size_inches(8, 6)
    ax.set_title(title)
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def compare_stock(num, order=True):
    with open(os.path.join('data','my_dict1d.pickle'), 'rb') as handle:
        ohlc_data = pickle.load(handle)

    tickers=ohlc_data.keys()
    compare = {}
    for ticker in tickers:
      close_prices = ohlc_data[ticker]['Price']
      daily_returns = (close_prices.pct_change() + 1).iloc[-num:]
      cumulative_returns = (daily_returns).cumprod()
      compare[ticker] = cumulative_returns
    df = pd.DataFrame(compare)

   # Sort the tickers based on the last cumulative return value in descending order
    sorted_tickers = df.iloc[-1].sort_values(ascending=not order).index

   # Create a new DataFrame with the sorted tickers
    sorted_df = df[sorted_tickers]
    sorted_df=(sorted_df-1)
    sorted_df.to_csv(os.path.join('data',f"data{num}{order}.csv"))

    return pd.DataFrame(sorted_df.iloc[:,[1,2,3,4,5]])

# Stock Recommendations
@app.route("/screener", methods=["GET", "POST"])
def screener():
    df=pd.read_csv(os.path.join('data',"Nifty_Result1d.csv"))
    html_table = df.to_html(classes="sortable-table")
    return render_template("screener.html", table=html_table)

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

def run(interval='1d'):
    df=pd.read_csv("nifty_data.csv")
    tickers=df['Symbol']

    ohlc_data={}
    dic={'1d':350,"5m":30,"10m":30,"15m":30}
    start = dt.datetime.today()-dt.timedelta(dic[interval])
    end = dt.datetime.today()

    for ticker in tickers:
        ohlc_data[ticker]=yf.download(ticker, interval=interval,start=start, end=end)

        ohlc_data[ticker]=indicater(ohlc_data[ticker])
        ohlc_data[ticker].drop(["Open","High","Low","Adj Close"],axis=1, inplace=True)
        ohlc_data[ticker].rename(columns = {'Close':'Price'}, inplace = True)
        ohlc_data[ticker]["Company Name"]=df[df['Symbol']==ticker]['Company Name'].iloc[0]
    
    with open(os.path.join('data',f'my_dict{interval}.pickle'), 'wb') as handle:
        pickle.dump(ohlc_data, handle, protocol=pickle.HIGHEST_PROTOCOL)

    final_data = [ohlc_data[ticker].iloc[-1] for ticker in tickers]

    df=pd.DataFrame(final_data).set_index("Company Name")
    df.to_csv(os.path.join('data',f"Nifty_Result{interval}.csv"))

scheduler = BackgroundScheduler()
scheduler.add_job(run, 'interval', minutes=1440)
scheduler.add_job(run, 'interval', minutes=15, args=["15m"])
scheduler.start()
#run("15m")
#run()

if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True)