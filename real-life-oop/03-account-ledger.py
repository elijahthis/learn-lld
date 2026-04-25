from collections import deque, defaultdict
from typing import Self, List
import uuid
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field, InitVar
import threading


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

class InvalidAmountError(ValueError):
    def __init__(self):
        super().__init__(f"ERROR: Amount cannot be negative.")
    
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

@dataclass(frozen=True)
class Account:
    account_type: AccountType
    name: str
    ID: uuid.UUID = field(default_factory=uuid.uuid4)

    def __hash__(self):
        return hash(self.ID)
    def __eq__(self, account):
        return isinstance(account, Account) and account.ID == self.ID
        

class NotificationService:
    def __init__(self):
        pass

    def account_creation_alert(self, account: Account):
        print(f"NOTIFICATION: Hello {account.name}. Welcome! Your {account.account_type} account has been successfully created with us.")
        
    def credit_alert(self, account: Account, amount: int):
        print(f"CREDIT SUCCESSFUL: Your account has been credited with a sum of £{float(amount/100):.2f}")
    
    def debit_alert(self, account: Account, amount: int):
        print(f"DEBIT SUCCESSFUL: Your account has been debited of a sum of £{float(amount/100):.2f}")
    
    def balance_alert(self, account: Account, balance: int):
        print(f"ACCOUNT BALANCE: Hello {account.name}! Your account balance is £{float(balance/100):.2f}")

@dataclass(frozen=True)
class Entry:
    account: Account
    amount: int
    is_debit: bool
    

@dataclass(frozen=True)
class EnrichedLedgerEntry:
    account: Account = field(init=False)
    amount: int = field(init=False)
    is_debit: bool = field(init=False)
    tx_id: uuid.UUID
    created_at: datetime

    entry: InitVar[Entry]
    
    def __post_init__(self, entry: Entry):
        object.__setattr__(self, "account", entry.account)
        object.__setattr__(self, "amount", entry.amount)
        object.__setattr__(self, "is_debit", entry.is_debit)


@dataclass(frozen=True)
class Transaction:
    entries: List[Entry]
    created_at: datetime
    ID: uuid.UUID = field(default_factory=uuid.uuid4)
    
    def _is_balanced(self):
        total_debit = sum(e.amount for e in self.entries if e.is_debit)
        total_credit = sum(e.amount for e in self.entries if not e.is_debit)

        return total_credit == total_debit
    
    
class Ledger:
    def __init__(self):
        # NOTE: Protect ledger from tampering
        self._ledger: List[EnrichedLedgerEntry] = []
        self._processed_tx_ids = set()
        self.notification_service: NotificationService = NotificationService()

        self.balance_checkpoint: int = 0
        self.balance_snapshot = defaultdict(int)      # {account_id -> balance} to be updated everyday 
    
    def create_transaction(self, amount: int, debit_account: Account, credit_account: Account, created_at: datetime) -> Transaction:
        tx_id = uuid.uuid4()
        
        return Transaction(
            ID=tx_id, 
            entries=[
                Entry(account=debit_account, amount=amount, is_debit=True),
                Entry(account=credit_account, amount=amount, is_debit=False)
            ], 
            created_at=created_at
        )
    
    def create_reverse_transaction(self, tx: Transaction, created_at: datetime) -> Transaction:
        new_tx_id = uuid.uuid4()
        
        return Transaction(
            ID=new_tx_id,
            entries=[Entry(account=e.account, amount=e.amount, is_debit=(not e.is_debit)) for e in tx.entries], 
            created_at=created_at
        )
    
    def _send_alert(self, entry: Entry):
        if entry.is_debit:
            self.notification_service.debit_alert(entry.account, entry.amount)
        else:
            self.notification_service.credit_alert(entry.account, entry.amount)
    
    def commit(self, tx: Transaction):
        if tx.ID in self._processed_tx_ids:
            return
        
        if not tx._is_balanced():
            raise TransactionImbalanceError()
        
        enriched_entries = [EnrichedLedgerEntry(entry=entry, tx_id=tx.ID, created_at=tx.created_at) for entry in tx.entries]
        self._ledger.extend(enriched_entries)
        self._processed_tx_ids.add(tx.ID)
        
        for entry in tx.entries:
            self._send_alert(entry)
    
    def calculate_account_balance(self, account: Account) -> int:
        bal = self.balance_snapshot[account.ID]
        
        total_debits = total_credits = 0
        for entry in self._ledger[self.balance_checkpoint:]:
            if entry.account == account:
                if entry.is_debit:
                    total_debits += entry.amount
                else:
                    total_credits += entry.amount
        
        bal_update = total_debits - total_credits if account.account_type == AccountType.ASSET else total_credits - total_debits
        return bal + bal_update

    def _cache_balance_snapshot(self):
        for entry in self._ledger[self.balance_checkpoint:]:
            if entry.account.account_type == AccountType.ASSET:
                if entry.is_debit:
                    self.balance_snapshot[entry.account.ID] += entry.amount
                else:
                    self.balance_snapshot[entry.account.ID] -= entry.amount
            else:
                if entry.is_debit:
                    self.balance_snapshot[entry.account.ID] -= entry.amount
                else:
                    self.balance_snapshot[entry.account.ID] += entry.amount
        
        self.balance_checkpoint = len(self._ledger)

    def daily_cron(self):
        self._cache_balance_snapshot()


