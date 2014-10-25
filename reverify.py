#!/usr/bin/python
# Computes what balances should be based on transaction history, then gives the
# option to update balances to reflect history. This tool is mostly good for
# fixing bugs.
from server import *
import sqlite3 as sql
import datetime

if __name__ == '__main__':
    with DBConnection() as conn:
        users = Users.select(conn, where=None)
        fixes = {}
        for user in users:
            # The amount of money a buyer pays is PriceEach * Count, but we record
            # it multiple times (one for each seller). So we need to not select
            # multiple rows with the same date.
            purchases = Purchases.select(conn, "Buyer = ? group by Date", user.Name)
            # The amount of money a seller gets is PriceEach * Count * ProfitSplit
            # Since the sum of ProfitSplits *and* Tax adds up to 1.0
            sales = Purchases.select(conn, "Seller = ?", user.Name)
            transfers = Transfers.select(conn, "Sender = ?", user.Name)
            received = Transfers.select(conn, "Receiver = ?", user.Name)
            changes = BalanceChanges.select(conn, "User = ?", user.Name)
            revenue = (sum(dollar_amount(change.Amount) for change in changes)
                       + sum(round_dollar_amount(dollar_amount(sale.PriceEach) * int(sale.Count) * Decimal(sale.ProfitSplit)) for sale in sales)
                       + sum(dollar_amount(receival.Amount) for receival in received)
                       - sum(round_dollar_amount(dollar_amount(purchase.PriceEach) * int(purchase.Count)) for purchase in purchases)
                       - sum(dollar_amount(transfer.Amount) for transfer in transfers))
            balance = user.Balance
            if (balance != str(revenue)):
                print("User %s" % user.Name)
                print("\tRecorded balance is %s." % balance)
                print("\tExpected balance is %s" % revenue)
                fixes[user.Name] = revenue
        print("Would you like to fix all balances? [y/n]")
        if input() == 'y':
            for username, new_balance in fixes.items():
                Users.update(conn, "Balance=?", "Name=?", str(new_balance), username)


    exit(0)
