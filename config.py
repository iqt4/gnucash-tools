import gnucashxml
import json
import datetime as dt


class configuration(object):

    # json style - to be read from/written to config file later
    _gnc_accounts = {
        "transaction": [
            "Aktiva:Barvermögen:Deutsche Bank:Depot maxblue"
        ],
        "money-market": [
            "Aktiva:Barvermögen:MLP:Tagesgeldkonto"
        ],
        "interest": [
            "Erträge:Zinsen:MLP Konten",
            "Erträge:Zinsen:MLP Tagesgeld"
        ],
        "commission": [
            "Aufwendungen:Bankgebühren:MLP:Wertpapierdepot",
            "Aufwendungen:Bankgebühren:MLP:Konten",
            "Aufwendungen:Bankgebühren:maxblue",
            "Aufwendungen:Bankgebühren:onvista"
        ],
        "tax": [
            "Aufwendungen:Steuern:Kapitalertragssteuer",
            "Aufwendungen:Steuern:Solidaritätszuschlag",
            "Aufwendungen:Steuern:Quellensteuer"
        ],
        "investment": "Aktiva:Investments:Wertpapierdepot",
        "dividend": "Erträge:Dividende:Wertpapierdepot"
    }

    _ini = {
        "gnc_file": "/Users/dirk/Documents/Private/Finanzen/Haushaltsbuch/Haushalt 2011.gnucash",
        "due_date": "2016-07-01"
    }

    def __init__(self, filename=None):
        self.ini_file = filename
        self.gnucash_file = None
        self.due_date = None
        self.accounts = {}
        self.book = gnucashxml.Book(None, None)
        self.stocks = None

    def read_config(self):
        self.gnucash_file = self._ini["gnc_file"]
        self.due_date = dt.datetime.strptime(self._ini['due_date'], '%Y-%m-%d')

    def open_book(self):
        self.book = gnucashxml.from_filename(self.gnucash_file)
        self._map_accounts()

        # find all stocks from commodities, except currencies and template
        self.stocks = [c for c in self.book.commodities
                       if c.space not in ['ISO4217', 'template']]

    def _map_accounts(self):
        account_map = {a.fullname: a for a in self.book.accounts}
# Todo KeyError
        for k, v in self._gnc_accounts.items():
            if isinstance(v, list):
                self.accounts[k] = [account_map[i] for i in v]
            else:
                self.accounts[k] = account_map[v]

# piecash accounts
#import piecash


# ab hier überarbeiten
# due_date = dt.datetime.strptime(ini['due_date'], '%Y-%m-%d')

# para = {'gnc_file': ini['gnc_file'],
#        'due_date': due_date,
#        'gnc_stocklist': stocks}

import sys


def load_ini():
    if len(sys.argv) > 1:
        ini = sys.argv[1]
    else:
        ini = 'pc.json'

    with open(ini, 'r') as f:
        return json.load(f)


def save_ini(para):
    def to_json(python_object):
        if isinstance(python_object, dt.datetime):
            #            return {'__class__': 'datetime',
            #                '__value__': python_object.date().isoformat()}
            return python_object.date().isoformat()
        elif isinstance(python_object, piecash.core.account.Account):
            return python_object.fullname.encode('utf-8')
        raise TypeError(repr(python_object) + ' is not JSON serializable')

    para_exp = {k: v for k, v in para.items()
                if k in ['gnc_file', 'due_date']}

    accounts = {p: para[p] for p in para
                if p in ['gnc_portfolio', 'gnc_dividend', 'gnc_account',
                         'gnc_charge', 'gnc_tax', 'gnc_dividend', 'gnc_day2day']}

    para_exp['accounts'] = accounts

    with open('pc.json', 'w') as f:
        json.dump(para_exp, f, ensure_ascii=False, indent=4, default=to_json)
