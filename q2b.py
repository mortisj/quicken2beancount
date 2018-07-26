#!/usr/bin/python

import os
import pprint
import sys
import re
import decimal
import qifparser
import csv
import forex_python.converter
import datetime
import pickle

class BcAccount(object):
    def __init__(self, qname=None, currency=None, accttype=None):
        self.qname = qname

        if currency:
            self.currency = currency
        else:
            self.currency = "CAD"
        #:
        self.accttype = accttype
        self.firstdate = None
        self.lastdate = None
        self.processed = False
        self.holdings = {}

        self.update_holdings("CAD", 0)
        self.update_holdings("USD", 0)
                     

        if qname == "_openingbalances" or "Opening Balance" in qname:
            self.bcname = "Equity:3500-Opening-Balance:%s" % self.cleanAccountName(qname)
            
        elif qname =="_IntInc_CAD":
            self.bcname = "Income:8092-Interest-Canadian"
        elif qname =="_IntInc_USD":
            self.bcname = "Income:8091-Interest-Foreign"
        elif qname =="_DivInc_CAD":
            self.bcname = "Income:8096-Dividends-Canadian"
        elif qname =="_DivInc_USD":
            self.bcname = "Income:8097-Dividends-Foreign"
        elif qname =="_RlzdGains":
            self.bcname = "Income:8211-Capital-Gains"
        elif qname =="_ST CapGnDst":
            self.bcname = "Income:8211-Capital-Gains-Short"
        elif qname =="_commissions":
            self.bcname = "Expenses:8869-Brokerage-Commissions"
        elif qname =="_IntExp":
            self.bcname = "Expenses:8869-Brokerage-Fees-Misc"
        elif qname =="_ShrsInOut":
            self.bcname   = "Equity:3500-Share-Transfers"

        elif qname.startswith("8231") or qname == "_Exchange":
            self.bcname = "Income:8231-Foreign-Exchange"

        elif qname == "3700 Dividends Declared":
            self.bcname = "Equity:3700-Dividends-Declared"

        elif qname.startswith("[3500"):
            self.bcname = "Equity:%s" % self.cleanAccountName(qname)
            
        elif qname.startswith("[2962") or qname.startswith("[2680"):
            self.bcname = "Liabilities:%s" % self.cleanAccountName(qname)
            
        elif accttype in ["CCard", "Oth L", "Bill", "Tax"]:
            self.bcname = "Liabilities:%s" % self.cleanAccountName(qname)

        elif accttype in ["Bank", "Cash", "Oth A", "Port", "Invoice", "RRSP", "Mutual"]:
            self.bcname = "Assets:%s" % self.cleanAccountName(qname)

        elif accttype == "Income":
            self.bcname = "Income:%s" % self.cleanAccountName(qname)
        elif accttype == "Expenses":
            self.bcname = "Expenses:%s" % self.cleanAccountName(qname)

        else:
            sys.stderr.write("Can't translate Quicken name: %s (%s)\n" % (qname, accttype))
        #:

        #sys.stderr.write("%s -> %s\n" % (qname, self.bcname))

        sys.stdout.write("1901-01-01 open %s\n" % (self.bcname))
    #:
    
    def cleanAccountName(self, s):
    
        s = re.sub(' ', '-', s)
        s = re.sub('[^A-Za-z0-9\-:]', '', s)
        s = re.sub('\-+', '-', s)

        parts = s.split(":")
        for i in range(len(parts)):
            parts[i] = parts[i][0].upper() + parts[i][1:]
        #:
        s = ":".join(parts)
    
        return s
    #:
    
    def update_holdings(self, qSecurityName, quantity):

        if qSecurityName not in self.holdings:
            self.holdings[qSecurityName] = 0
        #:
    
        self.holdings[qSecurityName] += quantity
    #:
#:

class BcSecurity(object):

    def __init__(self, qSecurityName=None, currency=None):
        self.qSecurityName = qSecurityName
        self.quantity = 0
        self.prices = []
        self.currency = currency
        self.bcSecurityName = self.cleanSecurityName(self.qSecurityName)
    #:

    def update_price(self, date, price):
        if not price:
            price = 0
        #:
        self.prices.append({"date":date, "price":price})
        self.prices.sort(key=lambda item:item["date"])
    #:

    def get_price(self, date):

        for price in self.prices:
            if date >= price["date"]:
                return price["price"]
            #:
        #:

        if self.prices:
            sys.stderr.write("Post-facto price for: %s %s\n" % (self.qSecurityName, str(date)))
            return self.prices[0]["price"]
        #:

        sys.stderr.write("No price for: %s %s\n" % (self.qSecurityName, str(date)))
        return 1.00
    #:
    
    def cleanSecurityName(self,s):
    
        s = re.sub(' ', '-', s)
        s = re.sub('[^A-Za-z0-9\-:]', '', s)
        s = re.sub('\-+', '-', s)
        s = s.upper()
        s = s[:24]
        while s[-1] == "-":
            s = s[:-1]
        #:
    
        return s
    #:
#:
    
def cleanString(s):

    if not s:
        return ""
    #:
    s = s.replace('"', "'")
    s = s.replace('\\', "")
    s = ''.join(c for c in s if ord(c)<128)
    
    return s

def recordExchange(date, fromAccount, toAccount, amount):

    fromCurrency = accounts[fromAccount].currency
    toCurrency = accounts[toAccount].currency

    if fromCurrency == toCurrency:
        return
    #:

    exchanges.append({
        "date": date,
        "toAccount": toAccount,
        "toCurrency": toCurrency,
        "fromAccount": fromAccount,
        "fromCurrency": fromCurrency,
        "amount": amount})
#:
    
def isProcessed(qname):
    return accounts[qname].processed
#:

def getExchangeRate(date, fromCurrency, toCurrency):

    key = "%s-%s-%s" % (date, fromCurrency, toCurrency)
    if key in forexRates:
        return forexRates[key]
    #:

    oDate = datetime.datetime.strptime(date, "%Y-%m-%d")

    try:
        sys.stderr.write("Querying for: %s\n" % key)
        rate = currencyConverter.convert(fromCurrency, toCurrency, 1.0, oDate)
    except:
        sys.stderr.write("Can't get rate: %s\n" % key)
        return 1.0
    #:

    forexRates[key] = rate
    return rate
#:

def write_posting(date, qname, quantity=None, currency="CAD", qSecurityName=None, price=None, cost=None, comment=None):

    if qSecurityName:
        bcSecurityName = securities[qSecurityName].bcSecurityName
        sys.stdout.write("  %-40s %12.4f %s" % (accounts[qname].bcname, quantity, bcSecurityName))
        if cost is not None:
            if cost:
                sys.stdout.write(" {%.6f %s}" % (cost, currency))
            else:
                sys.stdout.write(" {}")
        #:
        if price is not None:
            sys.stdout.write(" @ %.6f %s" % (price, currency))
        #:
    else:
        if quantity is not None:
            sys.stdout.write("  %-40s %12.2f %s" % (accounts[qname].bcname, quantity, currency))
        else:
            sys.stdout.write("  %-40s" % (accounts[qname].bcname))
        #:
    #:

    if comment:
        sys.stdout.write("; %s" % comment)
    #:

    sys.stdout.write("\n")
        
    if (not accounts[qname].firstdate) or (date < accounts[qname].firstdate):
        accounts[qname].firstdate = date
    #:
    if (not accounts[qname].firstdate) or (date > accounts[qname].lastdate):
        accounts[qname].lastdate = date
    #:
#:

