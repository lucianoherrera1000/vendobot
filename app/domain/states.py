from enum import Enum


class ConversationState(str, Enum):
    NEW = "NEW"
    GREETING = "GREETING"
    AWAITING_ORDER = "AWAITING_ORDER"
    ASK_DELIVERY = "ASK_DELIVERY"
    ASK_ADDRESS = "ASK_ADDRESS"
    ASK_PAYMENT = "ASK_PAYMENT"
    ASK_NAME = "ASK_NAME"
    ASK_CONFIRM = "ASK_CONFIRM"
    DONE = "DONE"
