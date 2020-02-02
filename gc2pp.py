#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  gc_xml_pp.py
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

import datetime as dt
import csv
import re
import difflib
from gnucashxml import CallableList
import config


def get_date(due_date):
    while True:
        info = 'Datum [{0}]: '.format(due_date.strftime('%d.%m.%Y'))
        user_input = input(info)
        try:
            if user_input == '':
                d = due_date
            else:
                d = dt.datetime.strptime(user_input, '%d.%m.%Y')
            return d
        except ValueError:
            print('Falsches Datum')


def get_transactions(splits, due_date):
    # use set to avoid doubles
    transactions = {sp.transaction for sp in splits
                    if sp.transaction.post_date.replace(tzinfo=None) >= due_date}

    return sorted(transactions, key=lambda tr: tr.post_date)


def export_stocklist(accounts):
    header = ['ISIN', 'WKN', 'Ticker-Symbol', 'Wertpapiername', 'Währung', 'Notiz']
    securities = [s.commodity for s in accounts['investment'].children]
    with open('stock.csv', 'wb') as f:
        f_csv = csv.DictWriter(f, header, delimiter=';', quoting=csv.QUOTE_NONE)
        f_csv.writeheader()

        for stock in securities:
            row = {'ISIN': stock.cusip,
                   'Ticker-Symbol': stock.mnemonic,
                   'Wertpapiername': stock.fullname,
                   'Währung': 'EUR',
                   'Notiz': stock.namespace}

            f_csv.writerow(row)