def process_investment(account, transaction):

    date = transaction.date.strftime("%Y-%m-%d")
                
    fromAccount = account.qname
    bcAccount = accounts[fromAccount]
    
    memo = cleanString(transaction.memo)
    amount = transaction.tAmount if transaction.tAmount else 0
    quantity = transaction.quantity if transaction.quantity else 0
    price = transaction.price if transaction.price else 0
    commission = transaction.commission if transaction.commission else 0
    currency = accounts[account.qname].currency
    qSecurityName = transaction.security
    
    if transaction.category:
        toAccount = transaction.category
    else:
        toAccount = ""
    #:

    # price in qif seems to be calculated with inadequate precision
    if quantity and amount:
        if transaction.action in ["Buy", "BuyX", "ReinvInt", "ReinvDiv"]:
            price = (amount - commission) / quantity
        elif transaction.action in ["Sell", "SellX"]:
            price = (amount + commission) / quantity
        #:
    #:

    sys.stdout.write("%s * \"%s\" \"%s\"\n" % (date, transaction.action, memo))

    if transaction.action == "Buy":
        bcAccount.update_holdings(qSecurityName, quantity)
        write_posting(date,fromAccount, quantity, currency, qSecurityName=qSecurityName, cost=price)
        write_posting(date,fromAccount, -amount, currency)
    elif transaction.action == "BuyX":
        bcAccount.update_holdings(qSecurityName, quantity)
        write_posting(date,fromAccount, quantity, currency, qSecurityName=qSecurityName, cost=price)
        write_posting(date,fromAccount, -amount, currency)
        recordExchange(date, fromAccount, toAccount, amount)
        if not isProcessed(toAccount):
            write_posting(date,fromAccount, amount, currency)
            write_posting(date,toAccount, -amount, currency)
        #:
    elif transaction.action == "Sell":
        bcAccount.update_holdings(qSecurityName, -quantity)
        write_posting(date,fromAccount, -quantity, currency, qSecurityName=qSecurityName, cost="", price=price)
        write_posting(date,fromAccount, amount, currency)
        write_posting(date,"_RlzdGains")
    elif transaction.action == "SellX":
        bcAccount.update_holdings(qSecurityName, -quantity)
        write_posting(date,fromAccount, -quantity, currency, qSecurityName=qSecurityName, cost="", price=price)
        write_posting(date,fromAccount, amount, currency)
        write_posting(date,"_RlzdGains")
        recordExchange(date, fromAccount, toAccount, -amount)
        if not isProcessed(toAccount):
            write_posting(date,fromAccount, -amount, currency)
            write_posting(date,toAccount, amount, currency)
        #:
    elif transaction.action == "Div":
        write_posting(date, fromAccount, amount, currency, comment=qSecurityName)
        write_posting(date,"_DivInc_%s" % currency, -amount, currency)
    elif transaction.action == "DivX":
        write_posting(date,fromAccount, amount, currency)
        write_posting(date,"_DivInc_%s" % currency, -amount, currency)
        recordExchange(date, fromAccount, toAccount, -amount)
        if not isProcessed(toAccount):
            write_posting(date,fromAccount, -amount, currency)
            write_posting(date,toAccount, amount, currency)
        #:
    elif transaction.action == "IntInc":
        write_posting(date,fromAccount, amount, currency, comment=qSecurityName)
        write_posting(date,"_IntInc_%s" % currency, -amount, currency)
    elif transaction.action == "ReinvInt":
        bcAccount.update_holdings(qSecurityName, -quantity)
        write_posting(date,fromAccount, quantity, currency, qSecurityName=qSecurityName, cost=price)
        write_posting(date,"_IntInc_%s" % currency, -amount, currency)
    elif transaction.action == "ReinvDiv":
        bcAccount.update_holdings(qSecurityName, quantity)
        write_posting(date,fromAccount, quantity, currency, qSecurityName=qSecurityName, cost=price)
        write_posting(date,"_DivInc_%s" % currency, -amount, currency)
    elif transaction.action == "XIn":
        recordExchange(date, fromAccount, toAccount, amount)
        if not isProcessed(toAccount):
            write_posting(date,fromAccount, amount, currency)
            write_posting(date,toAccount, -amount, currency)
        #:
    elif transaction.action == "XOut":
        recordExchange(date, fromAccount, toAccount, -amount)
        if not isProcessed(toAccount):
            write_posting(date,fromAccount, -amount, currency)
            write_posting(date,toAccount, amount, currency)
        #:
    elif transaction.action == "Cash":
        recordExchange(date, fromAccount, toAccount, amount)
        if not isProcessed(toAccount):
            write_posting(date,fromAccount, amount, currency)
            write_posting(date,toAccount, -amount, currency)
        #:
    elif transaction.action == "ShrsIn":
        if not price:
            price = securities[qSecurityName].get_price(transaction.date)
        #:
        if not price:
            sys.stderr.write("No price: %s\n" % str(transaction))
        #:
        if quantity != 0:
            bcAccount.update_holdings(qSecurityName, quantity)
            write_posting(date, fromAccount, quantity, currency, qSecurityName, cost=price)
            write_posting(date, "_ShrsInOut", None, currency, comment=qSecurityName)
        #:
    elif transaction.action == "ShrsOut":
        if price == 0:
            price = securities[qSecurityName].get_price(transaction.date)
        #:
        if quantity != 0:
            bcAccount.update_holdings(qSecurityName, -quantity)
            write_posting(date, fromAccount, -quantity, currency, qSecurityName, cost="", price=price)
            write_posting(date, "_ShrsInOut", quantity*decimal.Decimal(price), currency, comment=qSecurityName)
            write_posting(date,"_RlzdGains")
        #:
    elif transaction.action == "MiscIncX":
        # sys.stderr.write("MiscIncX: %s\n" % str(transaction))
        write_posting(date,fromAccount, amount, currency, comment=qSecurityName)
        write_posting(date,"_IntExp", -amount, currency)
        if toAccount:
            recordExchange(date, fromAccount, toAccount, -amount)
            if not isProcessed(toAccount):
                write_posting(date,fromAccount, -amount, currency)
                write_posting(date,toAccount, amount, currency)
            #:
        #
    elif transaction.action == "MiscExpX":
        sys.stderr.write("MiscExpX: %s %s\n" % (str(fromAccount), str(transaction)))
        write_posting(date,"_IntExp", amount, currency)
        write_posting(date,fromAccount, -amount, currency, comment=qSecurityName)
        if toAccount:
            recordExchange(date, fromAccount, toAccount, amount)
            if not isProcessed(toAccount):
                write_posting(date,fromAccount, amount, currency)
                write_posting(date,toAccount, -amount, currency)
            #:
        #
    elif transaction.action == "MargInt":
        write_posting(date,fromAccount, -amount, currency)
        write_posting(date,"_IntExp", amount, currency)
    elif transaction.action == "CGShort":
        write_posting(date,fromAccount, amount, currency)
        write_posting(date,"_ST CapGnDst", -amount, currency)
    elif transaction.action == "StkSplit":
        # probably should sell/rebuy each lot at cost
        splitFactor = quantity
        sys.stderr.write("StkSplit: %s Quantity: %s\n" % (transaction.security, transaction.quantity))

        oldQuantity = bcAccount.holdings[qSecurityName]
        newQuantity = oldQuantity * quantity / decimal.Decimal(10)
        oldPrice = securities[qSecurityName].get_price(transaction.date)
        newPrice = oldPrice / (splitFactor / decimal.Decimal(10))

        # sell
        bcAccount.update_holdings(qSecurityName, -oldQuantity)
        write_posting(date, fromAccount, -oldQuantity, currency, qSecurityName=qSecurityName, cost="", price=oldPrice)
        write_posting(date, fromAccount, oldQuantity*oldPrice, currency)
        write_posting(date, "_RlzdGains")

        # buy
        bcAccount.update_holdings(qSecurityName, newQuantity)
        write_posting(date, fromAccount, newQuantity, currency, qSecurityName=qSecurityName, cost=newPrice)
        write_posting(date, fromAccount, -newQuantity*newPrice, currency)

        securities[qSecurityName].update_price(transaction.date+datetime.timedelta(seconds=1), newPrice)
    elif transaction.action == "CGLong":
        sys.stderr.write("Ignored: %s\n" % transaction.action)
    elif transaction.action == "Reminder":
        sys.stderr.write("Ignored: %s\n" % transaction.action)
    else:
        sys.stderr.write("unhandled: %s\n" % transaction.action)
        sys.exit()
    #:

    if commission:
        write_posting(date,"_commissions", commission, currency)
    #:
    
    sys.stdout.write("\n")

