quicken2beancount
=================

Python program to translate a Quicken instance into a [Beancount](http://furius.ca/beancount) file.

Translating a complete Quicken database instance into Beancount
(or any other double-entry accounting
system like [GnuCash](https://www.gnucash.org/)
or [Ledger](https://www.ledger-cli.org) is painful to say the least.

Quicken is a single-entry accounting system, which means that amounts
can appear out of or disappear into thin air.  In a double-entry accounting
system you can't put amounts in an account without taking it out of another
account.

Quicken can export (almost) all of its data into a .qif file.
Unfortunately there are a
number of challenges in processing said file:
* Quicken uses "categories" to categorize expense and income transactions
within an account rather than detailed expense and income accounts. 
* No linkage between transactions which transfer funds from one account
to another is provided
* No record of currencies or exchange rates
* A .qif file may contain corrupted data due to bugs in the export process
* Accounts/categories are not identified as Asset/Liability/Expense/Income
* Stock splits have incomplete information
* The .qif file format is awkward and has evolved over time

This project includes:
* a module for parsing .qif files (qifparser.py)
* a program for converting a .qif file into a beancount file (q2b.py)

This is not a turn-key solution.  q2b.py will undoubtedly need to be configured
to translate account and category names for your circumstances.

q2b.py expect the .qif file to contain all accounts from the Quicken database,
unlike other utilities I've seen which process only a single account at a time.
You can select "all accounts" and all categories of information when exporting
the data from Quicken.

This code is provided to act as
a starting point for your migration adventure.  It works for my personal
and business accounts, but curiously nobody else wants to give me a copy of
their Quicken databases for testing purposes.  Your mileage may vary.

q2b.py could also be "easily" adjusted to emit Ledger, GnuCash, or hLedger
files instead of Beancount files.  Once you've made the move from single-entry
to double-entry accounting the world will be your oyster.

Good luck!
