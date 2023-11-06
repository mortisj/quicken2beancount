#!/usr/bin/python3

import sys
import pprint
import decimal
import datetime
import pprint

class Base(object):

    def __str__(self):
        return pprint.pformat(self.__dict__)
    #:

    def __getattr__(self, attr):
        # called only when attr does not already exist
        return None
    #:
#:

class Account(Base):

    def __init__(self):
        self.qname = None
        self.transactions = []
    #:

    def __repr__(self):
        return self.qname
    #:
#:

class Split(Base):
    pass

class Security(Base):
    def __repr__(self):
        return self.qname
    #:
#:

class Category(Base):
    pass

class Transaction(Base):

    def __init__(self):
        self.splits = []
        self.address = []
        self.lines= []
    #:
    
    def addSplit(self, field, value):
        if (not self.splits) or (getattr(self.splits[-1], field) is not None):
            self.splits.append(Split())
        #:
        setattr(self.splits[-1], field, value)
    #:

    def addLine(self, field, value):
        if (not self.lines) or hasattr(self.lines[-1], field):
            self.lines.append(Split())
        #:
        setattr(self.lines[-1], field, value)
    #:
#:

class Qif(object):

    def __init__(self, filename=None):

        if filename:
            self.fh = open(filename)
        else:
            self.fh = sys.stdin
        #:
        self.fh.reconfigure(errors="ignore")

        self.lastAccount = None
        self.accounts = {}
        self.categories = {}
        self.securities = {}
        
        self.getline()

        while self.inputLine:
            self.process_section()
        #:
    #:

        
    def getline(self):
        # skip blank input lines
        while True:
            self.inputLine = self.fh.readline()
            if not self.inputLine:
                return
            #:
            self.inputLine = self.inputLine.rstrip('\r\n').strip()
            if self.inputLine:
                return
            #:
        #:
    #:

    def getchunk(self):
        chunk = []
        while self.inputLine and (self.inputLine[0] not in ["^", "!"]):
            chunk.append(self.inputLine)
            self.getline()
        #:
        if self.inputLine.startswith("^"):
            self.getline()
        #:

        return chunk
    #:

    
    def process_section(self):

        if not self.inputLine.startswith("!"):
            sys.stderr.write("No header: %s\n" % self.inputLine)
            self.getline()
            return
        #:
        
        #sys.stderr.write("Header: %s\n" % self.inputLine)
        section = self.inputLine
        self.getline()
        
        if section == "!Type:Cat":
            self.process_section_cat()
        elif section == "!Type:Tag":
            self.process_section_ignored()
        elif section == "!Account":
            self.process_section_account()
        elif section == "!Type:Prices":
            self.process_section_ignored()
        elif section == "!Type:Template":
            self.process_section_ignored()
        elif section == "!Type:Memorized":
            self.process_section_ignored()
        elif section == "!Type:Security":
            self.process_section_security()
        elif section == "!Type:InvItem":
            self.process_section_ignored()
        else:
            self.process_section_transaction(section[6:])
        #:
    #:

    def process_section_ignored(self):
        #sys.stderr.write("Ignored: %s\n" % self.inputLine)
        while self.inputLine and not self.inputLine.startswith("!"):
            self.getline()
        #:
    #:

    def process_section_cat(self):
        chunk = self.getchunk()
        while chunk:
            category = Category()
            for thing in chunk:
                if thing[0] == "B":
                    category.budget = self.parseDecimal(thing[1:])
                elif thing[0] == "D":
                    category.description = thing[1:]
                elif thing[0] == "E":
                    category.e = thing[1:] 
                elif thing[0] == "I":
                    category.income = True 
                elif thing[0] == "N":
                    category.qname = thing[1:]
                elif thing[0] == "R":
                    category.taxSchedule = thing[1:]
                elif thing[0] == "T":
                    category.taxRelated = True 
                else:
                    sys.stderr.write("Unknown value for category: %s: %s\n" % (chunk[0], thing))
                #:
            #:
            if not category.qname:
                sys.stderr.write("No name for category: %s\n" % chunk[0])
                continue
            #:
            if category.qname not in self.categories:
                self.categories[category.qname] = category
            #:

            chunk = self.getchunk()
        #:
    #:

    def process_section_security(self):
        chunk = self.getchunk()
        while chunk:
            security = Security()
            for thing in chunk:
                if thing[0] == "G":
                    security.g = thing[1:]
                elif thing[0] == "N":
                    security.qname = thing[1:]
                elif thing[0] == "S":
                    security.symbol = thing[1:]
                elif thing[0] == "T":
                    security.type = thing[1:] 
                else:
                    sys.stderr.write("Unknown value for security: %s: %s\n" % (chunk[0], thing))
                #:
            #:
            if not security.qname:
                sys.stderr.write("No name for security: %s\n" % chunk[0])
                continue
            #:
            if security.qname not in self.securities:
                self.securities[security.qname] = security
            #:

            chunk = self.getchunk()
        #:
    #:

    def process_section_account(self):
        # contains one or more accounts
        
        chunk = self.getchunk()
        while chunk:
            #sys.stderr.write("Account: %s\n" % chunk[0])
            account = Account()
            for thing in chunk:
                if thing[0] == "D":
                    account.description = thing[1:]
                elif thing[0] == "L":
                    account.l = thing[1:]
                elif thing[0] == "N":
                    account.qname = thing[1:]
                elif thing[0] == "R":
                    account.r = thing[1:]
                elif thing[0] == "T":
                    account.type = thing[1:]
                else:
                    sys.stderr.write("Unknown value for Account: %s: %s\n" % (chunk[0], thing))
                #:
            #:
            if not account.qname:
                sys.stderr.write("No name for Account: %s\n" % chunk[0])
                continue
            #:
            if account.qname not in self.accounts:
                self.accounts[account.qname] = account
            #:

            self.lastAccount = self.accounts[account.qname]
            chunk = self.getchunk()
        #:
    #:

    def process_section_transaction(self, qtype):
        # contains one or more transactions for the previous account
            
        chunk = self.getchunk()
        while chunk:
            transaction = Transaction()
            transaction.qtype = qtype
            for thing in chunk:
                if thing[0] == "A":
                    transaction.address.append(thing[1:])
                elif thing[0] == "C":
                    transaction.cleared = thing[1:]
                elif thing[0] == "D":
                    transaction.date = self.parseDate(thing[1:])
                elif thing[0] == "E":
                    transaction.addSplit("memo", thing[1:])
                elif thing[0] == "I":
                    transaction.price = self.parseDecimal(thing[1:])
                elif thing[0] == "K":
                    transaction.k = thing[1:]
                elif thing[0] == "L":
                    s = thing[1:]
                    s = s.replace("|", "")  # garbage character
                    transaction.category = s.split("/")[0]
                    if transaction.category != s:
                        transaction.tag = s.split("/",1)[1]
                    #:
                elif thing[0] == "M":
                    transaction.memo = thing[1:]
                elif thing[0] == "N":
                    transaction.action = thing[1:]
                elif thing[0] == "O":
                    transaction.commission = self.parseDecimal(thing[1:])
                elif thing[0] == "P":
                    transaction.payee = thing[1:]
                elif thing[0] == "Q":
                    transaction.quantity = self.parseDecimal(thing[1:])
                elif thing[0] == "S":
                    s = thing[1:]
                    category = s.split("/")[0]
                    transaction.addSplit("category", category)
                    if category != s:
                        tag = s.split("/",1)[1]
                        transaction.addSplit("tag", tag)
                    #:
                elif thing[0] == "T":
                    transaction.tAmount = self.parseDecimal(thing[1:])
                elif thing[0] == "U":
                    transaction.uAmount = self.parseDecimal(thing[1:])
                elif thing[0] == "Y":
                    transaction.security = thing[1:]
                elif thing[0:2] == "XI":
                    transaction.transactionType = thing[2:]
                elif thing[0:2] == "XE":
                    transaction.dueDate = thing[2:]
                elif thing[0:2] == "XF":
                    transaction.addLine("taxable", thing[2:])
                elif thing[0:2] == "XN":
                    transaction.addLine("category", thing[2:])
                elif thing[0:2] == "XP":
                    transaction.lineItemP = thing[2:]
                elif thing[0:2] == "XR":
                    transaction.taxRate = thing[2:]
                elif thing[0:2] == "XS":
                    transaction.addLine("description", thing[2:])
                elif thing[0:2] == "XT":
                    transaction.taxAmount = thing[2:]
                elif thing[0:2] == "X#":
                    transaction.addLine("quantity", self.parseDecimal(thing[2:]))
                elif thing[0:2] == "X$":
                    transaction.addLine("price", self.parseDecimal(thing[2:]))
                elif thing[0] == "$":
                    if qtype == "Invst":
                        transaction.transferAmount = self.parseDecimal(thing[1:])
                    else:
                        transaction.addSplit("amount", self.parseDecimal(thing[1:]))
                    #:
                else:
                    sys.stderr.write("Unknown value for transaction: %s: %s\n" % (self.lastAccount.qname, thing))
                #:
            #:

            if self.lastAccount:
                transaction.account = self.lastAccount
                self.lastAccount.transactions.append(transaction)
            else:
                sys.stderr.write("No last account: %s\n" % qtype)
            #:
            
            chunk = self.getchunk()
        #:
    #:


    def parseDate(self, qdate):
        """ convert from QIF time format to ISO date string

        QIF is like "7/ 9/98"  "9/ 7/99" or "10/10/99" or "10/10'01" for y2k
        or, it seems (citibankdownload 20002) like "01/22/2002"
        or, (Paypal 2011) like "3/2/2011".
        ISO is like   YYYY-MM-DD  I think @@check
        """
        if qdate[1] == "/":
            qdate = "0" + qdate   # Extend month to 2 digits
        #:
        if qdate[4] == "/":
            qdate = qdate[:3]+"0" + qdate[3:]   # Extend month to 2 digits
        #:
        for i in range(len(qdate)):
            if qdate[i] == " ":
                qdate = qdate[:i] + "0" + qdate[i+1:]
            #:
        #:
        if len(qdate) == 10:  # new form with YYYY date
            iso_date = qdate[6:10] + "-" + qdate[0:2] + "-" + qdate[3:5]
            return datetime.datetime.strptime(iso_date, '%Y-%m-%d')
        #:
        if qdate[5] == "'":
            C = "20"
        else:
            C = "19"
        #:
        iso_date = C + qdate[6:8] + "-" + qdate[0:2] + "-" + qdate[3:5]
        return datetime.datetime.strptime(iso_date, '%Y-%m-%d')
    #:                

    def parseDecimal(self, s):
        try:
            d = decimal.Decimal(s.replace(",", ""))
        except:
            sys.stderr.write("Unknown decimal value: %s\n" % s)
            d = decimal.Decimal(0)
        #:
        return d
    #:
    
#:

if __name__ == "__main__":

    qif = Qif()

    test_amount = decimal.Decimal('1562.75')

    for account in qif.accounts.values():
        print(f"{account.qname} {account.description} {account.type}")
    #:

    for category in qif.categories.values():
        print(f"{category.qname}")
    #:
    
    for account in qif.accounts.values():
        for tx in account.transactions:
            print(f"{account.qname} {tx}")
            if tx.splits:
                for split in tx.splits:
                    print(f"{split}")
                #:
            #:
        #:
    #:
#:
