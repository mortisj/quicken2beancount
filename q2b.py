#!/usr/bin/python3

import os
import pprint
import sys
import re
import decimal
import qifparser
import datetime
import logging
import math

cents = decimal.Decimal('0.01')

def get_beancount_name(q_name, q_acct_type=None):

    tt = {"_OpeningBalances": "Equity:Opening-Balances",
          "_Commissions": "Expenses:Investment-Commissions",
          "_IntInc": "Income:Investments:Interest",
          "_DivInc": "Income:Investments:Dividends",
          "_ShrsInOut": "Equity:Share-Transfers",
          "_Exchange": "Expenses:Currency-Exchange",
          "_Accrued Int": "Income:Investments:Accruals",
          "House": "Assets:House",
          "Bonus": "Income:Salary:Bonus",
          "Consulting Inc": "Income:Consulting",
          "Bank-Interest": "Income:Bank-Interest",
          "Int Inc": "Income:Bank-Interest",
          "Loan Payment": "Liabilities:Bank-Loans",
          "Rental Income": "Income:Condo",
          "_ST CapGnDst": "Income:Investments:Capital-Gains",
          "_IntExp": "Expenses:Bank-Loan-Interest",
          "_RlzdGains": "Income:Investments:Realized-Gains",
          }

    if q_name in tt:
        return tt[q_name]
    #:
    
    s = q_name
    s = re.sub(' ', '-', s)
    s = re.sub('[^A-Za-z0-9\-:]', '', s)
    s = re.sub('\-+', '-', s)
    
    parts = s.split(":")
    for i in range(len(parts)):
        parts[i] = parts[i][0].upper() + parts[i][1:]
    #:
    s = ":".join(parts)

    clean_name = s
    
    if "Opening Balance" in q_name:
        return f"Equity:Opening-Balance:{clean_name}"
    #:
          
    if q_acct_type in ["CCard", "Oth L", "Bill", "Tax"]:
        return f"Liabilities:{clean_name}"
    #:
        
    if q_acct_type in ["Bank", "Cash", "Oth A", "Port", "Invoice", "RRSP", "Mutual"]:
        return f"Assets:{clean_name}"
    #:

    if q_acct_type == "Income":
        return f"Income:{clean_name}"
    #:
        
    if q_acct_type == "Expenses":
        return f"Expenses:{clean_name}"
    #:
        
    raise ValueError(f"Can't translate Quicken name: {q_name} {q_acct_type}")
#:

class Account(object):

    names = {}
    q_names = {}
    
    def __init__(self, q_name=None, q_category=None, q_account=None, currency=None):

        self.q = q_account

        if q_name:
            self.name = get_beancount_name(q_name)
            self.q_name = q_name
        elif q_category:
            if category.income:
                self.name = get_beancount_name(category.qname, "Income")
            else:
                self.name = get_beancount_name(category.qname, "Expenses")
            #
            self.q_name = q_category.qname
        elif q_account:
            self.name = get_beancount_name(q_account.qname, q_account.type)
            self.q_name = f"[{q_account.qname}]" 
        else:
            raise ValueError("Name not provided")
        #:
        
        if self.q_name and self.q_name in Account.q_names:
            raise ValueError(f"Duplicate account q_name: {self.q_name}")
        #:
        
        if self.name in Account.names:
            raise ValueError(f"Duplicate account name: {self.name}")
        #:

        Account.names[self.name] = self
        if self.q_name:
            Account.q_names[self.q_name] = self
        #:

        self.currency = Security.dict["CAD"]
        if currency:
            self.currency = Security.dict[currency]
        elif self.q and self.q.description:
            m = re.search("<(.*?)>", self.q.description)
            if m:
                self.currency = Security.dict[m.group(1)]
            #:
        #:
        
        self.firstdate = None
        self.lastdate = None
        self.holdings = {}
        self.pending_transfers = []
        self.transactions = []

        print(f"1901-01-01 open {self.name}")

        logging.debug(f"New account: {self.name} --> {self.q_name} {self.currency.name}")
    #:

    def __repr__(self):
        return self.name
    #:

    def add_holding(self, security, date, quantity, cost):

        logging.debug(f"Add holding: {security} {date} {quantity} {cost}")
        
        if security == self.currency:
            return
        #:
        
        if security.name not in self.holdings:
            self.holdings[security.name] = []
        #:
    
        self.holdings[security.name].append({
            "security": security,
            "date": date,
            "quantity": quantity,
            "cost": cost})
        #:
    #:

    def remove_holding(self, security, quantity_to_be_removed):

        logging.debug(f"Remove: {quantity_to_be_removed} {security.name}")
        logging.debug(f"Holdings: {pprint.pformat(self.holdings.get(security.name, []))}")
        removals = []
        remaining = quantity_to_be_removed

        while remaining > 0 and security.name in self.holdings:
            logging.debug(f"Remaining: {remaining}")
            holding = self.holdings[security.name][0]
            removal = dict(holding)
            if holding["quantity"] <= remaining:
                self.holdings[security.name].pop(0)
                if not self.holdings[security.name]:
                    del self.holdings[security.name]
                #:
            else:
                holding["quantity"] -= remaining
                removal["quantity"] = remaining
            #:
            remaining -= removal["quantity"] 
            removals.append(removal)
        #:

        if remaining > 0:
            logging.debug(f"Shorted: {security} {remaining}")
            removals.append({
                "security": security,
                "date": None,
                "quantity": remaining,
                "cost": None})
        #:

        logging.debug(f"Removed: {removals}")
        return removals
    #:

    def close(self, as_of):

        if self.holdings:
            logging.error(f"Cannot close non-empty account: {self.name} {self.holdings}")
            return
        #:

        print(f"{as_of.strftime('%Y-%m-%d')} close {self.name}")
        logging.debug(f"Closing account: {self.name} as of {as_of.strftime('%Y-%m-%d')}")
    #:
#:        

class Security(object):

    dict = {}
    
    def __init__(self, q_name):

        self.q_name = q_name

        self.name = q_name.upper()
        self.name = re.sub(' ', '-', self.name)
        self.name = re.sub('[^A-Za-z0-9\-:]', '', self.name)
        self.name = re.sub('\-+', '-', self.name)
        self.name = self.name[:24]
        while self.name[-1] == "-":
            self.name = self.name[:-1]
        #:

        logging.debug(f"New security: {self.q_name} --> {self.name}")
        
        if self.q_name in Security.dict:
            raise ValueError(f"Duplicate security name: {self.q_name}")
        #:

        Security.dict[self.q_name] = self
        
        self.prices = []
    #:

    def __repr__(self):
        return self.name
    #:

    def add_price(self, date, price):
        self.prices.append({"date": date, "price": price})
    #:
        
    def get_price(self, date):

        logging.debug(f"Get price: {self} {date}")
        logging.debug(f"Database: {self.prices}")
        
        if not self.prices:
            logging.error(f"No prices available for {self}")
            return None
        #:

        price = None
        
        for entry in self.prices:
            if date < entry["date"]:
                break
            #:
            price = entry["price"]
        #:

        if price is None:
            logging.error(f"Post-facto price for {self} {date}")
            price = self.prices[0]["price"]
        #:

        return price
    #:
#:
    
class Transaction():

    count = 0
    
    def __init__(self, from_account, q_transaction):

        logging.debug(f"Transaction: {from_account} {q_transaction}")
        self.from_account = from_account
        self.q = q_transaction

        Transaction.count += 1
        self.id = Transaction.count

        self.action = self.q.action
        self.date = self.q.date
        self.payee = self.clean_string(self.q.payee)
        self.memo = self.clean_string(self.q.memo)
        self.type = self.q.qtype

        if self.q.category:
            self.to_account = Account.q_names[self.q.category]
        else:
            self.to_account = None
        #:

        if self.to_account == self.from_account:
            self.from_account = Account.q_names["_OpeningBalances"]
        #:

        self.amount = Amount(self.q.tAmount, self.from_account.currency)
            
        self.splits = []
        for split in self.q.splits:
            if split.amount != decimal.Decimal('0'):
                amount = Amount(split.amount, self.from_account.currency)
                to_account = Account.q_names[split.category]
                self.splits.append({"amount": amount, "to_account": to_account, "memo": split.memo})
            #:
        #:
        
        self.posted = False
        self.postings = []

        if self.q.qtype != "Invst":
            return
        #:
        
        self.trade_amount = None
        self.trade_price = None
        
        self.commission = Amount(self.q.commission, self.from_account.currency)

        if not self.q.security:
            return
        #:
        
        self.security = Security.dict[self.q.security]

        if not self.q.quantity:
            return
        #:

        self.trade_amount = Amount(self.q.quantity, self.security, prec=7)

        if self.q.price:
            self.trade_price = Amount(self.q.price, self.security, prec=7)
        else:
            self.trade_price = self.security.get_price(self.date)
            if self.trade_price is None:
                self.trade_price = Amount(0, self.from_account.currency, prec=7)
            #:
            assert self.trade_price.security == self.from_account.currency
        #:

        if self.action in ["Buy", "BuyX", "ReinvDiv", "ReinvInt"]:
            commission_adjustment = self.commission
        elif self.action in ["Sell", "SellX"]:
            commission_adjustment = -self.commission
        else:
            assert not self.commission
            commission_adjustment = Amount(0)
        #:
    
        if not self.amount:
            calculated_amount = self.trade_amount.quantity * self.trade_price.quantity + commission_adjustment.quantity
            self.amount = Amount(calculated_amount, self.from_account.currency)
            logging.debug(f"calculated_amount: {calculated_amount}")
        #:
         
        # price in qif seems to be calculated with inadequate precision
        calculated_price = (self.amount.quantity - commission_adjustment.quantity) / self.trade_amount.quantity
        self.trade_price = Amount(calculated_price, self.from_account.currency, prec=7)
        self.security.add_price(date=self.date, price=self.trade_price)
        logging.debug(f"calculated_price: {calculated_price}")
        
        if self.security.name == "RBC-MANAGED-FUNDS":
            if self.action == "ShrsIn":
                self.action = "ReinvDiv"
            elif self.action == "ShrsOut":
                self.action = "ReinvDiv"
                self.trade_amount = -self.trade_amount
                self.amount = -self.amount
            #:
        #:
    #:

    def clean_string(self, s):

        if not s:
            return ""
        #:

        s = s.replace('"', "'")
        s = s.replace('\\', "")
        s = ''.join(c for c in s if ord(c)<128)
    
        return s
    #:

    def post(self):

        logging.debug(f"Post: {self.q}")
        
        if self.type == "Invst":
            self.post_investment()
        elif self.splits:
            self.post_splits()
        else:
            self.post_transaction()
        #:

        self.posted = True
    #:

    def post_leg(self, account, amount, cost=None, price=None, comment=None):

        logging.debug(f"Post Leg: {account} {amount} cost={cost} price={price} {comment}")
        
        if (not account.firstdate) or (self.date < account.firstdate):
            account.firstdate = self.date
        #:
            
        if (not account.lastdate) or (self.date > account.lastdate):
            account.lastdate = self.date
        #:

        if cost is None and price is None:
            posting = Posting(account, amount, comment=comment)
            self.postings.append(posting)
            account.add_holding(security=amount.security, quantity=amount.quantity, date=self.date, cost=cost)
            return posting
        #:
        
        if amount.quantity >= decimal.Decimal(0):
            posting = Posting(account, amount, cost=cost, price=price, comment=comment)
            self.postings.append(posting)
            account.add_holding(security=amount.security, quantity=amount.quantity, date=self.date, cost=cost)
            return
        #:
        
        realized_gain = decimal.Decimal()
        
        removals = account.remove_holding(amount.security, -amount.quantity)
        for removal in removals:
            removal_comment = comment if comment else ""
            if removal["cost"]:
                removal_comment = f"Lot dated {removal['date'].strftime('%Y-%m-%d')} {removal_comment}"
                self.postings.append(Posting(account, Amount(-removal["quantity"], amount.security, prec=7),
                                             cost=removal["cost"], comment=removal_comment))
            else:
                removal_comment = f"Lot unknown {removal_comment}"
                self.postings.append(Posting(account, Amount(-removal["quantity"], amount.security, prec=7),
                                             price=price, comment=removal_comment))
            #:
            if price is not None and removal["cost"]:
                logging.debug(f"realized_gain {removal['quantity']} {price} {removal['cost']}")
                if account.currency != removal["cost"].security:
                    raise ValueError("Mismatched currencies")
                #:
                realized_gain += removal["quantity"] * (price.quantity - removal["cost"].quantity)
            #:
        #:
        if realized_gain:
            self.postings.append(Posting(Account.q_names["_RlzdGain"], Amount(-realized_gain, account.currency)))
        #:
    #:

    def post_transfer(self, amount, to_account=None, comment=None):

        if not to_account:
            to_account = self.to_account
        #:
        
        logging.debug(f"Transfer: {self.from_account.q_name} -> {to_account.q_name}")
        if not to_account.q_name.startswith("["):
            # not a quicken account transfer so there will be no matching transaction
            self.post_leg(self.from_account, amount)
            self.post_leg(to_account, -amount, comment=comment)
            return
        #:

        logging.debug(f"Looking for match: {self.from_account.q_name} -> {to_account.q_name} {self.date} {amount}")

        match_count = 0
        last_match = None
        for i, transfer in enumerate(to_account.pending_transfers):
            if (transfer["to_account"] == self.from_account
                and transfer["date"] == self.date
                and (self.from_account.currency != to_account.currency or transfer["amount"] == -amount)):
                match_count += 1
                last_match = i
                logging.debug("Match")
            #:
        #:

        if match_count == 0:

            logging.debug(f"No match: {self.date} {self.from_account.name} -> {to_account.name} {amount}")

            from_posting = self.post_leg(self.from_account, amount=amount, comment=comment)
            to_posting = self.post_leg(to_account, amount=-amount, comment=comment)
            
            self.from_account.pending_transfers.append(
                {"date": self.date,
                 "to_account": to_account,
                 "amount": amount,
                 "from_posting": from_posting,
                 "to_posting": to_posting
                 })

            logging.debug(f"Pend transfer: {self.date} {to_account.name} {amount}")

            return
        #:
            
        if match_count > 1:
            logging.error(f"Multiple match: {self.date} {self.from_account.name} -> {to_account.name} {amount}")
        #:

        if match_count >= 1:
            logging.debug(f"Found match: {self.date} {self.from_account.name} -> {to_account.name} {amount}")

            transfer = to_account.pending_transfers.pop(last_match)
            logging.debug(f"Popped: {transfer}")

            if self.from_account.currency != to_account.currency:
                logging.debug("Currency Exchange")
                from_amount = transfer["amount"]
                rate = from_amount.quantity / -amount.quantity 

                prev_posting = transfer["to_posting"]
                prev_posting.amount = amount
                prev_posting.price = Amount(rate, self.to_account.currency, prec=7)
                prev_posting.comment = "Exchange"
            #:
        #:
    #:

    def post_investment(self):
        
        logging.debug(f"Post investment")
        logging.debug(f"{self.q}")
        logging.debug(f"self.action: {self.action}")

        if not self.amount and not self.trade_amount:
            logging.error(f"Null transaction: {self.q}")
            return
        #:

        self.payee = self.action

        comment = None
        if self.trade_amount:
            comment = self.trade_amount.security.name
        #:
        
        if self.action =="Buy":
            self.post_leg(self.from_account, self.trade_amount, cost=self.trade_price)
            self.post_leg(self.from_account, -self.amount)
        elif self.action == "BuyX":
            self.post_leg(self.from_account, self.trade_amount, cost=self.trade_price)
            self.post_leg(self.from_account, -self.amount)
            self.post_transfer(self.amount)
        elif self.action == "Sell":
            self.post_leg(self.from_account, -self.trade_amount, price=self.trade_price)
            self.post_leg(self.from_account, self.amount)
        elif self.action == "SellX":
            self.post_leg(self.from_account, -self.trade_amount, price=self.trade_price)
            self.post_leg(self.from_account, self.amount)
            self.post_transfer(-self.amount)
        elif self.action == "Div":
            self.post_leg(self.from_account, self.amount, comment=comment)
            self.post_leg(Account.q_names["_DivInc"], -self.amount)
        elif self.action == "DivX":
            self.post_leg(self.from_account, self.amount, comment=comment)
            self.post_leg(Account.q_names["_DivInc"], -self.amount)
            self.post_transfer(-self.amount)
        elif self.action == "IntInc":
            self.post_leg(self.from_account, self.amount)
            self.post_leg(Account.q_names[f"_IntInc"], -self.amount)
        elif self.action == "ReinvInt":
            self.post_leg(self.from_account, self.trade_amount, cost=self.trade_price)
            self.post_leg(Account.q_names[f"_IntInc"], -self.amount)
        elif self.action == "ReinvDiv":
            self.post_leg(self.from_account, self.trade_amount, cost=self.trade_price)
            if self.amount:
                self.post_leg(Account.q_names[f"_DivInc"], -self.amount)
            else:
                self.post_leg(Account.q_names[f"_DivInc"], -self.trade_amount)
            #:
        elif self.action == "XIn":
            self.post_transfer(self.amount)
        elif self.action == "XOut":
            self.post_transfer(-self.amount)
        elif self.action == "Cash":
            self.post_transfer(self.amount)
        elif self.action == "ShrsIn":
            self.post_leg(self.from_account, self.trade_amount, cost=self.trade_price)
            self.post_leg(Account.q_names["_ShrsInOut"], -self.amount)
        elif self.action == "ShrsOut":
            logging.debug(f"trade amount: {self.trade_amount}")
            self.post_leg(self.from_account, -self.trade_amount, price=self.trade_price)
            self.post_leg(Account.q_names["_ShrsInOut"], self.amount)
        elif self.action == "MiscIncX":
            self.post_transfer(-self.amount)
        elif self.action == "MiscExpX":
            self.post_transfer(self.amount)
        elif self.action == "MargInt":
            self.post_leg(self.from_account, -self.amount)
            self.post_leg(Account.q_names["_IntExp"], self.amount)
        elif self.action == "CGShort":
            self.post_leg(self.from_account, self.amount)
            self.post_leg(Account.q_names["_ST CapGnDst"], -self.amount)
        elif self.action == "StkSplit":
            logging.debug(f"StkSplit: {self.trade_amount}")
            logging.debug(f"{pprint.pformat(self.from_account.holdings)}")
            split_factor = self.trade_amount.quantity / decimal.Decimal(10)
            for holding in list(self.from_account.holdings.get(self.trade_amount.security.name, [])):
                if holding["cost"]:
                    new_cost = Amount(holding["cost"].quantity / split_factor, holding["cost"].security, prec=7)
                else:
                    new_cost = None
                #:
                new_trade_amount = Amount(holding["quantity"] * split_factor, holding["security"], prec=7)
                self.post_leg(self.from_account, -Amount(holding["quantity"], holding["security"], prec=7), price=holding["cost"])
                self.post_leg(self.from_account, new_trade_amount, cost=new_cost)
            #:
        elif self.action == "CGLong":
            logging.error("Ignored: %s\n" % self.action)
        elif self.action == "Reminder":
            logging.error("Ignored: %s\n" % self.action)
        else:
            logging.error("unhandled: %s\n" % self.action)
            sys.exit()
        #:

        if self.commission:
            self.post_leg(Account.q_names["_Commissions"], self.commission)
        #:
    #:
    
    def post_splits(self):
    
        logging.debug(f"Processing splits")

        for split in self.splits:
            self.post_transfer(split["amount"], to_account=split["to_account"], comment=split["memo"])
        #
    #:
    
    def post_transaction(self):

        self.post_transfer(self.amount)
    #:

    def emit(self):

        for posting in self.postings:
            if posting:
                break
            #:
        else:
            return
        #:
        
        date = self.date.strftime("%Y-%m-%d")

        comments = []
        if self.memo:
            comments.append(self.memo)
        #:
        comments.extend([posting.comment for posting in self.postings if posting.comment])
        comments = "/".join(comments)

        print("")
        print(f'{date} * "{self.payee}" "{comments}"')

        summary = list(self.postings)
        
        for i, posting in enumerate(summary):
            if i == 0:
                continue
            #:
            if posting.comment:
                continue
            #:
            for j in range(i):
                if (summary[j].account == posting.account
                    and summary[j].cost == posting.cost
                    and summary[j].price == posting.price
                    and not posting.comment):
                    summary[j].amount += posting.amount
                    posting.amount.quantity = decimal.Decimal('0')
                #:
            #:
        #:
            
        for posting in summary:

            logging.debug(f"Emit: {posting.account.name} {posting.amount} price={posting.price} cost={posting.cost} {posting.comment}")
            
            if posting.comment:
                comment = f" ; {posting.comment}"
            else:
                comment = ""
            #:

            if not posting.amount:
                continue
            #:
            
            if posting.cost is not None:
                #print(f"  {posting.account.name:40} {posting.amount} {{{posting.cost}}}{comment}")
                print(f"  {posting.account.name:40} {posting.amount} @ {posting.cost}{comment}")
            elif posting.price is not None:
                print(f"  {posting.account.name:40} {posting.amount} @ {posting.price}{comment}")
            else:
                print(f"  {posting.account.name:40} {posting.amount}{comment}")
            #:
        #:
    #:
#:

class Amount():
    def __init__(self, quantity=None, security=None, prec=2):

        if quantity:
            self.quantity = decimal.Decimal(str(quantity))
        else:
            self.quantity = decimal.Decimal()
        #:

        self.security = security
        self.prec = prec
    #:

    def __eq__(self, amount):
        if amount is None:
            return False
        #:
        return (self.quantity == amount.quantity and self.security == amount.security)
    #:

    def __neg__(self):
        return Amount(-self.quantity, self.security, prec=self.prec)
    #:

    def __add__(self, amount):
        if amount is None:
            raise ValueError("Amount is None")
        #:
        if amount.security != self.security:
            raise ValueError("Cannot add amounts with different securities")
        #:
        return Amount(self.quantity + amount.quantity, self.security, prec=max(self.prec, amount.prec))
    #:

    def __sub__(self, amount):
        return self + (-amount)
    #:

    def __repr__(self):
        return self.__str__()
    #:
    
    def __str__(self):
        # remove exponents and trailing zeros if present
        # integers remain integers, floating will have at least two decimal points

        d = self.quantity
        
        if "." not in str(d):
            d = d.quantize(decimal.Decimal("1"))
            return f"{d} {self.security.name}"
        #:

        d = d.quantize(decimal.Decimal("1." + ("0" * self.prec)))

        return f"{d} {self.security.name}"
    #:

    def __bool__(self):
        return self.quantity != decimal.Decimal("0")
    #:
#:

class Posting():
    
    def __init__(self, account=None, amount=None, price=None, cost=None, comment=None):

        logging.debug(f"Posting: {account.name} {amount} price={price} cost={cost} {comment}")
        self.account = account
        self.amount = amount
        self.price = price
        self.cost = cost
        if comment:
            self.comment = comment.replace('"', "'")
        else:
            self.comment = None
        #:
    #:
#:

if __name__ == "__main__":
    
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    logging.debug("Started...")
    
    print('option "title" "Tansay"')
    print('option "operating_currency" "CAD"')
    print('option "booking_method" "FIFO"')
    print('option "inferred_tolerance_default" "*:0.001"')
    print('option "inferred_tolerance_multiplier" "1.2"')
    print('')
    print('plugin "beancount.plugins.implicit_prices"')
    print('')
    print('1901-01-01 custom "fava-extension" "fava_dashboards"')
    print('1901-01-01 custom "fava-option" "show-accounts-with-zero-balance" "True"')
    print('1901-01-01 custom "fava-option" "collapse-pattern" ".*:.*"')
    print('')
    
    qif = qifparser.Qif(sys.argv[1])

    # create currencies

    Security("CAD")
    Security("USD")

    # create accounts for implicit categories

    Account(q_name="_OpeningBalances")
    Account(q_name="_Commissions") 
    Account(q_name="_ShrsInOut")

    # create accounts for Quicken categories
    
    for category in qif.categories.values():
        account = Account(q_category=category)
    #:

    # create accounts for user-defined Quicken accounts
    
    for q_account in qif.accounts.values():
        account = Account(q_account=q_account)
    #:

    # create securities
    
    for q_account in qif.accounts.values():
        for q_transaction in q_account.transactions:
            if q_transaction.qtype == "Invst" and q_transaction.security:
                if not Security.dict.get(q_transaction.security):
                    Security(q_transaction.security)
                #:
            #:
        #:
    #:
    
    # load Quicken transactions into accounts
    
    for q_account in qif.accounts.values():
        account = Account.q_names[f"[{q_account.qname}]"]
        for q_transaction in q_account.transactions:
            account.transactions.append(Transaction(account, q_transaction))
        #:
    #:
    
    # Pass 1 -- process investments
    # Multiple passes used so that account transfers appear preferentially with their investments

    for account in Account.names.values():
        for transaction in account.transactions:
            if transaction.type == "Invst" and not transaction.posted:
                transaction.post()
            #:
        #:
    #:

    # Pass 2 -- process splits 

    for account in Account.names.values():
        for transaction in account.transactions:
            if transaction.splits and not transaction.posted:
                transaction.post()
            #:
        #:
    #:

    # Pass 3 -- process the rest 

    for account in Account.names.values():
        for transaction in account.transactions:
            if not transaction.posted:
                transaction.post()
            #:
        #:
    #:

    # Emit transactions

    for account in Account.names.values():
        for transaction in account.transactions:
            transaction.emit()
        #:
    #:

    # List unmatched transactions
    
    for account in Account.names.values():
        if account.pending_transfers:
            logging.error(f"Unmatched transactions in {account.name}")
            for transfer in account.pending_transfers:
                logging.error(f"Unmatched: {transfer['date']} {transfer['amount']} {account.name} -> {transfer['to_account'].name}")
            #:
        #:
    #:

    # Close unused accounts

    as_of = datetime.datetime(datetime.datetime.today().year - 2, 1, 1)

    for account in Account.names.values():
        if not account.holdings and (not account.lastdate or account.lastdate < as_of):
            account.close(as_of)
        #:
    #:
#:
