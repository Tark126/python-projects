from aiogram.fsm.state import State, StatesGroup

class OrderState(StatesGroup):
    waiting_for_promo = State()
    waiting_for_payment = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

class ReviewState(StatesGroup):
    waiting_for_rating = State()
    waiting_for_comment = State()
