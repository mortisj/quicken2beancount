quicken2beancount
=================

Python program to translate a Quicken instance into a beancount file.

Translating a Quicken file into beancount (or any other double-entry accounting
system) is troublesome for a variety of reasons:

Quicken is a single-entry accounting system, which means that amounts
can appear out of or disappear into thin air.  In a double-entry accounting
system you can't put amounts in an account without taking it out of another
account.

Quicken can export its data into a .qif file.  Unfortunately there are a
number of challenges in processing a .qif file:
* No linkage between transactions which transfer funds from one account
to another
* No record of currency exchange rates
* Awkward file format
* Due to bugs in the export process corrupted data may appear in file
* Accounts not categorized as Asset/Liability/Expense/Income
* Quicken uses "categories" rather than accounts to record expense and income
transactions
* The .qif file format has evolved over time

This project includes:
* a module for parsing .qif files (qifparser.py)
* a program for converting a .qif file into a beancount file (q2b.py)

This is not a turn-key solution.  q2b.py will undoubtedly need to be configured
to translate account and category names.  This code is provided to act as
a starting point for your migration adventure.

Good luck!