#:
    
def process_transaction(account, transaction):

    date = transaction.date.strftime("%Y-%m-%d")

    fromAccount = account.qname

    payee = cleanString(transaction.payee)
    memo = cleanString(transaction.memo)
    currency = accounts[account.qname].currency
                
    if transaction.splits:

        headerWritten = False
        total = 0

        for split in transaction.splits:

            if split.amount == 0:
                continue
            #:

            if not split.category:
                sys.stderr.write("Blank category: %s %s\n" % (str(account.qname), str(transaction)))
                continue
            #:

            if not headerWritten:
                sys.stdout.write("%s * \"%s\" \"%s\"\n" % (date, payee, memo))
                headerWritten = True
            #:

            toAccount = split.category

            if isProcessed(toAccount):
                continue
            #:

            recordExchange(date, fromAccount, toAccount, -split.amount)
            write_posting(date,toAccount, -split.amount, currency, comment=cleanString(split.memo))

            total += split.amount
        #
        if total != 0:
            write_posting(date,fromAccount, total, currency)
            sys.stdout.write("\n")
        #:

    else:

        amount = transaction.tAmount

        if amount == 0:
            return
        #:

        toAccount = transaction.category

        if toAccount == fromAccount:
            fromAccount = "_openingbalances" 
        #:
        
        recordExchange(date, fromAccount, toAccount, amount)
        if not isProcessed(toAccount):
            sys.stdout.write("%s * \"%s\" \"%s\"\n" % (date, payee, memo))
            write_posting(date,fromAccount, amount, currency)
            write_posting(date,toAccount, -amount, currency)
            sys.stdout.write("\n")
        #:
    #:
#:

sys.stdout.write("option \"title\" \"Tansay\"\n")
sys.stdout.write("option \"operating_currency\" \"CAD\"\n")
sys.stdout.write("option \"booking_method\" \"FIFO\"\n")
sys.stdout.write("\n")

qif = qifparser.Qif(sys.argv[1])

currencyConverter = forex_python.converter.CurrencyRates()

accounts = {}
securities = {}
exchanges = []

try:
    with open('forexrates.pickle', 'rb') as handle:
        forexRates = pickle.load(handle)
    #:
except:
    sys.stderr.write("Failed to load forexrates.pickle\n")
    forexRates = {}
#:

for category in qif.categories.values():
    if category.income:
        accounts[category.qname] = BcAccount(qname=category.qname, accttype="Income")
    else:
        accounts[category.qname] = BcAccount(qname=category.qname, accttype="Expenses")
    #:
#:

for account in qif.accounts.values():
    if not account.qname.startswith("["):
        account.qname = "[%s]" % account.qname
    #:

    currency = None
    if account.description:
        m = re.search("<(.*?)>", account.description)
        if m and m.groups():
            currency = m.groups()[0]
        #:
    #:
    
    accounts[account.qname] = BcAccount(qname=account.qname, currency=currency, accttype=account.type)
#:

# Open accounts not present in Quicken

for qname in ["_openingbalances",
              "_commissions",
              "_RlzdGains",
              "_IntInc_CAD",
              "_IntInc_USD",
              "_DivInc_CAD",
              "_DivInc_USD",
              "_Exchange",
              "_ShrsInOut"]:
    accounts[qname] = BcAccount(qname=qname)
#:

# Pass 0 -- collect investment prices

securities["CAD"] = BcSecurity("CAD", "CAD")
securities["USD"] = BcSecurity("USD", "USD")

for account in qif.accounts.values():

    for transaction in account.transactions:
        if transaction.qtype == "Invst" and transaction.security:

            if transaction.security in securities:
                security = securities[transaction.security]
            else:
                security = BcSecurity(transaction.security)
                securities[transaction.security] = security
            #:

            if transaction.price:
                security.update_price(transaction.date, transaction.price)
            #:
        #:
    #:
#:

# Pass 1 -- process investments
# Two passes used so that account transfers appear preferentially with their investments

for account in qif.accounts.values():

    for transaction in account.transactions:
        if transaction.qtype == "Invst":
            process_investment(account, transaction)
            accounts[account.qname].processed = True
        #:
    #:
#:

# Pass 2 -- process non-investments 

for account in qif.accounts.values():

    for transaction in account.transactions:
        if transaction.qtype != "Invst":
            process_transaction(account, transaction)
            accounts[account.qname].processed = True
        #:
    #:
#:

# Find matching account transfers and generate currency exchange transactions so that
# accounts only hold a single currency.  Qif files don't contain exchange rates so
# calculate one based on the two matching transactions.

unmatchedExchanges = []

while exchanges:
    item = exchanges.pop(0)
    for listitem in exchanges:
        if item["fromAccount"] == listitem["toAccount"] \
           and item["toAccount"] == listitem["fromAccount"] \
           and item["date"] == listitem["date"]:
            rate = listitem["amount"] / -item["amount"] 
            sys.stdout.write("%s * \"Currency exchange\" \"\"\n" % (item["date"]))
            write_posting(item["date"], item["toAccount"], item["amount"], item["toCurrency"], item["fromCurrency"], rate)
            write_posting(item["date"], item["toAccount"], listitem["amount"], item["toCurrency"])
            write_posting(item["date"], "_Exchange")
            sys.stdout.write("\n")
            exchanges.remove(listitem)
            break
        #:
    else:
        unmatchedExchanges.append(item)
    #:
#:

# Generate exchange transactions for expenses.  The .qif file does not contain exchange rates
# so look them up.
#
#while unmatchedExchanges:
#    item = unmatchedExchanges.pop(0)
#    rate = getExchangeRate(item["date"], item["fromCurrency"], item["toCurrency"])
#    sys.stdout.write("%s * \"Currency exchange\" \"\"\n" % (item["date"]))
#    write_posting(item["date"], item["toAccount"], item["amount"], item["toCurrency"], item["fromCurrency"], rate)
#    write_posting(item["date"], item["toAccount"], -item["amount"] * decimal.Decimal(rate), item["toCurrency"])
#    sys.stdout.write("\n")
#:

# Save exchange rates for next time

with open('forexrates.pickle', 'wb') as handle:
    pickle.dump(forexRates, handle, protocol=pickle.HIGHEST_PROTOCOL)
#:

