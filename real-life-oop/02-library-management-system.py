import uuid
from collections import defaultdict, deque
from typing import List
from datetime import date
from enum import Enum

# Constants
BORROW_LIMIT = 5
BORROW_MAX_DURATION = 5
RESERVE_MAX_DURATION = 3
LATE_FEE_CONSTANT = 900
LATE_FEE_DYNAMIC = 300

# Enums
class BookItemStatus(Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    CHECKED_OUT = "checked-out"

# Exceptions
class BorrowLimitExceeded(Exception):
    def __init__(self):
        super().__init__(f"You have exceeded your borrow limit. Please return some of our books to borrow some more.")
class FullyBookedException(Exception):
    def __init__(self):
        super().__init__(f"All copies of this book are currently taken. Your request has been placed on hold. We will notify you once a copy becomes available.")
class UnpaidBalanceException(Exception):
    def __init__(self):
        super().__init__(f"You have unpaid fees. Please pay up to continue using the library")

class Author:
    def __init__(self, name):
        self.ID = uuid.uuid4()
        self.name = name

class Book:
    def __init__(self, title: str, author: Author, ISBN: str):
        self.title = title
        self.author = author
        self.ISBN = ISBN

class BookItem:
    def __init__(self, book: Book):
        self.ID = uuid.uuid4()
        self.book = book
        self.status = BookItemStatus.AVAILABLE
        self.reserved_at = None
        self.checked_out_at = None
    
    def set_status(self, status: BookItemStatus, current_date: date = None):
        current_date = current_date or date.today()
        
        self.status = status
        match status:
            case BookItemStatus.RESERVED:
                self._set_reserved_date(current_date)
                self._set_check_out_date(None)
            case BookItemStatus.CHECKED_OUT:
                self._set_reserved_date(None)
                self._set_check_out_date(current_date)
            case BookItemStatus.AVAILABLE:
                self._set_reserved_date(None)
                self._set_check_out_date(None)
        
    def _set_reserved_date(self, reserved_at: date):
        self.reserved_at = reserved_at
    def _set_check_out_date(self, checked_out_at: date):
        self.checked_out_at = checked_out_at

class User:
    def __init__(self, name: str, balance: int):
        self.ID = uuid.uuid4()
        self.name = name
        self.__balance = balance
    
    def get_balance(self):
        return self.__balance
    def print_balance(self):
        print(f"Your balance is £{float(self.__balance/100)}")

    def deduct_charges(self, amount):
        self.__balance -= amount

    
class NotificationService:
    def __init__(self):
        pass

    def notify_of_reservation(self, user: User, book: Book):
        print(f"NOTIFIATION: Congratulations {user.name}! You have successfully reserved a copy of this book: ({book.title}). Please drop by for pickup.")

    def notify_of_reservation_elapse(self, user: User, book: Book):
        print(f"NOTIFIATION: Hello {user.name}! Your reservation of ({book.title}) has elapsed.")

    def notify_of_checkout(self, user: User, book: Book):
        print(f"NOTIFIATION: Congratulations {user.name}! You have successfully checked out this book: ({book.title}).")
    
    def notify_of_return(self, user: User, book: Book):
        print(f"NOTIFIATION: Hello {user.name}! Thanks for returning this copy of: ({book.title}).")
    
    def notify_of_overdue_charge(self, user: User, days_overdue: int, late_fees: int):
        print(f"NOTIFIATION: Hello {user.name}! You are {days_overdue} days late. A sum of £{float(late_fees/100)} has been charged to your account in late fees.\n Your balance is £{float(self.__balance/100)}")


class Library:
    def __init__(self, book_items: List[BookItem], borrow_limit: int, borrow_max_duration: int, reserve_max_duration: int, late_fee_constant: int, late_fee_dynamic: int):
        self.borrow_limit = borrow_limit
        self.borrow_max_duration = borrow_max_duration
        self.reserve_max_duration = reserve_max_duration
        self.late_fee_constant, self.late_fee_dynamic = late_fee_constant, late_fee_dynamic
        self.balance = 0
        
        self.notification_service = NotificationService()

        self.book_items = book_items
        self.catalog = defaultdict(list)            # book -> list of book items

        for item in book_items:
            self.catalog[item.book].append(item)
            
        self.bookings = defaultdict(set)       # user -> set of book items
        self.reservations = defaultdict(set)       # user -> set of book items
        self.hold = defaultdict(deque)            # book -> queue of users
        
    
    def search_books(self, searchStr: str) -> List[Book]:
        """
        Search by Book Title, ISBN, or Author Name
        """
        res = []
        for book, _ in self.catalog.items():
            if book.title.startswith(searchStr) or book.ISBN.startswith(searchStr) or book.author.name.startswith(searchStr):
                res.append(book)
        return res
    
    def _find_available_book_copies(self, book: Book) -> BookItem:
        """
        Finds one copy of a book that is available (not checked out or reserved)
        """
        for book_item in self.catalog[book]:
            if book_item.status == BookItemStatus.AVAILABLE:
                return book_item
        
        raise FullyBookedException()

    def _verify_eligibility(self, user: User):
        """
        Verifies that a user hasn't borrowed more books than they're allowed to at a time AND doesn't have a pending unpaid balance
        """
        if len(self.bookings[user]) >= self.borrow_limit:
            raise BorrowLimitExceeded()
        if user.get_balance() < 0:
            raise UnpaidBalanceException()
    
    def _hold_book(self, user: User, book: Book):
        """
        Places a hold on a book for a user (usually when a user tries to reserve or checkout a book that is out of stock.)
        User will be notified once a copy of that book is returned (FIFO basis)
        """
        self.hold[book].append(user)
    
    def _remove_reservation(self, user: User, book_item: BookItem):
        """
        Removes a reservation (usually when the book is reserved past {reserve_max_duration} days without checkout)
        """
        self.reservations[user].remove(book_item)
        self.bookings[user].remove(book_item)
        book_item.set_status(BookItemStatus.AVAILABLE)
        self.notification_service.notify_of_reservation_elapse(user, book_item.book)
    
    def reserve_book(self, user: User, book: Book) -> BookItem:
        """
        Reserves a book for a user, except it's fully booked, then hold.
        """
        self._verify_eligibility(user)
        try:
            book_item = self._find_available_book_copies(book)
            
            self.reservations[user].add(book_item)
            self.bookings[user].add(book_item)
            book_item.set_status(BookItemStatus.RESERVED)

            self.notification_service.notify_of_reservation(user, book)
        except FullyBookedException as e:
            # put on hold
            self._hold_book(user, book)
            return None
        
        return book_item

    def check_out_book(self, user: User, book_item: BookItem):
        """
        Checks out a book for a user, except it's fully booked, then hold.
        Also removes book from reservations if previously reserved
        """

        self._verify_eligibility(user)

        # you didn't reserve AND it's not available (i.e. someone else reserved/checked out)
        if book_item.status != BookItemStatus.AVAILABLE and book_item not in self.reservations[user]:
            # put on hold
            self._hold_book(user, book_item.book)
            return

        if book_item in self.reservations[user]:
            self.reservations[user].remove(book_item)
        
        self.bookings[user].add(book_item)
        book_item.set_status(BookItemStatus.CHECKED_OUT)

        self.notification_service.notify_of_checkout(user, book_item.book)
    
    def return_book(self, user: User, book_item: BookItem):
        """
        Returns books / makes it available for other users.
        Also collects late fees when applicable
        Also reserves the returned book for a user on hold
        """

        if book_item not in self.bookings[user]:
            raise ValueError("You cannot return a book you did not borrow.")
        
        days_overdue = self._calculate_days_overdue(book_item)
        late_fees = self._calculate_late_fees(days_overdue)
        if late_fees:
            self._deduct_late_fees(user, days_overdue, late_fees)
        
        self.bookings[user].remove(book_item)
        book_item.set_status(BookItemStatus.AVAILABLE)

        self._reserve_for_user_on_hold(book_item.book)

        self.notification_service.notify_of_return(user, book_item.book)
    
    def _calculate_days_overdue(self, book_item: BookItem, current_date: date = None):
        """
        Calculates days overdue
        """
        current_date = current_date or date.today()

        borrow_duration = (current_date - book_item.checked_out_at).days
        if borrow_duration < 0:
            raise ValueError("Checkout date cannot be in the future")
        return max(0, borrow_duration - self.borrow_max_duration)

    def _calculate_late_fees(self, days_overdue: int):
        """
        Calculates late fees
        """
        return (days_overdue * self.late_fee_dynamic) + self.late_fee_constant if days_overdue else 0
    
    def _deduct_late_fees(self, user: User, days_overdue: int, amount: int):
        """
        Deducts late fees
        """
        user.deduct_charges(amount)
        self.balance += amount
        self.notification_service.notify_of_overdue_charge(user, days_overdue, amount)
    
    def _reserve_for_user_on_hold(self, book: Book):
        if self.hold[book]:
            new_user = self.hold[book].popleft()
            self.reserve_book(new_user, book)

    def daily_cron(self, current_date: date = None):
        """
        Run as Background task, preferrably at the beginning or end of every day
        Mostly clean-up for reservations / hold
        Removes stale reservations and reserves book for a new user on hold
        """
        current_date = current_date or date.today()

        # clean up reservations
        chopping_block = []
        for user, book_items in self.reservations.items():
            for book_item in book_items:
                if (current_date - book_item.reserved_at).days >= self.reserve_max_duration:
                    chopping_block.append((user, book_item))
        
        for user, book_item in chopping_block:
            self._remove_reservation(user, book_item)
            self._reserve_for_user_on_hold(book_item.book)
    

# ------------------------------------ Testing ------------------------------------
u1 = User("Elijah", 1000)

# Books & Authors
a1 = Author("J. K. Rowling")
a2 = Author("Rick Riordan")
hp1 = Book("Harry Potter and the Sorcerer's Stone", a1, "978-1408855652")
hp2 = Book("Harry Potter and the Chamber of Secrets", a1, "978-0439064866")
hp3 = Book("Harry Potter and the Prisoner of Azkaban", a1, "978-0439136365")
pc1 = Book("Percy Jackson and The Lightning Thief", a2, "978-0307245304")

# Book Items
hp11 = BookItem(hp1)
hp12 = BookItem(hp1)
hp21 = BookItem(hp2)
hp22 = BookItem(hp2)
hp31 = BookItem(hp3)
hp32 = BookItem(hp3)
pc11 = BookItem(pc1)
pc12 = BookItem(pc1)
pc13 = BookItem(pc1)

items = [hp11, hp12, hp21, hp22, hp31, hp32, pc11, pc12, pc13]

# Library
l1 = Library(items, BORROW_LIMIT, BORROW_MAX_DURATION, RESERVE_MAX_DURATION, LATE_FEE_CONSTANT, LATE_FEE_DYNAMIC)

try:
    search_res = l1.search_books("978-0307245304")
    if search_res:
        book_copy = l1.reserve_book(u1, search_res[0])
        l1.check_out_book(u1, book_copy)

    print("-------------------------------------------------------")
    if book_copy:
        l1.return_book(u1, book_copy)
except Exception as e:
    print(f"Error during flow: {str(e)}")
