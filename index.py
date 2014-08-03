from browser import doc
from limbo import async_request, Keycode, redirect, notify

def login_event(event):
    """This is called when the login button is pressed."""
    login(doc["username"].value)

def keydown_event(event):
    """This is called when a key is pressed while the username box is in
       focus. We check to see if the enter key was pressed, if so we log in."""
    if event.keyCode == Keycode.enter:
        login_event(event)

def get_usernames_done(usernames):
    """Once we have a list of all usernames, we populate autocomplete"""
    doc["usernames"].html = ''.join('<option value="%s">' % user
                                    for user in usernames)

def login(username):
    """This is called when the login button is pressed."""
    async_request(login_done, action="username", username=repr(username))

def login_done(user_data):
    """If the server has returned data, then the username exists and we may
       go to the store page."""
    if not user_data:
        # Redirect to the user creation page
        redirect("create_account.html", username=repr(doc["username"].value))
    else:
        # Login
        username, _, _, _, _ = user_data
        redirect("store.html", username=repr(username))

def donation_done(res):
    """Anonymous donation done, refresh the page."""
    redirect("index.html")

def donate_event(event):
    """The donation button has been pressed, record this anonymous donation."""
    amount = doc['donation'].value
    if not amount:
        notify("Invalid donation amount")
        return
    try:
        amount = float(amount)
    except ValueError:
        notify("Invalid donation amount")
        return
    if amount <= 0:
        notify("Amount must be nonzero")
        return
    async_request(donation_done, action="donate", amount=amount)

# Populate the variable "usernames".
## Todo: have a timeout to reload this.
async_request(get_usernames_done, action="usernames")

doc['username'].bind('keydown', keydown_event)
doc['login_button'].bind('click', login_event)
doc['donate_button'].bind('click', donate_event)
