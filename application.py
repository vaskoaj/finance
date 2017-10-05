from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():

    #initiate acounts invested cash
    account_invest = 0

    #store the current stocks in which the user is invested
    user_symbols = db.execute("SELECT shares, symbol FROM portfolios where id=:id", id=session["user_id"])

    #calculate the values of the invested funds
    for user_symbol in user_symbols:
        for_sym = user_symbol["symbol"]
        for_shares = user_symbol["shares"]
        for_stock = lookup(for_sym)
        for_total = for_shares * for_stock["price"]
        account_invest += for_total
        db.execute("UPDATE portfolios SET price=:price, total=:total WHERE id=:id AND symbol=:symbol", \
                price=usd(for_stock["price"]), total=usd(for_total), id=session["user_id"], symbol=for_sym)

    #get the amount of money not invested
    account_cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])

    #calucate the total net worth
    net_worth = account_invest + account_cash[0]["cash"]

    #get the entire portfolio and display it in the index page
    portfolio = db.execute("SELECT * FROM portfolios WHERE id=:id", id=session["user_id"])
    return render_template("index.html", portfolio=portfolio, cash=usd(account_cash[0]["cash"]), total=usd(net_worth))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""

    #if the user navigates o the page return the buy template
    if request.method == "GET":
        return render_template("buy.html")

    #if the user inputs information into the fields
    else:
        #look up the symbol
        stock = lookup(request.form.get("symbol"))

        #check for invalid entries
        if not stock:
            return apology("invalid entry")

        try:
            shares = int(request.form.get("shares"))

            if shares < 0:
                return apology("invalid entry")

        except:
            return apology("invalid entry")

        #compare the cost of the request to the cash on hand
        cost = shares * stock["price"]
        cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
        if not cash or cash[0]["cash"] < cost:
            return apology("not enough money")

        #update history database with transaction
        db.execute("INSERT INTO history (user_id, shares, symbol, price) VALUES(:user_id, :shares, :symbol, :price)", \
                user_id=session["user_id"], shares=shares, symbol=stock["symbol"], price=usd(stock["price"]))

        #update the user database with new cash available
        db.execute("UPDATE users SET cash=cash - :cost WHERE id=:id", id=session["user_id"], cost=cost)

        #determine if user has shares of this stock already
        user_shares = db.execute("SELECT shares FROM portfolios WHERE id=:id AND symbol=:symbol",
                id=session["user_id"], symbol=stock["symbol"])

        #if not, create a new portfolios item
        if not user_shares:
            db.execute("INSERT INTO portfolios (name, id, shares, symbol, price, total) \
                    VALUES(:name, :id, :shares, :symbol, :price, :total)", \
                    name=stock["name"], id=session["user_id"], shares=shares, symbol=stock["symbol"], \
                    price=usd(stock["price"]), total=usd(shares * stock["price"]))

        #if so, add to existing portfolio
        else:
            shares = shares + user_shares[0]["shares"]
            db.execute("UPDATE portfolios SET price=:price, shares=:shares WHERE id=:id AND symbol=:symbol", \
                    price=usd(stock["price"]), shares=shares, id=session["user_id"], symbol=stock["symbol"])

        #redirect to newly updates index page
        return redirect(url_for("index"))

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""

    #get histories pertaining to this user
    histories = db.execute("SELECT * FROM history WHERE user_id=:id", id=session["user_id"])

    #display the history
    return render_template("history.html", histories=histories)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        rows = lookup(request.form.get("SYMBOL"))

        # ensure username was submitted
        if not rows:
            return apology("must provide SYMBOL")

        # redirect user to home page
        return render_template("quoted.html", stock=rows)

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # insure that passwords submitted are the same
        elif request.form.get("password") != request.form.get("password2"):
            return apology("passwords don't match")

        # insert user into database
        implemented = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", \
                username=request.form.get("username"), hash=pwd_context.hash(request.form.get("password")))

        #make sure username is not already in use
        if not implemented:
            return apology('username not available')

        #store this user for the session
        session['user_id'] = implemented

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""

    #show the form
    if request.method == "GET":
        return render_template("sell.html")

    #upon submission of form
    else:
        #look up the stock they want to sell
        stock = lookup(request.form.get("symbol"))

        #make sure it's a valid stock and shares
        if not stock:
            return apology("invalid entry")

        try:
            shares = int(request.form.get("shares"))

            if shares < 0:
                return apology("invalid entry")

        except:
            return apology("invalid entry")

        #calculate the cost of the shares
        cost = shares * stock["price"]
        user_shares = db.execute("SELECT shares FROM portfolios WHERE id=:id AND symbol=:symbol", \
                id=session["user_id"], symbol=stock["symbol"])

        #check to make sure user has the shares being sold
        if not user_shares or user_shares[0]["shares"] < shares:
            return apology("you don't have that many shares")

        #add transaction to history
        db.execute("INSERT INTO history (user_id, shares, symbol, price) VALUES(:user_id, -:shares, :symbol, -:price)", \
                user_id=session["user_id"], shares=shares, symbol=stock["symbol"], price=usd(stock["price"]))

        #update users database
        db.execute("UPDATE users SET cash=cash + :cost WHERE id=:id", id=session["user_id"], cost=usd(cost))

        #update portfolios to reflect sale
        db.execute("UPDATE portfolios SET shares=shares - :shares WHERE symbol=:symbol AND id=:id", \
                id=session["user_id"], shares=shares, symbol=stock["symbol"])

        #redirect to index
        return redirect(url_for("index"))