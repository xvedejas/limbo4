#!/usr/bin/python3
# Backend to Limbo4. This is called as a cgi script.

# CGI scripts must start with this.
print("Content-Type:text/html\n\n")

import cgi, cgitb
cgitb.enable()

import sys
sys.path.append('../')
from server import *

def initialize_test_database():
    """This function should only be called on an empty new database. This
       function should also be where you create fake users/items for testing."""
    with sql.connect(sql_database) as conn:
        Users.create(conn)
        Items.create(conn)
        Sellers.create(conn)
        Purchases.create(conn)
        Transfers.create(conn)
        BalanceChanges.create(conn)
        Stocking.create(conn)
        Donations.create(conn)
        ExpiryEvents.create(conn)
        Statistics.create(conn)

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

    with sql.connect(sql_database) as conn:
        tax = Items.select_one(conn, "Name=?", itemname).Tax

        # Subtract count from the item. If count is zero, then remove the item
        # record. If the count goes below zero, we have an error. Do not record
        # the transaction and return False.
        new_count = current_count - count
        if new_count < 0:
            return False
        elif new_count == 0:
            Items.delete(conn, "Name=?", itemname)
            Sellers.delete(conn, "ItemName=?", itemname)
        else:
            Items.update(conn, "Count=?", "Name=?", new_count, itemname)

        # Subtract money from buyer
        ## Todo: use demical
        Users.update(conn, "Balance=Balance-?", "Name=?",
                     str(total_price), buyer)

        for seller, profit_split in profit_split_by_sellers.items():
            # Record the transaction
            Purchases.insert(conn, itemname, date, stockdate, expiry,
                                          buyer, seller, profit_split,
                                          price_each, count, tax)
            # Add money to seller
            Users.update(conn, "Balance=Balance+?", "Name=?",
                         str(round_price(total_price * Decimal(profit_split))),
                         seller)
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

    with sql.connect(sql_database) as conn:
        Items.insert(conn, itemname, count, str(price_each), str(tax),
                                 stockdate, expirydate, description)
        for seller, profit_split in sellers.items():
            Sellers.insert(conn, itemname, seller, profit_split)
            Stocking.insert(conn,
                            itemname, stockdate, stockdate, expirydate,
                            seller, profit_split, str(price_each), 0,
                            count, str(tax))
    return True

def add_user(username, email, uid=0):
    """Creates a new user and inserts into the database.
       Returns True if successful"""
    assert isinstance(uid, int)
    with sql.connect(sql_database) as conn:
        balance = Decimal('0.00')
        joindate = datetime.datetime.now()
        Users.insert(conn, username, email, str(balance), uid, joindate)
    return True

def get_all_stock():
    """Returns all items stocked and all the associated data."""
    with sql.connect(sql_database) as conn:
        return list(Items.select(conn, None))

def get_fraction_by_sellers(itemname):
    """Returns a dictionary with sellers as keys, profit fractions as values."""
    with sql.connect(sql_database) as conn:
        rows = Sellers.select(conn, "ItemName=?", itemname)
    return dict((row.Seller, row.ProfitSplit) for row in rows)

def get_all_sellers():
    """Returns a dictionary with item names as keys, seller lists as values."""
    with sql.connect(sql_database) as conn:
        rows = Sellers.select(conn, None)
    sellers_by_item = {}
    for row in rows:
        if row.ItemName in sellers_by_item:
            sellers_by_item[row.ItemName].append(row.Seller)
        else:
            sellers_by_item[row.ItemName] = [row.Seller]
    return sellers_by_item

def get_user_stock(username):
    """Returns all item names which list the given username as a seller."""
    rows = []
    with sql.connect(sql_database) as conn:
        for row in Sellers.select(conn, "Seller=?", username):
            rows.append(row.ItemName)
    return rows

def get_usernames():
    """Returns a list of all usernames."""
    names = []
    with sql.connect(sql_database) as conn:
        for row in Users.select(conn, None):
            names.append(row.Name)
    return names

def get_username(username):
    """Returns the information on a username if it exists, otherwise False."""
    with sql.connect(sql_database) as conn:
        t = Users.select_one(conn, "Name=?", username)
    return t

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
    with sql.connect(sql_database) as conn:
        row = Items.select_one(conn, "Name=?", itemname)
    return row.Count, row.Price, row.StockDate, row.ExpiryDate, row.Description

