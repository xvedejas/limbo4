from browser import doc, alert, html
from limbo import async_request, sync_request, notify, redirect, Keycode

class Item():
    def __init__(self, database_row):
        self.name, self.count, self.price, self.tax, self.stock_date, \
            self.expiry_date, self.desc = database_row
    def __repr__(self):
        return "%s x%i" % (self.name, self.count)

class StoreSession():
    def __init__(self):
        self.username = eval(doc.query.getfirst("username", ""))
        sync_request(self.get_store_info_done,
                     action="store_info",
                     username=repr(self.username))

    def get_store_info_done(self, t):
        userinfo, all_stock, usernames, \
            user_stock, sellers_by_item, transactions = t
        self.usernames = usernames
        self.user_stock = user_stock
        if not userinfo:
            # Invalid username
            redirect("index.html")
        username, email, balance, uid, signup_date = userinfo
        self.balance = float(balance)
        doc["welcome"].html = ("Welcome, <b>%s</b>. Your balance is $%.2f." %
                               (username, self.balance))
        doc["new_balance"].html = ("Your new balance will be $%.2f" %
                                   self.balance)

        # Build a list of all things in-stock
        inventory_list = list(map(Item, all_stock))
        self.inventory = dict((item.name, item) for item in inventory_list)
        self.in_stock = dict((item.name, item.count) for item in inventory_list)
        self.checkout = {}

        # And the user's own stock
        self.my_stock = dict((itemname, self.inventory[itemname])
                             for itemname in user_stock)

        # Keep track of stock amount changes (before confirmed)
        self.to_add = dict((itemname, 0) for itemname in self.user_stock)

        self.payment = 0.0
        self.populate_lists()

        doc["in_stock"].bind("click", self.select_item_event)
        doc["in_stock"].bind("dblclick", self.checkout_event)
        doc["in_stock"].bind("keyup", self.checkout_all_event)

        doc["checkout"].bind("click", self.select_item_event)
        doc["checkout"].bind("dblclick", self.undo_checkout_event)
        doc["checkout"].bind("keyup", self.undo_checkout_all_event)

        doc["clear_button"].bind("click", self.clear_items_event)

        doc['search'].bind('keydown', self.search_event)
        doc['search'].bind('keyup', self.search_event)

        doc['payment'].bind('keyup', self.set_payment_event)
        self.payment = 0.0

        doc["inventory"].bind("dblclick", self.remove_inventory_event)
        doc["inventory"].bind("keyup", self.inventory_key_event)

        doc["add_seller"].bind("click", self.add_seller_space_event)
        self.seller_count = 1

        doc["usernames"].html = ''.join('<option value="%s">' % user
                                        for user in self.usernames
                                        if user != self.username)

        doc["add_item"].bind("click", self.stock_event)

        doc['price'].bind('keyup', self.change_profits_event)
        doc['tax'].bind('keyup', self.change_profits_event)

        doc['checkout_button'].bind('click', self.checkout_submit_event)

        doc['confirm_remove_inventory'].bind('click',
                                             self.confirm_addremove_event)
        doc['clear_remove_inventory'].bind('click',
                                           self.clear_to_addremove_event)

        doc['transfer_button'].bind('click', self.transfer_event)

        self.sellers_by_item = sellers_by_item

        # Populate the list of transactions.
        ## TODO: when a transaction is clicked on, shows more info
        purchases, transfers, balances, stocks, expiries = transactions

        entries = []
        for purchase in purchases:
            item, date, stockdate, expirydate, buyer, seller, profit_split, \
                price_each, count, tax = purchase
            entry = ("<option>{0}: {1}x {2} at ${3} each; "
                     "{4} sold to {5}.</option>")
            entries.append(entry.format(date, count, item,
                                        price_each, seller, buyer))

        for transfer in transfers:
            date, sender, receiver, amount = transfer
            entry = "<option>{0}: transfer ${1} from {2} to {3}</option>"
            entries.append(entry.format(date, amount, sender, receiver))

        for balance in balances:
            date, user, amount = balance
            if amount > 0:
                entry = "<option>{0}: deposited ${1}</option>"
                entries.append(entry.format(date, amount))
            else:
                entry = "<option>{0}: withdrew ${1}</option>"
                entries.append(entry.format(date, -amount))

        for stock in stocks:
            item, date, stockdate, expirydate, seller, profit_split, \
                price_each, oldcount, newcount, tax = stock
            entry = ("<option>{0}: change stock from {1} to "
                     "{2}x {3} (${4} each)</option>")
            entries.append(entry.format(date, oldcount, newcount,
                                        item, price_each))

        doc["transactions"].html = ''.join(entries)

    def transfer_event(self, ev):
        """The user has clicked the 'transfer' button to transfer some of their
           funds to another user."""
        amount = doc['transfer_amount'].value
        target = doc['transfer_target'].value
        try:
            if not amount:
                notify("Amount must be an integer")
                return
            count = int(amount)
        except ValueError:
            notify("Amount must be an integer")
            return
        if target not in self.usernames:
            notify("Invalid username")
            return
        async_request(self.done_checkout,
                      action='transfer',
                      sender=repr(self.username),
                      receiver=repr(target),
                      amount=amount)

    def checkout_submit_event(self, ev):
        """The user has clicked the checkout submit button. Send an async
           request for each item. TODO: it might be better to just send one
           request which encodes for each item."""
        for child in doc['checkout']:
            item = child.id
            count = child.count
            async_request(self.done_checkout,
                          action="checkout",
                          itemname=repr(item),
                          buyer=repr(self.username),
                          count=count)

    def clear_to_addremove_event(self, ev):
        """Clears the inventory stock amount modifications."""
        self.to_add = dict((itemname, 0) for itemname in self.user_stock)
        self.populate_lists()

    def confirm_addremove_event(self, ev):
        """Confirms changes in inventory."""
        any_changes = False
        for child in doc['inventory']:
            item = child.id
            to_add = self.to_add[item]
            if to_add != 0:
                async_request(self.done_checkout,
                              action="addremove",
                              itemname=repr(item),
                              count_to_add=to_add)
                any_changes = True
        if any_changes:
            redirect("store.html", username=repr(self.username))

    def done_checkout(self, res):
        if res:
            redirect("store.html", username=repr(self.username))
        else:
            notify("Transaction Failed")

    def set_payment_event(self, ev):
        try:
            self.payment = float(doc['payment'].value)
        except:
            self.payment = 0.0
        self.populate_lists()

    def populate_lists(self):
        """Fills the selection lists"""
        option = ("<option value=\"{0}\" id=\"{0}\" count={1}>"
                  "{1}x {0} (${2})</option>")

        doc["in_stock"].html = ''.join(
            option.format(itemname,
                          amount,
                          self.inventory[itemname].price)
            for itemname, amount in self.in_stock.items())
        doc["checkout"].html = ''.join(
            option.format(itemname,
                          amount,
                          self.inventory[itemname].price)
            for itemname, amount in self.checkout.items())

        total = sum(amount * float(self.inventory[itemname].price)
                    for itemname, amount in self.checkout.items())
        doc["total"].html = "Your total is $%.2f" % total
        new_balance = self.balance - total + self.payment
        doc["new_balance"].html = "Your new balance will be $%.2f" % new_balance

        option = ("<option value=\"{0}\" id=\"{0}\" count={1}>"
                  "{1}x {0} (${2}) {3}</option>")
        doc["inventory"].html = ''.join(
            option.format(itemname,
                          item.count,
                          item.price,
                          "[To Change: %i]" % self.to_add[itemname]
                          if self.to_add[itemname] else "")
            for itemname, item in self.my_stock.items())

    def select_item_event(self, ev):
        """Single-clicking on an item should show its description"""
        item = self.inventory[ev.target.value]
        doc["description"].html = item.desc
        sellers = ', '.join(self.sellers_by_item[item.name])
        doc["sold_by"].html = 'Sold by: <b>%s</b>' % sellers

    def select_item_key_event(self, ev):
        if ev.keyCode == Keycode.enter:
            self.checkout_event(ev)
        self.select_item_event(ev)

    def checkout_event(self, ev):
        """Double-clicking on inventory should add to self.checkout"""
        item = self.inventory[ev.target.value]
        if self.in_stock[item.name] == 0:
            return
        self.in_stock[item.name] -= 1
        if item.name not in self.checkout:
            self.checkout[item.name] = 1
        else:
            self.checkout[item.name] += 1
        self.populate_lists()

    def checkout_all_event(self, ev):
        """Pressing Enter on inventory should add all to self.checkout"""
        if ev.keyCode != Keycode.enter:
            # It's possible we just pressed an arrow key, changing the item
            # selection.
            self.select_item_key_event(ev)
            return
        item = self.inventory[ev.target.value]
        if self.in_stock[item.name] == 0:
            return
        if item.name not in self.checkout:
            self.checkout[item.name] = self.in_stock[item.name]
        else:
            self.checkout[item.name] += self.in_stock[item.name]
        self.in_stock[item.name] = 0
        self.populate_lists()

    def undo_checkout_event(self, ev):
        """Double-clicking on self.checkout items should remove them"""
        item = self.inventory[ev.target.value]
        self.checkout[item.name] -= 1
        self.in_stock[item.name] += 1
        if self.checkout[item.name] == 0:
            del self.checkout[item.name]
        self.populate_lists()

    def undo_checkout_all_event(self, ev):
        """Pressing delete on self.checkout items should remove them all"""
        if ev.keyCode != Keycode.delete:
            # It's possible we just pressed an arrow key, changing the item
            # selection.
            self.select_item_key_event(ev)
            return
        item = self.inventory[ev.target.value]
        self.in_stock[item.name] += self.checkout[item.name]
        del self.checkout[item.name]
        self.populate_lists()

    def clear_items_event(self, ev):
        """Clears the 'shopping cart' style checkout."""
        for itemname in self.checkout:
            self.in_stock[itemname] += self.checkout[itemname]
        self.checkout = {}
        self.populate_lists()

    def search_event(self, ev):
        """Whenever the search term is altered, filters items shown."""
        search_term = doc["search"].value.lower()
        # Hide all in_stock items which don't satisfy the search term
        all_hidden = True
        for option in doc["in_stock"].children:
            option.hidden = search_term not in option.value.lower()
            all_hidden = all_hidden and option.hidden
        # ...unless none of them satisfy the search term
        if all_hidden:
            for option in doc["in_stock"].children:
                option.hidden = False

    def inventory_key_event(self, ev):
        """Any key event which changes our stock counts (non-final)."""
        itemname = ev.target.value
        if ev.keyCode == Keycode.delete:
            self.to_add[itemname] = -self.inventory[itemname].count
        elif ev.keyCode in Keycode.digits:
            self.to_add[itemname] += Keycode.digits.index(ev.keyCode)
        self.populate_lists()

    def remove_inventory_event(self, ev):
        """Double click on our personal stock"""
        itemname = ev.target.value
        if self.inventory[itemname].count >= 0:
            self.to_add[itemname] -= 1
            self.populate_lists()

    def add_seller_space_event(self, ev):
        """Fill in usernames autocomplete in stocking items form"""
        self.seller_count += 1
        # The text input uses the datalist tag to suggest autocomplete terms.
        # This is separate from browser autocomplete, which we want to specify
        # as off.
        # The datalist tag is populated by get_usernames_done(). For explanation
        # on the datalist tag, see
        # http://www.w3schools.com/tags/tag_datalist.asp
        seller_id = "additional_seller" + str(self.seller_count)
        profit_id = "additional_seller_profit" + str(self.seller_count)
        entry = html.TR(html.TD(html.INPUT(type="text",
                                           id=seller_id,
                                           list="usernames",
                                           autocomplete="off",
                                           placeholder="seller"),
                                align="right") +
                        html.TD(html.INPUT(type="text",
                                           placeholder="percent of profits",
                                           id=profit_id)))
        doc["stocking_table"] <= entry
        doc[profit_id].bind("keyup", self.change_profits_event)

    def change_profits_event(self, ev):
        """When we alter the profit splitting in the stock-item form, we want to
           update the amounts (and percentages) of profit shown."""
        values = [doc["additional_seller_profit" + str(seller + 2)].value
                  for seller in range(self.seller_count - 1)]
        total = 0.0
        for value in values:
            if value:
                total += float(value)
        total += float(doc["tax"].value)
        percent = 100.0 - total
        listed_price_each = float(doc["price"].value)
        doc["your_percentage"].html = str(percent) + '%'Delete key or plus key on our personal stock
        doc["your_income"].html = '$%.2f' % (percent * 0.01 * listed_price_each)

    def stock_item_done(self, res):
        """Refresh when an item is stocked."""
        redirect("store.html", username=repr(self.username))

    def stock_event(self, ev):
        """Validate the form for stocking items and then stock the item."""
        try:
            if not doc["itemcount"].value:
                notify("Count must be an integer")
                return
            count = int(doc["itemcount"].value)
        except ValueError:
            notify("Count must be an integer")
            return
        try:
            if not doc["expiry"].value:
                expiry = 52
            else:
                expiry = int(doc["expiry"].value)
        except ValueError:
            notify("Weeks until expiry must be an integer")
            return
        try:
            if not doc["price"].value:
                notify("Invalid price")
                return
            price = "%.2f" % float(doc["price"].value)
        except ValueError:
            notify("Invalid price")
            return
        try:
            if not doc["tax"].value:
                notify("Invalid tax")
                return
            tax = float(doc["tax"].value) * 0.01
        except ValueError:
            notify("Invalid tax percentage")
            return
        if tax > 100.0:
            notify("Invalid tax percentage. Must be less than 100%.")
            return
        name = doc["itemname"].value
        if name in self.in_stock:
            notify("There is already an item with this name. "
                   "Please provide a unique and descriptive name.")
            return
        if len(name) < 4:
            notify("Please input a name at least 4 characters long.")
            return
        description = doc["description"].text
        if len(description) < 5:
            notify("Please add a useful description! "
                   "It will help people buy your stuff.")
            return
        total_profit = 0.00
        sellers = {}
        for seller_number in range(2, self.seller_count + 1):
            seller = doc["additional_seller%i" % seller_number].value
            if seller == self.username or seller not in self.usernames:
                notify("Invalid Seller Username Chosen")
                return
            profit_string = doc["additional_seller_profit%i" %
                                seller_number].value
            profit = float(profit_string) * 0.01
            total_profit += profit
            if total_profit >= 1.00:
                notify("Invalid profits chosen: "
                       "profits and tax cannot total over 100%.")
                return
            sellers[seller] = profit

        sellers[self.username] = 1.00 - total_profit

        async_request(self.stock_item_done, action="add_item",
                      itemname=repr(name), sellers=sellers, count=count,
                      price=price, tax=tax, expiry_time_in_weeks=expiry,
                      description=repr(description))

StoreSession()
