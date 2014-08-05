#!/usr/bin/python3
# Backend to Limbo4. This is called as a cgi script.

# CGI scripts must start with this.
print("Content-Type:text/html\n\n")

import cgi, cgitb
cgitb.enable()
import sqlite3 as sql
import datetime
# All prices should be manipulated as Decimal values roudned to two places after
# the decimal point. All fractions should also be Decimal values.
# Use str(decimal_value) to get the representation to put in the database.
import decimal
from decimal import Decimal
decimal.getcontext().prec = 6

# There's a decent sqlite tutorial here:
# http://zetcode.com/db/sqlitepythontutorial/
sql_database = 'limbo4.db'

def round_price(decimal_price):
    """Take a decimal value and round down to the nearest cent."""
    return decimal_price.quantize(Decimal('.01'), rounding=decimal.ROUND_DOWN)

def price(string):
    return round_price(Decimal(string))

def first(iterable):
    for item in iterable:
        return item

def initialize_test_database():
    """This function should only be called on an empty new database. This
       function should also be where you create fake users/items for testing."""
    with sql.connect(sql_database) as connection:
        # Some notes on data storage:
        # Balance/Price are python decimal amounts, so they are stored as their
        # text representation.
        # All dates are stored in ISO 8601 format, which are the default string
        # representation of datetime objects.
        connection.execute("""CREATE TABLE Users(
                              Name      TEXT PRIMARY KEY NOT NULL,
                              Email     TEXT NOT NULL,
                              Balance   TEXT NOT NULL,
                              CaltechID INTEGER NOT NULL,
                              JoinDate  TEXT NOT NULL)""")
        # Stock is no longer valid if Count is zero or if it's after the expiry
        # date.
        connection.execute("""CREATE TABLE Items(
                              Name         TEXT PRIMARY KEY NOT NULL,
                              Count        INTEGER NOT NULL,
                              Price        TEXT NOT NULL,
                              Tax          TEXT NOT NULL,
                              StockDate    TEXT NOT NULL,
                              ExpiryDate   TEXT NOT NULL,
                              Description  TEXT)""")
        # An item is allowed multiple sellers. We keep this in a separate table.
        # The "profit split" should be a percentage of the price, and should
        # always sum up to 100% or less (in the case of optional limbo tax).
        connection.execute("""CREATE TABLE Sellers(
                              ItemName     TEXT NOT NULL,
                              Seller       TEXT NOT NULL,
                              ProfitSplit  TEXT NOT NULL)""")
        # Transactions
        # each field 'ProfitSplit' is some number between 0.0 and 1.0 inclusive.
        # likewise with tax, it is some number between 0.0 and 1.0 inclusive.
        #   Buying and Selling
        #     If a purchase has multiple sellers, then we use multiple rows.
        connection.execute("""CREATE TABLE Purchases(
                              ItemName     TEXT NOT NULL,
                              Date         TEXT NOT NULL,
                              StockDate    TEXT NOT NULL,
                              ExpiryDate   TEXT NOT NULL,
                              Buyer        TEXT NOT NULL,
                              Seller       TEXT NOT NULL,
                              ProfitSplit  TEXT NOT NULL,
                              PriceEach    TEXT NOT NULL,
                              Count        INTEGER NOT NULL,
                              Tax          TEXT NOT NULL)""")
        #   Money transfers
        connection.execute("""CREATE TABLE Transfers(
                              Date       TEXT NOT NULL,
                              Sender     TEXT NOT NULL,
                              Receiver   TEXT NOT NULL,
                              Amount     TEXT NOT NULL)""")
        #   Withdrawing and Depositing
        connection.execute("""CREATE TABLE BalanceChanges(
                              Date       TEXT NOT NULL,
                              User       TEXT NOT NULL,
                              Amount     TEXT NOT NULL)""")
        #   Stocking and Unstocking
        #     If a stocked item has multiple sellers, then we use multiple rows.
        connection.execute("""CREATE TABLE Stocking(
                              ItemName     TEXT NOT NULL,
                              Date         TEXT NOT NULL,
                              StockDate    TEXT NOT NULL,
                              ExpiryDate   TEXT NOT NULL,
                              Seller       TEXT NOT NULL,
                              ProfitSplit  TEXT NOT NULL,
                              PriceEach    TEXT NOT NULL,
                              OldCount     INTEGER NOT NULL,
                              NewCount     INTEGER NOT NULL,
                              Tax          TEXT NOT NULL)""")
        #   Anonymous Donations of cash
        connection.execute("""CREATE TABLE Donations(
                              Date       TEXT NOT NULL,
                              Amount     TEXT NOT NULL)""")
        #   Expiration events
        #     If the expired item has multiple sellers, we use multiple rows.
        connection.execute("""CREATE TABLE ExpiryEvent(
                              ItemName     TEXT NOT NULL,
                              Date         TEXT NOT NULL,
                              StockDate    TEXT NOT NULL,
                              ExpiryDate   TEXT NOT NULL,
                              Seller       TEXT NOT NULL,
                              ProfitSplit  TEXT NOT NULL,
                              PriceEach    TEXT NOT NULL,
                              Count        INTEGER NOT NULL,
                              Tax          TEXT NOT NULL)""")

        # Now we will populate the Users and Items tables with some fake users
        # and items.
        add_user("jrmole", "jrmole@blacker.caltech.edu")
        add_user("socialmole", "socialmole@blacker.caltech.edu")
        add_user("mole", "mole@blacker.caltech.edu")
        add_user("srmole", "srmole@blacker.caltech.edu")

        add_item("snapple", {"jrmole": '0.50', "srmole": '0.50'},
                 24, '1.23', '0.00', 52, 'A Juicy Beverage')
        add_item("Lorem ipsum", {"mole": '0.95'}, 2, '1.55', '0.05', 24,
                 """Lorem ipsum dolor sit amet, consectetur adipisicing elit""")
        add_item("Test item", {"mole": '0.95'}, 123, '1.23', '0.05', 24,
                 """Lorem ipsum dolor sit amet, consectetur adipisicing elit""")
    return True

def delete_test_database():
    """Delete the database. Be careful! Also rebuilds the database."""
    import os
    os.remove(sql_database)
    return initialize_test_database()

def checkout(itemname, buyer, count):
    """Buyer checkouts any amount of a single item."""
    date = datetime.datetime.now()
    profit_split_by_sellers = get_fraction_by_sellers(itemname)
    current_count, price_each, stockdate, expiry, _ = get_item_info(itemname)
    total_price = round_price(Decimal(price_each) * count)

    with sql.connect(sql_database) as connection:
        tax = first(connection.execute("SELECT Tax FROM Items WHERE Name=?",
                                      (itemname,)))

        # Subtract count from the item. If count is zero, then remove the item
        # record. If the count goes below zero, we have an error. Do not record
        # the transaction and return False.
        if current_count < count:
            return False
        elif current_count == count:
            connection.execute("DELETE FROM Items WHERE Name=?",
                               (itemname,))
            connection.execute("DELETE FROM Sellers WHERE ItemName=?",
                               (itemname,))
        else:
            connection.execute("UPDATE Items SET Count=? WHERE Name=?",
                               (current_count - count, itemname))

        # Subtract money from buyer
        connection.execute("UPDATE Users SET Balance=Balance-? WHERE Name=?",
                           (str(total_price), buyer))

        # Record the transaction
        for seller, profit_split in profit_split_by_sellers.items():
            connection.execute("INSERT INTO Purchases "
                               "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (itemname, date, stockdate, expiry, buyer,
                                seller, profit_split, price_each,
                                count, tax))
            # Add money to seller
            connection.execute("UPDATE Users SET Balance=Balance+? "
                               "WHERE Name=?",
                               (str(round_price(total_price *
                                                Decimal(profit_split))),
                                seller))
    return True


def add_item(itemname, sellers, count, price_each, tax, expiry_time_in_weeks,
             description=''):
    """Adds an item as being in-stock and stocked by certain sellers.
       Returns True if successful."""
    assert isinstance(count, int)
    assert isinstance(expiry_time_in_weeks, int)
    price_each = round_price(Decimal(price_each))
    tax = Decimal(tax)
    assert (sum(map(Decimal, sellers.values())) + tax == Decimal('1.00'))
    
    duration = datetime.timedelta(weeks=expiry_time_in_weeks)
    stockdate = datetime.datetime.now()
    expirydate = stockdate + duration
    
    with sql.connect(sql_database) as connection:
        connection.execute("INSERT INTO Items VALUES(?, ?, ?, ?, ?, ?, ?)",
                           (itemname, count, str(price_each), str(tax),
                            stockdate, expirydate, description))
        for seller, profit_split in sellers.items():
            connection.execute("INSERT INTO Sellers VALUES(?, ?, ?)",
                               (itemname, seller, profit_split))
            connection.execute("INSERT INTO Stocking "
                               "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (itemname, stockdate, stockdate, expirydate,
                                seller, profit_split, str(price_each), 0,
                                count, str(tax)))
    return True

def add_user(username, email, uid=0):
    """Creates a new user and inserts into the database.
       Returns True if successful"""
    assert isinstance(uid, int)
    with sql.connect(sql_database) as connection:
        balance = Decimal('0.00')
        joindate = datetime.datetime.now()
        connection.execute("INSERT INTO Users VALUES(?, ?, ?, ?, ?)",
                           (username, email, str(balance), uid, joindate))
    return True

def get_all_stock():
    """Returns all items stocked and all the associated data."""
    with sql.connect(sql_database) as connection:
        return list(connection.execute("SELECT * FROM Items"))

def get_fraction_by_sellers(itemname):
    """Returns a dictionary with sellers as keys, profit fractions as values."""
    with sql.connect(sql_database) as connection:
        rows = list(connection.execute("SELECT ProfitSplit, Seller "
                                       "FROM Sellers WHERE ItemName=?",
                                       (itemname,)))
    return dict((seller, float(fraction)) for fraction, seller in rows)

def get_all_sellers():
    """Returns a dictionary with item names as keys, seller lists as values."""
    with sql.connect(sql_database) as connection:
        rows = list(connection.execute("SELECT ItemName, Seller FROM Sellers"))
    sellers_by_item = {}
    for item, seller in rows:
        if item in sellers_by_item:
            sellers_by_item[item].append(seller)
        else:
            sellers_by_item[item] = [seller]
    return sellers_by_item

def get_user_stock(username):
    """Returns all item names which list the given username as a seller."""
    rows = []
    with sql.connect(sql_database) as connection:
        for row in connection.execute("SELECT ItemName FROM Sellers "
                                      "WHERE Seller=?", (username,)):
            rows.append(row[0])
    return rows

def get_usernames():
    """Returns a list of all usernames."""
    names = []
    with sql.connect(sql_database) as connection:
        for row in connection.execute("SELECT Name FROM Users"):
            names.append(row[0])
    return names

def get_username(username):
    """Returns the information on a username if it exists, otherwise False."""
    with sql.connect(sql_database) as connection:
        rows = connection.execute("SELECT * FROM Users WHERE Name=?",
                                  (username,))
    if rows:
        return first(rows)
    else:
        return False

def get_store_info(username):
    """This request returns all the information needed when store.html loads.
       This includes the username, all in-stock items, all items being sold by
       the user, and past transactions of that user."""
    userinfo = get_username(username)
    if not username:
        return False
    all_stock = get_all_stock()
    usernames = get_usernames()
    user_stock = get_user_stock(username)
    sellers_by_item = get_all_sellers()
    transactions = get_user_transactions(username)
    return (userinfo, all_stock, usernames, user_stock,
            sellers_by_item, transactions)

def get_item_info(itemname):
    """Returns count, price, stock date, expiry date, description of an item."""
    with sql.connect(sql_database) as connection:
        row = first(connection.execute("SELECT Count, Price, StockDate, "
                                       "ExpiryDate, Description FROM Items "
                                       "WHERE Name=?", (itemname,)))
    count, price_each, stockdate, expiry, desc = row
    return count, price_each, stockdate, expiry, desc

def addremove_item(itemname, count_to_add):
    """Modifies stock by altering item count only. Returns True if
       successful."""
    assert isinstance(count_to_add, int)
    date = datetime.datetime.now()
    with sql.connect(sql_database) as connection:
        _, count, price, tax, stockdate, expirydate, _ = first(
            connection.execute("SELECT * FROM Items WHERE Name=?",
                               (itemname,)))

        if (-count_to_add) > count:
            return False

        profit_splits_by_seller = dict(
            connection.execute("SELECT Seller, ProfitSplit FROM Sellers "
                               "WHERE ItemName=?", (itemname,)))

        if (-count_to_add) == count:
            connection.execute("DELETE FROM Sellers WHERE ItemName=?",
                               (itemname,))
            connection.execute("DELETE FROM Items WHERE Name=?",
                               (itemname,))
        else:
            connection.execute("UPDATE Items SET Count=? WHERE Name=?",
                               (count + count_to_add, itemname))

        for seller, profit_split in profit_splits_by_seller.items():
            # Record this stock change
            connection.execute("INSERT INTO Stocking "
                               "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (itemname, date, stockdate, expirydate,
                                seller, profit_split, price, count,
                                count + count_to_add, tax))
    return True

def check_expired_stock():
    """Removes all stock which has expired and records this."""
    pass # todo

def get_user_transactions(username):
    """Returns all transactions associated with a username."""
    with sql.connect(sql_database) as connection:
        purchases = list(connection.execute("SELECT * FROM Purchases "
                                            "WHERE Buyer=? OR Seller=? "
                                            "ORDER BY Date",
                                            (username, username)))
        transfers = list(connection.execute("SELECT * FROM Transfers "
                                            "WHERE Sender=? OR Receiver=? "
                                            "ORDER BY Date",
                                            (username, username)))
        balance = list(connection.execute("SELECT * FROM BalanceChanges "
                                          "WHERE User=? "
                                          "ORDER BY Date", (username,)))
        stock = list(connection.execute("SELECT * FROM Stocking "
                                        "WHERE Seller=? "
                                        "ORDER BY Date", (username,)))
        expiry = list(connection.execute("SELECT * FROM ExpiryEvent "
                                         "WHERE Seller=? "
                                         "ORDER BY Date", (username,)))
    return purchases, transfers, balance, stock, expiry

def transfer_funds(sender, receiver, amount):
    """Transfers any nonzero amount of funds from one user to another.
       Returns True if successful."""
    amount = price(amount)
    assert amount > 0
    date = datetime.datetime.now()
    with sql.connect(sql_database) as connection:
        sender_balance = first(connection.execute("SELECT Balance FROM Users "
                                                  "WHERE Name=?",
                                                  (sender,)))
        receiver_balance = first(connection.execute("SELECT Balance FROM Users "
                                                    "WHERE Name=?",
                                                    (receiver,)))
        balance = Decimal(balance)
        connection.execute("UPDATE Users SET Balance=Balance-? WHERE Name=?",
                           (str(sender_balance - amount), sender))
        connection.execute("UPDATE Users SET Balance=Balance+? WHERE Name=?",
                           (str(receiver_balance + amount), receiver))
        connection.execute("INSERT INTO Transfers VALUES(?, ?, ?, ?)",
                           (date, sender, receiver, str(amount)))
    return True

def donate(amount):
    """Records an anonymous donation of cash. Returns True if successful."""
    amount = price(amount)
    assert amount > 0
    date = datetime.datetime.now()
    with sql.connect(sql_database) as connection:
        connection.execute("INSERT INTO Donations VALUES(?, ?)", (date, amount))
    return True

def get_total_cash():
    """The expected amount of cash in Limbo is the sum of all user balances
       and all donations."""
    with sql.connect(sql_database) as connection:
        balances = list(connection.execute("SELECT Balance FROM Users"))
        total = sum(Decimal(balance[0]) for balance in balances)
        donations = list(connection.execute("SELECT Amount FROM Donations"))
        total_donations = sum(Decimal(donation[0]) for donation in donations)
        return total + total_donations

def change_balance(username, amount):
    """Deposit or withdraw some amount."""
    amount = price(amount)
    date = datetime.datetime.now()
    with sql.connect(sql_database) as connection:
        if amount == 0:
            return True
        else:
            connection.execute("UPDATE Users SET Balance=Balance+? "
                               "WHERE Name=?", (str(amount), username))
        connection.execute("INSERT INTO BalanceChanges VALUES(?, ?, ?)",
                           (date, username, str(amount)))
    return True

def main():
    # These are the allowed actions of cgi requests.
    actions = {
        "add_user":     add_user,
        "usernames":    get_usernames,
        "username":     get_username,
        "store_info":   get_store_info,
        "add_item":     add_item,
        "addremove":    addremove_item,
        "item_info":    get_item_info,
        "checkout":     checkout,
        "transactions": get_user_transactions,
        "transfer":     transfer_funds,
        "donate":       donate,
        "cash":         get_total_cash,
        "balance":      change_balance,
        # remove the following line in production
        "delete_test_database": delete_test_database,
    }
    # Get cgi arguments
    form = cgi.FieldStorage()
    action = form.getfirst("action", "")
    # If no valid action is provided, don't do anything.
    if action not in actions:
        return
    function = actions[action]
    # What is about to happen uses CPython-specific code to find the arguments
    # in the function and assign them based on name.
    argnames = function.__code__.co_varnames[:function.__code__.co_argcount]
    arguments_to_apply = {}
    for argname in argnames:
        arguments_to_apply[argname] = eval(form.getfirst(argname, None))
    # Print the return value to send to the client.
    print(function(**arguments_to_apply))

main()
