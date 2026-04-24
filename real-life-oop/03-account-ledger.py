from collections import deque
from typing import Self, List
import uuid
from datetime import datetime
from enum import Enum


class AccountType(Enum):
    CHECKING = "current"
    SAVINGS = "savings"
    ASSET = "asset"     # belongs to the bank

# Exceptions
class NegativeBalanceError(ValueError):
    def __init__(self):
        super().__init__(f"ERROR: Balance cannot be negative.")

class InsufficientFundsError(ValueError):
    def __init__(self):
        super().__init__(f"ERROR: Insufficient Funds.")
    
class InvalidAccountTypeError(ValueError):
    def __init__(self):
        super().__init__(f"ERROR: Invalid account type.")

class UnauthorizedAssetAccountCreationError(Exception):
    def __init__(self):
        super().__init__(f"ERROR: You do not have the permission to create an asset account!")

class TransactionImbalanceError(ValueError):
    def __init__(self):
        super().__init__(f"ERROR: This transaction is imbalanced, and so has been rejected.")

class AccountNotRecognizedError(Exception):
    def __init__(self):
        super().__init__(f"ERROR: Our bank does not recognize this account")


class Account:
    def __init__(self, account_type: AccountType, default_bal=0):
        self._balance = default_bal
        self.account_type = account_type
    
    @property
    def balance(self) -> int:
        return self._balance

    def _set_balance(self, amount: int):
        if amount < 0:
            raise NegativeBalanceError()
        if amount > self.balance:
            raise InsufficientFundsError()
        self._balance = amount
    
    def debit(self, amount: int):
        if self.account_type == AccountType.ASSET:
            self._set_balance(self.balance + amount)
        else:
            self._set_balance(self.balance - amount)
    
    def credit(self, amount: int):
        if self.account_type == AccountType.ASSET:
            self._set_balance(self.balance - amount)
        else:
            self._set_balance(self.balance + amount)

class Entry:
    def __init__(self, account: Account, amount: int, is_debit: bool):
        self.account: Account = account
        self.amount: int = amount
        self.is_debit: bool = is_debit

class EnrichedLedgerEntry:
    def __init__(self, entry: Entry, tx_id: uuid, created_at: datetime):
        self.account: Account = entry.account
        self.amount: int = entry.amount
        self.is_debit: bool = entry.is_debit
        self.tx_id = tx_id
        self.created_at: datetime = created_at

class Transaction:
    def __init__(self, ID: uuid, entries: List[Entry], created_at: datetime):
        self.ID: uuid = ID
        self.entries: List[Entry] = entries
        self.created_at: datetime = created_at
    
    def _is_balanced(self):
        total_debit = sum(e.amount for e in self.entries if e.is_debit)
        total_credit = sum(e.amount for e in self.entries if not e.is_debit)

        return total_credit == total_debit
    
    def post(self):
        if not self._is_balanced():
            raise TransactionImbalanceError()

        for entry in self.entries:
            if entry.is_debit:
                entry.account.debit(entry.amount)
            else:
                entry.account.credit(entry.amount)
    
class Ledger:
    def __init__(self):
        # NOTE: Protect ledger from tampering
        self._debit_ledger: List[EnrichedLedgerEntry] = deque()  
        self._credit_ledger: List[EnrichedLedgerEntry] = deque() 
    
    def _insert_credit_entry(self, transaction_ID: uuid, account: Account, amount: int, created_at: datetime):
        self._credit_ledger.append({
            "ID": transaction_ID,
            "account": account,
            "amount": amount,
            "created_at": created_at
        })
    def _insert_debit_entry(self, transaction_ID: uuid, account: Account, amount: int, created_at: datetime):
        self._debit_ledger.append({
            "ID": transaction_ID,
            "account": account,
            "amount": amount,
            "created_at": created_at
        })
    
    def create_transaction(self, amount: int, debit_account: Account, credit_account: Account, created_at: datetime) -> Transaction:
        tx_id = uuid.uuid4()
        
        return Transaction(
            tx_id, 
        [
            Entry(debit_account, amount, True),
            Entry(credit_account, amount, False)
        ], 
        created_at
        )

    def record_transaction(self, tx: Transaction):
        for entry in tx.entries:
            if entry.is_debit:
                self._debit_ledger.append(EnrichedLedgerEntry(entry, tx.ID, tx.created_at))
            else:
                self._credit_ledger.append(EnrichedLedgerEntry(entry, tx.ID, tx.created_at))
    
    def create_reverse_transaction(self, tx: Transaction, created_at: datetime):
        new_tx_id = uuid.uuid4()
        
        return Transaction(
            new_tx_id,
            [Entry(e.account, e.amount, not e.is_debit) for e in tx.entries], 
            created_at
        )
                


class Bank:
    def __init__(self):
        self.ledger = Ledger()
        self.asset_account = Account(AccountType.ASSET)
        self.customer_accounts = set()
    
    def create_account(self, account_type: AccountType) -> Account:
        if not isinstance(account_type, AccountType):
            raise InvalidAccountTypeError()
        if account_type == AccountType.ASSET:
            raise UnauthorizedAssetAccountCreationError()
        
        new_acct = Account(account_type)
        self.customer_accounts.add(new_acct)
        return new_acct

    def _verify_account_is_customer(self, account: Account):
        if account not in self.customer_accounts:
            raise AccountNotRecognizedError()

    # main user transaction types
    def deposit(self, credit_account: Account, amount: int, created_at: datetime):
        self._verify_account_is_customer()
        
        tx = self.ledger.create_transaction(amount, self.asset_account, credit_account, created_at)
        tx.post()
        self.ledger.record_transaction(tx)
    def withdraw(self, debit_account: Account, amount: int, created_at: datetime):
        self._verify_account_is_customer()

        tx = self.ledger.create_transaction(amount, debit_account, self.asset_account, created_at)
        tx.post()
        self.ledger.record_transaction(tx)
    def transfer(self, debit_account: Account, credit_account: Account, amount: int, created_at: datetime):
        self._verify_account_is_customer()

        tx = self.ledger.create_transaction(amount, debit_account, credit_account, created_at)
        tx.post()
        self.ledger.record_transaction(tx)
    
    def reverse_transaction(self, tx: Transaction):
        new_tx = self.ledger.create_reverse_transaction(tx, datetime.now())
        new_tx.post()
        self.ledger.record_transaction(new_tx)


# Testing
eBank = Bank()

eliCheckingAcct = eBank.create_account(AccountType.CHECKING)
eBank.deposit(eliCheckingAcct, 50000, datetime.now())