def addremove_item(itemname, count_to_add):
    """Modifies stock by altering item count only. Returns True if
       successful."""
    assert isinstance(count_to_add, int)
    date = datetime.datetime.now()
    with sql.connect(sql_database) as conn:
        row = Items.select_one(conn, "Name=?", itemname)
        _, count, price, tax, stockdate, expirydate, _ = row
        new_count = count + count_to_add
        if new_count < 0:
            return False
        
        rows = Sellers.select(conn, "ItemName=?", itemname)
        profit_splits_by_seller = dict((row.Seller, row.ProfitSplit)
                                       for row in rows)
        
        if new_count == 0:
            Sellers.delete(conn, "ItemName=?", itemname)
            Items.delete(conn, "ItemName=?", itemname)
        else:
            Items.update(conn, "Count=?", "Name=?", new_count, itemname)

        for seller, profit_split in profit_splits_by_seller.items():
            # Record this stock change
            Stocking.insert(conn, itemname, date, stockdate, expirydate,
                                seller, profit_split, price, count,
                                new_count, tax)
    return True

def get_user_transactions(username):
    """Returns all transactions associated with a username."""
    with sql.connect(sql_database) as conn:
        purchases = Purchases.select(conn, "Buyer=? OR Seller=?",
                                     username, username)
        transfers = Transfers.select(conn, "Sender=? OR Receiver=?",
                                     username, username)
        balances = BalanceChanges.select(conn, "User=?", username)
        stocks = Stocking.select(conn, "Seller=?", username)
        expiries = ExpiryEvents.select(conn, "Seller=?", username)
    return purchases, transfers, balances, stocks, expiries

def transfer_funds(sender, receiver, amount):
    """Transfers any nonzero amount of funds from one user to another.
       Returns True if successful."""
    amount = price(amount)
    assert amount > 0
    date = datetime.datetime.now()
    with sql.connect(sql_database) as conn:
        sender_balance = Users.select_one(conn, "Name=?", (sender,)).Balance
        receiver_balance = Users.select_one(conn, "Name=?", (receiver,)).Balance
        
        Users.update(conn, "Balance=?", "Name=?",
                     str(sender_balance - amount), sender)
        Users.update(conn, "Balance=?", "Name=?",
                     str(receiver_balance + amount), receiver)
        Transfers.insert(conn, date, sender, receiver, str(amount))
    return True

def donate(amount):
    """Records an anonymous donation of cash. Returns True if successful."""
    amount = price(amount)
    assert amount > 0
    date = datetime.datetime.now()
    with sql.connect(sql_database) as conn:
        Donations.insert(conn, date, amount)
    return True

def get_total_cash():
    """The expected amount of cash in Limbo is the sum of all user balances
       and all donations."""
    with sql.connect(sql_database) as conn:
        total_balances = sum(Decimal(user.Balance)
                             for user in Users.select(conn, None))
        total_donations = sum(Decimal(donation.Amount)
                              for donation in Donations.select(conn, None))
        return total_balances + total_donations

def change_balance(username, amount):
    """Deposit or withdraw some amount."""
    amount = price(amount)
    date = datetime.datetime.now()
    with sql.connect(sql_database) as conn:
        if amount == 0:
            return True
        else:
            Users.update(conn, "Balance=Balance+?", "Name=?",
                         str(amount), username)
        BalanceChanges.insert(conn, date, username, str(amount))
    return True

def generate_transactions_csv(username):
    purchases, transfers, balances, stocks, expiries = \
        get_user_transactions(username)
    for purchase in purchases:
        print("Purchase, %s<br />" % str(purchase)[1:-1])
    for transfer in transfers:
        print("Transfer, %s<br />" % str(transfer)[1:-1])
    for balance in balances:
        print("Balance, %s<br />" % str(balance)[1:-1])
    for stock in stocks:
        print("Stock, %s<br />" % str(stock)[1:-1])
    for expiry in expiries:
        print("Expiry, %s<br />" % str(expiry)[1:-1])
    return ''

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
        "transactions.csv": generate_transactions_csv,
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
