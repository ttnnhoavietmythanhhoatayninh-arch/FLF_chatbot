from decimal import Decimal, InvalidOperation

class BudgetError(RuntimeError):pass

def money(x):
    try:v=Decimal(str(x))
    except (InvalidOperation,ValueError):raise BudgetError('Invalid cost')
    if not v.is_finite() or v<0:raise BudgetError('Invalid cost')
    return v

class Budget:
    def __init__(self,limit='0.09'):
        self.limit=money(limit)
        if not 0<self.limit<=Decimal('0.10'):raise BudgetError('Budget must be positive and <=0.10 USD per query')
        self.spent=Decimal(0);self._reservations={};self._next=0
    def reserve(self,amount):
        amount=money(amount)
        if self.spent+sum(self._reservations.values())+amount>self.limit:
            raise BudgetError('Per-question budget exhausted before request')
        self._next+=1;self._reservations[self._next]=amount;return self._next
    def settle(self,token,actual):
        reserved=self._reservations.pop(token)
        actual=reserved if actual is None else money(actual)
        self.spent+=actual
        if self.spent>self.limit:raise BudgetError('Recorded cost exceeded configured budget')
