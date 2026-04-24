from dataclasses import dataclass
from typing import List

COINS_MAP = frozenset([25,50,100,200])
DENOMS = [200, 100, 50, 25]

# Custom Exceptions
class OutOfStockError(Exception):
    def __init__(self, snack_SKU):
        super().__init__(f"Out of stock! There are no item with SKU {snack_SKU} in stock")
class InsufficientSnacksError(Exception):
    def __init__(self, snack_SKU, qty_available):
        super().__init__(f"Insufficient {snack_SKU}s. There are only {qty_available} items with SKU {snack_SKU} available")
class InsufficientFundsError(Exception):
    def __init__(self, shortfall):
        super().__init__(f"Insufficient funds! You need £{shortfall} more to buy this item")
class InsufficientChangeError(Exception):
    def __init__(self):
        super().__init__("Insufficient Change")

# Snack Classes and Subclasses
class Snack:
    def __init__(self, price: int):
        self.SKU = "SNACK"
        self.price = price  # price in p

    @staticmethod
    def generate_SKU(name, variant, price):
        return f"{name.upper()}-{variant.upper()}-{price}"

class Chocolate(Snack):
    def __init__(self, price: int, variant: str):
        self.price = price  # price in p
        self.variant = variant
        self.SKU = Snack.generate_SKU(self.__class__.__name__, variant, price)
        
class Coke(Snack):
    def __init__(self, price: int):
        self.price = price  # price in p
        self.SKU = Snack.generate_SKU(self.__class__.__name__, "", price)

# Coin Class
class Coin:
    def __init__(self, val):
        if val not in COINS_MAP:
            raise ValueError("Invalid coin value")
        self.val = val

# VendingMachine Class
class VendingMachine:
    def __init__(self, inventory):
        from collections import Counter

        self.inventory = inventory
        self._coin_balance = Counter({200: 20, 100: 20, 50: 20, 25: 0})     # denom -> count (Bank)
        self._temp_coin_balance = Counter({200: 0, 100: 0, 50: 0, 25: 0})   # denom -> count (Temporary store)
    
    def _verify_stock(self, snack_SKU: str, qty: int):
        """
        Verifies we have sufficient stock of a given snack to fulfil an order
        """
        qty_available = self.inventory.get(snack_SKU, 0)
        if not qty_available:
            raise OutOfStockError(snack_SKU)
        if qty_available < qty:
            raise InsufficientSnacksError(snack_SKU, qty_available)
    
    def _verify_balance_eligibility(self, snack: Snack, qty) -> int:
        """
        Verifies the client has put in sufficient money to fulfil an order
        """
        temp_bal, amount_required = self._calculate_temp_balance(), snack.price*qty
        change = temp_bal - amount_required

        if change < 0:
            raise InsufficientFundsError(float(abs(change)/100))
        return change
    
    def _calculate_change_coins(self, change: int) -> Counter:
        """
        Calculates the no. of coins of each denomination needed to give change. Raises an exception if insufficient
        """
        from collections import Counter

        res = Counter()
        for d in DENOMS:
            coins_needed = change // d
            totalDenomBalance = self._coin_balance[d] + self._temp_coin_balance[d]
            if coins_needed and totalDenomBalance:
                res[d] = min(coins_needed, totalDenomBalance)
                change -= (min(coins_needed, totalDenomBalance)*d)

            if change == 0:
                break
        
        if change > 0:
            raise InsufficientChangeError()

        return res


    def _calculate_temp_balance(self) -> int:
        return sum(denom * qty for denom, qty in self._temp_coin_balance.items())
    
    def _persist_temp_balance(self):
        for d in DENOMS:
            self._coin_balance[d] += self._temp_coin_balance[d]
    
    def _reset_temp_balance(self):
        for d in DENOMS:
            self._temp_coin_balance[d] = 0
    
    def buy_snack(self, snack: Snack, qty: int) -> List[Coin]:
        from collections import Counter
        
        change_counter = Counter()
        try:
            # Validation 
            self._verify_stock(snack.SKU, qty)
            change = self._verify_balance_eligibility(snack, qty)
            change_counter = self._calculate_change_coins(change)
        except (OutOfStockError, InsufficientSnacksError, InsufficientFundsError, InsufficientChangeError, ) as e:
            # eject coins
            print(f"Unable to make purchase. Error: {str(e)}")
            return self._eject_coins(self._temp_coin_balance, self._temp_coin_balance)

        # store and reset temp balance
        self._persist_temp_balance()
        self._reset_temp_balance()
        
        self.inventory[snack.SKU] -= qty
        print(f"You have succesfully purchased {qty} items with SKU {snack.SKU}. Your change is £{float(change/100)}.")

        return VendingMachine._eject_coins(change_counter, self._coin_balance)

    def insert_coin(self, coin: Coin):
        self._temp_coin_balance[coin.val] += 1

    @staticmethod
    def _eject_coins(eject_counter: Counter, coin_counter: Counter) -> List[Coin]:
        # eject_counter -> number of coins to eject
        # coin_counter -> counter that gets decremented

        coins = []
        for d, count in eject_counter.items():
            for _ in range(count):
                coins.append(Coin(d))
            coin_counter[d] -= count
        return coins


print("------------------------------------------------------------------------\n")
s1 = Chocolate(50, "white")
s2 = Chocolate(75, "black")
s3 = Coke(125)

inventory = {}
SNACKS: List[Snack] = [s1,s2, s3]
for snack in SNACKS:
    inventory[snack.SKU] = 10

print(inventory)

vMachine = VendingMachine(inventory)

try:
    vMachine.insert_coin(Coin(100))
    vMachine.insert_coin(Coin(50))
    print(vMachine.buy_snack(s2, 1))
except Exception as e:
    print(f"Unable to make purchase. Error: {str(e)}")

print("------------------------------------------------------------------------\n")