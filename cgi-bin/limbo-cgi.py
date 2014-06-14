#!/usr/bin/python3
# Backend to Limbo4. This is called as a cgi script.

# CGI scripts must start with this.
print("Content-Type:text/html\n\n")

import cgi, cgitb
import sqlite3 as sql    
from decimal import *
getcontext().prec = 6
import datetime
cgitb.enable()
form = cgi.FieldStorage()

# There's a decent sqlite tutorial here: http://zetcode.com/db/sqlitepythontutorial/
database = 'limbo4.db'

def round(decimal):
    decimal.quantize(Decimal('.01'), rounding=ROUND_DOWN)

def initialize_test_database():
    """This function should only be called on an empty new database. This
       function should also be where you create fake users/items for testing."""
    with sql.connect(database) as connection:
        # Some notes on data storage:
        # Balance/Price are python decimal amounts, so they are stored as their text representation
        # All dates are stored in ISO 8601 format, which are the default string representation of datetime objects.
        connection.execute("""CREATE TABLE Users(
                            Name     TEXT PRIMARY KEY NOT NULL,
                            Email    TEXT NOT NULL,
                            Balance  TEXT NOT NULL,
                            JoinDate INTEGER NOT NULL)""")
        # Stock is no longer valid if Count is zero or if it's after the expiry
        # date.
        connection.execute("""CREATE TABLE Items(
                              Name         TEXT NOT NULL UNIQUE,
                              Seller       TEXT NOT NULL,
                              Count     INTEGER NOT NULL,
                              Price        TEXT NOT NULL,
                              StockDate    TEXT NOT NULL,
                              ExpiryDate   TEXT NOT NULL,
                              Description  TEXT)""")
        # A "Transaction" is either a purchase, money transfer, withdrawal, or
        # deposit. For a purchase, all fields need to be filled. For a transfer,
        # the "item" field is NULL. For a withdrawal, the Seller and Item fields
        # are NULL. For a deposit, the Buyer and Item fields are NULL.
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
        
        add_item("snapple", "jrmole", 24, Decimal('1.23'), 52, 'A Juicy Beverage')
        add_item("Lorem ipsum", "mole", 2, Decimal('1.55'), 24, 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.')
    return True

def delete_test_database():
    import os
    os.remove(database)

def add_item(itemname, sellername, count, price, expiry_time_in_weeks, description=''):
    with sql.connect(database) as connection:
        duration = datetime.timedelta(weeks=expiry_time_in_weeks)
        stockdate = datetime.datetime.now()
        expirydate = stockdate + duration
        connection.execute("INSERT INTO Items VALUES(?, ?, ?, ?, ?, ?, ?)",
                           (itemname, sellername, count, str(price), stockdate,
                            expirydate, description))

def add_user(username, email):
    with sql.connect(database) as connection:
        balance = Decimal('0.00')
        joindate = datetime.datetime.now()
        connection.execute("INSERT INTO Users VALUES(?, ?, ?, ?)",
                           (username, email, str(balance), joindate))

def get_all_stock():
    with sql.connect(database) as connection:
        rows = list(connection.execute("SELECT * FROM Items"))
    return rows

def get_user_stock(username):
    rows = []
    with sql.connect(database) as connection:
        for row in connection.execute("SELECT * FROM Items WHERE Name=?", (username,)):
            rows.append(row)
    return rows

def get_usernames():
    names = []
    with sql.connect(database) as connection:
        for row in connection.execute("SELECT Name FROM Users"):
            names.append(row[0])
    return names

def get_username(username):
    with sql.connect(database) as connection:
        rows = list(connection.execute("SELECT * FROM Users WHERE Name=?", (username,)))
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
    my_stock = get_user_stock(username)
    all_stock = get_all_stock()
    return (userinfo, my_stock, all_stock)

# These are the allowed actions of cgi requests.
actions = {
    "usernames": get_usernames,
    "username": get_username,
    "store_info": get_store_info,
    "init_test_database": initialize_test_database, # remove this line in production
    "delete_test_database": delete_test_database, # remove this line in production
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
        arguments_to_apply[argname] = form.getfirst(argname, None)
    # Print the return value
    print(function(**arguments_to_apply))

main()
