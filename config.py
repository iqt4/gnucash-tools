import json
import argparse
import gnucashxml
# import piecash
import datetime as dt


class Configuration(object):

    def __init__(self, filename=None, due_date=None):
        self.conf_file = filename
        self._conf_json = None
        self.gnc_file = None
        self.due_date = due_date
        self._gnc_accounts = None
        self.accounts = {}
        self.stocks = None

        self.read_config()

    def read_config(self):
        with open(self.conf_file, 'r') as f:
            self._conf_json = json.load(f)

        self.gnc_file = self._conf_json['gnc_file']
        self.due_date = dt.datetime.strptime(self._conf_json['due_date'], '%Y-%m-%d')
        self._gnc_accounts = self._conf_json['accounts']
        # Todo sql versus xml
        # with piecash.open_book(config.ini['gnc_file'], open_if_lock=True) as book:
        self.read_book_xml()

    def read_book_xml(self):
        book = gnucashxml.from_filename(self.gnc_file)
        account_map = {a.fullname: a for a in book.accounts}
        # Todo KeyError
        for k, v in self._gnc_accounts.items():
            if isinstance(v, list):
                self.accounts[k] = [account_map[i] for i in v]
            else:
                self.accounts[k] = account_map[v]

        # find all stocks from commodities, except currencies and template
        self.stocks = [c for c in book.commodities
                       if c.space not in ['ISO4217', 'template']]


def get_configuration():
    # Todo argument parser for DueDate and GncFilename
    ini_file = 'gc-tools.conf'
    conf = Configuration(filename=ini_file)
    return conf


# ab hier überarbeiten
# due_date = dt.datetime.strptime(ini['due_date'], '%Y-%m-%d')

# para = {'gnc_file': ini['gnc_file'],
#        'due_date': due_date,
#        'gnc_stocklist': stocks}

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
