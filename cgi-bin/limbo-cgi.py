#!/usr/bin/python3
# Backend to Limbo4. This is called as a cgi script.

# CGI scripts must start with this.
print("Content-Type:text/html\n\n")

import cgi, cgitb
import sqlite3 as sql
import decimal
from decimal import Decimal
decimal.getcontext().prec = 6
import datetime
cgitb.enable()
form = cgi.FieldStorage()

# There's a decent sqlite tutorial here:
# http://zetcode.com/db/sqlitepythontutorial/
database = 'limbo4.db'

def decimal_round(d):
    d.quantize(Decimal('.01'), rounding=decimal.ROUND_DOWN)

def initialize_test_database():
    """This function should only be called on an empty new database. This
       function should also be where you create fake users/items for testing."""
    with sql.connect(database) as connection:
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
                              Count     INTEGER NOT NULL,
                              Price        TEXT NOT NULL,
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
        # A "Transaction" is either a purchase, money transfer, withdrawal, or
        # deposit. For a purchase, all fields need to be filled. For a transfer,
        # the "item" field is NULL. For a withdrawal, the Seller and Item fields
        # are NULL. For a deposit, the Buyer and Item fields are NULL.
        # If there were multiple sellers, then use multiple rows.
        connection.execute("""CREATE TABLE Transactions(
                              Date       TEXT NOT NULL,
                              Buyer      TEXT,
                              Seller     TEXT,
                              Item       INTEGER,
                              Count      INTEGER NOT NULL,
                              Price      TEXT NOT NULL,
                              StockDate  TEXT NOT NULL,
                              ExpiryDate TEXT NOT NULL)""")
        # Now we will populate the Users and Items tables with some fake users
        # and items.
        add_user("jrmole", "jrmole@blacker.caltech.edu")
        add_user("socialmole", "socialmole@blacker.caltech.edu")
        add_user("mole", "mole@blacker.caltech.edu")
        add_user("srmole", "srmole@blacker.caltech.edu")

        add_item("snapple", {"jrmole": '1.00'}, 24, '1.23', '0.00', 52,
                 'A Juicy Beverage')
        add_item("Lorem ipsum", {"mole": '0.90'}, 2, '1.55', '0.05', 24,
                 """Lorem ipsum dolor sit amet, consectetur adipisicing elit""")
    return True

def delete_test_database():
    import os
    os.remove(database)

def add_item(itemname, sellers, count, price, tax, expiry_time_in_weeks,
             description=''):
    with sql.connect(database) as connection:
        duration = datetime.timedelta(weeks=expiry_time_in_weeks)
        stockdate = datetime.datetime.now()
        expirydate = stockdate + duration
        connection.execute("INSERT INTO Items VALUES(?, ?, ?, ?, ?, ?)",
                           (itemname, count, str(price), stockdate,
                            expirydate, description))
        for seller, profit_split in sellers.items():
            connection.execute("INSERT INTO Sellers VALUES(?, ?, ?)",
                               (itemname, seller, profit_split))

def add_user(username, email, uid=0):
    with sql.connect(database) as connection:
        balance = Decimal('0.00')
        joindate = datetime.datetime.now()
        connection.execute("INSERT INTO Users VALUES(?, ?, ?, ?, ?)",
                           (username, str(email), str(balance), int(uid), joindate))
    return True

def get_all_stock():
    with sql.connect(database) as connection:
        rows = list(connection.execute("SELECT * FROM Items"))
    return rows

def get_sellers(itemname):
    with sql.connect(database) as connection:
        rows = list(connection.execute("SELECT Seller FROM Sellers WHERE ItemName=?", itemname))
    return rows

def get_user_stock(username):
    rows = []
    with sql.connect(database) as connection:
        for row in connection.execute("SELECT ItemName FROM Sellers WHERE Seller=?",
                                      (username,)):
            rows.append(row[0])
    return rows

def get_usernames():
    names = []
    with sql.connect(database) as connection:
        for row in connection.execute("SELECT Name FROM Users"):
            names.append(row[0])
    return names

def get_username(username):
    with sql.connect(database) as connection:
        rows = list(connection.execute("SELECT * FROM Users WHERE Name=?",
                                       (username,)))
    if rows:
        return rows[0]
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
    return (userinfo, all_stock, usernames, user_stock)

def remove_item(itemname, count_to_remove):
    """If count_to_remove >= count, removes all."""
    pass

def check_expired_stock():
    pass # todo

# These are the allowed actions of cgi requests.
actions = {
    "add_user": add_user,
    "usernames": get_usernames,
    "username": get_username,
    "store_info": get_store_info,
    "add_item": add_item,
    "remove_item": remove_item,
    # remove the following lines in production
    "init_test_database": initialize_test_database,
    "delete_test_database": delete_test_database,
}

def main():
    action = form.getfirst("action", "")
    # If no valid action is provided, don't do anything.
    if action not in actions:
        return
    function = actions[action]
    arguments_to_apply = {}
    # What is about to happen uses CPython-specific code to find the arguments
    # in the function.
    argnames = function.__code__.co_varnames[:function.__code__.co_argcount]
    for argname in argnames:
        arguments_to_apply[argname] = eval(form.getfirst(argname, None))
    # Print the return value
    print(function(**arguments_to_apply))

main()