class Bank:
    def __init__(self):
        self.ledger = Ledger()
        self.asset_account = Account(account_type=AccountType.ASSET, name="Bank Assets")
        self._customer_account_ids = set()
        self.notification_service = NotificationService()
        self.tx_lock = threading.Lock()
    
    def create_account(self, account_type: AccountType, name: str) -> Account:
        if not isinstance(account_type, AccountType):
            raise InvalidAccountTypeError()
        if account_type == AccountType.ASSET:
            raise UnauthorizedAssetAccountCreationError()
        
        new_acct = Account(account_type=account_type, name=name)
        self._customer_account_ids.add(new_acct.ID)

        self.notification_service.account_creation_alert(new_acct)
        
        return new_acct
    
    def _get_account_balance(self, account: Account) -> int:
        return self.ledger.calculate_account_balance(account)
    
    def print_account_balance(self, account: Account):
        bal = self._get_account_balance(account)
        self.notification_service.balance_alert(account, bal)

    def _verify_account_is_customer(self, account: Account):
        if account.ID not in self._customer_account_ids:
            raise AccountNotRecognizedError()
    
    def _verify_balance_eligibility(self, account: Account, amount: int):
        bal = self._get_account_balance(account)
        if bal < amount:
            raise InsufficientFundsError()
    
    def _verify_amount(self, amount: int):
        if not isinstance(amount, int) or amount < 1:
            raise InvalidAmountError()

    # main user transaction types
    def deposit(self, credit_account: Account, amount: int, created_at: datetime = None):
        created_at = created_at or datetime.now()
        
        self._verify_account_is_customer(credit_account)
        self._verify_amount(amount)
        
        with self.tx_lock:
            tx = self.ledger.create_transaction(amount, self.asset_account, credit_account, created_at)
            self.ledger.commit(tx)

    def withdraw(self, debit_account: Account, amount: int, created_at: datetime = None):
        created_at = created_at or datetime.now()

        self._verify_account_is_customer(debit_account)
        self._verify_amount(amount)

        with self.tx_lock:
            self._verify_balance_eligibility(debit_account, amount)
            tx = self.ledger.create_transaction(amount, debit_account, self.asset_account, created_at)
            self.ledger.commit(tx)
        
    def transfer(self, debit_account: Account, credit_account: Account, amount: int, created_at: datetime = None):
        created_at = created_at or datetime.now()
        
        self._verify_account_is_customer(debit_account)
        self._verify_account_is_customer(credit_account)
        self._verify_amount(amount)

        with self.tx_lock:
            self._verify_balance_eligibility(debit_account, amount)
            tx = self.ledger.create_transaction(amount, debit_account, credit_account, created_at)
            self.ledger.commit(tx)
    
    def reverse_transaction(self, tx: Transaction):
        with self.tx_lock:
            new_tx = self.ledger.create_reverse_transaction(tx, datetime.now())
            self.ledger.commit(new_tx)



# Testing
eBank = Bank()

eliCheckingAcct = eBank.create_account(AccountType.CHECKING, "Elijah")
eliSavingsAcct = eBank.create_account(AccountType.SAVINGS, "Elijah")

print("-----------------------------------")
eBank.deposit(eliCheckingAcct, 50000)
eBank.deposit(eliSavingsAcct, 50000)
eBank.transfer(eliCheckingAcct, eliSavingsAcct, 30000)
# eBank.withdraw(eliCheckingAcct, 50000)

print("-----------------------------------")
eBank.print_account_balance(eliCheckingAcct)
eBank.print_account_balance(eliSavingsAcct)
eBank.print_account_balance(eBank.asset_account)

print("-----------------------------------")
eBank.ledger.daily_cron()

