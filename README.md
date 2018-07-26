quicken2beancount
=================

Python program to translate a Quicken instance into a beancount file.

Translating a complete Quicken database instance into beancount
(or any other double-entry accounting
system like [GnuCash](https://www.gnucash.org/)
or [Ledger](https://www.ledger-cli.org) is painful to say the least.

Quicken is a single-entry accounting system, which means that amounts
can appear out of or disappear into thin air.  In a double-entry accounting
system you can't put amounts in an account without taking it out of another
account.

Quicken can export its data into a .qif file.  Unfortunately there are a
number of challenges in processing a .qif file:
* Quicken uses "categories" to categorize expense and income transactions
within an account rather than detailed expense and income accounts. 
* No linkage between transactions which transfer funds from one account
to another
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

This code is provided to act as
a starting point for your migration adventure.

Good luck!
