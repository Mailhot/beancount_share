"""
Plugin for Beancount to share expenses.

Credits: Based on Martin Blais <blais@furius.ca> personal snippet: https://github.com/beancount/beancount/issues/474.
"""
__author__ = "Akuukis"

import datetime
import re
from typing import NamedTuple, Set, List

from beancount.core.inventory import Inventory
from beancount.core.number import D, Decimal, ONE
from beancount.core.data import Account, Entries, Posting, Open, Transaction, new_metadata


__plugins__ = ('share',)


Config = NamedTuple(
    'Config', [
        ('tag', str),
        ('no_tag', str),
        ('open_date', datetime.date),
        ('account_reroot', str),
        ('account_share', str),
        ('fraction', Decimal),
        ('meta', dict),
        ('quantize', Decimal),
        ('start_date', datetime.date),
        ('end_date', datetime.date),
    ])


CONFIGS = [
    Config('wife',
           'noshare',
           datetime.date(2013, 1, 1),
           None,
           'Assets:US:Share:Wife',
           D('0.65'),
           {'share': True},
           D('0.01'),
           datetime.date(2013, 1, 1),
           datetime.date(2019, 1, 1)),

    Config('wife',
           'noshare',
           datetime.date(2013, 1, 1),
           None,
           'Assets:US:Share:Wife',
           D('0.80'),
           {'share': True},
           D('0.005'),
           datetime.date(2019, 1, 1),
           datetime.date(2030, 1, 1)),
]


def share(entries: Entries, unused_options_map) -> Entries:
    new_accounts = set()
    new_entries: Entries = []

    for entry in entries:
        for config in CONFIGS:
            if (isinstance(entry, Transaction) and
                (config.tag in entry.tags) and
                not (config.no_tag in entry.tags) and
                config.start_date <= entry.date < config.end_date):
                entry = share_expenses(entry, new_accounts, config)
                break
        new_entries.append(entry)

    for account in sorted(new_accounts):
        new_meta = new_metadata(entries[0].meta['filename'], 0)
        open_entry = Open(new_meta, config.open_date, account, None, None)
        new_entries.append(open_entry)

    return new_entries, []


def group_postings(postings: List[Posting], account: Account) -> List[Posting]:
    grouped_postings = []
    share_postings = []
    share_balance = Inventory()
    for posting in postings:
        if posting.account == account:
            share_postings.append(posting)
            share_balance.add_position(posting)
        else:
            grouped_postings.append(posting)
    if share_postings:
        for pos in share_balance:
            grouped_postings.append(
                Posting(account, pos.units, pos.cost, None, None, share_postings[0].meta))
    return grouped_postings


def share_expenses(entry: str, new_accounts: List[Account], config: Config) -> Transaction:
    new_postings = []
    for posting in entry.postings:
        if re.match('Expenses:', posting.account):
            number = posting.units.number
            expenses_account = (
                re.sub(r'^Expenses\b', config.account_reroot, posting.account)
                if config.account_reroot
                else posting.account)
            new_postings.append(posting._replace(
                account=expenses_account,
                units=posting.units._replace(
                    number=(number * config.fraction).quantize(config.quantize))))
            new_meta = posting.meta.copy() if posting.meta else {}
            new_meta.update(config.meta)
            new_postings.append(
                Posting(
                    config.account_share,
                    posting.units._replace(number=(
                        number * (ONE - config.fraction)
                    ).quantize(config.quantize)),
                    cost=posting.cost,
                    price=None,
                    flag=None,
                    meta=new_meta))

            if config.account_reroot and (expenses_account not in new_accounts):
                new_accounts.add(expenses_account)
        else:
            new_postings.append(posting)

    # For the share account, group the postings together.
    grouped_postings = group_postings(new_postings, config.account_share)

    return entry._replace(postings=grouped_postings)
