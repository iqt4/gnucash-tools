import json
from enum import Enum
import argparse
import gnucashxml
# import piecash
import datetime as dt


class AccountType(Enum):
    DEPOSIT = "deposit"
    PORTFOLIO = "portfolio"
    FEE = "fee"
    TAX = "tax"
    DIVIDEND = "dividend"
    INTEREST = "interest"


def get_transactions_from_splits(splits, due_date):
    # use a set to avoid doubles
    transactions = {sp.transaction for sp in splits
                    if sp.transaction.post_date.replace(tzinfo=None) >= due_date}

    return transactions


class Configuration(object):

    def __init__(self, filename=None, due_date=None):
        self.conf_file = filename
        self.due_date = due_date
        self.gnc_file = None
        self._conf_json = None
        self._gnc_accounts = None
        self.accounts = {account_type: [] for account_type in AccountType}
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
        for g in self._gnc_accounts:
            # Todo KeyError
            account_type = AccountType(g['type'])
            account_name = g['gnc']
            account = account_map[account_name]
            self.accounts[account_type].append(account)

        tr_deposit = set()
        for account in self.accounts[AccountType.DEPOSIT]:
            transactions = get_transactions_from_splits(account.splits, self.due_date)
            tr_deposit.update(transactions)

        tr_investment = set()
        for portfolio in self.accounts[AccountType.PORTFOLIO]:
            for security in portfolio.children:
                transactions = get_transactions_from_splits(security.splits, self.due_date)
                tr_investment.update(transactions)

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

# account.BUY             = Kauf
# account.DEPOSIT         = Einlage
# account.DIVIDENDS       = Dividende
# account.FEES            = Geb\u00FChren
# account.FEES_REFUND     = Geb\u00FChrenerstattung
# account.INTEREST        = Zinsen
# account.INTEREST_CHARGE = Zinsbelastung
# account.REMOVAL         = Entnahme
# account.SELL            = Verkauf
# account.TAXES           = Steuern
# account.TAX_REFUND      = Steuerr\u00FCckerstattung
# account.TRANSFER_IN     = Umbuchung (Eingang)
# account.TRANSFER_OUT    = Umbuchung (Ausgang)
#
# event.STOCK_SPLIT = Aktiensplit
#
# portfolio.BUY               = Kauf
# portfolio.DELIVERY_INBOUND  = Einlieferung
# portfolio.DELIVERY_OUTBOUND = Auslieferung
# portfolio.SELL              = Verkauf
# portfolio.TRANSFER_IN       = Umbuchung (Eingang)
# portfolio.TRANSFER_OUT      = Umbuchung (Ausgang)

# CSVColumn_AccountName = Konto
# CSVColumn_AccountName2nd = Gegenkonto
# CSVColumn_CumulatedPerformanceInPercent = Kumulierte Performance in %
# CSVColumn_Currency = W\u00E4hrung
# CSVColumn_CurrencyGrossAmount = W\u00E4hrung Bruttobetrag
# CSVColumn_Date = Datum
# CSVColumn_DateQuote = Kursdatum
# CSVColumn_DateValue = Datum Wert
# CSVColumn_DeltaInPercent = Delta in %
# CSVColumn_ExchangeRate = Wechselkurs
# CSVColumn_Fees = Geb\u00FChren
# CSVColumn_GrossAmount = Bruttobetrag
# CSVColumn_ISIN = ISIN
# CSVColumn_InboundTransferals = Zug\u00E4nge
# CSVColumn_Note = Notiz
# CSVColumn_OutboundTransferals = Abg\u00E4nge
# CSVColumn_PortfolioName = Depot
# CSVColumn_PortfolioName2nd = Gegendepot
# CSVColumn_Quote = Kurs
# CSVColumn_SecurityName = Wertpapiername
# CSVColumn_Shares = St\u00FCck
# CSVColumn_Taxes = Steuern
# CSVColumn_TickerSymbol = Ticker-Symbol
# CSVColumn_Time = Uhrzeit
# CSVColumn_TransactionCurrency = Buchungsw\u00E4hrung
# CSVColumn_Transferals = Zu-/Abg\u00E4nge
# CSVColumn_Type = Typ
# CSVColumn_Value = Wert
# CSVColumn_WKN = WKN

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