def export_investment(accounts, due_date):
    header = ['Datum', 'Typ', 'Wert', 'Buchungswährung',
              'Bruttobetrag', 'Währung Bruttobetrag', 'Wechselkurs',
              'Gebühren', 'Steuern', 'Stück',
              'ISIN', 'WKN', 'Ticker-Symbol', 'Wertpapiername',
              'Notiz']

    acc = ['commission', 'tax', 'transaction']

    with open('investment.csv', 'w') as f:
        f_csv = csv.DictWriter(f, header, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        f_csv.writeheader()

        for stock_account in accounts['investment'].children:
            transactions = get_transactions(stock_account.splits, due_date)
            if not transactions:
                continue

            for tr in transactions:
                val = dict.fromkeys(acc, 0)
                stock_quantity = 0
                stock_value = 0

                for sp in tr.splits:
                    if sp.account == stock_account:
                        stock_quantity += sp.quantity
                        stock_value += sp.value
                    else:
                        for a in acc:
                            if sp.account in accounts[a]:
                                val[a] += sp.value

                if stock_quantity == 0:
                    continue

                if val['transaction'] != 0 or stock_value == 0:  # Abrechnungskonto oder Incentiv
                    if stock_quantity < 0:
                        deal = 'Verkauf'
                    else:
                        deal = 'Kauf'
                    total = abs(val['transaction'])
                else:
                    if stock_quantity < 0:
                        deal = 'Auslieferung'
                    else:
                        deal = 'Einlieferung'
                    total = stock_value

                stock = stock_account.commodity

                row = {'Datum': tr.post_date.strftime('%Y-%m-%d'),
                       'Typ': deal,
                       'Wert': str(total),
                       'Buchungswährung': 'EUR',
                       'Gebühren': str(val['commission']),
                       'Steuern': str(val['tax']),
                       'Stück': str(abs(stock_quantity)),
                       'ISIN': stock.cusip,
                       'Ticker-Symbol': stock.mnemonic,
                       'Wertpapiername': stock.fullname,
                       'Notiz': tr.description}

                f_csv.writerow(row)


def write_transfer(f_csv, transaction, accounts):
    value = 0
    for sp in transaction.splits:
        if sp.account in accounts['money-market']:
            value += sp.value

    if value != 0:
        row = {'Datum': transaction.post_date.strftime('%Y-%m-%d'),
               'Buchungswährung': 'EUR',
               'Notiz': transaction.description}

        if value > 0:
            row['Typ'] = 'Umbuchung (Ausgang)'
        else:
            row['Typ'] = 'Umbuchung (Eingang)'
        row['Wert'] = str(-value)
        f_csv.writerow(row)


def write_split(f_csv, transaction, accounts):
    acc = ['commission', 'tax', 'interest', 'transaction', 'money-market']
    val = dict.fromkeys(acc, 0)

    for sp in transaction.splits:
        for a in acc:
            if sp.account in accounts[a]:
                val[a] += sp.value

    delta = sum(val.values())

    row = {'Datum': transaction.post_date.strftime('%Y-%m-%d'),
           'Buchungswährung': 'EUR',
           'Notiz': transaction.description}

    if val['commission'] != 0:
        if val['commission'] > 0:
            row['Typ'] = 'Gebühren'
        else:
            row['Typ'] = 'Gebührenerstattung'  # to be checked
        row['Wert'] = str(abs(val['commission']))
        f_csv.writerow(row)

    if val['tax'] != 0:
        if val['tax'] > 0:
            row['Typ'] = 'Steuern'
        else:
            row['Typ'] = 'Steuerrückerstattung'
        row['Wert'] = str(abs(val['tax']))
        f_csv.writerow(row)

    if val['interest'] < 0:
        row['Typ'] = 'Zinsen'
        row['Wert'] = str(-val['interest'])
        f_csv.writerow(row)

    if delta != 0:
        if delta > 0:
            row['Typ'] = 'Einlage'
        else:
            row['Typ'] = 'Entnahme'
        row['Wert'] = str(abs(delta))
        f_csv.writerow(row)


def write_dividend(f_csv, transaction, accounts):
    junk = ['INHABER', 'NAMENS', 'VORZUGS', 'STAMM', 'AKTIEN',
            'SHARES', 'REGISTERED']

    stock = None
    quantity = 0

    # find stock by ISIN (MLP)
    r = re.search(r'WKN [A-Z0-9]{6} / '
                  r'(?P<ISIN>[A-Z]{2}[A-Z0-9]{9}[0-9])'
                  r'.*?MENGE '
                  r'(?P<quantity>[0-9]*)', transaction.description)

    securities = [s.commodity for s in accounts['investment'].children]
    securities = CallableList(securities)
    if r:
        stock = securities(cusip=r.group('ISIN'))
        quantity = r.group('quantity')
    else:
        # find stock by name (maxblue)
        r = re.search(r'STK/NOM: '
                      r'(?P<quantity>[0-9]*) '
                      r'(?P<name>.*)', transaction.description)
        if r:
            quantity, name = r.groups()
            for j in junk:
                name = name.replace(j, '')

            security_names = [s.name for s in securities]

            result = difflib.get_close_matches(name, security_names, n=1)
            if result:
                stock = securities(name=result[0])

    if stock:
        tax = 0
        dividend = 0
        for sp in transaction.splits:
            if sp.account == accounts['dividend']:
                dividend = abs(sp.value)

            elif sp.account in accounts['tax']:
                tax += sp.value

        row = {
            'Datum': transaction.post_date.strftime('%Y-%m-%d'),
            'Typ': 'Dividende',
            'Wert': str(dividend - tax),
            'Buchungswährung': 'EUR',
            'Stück': quantity,
            'ISIN': stock.cusip,
            'Ticker-Symbol': stock.mnemonic,
            'Wertpapiername': stock.fullname,
            'Notiz': transaction.description
        }
        if tax:
            row['Steuern'] = str(tax)

        f_csv.writerow(row)


def export_money(accounts, due_date):
    tr_money = []
    for a in accounts['money-market']:
        tr_money += get_transactions(a.splits, due_date)

    tr_bank = []
    for a in accounts['transaction']:
        tr_bank += get_transactions(a.splits, due_date)

    header = ['Datum', 'Typ', 'Wert', 'Buchungswährung', 'Steuern',
              'Stück', 'ISIN', 'WKN', 'Ticker-Symbol', 'Wertpapiername',
              'Notiz']

    with open('money-market.csv', 'w') as f:
        f_csv = csv.DictWriter(f, header, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        f_csv.writeheader()

        for tr in tr_money:
            if tr not in tr_bank:  # Umbuchung already done
                write_split(f_csv, tr, accounts)


def export_bank(accounts, due_date):
    tr_dividend = get_transactions(accounts['dividend'].splits, due_date)

    tr_investment = []
    for a in accounts['investment'].children:
        tr_investment += get_transactions(a.splits, due_date)

    tr_bank = []
    for a in accounts['transaction']:
        tr_bank += get_transactions(a.splits, due_date)

    header = ['Datum', 'Typ', 'Wert', 'Buchungswährung', 'Steuern',
              'Stück', 'ISIN', 'WKN', 'Ticker-Symbol', 'Wertpapiername',
              'Notiz']

    with open('bank.csv', 'w') as f:
        f_csv = csv.DictWriter(f, header, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        f_csv.writeheader()

        for tr in tr_bank:
            if tr in tr_investment:
                continue
            elif tr in tr_dividend:
                write_dividend(f_csv, tr, accounts)
            else:
                write_transfer(f_csv, tr, accounts)
                write_split(f_csv, tr, accounts)


def main():
    # with piecash.open_book(config.ini['gnc_file'], open_if_lock=True) as book:
    conf = config.configuration()
    conf.read_config()
    conf.open_book()

    export_bank(conf.accounts, conf.due_date)
    export_money(conf.accounts, conf.due_date)
    export_investment(conf.accounts, conf.due_date)

    # export_stocklist(conf.accounts)

    exit()

        # para['due_date'] = dt.datetime.now()

        # save_ini(para)
    return 0


if __name__ == '__main__':
    main()
